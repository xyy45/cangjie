"""Actual SDK/native Array defects with explicit self-built reference fixes.

This is not live LLM/remote MCP quality evidence.
"""
import asyncio,json
import pytest
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.contracts import CandidateProposal,file_hash,source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.repair import oracle,sequences
from nexus.repair.sequence_service import failure_trace
from tests.sdk.test_string_loop_sdk import SERVICES

pytestmark=pytest.mark.sdk


def scenario(kind):
    if kind in ('oracle','property'):
        bad='''package bench
public func total(items: Array<Int64>, fee: Int64): Int64 {
 var amount = fee
 for (item in items) {
  if (item > 0) { amount = amount + item }
 }
 return amount
}
''';fixed=bad.replace('if (item > 0) { amount = amount + item }','amount = amount + item')
        domains=dict(items=dict(values=[[],[0],[1],[1,2],[-1],[1,-1],[-2,3],[2,2]]),fee=dict(min=0,max=2,points=[]))
        if kind=='oracle':model=dict(version=4,function='total',domains=domains,expression='array_sum(items) + fee',seed=7,max_cases=16,excluded_inputs=[])
        else:model=dict(version=3,kind='single',function='total',domains=domains,properties=[dict(id='PROP-TOTAL',text='含负调整的每项均参与累计',precondition='True',assertion='result == array_sum(arg0) + arg1')],seed=7,max_cases=16,excluded_inputs=[])
        return dict(function='total',path='src/order.cj',files={'src/order.cj':bad.encode()},fixed=fixed,model=model,goal='每个订单项目（含负数退款调整）都累加，再加附加费fee；空数组返回fee。',examples=[dict(args=[[1,2],0],expected=3,suite='target'),dict(args=[[],2],expected=2,suite='regression')])
    if kind=='relation':
        bad='''package bench
public func calculate(items: Array<Int64>): Int64 {
 if (items.size == 0) { return 0 }
 return items[0]
}
''';fixed='''package bench
public func calculate(items: Array<Int64>): Int64 {
 var result: Int64 = 0
 for (item in items) { result = result + item }
 return result
}
''';wrapper=b'package bench\npublic func total(items: Array<Int64>): Int64 { calculate(items) }\n'
        model=dict(version=3,kind='relation',function='total',domains=dict(items=dict(values=[[],[0],[2],[1,2],[2,1]])),relations=[dict(id='REL-PERMUTATION',text='和相同但排列不同的项目不得改变合计',precondition='left_arg0 != right_arg0 and array_sum(left_arg0) == array_sum(right_arg0)',assertion='left_result == right_result')],seed=7,max_pairs=16,excluded_inputs=[])
        return dict(function='total',path='src/calculation.cj',files={'src/calculation.cj':bad.encode(),'src/order.cj':wrapper},fixed=fixed,model=model,goal='计算项目合计；数组排列不同但和相同，不得改变合计。只能改计算helper。',examples=[dict(args=[[2]],expected=2,suite='target'),dict(args=[[]],expected=0,suite='regression')])
    bug='if (state[0] == 2 && quantity > 5) { return state }\n'
    bad='''package bench
public func advance(state: Array<Int64>, quantity: Int64): Array<Int64> {
 if (state.size == 2) {
'''+bug+'''  return [state[1], state[0]]
 }
 return state
}
'''
    model=dict(version=3,kind='sequence',function='advance',state_param='state',domains=dict(state=dict(values=[[1,2],[2,1],[]]),quantity=dict(min=0,max=100,points=[])),initial_states=[[1,2]],initial_precondition='True',context_params=[],operations=[dict(id='OP-SWAP',text='交换两项，数量不应改变规则',args=[dict(domain='quantity')],transition='[array_at(state,1), array_at(state,0)] if array_len(state) == 2 else state')],invariants=[dict(id='INV-SHAPE',text='保持两项及其合计',precondition='True',assertion='array_len(result) == 2 and array_sum(result) == 3')],seed=7,max_sequences=8,max_steps=4,excluded_inputs=[])
    return dict(function='advance',path='src/state.cj',files={'src/state.cj':bad.encode()},fixed=bad.replace(bug,''),bug=bug,model=model,goal='每次调用交换两项状态，quantity不改变交换语义；空状态保持空。连续调用必须使用上一次实际返回。',examples=[dict(args=[[1,2],1],expected=[2,1],suite='target'),dict(args=[[],0],expected=[],suite='regression')])


def setup(root,kind):
    data=scenario(kind);store=RunStore(root);uploads=UploadService(store);files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,**data['files']}
    draft=uploads.prepare_project('array-'+kind,None,data['goal'],actor_id='ARRAY_SDK_FIXTURE',request_key='one',entries=files)
    key=dict(oracle='oracle_json',property='properties_json',relation='relations_json',sequence='sequences_json')[kind]
    uploads.confirm(draft['id'],expected_version=1,function=data['function'],examples_json=json.dumps(data['examples']),allowed_paths=[data['path']],consent=True,actor_id='ARRAY_SDK_FIXTURE',**{key:json.dumps(data['model'])})
    source=uploads.source(draft['id'],actor_id='ARRAY_SDK_FIXTURE');ws=WorkspaceStore(root,registered=[source]);baseline=ws.import_project(source,'.')
    req=RequirementService(store);d=req.prepare_requirement(draft['id'],draft['goal']);spec=req.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='ARRAY_SDK_FIXTURE')
    task=req.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,data['path'])
    def candidate(fixed=False):return ws.apply_candidate(store.get_task(task.id),CandidateProposal(edits=[dict(path=data['path'],before_hash=file_hash(original),content=(data['fixed'] if fixed else original)+'\n// reference verification candidate\n')],requirement_refs=['REQ-UPLOAD']))
    return store,ws,task,candidate,data


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_array_public_pass_independent_failure_reference_fix_and_all_history(tmp_path,kind):
    store,ws,task,apply,data=setup(tmp_path.resolve(),kind);verifier=CangjieVerifier(store.root,task.id);engine=SERVICES[kind](store);reports=[]
    for fixed in (False,True):
        candidate=apply(fixed);assert asyncio.run(verifier.build(candidate.id)).state=='PASS'
        public=asyncio.run(verifier.test(candidate.id));assert public.state=='PASS',public.diagnostics
        before=source_manifest(ws.subject_path(candidate.id));report=asyncio.run(engine.run(candidate.id));reports.append(report)
        (tmp_path/(('fixed' if fixed else 'defect')+'-report.json')).write_text(json.dumps(report,ensure_ascii=True,indent=2))
        assert report['state']==('PASS' if fixed else 'FAIL'),(report.get('reason'),report)
        assert report['public_test_state']=='PASS' and engine.verify(candidate.id)==report and source_manifest(ws.subject_path(candidate.id))==before
        for batch in report['batches']:
            log=(store.root/batch['log_ref']).read_text();assert 'NEXUS_EXECUTION_PHASE' in log and '_V3|' in log and 'FIXTURE' not in log
    failed,passed=reports
    if kind=='sequence':
        contract=engine.binding(passed['candidate_id'])[3];retained={sequences.trace_key(failure_trace(contract,f)) for f in failed['failures']}
        assert passed['regression_traces']>0 and retained<={sequences.trace_key(t) for t in passed['batches'][0]['traces']}
        first=failed['batches'][0]['result']['failures'];later=[f for b in failed['batches'][1:] for f in b['result']['failures']]
        assert later and min(sequences.trace_score(failure_trace(contract,f)) for f in later)<min(sequences.trace_score(failure_trace(contract,f)) for f in first)
    elif kind=='relation':
        assert passed['regression_pairs']>0 and failed['failures'][0]['left_actual_return']!=failed['failures'][0]['right_actual_return']
    else:
        assert passed['regression_cases']>0 and {oracle.input_key(f['args']) for f in failed['failures']}<={oracle.input_key(a) for a in passed['batches'][0]['inputs']}
