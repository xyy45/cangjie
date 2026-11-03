"""Real MCP/Policy/SDK binding regression. Candidate is explicitly hand-written."""
import asyncio
import json
import hashlib
import zipfile
from pathlib import Path
import pytest
from nexus.contracts import AcceptanceRecord, CandidateRecord, file_hash
from nexus.execution.delivery import DeliveryService
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient
from nexus.requirements.service import RequirementService
from nexus.store import RunStore

pytestmark=pytest.mark.sdk
ROOT=Path(__file__).resolve().parents[2]


def test_v11_confirmed_requirement_real_checks_and_delivery_reject_changed_report(tmp_path):
    store=RunStore(tmp_path)
    service=RequirementService(store)
    fixture=ROOT/'fixtures/order-demo-bug'
    ws=WorkspaceStore(tmp_path,registered=[fixture])
    baseline=ws.import_project(fixture,'.')
    draft=service.prepare_requirement('order-demo-bug','Fix quantity; keep price and totals')
    spec=service.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=1,
        requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='HAND_WRITTEN_SDK_OPERATOR')
    task=service.prepare_task('order-demo-bug',spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    content=ws.read_file(baseline,'src/quantity.cj')
    async def run():
        async with ToolClient(tmp_path) as client:
            async def call(name,**args):
                result=await client.call_tool(name,dict(task_id=task.id,request_id=name,**args))
                assert result.operation_status=='OK',result
                return result.data
            diagnosed=await call('project.diagnose',subject_id=baseline)
            assert diagnosed['build']['state']=='PASS' and diagnosed['test']['state']=='FAIL'
            assert diagnosed['test']['suite_results']['order-target']['state']=='FAIL'
            candidate=CandidateRecord.model_validate(await call('candidate.apply',proposal=dict(
                edits=[dict(path='src/quantity.cj',before_hash=file_hash(content),
                            content=content.replace('quantity >= 0','quantity >= 1'))],requirement_refs=['REQ-QTY'])))
            assert candidate.spec_hash==spec.spec_hash and candidate.schema_version==2
            args=dict(candidate_id=candidate.id,expected_tree_hash=candidate.tree_hash)
            for kind in ('build','test'):
                check=await call('candidate.'+kind,**args)
                assert check['state']=='PASS' and check['duration_ms']>=0
                assert check['argv']==(['cjpm','build','-V'] if kind=='build' else ['cjpm','test'])
                assert check['spec_hash']==task.spec_hash and check['verification_plan_hash']==task.verification_plan_hash
                assert json.loads((tmp_path/check['report_ref']).read_text())==check
                if kind=='test':assert all(s['state']=='PASS' for s in check['suite_results'].values())
            return candidate,check
    candidate,check=asyncio.run(run())
    store.update_task(task.id,status='REVIEW_PENDING')
    store.append_record(task.id,'event',{'selected_candidate_id':candidate.id,'origin':'HAND_WRITTEN_SDK_TEST'})
    delivery=DeliveryService(store)
    from nexus.web.app import create_app
    from nexus.repair.cegis_loop import RepairLoop
    app=create_app(store,RepairLoop(store),delivery,operator_key='d'*64)
    app.config['RUN_TASKS']=False
    web=app.test_client();web.get('/')
    with web.session_transaction() as session:
        actor=session['actor_id'];token=session['csrf']
    headers={'Origin':'http://localhost','X-CSRF-Token':token}
    assert web.post('/api/operator/authorize',json={'key':'d'*64},headers=headers).status_code==200
    response=web.post('/api/candidates/'+candidate.id+'/accept',headers=headers,json=dict(
        check_set_hash=delivery.check_set_hash(candidate.id),task_revision=store.get_task(task.id).revision))
    assert response.status_code==200,response.json
    acceptance=AcceptanceRecord.model_validate(response.json)
    assert acceptance.schema_version==2 and acceptance.actor_id==actor
    assert acceptance.allowed_action=='candidate.export' and acceptance.spec_hash==spec.spec_hash
    with pytest.raises(ValueError,match='another local session'):
        delivery.acceptance(candidate.id,acceptance.id,actor_id='other-user')
    native_request=tmp_path/store.records(task.id,'tool_call')[0]['request_ref']
    original_request=native_request.read_bytes()
    native_request.unlink()
    try:
        with pytest.raises(FileNotFoundError):delivery.export(candidate.id,acceptance.id)
        assert list((tmp_path/'exports').glob('*.zip'))==[]
    finally:native_request.write_bytes(original_request)
    async def export_via_mcp():
        async with ToolClient(tmp_path) as client:
            args=dict(task_id=task.id,candidate_id=candidate.id,acceptance_id=acceptance.id,request_id='v11-export')
            first=await client.call_tool('candidate.export',args)
            assert first.operation_status=='OK',first
            repeated=await client.call_tool('candidate.export',args)
            assert repeated.operation_status=='OK' and repeated.data['export_id']==first.data['export_id'],repeated
            return first.data
    exported=asyncio.run(export_via_mcp())
    assert exported['status']=='DELIVERED'
    artifact=delivery.verify_archive(exported['export_id'],acceptance)
    downloaded=web.get('/downloads/'+exported['export_id'])
    assert downloaded.status_code==200 and downloaded.data==artifact.read_bytes()
    repeated_http=web.post('/api/candidates/'+candidate.id+'/export',headers=headers,
        json={'acceptance_id':acceptance.id})
    assert repeated_http.status_code==200 and repeated_http.json['export_id']==exported['export_id'],repeated_http.json
    with zipfile.ZipFile(artifact) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        assert manifest['project_tree_hash']==candidate.tree_hash
        for name,identity in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==identity
        assert archive.read('project/src/quantity.cj')==(ws.subject_path(candidate.id)/'src/quantity.cj').read_bytes()
        assert archive.read('evidence/changes.diff')==ws.diff(candidate.id).encode()
        assert json.loads(archive.read('evidence/requirements.json'))['spec']['spec_hash']==spec.spec_hash
        sessions=json.loads(archive.read('evidence/sessions.json'))
        assert sessions['model_evidence']=='NO_MODEL_CALL_RECORDED'
        assert sessions['native_records'] and sessions['mcp_operations']
        approval=json.loads(archive.read('evidence/acceptance.json'))
        assert approval['export_id']==exported['export_id'] and approval['consumption_state']=='RESERVED'
        assert not any('.env' in name or '/target/' in name or '/.git/' in name for name in archive.namelist())
    with store.connect() as db:
        receipt=db.execute('SELECT archive_hash FROM export_artifacts WHERE export_id=?',(exported['export_id'],)).fetchone()
    assert receipt[0]==hashlib.sha256(artifact.read_bytes()).hexdigest()
    original_archive=artifact.read_bytes()
    with zipfile.ZipFile(artifact,'a') as archive:archive.writestr('unexpected.txt','changed')
    with pytest.raises(ValueError):delivery.verify_archive(exported['export_id'],acceptance)
    artifact.write_bytes(original_archive)
    assert delivery.verify_archive(exported['export_id'],acceptance)==artifact
    (tmp_path/check['report_ref']).write_text('{}')
    with pytest.raises(ValueError,match='report content changed'):
        delivery.export(candidate.id,acceptance.id)


def test_v11_real_fail_feedback_reaches_next_proposal_with_confirmed_requirements(tmp_path):
    from nexus.contracts import CandidateProposal
    from nexus.repair.cegis_loop import RepairLoop
    store=RunStore(tmp_path)
    service=RequirementService(store)
    fixture=ROOT/'fixtures/order-demo-bug'
    ws=WorkspaceStore(tmp_path,registered=[fixture])
    baseline=ws.import_project(fixture,'.')
    draft=service.prepare_requirement('order-demo-bug','Fix boundary and keep all registered behavior')
    spec=service.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=1,
        requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='DETERMINISTIC_SDK_TEST')
    task=service.prepare_task('order-demo-bug',spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,'src/quantity.cj')
    contexts=[]
    class DeterministicProposals:
        # This replaces only candidate generation. It is NOT a LIVE model test.
        async def propose(self,context):
            contexts.append(context)
            assert context['requirements']['spec_hash']==spec.spec_hash
            assert 'confirmed_by' not in context['requirements']
            lower='-1' if len(contexts)==1 else '1'
            return CandidateProposal(edits=[dict(path='src/quantity.cj',before_hash=file_hash(original),
                content=original.replace('quantity >= 0','quantity >= '+lower))],requirement_refs=['REQ-QTY'])
    result=asyncio.run(RepairLoop(store,provider_factory=lambda *_:DeterministicProposals()).run(task.id))
    assert result.status=='REVIEW_PENDING' and result.attempt_count==2
    assert len(contexts)==2
    feedback=contexts[1]['feedback'][0]
    assert '+    quantity >= -1' in feedback['diff']
    assert feedback['edited_files'][0]['content']==original.replace('quantity >= 0','quantity >= -1')
    assert feedback['edited_files'][0]['before_hash']==file_hash(original)
    assert feedback['failed_checks'][0]['state']=='FAIL'
    assert feedback['requirement_refs']==['REQ-QTY']
    assert ws.read_file(baseline,'src/quantity.cj')==original
    assert store.records(task.id,'model_call')==[]
