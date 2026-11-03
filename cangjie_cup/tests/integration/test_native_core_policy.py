"""The new native policy must enforce service-held scope and version facts."""
import asyncio
from copy import deepcopy
import importlib
import time

import pytest

from nexus.contracts import ToolResult, digest
from nexus.policy.gate import gate_and_execute
from nexus.policy.core import PROJECT_ROOT


def request(action='candidate.apply'):
    now=int(time.time()*1000)
    return dict(schema_version=1,policy_version='2.0',deadline_at=now+30000,approval_binding='',
        action=action,task_id='task',request_id='request',paths=['src/a.cj'] if action=='candidate.apply' else [],
        input_tree_hash='a'*64,arguments_hash='b'*64,remaining_budget=2,accepted=False,
        facts=dict(task_id='task',subject_task_id='task',subject_id='candidate',status='APPLYING',revision=4,
            task_hash='f'*64,allowed_paths=['src/a.cj'],spec_hash='c'*64,verification_plan_hash='d'*64,
            tree_hash='a'*64,check_set_hash='',now_ms=now,approval={},export_verified=False))


def policy():
    module=importlib.import_module('nexus.policy.core')
    assert hasattr(module,'NativePolicyClient'),'new native runtime policy adapter is missing'
    return module.NativePolicyClient(PROJECT_ROOT)


def test_native_exact_scope_allows_only_the_confirmed_files():
    good=request()
    assert asyncio.run(policy().decide(good))['decision']=='Allow'
    for paths,reason in [(['src/b.cj'],'OUTSIDE_SCOPE'),(['src/a.cj','src/a.cj'],'DUPLICATE_PATH'),
                          (['src/a_test.cj'],'PROTECTED_PATH')]:
        bad=deepcopy(good);bad['paths']=paths
        result=asyncio.run(policy().decide(bad))
        assert result['decision']=='Deny' and result['reason']==reason


@pytest.mark.parametrize('field,value', [('status','DELIVERED'),('status','GENERATING'),
    ('revision',-1),('subject_task_id','foreign'),('tree_hash','e'*64),('spec_hash','invalid')])
def test_native_state_or_version_denial_executes_no_action(field,value):
    data=request();data['facts'][field]=value;executed=[]
    async def action():
        executed.append(True)
        return ToolResult(operation_status='OK')
    result=asyncio.run(gate_and_execute(data,action,policy=policy()))
    assert result.operation_status=='ERROR' and not executed


def export_request():
    data=request('candidate.export');facts=data['facts'];facts['status']='REVIEW_PENDING';facts['check_set_hash']='e'*64
    facts['approval']=dict(task_id='task',candidate_id='candidate',tree_hash='a'*64,
        spec_hash='c'*64,verification_plan_hash='d'*64,check_set_hash='e'*64,expires_at_ms=facts['now_ms']+20000)
    data.update(accepted=True,approval_binding=digest(facts['approval']))
    return data


def test_native_approval_is_bound_to_current_versions_and_expiry():
    good=export_request()
    assert asyncio.run(policy().decide(good))['decision']=='Allow'
    for field,value in [('task_id','foreign'),('candidate_id','other'),('tree_hash','f'*64),
                        ('spec_hash','f'*64),('verification_plan_hash','f'*64),('check_set_hash','f'*64),('expires_at_ms',1)]:
        data=deepcopy(good);data['facts']['approval'][field]=value
        result=asyncio.run(policy().decide(data))
        assert result['decision']=='NeedApproval',field
    data=deepcopy(good);data['accepted']=False;data['facts']['approval']={};data['approval_binding']=''
    assert asyncio.run(policy().decide(data))['decision']=='NeedApproval'


def test_fresh_precondition_failure_is_audited_without_entering_action():
    data=request();executed=[];events=[]
    def precondition():raise ValueError('Task revision changed')
    async def action():
        executed.append(True)
        return ToolResult(operation_status='OK')
    result=asyncio.run(gate_and_execute(data,action,policy=policy(),precondition=precondition,
        audit=lambda payload:events.append(payload) or str(len(events))))
    assert result.error=='POLICY_STATE_CHANGED' and not executed
    assert events[-1]['policy_outcome']['action_executed'] is False


def test_active_mcp_uses_native_exact_scope_and_records_its_actual_proof(tmp_path):
    from nexus.store import RunStore
    from nexus.execution.workspace import WorkspaceStore
    from nexus.mcp.client import ToolClient
    from nexus.contracts import file_hash
    source=PROJECT_ROOT/'fixtures/order-demo'
    store=RunStore(tmp_path);ws=WorkspaceStore(tmp_path,registered=[source]);baseline=ws.import_project(source,'.')
    task=store.create_task(baseline,'Scope integration',['src/quantity.cj'])
    async def run():
        async with ToolClient(tmp_path) as client:
            original=ws.read_file(baseline,'src/fee.cj')
            result=await client.call_tool('candidate.apply',dict(task_id=task.id,proposal=dict(
                edits=[dict(path='src/fee.cj',before_hash=file_hash(original),content=original+'\n// invalid scope\n')],
                requirement_refs=['REQ-SCOPE'])))
            assert result.operation_status=='ERROR' and result.error=='OUTSIDE_SCOPE'
            assert not store.records(task.id,'candidate')
            original=ws.read_file(baseline,'src/quantity.cj')
            result=await client.call_tool('candidate.apply',dict(task_id=task.id,proposal=dict(
                edits=[dict(path='src/quantity.cj',before_hash=file_hash(original),content=original.replace('quantity <= 1000','quantity <= 999'))],
                requirement_refs=['REQ-SCOPE'])))
            assert result.operation_status=='OK',result
    asyncio.run(run())
    decisions=[e['policy'] for e in store.records(task.id,'event') if e.get('policy',{}).get('decision')]
    assert len(decisions)==2 and all(e['request']['policy_version']=='2.0' for e in decisions)
    assert decisions[0]['decision']['native_proof']['response']['data']['reason']=='OUTSIDE_SCOPE'
    assert decisions[1]['decision']['native_proof']['response']['data']['decision']=='Allow'
