import asyncio
from nexus.mcp.client import ToolClient


def test_legal_mcp_proposal_denied_when_native_policy_unavailable(tmp_path, monkeypatch):
    import sys
    from pathlib import Path
    from mcp import StdioServerParameters
    from mcp.client.stdio import stdio_client as real_stdio
    from nexus.contracts import CandidateProposal, file_hash, tree_hash
    from nexus.execution.workspace import WorkspaceStore
    from nexus.store import RunStore
    source = Path(__file__).resolve().parents[2] / 'fixtures/order-demo'
    root = tmp_path / 'runs'
    ws = WorkspaceStore(root, registered=[source])
    baseline = ws.import_project(source, '.')
    store = RunStore(root)
    task = store.create_task(baseline, 'change', ['src/quantity.cj'])
    content = ws.read_file(baseline, 'src/quantity.cj')
    proposal = CandidateProposal(edits=[dict(path='src/quantity.cj', before_hash=file_hash(content),
        content=content+'\n// legal candidate\n')], requirement_refs=['goal'])
    before = tree_hash(ws.subject_path(baseline))
    # Only fault-inject the native binary location in an independent real server.
    # No SDK/Policy success is synthesized; the executable truly does not exist.
    code = """import asyncio, sys
from pathlib import Path
import nexus.policy.gate as gate
from nexus.policy.client import PolicyClient
from cang_sight_server.server import main
gate.PolicyClient = lambda _: PolicyClient(Path(sys.argv[2]))
asyncio.run(main(Path(sys.argv[1])))
"""
    def missing_policy_transport(parameters):
        return real_stdio(StdioServerParameters(command=sys.executable,
            args=['-c', code, str(root), str(tmp_path / 'missing-policy')], cwd=parameters.cwd))
    monkeypatch.setattr('nexus.mcp.client.stdio_client', missing_policy_transport)
    async def run():
        async with ToolClient(root) as client:
            result = await client.call_tool('candidate.apply', dict(task_id=task.id,
                request_id='legal-without-policy', proposal=proposal.model_dump()))
            assert result.operation_status == 'ERROR'
            assert result.error == 'POLICY_UNAVAILABLE'
            assert result.data['policy']['decision'] == 'Deny'
    asyncio.run(run())
    assert store.get_task(task.id).attempt_count == 0
    assert store.records(task.id, 'candidate') == []
    assert list((root / 'candidates').iterdir()) == []
    assert tree_hash(ws.subject_path(baseline)) == before


def test_native_gate_allows_real_mcp_candidate(tmp_path):
    from pathlib import Path
    from nexus.execution.workspace import WorkspaceStore
    from nexus.store import RunStore
    from nexus.contracts import file_hash
    source = Path(__file__).resolve().parents[2] / 'fixtures/order-demo'
    ws = WorkspaceStore(tmp_path, registered=[source])
    baseline = ws.import_project(source, '.')
    task = RunStore(tmp_path).create_task(baseline, 'change', ['src/quantity.cj'])
    content = ws.read_file(baseline, 'src/quantity.cj')
    async def run():
        async with ToolClient(tmp_path) as client:
            result = await client.call_tool('candidate.apply', dict(task_id=task.id, request_id='apply-one',
                proposal=dict(edits=[dict(path='src/quantity.cj', before_hash=file_hash(content),
                                          content=content+'\n// candidate\n')], requirement_refs=['goal'])))
            assert result.operation_status == 'OK', result.error
            diff = await client.call_tool('candidate.diff', dict(task_id=task.id, request_id='diff-one', candidate_id=result.data['id']))
            assert '+// candidate' in diff.data['diff']
    asyncio.run(run())
