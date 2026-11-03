import asyncio
import time
from nexus.contracts import ToolResult
from nexus.policy.gate import gate_and_execute


def test_gate_records_actual_action_outcome_and_request_binding():
    events=[]
    class Policy:
        async def decide(self,request):return {**request,'decision':'Allow','reason':'PERMITTED'}
        def component_identity(self):return {}
    request=dict(schema_version=1,policy_version='1.1',request_id='req',task_id='task',action='candidate.build',
        input_tree_hash='a'*64,arguments_hash='b'*64,approval_binding='',deadline_at=int(time.time()*1000)+10000)
    async def action():return ToolResult(operation_status='ERROR',error='BUILD_FAILED')
    def audit(payload):events.append(payload);return 'records/test.json'
    result=asyncio.run(gate_and_execute(request,action,policy=Policy(),audit=audit))
    assert result.operation_status=='ERROR'
    outcome=events[-1]['policy_outcome']
    assert outcome['request_id']=='req' and outcome['action_executed'] is True
    assert outcome['operation_status']=='ERROR' and outcome['error']=='BUILD_FAILED'


def test_need_approval_has_zero_action_execution():
    events=[]
    class Policy:
        async def decide(self,request):return {**request,'decision':'NeedApproval','reason':'ACCEPTANCE_REQUIRED'}
    async def action():raise AssertionError('export must not execute')
    def audit(payload):events.append(payload);return 'records/test.json'
    asyncio.run(gate_and_execute({'request_id':'approval','action':'candidate.export'},action,policy=Policy(),audit=audit))
    assert events[-1]['policy_outcome']['action_executed'] is False
