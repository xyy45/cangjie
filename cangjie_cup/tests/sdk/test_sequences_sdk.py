"""Real pinned SDK state chaining. No model or remote analysis requests."""
import asyncio
import json

import pytest

from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.contracts import source_manifest
from nexus.execution.runner import run_command
from nexus.repair import sequences,sequence_trace,oracle
from nexus.uploads.language import inspect_source
from tests.test_sequences import refund_raw
from tests.test_sequence_trace import trajectory
from tests.test_primitive_trace import TOKEN

pytestmark=pytest.mark.sdk


def execute(root,contract,traces,source):
    root=root.resolve();project=root/'project';(project/'src').mkdir(parents=True)
    inspect_source('package bench\n'+source)
    (project/'cjpm.toml').write_bytes(CONFIG);(project/'cjpm.lock').write_bytes(LOCK)
    (project/'src/logic.cj').write_text('package bench\n'+source)
    (project/'src/sequence_observations_test.cj').write_bytes(sequence_trace.harness(contract,traces,'bench',TOKEN))
    before=source_manifest(project);commands=[]
    (root/'verification-input.json').write_text(json.dumps(dict(contract=contract,traces=traces,token=TOKEN,package='bench',project_manifest=before),sort_keys=True))
    code,log,problem=asyncio.run(run_command(project,['cjpm','test'],private_root=root,timeout=60,test_output='all',execution_argv=commands))
    (root/'sdk.log').write_text(log)
    result=sequence_trace.interpret(contract,traces,TOKEN,log,code,problem)
    (root/'verification-result.json').write_text(json.dumps(dict(result=result,exit_code=code,problem=problem,execution_argv=commands),sort_keys=True))
    assert code==0 and problem is None and result['execution_state']=='PASS',(code,problem,log[-4000:])
    assert result['state'] in ('PASS','FAIL') and result['counts']['total']==len(traces)
    assert commands==[['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]
    assert source_manifest(project)==before
    for path in result['observations']:
        assert len({s['test_id'] for s in path['steps']})==1
        assert len({s['source']['start_char'] for s in path['steps']})==len(path['steps'])
    return result


@pytest.mark.parametrize('fixed',[False,True])
def test_sdk_sequences_chain_actual_state_and_stop_at_first_mismatch(tmp_path,fixed):
    raw,signature=refund_raw();contract=sequences.validate_contract(raw,signature,[])
    source='public func refund(state: Int64, amount: Int64, paid: Int64): Int64 {\n if (state >= paid) { return state }\n'
    if fixed:source+=' if (amount > paid - state) { return paid }\n'
    source+=' return state + amount\n}\n'
    result=execute(tmp_path,contract,[trajectory()],source)
    assert result['planned_calls']==3
    if fixed:
        assert result['state']=='PASS' and result['observed_calls']==3 and result['unexecuted_calls']==0
        assert [s['actual_return'] for s in result['observations'][0]['steps']]==[7,10,10]
    else:
        assert result['state']=='FAIL' and result['observed_calls']==2 and result['unexecuted_calls']==1
        assert [s['args'] for s in result['failures'][0]['steps']]==[[0,7,10],[7,7,10]]
        assert result['failures'][0]['actual_return']==14 and result['failures'][0]['expected_state']==10
        assert result['observations'][0]['stop_reason']=='MODEL_MISMATCH'


def test_sdk_bool_state_and_nonfirst_state_parameter(tmp_path):
    signature=dict(name='apply',params=[dict(name='operation',type='Int64'),dict(name='state',type='Bool')],return_type='Bool')
    raw=dict(version=1,kind='sequence',function='apply',state_param='state',domains=dict(operation=dict(min=0,max=0),state={}),initial_states=[True],initial_precondition='True',context_params=[],
        operations=[dict(id='OP-TOGGLE',text='切换',args=[0],transition='not state')],invariants=[dict(id='INV-TOGGLE',text='改变状态',precondition='True',assertion='result != before_state')],seed=0,max_sequences=8,max_steps=4,excluded_inputs=[])
    contract=sequences.validate_contract(raw,signature,[]);trace=dict(initial_state=True,context=[],steps=[dict(operation_id='OP-TOGGLE',args=[0])]*4)
    source='public func apply(operation: Int64, state: Bool): Bool {\n if (operation == 0) { return !state }\n return state\n}\n'
    result=execute(tmp_path,contract,[trace],source)
    assert result['state']=='PASS' and result['observed_calls']==4
    assert [s['args'] for s in result['observations'][0]['steps']]==[[0,True],[0,False],[0,True],[0,False]]
    assert [s['actual_return'] for s in result['observations'][0]['steps']]==[False,True,False,True]


def keep_contract(name='keep',maximum=False):
    values=list(range(16)) if maximum else [oracle.LOW]
    signature=dict(name=name,params=[dict(name='state',type='Int64')],return_type='Int64')
    raw=dict(version=1,kind='sequence',function=name,state_param='state',domains=dict(state=dict(min=values[0],max=values[-1])),initial_states=values,initial_precondition='True',context_params=[],
        operations=[dict(id='OP-KEEP',text='保持',args=[],transition='state')],invariants=[dict(id='INV-KEEP',text='保持状态',precondition='True',assertion='result == before_state')],seed=0,max_sequences=16,max_steps=8,excluded_inputs=[])
    return sequences.validate_contract(raw,signature,[])


@pytest.mark.parametrize('kind',['LOW','128-calls'])
def test_sdk_int64_low_and_128_planned_calls(tmp_path,kind):
    contract=keep_contract(maximum=kind=='128-calls');steps=8 if kind=='128-calls' else 2
    traces=[dict(initial_state=v,context=[],steps=[dict(operation_id='OP-KEEP',args=[])]*steps) for v in contract['initial_states']]
    result=execute(tmp_path,contract,traces,'public func keep(state: Int64): Int64 { return state }\n')
    assert result['state']=='PASS' and result['observed_calls']==result['planned_calls']==len(traces)*steps
    if kind=='128-calls':assert result['counts']['passed']==16 and result['observed_calls']==128
    else:assert [s['actual_return'] for s in result['observations'][0]['steps']]==[oracle.LOW,oracle.LOW]


@pytest.mark.parametrize('name',['__nexusSeqPrint'+TOKEN,'__nexusSeqTarget'+TOKEN,'NexusSequences'+TOKEN])
def test_sdk_observer_aliases_and_class_do_not_shadow_selected_function(tmp_path,name):
    contract=keep_contract(name);trace=dict(initial_state=oracle.LOW,context=[],steps=[dict(operation_id='OP-KEEP',args=[])]*2)
    result=execute(tmp_path,contract,[trace],'public func '+name+'(state: Int64): Int64 { return state }\n')
    assert result['state']=='PASS' and result['observed_calls']==2


def stock_system(root):
    """Two-file public-test-safe defect only exposed after debit then restore."""
    from nexus.contracts import CandidateProposal,file_hash
    from nexus.execution.workspace import WorkspaceStore
    from nexus.requirements.service import RequirementService
    from nexus.store import RunStore
    from nexus.uploads.service import UploadService
    store=RunStore(root);uploads=UploadService(store)
    bug=' if (state < capacity && quantity == capacity - state) { return capacity - 1 }\n'
    source='package bench\npublic func update(state: Int64, operation: Int64, quantity: Int64, capacity: Int64): Int64 {\n if (operation == 0) {\n if (quantity <= state) { return state - quantity }\n return state\n }\n if (quantity > capacity - state) { return capacity }\n'+bug+' return state + quantity\n}\n'
    wrapper=b'package bench\npublic func adjust(state: Int64, operation: Int64, quantity: Int64, capacity: Int64): Int64 { return update(state, operation, quantity, capacity) }\n'
    model=dict(version=1,kind='sequence',function='adjust',state_param='state',domains=dict(state=dict(min=0,max=10),operation=dict(min=0,max=1),quantity=dict(min=0,max=10,points=[3,7]),capacity=dict(min=10,max=10)),
        initial_states=[10],initial_precondition='True',context_params=['capacity'],operations=[
            dict(id='OP-DEBIT',text='库存足够则扣减，否则保持',args=[0,dict(domain='quantity'),dict(context='capacity')],transition='state - arg2 if arg2 <= state else state'),
            dict(id='OP-CANCEL',text='取消订单恢复库存并封顶',args=[1,dict(domain='quantity'),dict(context='capacity')],transition='min(arg3, state + arg2)')],
        invariants=[dict(id='INV-BOUND',text='库存保持合法范围',precondition='True',assertion='result >= 0 and result <= arg3')],seed=0,max_sequences=16,max_steps=4,excluded_inputs=[])
    files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,'src/stock.cj':source.encode(),'src/adjust.cj':wrapper}
    examples=[dict(args=[10,0,3,10],expected=7,suite='target'),dict(args=[10,1,0,10],expected=10,suite='regression')]
    draft=uploads.prepare_project('stock-sequence',None,'库存扣减后取消应准确恢复，库存不得越界',actor_id='alice',request_key='one',entries=files)
    uploads.confirm(draft['id'],expected_version=1,function='adjust',examples_json=json.dumps(examples),sequences_json=json.dumps(model),allowed_paths=['src/stock.cj'],consent=True,actor_id='alice')
    original=uploads.source(draft['id'],actor_id='alice');ws=WorkspaceStore(root,registered=[original]);baseline=ws.import_project(original,'.')
    req=RequirementService(store);rd=req.prepare_requirement(draft['id'],draft['goal'])
    spec=req.confirm_requirement(rd['id'],dict(schema_version=1,expected_version=1,requirements=rd['requirements'],allowed_paths=rd['allowed_paths']),actor_id='alice')
    task=req.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    def candidate(fixed=False):
        proposal=CandidateProposal(edits=[dict(path='src/stock.cj',before_hash=file_hash(source),content=(source.replace(bug,'') if fixed else source)+'\n// candidate\n')],requirement_refs=['REQ-UPLOAD'])
        return ws.apply_candidate(store.get_task(task.id),proposal)
    return store,ws,task,candidate


def test_two_file_stock_sequence_fails_and_reference_regresses_prefix(tmp_path):
    from nexus.adapters.cangjie.verifier import CangjieVerifier
    from nexus.repair.sequence_service import SequenceService,failure_trace
    store,ws,task,apply=stock_system(tmp_path.resolve());engine=SequenceService(store);verifier=CangjieVerifier(store.root,task.id)
    first=apply();assert asyncio.run(verifier.build(first.id)).state=='PASS';assert asyncio.run(verifier.test(first.id)).state=='PASS'
    before=source_manifest(ws.subject_path(first.id));failed=asyncio.run(engine.run(first.id))
    assert failed['state']=='FAIL' and failed['public_test_state']=='PASS'
    failure=failed['failures'][0];assert len(failure['steps'])==2
    assert [s['operation_id'] for s in failure['steps']]==['OP-DEBIT','OP-CANCEL']
    assert failure['actual_return']==9 and failure['expected_state']==10 and failure['initial_state']==10
    assert source_manifest(ws.subject_path(first.id))==before
    second=apply(True);assert asyncio.run(verifier.build(second.id)).state=='PASS';assert asyncio.run(verifier.test(second.id)).state=='PASS'
    passed=asyncio.run(engine.run(second.id));assert passed['state']=='PASS' and passed['regression_traces']>0
    contract=engine.binding(second.id)[3]
    assert {sequences.trace_key(failure_trace(contract,f)) for f in failed['failures']}<={sequences.trace_key(t) for t in passed['batches'][0]['traces']}
    for report in (failed,passed):
        assert engine.verify(report['candidate_id'])==report
        for batch in report['batches']:
            assert {'src/stock.cj','src/adjust.cj'}<=set(batch['project_manifest'])
            text=(store.root/batch['log_ref']).read_text()
            assert 'NEXUS_EXECUTION_PHASE' in text and 'NEXUS_SEQUENCE_END_V1|' in text and 'FIXTURE' not in text


def test_real_sequence_shrink_reexecutes_reachable_prefix(tmp_path):
    from nexus.adapters.cangjie.verifier import CangjieVerifier
    from nexus.repair.sequence_service import SequenceService,failure_trace,score
    store,ws,task,apply=stock_system(tmp_path.resolve());engine=SequenceService(store);verifier=CangjieVerifier(store.root,task.id);candidate=apply()
    assert asyncio.run(verifier.build(candidate.id)).state=='PASS';assert asyncio.run(verifier.test(candidate.id)).state=='PASS'
    report=asyncio.run(engine.run(candidate.id));assert report['state']=='FAIL' and report['shrink_traces']>0
    contract=engine.binding(candidate.id)[3];initial=min(report['batches'][0]['result']['failures'],key=lambda f:score(contract,f));target=initial['failure_ids'][0]
    for batch in report['batches'][1:]:
        assert batch['result']['execution_state']=='PASS'
        for trace in batch['traces']:assert trace['initial_state']==10
        for failure in batch['result']['failures']:
            assert failure['initial_state']==10 and len(failure['steps'])>=2
            assert sequences.reference_trace(contract,failure_trace(contract,failure))['eligible']
            assert failure['steps'][0]['before_state']==10
    assert target in report['failures'][0]['failure_ids']
    assert engine.verify(candidate.id)==report
