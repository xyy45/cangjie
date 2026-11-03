"""Single-call properties consume observed returns, never model self-judgment."""
from copy import deepcopy
import importlib
import importlib.util

import pytest

from nexus.repair import oracle
from nexus.benchmark.corpus import build_corpus


SIG=dict(name='refundState',params=[dict(name=n,type='Int64') for n in ('paid','refunded','requested')],return_type='Int64')
EXAMPLES=[dict(args=[1000,800,100],expected=900,suite='target'),dict(args=[1000,800,200],expected=1000,suite='regression')]


def api():
    assert importlib.util.find_spec('nexus.repair.properties') is not None,'properties contract missing'
    return importlib.import_module('nexus.repair.properties')


def raw():
    return dict(version=1,kind='single',function='refundState',domains=dict(
        paid=dict(min=900,max=1000,points=[900,1000]),refunded=dict(min=800,max=900,points=[800,900]),
        requested=dict(min=100,max=200,points=[100,200])),properties=[
        dict(id='PROP-RANGE',text='累计退款不超实付',precondition='True',assertion='0 <= result <= arg0'),
        dict(id='PROP-INVALID',text='超额申请保持旧累计',precondition='arg2 > arg0-arg1',assertion='result == arg1')],
        seed=1234,max_cases=32,excluded_inputs=[])


@pytest.mark.parametrize('field',['precondition','assertion'])
@pytest.mark.parametrize('value',[[],{},None,False,3])
def test_nonstring_property_expressions_are_validation_errors_before_cache(field,value):
    source=raw();source['properties'][0][field]=value
    with pytest.raises(ValueError):api().validate_contract(source,SIG,EXAMPLES)


def test_properties_aliases_int_bool_and_refund_invariant():
    module=api();value=raw();contract=module.validate_contract(value,SIG,EXAMPLES)
    assert contract['algorithm']=='single-properties-v1'
    assert contract['aliases']==dict(arg0='paid',arg1='refunded',arg2='requested')
    assert module.applicable(contract,[1000,900,200])==['PROP-RANGE','PROP-INVALID']
    failure=module.evaluate_result(contract,[1000,900,200],1100)
    assert failure['state']=='FAIL' and len(failure['failures'])==2
    assert all(f['actual_return']==1100 and f['assertion_value'] is False and f['expected_property'] is True for f in failure['failures'])
    assert module.evaluate_result(contract,[1000,900,200],900)['state']=='PASS'
    assert module.evaluate_result(contract,[1000,800,100],900)['applicable']==['PROP-RANGE']
    value['properties'][0]['assertion']='False';value['domains']['paid']['points'].append(901)
    assert contract['properties'][0]['assertion']!='False' and contract['domains']['paid']['points']==[900,1000]
    for bad in (True,None,1.2,2**63):
        with pytest.raises(ValueError):module.evaluate_result(contract,[1000,900,200],bad)


def test_return_bool_and_source_parameter_named_result_do_not_collide():
    module=api();signature=dict(name='allowed',params=[dict(name='result',type='Int64')],return_type='Bool')
    value=dict(version=1,kind='single',function='allowed',domains=dict(result=dict(min=-1,max=1,points=[0])),
        properties=[dict(id='PROP-POSITIVE',text='正数才允许',precondition='arg0 >= 0',assertion='result == (arg0 > 0)')],seed=0,max_cases=16,excluded_inputs=[])
    contract=module.validate_contract(value,signature,[])
    assert contract['aliases']==dict(arg0='result')
    assert module.evaluate_result(contract,[0],True)['state']=='FAIL'
    assert module.evaluate_result(contract,[0],False)['state']=='PASS'
    assert module.evaluate_result(contract,[-1],False)['state']=='UNKNOWN'
    with pytest.raises(ValueError):module.evaluate_result(contract,[0],0)
    value['properties'][0]['assertion']='result == 1'
    with pytest.raises(ValueError):module.validate_contract(value,signature,[])


@pytest.mark.parametrize('change',[
    'version-bool','wrong-kind','extra-field','too-many-cases','bad-seed','empty-properties','duplicate-id',
    'result-in-guard','non-bool-assertion','int-and-bool','unknown-name','attribute','call','mixed-branch',
    'empty-guard','zero-divisor','overflow','conflict','bad-domain','bool-integer-domain','long-text','bad-id'])
def test_properties_reject_bad_schema_types_guards_and_expression(change):
    module=api();value=raw();prop=value['properties'][0]
    if change=='version-bool':value['version']=True
    elif change=='wrong-kind':value['kind']='sequence'
    elif change=='extra-field':value['source']='untrusted'
    elif change=='too-many-cases':value['max_cases']=256
    elif change=='bad-seed':value['seed']=-1
    elif change=='empty-properties':value['properties']=[]
    elif change=='duplicate-id':value['properties'].append(deepcopy(prop))
    elif change=='result-in-guard':prop['precondition']='result >= 0'
    elif change=='non-bool-assertion':prop['assertion']='result'
    elif change=='int-and-bool':prop['assertion']='arg0 and True'
    elif change=='unknown-name':prop['assertion']='other > 0'
    elif change=='attribute':prop['assertion']='arg0.real > 0'
    elif change=='call':prop['assertion']='__import__("os") == 1'
    elif change=='mixed-branch':prop['assertion']='True if arg0 >= 900 else 1'
    elif change=='empty-guard':prop['precondition']='False'
    elif change=='zero-divisor':prop['precondition']='arg0//0 > 0'
    elif change=='overflow':prop['precondition']=f'arg0 + {oracle.HIGH} > 0'
    elif change=='conflict':prop['assertion']='result < 0'
    elif change=='bad-domain':value['domains']['paid']['min']=1001
    elif change=='bool-integer-domain':value['domains']['paid']['min']=True
    elif change=='long-text':prop['text']='x'*501
    else:prop['id']='__INVALID'
    with pytest.raises(ValueError):module.validate_contract(value,SIG,EXAMPLES)


def test_reserved_inputs_type_exact_and_outside_domain():
    module=api();value=raw();value['excluded_inputs']=[[0,0,0],[1000,900,200]]
    contract=module.validate_contract(value,SIG,EXAMPLES);sampler=module.sampler(contract)
    forbidden={oracle.input_key(a) for a in value['excluded_inputs']}
    generated=oracle.generate_inputs(sampler)
    assert generated and not forbidden.intersection(oracle.input_key(a) for a in generated)
    for args in generated:assert not forbidden.intersection(oracle.input_key(a) for a in oracle.shrink_inputs(sampler,args))
    with pytest.raises(ValueError):module.applicable(contract,[1000,900,200])
    for excluded in ([[True,0,0]],[[0,0,0],[0,0,0]],[[0,0]],'bad'):
        value['excluded_inputs']=excluded
        with pytest.raises(ValueError):module.validate_contract(value,SIG,EXAMPLES)


def test_domain_excludes_public_example_without_expanding_property_scope():
    module=api();examples=EXAMPLES+[dict(args=[1,0,1],expected=1,suite='regression')]
    contract=module.validate_contract(raw(),SIG,examples)
    assert contract['domains']['paid']['min']==900
    with pytest.raises(ValueError):module.evaluate_result(contract,[1,0,1],1)


def test_int64_minimum_and_static_types_follow_legacy_arithmetic():
    module=api();signature=dict(name='identity',params=[dict(name='x',type='Int64')],return_type='Int64')
    value=dict(version=1,kind='single',function='identity',domains=dict(x=dict(min=oracle.LOW,max=oracle.LOW+2)),
        properties=[dict(id='PROP-LOW',text='Int64下界',precondition='True',assertion=f'result >= {oracle.LOW}')],seed=0,max_cases=16,excluded_inputs=[])
    contract=module.validate_contract(value,signature,[])
    assert module.evaluate_result(contract,[oracle.LOW],oracle.LOW)['state']=='PASS'
    value['properties'][0]['assertion']='result == (True if arg0 > 0 else 0)'
    with pytest.raises(ValueError):module.validate_contract(value,signature,[])


def test_old_corpus_hashes_after_shared_domain_extraction(tmp_path):
    assert build_corpus(tmp_path/'thirty',30)=='d7cc0ee64e24230091bf891d94e11dc671cc180419dee4062937c5681e15333d'
    assert build_corpus(tmp_path/'hundred',100)=='d16e7982a09999f55206b564d91383c96bf2072debb2228942c4a1ef70389bd1'


def test_zero_argument_primitive_function_keeps_existing_language_support():
    module=api();signature=dict(name='limit',params=[],return_type='Int64')
    value=dict(version=1,kind='single',function='limit',domains={},properties=[
        dict(id='PROP-POSITIVE',text='固定阈值为正',precondition='True',assertion='result > 0')],seed=0,max_cases=16,excluded_inputs=[])
    contract=module.validate_contract(value,signature,[])
    assert oracle.generate_inputs(module.sampler(contract))==[[]]
    assert module.evaluate_result(contract,[],0)['state']=='FAIL'
    assert module.evaluate_result(contract,[],10)['state']=='PASS'


def test_bool_input_and_reserved_boolean_are_not_integer_one():
    module=api();signature=dict(name='bit',params=[dict(name='flag',type='Bool')],return_type='Int64')
    value=dict(version=1,kind='single',function='bit',domains=dict(flag={}),properties=[
        dict(id='PROP-BIT',text='Bool映射到整数',precondition='True',assertion='result == (1 if arg0 else 0)')],seed=0,max_cases=16,excluded_inputs=[[True]])
    contract=module.validate_contract(value,signature,[])
    assert oracle.generate_inputs(module.sampler(contract))==[[False]]
    assert module.evaluate_result(contract,[False],0)['state']=='PASS'
    with pytest.raises(ValueError):module.evaluate_result(contract,[1],1)
    value['excluded_inputs']=[[1]]
    with pytest.raises(ValueError):module.validate_contract(value,signature,[])
