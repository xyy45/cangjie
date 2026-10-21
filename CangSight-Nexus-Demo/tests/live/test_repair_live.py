import asyncio
import hashlib
import json
import time
from pathlib import Path
import pytest
from nexus.execution.workspace import WorkspaceStore
from nexus.repair.cegis_loop import RepairLoop
from nexus.store import RunStore, uid
from nexus.requirements.service import RequirementService
from nexus.execution.delivery import DeliveryService
from nexus.mcp.client import ToolClient
from nexus.policy.client import PolicyClient
from nexus.contracts import digest, source_manifest, tree_hash

pytestmark = pytest.mark.live
ROOT = Path(__file__).resolve().parents[2]


def test_live_main_case():
    root = ROOT / '.runtime/live' / uid()
    source = ROOT / 'fixtures/order-demo-bug'
    baseline = WorkspaceStore(root, registered=[source]).import_project(source, '.')
    store = RunStore(root)
    service = RequirementService(store)
    draft = service.prepare_requirement('order-demo-bug',
        'Fix order validation. Quantity must be 1–1000; unit price 0–1000000. Invalid inputs return -1. '
        'Valid order total is quantity multiplied by unit price. Preserve all frozen tests.')
    spec = service.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=draft['version'],
        requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='LIVE_TEST_OPERATOR')
    task = service.prepare_task('order-demo-bug',spec.id,baseline)
    with store.connect() as db:
        db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    result = asyncio.run(RepairLoop(store).run(task.id))
    assert result.status == 'REVIEW_PENDING', f'LIVE {result.status}; records: {root}'
    calls = store.records(task.id, 'model_call')
    assert any(c['origin'] == 'LIVE' and c['status'] == 'SUCCEEDED' for c in calls)
    selected=[event['selected_candidate_id'] for event in store.records(task.id,'event') if 'selected_candidate_id' in event][-1]
    ws=WorkspaceStore(root)
    original=source_manifest(ws.verify_baseline(baseline))
    async def protection_and_export():
        # D is a hand-written protection probe, not model-generated malicious code.
        content=ws.read_file(baseline,'src/order_test.cj')
        proposal=dict(edits=[dict(path='src/order_test.cj',before_hash=hashlib.sha256(content.encode()).hexdigest(),
            content=content+'\n// forbidden test edit\n')],requirement_refs=['REQ-QTY'])
        async with ToolClient(root) as client:
            denied=await client.call_tool('candidate.apply',dict(task_id=task.id,proposal=proposal))
            assert denied.operation_status=='ERROR'
            native=await PolicyClient(ROOT).decide(dict(schema_version=1,policy_version='1.1',
                action='candidate.apply',task_id=task.id,request_id=uid(),paths=['src/order_test.cj'],
                input_tree_hash=tree_hash(ws.verify_baseline(baseline)),arguments_hash=digest(proposal),
                remaining_budget=3-result.attempt_count,accepted=False,approval_binding='',
                deadline_at=int(time.time()*1000)+30000))
            assert native['decision']=='Deny' and native['reason']=='PROTECTED_PATH'
            assert source_manifest(ws.verify_baseline(baseline))==original
            store.append_record(task.id,'event',dict(protection_probe=dict(origin='HAND_WRITTEN_PROBE',
                mcp_error=denied.error,native_decision=native,baseline_unchanged=True)))
            delivery=DeliveryService(store)
            # Explicit test-operator approval, not evidence of independent human reproduction.
            approval=delivery.accept(selected,delivery.check_set_hash(selected),actor_id='LIVE_TEST_OPERATOR')
            exported=await client.call_tool('candidate.export',dict(task_id=task.id,candidate_id=selected,
                acceptance_id=approval.id))
            assert exported.operation_status=='OK' and exported.data['status']=='DELIVERED',exported
            artifact=delivery.verify_archive(exported.data['export_id'],approval)
            return exported.data,artifact
    exported,artifact=asyncio.run(protection_and_export())
    summary=dict(schema_version=1,origin='LIVE',task_id=task.id,candidate_id=selected,
        status=store.get_task(task.id).status,attempts=result.attempt_count,
        model_calls=[call for call in calls if call['status']!='STARTED'],
        approval_actor='LIVE_TEST_OPERATOR',independent_human_reproduction='PENDING',
        protection_probe_origin='HAND_WRITTEN_PROBE',export_id=exported['export_id'],
        archive=str(artifact),archive_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
    (root/'validation-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print('LIVE validation records: '+str(root))
