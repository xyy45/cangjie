"""Narrowed user scope: actual HTTP confirmation and MCP/Policy, no model/build."""
import asyncio
from nexus.contracts import file_hash, tree_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient
from test_web import setup_app


def test_user_narrowed_scope_is_frozen_and_enforced_over_real_mcp(tmp_path):
    store,loop,web,headers=setup_app(tmp_path)
    draft=web.post('/api/requirements/drafts',json={'project':'order-demo-bug','goal':'fix quantity only'},headers=headers).json
    spec=web.post('/api/requirements/drafts/'+draft['id']+'/confirm',headers=headers,json=dict(schema_version=1,
        expected_version=draft['version'],requirements=draft['requirements'],allowed_paths=['src/quantity.cj'])).json
    assert spec['allowed_paths']==['src/quantity.cj']
    response=web.post('/api/tasks',headers=headers,json=dict(project='order-demo-bug',spec_id=spec['id'],idempotency_key='narrow'))
    assert response.status_code==200,response.json
    task=store.get_task(response.json['id'])
    assert task.allowed_paths==['src/quantity.cj'] and task.spec_hash==spec['spec_hash']
    ws=WorkspaceStore(tmp_path)
    baseline=tree_hash(ws.verify_baseline(task.baseline_id))
    async def run():
        async with ToolClient(tmp_path) as client:
            async def propose(path):
                original=ws.read_file(task.baseline_id,path)
                return await client.call_tool('candidate.apply',dict(task_id=task.id,proposal=dict(
                    edits=[dict(path=path,before_hash=file_hash(original),content=original+'\n// explicit scope test\n')],
                    requirement_refs=['REQ-QTY'])))
            rejected=await propose('src/fee.cj')
            assert rejected.operation_status=='ERROR' and 'protected' in rejected.error
            assert store.get_task(task.id).attempt_count==0
            assert store.records(task.id,'candidate')==[]
            allowed=await propose('src/quantity.cj')
            assert allowed.operation_status=='OK',allowed
            assert allowed.data['spec_hash']==spec['spec_hash']
            assert [edit['path'] for edit in allowed.data['edits']]==['src/quantity.cj']
    asyncio.run(run())
    assert tree_hash(ws.verify_baseline(task.baseline_id))==baseline
    assert store.records(task.id,'model_call')==[] and loop.calls==0
