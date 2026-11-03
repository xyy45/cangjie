"""Real SDK/MCP scenarios. Reference changes here are test data, never AI evidence."""
import asyncio
from pathlib import Path

import pytest

from nexus.contracts import file_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient
from nexus.requirements.service import RequirementService
from nexus.scenarios import get_profile
from nexus.store import RunStore
from nexus.demo.probes import execute_probe

pytestmark=pytest.mark.sdk
ROOT=Path(__file__).resolve().parents[2]
REFERENCE={
 'order-price':{'src/price.cj':('price < 1000000','price <= 1000000')},
 'order-discount':{'src/discount.cj':('amount > 100','amount >= 100')},
 'cross-validation':{'src/quantity.cj':('quantity >= 0','quantity >= 1'),'src/fee.cj':('quantity + unitPrice','quantity * unitPrice')},
 'cross-discount':{'src/discount.cj':('amount > 100','amount >= 100'),'src/checkout.cj':('amount + discountFor(amount)','amount - discountFor(amount)')},
 'cross-stock':{'src/stock.cj':('requested <= stock','requested >= 1 && requested <= stock'),'src/inventory.cj':('stock + requested','stock - requested')},
}

@pytest.mark.parametrize('project',REFERENCE)
def test_registered_example_fails_before_and_passes_reference_fix(tmp_path,project):
    store=RunStore(tmp_path);profile=get_profile(project);fixture=ROOT/profile['source']
    ws=WorkspaceStore(tmp_path,registered=[fixture]);base=ws.import_project(fixture,'.')
    service=RequirementService(store);draft=service.prepare_requirement(project,'修复本案例')
    spec=service.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=1,
        requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='REFERENCE_TEST')
    task=service.prepare_task(project,spec.id,base)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    async def run():
        async with ToolClient(tmp_path) as client:
            async def call(name,**args):
                result=await client.call_tool(name,dict(task_id=task.id,request_id=name,**args))
                assert result.operation_status=='OK',result
                return result.data
            diagnosis=await call('project.diagnose',subject_id=base)
            assert diagnosis['build']['state']=='PASS',diagnosis['build']
            assert diagnosis['test']['state']=='FAIL',diagnosis['test']
            edits=[]
            for path,(before,after) in REFERENCE[project].items():
                original=ws.read_file(base,path);assert before in original
                edits.append(dict(path=path,before_hash=file_hash(original),content=original.replace(before,after)))
            candidate=await call('candidate.apply',proposal=dict(edits=edits,requirement_refs=[r.id for r in spec.requirements]))
            for kind in ('build','test'):
                check=await call('candidate.'+kind,candidate_id=candidate['id'],expected_tree_hash=candidate['tree_hash'])
                assert check['state']=='PASS',check
                if kind=='test':assert all(s['state']=='PASS' for s in check['suite_results'].values()),check
    asyncio.run(run())
    assert not store.records(task.id,'model_call')

@pytest.mark.parametrize('case_id',['policy','policy-config','policy-path'])
def test_native_probe_rejects_before_any_write(tmp_path,case_id):
    store=RunStore(tmp_path);result=asyncio.run(execute_probe(store,case_id))
    assert result['status']=='REJECTED'
    event=store.records(result['task_id'],'event')[-2]
    event=next(e for e in store.records(result['task_id'],'event') if e.get('type')=='NATIVE_PROBE')
    assert event['policy']['decision']['decision']=='Deny'
    assert event['policy']['decision']['reason']=='PROTECTED_PATH'
    assert event['mcp_status']=='ERROR' and event['baseline_unchanged'] and event['candidate_writes']==0
    assert not store.records(result['task_id'],'model_call')
