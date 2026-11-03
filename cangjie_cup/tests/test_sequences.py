"""Hand-checked state paths; no candidate execution or external services."""
from copy import deepcopy
import importlib
import importlib.util

import pytest

from nexus.repair import oracle

SIG=dict(name='adjust',params=[dict(name='stock',type='Int64'),dict(name='operation',type='Int64'),dict(name='amount',type='Int64'),dict(name='capacity',type='Int64')],return_type='Int64')


def api():
    assert importlib.util.find_spec('nexus.repair.sequences') is not None,'sequence contract missing'
    return importlib.import_module('nexus.repair.sequences')


def raw():
    return dict(version=1,kind='sequence',function='adjust',state_param='stock',
        domains=dict(stock=dict(min=0,max=20,points=[3,7,10]),operation=dict(min=0,max=1),amount=dict(min=0,max=10,points=[3,7]),capacity=dict(min=10,max=20,points=[10])),
        initial_states=[10],initial_precondition='initial_state <= ctx3',context_params=['capacity'],
        operations=[dict(id='OP-DEBIT',text='合法扣减',args=[0,dict(domain='amount'),dict(context='capacity')],transition='state - arg2 if arg2 <= state else state'),
                    dict(id='OP-CANCEL',text='取消恢复且不超过容量',args=[1,dict(domain='amount'),dict(context='capacity')],transition='min(arg3, state + arg2)')],
        invariants=[dict(id='INV-BOUND',text='库存非负且不超过容量',precondition='True',assertion='result >= 0 and result <= arg3')],
        seed=1234,max_sequences=16,max_steps=4,excluded_inputs=[])


def stock_trace(amount=3,restore=3,initial=10,capacity=10):
    return dict(initial_state=initial,context=[capacity],steps=[dict(operation_id='OP-DEBIT',args=[0,amount,capacity]),dict(operation_id='OP-CANCEL',args=[1,restore,capacity])])


def refund_raw():
    signature=dict(name='refund',params=[dict(name='state',type='Int64'),dict(name='amount',type='Int64'),dict(name='paid',type='Int64')],return_type='Int64')
    source=dict(version=1,kind='sequence',function='refund',state_param='state',domains=dict(state=dict(min=0,max=10),amount=dict(min=0,max=10,points=[7]),paid=dict(min=10,max=10)),
        initial_states=[0],initial_precondition='True',context_params=['paid'],operations=[dict(id='OP-REFUND',text='累计退款封顶实付',args=[dict(domain='amount'),dict(context='paid')],transition='min(arg2, state + arg1)')],
        invariants=[dict(id='INV-BOUND',text='不超过实付',precondition='True',assertion='result >= 0 and result <= arg2')],seed=1,max_sequences=16,max_steps=4,excluded_inputs=[])
    return source,signature


def refund_trace():
    return dict(initial_state=0,context=[10],steps=[dict(operation_id='OP-REFUND',args=[7,10]),dict(operation_id='OP-REFUND',args=[7,10])])


def test_reference_trace_preserves_reachable_states():
    module=api();source,signature=refund_raw();contract=module.validate_contract(source,signature,[])
    result=module.reference_trace(contract,refund_trace())
    assert result['eligible'] is True
    assert [s['args'] for s in result['steps']]==[[0,7,10],[7,7,10]]
    assert [s['before_state'] for s in result['steps']]==[0,7]
    assert [s['expected_state'] for s in result['steps']]==[7,10]
    assert [s['step_index'] for s in result['steps']]==[0,1]
    failure=module.evaluate_step(contract,result['steps'][1],14)
    assert failure['state']=='FAIL' and set(f['failure_id'] for f in failure['failures'])=={'MODEL-OP-REFUND','INV-BOUND'}
    assert module.evaluate_step(contract,result['steps'][1],10)['state']=='PASS'
    for bad in (True,None,1.0,oracle.HIGH+1):
        with pytest.raises(ValueError):module.evaluate_step(contract,result['steps'][1],bad)


def test_contract_is_frozen_independently_of_mutable_input():
    module=api();source=raw();signature=deepcopy(SIG);contract=module.validate_contract(source,signature,[])
    source['operations'][0]['transition']='0';source['domains']['amount']['points'].append(5);signature['params'][0]['name']='changed'
    assert contract['operations'][0]['transition']=='state - arg2 if arg2 <= state else state'
    assert contract['domains']['amount']['points']==[3,7] and contract['signature']['params'][0]['name']=='stock'
    assert [s['expected_state'] for s in module.reference_trace(contract,stock_trace())['steps']]==[7,10]


@pytest.mark.parametrize('text',['initial_state','step_index','state + step_index','initial_state if arg2 == 0 else state'])
def test_contract_rejects_hidden_history_in_transition(text):
    source=raw();source['operations'][0]['transition']=text
    with pytest.raises(ValueError):api().validate_contract(source,SIG,[])


def test_public_middle_state_is_checked_outside_initial_states():
    module=api();source,signature=refund_raw()
    assert source['initial_states']==[0]
    example=dict(args=[7,7,10],expected=10,suite='target')
    assert module.validate_contract(source,signature,[example])['function']=='refund'
    with pytest.raises(ValueError):module.validate_contract(source,signature,[{**example,'expected':14}])
    # Public tests outside the model domain stay public, never get a fabricated model answer.
    assert module.validate_contract(source,signature,[dict(args=[-1,7,10],expected=-1,suite='target')])


@pytest.mark.parametrize('change',['extra','version','kind','function','state-param','seed','budget','depth','domains','empty-initial','duplicate-initial','initial-type','initial-outside',
    'initial-unknown','initial-no-coverage','context-unknown','context-state','context-duplicate','empty-ops','duplicate-op','op-id','op-text','op-extra','op-arity','op-type','op-outside','wrong-domain','wrong-context','context-literal',
    'transition-bool','transition-call','transition-attribute','empty-invariants','duplicate-invariant','invariant-id','invariant-type','result-in-guard','invariant-mixed','no-invariant-coverage','excluded-type','excluded-duplicate'])
def test_invalid_sequence_contract_cannot_be_frozen(change):
    source=raw();op=source['operations'][0];inv=source['invariants'][0]
    if change=='extra':source['script']='x'
    elif change=='version':source['version']=True
    elif change=='kind':source['kind']='relation'
    elif change=='function':source['function']='other'
    elif change=='state-param':source['state_param']='missing'
    elif change=='seed':source['seed']=2**32
    elif change=='budget':source['max_sequences']=17
    elif change=='depth':source['max_steps']=9
    elif change=='domains':source['domains']['stock']['min']=False
    elif change=='empty-initial':source['initial_states']=[]
    elif change=='duplicate-initial':source['initial_states']=[10,10]
    elif change=='initial-type':source['initial_states']=[True]
    elif change=='initial-outside':source['initial_states']=[21]
    elif change=='initial-unknown':source['initial_precondition']='arg0 >= 0'
    elif change=='initial-no-coverage':source['initial_precondition']='False'
    elif change=='context-unknown':source['context_params']=['missing']
    elif change=='context-state':source['context_params']=['stock']
    elif change=='context-duplicate':source['context_params']=['capacity','capacity']
    elif change=='empty-ops':source['operations']=[]
    elif change=='duplicate-op':source['operations'].append(deepcopy(op))
    elif change=='op-id':op['id']='bad'
    elif change=='op-text':op['text']='x'*501
    elif change=='op-extra':op['permission']=True
    elif change=='op-arity':op['args']=[]
    elif change=='op-type':op['args'][0]=True
    elif change=='op-outside':op['args'][0]=2
    elif change=='wrong-domain':op['args'][1]=dict(domain='stock')
    elif change=='wrong-context':op['args'][2]=dict(context='amount')
    elif change=='context-literal':op['args'][2]=10
    elif change=='transition-bool':op['transition']='True'
    elif change=='transition-call':op['transition']='eval("state")'
    elif change=='transition-attribute':op['transition']='state.real'
    elif change=='empty-invariants':source['invariants']=[]
    elif change=='duplicate-invariant':source['invariants'].append(deepcopy(inv))
    elif change=='invariant-id':inv['id']='other'
    elif change=='invariant-type':inv['assertion']='result'
    elif change=='result-in-guard':inv['precondition']='result >= 0'
    elif change=='invariant-mixed':inv['assertion']='result == True'
    elif change=='no-invariant-coverage':inv['precondition']='False'
    elif change=='excluded-type':source['excluded_inputs']=[[10,0,True,10]]
    else:source['excluded_inputs']=[[10,0,0,10],[10,0,0,10]]
    with pytest.raises(ValueError):api().validate_contract(source,SIG,[])


def test_return_type_must_match_the_explicit_state_parameter():
    signature=deepcopy(SIG);signature['return_type']='Bool'
    with pytest.raises(ValueError):api().validate_contract(raw(),signature,[])
    signature['params']=[]
    with pytest.raises(ValueError):api().validate_contract(raw(),signature,[])


def test_context_is_fixed_across_all_steps():
    module=api();contract=module.validate_contract(raw(),SIG,[]);trace=stock_trace();trace['steps'][1]['args'][2]=20
    with pytest.raises(ValueError):module.reference_trace(contract,trace)
    trace=stock_trace();trace['context']=[True]
    with pytest.raises(ValueError):module.reference_trace(contract,trace)


def test_reserved_intermediate_call_filters_entire_trace():
    module=api();source,signature=refund_raw();source['excluded_inputs']=[[7,7,10],[-100,0,10]]
    contract=module.validate_contract(source,signature,[])
    assert module.reference_trace(contract,refund_trace())['eligible'] is False
    for trace in module.generate_traces(contract)['traces']:
        assert all(s['args']!=[7,7,10] for s in module.reference_trace(contract,trace)['steps'])
    with pytest.raises(ValueError):module.generate_traces(contract,cumulative=[refund_trace()])
    with pytest.raises(ValueError):module.validate_contract(source,signature,[dict(args=[7,7,10],expected=10,suite='target')])


def test_all_reserved_initial_calls_prevent_search():
    source,signature=refund_raw();source['operations'][0]['args'][0]=7;source['excluded_inputs']=[[0,7,10]]
    with pytest.raises(ValueError):api().validate_contract(source,signature,[])


@pytest.mark.parametrize('change',['overflow','state-domain','contradictory-invariant'])
def test_invalid_model_is_not_silently_filtered(change):
    module=api();contract=module.validate_contract(raw(),SIG,[])
    if change=='overflow':contract['operations'][0]['transition']=f'state + {oracle.HIGH}'
    elif change=='state-domain':contract['operations'][0]['transition']='99'
    else:contract['invariants'][0]['assertion']='False'
    with pytest.raises(ValueError):module.reference_trace(contract,stock_trace())
    with pytest.raises(ValueError):module.generate_traces(contract)


def test_generation_is_deterministic_bounded_and_covers_repeated_operations():
    module=api();contract=module.validate_contract(raw(),SIG,[]);first=module.generate_traces(contract)
    assert first==module.generate_traces(contract)
    assert 1<=len(first['traces'])<=16 and sum(len(t['steps']) for t in first['traces'])<=128
    assert 0<first['candidate_checks']<=8192 and first['regression_traces']==0
    assert len({module.trace_key(t) for t in first['traces']})==len(first['traces'])
    assert {s['operation_id'] for t in first['traces'] for s in t['steps']}=={'OP-DEBIT','OP-CANCEL'}
    assert any(t['steps'][0]==t['steps'][1] for t in first['traces'])
    assert any(t['steps'][0]['operation_id']!=t['steps'][1]['operation_id'] for t in first['traces'])
    for trace in first['traces']:
        planned=module.reference_trace(contract,trace);assert planned['eligible'] is True
        for step in planned['steps']:assert module.evaluate_step(contract,step,step['expected_state'])['state']=='PASS'
    with pytest.raises(ValueError):module.generate_traces(contract,axes=[[0],[0],[0],[10]])


def test_regression_union_above_eight_is_not_silently_truncated():
    module=api();contract=module.validate_contract(raw(),SIG,[]);required=[stock_trace(amount=i,restore=1) for i in range(9)]
    result=module.generate_traces(contract,cumulative=required+required[:2])
    assert result['regression_traces']==9 and result['traces'][:9]==required
    source=raw();source['max_sequences']=8;small=module.validate_contract(source,SIG,[])
    with pytest.raises(ValueError):module.generate_traces(small,cumulative=required)
    trace=stock_trace();trace['steps']=trace['steps']*3
    with pytest.raises(ValueError):module.generate_traces(contract,cumulative=[trace])


def test_shrink_recomputes_reachable_model_and_preserves_context_and_failure_scope():
    module=api();source=raw();source['initial_states']=[0,5,10];contract=module.validate_contract(source,SIG,[])
    original=stock_trace(amount=7,restore=7);original['steps']*=2
    items=module.shrink_traces(contract,original,'MODEL-OP-CANCEL')
    assert 1<=len(items)<=8 and len({module.trace_key(t) for t in items})==len(items)
    assert any(len(t['steps'])<4 for t in items)
    for trace in items:
        assert module.trace_score(trace)<module.trace_score(original)
        assert module.reference_trace(contract,trace)['eligible'] is True
        assert any(s['operation_id']=='OP-CANCEL' for s in trace['steps'])
        assert all(s['args'][2]==trace['context'][0] for s in trace['steps'])
    with pytest.raises(ValueError):module.shrink_traces(contract,original,'INV-UNKNOWN')


def test_bool_state_in_nonfirst_slot_uses_real_argument_order():
    module=api();signature=dict(name='switch',params=[dict(name='operation',type='Int64'),dict(name='state',type='Bool')],return_type='Bool')
    source=dict(version=1,kind='sequence',function='switch',state_param='state',domains=dict(operation=dict(min=0,max=1),state={}),initial_states=[False],initial_precondition='True',context_params=[],
        operations=[dict(id='OP-ON',text='启用',args=[1],transition='True'),dict(id='OP-OFF',text='关闭',args=[0],transition='False')],
        invariants=[dict(id='INV-MODEL',text='遵守操作模型',precondition='True',assertion='result == expected_state')],seed=0,max_sequences=8,max_steps=2,excluded_inputs=[])
    contract=module.validate_contract(source,signature,[]);trace=dict(initial_state=False,context=[],steps=[dict(operation_id='OP-ON',args=[1]),dict(operation_id='OP-OFF',args=[0])]);result=module.reference_trace(contract,trace)
    assert [s['args'] for s in result['steps']]==[[1,False],[0,True]]
    assert [s['expected_state'] for s in result['steps']]==[True,False]
    with pytest.raises(ValueError):module.evaluate_step(contract,result['steps'][0],1)
    assert module.trace_key(dict(initial_state=False,context=[],steps=[dict(operation_id='OP-ON',args=[True])]))!=module.trace_key(dict(initial_state=0,context=[],steps=[dict(operation_id='OP-ON',args=[1])]))


def test_state_only_int64_lower_bound_and_no_context_are_supported():
    module=api();signature=dict(name='keep',params=[dict(name='value',type='Int64')],return_type='Int64')
    source=dict(version=1,kind='sequence',function='keep',state_param='value',domains=dict(value=dict(min=oracle.LOW,max=oracle.LOW)),initial_states=[oracle.LOW],initial_precondition='True',context_params=[],
        operations=[dict(id='OP-KEEP',text='保持状态',args=[],transition='state')],invariants=[dict(id='INV-KEEP',text='状态保持',precondition='True',assertion='result == before_state')],seed=0,max_sequences=8,max_steps=2,excluded_inputs=[])
    contract=module.validate_contract(source,signature,[]);generated=module.generate_traces(contract)
    assert len(generated['traces'])==1
    result=module.reference_trace(contract,generated['traces'][0]);assert [s['expected_state'] for s in result['steps']]==[oracle.LOW,oracle.LOW]


@pytest.mark.parametrize('bad',[{},dict(initial_state=0,context=[],steps=[],extra=True),dict(initial_state=None,context=[],steps=[]),dict(initial_state=0,context=[],steps=[dict(operation_id='OP-A',args=[1.0])])])
def test_trace_identity_rejects_malformed_or_untyped_data(bad):
    with pytest.raises(ValueError):api().trace_key(bad)


def test_raw_cumulative_attempts_obey_the_bounded_condition_budget():
    module=api();contract=module.validate_contract(raw(),SIG,[])
    with pytest.raises(ValueError):module.generate_traces(contract,cumulative=[stock_trace()]*4097)


@pytest.mark.parametrize('example',[dict(args=[-1,0,0,10],expected=True,suite='target'),dict(args=[-1,0,False,10],expected=0,suite='target')])
def test_public_values_are_type_checked_even_outside_model_scope(example):
    with pytest.raises(ValueError):api().validate_contract(raw(),SIG,[example])
