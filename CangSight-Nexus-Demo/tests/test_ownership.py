"""Real OS lock contention and read-only reconciliation effects, never LIVE."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
from nexus.execution.ownership import RuntimeOwner
from nexus.store import RunStore


def test_live_owner_cannot_be_mistaken_for_crashed_owner(tmp_path):
    code='from pathlib import Path;from nexus.execution.ownership import RuntimeOwner;import sys;owner=RuntimeOwner(Path(sys.argv[1]));assert owner.acquire();print("LOCKED",flush=True);sys.stdin.read();owner.close()'
    process=subprocess.Popen([sys.executable,'-c',code,str(tmp_path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        assert process.stdout.readline().strip()=='LOCKED'
        contender=RuntimeOwner(tmp_path)
        before=(tmp_path/'.controller-owner.json').read_bytes()
        assert contender.acquire() is False
        assert (tmp_path/'.controller-owner.json').read_bytes()==before
        with pytest.raises(ValueError):contender.reconcile(RunStore(tmp_path))
        assert process.poll() is None
    finally:
        process.communicate('',timeout=5)
    assert contender.acquire()
    contender.close()


def test_restart_marks_unknown_and_unstarted_without_replaying(tmp_path):
    store=RunStore(tmp_path)
    ready=store.create_task('base','ready',['src/a.cj'])
    running=store.create_task('base','running',['src/a.cj'])
    store.update_task(running.id,status='GENERATING')
    review=store.create_task('base','review',['src/a.cj'])
    store.update_task(review.id,status='REVIEW_PENDING')
    store.append_record(running.id,'model_call',dict(id='pending',task_id=running.id,origin='TEST',
        model_id='NO_API',request_ref='records/not-replayed.json',status='STARTED'))
    before=store.records(running.id,'model_call')
    owner=RuntimeOwner(tmp_path)
    assert owner.acquire()
    try:
        key=owner.session_key()
        assert len(key)==32 and (tmp_path/'.session-key').stat().st_mode&0o777==0o600
        affected=owner.reconcile(store)
        assert {r['task_id']:r['status'] for r in affected}=={ready.id:'BLOCKED',running.id:'IN_DOUBT'}
        assert store.get_task(review.id).status=='REVIEW_PENDING'
        assert store.records(running.id,'model_call')==before
        assert store.records(running.id,'candidate')==[]
        assert store.records(running.id,'check')==[]
        assert store.records(running.id,'event')[-1]['type']=='CONTROLLER_RESTARTED'
        assert owner.reconcile(store)==[]
    finally:owner.close()
    another=RuntimeOwner(tmp_path)
    assert another.acquire()
    try:assert another.session_key()==key
    finally:another.close()


def test_unconfirmed_owner_api_is_read_only_and_reports_reason(tmp_path):
    from nexus.web.app import create_app
    from nexus.execution.delivery import DeliveryService
    from test_web import Loop
    store=RunStore(tmp_path)
    loop=Loop()
    app=create_app(store,loop,DeliveryService(store),writes_enabled=False)
    client=app.test_client();client.get('/')
    with client.session_transaction() as session:token=session['csrf']
    headers={'Origin':'http://localhost','X-CSRF-Token':token}
    response=client.post('/api/requirements/drafts',json={'project':'order-demo-bug','goal':'test'},headers=headers)
    assert response.status_code==503 and response.json['code']=='OWNER_UNCONFIRMED'
    environment=client.get('/api/environment').json
    assert environment['ready'] is False
    assert any(item['code']=='OWNER_UNCONFIRMED' for item in environment['missing'])
    assert loop.calls==0


def test_managed_real_mcp_write_requires_the_held_controller_lease(tmp_path):
    import asyncio
    from nexus.contracts import file_hash
    from nexus.execution.workspace import WorkspaceStore
    from nexus.mcp.client import ToolClient
    fixture=Path(__file__).resolve().parents[1]/'fixtures/order-demo'
    ws=WorkspaceStore(tmp_path,registered=[fixture])
    baseline=ws.import_project(fixture,'.')
    store=RunStore(tmp_path)
    task=store.create_task(baseline,'ownership',['src/quantity.cj'])
    content=ws.read_file(baseline,'src/quantity.cj')
    arguments=dict(task_id=task.id,proposal=dict(edits=[dict(path='src/quantity.cj',
        before_hash=file_hash(content),content=content+'\n// owned write\n')],requirement_refs=['goal']))
    owner=RuntimeOwner(tmp_path)
    assert owner.acquire()
    owner.close()  # A stale metadata token is not ownership.
    async def denied():
        async with ToolClient(tmp_path) as client:
            result=await client.call_tool('candidate.apply',arguments)
            assert result.operation_status=='ERROR' and 'OWNER_UNCONFIRMED' in result.error
            read=await client.call_tool('workspace.list_files',dict(baseline_id=baseline,task_id=task.id))
            assert read.operation_status=='OK'
        assert store.get_task(task.id).attempt_count==0
    asyncio.run(denied())
    assert owner.acquire()
    async def allowed():
        async with ToolClient(tmp_path) as client:
            result=await client.call_tool('candidate.apply',arguments)
            assert result.operation_status=='OK',result
    try:asyncio.run(allowed())
    finally:owner.close()
    assert store.get_task(task.id).attempt_count==1
