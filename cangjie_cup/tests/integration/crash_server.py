"""Fault-injection MCP process: performs a marker write, then drops the reply."""
import asyncio
import os
from pathlib import Path
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

server=Server('fault-injection')

@server.list_tools()
async def tools():
    return [Tool(name='candidate.apply',description='fault injection',inputSchema={'type':'object','properties':{}})]

@server.call_tool()
async def apply(name,arguments):
    with Path(sys.argv[1]).open('a') as stream:
        stream.write('called\n')
    os._exit(7)

async def main():
    async with stdio_server() as (read,write):
        await server.run(read,write,server.create_initialization_options())

asyncio.run(main())
