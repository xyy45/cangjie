"""Real Cangjie code under Native MCP/Policy execution; no model call."""
import asyncio
import json
from pathlib import Path
import threading
import pytest
from werkzeug.serving import make_server

from nexus.contracts import file_hash
from nexus.execution.delivery import DeliveryService
from nexus.execution.ownership import RuntimeOwner
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient
from nexus.store import RunStore
from nexus.web.app import create_app

pytestmark=pytest.mark.sdk
ROOT=Path(__file__).resolve().parents[2]


def test_real_cangjie_cannot_read_operator_key_or_read_approval_data(tmp_path):
    ws=WorkspaceStore(tmp_path,registered=[ROOT/'fixtures/order-demo-bug'])
    baseline=ws.import_project(ROOT/'fixtures/order-demo-bug','.')
    store=RunStore(tmp_path)
    task=store.create_task(baseline,'HAND_WRITTEN native security probe',['src/quantity.cj'])
    owner=RuntimeOwner(tmp_path);assert owner.acquire()
    class NoModel:
        async def run(self,*args):raise AssertionError('Security probe must not start model')
    try:
        key=owner.operator_key()
        app=create_app(store,NoModel(),DeliveryService(store),operator_key=key)
        statuses=[]
        @app.after_request
        def observed(response):
            from flask import request
            if request.path=='/api/tasks':statuses.append(response.status_code)
            return response
        server=make_server('127.0.0.1',0,app)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        probe=r'''
import std.fs.*
import std.net.*
import std.console.*
import std.process.*

func controllerBoundaryProbe(): Unit {
    try {
        let child = Process.start("/bin/sh", ["-c", "printf UNEXPECTED_SHELL"])
        let ignored = child.wait()
        throw Exception("Candidate started a shell")
    } catch (error: ProcessException) {
        if (!error.message.contains("Operation not permitted")) {
            throw Exception("Expected process execution denial")
        }
    }
    if (Console.stdIn.readln() != None) {
        throw Exception("Controller stdin leaked to candidate")
    }
    try {
        let ignored = File.readFrom(PRIVATE_PATH)
        throw Exception("Controller credential was readable")
    } catch (error: FSException) {
        if (!error.message.contains("Operation not permitted")) {
            throw Exception("Expected sandbox permission denial")
        }
    }
    try (socket = TcpSocket("127.0.0.1", PROBE_PORT)) {
        socket.connect()
        socket.write("GET /api/tasks HTTP/1.0\r\nHost: 127.0.0.1:PROBE_PORT\r\nConnection: close\r\n\r\n".toArray())
        let buffer = Array<Byte>(4096, repeat: 0)
        let count = socket.read(buffer)
        let response = String.fromUtf8(buffer[..count])
        if (!response.startsWith("HTTP/1.0 403")) {
            throw Exception("Unpaired candidate reached controller data")
        }
    }
}
'''.replace('PRIVATE_PATH',json.dumps(str(tmp_path/'.operator-key'),ensure_ascii=False)).replace('PROBE_PORT',str(server.server_port))
        source=ws.read_file(baseline,'src/quantity.cj')
        content=source.replace('package orderdemo','package orderdemo\n'+probe).replace(
            'quantity >= 0','controllerBoundaryProbe()\n    quantity >= 1')
        assert content!=source and key not in content
        async def run():
            async with ToolClient(tmp_path) as client:
                applied=await client.call_tool('candidate.apply',dict(task_id=task.id,proposal=dict(
                    edits=[dict(path='src/quantity.cj',before_hash=file_hash(source),content=content)],requirement_refs=['goal'])))
                assert applied.operation_status=='OK',applied
                args=dict(task_id=task.id,candidate_id=applied.data['id'],expected_tree_hash=applied.data['tree_hash'])
                for name in ('build','test'):
                    result=await client.call_tool('candidate.'+name,args)
                    assert result.operation_status=='OK' and result.data['state']=='PASS',result
                    if name=='test':assert result.data['counts']['passed']==11
                    if name=='test':assert result.data['execution_argv']==[
                        ['cjpm','test','--no-run'],['cjpm','test','--skip-build']]
        try:
            asyncio.run(run())
            assert statuses==[403]*11,statuses
            assert store.records(task.id,'acceptance')==[]
            assert store.records(task.id,'model_call')==[]
            (tmp_path/'boundary-summary.json').write_text(json.dumps(dict(
                origin='HAND_WRITTEN_NATIVE_SECURITY_PROBE',task_id=task.id,
                run_directory=str(tmp_path),http_statuses=statuses,
                credential_read='PERMISSION_DENIED_IN_REAL_CANGJIE',stdin='EOF_IN_REAL_CANGJIE',
                shell_start='PERMISSION_DENIED_IN_REAL_CANGJIE',
                acceptance_count=0,model_calls=0,checks=store.records(task.id,'check')),indent=2))
        finally:server.shutdown();server.server_close();thread.join(timeout=3)
    finally:owner.close()
