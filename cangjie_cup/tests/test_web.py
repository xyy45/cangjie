from nexus.store import RunStore
from nexus.execution.delivery import DeliveryService
from nexus.web.app import create_app


OPERATOR_KEY='d'*64  # Synthetic test-only local operator credential.


def authorize(client):
    client.get('/')
    with client.session_transaction() as session:token=session['csrf']
    result=client.post('/api/operator/authorize',json={'key':OPERATOR_KEY},
        headers={'Origin':'http://localhost','X-CSRF-Token':token})
    assert result.status_code==200,result.json


class Loop:
    calls = 0
    async def run(self, task_id): self.calls += 1


def setup_app(tmp_path):
    store = RunStore(tmp_path)
    loop = Loop()
    app = create_app(store,loop,DeliveryService(store),operator_key=OPERATOR_KEY)
    app.config['RUN_TASKS'] = False
    app.testing = True
    client = app.test_client()
    authorize(client)
    with client.session_transaction() as session:
        token = session['csrf']
    return store, loop, client, {'Origin':'http://localhost','X-CSRF-Token':token}


def test_refresh_only_reads_task(tmp_path):
    store, loop, client, headers = setup_app(tmp_path)
    task = store.create_task('base','fix',['src/a.cj'])
    for _ in range(2): assert client.get('/api/tasks/'+task.id).status_code == 200
    assert loop.calls == 0


def confirm_spec(client, headers, goal='fix order'):
    response=client.post('/api/requirements/drafts',json={'project':'order-demo-bug','goal':goal},headers=headers)
    assert response.status_code==200,response.json
    draft=response.json
    confirmed=client.post('/api/requirements/drafts/'+draft['id']+'/confirm',json=dict(
        schema_version=1,expected_version=draft['version'],requirements=draft['requirements'],
        allowed_paths=draft['allowed_paths']),headers=headers)
    assert confirmed.status_code==200,confirmed.json
    return confirmed.json


def test_duplicate_start_returns_same_task(tmp_path):
    store, loop, client, headers = setup_app(tmp_path)
    spec=confirm_spec(client,headers)
    body = dict(project='order-demo-bug', spec_id=spec['id'], idempotency_key='one-click')
    a = client.post('/api/tasks', json=body,headers=headers)
    b = client.post('/api/tasks', json=body,headers=headers)
    assert a.status_code == b.status_code == 200
    assert a.json['id'] == b.json['id']


def test_accept_requires_user_route(tmp_path):
    store, loop, client, headers = setup_app(tmp_path)
    assert client.post('/api/candidates/x/accept',json={}).status_code == 403
    assert client.post('/api/tasks',json={},headers={**headers,'Origin':'https://attacker.example'}).status_code == 403


def test_optional_analysis_unavailable_does_not_disable_repair(tmp_path):
    store, loop, client, headers = setup_app(tmp_path)
    spec=confirm_spec(client,headers)
    response = client.post('/api/tasks',json=dict(project='order-demo-bug',spec_id=spec['id'],idempotency_key='start'),headers=headers)
    assert response.status_code == 200
    assert response.json['status'] == 'READY'


def test_native_policy_probe_denies_and_preserves_frozen_files(tmp_path):
    store,loop,client,headers=setup_app(tmp_path)
    response=client.post('/api/policy-probe',json={},headers=headers)
    assert response.status_code==200,response.json
    assert response.json==dict(decision='Deny',reason='PROTECTED_PATH',unchanged=True,action_executed=False)
    assert loop.calls==0


def test_unconfirmed_requirement_and_client_actor_or_goal_cannot_start(tmp_path):
    store,loop,client,headers=setup_app(tmp_path)
    missing=client.post('/api/tasks',json=dict(project='order-demo-bug',spec_id='unknown',
        idempotency_key='missing'),headers=headers)
    assert missing.status_code==400 and missing.json['code']=='REQUIREMENT_UNCONFIRMED'
    spec=confirm_spec(client,headers,'exact original goal')
    assert spec['confirmed_by'].startswith('local-')
    for extra in ({'goal':'different goal'},{'confirmed_by':'attacker'}):
        response=client.post('/api/tasks',json=dict(project='order-demo-bug',spec_id=spec['id'],
            idempotency_key='extra',**extra),headers=headers)
        assert response.status_code==400
    result=client.post('/api/tasks',json=dict(project='order-demo-bug',spec_id=spec['id'],
        idempotency_key='valid'),headers=headers)
    assert result.status_code==200,result.json
    task=store.get_task(result.json['id'])
    assert task.schema_version==2 and task.spec_hash==spec['spec_hash']
    assert task.goal=='exact original goal' and loop.calls==0
    view=client.get('/api/tasks/'+task.id).json
    assert view['requirement_spec']['id']==spec['id']


def test_environment_and_requirement_draft_do_not_call_model_or_create_task(tmp_path):
    store,loop,client,headers=setup_app(tmp_path)
    status=client.get('/api/environment')
    assert status.status_code==200
    assert isinstance(status.json['ready'],bool)
    assert all('code' in item and 'message' in item for item in status.json['missing'])
    assert 'api_key' not in str(status.json).lower()
    draft=client.post('/api/requirements/drafts',json={'project':'order-demo-bug','goal':'fix'},headers=headers)
    assert draft.status_code==200
    with store.connect() as db:assert db.execute('SELECT count(*) FROM tasks').fetchone()[0]==0
    assert loop.calls==0


def test_history_and_sequential_events_are_read_only(tmp_path):
    store,loop,client,headers=setup_app(tmp_path)
    task=store.create_task('base','history goal',['src/a.cj'])
    store.update_task(task.id,status='BLOCKED')
    store.append_record(task.id,'event',{'message':'read-only history'})
    history=client.get('/api/tasks').json
    assert history['tasks'][0]['id']==task.id and history['limit']==50
    first=client.get('/api/tasks/'+task.id+'/events?after=0').json
    assert [e['sequence'] for e in first['events']]==[1,2]
    second=client.get('/api/tasks/'+task.id+'/events?after=1').json
    assert [e['sequence'] for e in second['events']]==[2]
    assert client.get('/api/tasks/'+task.id+'/events?after=-1').status_code==400
    assert store.get_task(task.id).status=='BLOCKED'
    assert loop.calls==0 and store.records(task.id,'model_call')==[]
