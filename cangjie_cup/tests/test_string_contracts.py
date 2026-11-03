"""Version-gated finite String models, independent of candidates."""
from copy import deepcopy
import pytest
from nexus.repair import oracle,properties,relations,sequences


def signature():return dict(name='ticket',params=[dict(name='code',type='String'),dict(name='qty',type='Int64')],return_type='String')

def raw_oracle():return dict(version=3,function='ticket',domains=dict(code=dict(values=['','a','中']),qty=dict(min=0,max=2,points=[])),expression='code + (":Y" if qty > 0 else ":N")',seed=7,max_cases=16,excluded_inputs=[])

def examples():return [dict(args=['',0],expected=':N',suite='target'),dict(args=['中',1],expected='中:Y',suite='regression')]

def raw_property():
    raw=raw_oracle();return dict(version=2,kind='single',function='ticket',domains=raw['domains'],properties=[dict(id='PROP-SIZE',text='输出不能丢失码点',precondition='rune_len(arg0) >= 0',assertion='rune_len(result) >= rune_len(arg0)')],seed=7,max_cases=16,excluded_inputs=[])

def raw_relation():
    raw=raw_oracle();return dict(version=2,kind='relation',function='ticket',domains=raw['domains'],relations=[dict(id='REL-DISTINCT',text='不同编码不能冲突',precondition='left_arg0 != right_arg0',assertion='left_result != right_result')],seed=7,max_pairs=16,excluded_inputs=[])

def sequence_raw():
    sig=dict(name='appendState',params=[dict(name='op',type='Int64'),dict(name='current',type='String'),dict(name='label',type='String')],return_type='String')
    raw=dict(version=2,kind='sequence',function='appendState',state_param='current',domains=dict(op=dict(min=0,max=1,points=[]),current=dict(values=['','a','aa','aaa']),label=dict(values=['a'])),initial_states=['','a'],initial_precondition='byte_len(initial_state) <= 1',context_params=['label'],operations=[dict(id='OP-APPEND',text='有界追加',args=[0,{'context':'label'}],transition='state + arg2 if byte_len(state) < 3 else state'),dict(id='OP-RESET',text='重置',args=[1,{'context':'label'}],transition='""')],invariants=[dict(id='INV-SIZE',text='状态始终有界且匹配参考',precondition='True',assertion='byte_len(result) <= 3 and result == expected_state')],seed=7,max_sequences=16,max_steps=4,excluded_inputs=[])
    return raw,sig


def test_string_oracle_preserves_typed_result_and_explicit_algorithm():
    c=oracle.validate_contract(raw_oracle(),signature(),examples())
    assert c['version']==3 and c['algorithm']=='boundary-string-v3'
    assert oracle.expected(c,['中',1])=='中:Y' and oracle.expected(c,['',0])==':N'
    assert c['domains']['code']=={'values':['','a','中']}


@pytest.mark.parametrize('factory,module',[(raw_oracle,oracle),(raw_property,properties),(raw_relation,relations)])
def test_string_contracts_reject_legacy_version_and_new_version_on_numeric_signature(factory,module):
    raw=factory();old=deepcopy(raw);old['version']=1
    with pytest.raises(ValueError):module.validate_contract(old,signature(),[])
    numeric=signature();numeric['params'][0]['type']='Int64';numeric['return_type']='Int64'
    with pytest.raises(ValueError):module.validate_contract(raw,numeric,[])


@pytest.mark.parametrize('domain',[{},dict(values=[]),dict(values=['a','a']),dict(values=[1]),dict(values=[True]),dict(values=['x'*257]),dict(values=[chr(0xd800)]),dict(values=['a'],extra=1),dict(values=[str(i) for i in range(17)])])
def test_string_domain_is_strict_finite_and_bounded(domain):
    raw=raw_oracle();raw['domains']['code']=domain
    with pytest.raises(ValueError):oracle.validate_contract(raw,signature(),[])


@pytest.mark.parametrize('expression',['code + qty','code * 2','code < "z"','min(code,code)','byte_len(qty)','rune_len(code,code)','code[0]','code.real','__import__("os")','code if qty else "x"','code + "x"*257'])
def test_string_expression_type_and_capability_errors_rejected_before_execution(expression):
    raw=raw_oracle();raw['expression']=expression
    with pytest.raises(ValueError):oracle.validate_contract(raw,signature(),[])


def test_string_intermediate_limit_examples_and_reserved_conflicts_are_errors():
    raw=raw_oracle();raw['domains']['code']={'values':['x'*256]};raw['expression']='code + "!"'
    with pytest.raises(ValueError):oracle.validate_contract(raw,signature(),[])
    with pytest.raises(ValueError):oracle.validate_contract(raw_oracle(),signature(),[dict(args=['a',0],expected='wrong')])
    raw=raw_oracle();raw['excluded_inputs']=[['',0]]
    with pytest.raises(ValueError):oracle.validate_contract(raw,signature(),examples())


def test_numeric_legacy_never_gains_string_literals_or_length_helpers():
    sig=dict(name='f',params=[dict(name='x',type='Int64')],return_type='Int64')
    raw=dict(version=1,function='f',domains={'x':dict(min=0,max=2,points=[])},expression='x',seed=0,max_cases=16)
    for expression in ('byte_len("a")','rune_len("a")','"a"'):
        with pytest.raises(ValueError):oracle.validate_contract({**raw,'expression':expression},sig,[])


def test_string_properties_require_observed_typed_returns():
    c=properties.validate_contract(raw_property(),signature(),examples())
    assert c['algorithm']=='single-properties-string-v2' and c['version']==2
    assert properties.evaluate_result(c,['中',1],'中:Y')['state']=='PASS'
    assert properties.evaluate_result(c,['中',1],'')['state']=='FAIL'
    with pytest.raises(ValueError):properties.evaluate_result(c,['中',1],False)


def test_string_relation_uses_actual_left_and_right_returns():
    c=relations.validate_contract(raw_relation(),signature(),examples());pair=dict(left=['a',0],right=['中',0])
    assert c['algorithm']=='paired-relations-string-v2' and c['version']==2
    assert relations.evaluate_pair(c,pair,'a:N','中:N')['state']=='PASS'
    assert relations.evaluate_pair(c,pair,'same','same')['state']=='FAIL'
    with pytest.raises(ValueError):relations.evaluate_pair(c,pair,1,'same')


def test_nonfirst_string_state_uses_actual_signature_and_explicit_v2():
    raw,sig=sequence_raw();c=sequences.validate_contract(raw,sig,[])
    assert c['algorithm']=='state-sequences-string-v2' and c['state_index']==1 and c['context_indices']==[2]
    trace=dict(initial_state='',context=['a'],steps=[dict(operation_id='OP-APPEND',args=[0,'a']) for _ in range(3)])
    plan=sequences.reference_trace(c,trace);assert [s['expected_state'] for s in plan['steps']]==['a','aa','aaa']
    assert sequences.evaluate_step(c,plan['steps'][1],'aa')['state']=='PASS'
    assert sequences.evaluate_step(c,plan['steps'][1],'a')['state']=='FAIL'
    with pytest.raises(ValueError):sequences.validate_contract({**raw,'version':1},sig,[])


def test_string_state_models_cannot_disagree_for_identical_function_input():
    raw,sig=sequence_raw();other=deepcopy(raw['operations'][0]);other.update(id='OP-OTHER',transition='""');raw['operations'].append(other)
    with pytest.raises(ValueError):sequences.validate_contract(raw,sig,[])


def test_string_return_without_string_parameters_still_uses_explicit_string_expressions():
    sig=dict(name='fixed',params=[],return_type='String')
    raw=dict(version=3,function='fixed',domains={},expression='"中😀"',seed=0,max_cases=16,excluded_inputs=[])
    c=oracle.validate_contract(raw,sig,[dict(args=[],expected='中😀')]);assert oracle.expected(c,[])=='中😀'
    prop=dict(version=2,kind='single',function='fixed',domains={},properties=[dict(id='PROP-FIXED',text='显式码点数',precondition='byte_len("a") == 1',assertion='rune_len(result) == 2')],seed=0,max_cases=16,excluded_inputs=[])
    c=properties.validate_contract(prop,sig,[]);assert properties.evaluate_result(c,[],'中😀')['state']=='PASS'


def test_string_parameters_can_return_int64_byte_and_rune_difference():
    sig=dict(name='difference',params=[dict(name='text',type='String')],return_type='Int64')
    raw=dict(version=3,function='difference',domains=dict(text=dict(values=['','中','中😀'])),expression='byte_len(text) - rune_len(text)',seed=0,max_cases=16,excluded_inputs=[])
    c=oracle.validate_contract(raw,sig,[dict(args=['中'],expected=2)]);assert oracle.expected(c,['中😀'])==5
    with pytest.raises(ValueError):oracle.validate_contract(raw,sig,[dict(args=[''],expected=False)])
