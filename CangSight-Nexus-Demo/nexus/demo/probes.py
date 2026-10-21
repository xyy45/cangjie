"""Fixed owned proposals verify native denial; no arbitrary path parameter."""
import asyncio
import time

from nexus.contracts import digest, file_hash, tree_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient
from nexus.policy.client import PolicyClient
from nexus.scenarios import ROOT, get_scenario
from nexus.store import uid


async def execute_approval_probe(store,task_id):
    """Exercise a no-approval native decision; never create/consume acceptance."""
    from nexus.contracts import ToolResult
    from nexus.policy.gate import gate_and_execute
    task=store.get_task(task_id)
    if task.status!='REVIEW_PENDING':raise ValueError('Approval probe requires a reviewable task')
    selected=[e['selected_candidate_id'] for e in store.records(task.id,'event') if 'selected_candidate_id' in e]
    if not selected:raise ValueError('No reviewed candidate')
    ws=WorkspaceStore(store.root);candidate=ws.candidate(selected[-1]);executed=[]
    request=dict(schema_version=1,policy_version='1.1',request_id=uid(),task_id=task.id,
        action='candidate.export',paths=[],input_tree_hash=candidate.tree_hash,
        arguments_hash=digest({'probe':'export-without-approval','candidate_id':candidate.id}),
        remaining_budget=0,accepted=False,approval_binding='',deadline_at=int(time.time()*1000)+30000)
    async def action():
        executed.append(True)
        return ToolResult(operation_status='ERROR',error='Probe action must never execute')
    store.append_record(task.id,'event',dict(type='POLICY_PROBE',request_id=request['request_id'],
        label='未批准导出探测',candidate_id=candidate.id))
    result=await gate_and_execute(request,action,audit=lambda payload:store.append_record(task.id,'event',{'policy':payload}))
    return dict(task_id=task.id,request_id=request['request_id'],probe=True,action_executed=bool(executed),
        operation_status=result.operation_status,error=result.error)


async def execute_probe(store,case_id):
    scenario=get_scenario(case_id)
    if scenario['kind']!='probe':raise ValueError('Not a registered policy probe')
    source=ROOT/scenario['source']
    ws=WorkspaceStore(store.root,registered=[source])
    baseline=ws.import_project(source,'.')
    identity=tree_hash(ws.verify_baseline(baseline))
    task=store.create_task(baseline,scenario['title'],scenario['allowed_paths'])
    target=scenario['probe_target']
    request=dict(schema_version=1,policy_version='1.1',request_id=uid(),task_id=task.id,
        action='candidate.apply',paths=[target],input_tree_hash=identity,arguments_hash=digest({'probe':case_id,'target':target}),
        remaining_budget=1,accepted=False,approval_binding='',deadline_at=int(time.time()*1000)+30000)
    decision=await PolicyClient(ROOT).decide(request)
    status='IN_DOUBT'
    if decision['decision']=='Deny' and decision.get('reason')=='PROTECTED_PATH':
        # Invalid target is rejected by the public MCP contract too. It is never
        # normalized/read on the host, and cannot reach a write operation.
        async with ToolClient(store.root) as client:
            result=await client.call_tool('candidate.apply',dict(task_id=task.id,request_id=uid(),
                proposal=dict(edits=[dict(path=target,before_hash='0'*64,content='// controlled rejected proposal\n')],
                              requirement_refs=['REQ-SCOPE'])))
        unchanged=tree_hash(ws.verify_baseline(baseline))==identity
        if result.operation_status=='ERROR' and unchanged and not store.records(task.id,'candidate'):
            status='REJECTED'
        store.append_record(task.id,'event',dict(type='NATIVE_PROBE',case_id=case_id,target=target,
            policy={'request':request,'decision':decision},mcp_status=result.operation_status,
            baseline_unchanged=unchanged,candidate_writes=len(store.records(task.id,'candidate'))))
    else:
        store.append_record(task.id,'event',dict(type='NATIVE_PROBE',case_id=case_id,target=target,
            policy={'request':request,'decision':decision},mcp_status='NOT_RUN',baseline_unchanged=True,candidate_writes=0))
    store.update_task(task.id,status=status)
    return dict(task_id=task.id,status=status)
