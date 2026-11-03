"""Actual derived base dispatcher + RepairLoop + real MCP/Policy/cjpm.

Generation is explicitly scripted; no model HTTP and no LIVE claim.
"""
import json
import time
import pytest

from nexus.contracts import CandidateProposal, file_hash
from nexus.execution.delivery import DeliveryService
from nexus.integrations.sympas_runtime import ADAPTER_SHA256, BASE_COMMIT
from nexus.repair.cegis_loop import RepairLoop
from nexus.store import RunStore
from nexus.web.app import create_app

pytestmark=pytest.mark.sdk


def test_base_dispatcher_calls_one_real_repair_loop_and_preserves_review(tmp_path,monkeypatch):
    # Only satisfy presence checks with synthetic values. The injected provider
    # cannot call HTTP; accidental use of ModelProvider hits a reserved invalid host.
    monkeypatch.setenv('DEEPSEEK_API_KEY','SYNTHETIC_NO_MODEL_SDK_TEST')
    monkeypatch.setenv('DEEPSEEK_BASE_URL','https://example.invalid/v1')
    monkeypatch.setenv('DEEPSEEK_MODEL','SCRIPTED_NO_MODEL_SDK_TEST')
    contexts=[]
    class ScriptedGeneration:
        async def propose(self,context):
            contexts.append(context)
            original=context['files']['src/quantity.cj']['content']
            return CandidateProposal(edits=[dict(path='src/quantity.cj',before_hash=file_hash(original),
                content=original.replace('quantity >= 0','quantity >= 1'))],requirement_refs=['REQ-QTY'])
    store=RunStore(tmp_path)
    loop=RepairLoop(store,provider_factory=lambda *_:ScriptedGeneration())
    app=create_app(store,loop,DeliveryService(store),operator_key='d'*64)
    client=app.test_client();client.get('/')
    with client.session_transaction() as session:token=session['csrf']
    headers={'Origin':'http://localhost','X-CSRF-Token':token}
    assert client.post('/api/operator/authorize',json={'key':'d'*64},headers=headers).status_code==200
    draft_response=client.post('/api/requirements/drafts',headers=headers,json=dict(
        project='order-demo-bug',goal='SCRIPTED_GENERATION_REAL_MCP_NOT_LIVE fix quantity'))
    assert draft_response.status_code==200,draft_response.json
    draft=draft_response.json
    spec_response=client.post('/api/requirements/drafts/'+draft['id']+'/confirm',headers=headers,
        json=dict(schema_version=1,expected_version=draft['version'],requirements=draft['requirements'],
            allowed_paths=draft['allowed_paths']))
    assert spec_response.status_code==200,spec_response.json
    body=dict(schema_version=1,team_profile='cangjie-repair',payload=dict(
        project='order-demo-bug',spec_id=spec_response.json['id'],idempotency_key='actual-base-dispatch'))
    response=client.post('/agents/runs',json=body,headers=headers)
    assert response.status_code==200,response.json
    task_id=response.json['run_id']
    repeated=client.post('/agents/runs',json=body,headers=headers)
    assert repeated.status_code==200 and repeated.json['run_id']==task_id
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        events=store.records(task_id,'event')
        if any(e['type'] in ('SYMPAS_RUN_FINISHED','SYMPAS_RUN_FAILED') for e in events):break
        time.sleep(0.05)
    else:pytest.fail('Real base dispatch did not terminate within 60s; no restart attempted')
    task=store.get_task(task_id)
    assert task.status=='REVIEW_PENDING',task
    assert len(contexts)==1 and task.attempt_count==1
    assert task.runtime_binding['base_commit']==BASE_COMMIT
    assert task.runtime_binding['adapter_sha256']==ADAPTER_SHA256
    assert sum(e['type']=='SYMPAS_RUN_QUEUED' for e in events)==1
    assert sum(e['type']=='SYMPAS_RUN_STARTED' for e in events)==1
    assert sum(e['type']=='SYMPAS_RUN_FINISHED' for e in events)==1
    assert store.records(task_id,'model_call')==store.records(task_id,'acceptance')==[]
    calls=store.records(task_id,'tool_call')
    assert {'project.diagnose','workspace.list_files','workspace.read_file',
        'candidate.apply','candidate.build','candidate.test'}<={c['tool'] for c in calls}
    assert 'candidate.export' not in {c['tool'] for c in calls}
    checks=store.records(task_id,'check')
    assert any(c['state']=='FAIL' and c['subject_id']==task.baseline_id for c in checks)
    candidate=store.records(task_id,'candidate')[0]
    verified=[c for c in checks if c['subject_id']==candidate['id']]
    assert {c['kind'] for c in verified}=={'build','test'}
    assert all(c['state']=='PASS' for c in verified)
    result=client.get('/agents/runs/'+task_id)
    assert result.json['status']=='REVIEW_PENDING' and result.json['download_url'] is None
    assert result.json['tool_calls']==calls
    (tmp_path/'base-dispatch-summary.json').write_text(json.dumps(dict(
        scope='ACTUAL_DERIVED_DISPATCH_REAL_LOOP_SCRIPTED_GENERATION_NOT_LIVE',
        base_commit=BASE_COMMIT,adapter_sha256=ADAPTER_SHA256,task_id=task_id,status=task.status,run_directory=str(tmp_path),
        generated_proposals=len(contexts),candidate_id=candidate['id'],events=events,
        tool_calls=calls,checks=checks,model_http_calls=0,acceptances=0),ensure_ascii=False,indent=2))
