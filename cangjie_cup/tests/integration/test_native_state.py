"""Native transition decisions and commit-time task versions are independent."""
from pathlib import Path

import pytest

from nexus.policy.core import NativeCoreClient,PROJECT_ROOT
from nexus.store import RunStore


def transition(**changes):
    return dict(task_id='task',from_status='GENERATING',to_status='APPLYING',revision=4,
        expected_revision=4,new_revision=5,attempt_count=1,next_attempt_count=1,**changes)


def native(payload):
    core=NativeCoreClient()
    assert hasattr(core,'call_sync'),'native synchronous transition transport missing'
    return core.call_sync('task.transition',payload)['response']['data']


def test_native_transition_checks_terminals_revision_and_budget():
    assert native(transition())['decision']=='Allow'
    for changes in [dict(from_status='DELIVERED',to_status='READY'),dict(from_status='CANCELLED',to_status='APPLYING'),
                    dict(expected_revision=3),dict(new_revision=4),dict(next_attempt_count=0),
                    dict(next_attempt_count=4),dict(to_status='DELIVERED'),dict(from_status='UNKNOWN'),
                    dict(from_status='CANCELLED',to_status='CANCELLED',next_attempt_count=2)]:
        payload=transition();payload.update(changes)
        assert native(payload)['decision']=='Deny',changes


def test_terminal_task_cannot_resume_and_keeps_native_evidence(tmp_path):
    store=RunStore(tmp_path);task=store.create_task('base','goal',['src/a.cj'])
    cancelled=store.update_task(task.id,status='CANCELLED')
    with pytest.raises(ValueError):store.update_task(task.id,status='READY')
    assert store.get_task(task.id)==cancelled
    event=store.records(task.id,'event')[-1]
    assert event['native_transition']['response']['data']['decision']=='Allow'


def test_task_version_change_after_native_decision_is_not_overwritten(tmp_path,monkeypatch):
    core=NativeCoreClient()
    assert hasattr(core,'call_sync'),'native synchronous transition transport missing'
    original=NativeCoreClient.call_sync
    store=RunStore(tmp_path);task=store.create_task('base','goal',['src/a.cj'])
    def race(self,operation,payload,**kwargs):
        proof=original(self,operation,payload,**kwargs)
        if operation=='task.transition':
            changed=task.model_copy(update={'status':'CANCELLED','revision':1})
            with store.connect() as db:db.execute('UPDATE tasks SET payload=? WHERE id=?',(changed.model_dump_json(),task.id))
        return proof
    monkeypatch.setattr(NativeCoreClient,'call_sync',race)
    assert store.update_task(task.id,expected_revision=0,status='GENERATING') is None
    assert store.get_task(task.id).status=='CANCELLED'
    assert store.records(task.id,'event')==[]


def test_cancel_during_candidate_copy_registers_no_candidate_or_attempt(tmp_path,monkeypatch):
    import shutil
    from nexus.execution.workspace import WorkspaceStore
    from nexus.contracts import CandidateProposal,file_hash
    source=PROJECT_ROOT/'fixtures/order-demo'
    store=RunStore(tmp_path);ws=WorkspaceStore(tmp_path,registered=[source]);baseline=ws.import_project(source,'.')
    task=store.create_task(baseline,'goal',['src/quantity.cj'])
    text=ws.read_file(baseline,'src/quantity.cj')
    proposal=CandidateProposal(edits=[dict(path='src/quantity.cj',before_hash=file_hash(text),content=text+'\n// candidate\n')],requirement_refs=['goal'])
    copy=shutil.copytree
    def racing_copy(*args,**kwargs):
        result=copy(*args,**kwargs)
        store.update_task(task.id,status='CANCELLED')
        return result
    monkeypatch.setattr(shutil,'copytree',racing_copy)
    with pytest.raises(ValueError):ws.apply_candidate(task,proposal)
    assert store.get_task(task.id).status=='CANCELLED'
    assert store.get_task(task.id).attempt_count==0
    assert store.records(task.id,'candidate')==[]
    assert not list((tmp_path/'candidates').iterdir())


@pytest.mark.parametrize('fault',['request_id','payload_hash','core_version','status','component_unavailable'])
def test_commit_rejects_forged_reply_or_component_changed_after_decision(tmp_path,monkeypatch,fault):
    from nexus.policy.state import prepare_update
    store=RunStore(tmp_path);task=store.create_task('base','goal',['src/a.cj'])
    current=store.update_task(task.id,status='GENERATING')
    updated,proof=prepare_update(current,status='APPLYING')
    events=store.records(task.id,'event')
    if fault=='component_unavailable':
        def unavailable(self):raise ValueError('Native component changed after decision')
        monkeypatch.setattr(NativeCoreClient,'component_identity',unavailable)
    else:proof['response'][fault]='forged'
    with pytest.raises(ValueError):
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            store._commit_task(db,current,updated,proof)
    assert store.get_task(task.id)==current
    assert store.records(task.id,'event')==events


def test_recovery_uses_pending_operations_that_arrive_during_native_decision(tmp_path,monkeypatch):
    from nexus.execution.ownership import RuntimeOwner
    store=RunStore(tmp_path);task=store.create_task('base','goal',['src/a.cj'])
    owner=RuntimeOwner(tmp_path);assert owner.acquire()
    original=NativeCoreClient.call_sync;inserted=[]
    def late_operation(self,operation,payload,**kwargs):
        proof=original(self,operation,payload,**kwargs)
        if operation=='task.transition' and not inserted:
            inserted.append(True)
            store.append_record(task.id,'model_call',dict(id='late-request',task_id=task.id,origin='TEST',
                model_id='NO_API',request_ref='records/not-replayed.json',status='STARTED'))
        return proof
    monkeypatch.setattr(NativeCoreClient,'call_sync',late_operation)
    try:
        assert owner.reconcile(store)==[dict(task_id=task.id,status='IN_DOUBT')]
        event=store.records(task.id,'event')[-1]
        assert event['model_call_ids']==['late-request']
        assert store.records(task.id,'model_call')[0]['status']=='STARTED'
    finally:owner.close()


def test_candidate_entry_rejects_task_snapshot_stale_since_policy_decision(tmp_path):
    from nexus.execution.workspace import WorkspaceStore
    from nexus.contracts import CandidateProposal,file_hash
    source=PROJECT_ROOT/'fixtures/order-demo'
    store=RunStore(tmp_path);ws=WorkspaceStore(tmp_path,registered=[source]);baseline=ws.import_project(source,'.')
    snapshot=store.create_task(baseline,'original goal',['src/quantity.cj'])
    current=store.update_task(snapshot.id,goal='updated goal')
    content=ws.read_file(baseline,'src/quantity.cj')
    proposal=CandidateProposal(edits=[dict(path='src/quantity.cj',before_hash=file_hash(content),content=content+'\n// old decision\n')],requirement_refs=['goal'])
    with pytest.raises(ValueError):ws.apply_candidate(snapshot,proposal)
    assert store.get_task(snapshot.id)==current
    assert store.records(snapshot.id,'candidate')==[]
