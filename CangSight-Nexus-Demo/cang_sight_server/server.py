"""Independent official MCP SDK stdio server. stdout is protocol only."""
import argparse
import asyncio
import inspect
import os
import time
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from nexus.contracts import ToolResult, digest, tree_hash
from nexus.store import RunStore
from nexus.policy.gate import gate_and_execute
from nexus.policy.client import PolicyClient
from nexus.mcp.requests import RequestLedger
from nexus.execution.ownership import verify_write_owner
from nexus.mcp.tools.candidate import ApplyRequest, DiffRequest, CheckRequest, ExportRequest
from nexus.execution.delivery import DeliveryService
from nexus.mcp.tools.project import DiagnoseRequest, diagnose
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.tools.workspace import ListRequest, ReadRequest, SearchRequest, list_files, read_file, search


def create_server(root: Path) -> Server:
    server = Server('cangsight-nexus')
    ws = WorkspaceStore(root)
    async def gate(context, action):
        return await gate_and_execute(context, action, audit=lambda payload: RunStore(root).append_record(
            context['task_id'], 'event', {'policy': payload}))

    routes = {'workspace.list_files': (ListRequest, list_files),
              'workspace.read_file': (ReadRequest, read_file),
              'workspace.search': (SearchRequest, search)}

    def candidate_diff(ws, request):
        candidate = ws.candidate(request.candidate_id)
        if candidate.task_id != request.task_id:
            raise ValueError('foreign candidate')
        return {'diff': ws.diff(request.candidate_id), 'tree_hash': candidate.tree_hash}

    async def gated_apply(ws, request):
        task = RunStore(root).get_task(request.task_id)
        context = dict(schema_version=1,policy_version='1.1',deadline_at=request.deadline_at,approval_binding='',action='candidate.apply', task_id=task.id, request_id=request.request_id,
                       paths=[edit.path for edit in request.proposal.edits],
                       input_tree_hash=tree_hash(ws.verify_baseline(task.baseline_id)),
                       arguments_hash=digest(request.model_dump()),
                       remaining_budget=3-task.attempt_count, accepted=False)
        async def action():
            verify_write_owner(root,os.environ.get('CANGSIGHT_OWNER_TOKEN'))
            if digest(request.model_dump()) != context['arguments_hash']:
                raise ValueError('policy arguments changed')
            candidate = ws.apply_candidate(task, request.proposal)
            return ToolResult(operation_status='OK', data=candidate.model_dump())
        result = await gate(context, action)
        return result

    routes['candidate.apply'] = (ApplyRequest, gated_apply)
    routes['candidate.diff'] = (DiffRequest, candidate_diff)

    async def gated_check(name, request):
        task = RunStore(root).get_task(request.task_id)
        verifier = CangjieVerifier(root, task.id, deadline_at=request.deadline_at)
        subject_id = request.subject_id if name == 'project.diagnose' else request.candidate_id
        path, identity, _ = verifier.identity(subject_id)
        if name != 'project.diagnose' and identity != request.expected_tree_hash:
            raise ValueError('expected tree changed')
        context = dict(schema_version=1,policy_version='1.1',deadline_at=request.deadline_at,approval_binding='',action=name, task_id=task.id, request_id=request.request_id, paths=[],
                       input_tree_hash=identity, arguments_hash=digest(request.model_dump()),
                       remaining_budget=3-task.attempt_count, accepted=False)
        async def action():
            verify_write_owner(root,os.environ.get('CANGSIGHT_OWNER_TOKEN'))
            if digest(request.model_dump()) != context['arguments_hash']:
                raise ValueError('policy arguments changed')
            if name == 'project.diagnose':
                data = await diagnose(root, request)
            else:
                result = await (verifier.build(subject_id) if name == 'candidate.build' else verifier.test(subject_id))
                data = result.model_dump()
            return ToolResult(operation_status='OK', data=data)
        return await gate(context, action)

    async def build_route(ws, request):
        return await gated_check('candidate.build', request)

    async def test_route(ws, request):
        return await gated_check('candidate.test', request)

    async def diagnose_route(ws, request):
        return await gated_check('project.diagnose', request)

    routes.update({'candidate.build': (CheckRequest, build_route),
                   'candidate.test': (CheckRequest, test_route),
                   'project.diagnose': (DiagnoseRequest, diagnose_route)})

    async def export_route(ws, request):
        delivery = DeliveryService(RunStore(root))
        c = ws.candidate(request.candidate_id)
        if c.task_id != request.task_id:
            raise ValueError('foreign candidate')
        acceptance, _, _ = delivery.acceptance(c.id, request.acceptance_id)
        context = dict(schema_version=1,policy_version='1.1',deadline_at=request.deadline_at,approval_binding='',action='candidate.export',task_id=c.task_id,request_id=request.request_id,
                       paths=[],input_tree_hash=c.tree_hash,arguments_hash=digest(request.model_dump()),
                       remaining_budget=0,accepted=True)
        context['approval_binding'] = digest(acceptance.model_dump())
        async def action():
            verify_write_owner(root,os.environ.get('CANGSIGHT_OWNER_TOKEN'))
            if digest(request.model_dump()) != context['arguments_hash']:
                raise ValueError('policy arguments changed')
            return ToolResult(operation_status='OK',data=delivery.export(c.id,request.acceptance_id))
        return await gate(context,action)

    routes['candidate.export'] = (ExportRequest, export_route)

    @server.list_tools()
    async def tools():
        return [Tool(name=name, description=name, inputSchema=model.model_json_schema())
                for name, (model, _) in routes.items()]

    @server.call_tool()
    async def call(name: str, arguments: dict):
        parsed=None
        replayed=False
        try:
            if name not in routes:
                raise ValueError('tool unavailable; writes require native policy gate')
            model, handler = routes[name]
            parsed = model.model_validate(arguments)
            if parsed.deadline_at<=int(time.time()*1000):
                raise ValueError('REQUEST_DEADLINE_EXCEEDED')
            if parsed.deadline_at>int(time.time()*1000)+480000:
                raise ValueError('REQUEST_DEADLINE_OUT_OF_RANGE')
            if name.startswith('workspace.'):
                actual_input=tree_hash(ws.verify_baseline(parsed.baseline_id))
            elif name=='candidate.apply':
                current=RunStore(root).get_task(parsed.task_id)
                actual_input=tree_hash(ws.verify_baseline(current.baseline_id))
            elif name=='project.diagnose':
                _,actual_input,_=CangjieVerifier(root,parsed.task_id).identity(parsed.subject_id)
            else:
                actual_input=ws.candidate(parsed.candidate_id).tree_hash
            if parsed.input_tree_hash is not None and parsed.input_tree_hash!=actual_input:
                raise ValueError('REQUEST_INPUT_TREE_CHANGED')
            parsed=parsed.model_copy(update={'input_tree_hash':actual_input})
            if name.startswith('workspace.') and parsed.task_id:
                task = RunStore(root).get_task(parsed.task_id)
                if task.baseline_id != parsed.baseline_id:
                    raise ValueError('foreign baseline')
            store=RunStore(root) if parsed.task_id else None
            binding={}
            if store:
                task=store.get_task(parsed.task_id)
                if task.schema_version==2:
                    from nexus.requirements.service import RequirementService
                    spec,frozen=RequirementService(store).task_context(task)
                    binding={'spec_hash':spec.spec_hash,'verification_plan_hash':frozen.plan_hash}
                    if name not in task.allowed_tools:
                        raise ValueError('Tool is not allowed by the task')
            writes=name in ('candidate.apply','candidate.build','candidate.test','candidate.export','project.diagnose')
            ledger=None
            fresh=True
            if writes:
                verify_write_owner(root,os.environ.get('CANGSIGHT_OWNER_TOKEN'))
                ledger=RequestLedger(store)
                binding['policy']=PolicyClient(Path(__file__).resolve().parents[1]).component_identity()
                if name in ('candidate.build','candidate.test','project.diagnose'):
                    subject=parsed.subject_id if name=='project.diagnose' else parsed.candidate_id
                    binding['execution_plan']=CangjieVerifier(root,parsed.task_id).identity(subject)[2]
                if name=='candidate.export':
                    # Cached export is still subject to current acceptance/check/archive validation.
                    DeliveryService(store).acceptance(parsed.candidate_id,parsed.acceptance_id)
                identity=digest({'tool':name,'arguments':parsed.model_dump(exclude={'deadline_at'}),'binding':binding})
                fresh,result=ledger.claim(parsed.task_id,parsed.request_id,name,identity,parsed.model_dump())
                replayed=not fresh
                if not fresh and name=='candidate.apply' and result.operation_status=='OK':
                    ws.candidate(result.data['id'])
            if fresh:
                try:
                    value=handler(ws,parsed)
                    result=await value if inspect.isawaitable(value) else ToolResult(operation_status='OK',data=value)
                except (ValueError,OSError) as exc:
                    result=ToolResult(operation_status='ERROR',error=str(exc))
                if ledger:
                    try:ledger.complete(parsed.task_id,parsed.request_id,result)
                    except (OSError,ValueError):
                        result=ToolResult(operation_status='IN_DOUBT',error='REQUEST_RESULT_NOT_DURABLY_RECORDED')
        except (ValueError, OSError) as exc:
            result = ToolResult(operation_status='ERROR', error=str(exc))
        task_id = arguments.get('task_id')
        if task_id:
            try:
                store = RunStore(root)
                identifier = __import__('uuid').uuid4().hex
                ref = f'records/{identifier}.tool.json'
                (root / ref).write_text(result.model_dump_json())
                request_ref=f'records/{identifier}.tool-request.json'
                (root/request_ref).write_text(__import__('json').dumps({'tool':name,'arguments':arguments},ensure_ascii=False))
                record_ref = store.append_record(task_id, 'tool_call', dict(id=identifier, task_id=task_id,
                    tool=name, status=result.operation_status, result_ref=ref,request_ref=request_ref,
                    request_id=arguments.get('request_id'),tool_version=arguments.get('tool_version'),
                    input_tree_hash=parsed.input_tree_hash if parsed else None,replayed=replayed,
                    candidate_id=getattr(parsed,'candidate_id',None) if parsed else None,
                    policy_ref=next((r for r in result.record_refs if r.endswith('.json')), None)))
                result.record_refs.append(record_ref)
            except ValueError:
                pass
        return [TextContent(type='text', text=result.model_dump_json())]

    return server


async def main(root: Path):
    server = create_server(root)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    asyncio.run(main(parser.parse_args().root))
