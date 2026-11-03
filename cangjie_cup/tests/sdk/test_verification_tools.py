import asyncio
from pathlib import Path
import pytest
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.contracts import CandidateProposal, file_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.store import RunStore

pytestmark = pytest.mark.sdk
ROOT = Path(__file__).resolve().parents[2]


def test_build_fail_test_not_run_and_changed_source_invalidates_check(tmp_path):
    ws = WorkspaceStore(tmp_path, registered=[ROOT/'fixtures/order-demo'])
    baseline = ws.import_project(ROOT/'fixtures/order-demo', '.')
    store = RunStore(tmp_path)
    task = store.create_task(baseline, 'fix', ['src/quantity.cj'])
    content = ws.read_file(baseline, 'src/quantity.cj')
    p = CandidateProposal(edits=[dict(path='src/quantity.cj', before_hash=file_hash(content), content='invalid syntax')], requirement_refs=['goal'])
    candidate = ws.apply_candidate(task, p)
    async def run():
        verifier = CangjieVerifier(tmp_path, task.id)
        build = await verifier.build(candidate.id)
        assert build.state == 'FAIL', build.diagnostics
        assert (await verifier.test(candidate.id)).state == 'NOT_RUN'
        good = await verifier.build(baseline)
        assert good.state == 'PASS', good.diagnostics
        assert (await verifier.test(baseline)).state == 'PASS'
        (ws.subject_path(baseline)/'src/quantity.cj').write_text('tampered')
        assert (await verifier.test(baseline)).state == 'UNKNOWN'
    asyncio.run(run())


def test_real_mcp_apply_build_test(tmp_path):
    from nexus.mcp.client import ToolClient
    ws = WorkspaceStore(tmp_path, registered=[ROOT/'fixtures/order-demo'])
    baseline = ws.import_project(ROOT/'fixtures/order-demo', '.')
    task = RunStore(tmp_path).create_task(baseline, 'check candidate', ['src/quantity.cj'])
    content = ws.read_file(baseline, 'src/quantity.cj')
    async def run():
        async with ToolClient(tmp_path) as client:
            diagnosed = await client.call_tool('project.diagnose', dict(task_id=task.id, request_id='diagnose', subject_id=baseline))
            assert diagnosed.data['build']['state'] == 'PASS', diagnosed
            applied = await client.call_tool('candidate.apply', dict(task_id=task.id, request_id='apply', proposal=dict(
                edits=[dict(path='src/quantity.cj', before_hash=file_hash(content), content=content+'\n// real candidate\n')], requirement_refs=['goal'])))
            assert applied.operation_status == 'OK', applied
            args = dict(task_id=task.id, candidate_id=applied.data['id'], expected_tree_hash=applied.data['tree_hash'])
            build = await client.call_tool('candidate.build', dict(**args, request_id='build'))
            assert build.data['state'] == 'PASS', build
            test = await client.call_tool('candidate.test', dict(**args, request_id='test'))
            assert test.data['state'] == 'PASS' and test.data['counts']['total'] == 11, test
    asyncio.run(run())
