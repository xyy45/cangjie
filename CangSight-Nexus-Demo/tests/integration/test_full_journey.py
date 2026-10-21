"""Real MCP + SDK + native Policy + HTTP delivery, with a hand-written candidate.
This integration is NOT evidence of LIVE model repair.
"""
import asyncio
import time
from io import BytesIO
from pathlib import Path
import zipfile
import pytest
from nexus.contracts import file_hash, source_manifest
from nexus.execution.delivery import DeliveryService
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient
from nexus.policy.client import PolicyClient
from nexus.repair.cegis_loop import RepairLoop
from nexus.store import RunStore
from nexus.web.app import create_app

pytestmark = pytest.mark.sdk
ROOT = Path(__file__).resolve().parents[2]


def test_full_journey_matches_exported_candidate(tmp_path):
    source = ROOT/'fixtures/order-demo-bug'
    ws = WorkspaceStore(tmp_path,registered=[source])
    baseline = ws.import_project(source,'.')
    store = RunStore(tmp_path)
    task = store.create_task(baseline,'Fix quantity validation',['src/quantity.cj'])
    frozen = source_manifest(ws.subject_path(baseline))
    async def run():
        async with ToolClient(tmp_path) as client:
            diagnosis = await client.call_tool('project.diagnose',dict(task_id=task.id,request_id='baseline',subject_id=baseline))
            assert diagnosis.data['build']['state']=='PASS'
            assert diagnosis.data['test']['state']=='FAIL'
            assert diagnosis.data['test']['counts']['failed']==1
            content = ws.read_file(baseline,'src/quantity.cj')
            result = await client.call_tool('candidate.apply',dict(task_id=task.id,request_id='apply',proposal=dict(
                edits=[dict(path='src/quantity.cj',before_hash=file_hash(content),content=content.replace('quantity >= 0','quantity >= 1'))],
                requirement_refs=['goal'])))
            assert result.operation_status=='OK',result
            c=result.data
            args=dict(task_id=task.id,candidate_id=c['id'],expected_tree_hash=c['tree_hash'])
            for name in ('build','test'):
                checked=await client.call_tool('candidate.'+name,dict(**args,request_id=name))
                assert checked.data['state']=='PASS',checked
            denied=await PolicyClient(ROOT).decide(dict(schema_version=1,policy_version='1.1',deadline_at=int(time.time()*1000)+30000,approval_binding='',
                action='candidate.apply',task_id=task.id,request_id='deny',
                paths=['src/order_test.cj'],input_tree_hash=c['tree_hash'],arguments_hash='a'*64,remaining_budget=2,accepted=False))
            assert denied['decision']=='Deny'
            assert source_manifest(ws.subject_path(baseline))==frozen
            return c
    c=asyncio.run(run())
    store.update_task(task.id,status='REVIEW_PENDING')
    store.append_record(task.id,'event',{'selected_candidate_id':c['id'],'origin':'HAND_WRITTEN_SDK_TEST'})
    delivery=DeliveryService(store)
    app=create_app(store,RepairLoop(store),delivery,operator_key='d'*64)
    client=app.test_client()
    client.get('/')
    with client.session_transaction() as session: token=session['csrf']
    headers={'Origin':'http://localhost','X-CSRF-Token':token}
    assert client.post('/api/operator/authorize',json={'key':'d'*64},headers=headers).status_code==200
    details=client.get('/api/candidates/'+c['id']).json
    accepted=client.post('/api/candidates/'+c['id']+'/accept',json={'check_set_hash':details['check_set_hash']},headers=headers)
    assert accepted.status_code==200,accepted.json
    result=client.post('/api/candidates/'+c['id']+'/export',json={'acceptance_id':accepted.json['id']},headers=headers)
    assert result.status_code==200,result.json
    refreshed=client.get('/api/tasks/'+task.id)
    assert refreshed.json['download_url']==result.json['download_url']
    downloaded=client.get(refreshed.json['download_url'])
    assert downloaded.status_code==200
    with zipfile.ZipFile(BytesIO(downloaded.data)) as archive:
        for name in source_manifest(ws.subject_path(c['id'])):
            assert archive.read(name)==(ws.subject_path(c['id'])/name).read_bytes()
    assert store.get_task(task.id).status=='DELIVERED'
