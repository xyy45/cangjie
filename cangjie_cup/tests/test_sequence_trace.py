"""Explicit protocol log fixtures, not live SDK or business-quality evidence."""
from copy import deepcopy
import importlib
import importlib.util

import pytest

from nexus.repair import oracle,sequences
from tests.test_sequences import refund_raw,refund_trace,raw,SIG,stock_trace
from tests.test_primitive_trace import TOKEN


def api():
    assert importlib.util.find_spec('nexus.repair.sequence_trace') is not None,'sequence observation protocol missing'
    return importlib.import_module('nexus.repair.sequence_trace')


def contract():
    source,signature=refund_raw();return sequences.validate_contract(source,signature,[])


def trajectory():
    result=refund_trace();result['steps'].append(dict(operation_id='OP-REFUND',args=[1,10]));return result


def log(cases=None,ends=None,kind='Int64'):
    cases=[[(0,7),(7,10),(10,10)]] if cases is None else cases
    ends=[(len(c),'COMPLETE') for c in cases] if ends is None else ends
    def text(v):return str(v).lower() if type(v) is bool else str(v)
    result='EXPLICIT LOG FIXTURE ONLY\nTP: bench, RESULT:\n TCS: NexusSequences'+TOKEN+', RESULT:\n'
    for i,(observed,end) in enumerate(zip(cases,ends)):
        result+=' [ PASSED ] CASE: case'+str(i)+' (1 ns)\n STDOUT:\n'
        for index,(before,after) in enumerate(observed):result+=' NEXUS_SEQUENCE_V1|'+TOKEN+'|case'+str(i)+'|step'+str(index)+'|'+kind+'|'+text(before)+'|'+text(after)+'\n'
        result+=' NEXUS_SEQUENCE_END_V1|'+TOKEN+'|case'+str(i)+'|'+str(end[0])+'|'+end[1]+'\n'
    n=len(cases);return result+f'Summary: TOTAL: {n} PASSED: {n}, SKIPPED: 0, ERROR: 0 FAILED: 0\ncjpm test success\n'


def test_complete_path_retains_separate_calls_even_when_inputs_repeat():
    module=api();trace=trajectory();trace['steps'].append(dict(operation_id='OP-REFUND',args=[1,10]));text=log([[(0,7),(7,10),(10,10),(10,10)]])
    result=module.interpret(contract(),[trace],TOKEN,text,0,None)
    assert result['state']=='PASS' and result['execution_state']=='PASS'
    assert result['planned_calls']==result['observed_calls']==4 and result['unexecuted_calls']==0
    path=result['observations'][0];assert len(path['steps'])==4 and path['stop_reason']=='COMPLETE'
    assert [s['args'] for s in path['steps']]==[[0,7,10],[7,7,10],[10,1,10],[10,1,10]]
    assert len({s['test_id'] for s in path['steps']})==1
    assert [s['step_index'] for s in path['steps']]==[0,1,2,3]
    assert len({s['source']['start_char'] for s in path['steps']})==4
    for step in path['steps']:
        source=step['source'];assert source['coordinate']=='ANSI_STRIPPED_FULL_LOG'
        assert text[source['start_char']:source['end_char']].strip().startswith('NEXUS_SEQUENCE_V1|')
    assert result['per_operation'][0]['observed']==4 and result['per_invariant'][0]['observed']==4


def test_model_mismatch_requires_exact_early_end_and_never_invents_tail_calls():
    module=api();text=log([[(0,7),(7,14)]],[(2,'MODEL_MISMATCH')]);result=module.interpret(contract(),[trajectory()],TOKEN,text,0,None)
    assert result['state']=='FAIL' and result['execution_state']=='PASS' and result['counts']['passed']==1
    assert (result['planned_calls'],result['observed_calls'],result['unexecuted_calls'])==(3,2,1)
    failure=result['failures'][0]
    assert failure['kind']=='business_sequence' and failure['initial_state']==0 and failure['context']==[10]
    assert [s['args'] for s in failure['steps']]==[[0,7,10],[7,7,10]]
    assert failure['step_index']==1 and failure['actual_return']==14 and failure['expected_state']==10
    assert failure['model_mismatch'] is True and set(failure['failure_ids'])=={'MODEL-OP-REFUND','INV-BOUND'}
    assert failure['test_id']=='NexusSequences'+TOKEN+'.case0'
    assert len(failure['steps'])==2 and result['observations'][0]['stop_reason']=='MODEL_MISMATCH'
    end=result['observations'][0]['end_source'];assert 'NEXUS_SEQUENCE_END_V1|' in text[end['start_char']:end['end_char']]


def test_before_state_is_previous_actual_return():
    result=api().interpret(contract(),[trajectory()],TOKEN,log([[(0,7),(8,10),(10,10)]]),0,None)
    assert result['state']=='UNKNOWN' and result['observations']==[] and result['failures']==[]


@pytest.mark.parametrize('change',['missing-step','duplicate-step','wrong-step','wrong-case','wrong-token','wrong-type','overflow','before-noncanonical','after-noncanonical','negative-zero','stderr',
    'missing-end','duplicate-end','end-count','end-token','end-case','end-mode','after-end','false-complete','premature-mismatch','late-mismatch','mixed-protocol','bad-summary','missing-summary','truncated','exit','problem'])
def test_incomplete_or_misbound_protocol_is_unknown(change):
    module=api();text=log();code=0;problem=None;marker='NEXUS_SEQUENCE_V1|'+TOKEN+'|case0|step1|Int64|7|10';end='NEXUS_SEQUENCE_END_V1|'+TOKEN+'|case0|3|COMPLETE'
    if change=='missing-step':text=text.replace(marker,'')
    elif change=='duplicate-step':text=text.replace(marker,marker+'\n'+marker)
    elif change=='wrong-step':text=text.replace('|step1|','|step2|')
    elif change=='wrong-case':text=text.replace(marker,marker.replace('|case0|','|case1|'))
    elif change=='wrong-token':text=text.replace(marker,marker.replace(TOKEN,'f'*16))
    elif change=='wrong-type':text=text.replace(marker,marker.replace('|Int64|','|Bool|'))
    elif change=='overflow':text=text.replace(marker,marker[:-2]+str(oracle.HIGH+1))
    elif change=='before-noncanonical':text=text.replace(marker,marker.replace('|7|10','|07|10'))
    elif change=='after-noncanonical':text=text.replace(marker,marker[:-2]+'010')
    elif change=='negative-zero':text=text.replace('|Int64|0|7','|Int64|-0|7')
    elif change=='stderr':text=text.replace('STDOUT:','STDERR:')
    elif change=='missing-end':text=text.replace(end,'')
    elif change=='duplicate-end':text=text.replace(end,end+'\n'+end)
    elif change=='end-count':text=text.replace(end,end.replace('|3|','|2|'))
    elif change=='end-token':text=text.replace(end,end.replace(TOKEN,'f'*16))
    elif change=='end-case':text=text.replace(end,end.replace('|case0|','|case1|'))
    elif change=='end-mode':text=text.replace('|COMPLETE','|PASSED')
    elif change=='after-end':text=text.replace(end,end+'\n'+marker.replace('step1','step3'))
    elif change=='false-complete':text=log([[(0,7),(7,14)]],[(2,'COMPLETE')])
    elif change=='premature-mismatch':text=log([[(0,7)]],[(1,'MODEL_MISMATCH')])
    elif change=='late-mismatch':text=log([[(0,7),(7,14),(14,15)]],[(3,'MODEL_MISMATCH')])
    elif change=='mixed-protocol':text=text.replace(end,'NEXUS_RELATION_V1|'+TOKEN+'|case0|Int64|10\n'+end)
    elif change=='bad-summary':text=text.replace('TOTAL: 1','TOTAL: 2')
    elif change=='missing-summary':text=text.split('Summary:',1)[0]
    elif change=='truncated':text=text[:text.index(marker)]
    elif change=='exit':code=1
    else:problem='TimeoutError'
    result=module.interpret(contract(),[trajectory()],TOKEN,text,code,problem)
    assert result['state']=='UNKNOWN' and result['observations']==[] and result['failures']==[]
    assert result['observed_calls']==0,'unmatched partial bytes cannot count as verified calls'


def test_no_model_failure_can_mask_a_different_incomplete_sdk_case():
    one=trajectory();two=trajectory();two['steps'][0]['args'][0]=6
    text=log([[(0,7),(7,14)],[(0,6),(6,10),(10,10)]],[(2,'MODEL_MISMATCH'),(3,'COMPLETE')]);text=text.replace('NEXUS_SEQUENCE_END_V1|'+TOKEN+'|case1|3|COMPLETE','')
    assert api().interpret(contract(),[one,two],TOKEN,text,0,None)['state']=='UNKNOWN'


def test_operation_and_invariant_coverage_are_required_only_for_a_pass():
    module=api();value=sequences.validate_contract(raw(),SIG,[]);trace=stock_trace(amount=0,restore=0);trace['steps'][1]=deepcopy(trace['steps'][0]);text=log([[(10,10),(10,10)]])
    assert module.interpret(value,[trace],TOKEN,text,0,None)['state']=='UNKNOWN'
    relaxed=module.interpret(value,[trace],TOKEN,text,0,None,require_coverage=False)
    assert relaxed['state']=='PASS'
    source=raw();source['invariants'][0]['precondition']='step_index == 3';value=sequences.validate_contract(source,SIG,[])
    trace=stock_trace();text=log([[(10,7),(7,9)]],[(2,'MODEL_MISMATCH')])
    known=module.interpret(value,[trace],TOKEN,text,0,None)
    assert known['state']=='FAIL' and known['failures'][0]['failure_ids']==['MODEL-OP-CANCEL']
    assert known['per_invariant'][0]['observed']==0


def test_protocol_constructor_rejects_unsafe_or_unconfirmed_inputs():
    module=api();value=contract()
    for traces in ([],[trajectory()]*2,[trajectory()]*17):
        with pytest.raises(ValueError):module.harness(value,traces,'bench',TOKEN)
    for package,token in [('bench;import unsafe',TOKEN),('bench',None),('bench','not-a-token')]:
        with pytest.raises(ValueError):module.harness(value,[trajectory()],package,token)
    source,signature=refund_raw();source['excluded_inputs']=[[7,7,10]];reserved=sequences.validate_contract(source,signature,[])
    with pytest.raises(ValueError):module.harness(reserved,[trajectory()],'bench',TOKEN)
    for scope in (None,{},1):
        with pytest.raises(ValueError):module.interpret(value,[trajectory()],TOKEN,log(),0,None,require_coverage=scope)


def test_bool_values_are_not_integers_or_noncanonical_capitalized_text():
    module=api();signature=dict(name='toggle',params=[dict(name='state',type='Bool')],return_type='Bool')
    source=dict(version=1,kind='sequence',function='toggle',state_param='state',domains=dict(state={}),initial_states=[True],initial_precondition='True',context_params=[],operations=[dict(id='OP-TOGGLE',text='切换',args=[],transition='not state')],
        invariants=[dict(id='INV-TOGGLE',text='改变状态',precondition='True',assertion='result != before_state')],seed=0,max_sequences=8,max_steps=2,excluded_inputs=[])
    value=sequences.validate_contract(source,signature,[]);trace=dict(initial_state=True,context=[],steps=[dict(operation_id='OP-TOGGLE',args=[])]*2);text=log([[(True,False),(False,True)]],kind='Bool')
    passed=module.interpret(value,[trace],TOKEN,text,0,None);assert passed['state']=='PASS'
    assert [s['actual_return'] for s in passed['observations'][0]['steps']]==[False,True]
    for bad in (text.replace('|true','|True'),text.replace('|false','|0')):
        assert module.interpret(value,[trace],TOKEN,bad,0,None)['state']=='UNKNOWN'


@pytest.mark.parametrize('marker',['NEXUS_SEQUENCE_V1|'+TOKEN+'|case0|step3|Int64|10|10','NEXUS_SEQUENCE_END_V1|'+TOKEN+'|case0|3|COMPLETE'])
def test_protocol_markers_after_sdk_summary_are_not_silently_ignored(marker):
    text=log().replace('cjpm test success',marker+'\ncjpm test success')
    assert api().interpret(contract(),[trajectory()],TOKEN,text,0,None)['state']=='UNKNOWN'
