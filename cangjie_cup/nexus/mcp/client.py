"""One owned stdio session; never retries a write or paid operation."""
from contextlib import AsyncExitStack
import json
from pathlib import Path
import sys
import time
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from nexus.contracts import ToolResult
from nexus.execution.ownership import owner_token


class ToolClient:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.session = None
        self.stack = AsyncExitStack()

    async def __aenter__(self):
        try:
            token=owner_token(self.root)
            read, write = await self.stack.enter_async_context(stdio_client(StdioServerParameters(
                command=sys.executable, args=['-m', 'cang_sight_server.server', '--root', str(self.root)],
                env={'CANGSIGHT_OWNER_TOKEN':token} if token else {},
                cwd=str(Path(__file__).resolve().parents[2]))))
            self.session = await self.stack.enter_async_context(ClientSession(read, write))
            await self.session.initialize()
            return self
        except BaseException:
            await self.stack.aclose()
            raise

    async def __aexit__(self, *args):
        self.session = None
        await self.stack.aclose()

    async def list_tools(self) -> list[dict[str, object]]:
        if self.session is None:
            raise RuntimeError('MCP disconnected')
        result = await self.session.list_tools()
        return [tool.model_dump() for tool in result.tools]

    async def call_tool(self, name: str, arguments: dict[str, object]) -> ToolResult:
        write = name in ('candidate.apply', 'candidate.build', 'candidate.test', 'candidate.export', 'project.diagnose')
        try:
            if self.session is None:
                raise RuntimeError('MCP disconnected')
            arguments = {'schema_version':1,'tool_version':'1.1','request_id':uuid.uuid4().hex,
                         'deadline_at':int(time.time()*1000)+480000,**arguments}
            result = await self.session.call_tool(name, arguments)
            if result.isError:
                return ToolResult(operation_status='ERROR', error=str(result.content))
            payload=json.loads(result.content[0].text)
            if type(payload.get('schema_version')) is not int or payload['schema_version']!=1:
                raise ValueError('Unsupported MCP result schema version')
            return ToolResult.model_validate(payload)
        except Exception as exc:
            return ToolResult(operation_status='IN_DOUBT' if write else 'ERROR', error=f'MCP transport/result unavailable: {type(exc).__name__}')
