import asyncio
from pathlib import Path
from nexus.contracts import file_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient
from nexus.store import RunStore

ROOT=Path(__file__).resolve().parents[2]


def setup(tmp_path):
    fixture=ROOT/'fixtures/order-demo'
    ws=WorkspaceStore(tmp_path,registered=[fixture])
    baseline=ws.import_project(fixture,'.')
    store=RunStore(tmp_path)
    task=store.create_task(baseline,'test request identity',['src/quantity.cj'])
    content=ws.read_file(baseline,'src/quantity.cj')
    args=dict(task_id=task.id,request_id='same-write',proposal=dict(edits=[dict(path='src/quantity.cj',
        before_hash=file_hash(content),content=content+'\n// one write\n')],requirement_refs=['goal']))
    return ws,store,task,args


def test_completed_request_returns_same_candidate_across_real_server_sessions(tmp_path):
    ws,store,task,args=setup(tmp_path)
    async def run():
        async with ToolClient(tmp_path) as client:
            first=await client.call_tool('candidate.apply',args)
            assert first.operation_status=='OK'
        async with ToolClient(tmp_path) as client:
            repeated=await client.call_tool('candidate.apply',args)
            assert repeated.operation_status=='OK',repeated
            assert repeated.data['id']==first.data['id']
            changed={**args,'proposal':{**args['proposal'],'requirement_refs':['changed']}}
            denied=await client.call_tool('candidate.apply',changed)
            assert denied.operation_status=='ERROR' and 'REQUEST_ID_REUSED' in denied.error
        assert store.get_task(task.id).attempt_count==1
        assert len(store.records(task.id,'candidate'))==1
    asyncio.run(run())


def test_missing_completed_artifact_never_reexecutes_write(tmp_path):
    ws,store,task,args=setup(tmp_path)
    async def run():
        async with ToolClient(tmp_path) as client:
            first=await client.call_tool('candidate.apply',args)
            assert first.operation_status=='OK'
            diff=tmp_path/first.data['diff_ref']
            diff.write_text('tampered')
            result=await client.call_tool('candidate.apply',args)
            assert result.operation_status=='IN_DOUBT'
            assert store.get_task(task.id).attempt_count==1
    asyncio.run(run())


def test_concurrent_real_clients_commit_only_one_candidate(tmp_path):
    ws,store,task,args=setup(tmp_path)
    async def run():
        async with ToolClient(tmp_path) as left, ToolClient(tmp_path) as right:
            results=await asyncio.gather(left.call_tool('candidate.apply',args),
                                         right.call_tool('candidate.apply',args))
        assert all(result.operation_status in ('OK','IN_DOUBT') for result in results),results
        assert any(result.operation_status=='OK' for result in results)
        assert store.get_task(task.id).attempt_count==1
        assert len(store.records(task.id,'candidate'))==1
    asyncio.run(run())


def test_missing_original_operation_request_never_reexecutes(tmp_path):
    ws,store,task,args=setup(tmp_path)
    async def run():
        async with ToolClient(tmp_path) as client:
            assert (await client.call_tool('candidate.apply',args)).operation_status=='OK'
            with store.connect() as db:
                ref=db.execute('SELECT request_ref FROM tool_requests WHERE task_id=?',(task.id,)).fetchone()[0]
            (tmp_path/ref).unlink()
            result=await client.call_tool('candidate.apply',args)
            assert result.operation_status=='IN_DOUBT'
            assert store.get_task(task.id).attempt_count==1
    asyncio.run(run())


def test_interrupted_operation_is_in_doubt_and_never_replayed(tmp_path):
    ws,store,task,args=setup(tmp_path)
    async def run():
        async with ToolClient(tmp_path) as client:
            assert (await client.call_tool('candidate.apply',args)).operation_status=='OK'
        # Simulate loss of the durable completion after an actual write, not a successful model.
        with store.connect() as db:
            db.execute("UPDATE tool_requests SET state='STARTED',result_ref=NULL WHERE task_id=?",(task.id,))
        async with ToolClient(tmp_path) as client:
            result=await client.call_tool('candidate.apply',args)
            assert result.operation_status=='IN_DOUBT'
            assert result.error=='REQUEST_IN_FLIGHT_OR_INTERRUPTED'
        assert store.get_task(task.id).attempt_count==1
        assert len(store.records(task.id,'candidate'))==1
    asyncio.run(run())
