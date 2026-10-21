import asyncio
from pathlib import Path
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient

ROOT = Path(__file__).resolve().parents[2]


def test_real_stdio_lists_and_reads_fixture(tmp_path):
    source = ROOT / 'fixtures/order-demo'
    ws = WorkspaceStore(tmp_path, registered=[source])
    baseline = ws.import_project(source, '.')

    async def journey():
        async with ToolClient(tmp_path) as client:
            tools = await client.list_tools()
            assert {t['name'] for t in tools} == {
                'workspace.list_files', 'workspace.read_file', 'workspace.search', 'project.diagnose',
                'candidate.apply', 'candidate.diff', 'candidate.build', 'candidate.test', 'candidate.export'}
            result = await client.call_tool('workspace.read_file', dict(baseline_id=baseline, path='src/quantity.cj'))
            assert result.operation_status == 'OK'
            assert result.data['content'] == (source / 'src/quantity.cj').read_text()
            bad = await client.call_tool('workspace.read_file', dict(baseline_id=baseline, path='../secret'))
            assert bad.operation_status == 'ERROR'
            invalid = await client.call_tool('workspace.search', dict(baseline_id=baseline, query=''))
            assert invalid.operation_status == 'ERROR'
    asyncio.run(journey())


def test_lost_write_is_in_doubt_and_never_replayed(tmp_path):
    async def journey():
        client = ToolClient(tmp_path)
        result = await client.call_tool('candidate.apply', {})
        assert result.operation_status == 'IN_DOUBT'
    asyncio.run(journey())



def test_inflight_write_disconnect_is_not_replayed(tmp_path,monkeypatch):
    import sys
    from mcp import StdioServerParameters
    from mcp.client.stdio import stdio_client as real_stdio
    marker=tmp_path/'calls'
    def crash_transport(parameters):
        return real_stdio(StdioServerParameters(command=sys.executable,
            args=[str(ROOT/'tests/integration/crash_server.py'),str(marker)]))
    monkeypatch.setattr('nexus.mcp.client.stdio_client',crash_transport)
    async def run():
        async with ToolClient(tmp_path) as client:
            result=await client.call_tool('candidate.apply',{})
            assert result.operation_status=='IN_DOUBT'
        assert marker.read_text().splitlines()==['called']
    asyncio.run(run())


def test_real_stdio_search_matches_misses_empty_and_limit(tmp_path):
    source = tmp_path / 'registered'
    (source / 'src').mkdir(parents=True)
    (source / 'cjpm.toml').write_text('[package]\nname="searchdemo"')
    content = 'package searchdemo\n' + ''.join(f'// needle line {n}\n' for n in range(105))
    (source / 'src/search.cj').write_text(content)
    ws = WorkspaceStore(tmp_path / 'runs', registered=[source])
    baseline = ws.import_project(source, '.')
    async def run():
        async with ToolClient(ws.root) as client:
            async def search(query):
                return await client.call_tool('workspace.search', dict(baseline_id=baseline, query=query))
            hit = await search('needle line 104')
            assert hit.operation_status == 'OK'
            assert hit.data == {'matches': [{'path': 'src/search.cj', 'line': 106,
                                             'text': '// needle line 104'}], 'truncated': False}
            missing = await search('not-in-this-project')
            assert missing.operation_status == 'OK'
            assert missing.data == {'matches': [], 'truncated': False}
            empty = await search('')
            assert empty.operation_status == 'ERROR'
            assert empty.error and empty.data == {}
            limited = await search('needle')
            assert limited.operation_status == 'OK'
            assert limited.data['truncated'] is True
            assert limited.data['matches'] == [
                {'path': 'src/search.cj', 'line': n+2, 'text': f'// needle line {n}'} for n in range(100)]
    asyncio.run(run())
