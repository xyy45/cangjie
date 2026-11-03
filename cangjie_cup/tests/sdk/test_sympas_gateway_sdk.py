"""Derived gateway plus real MCP/Policy/cjpm; explicit hand-written proposal.

No paid model and no claim that the unmodified upstream application was started.
"""
import asyncio
import json
import pytest

from nexus.contracts import file_hash
from nexus.execution.delivery import DeliveryService
from nexus.execution.workspace import WorkspaceStore
from nexus.integrations.sympas_runtime import BASE_COMMIT
from nexus.mcp.client import ToolClient
from nexus.store import RunStore
from nexus.web.app import create_app

pytestmark=pytest.mark.sdk


def test_derived_gateway_task_has_real_mcp_candidate_and_restart_history(tmp_path):
    class NoModel:
        async def run(self,*args):raise AssertionError('No paid model in gateway probe')
    store=RunStore(tmp_path);key='d'*64
    app=create_app(store,NoModel(),DeliveryService(store),operator_key=key)
    app.config['RUN_TASKS']=False
    client=app.test_client();client.get('/')
    with client.session_transaction() as session:csrf=session['csrf']
    headers={'Origin':'http://localhost','X-CSRF-Token':csrf}
    assert client.post('/api/operator/authorize',json={'key':key},headers=headers).status_code==200
    draft=client.post('/api/requirements/drafts',headers=headers,json=dict(
        project='order-demo-bug',goal='HAND_WRITTEN_GATEWAY_PROBE fix quantity')).json
    spec=client.post('/api/requirements/drafts/'+draft['id']+'/confirm',headers=headers,json=dict(
        schema_version=1,expected_version=draft['version'],requirements=draft['requirements'],
        allowed_paths=draft['allowed_paths'])).json
    response=client.post('/agents/runs',headers=headers,json=dict(schema_version=1,
        team_profile='cangjie-repair',payload=dict(project='order-demo-bug',spec_id=spec['id'],
            idempotency_key='hand-written-gateway-probe')))
    assert response.status_code==200,response.json
    assert response.json['run_id']==response.json['id']
    task=store.get_task(response.json['id'])
    assert task.runtime_binding['base_commit']==BASE_COMMIT
    ws=WorkspaceStore(tmp_path);content=ws.read_file(task.baseline_id,'src/quantity.cj')
    async def exercise():
        async with ToolClient(tmp_path) as mcp:
            diagnosis=await mcp.call_tool('project.diagnose',dict(task_id=task.id,subject_id=task.baseline_id))
            assert diagnosis.operation_status=='OK'
            assert diagnosis.data['build']['state']=='PASS' and diagnosis.data['test']['state']=='FAIL'
            applied=await mcp.call_tool('candidate.apply',dict(task_id=task.id,proposal=dict(
                edits=[dict(path='src/quantity.cj',before_hash=file_hash(content),
                    content=content.replace('quantity >= 0','quantity >= 1'))],requirement_refs=['REQ-QTY'])))
            assert applied.operation_status=='OK',applied
            candidate=applied.data
            for name in ('build','test'):
                result=await mcp.call_tool('candidate.'+name,dict(task_id=task.id,
                    candidate_id=candidate['id'],expected_tree_hash=candidate['tree_hash']))
                assert result.operation_status=='OK' and result.data['state']=='PASS',result
                if name=='test':assert result.data['counts']['passed']==11
            return candidate
    candidate=asyncio.run(exercise())
    current=client.get('/agents/runs/'+task.id)
    assert current.status_code==200 and current.json['candidates'][0]['id']==candidate['id']
    calls=store.records(task.id,'tool_call')
    assert len(calls)>=4 and store.records(task.id,'model_call')==[]
    assert current.json['tool_calls']==calls
    reopened=RunStore(tmp_path)
    restarted=create_app(reopened,NoModel(),DeliveryService(reopened),operator_key=key)
    new=restarted.test_client();new.get('/')
    with new.session_transaction() as session:token=session['csrf']
    assert new.post('/api/operator/authorize',json={'key':key},headers={
        'Origin':'http://localhost','X-CSRF-Token':token}).status_code==200
    restored=new.get('/agents/runs/'+task.id)
    assert restored.json['runtime_binding']==current.json['runtime_binding']
    assert restored.json['candidates']==current.json['candidates']
    assert restored.json['tool_calls']==calls
    assert reopened.records(task.id,'tool_call')==calls
    (tmp_path/'gateway-summary.json').write_text(json.dumps(dict(
        scope='DERIVED_GATEWAY_HAND_WRITTEN_MCP_PROBE_NOT_LIVE',base_commit=BASE_COMMIT,
        task_id=task.id,candidate_id=candidate['id'],tool_calls=calls,
        checks=store.records(task.id,'check'),model_calls=0,
        original_upstream_application_started=False),ensure_ascii=False,indent=2))
