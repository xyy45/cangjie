"""Actual MCP/Policy/cjpm failure feeds actual previous code; no model call."""
import asyncio
from pathlib import Path
import pytest
from nexus.contracts import CandidateRecord, file_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient
from nexus.repair.feedback import build_feedback
from nexus.store import RunStore

pytestmark = pytest.mark.sdk
ROOT = Path(__file__).resolve().parents[2]


def test_actual_failed_candidate_feedback_preserves_baseline_and_real_diff(tmp_path):
    fixture = ROOT/'fixtures/order-demo-bug'
    ws = WorkspaceStore(tmp_path,registered=[fixture])
    baseline = ws.import_project(fixture,'.')
    store = RunStore(tmp_path)
    task = store.create_task(baseline,'Fix quantity',['src/quantity.cj'])
    original = ws.read_file(baseline,'src/quantity.cj')
    changed = original.replace('quantity >= 0', 'quantity >= -1')
    assert changed != original
    async def run():
        async with ToolClient(tmp_path) as client:
            async def call(name, **args):
                result = await client.call_tool(name,dict(task_id=task.id,request_id=name,**args))
                assert result.operation_status == 'OK',result
                return result.data
            candidate = CandidateRecord.model_validate(await call('candidate.apply',proposal={
                'edits':[dict(path='src/quantity.cj',before_hash=file_hash(original),content=changed)],
                'requirement_refs':['REQ-QTY']}))
            args=dict(candidate_id=candidate.id,expected_tree_hash=candidate.tree_hash)
            build=await call('candidate.build',**args)
            test=await call('candidate.test',**args)
            assert build['state']=='PASS' and test['state']=='FAIL'
            assert test['counts']['failed'] > 0 and test['counts']['total']==11
            diff=await call('candidate.diff',candidate_id=candidate.id)
            feedback=build_feedback(candidate,diff,build,test,remaining_budget=2,
                                    requirement_refs=['REQ-QTY'],diagnostics_public=True)
            assert feedback.diff == ws.diff(candidate.id)
            assert feedback.edited_files[0].content == (ws.subject_path(candidate.id)/'src/quantity.cj').read_text()
            assert feedback.edited_files[0].before_hash == file_hash(original)
            assert 'zeroQuantity' in feedback.diagnostic_snippets[0]['text']
            assert ws.read_file(baseline,'src/quantity.cj') == original
    asyncio.run(run())
