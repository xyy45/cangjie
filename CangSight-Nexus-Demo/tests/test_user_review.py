"""User actions and CAS boundaries; synthetic checks here are unit fixtures only."""
from test_web import authorize, OPERATOR_KEY
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from nexus.execution.review import ReviewService
from nexus.store import RunStore
from test_delivery import checked


def test_user_reject_binds_identity_and_blocks_accept_export(tmp_path):
    ws,store,c,delivery=checked(tmp_path)
    a=delivery.accept(c.id,delivery.check_set_hash(c.id))
    revision=store.get_task(c.task_id).revision
    review=ReviewService(store).reject(c.id,revision,actor_id='local-user',reason='Needs another approach')
    assert review.decision=='REJECT' and review.decision_source=='USER' and review.actor_id=='local-user'
    assert store.get_task(c.task_id).status=='REJECTED'
    with pytest.raises(ValueError):delivery.accept(c.id,delivery.check_set_hash(c.id))
    with pytest.raises(ValueError):delivery.export(c.id,a.id)
    assert store.records(c.task_id,'model_call')==[]


def test_stale_revision_foreign_selection_and_forged_actor_rejected(tmp_path):
    ws,store,c,delivery=checked(tmp_path)
    revision=store.get_task(c.task_id).revision
    service=ReviewService(store)
    with pytest.raises(ValueError):service.reject(c.id,revision-1,actor_id='local-user')
    with pytest.raises(ValueError):service.reject(c.id,revision,actor_id='')
    store.append_record(c.task_id,'event',{'selected_candidate_id':'other'})
    with pytest.raises(ValueError):service.reject(c.id,revision,actor_id='local-user')
    assert store.get_task(c.task_id).status=='REVIEW_PENDING'


def test_cancel_records_inflight_unknown_without_replaying_or_resetting(tmp_path):
    store=RunStore(tmp_path)
    task=store.create_task('base','goal',['src/a.cj'])
    task=store.update_task(task.id,status='GENERATING')
    store.append_record(task.id,'model_call',dict(id='request',task_id=task.id,origin='TEST',model_id='fixture',
        request_ref='records/fixture-request.json',status='STARTED'))
    result=ReviewService(store).cancel(task.id,task.revision,actor_id='local-user')
    assert result['status']=='CANCELLED' and result['in_flight_unknown'] is True
    assert store.get_task(task.id).attempt_count==0
    assert store.records(task.id,'model_call')[0]['status']=='STARTED'
    assert store.records(task.id,'event')[-1]['data']['in_flight_unknown'] is True


def test_events_have_ordered_versioned_native_records_and_atomic_state(tmp_path):
    store=RunStore(tmp_path)
    task=store.create_task('base','goal',['src/a.cj'])
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(lambda number:store.append_record(task.id,'event',{'message':str(number)}),range(12)))
    store.update_task(task.id,expected_revision=task.revision,status='BLOCKED')
    events=store.records(task.id,'event')
    assert [event['sequence'] for event in events]==list(range(1,len(events)+1))
    assert all(event['schema_version']==1 and event['task_id']==task.id for event in events)
    assert events[-1]['type']=='TASK_STATE_CHANGED' and events[-1]['status']=='BLOCKED'
    with store.connect() as db:
        ref=db.execute("SELECT ref FROM records WHERE task_id=? AND kind='event' ORDER BY rowid DESC",(task.id,)).fetchone()[0]
    raw=json.loads((tmp_path/ref).read_text())
    assert raw['event_id'] and raw['occurred_at'] and raw['data']['previous_status']=='READY'
    assert store.update_task(task.id,expected_revision=task.revision,status='GENERATING') is None


def test_cancel_during_packaging_does_not_publish_or_overwrite_cancelled(tmp_path,monkeypatch):
    ws,store,c,delivery=checked(tmp_path)
    a=delivery.accept(c.id,delivery.check_set_hash(c.id))
    original=delivery._package
    def cancel_before_publication(*args):
        ref=original(*args)
        ReviewService(store).cancel(c.task_id,store.get_task(c.task_id).revision,actor_id='local-user')
        return ref
    monkeypatch.setattr(delivery,'_package',cancel_before_publication)
    with pytest.raises(ValueError):delivery.export(c.id,a.id)
    assert store.get_task(c.task_id).status=='CANCELLED'
    assert list((tmp_path/'exports').glob('*.zip'))==[]


def test_review_and_cancel_http_identity_is_server_owned(tmp_path):
    from nexus.web.app import create_app
    from test_web import Loop
    ws,store,c,delivery=checked(tmp_path)
    app=create_app(store,Loop(),delivery,operator_key=OPERATOR_KEY)
    app.config['RUN_TASKS']=False
    client=app.test_client();authorize(client)
    with client.session_transaction() as session:
        actor=session['actor_id'];token=session['csrf']
    headers={'Origin':'http://localhost','X-CSRF-Token':token}
    revision=store.get_task(c.task_id).revision
    endpoint='/api/candidates/'+c.id+'/reject'
    assert client.post(endpoint,json={'task_revision':revision,'actor_id':'forged'},headers=headers).status_code==400
    assert client.post(endpoint,json={'task_revision':revision-1},headers=headers).status_code==400
    response=client.post(endpoint,json={'task_revision':revision,'reason':'user choice'},headers=headers)
    assert response.status_code==200,response.json
    assert response.json['actor_id']==actor and response.json['decision_source']=='USER'
    assert store.records(c.task_id,'model_call')==[]


def test_completed_model_call_is_not_reported_as_still_inflight(tmp_path):
    store=RunStore(tmp_path)
    task=store.create_task('base','goal',['src/a.cj'])
    common=dict(task_id=task.id,origin='TEST',model_id='fixture',request_ref='records/unit.json')
    store.append_record(task.id,'model_call',dict(id='one',status='STARTED',**common))
    store.append_record(task.id,'model_call',dict(id='one-result',status='SUCCEEDED',**common))
    result=ReviewService(store).cancel(task.id,task.revision,actor_id='user')
    assert result['in_flight_unknown'] is False


def test_history_never_advertises_a_stale_archive_as_downloadable(tmp_path):
    from nexus.web.app import create_app
    from test_web import Loop
    ws,store,c,delivery=checked(tmp_path)
    app=create_app(store,Loop(),delivery,operator_key=OPERATOR_KEY)
    client=app.test_client();authorize(client)
    with client.session_transaction() as session:actor=session['actor_id']
    approval=delivery.accept(c.id,delivery.check_set_hash(c.id),actor_id=actor)
    delivery.export(c.id,approval.id)
    assert client.get('/api/tasks/'+c.task_id).json['download_url']
    (tmp_path/'records/test.log').write_text('missing original evidence')
    history=client.get('/api/tasks/'+c.task_id).json
    assert history['download_url'] is None and '新建任务' in history['review_notice']
    assert store.get_task(c.task_id).status=='DELIVERED'
    assert store.records(c.task_id,'model_call')==[]
