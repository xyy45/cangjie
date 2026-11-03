"""Versioned Array models; candidate code is never executed here."""
from copy import deepcopy
import pytest
from nexus.repair import oracle,properties,relations,sequences

LOW=-(1<<63);HIGH=(1<<63)-1

def signature():return dict(name='orderTotal',params=[dict(name='values',type='Array<Int64>'),dict(name='bonus',type='Int64')],return_type='Int64')
def raw_oracle():return dict(version=4,function='orderTotal',domains=dict(values=dict(values=[[],[1],[1,2],[2,1],[-1,3]]),bonus=dict(min=0,max=2,points=[])),expression='array_sum(values) + bonus',seed=7,max_cases=16,excluded_inputs=[])
def examples():return [dict(args=[[],0],expected=0,suite='target'),dict(args=[[1,2],1],expected=4,suite='regression')]
def raw_property():
    return dict(version=3,kind='single',function='orderTotal',domains=raw_oracle()['domains'],properties=[dict(id='PROP-TOTAL',text='逐项计费不漏项',precondition='array_len(arg0) >= 0',assertion='result == array_sum(arg0) + arg1')],seed=7,max_cases=16,excluded_inputs=[])
def raw_relation():
    return dict(version=3,kind='relation',function='orderTotal',domains=raw_oracle()['domains'],relations=[dict(id='REL-PERMUTATION',text='相同合计与附加费不因排列不同而改变',precondition='left_arg0 != right_arg0 and left_arg1 == right_arg1 and array_sum(left_arg0) == array_sum(right_arg0)',assertion='left_result == right_result')],seed=7,max_pairs=16,excluded_inputs=[])
def sequence_raw():
    sig=dict(name='rotateState',params=[dict(name='op',type='Int64'),dict(name='current',type='Array<Int64>'),dict(name='label',type='String')],return_type='Array<Int64>')
    raw=dict(version=3,kind='sequence',function='rotateState',state_param='current',domains=dict(op=dict(min=0,max=1,points=[]),current=dict(values=[[],[1,2],[2,1]]),label=dict(values=['a','中'])),initial_states=[[],[1,2]],initial_precondition='array_len(initial_state) == 0 or array_len(initial_state) == 2',context_params=['label'],operations=[dict(id='OP-SWAP',text='交换两项',args=[0,{'context':'label'}],transition='[array_at(state, 1), array_at(state, 0)] if array_len(state) == 2 else state'),dict(id='OP-RESET',text='清空',args=[1,{'context':'label'}],transition='[]')],invariants=[dict(id='INV-STATE',text='实际返回与参考一致',precondition='True',assertion='result == expected_state and (array_len(result) == 0 or array_len(result) == 2)')],seed=7,max_sequences=16,max_steps=4,excluded_inputs=[])
    return raw,sig


def test_array_oracle_uses_explicit_v4_typed_domains_and_results():
    raw=raw_oracle();c=oracle.validate_contract(raw,signature(),examples())
    assert c['version']==4 and c['algorithm']=='boundary-array-v4'
    assert oracle.expected(c,[[1,2],1])==4
    assert oracle.expected(c,[[],0])==0
    raw['domains']['values']['values'][0].append(99)
    assert c['domains']['values']['values'][0]==[]

@pytest.mark.parametrize('factory,module',[(raw_oracle,oracle),(raw_property,properties),(raw_relation,relations)])
@pytest.mark.parametrize('version',[1,2])
def test_array_models_reject_old_versions(factory,module,version):
    raw=factory();raw['version']=version
    with pytest.raises(ValueError):module.validate_contract(raw,signature(),[])

@pytest.mark.parametrize('domain',[{},dict(values=[]),dict(values=[[],[]]),dict(values=[True]),dict(values=[[True]]),dict(values=[[1.0]]),dict(values=[[[1]]]),dict(values=[[HIGH+1]]),dict(values=[[0]*17]),dict(values=[[i] for i in range(17)]),dict(values=[[]],extra=1)])
def test_array_domains_are_unique_typed_bounded_and_explicit(domain):
    raw=raw_oracle();raw['domains']['values']=domain
    with pytest.raises(ValueError):oracle.validate_contract(raw,signature(),[])

@pytest.mark.parametrize('expression,want,value',[
 ('array_len(values)','Int64',2),('array_sum(values)','Int64',3),('array_at(values, 1) if array_len(values) > 1 else 0','Int64',2),
 ('array_append(values, bonus)','Array<Int64>',[1,2,1]),('array_replace(values, 0, bonus) if array_len(values) > 0 else []','Array<Int64>',[1,2]),
 ('values','Array<Int64>',[1,2]),('[bonus, -9223372036854775808]','Array<Int64>',[1,LOW]),
 ('values == [1, 2]','Bool',True),('rune_len("中") + array_len(values)','Int64',3),
])
def test_checked_array_helpers_lists_and_mixed_string_expressions(expression,want,value):
    raw=raw_oracle();raw['expression']=expression;sig=signature();sig['return_type']=want
    c=oracle.validate_contract(raw,sig,[]);assert oracle.expected(c,[[1,2],1])==value

@pytest.mark.parametrize('expression',[
 'values[0]','values.size','values + values','values < []','values == True','array_len(bonus)','array_at(values, True)',
 'array_at(values, -1)','array_at(values, 16)','array_at(values)','array_sum(values, values)','array_append(values, True)',
 'array_replace(values, -1, 1)','[True]','[[1]]','[1]*17','array_append([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],1)',
 'array_sum([9223372036854775807,1])','array_sum([-9223372036854775808,-1])','[9223372036854775808]',
 'array_at(values, 0) if bonus else 0','[x for x in values]','__import__("os")',
])
def test_bad_array_expression_is_rejected_before_execution(expression):
    raw=raw_oracle();raw['expression']=expression
    with pytest.raises(ValueError):oracle.validate_contract(raw,signature(),[])


def test_array_return_is_copied_and_empty_zero_param_model_is_supported():
    sig=dict(name='empty',params=[],return_type='Array<Int64>');raw=dict(version=4,function='empty',domains={},expression='[]',seed=0,max_cases=16,excluded_inputs=[])
    c=oracle.validate_contract(raw,sig,[dict(args=[],expected=[])]);a=oracle.expected(c,[]);a.append(1);assert oracle.expected(c,[])==[]


def test_array_properties_and_relations_require_real_typed_returns():
    p=properties.validate_contract(raw_property(),signature(),examples());r=relations.validate_contract(raw_relation(),signature(),examples())
    assert p['algorithm']=='single-properties-array-v3' and r['algorithm']=='paired-relations-array-v3'
    assert properties.evaluate_result(p,[[1,2],1],4)['state']=='PASS'
    assert properties.evaluate_result(p,[[1,2],1],2)['state']=='FAIL'
    pair=dict(left=[[1,2],1],right=[[2,1],1])
    assert relations.evaluate_pair(r,pair,4,4)['state']=='PASS'
    assert relations.evaluate_pair(r,pair,3,4)['state']=='FAIL'
    with pytest.raises(ValueError):properties.evaluate_result(p,[[1,2],1],True)


def test_array_state_nonfirst_parameter_and_string_context_have_reachable_steps():
    raw,sig=sequence_raw();c=sequences.validate_contract(raw,sig,[])
    assert c['algorithm']=='state-sequences-array-v3' and c['state_index']==1 and c['context_indices']==[2]
    trace=dict(initial_state=[1,2],context=['中'],steps=[dict(operation_id=i,args=[0 if i=='OP-SWAP' else 1,'中']) for i in ('OP-SWAP','OP-SWAP','OP-RESET')])
    plan=sequences.reference_trace(c,trace)
    assert [s['expected_state'] for s in plan['steps']]==[[2,1],[1,2],[]]
    assert sequences.evaluate_step(c,plan['steps'][0],[2,1])['state']=='PASS'
    assert sequences.evaluate_step(c,plan['steps'][0],[1,2])['state']=='FAIL'
    plan['steps'][0]['before_state'].append(99)
    assert trace['initial_state']==[1,2] and c['initial_states'][1]==[1,2]


def test_array_state_transitions_cannot_escape_domain_or_disagree_for_same_input():
    raw,sig=sequence_raw();raw['operations'][0]['transition']='[99]'
    with pytest.raises(ValueError):sequences.validate_contract(raw,sig,[])
    raw,sig=sequence_raw();raw['initial_states']=[[1,2],[]];other=deepcopy(raw['operations'][0]);other.update(id='OP-OTHER',transition='[]');raw['operations'].append(other)
    with pytest.raises(ValueError):sequences.validate_contract(raw,sig,[])

@pytest.mark.parametrize('new_version',[1,2])
def test_numeric_old_models_do_not_gain_array_helpers(new_version):
    raw=dict(version=new_version,function='f',domains={'x':dict(min=0,max=2,points=[])},expression='array_len([])',seed=0,max_cases=16)
    if new_version==2:raw['excluded_inputs']=[]
    sig=dict(name='f',params=[dict(name='x',type='Int64')],return_type='Int64')
    with pytest.raises(ValueError):oracle.validate_contract(raw,sig,[])



def test_array_feature_propagates_through_nested_string_length_helper():
    raw=raw_oracle();raw['expression']='byte_len("中" if array_len(values) > 0 else "")'
    c=oracle.validate_contract(raw,signature(),[])
    assert oracle.expected(c,[[1],0])==3 and oracle.expected(c,[[],0])==0


def test_array_relation_failure_is_a_value_snapshot_not_a_mutable_alias():
    sig=signature();sig['return_type']='Array<Int64>';raw=raw_relation()
    raw['relations'][0].update(precondition='left_arg0 != right_arg0',assertion='left_result != right_result')
    c=relations.validate_contract(raw,sig,[]);pair=dict(left=[[1,2],1],right=[[2,1],1]);actual=[]
    result=relations.evaluate_pair(c,pair,actual,actual);assert result['state']=='FAIL'
    actual.append(99);pair['left'][0].append(99)
    assert result['failures'][0]['left_args']==[[1,2],1]
    assert result['failures'][0]['left_actual_return']==[] and result['failures'][0]['right_actual_return']==[]


def test_array_state_failure_snapshot_does_not_alias_reference_plan():
    raw,sig=sequence_raw();c=sequences.validate_contract(raw,sig,[])
    trace=dict(initial_state=[1,2],context=['a'],steps=[dict(operation_id='OP-SWAP',args=[0,'a'])])
    plan=sequences.reference_trace(c,trace);result=sequences.evaluate_step(c,plan['steps'][0],[1,2])
    assert result['state']=='FAIL'
    plan['steps'][0]['expected_state'].append(99)
    assert result['failures'][0]['expected_state']==[2,1]
