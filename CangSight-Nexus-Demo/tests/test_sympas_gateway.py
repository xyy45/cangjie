"""Derived gateway/control-plane contracts; these are not LIVE repair tests."""
import json
import pytest

from nexus.execution.delivery import DeliveryService
from nexus.integrations.sympas_runtime import ADAPTER_SHA256, BASE_COMMIT, RuntimeBridge, _execute_run, _public_value
from nexus.store import RunStore
from nexus.web.app import create_app
from test_web import OPERATOR_KEY, authorize, confirm_spec, setup_app


def request_body(client, headers, key='gateway-start'):
    spec=confirm_spec(client,headers)
    return dict(schema_version=1,team_profile='cangjie-repair',payload=dict(
        project='order-demo-bug',spec_id=spec['id'],idempotency_key=key))


def test_gateway_shares_task_identity_and_reopens_same_store(tmp_path):
    store,loop,client,headers=setup_app(tmp_path)
    body=request_body(client,headers)
    first=client.post('/agents/runs',json=body,headers=headers)
    again=client.post('/agents/runs',json=body,headers=headers)
    assert first.status_code==again.status_code==200
    task=first.json
    assert task['run_id']==task['id']
    assert task['id']==again.json['id']
    assert task['runtime_binding']==dict(implementation='CangSight native RunStore',
        sympas_integration='DERIVED_GATEWAY',base_commit=BASE_COMMIT,adapter_sha256=ADAPTER_SHA256,contract_version=1,
        external_run_id=task['id'],internal_task_id=task['id'])
    event=store.append_record(task['id'],'event',dict(type='GATEWAY_TEST_EVENT'))
    current=client.get('/agents/runs/'+task['id'])
    assert current.status_code==200 and current.json['id']==task['id']
    assert current.json['run_id']==task['id']
    assert client.get('/api/tasks/'+task['id']).json['id']==task['id']
    events=client.get('/agents/runs/'+task['id']+'/events').json
    assert json.loads((tmp_path/event).read_text()) in events['events']
    assert client.get('/agents/runs/'+task['id']+'/events',headers={
        'Last-Event-ID':str(events['last_event_id'])}).json['events']==[]
    assert client.get('/agents/runs/'+task['id']+'/events?after_event_id=-1').status_code==400
    assert client.post('/api/tasks',json=body['payload'],headers=headers).status_code==400
    restarted=RunStore(tmp_path)
    app=create_app(restarted,loop,DeliveryService(restarted),operator_key=OPERATOR_KEY)
    fresh=app.test_client()
    assert fresh.get('/agents/runs/'+task['id']).status_code==403
    authorize(fresh)
    assert fresh.get('/agents/runs/'+task['id']).json['id']==task['id']
    assert loop.calls==0  # Explicit controller-only test, never claimed as repair success.


@pytest.mark.parametrize('change',[{'schema_version':2},{'schema_version':True},
    {'team_profile':'security_pipeline'},{'payload':{'project':'order-demo-bug'}}])
def test_gateway_rejects_unknown_contract_or_unconfirmed_input(tmp_path,change):
    store,loop,client,headers=setup_app(tmp_path)
    body=request_body(client,headers);body.update(change)
    response=client.post('/agents/runs',json=body,headers=headers)
    assert response.status_code==400,response.json
    with store.connect() as db:assert db.execute('SELECT count(*) FROM tasks').fetchone()[0]==0
    assert loop.calls==0


def test_gateway_has_no_anonymous_or_old_domain_approval_route(tmp_path):
    store,loop,client,headers=setup_app(tmp_path)
    body=request_body(client,headers)
    anonymous=client.application.test_client();anonymous.get('/')
    with anonymous.session_transaction() as session:csrf=session['csrf']
    assert anonymous.post('/agents/runs',json=body,headers={
        'Origin':'http://localhost','X-CSRF-Token':csrf}).status_code==403
    assert client.post('/agents/runs',json=body,headers={**headers,'Origin':'https://bad.invalid'}).status_code==403
    assert client.get('/agents/runs/missing').status_code==404
    assert client.post('/agents/approve/missing',json={},headers=headers).status_code==404
    assert client.post('/run/cegis',json={},headers=headers).status_code==404
    assert client.get('/agents/runs/missing/events').status_code==404


def test_upstream_public_value_filter_retains_no_credential_values():
    assert _public_value({'deepseek_api_key':'synthetic','nested':[{'owner_token':'synthetic'}],
        'Set-Cookie':'synthetic'})=={'deepseek_api_key':'[REDACTED]',
        'nested':[{'owner_token':'[REDACTED]'}],'Set-Cookie':'[REDACTED]'}


def test_gateway_cannot_write_when_runtime_owner_is_unconfirmed(tmp_path):
    store,loop,client,headers=setup_app(tmp_path)
    body=request_body(client,headers)
    client.application.config['WRITES_ENABLED']=False
    assert client.post('/agents/runs',json=body,headers=headers).status_code==503
    with store.connect() as db:assert db.execute('SELECT count(*) FROM tasks').fetchone()[0]==0
    assert loop.calls==0


def test_upstream_dispatch_completion_does_not_deliver_or_approve(tmp_path):
    store=RunStore(tmp_path)
    task=store.create_task('controller-only-fixture','dispatch contract',['src/a.cj'])
    def handler(payload):
        assert payload['_run_id']==task.id
        payload['_emit_event']('handler_entered',{'fixture':True})
        store.update_task(task.id,status='REVIEW_PENDING')
        return {'task_id':task.id,'status':'REVIEW_PENDING'}
    _execute_run(task.id,'cangjie-repair',{},RuntimeBridge(store),handler)
    assert store.get_task(task.id).status=='REVIEW_PENDING'
    assert store.records(task.id,'acceptance')==[]
    events=store.records(task.id,'event')
    assert any(e['type']=='SYMPAS_RUN_FINISHED' for e in events)
    assert any(e['type']=='SYMPAS_HANDLER_ENTERED' for e in events)


def test_dispatch_failure_is_in_doubt_without_replay_or_secret_echo(tmp_path,caplog):
    store=RunStore(tmp_path)
    task=store.create_task('controller-only-fixture','dispatch failure',['src/a.cj'])
    calls=[]
    def handler(payload):
        calls.append(payload['_run_id'])
        raise RuntimeError('SYNTHETIC_SECRET_MUST_NOT_ESCAPE')
    _execute_run(task.id,'cangjie-repair',{},RuntimeBridge(store),handler)
    assert store.get_task(task.id).status=='IN_DOUBT' and calls==[task.id]
    assert 'SYNTHETIC_SECRET_MUST_NOT_ESCAPE' not in str(store.records(task.id,'event'))+caplog.text
    assert store.records(task.id,'model_call')==[]


def test_dispatch_thread_failure_does_not_restart_on_idempotent_retry(tmp_path,monkeypatch):
    store,loop,client,headers=setup_app(tmp_path)
    body=request_body(client,headers)
    client.application.config['RUN_TASKS']=True
    # Control-flow failure fixture only; real environment gates are tested separately.
    monkeypatch.setattr('nexus.web.app.readiness',lambda:{'ready':True})
    starts=[]
    class CannotStart:
        def __init__(self,*args,**kwargs):pass
        def start(self):
            starts.append('attempted')
            raise RuntimeError('SYNTHETIC_BOOTSTRAP_SECRET')
    monkeypatch.setattr('nexus.integrations.sympas_runtime.threading.Thread',CannotStart)
    first=client.post('/agents/runs',json=body,headers=headers)
    repeated=client.post('/agents/runs',json=body,headers=headers)
    assert first.status_code==repeated.status_code==200
    assert first.json['id']==repeated.json['id'] and repeated.json['status']=='IN_DOUBT'
    assert starts==['attempted'] and loop.calls==0
    assert 'SYNTHETIC_BOOTSTRAP_SECRET' not in str(store.records(first.json['id'],'event'))
