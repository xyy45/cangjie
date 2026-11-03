from copy import deepcopy
import pytest
from nexus.contracts import CandidateProposal, file_hash, tree_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.store import RunStore
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def bound_task(tmp_path):
    store=RunStore(tmp_path)
    service=RequirementService(store)
    source=ROOT/'fixtures/order-demo-bug'
    ws=WorkspaceStore(tmp_path,registered=[source])
    baseline=ws.import_project(source,'.')
    draft=service.prepare_requirement('order-demo-bug','Fix quantity, retain price and total')
    spec=service.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=1,
        requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='local-user')
    task=service.prepare_task('order-demo-bug',spec.id,baseline)
    with store.connect() as db:
        db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    return store,service,ws,task


def test_v11_task_binds_original_confirmed_spec_baseline_and_plan(tmp_path):
    store,service,ws,task=bound_task(tmp_path)
    assert task.schema_version==2
    spec,plan=service.task_context(task)
    assert task.goal==spec.source_text
    assert task.allowed_paths==spec.allowed_paths
    assert task.spec_hash==spec.spec_hash and task.verification_plan_hash==plan.plan_hash
    assert plan.baseline_hash==tree_hash(ws.subject_path(task.baseline_id))
    assert store.get_task(task.id)==task


def test_candidate_requirement_refs_and_plan_binding_are_enforced(tmp_path):
    store,service,ws,task=bound_task(tmp_path)
    content=ws.read_file(task.baseline_id,'src/quantity.cj')
    def proposal(refs):
        return CandidateProposal(edits=[dict(path='src/quantity.cj',before_hash=file_hash(content),
            content=content+'\n// candidate\n')],requirement_refs=refs)
    for refs in (['goal'],['REQ-NOT-REGISTERED'],['REQ-QTY','REQ-QTY']):
        with pytest.raises(ValueError):ws.apply_candidate(task,proposal(refs))
    assert store.get_task(task.id).attempt_count==0
    candidate=ws.apply_candidate(task,proposal(['REQ-QTY']))
    assert candidate.schema_version==2
    assert candidate.spec_hash==task.spec_hash and candidate.verification_plan_hash==task.verification_plan_hash


def test_unknown_task_schema_and_changed_bound_goal_are_rejected(tmp_path):
    import json
    store,service,ws,task=bound_task(tmp_path)
    with store.connect() as db:
        data=task.model_dump();data['schema_version']=99
        db.execute('UPDATE tasks SET payload=? WHERE id=?',(json.dumps(data),task.id))
    with pytest.raises(ValueError):store.get_task(task.id)
    with store.connect() as db:
        data=task.model_dump();data['goal']='silently different requirements'
        db.execute('UPDATE tasks SET payload=? WHERE id=?',(json.dumps(data),task.id))
    with pytest.raises(ValueError,match='binding'):service.task_context(store.get_task(task.id))


def test_real_mcp_bound_context_requires_task_and_excludes_verification_only(tmp_path):
    import asyncio,json
    from nexus.contracts import digest
    from nexus.mcp.client import ToolClient
    store,service,ws,task=bound_task(tmp_path)
    plan=service.get_plan(task.verification_plan_id)
    # Trusted maintainer profile fixture, not a model-supplied visibility override.
    data=plan.model_dump(exclude={'plan_hash'})
    data['context_visibility']['src/order_test.cj']='VERIFICATION_ONLY'
    data['plan_hash']=digest(data)
    with store.connect() as db:
        db.execute('UPDATE verification_plans SET payload=? WHERE id=?',(json.dumps(data),plan.id))
        changed=task.model_dump();changed['verification_plan_hash']=data['plan_hash']
        db.execute('UPDATE tasks SET payload=? WHERE id=?',(json.dumps(changed),task.id))
    async def run():
        async with ToolClient(tmp_path) as client:
            args=dict(task_id=task.id,request_id='visibility',baseline_id=task.baseline_id)
            listed=await client.call_tool('workspace.list_files',args)
            assert listed.operation_status=='OK'
            assert 'src/order_test.cj' not in [f['path'] for f in listed.data['files']]
            read=await client.call_tool('workspace.read_file',dict(**args,path='src/order_test.cj'))
            assert read.operation_status=='ERROR'
            missing_task=await client.call_tool('workspace.read_file',dict(baseline_id=task.baseline_id,path='src/order_test.cj'))
            assert missing_task.operation_status=='ERROR'
            searched=await client.call_tool('workspace.search',dict(**args,query='@Expect'))
            assert searched.operation_status=='OK' and searched.data['matches']==[]
            production=await client.call_tool('workspace.read_file',dict(**args,path='src/quantity.cj'))
            assert production.operation_status=='OK'
    asyncio.run(run())
