"""Workbench failure contracts; injected transport outcomes are not LIVE evidence."""
from test_web import authorize, OPERATOR_KEY
from nexus.contracts import ToolResult
from nexus.web.app import create_app
from test_delivery import checked
from test_web import Loop, setup_app


def user_app(tmp_path):
    ws,store,c,delivery=checked(tmp_path)
    app=create_app(store,Loop(),delivery,operator_key=OPERATOR_KEY)
    app.testing=True;app.config['RUN_TASKS']=False
    client=app.test_client();authorize(client)
    with client.session_transaction() as session:
        token=session['csrf'];actor=session['actor_id']
    return store,c,delivery,client,{'Origin':'http://localhost','X-CSRF-Token':token},actor


def test_check_failure_has_business_code_and_keeps_raw_reason_in_evidence(tmp_path):
    store,c,delivery,client,headers,actor=user_app(tmp_path)
    original=delivery.check_set_hash(c.id)
    (tmp_path/'records/test.log').write_text('incomplete native report')
    response=client.post('/api/candidates/'+c.id+'/accept',json={'check_set_hash':original},headers=headers)
    assert response.status_code==400
    assert response.json['code']=='CHECKS_NOT_PASS'
    assert 'test evidence inconsistent' not in response.json['error']
    assert response.json['record_refs']
    event=store.records(c.task_id,'event')[-1]
    assert event['type']=='API_REJECTED' and event['technical_reason']=='test evidence inconsistent'
    assert store.records(c.task_id,'acceptance')==[]


def test_unconfirmed_export_outcome_is_explicit_and_not_retried(tmp_path,monkeypatch):
    store,c,delivery,client,headers,actor=user_app(tmp_path)
    approval=delivery.accept(c.id,delivery.check_set_hash(c.id),actor_id=actor)
    calls=[]
    class Disconnected:
        def __init__(self,*args):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def call_tool(self,name,args):
            calls.append(name)
            return ToolResult(operation_status='IN_DOUBT',error='CONNECTION_LOST_AFTER_WRITE')
    monkeypatch.setattr('nexus.web.app.ToolClient',Disconnected)
    response=client.post('/api/candidates/'+c.id+'/export',json={'acceptance_id':approval.id},headers=headers)
    assert response.status_code==409 and response.json['code']=='RESULT_IN_DOUBT'
    assert response.json['operation_status']=='IN_DOUBT'
    assert 'CONNECTION_LOST_AFTER_WRITE' not in response.json['error']
    assert calls==['candidate.export']
    assert store.get_task(c.task_id).status=='REVIEW_PENDING'
    assert list((tmp_path/'exports').glob('*.zip'))==[]
    assert store.records(c.task_id,'event')[-1]['technical_reason']=='CONNECTION_LOST_AFTER_WRITE'


def test_expired_approval_reports_actionable_code_without_new_mcp_call(tmp_path,monkeypatch):
    store,c,delivery,client,headers,actor=user_app(tmp_path)
    approval=delivery.accept(c.id,delivery.check_set_hash(c.id),actor_id=actor)
    approval.expires_at=0.0
    with store.connect() as db:db.execute('UPDATE acceptances SET payload=? WHERE id=?',(approval.model_dump_json(),approval.id))
    def forbidden(*args):raise AssertionError('MCP must not start for an expired approval')
    monkeypatch.setattr('nexus.web.app.ToolClient',forbidden)
    response=client.post('/api/candidates/'+c.id+'/export',json={'acceptance_id':approval.id},headers=headers)
    assert response.status_code==400 and response.json['code']=='APPROVAL_INVALID'
    assert 'acceptance expired' not in response.json['error']
    assert response.json['record_refs']


def test_invalid_input_does_not_echo_raw_validation_or_sensitive_values(tmp_path):
    store,loop,client,headers=setup_app(tmp_path)
    response=client.post('/api/requirements/drafts',json={'project':'order-demo-bug','goal':{'api_key':'do-not-echo-secret'}},headers=headers)
    assert response.status_code==400 and response.json['code']=='INVALID_REQUEST'
    assert 'do-not-echo-secret' not in str(response.json)
    assert 'str type expected' not in response.json['error']
    assert loop.calls==0


def test_malformed_json_returns_json_error_instead_of_html(tmp_path):
    store,loop,client,headers=setup_app(tmp_path)
    response=client.post('/api/requirements/drafts',data='{ invalid JSON',content_type='application/json',headers=headers)
    assert response.status_code==400 and response.is_json
    assert response.json['code']=='INVALID_REQUEST'
    assert loop.calls==0


def test_cancelled_inflight_task_displays_uncertain_effects(tmp_path):
    store,loop,client,headers=setup_app(tmp_path)
    task=store.create_task('base','goal',['src/a.cj'])
    task=store.update_task(task.id,status='GENERATING')
    store.append_record(task.id,'model_call',dict(id='pending',task_id=task.id,origin='TEST',
        model_id='NO_NETWORK',request_ref='records/unit.json',status='STARTED'))
    response=client.post('/api/tasks/'+task.id+'/cancel',json={'task_revision':task.revision},headers=headers)
    assert response.status_code==200 and response.json['code']=='RESULT_IN_DOUBT'
    view=client.get('/api/tasks/'+task.id).json
    assert view['status']=='CANCELLED' and '费用' in view['review_notice'] and '核实' in view['review_notice']
    assert store.records(task.id,'model_call')[0]['status']=='STARTED'
    assert loop.calls==0


def test_policy_export_denial_has_distinct_code_and_original_reason(tmp_path,monkeypatch):
    store,c,delivery,client,headers,actor=user_app(tmp_path)
    approval=delivery.accept(c.id,delivery.check_set_hash(c.id),actor_id=actor)
    class Denied:
        def __init__(self,*args):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def call_tool(self,*args):return ToolResult(operation_status='ERROR',error='POLICY_UNAVAILABLE')
    monkeypatch.setattr('nexus.web.app.ToolClient',Denied)
    response=client.post('/api/candidates/'+c.id+'/export',json={'acceptance_id':approval.id},headers=headers)
    assert response.status_code==409 and response.json['code']=='EXPORT_BLOCKED'
    assert response.json['operation_status']=='ERROR'
    assert 'POLICY_UNAVAILABLE' not in response.json['error']
    assert store.records(c.task_id,'event')[-1]['technical_reason']=='POLICY_UNAVAILABLE'


def test_raw_pydantic_error_does_not_echo_forbidden_credential_field(tmp_path):
    store,loop,client,headers=setup_app(tmp_path)
    draft=client.post('/api/requirements/drafts',json={'project':'order-demo-bug','goal':'fix'},headers=headers).json
    body=dict(schema_version=1,expected_version=draft['version'],requirements=draft['requirements'],
        allowed_paths=draft['allowed_paths'],api_key='do-not-echo-secret')
    response=client.post('/api/requirements/drafts/'+draft['id']+'/confirm',json=body,headers=headers)
    assert response.status_code==400 and response.json['code']=='INVALID_REQUEST'
    assert 'do-not-echo-secret' not in str(response.json)
    with store.connect() as db:assert db.execute('SELECT COUNT(*) FROM requirement_specs').fetchone()[0]==0
    assert loop.calls==0


def test_environment_error_preserves_its_code_and_does_not_start_worker(tmp_path,monkeypatch):
    from test_web import confirm_spec
    store,loop,client,headers=setup_app(tmp_path)
    spec=confirm_spec(client,headers)
    client.application.config['RUN_TASKS']=True
    monkeypatch.setattr('nexus.web.app.readiness',lambda:{'ready':False,'missing':[{'code':'SDK_NOT_READY'}]})
    response=client.post('/api/tasks',json=dict(project='order-demo-bug',spec_id=spec['id'],idempotency_key='missing-sdk'),headers=headers)
    assert response.status_code==400 and response.json['code']=='ENVIRONMENT_NOT_READY'
    assert loop.calls==0
    with store.connect() as db:assert db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]==0
