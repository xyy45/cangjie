"""Typed bounded relations, with hand-checked business expectations; no execution."""
from copy import deepcopy
import importlib
import importlib.util

import pytest

from nexus.repair import oracle

SIG=dict(name='amount',params=[dict(name='quantity',type='Int64'),dict(name='price',type='Int64'),dict(name='promotion',type='Bool')],return_type='Int64')
EXAMPLES=[dict(args=[1,100,False],expected=100,suite='target'),dict(args=[2,100,False],expected=200,suite='regression')]


def api():
    assert importlib.util.find_spec('nexus.repair.relations') is not None,'paired relation contract missing'
    return importlib.import_module('nexus.repair.relations')


def raw():
    return dict(version=1,kind='relation',function='amount',domains=dict(quantity=dict(min=0,max=20,points=[9,10]),price=dict(min=1,max=100,points=[100]),promotion={}),
        relations=[dict(id='REL-MONOTONE',text='固定正价且无优惠时，增加数量不能降低费用',
        precondition='left_arg1 == right_arg1 and left_arg1 > 0 and not left_arg2 and not right_arg2 and left_arg0 < right_arg0',
        assertion='left_result <= right_result')],seed=1234,max_pairs=32,excluded_inputs=[])


def pair(left,right):return dict(left=left,right=right)


def test_relation_uses_two_typed_observations_without_inventing_numeric_answers():
    module=api();source=raw();contract=module.validate_contract(source,SIG,EXAMPLES)
    assert contract['algorithm']=='paired-relations-v1'
    assert contract['aliases']['left_arg0']=='quantity' and contract['aliases']['right_arg2']=='promotion'
    inputs=pair([9,100,False],[10,100,False])
    result=module.evaluate_pair(contract,inputs,900,0)
    assert result['state']=='FAIL' and result['applicable']==['REL-MONOTONE']
    assert result['failures']==[dict(kind='business_relation',relation_id='REL-MONOTONE',relation_text=source['relations'][0]['text'],
        left_args=[9,100,False],right_args=[10,100,False],left_actual_return=900,right_actual_return=0,assertion_value=False,expected_relation=True)]
    assert module.evaluate_pair(contract,inputs,900,1000)['state']=='PASS'
    assert module.evaluate_pair(contract,pair([9,100,True],[10,100,False]),900,0)['state']=='UNKNOWN'
    source['relations'][0]['assertion']='False';source['domains']['quantity']['points'].append(11)
    assert contract['relations'][0]['assertion']=='left_result <= right_result' and contract['domains']['quantity']['points']==[9,10]
    for bad in (True,None,1.0,oracle.HIGH+1):
        with pytest.raises(ValueError):module.evaluate_pair(contract,inputs,bad,0)
        with pytest.raises(ValueError):module.evaluate_pair(contract,inputs,900,bad)


@pytest.mark.parametrize('field',['precondition','assertion'])
@pytest.mark.parametrize('value',[None,True,[],{},3])
def test_nonstring_relation_expressions_are_rejected_before_cache(field,value):
    source=raw();source['relations'][0][field]=value
    with pytest.raises(ValueError):api().validate_contract(source,SIG,EXAMPLES)


@pytest.mark.parametrize('change',['extra','version','kind','function','seed','budget','empty','duplicate','id','text','item-field',
    'return-in-guard','unknown','call','attribute','integer-assertion','mixed-types','division','overflow','no-coverage','conflict','domain'])
def test_invalid_or_contradictory_relation_cannot_be_frozen(change):
    source=raw();item=source['relations'][0]
    if change=='extra':source['untrusted']=True
    elif change=='version':source['version']=True
    elif change=='kind':source['kind']='single'
    elif change=='function':source['function']='other'
    elif change=='seed':source['seed']=2**32
    elif change=='budget':source['max_pairs']=65
    elif change=='empty':source['relations']=[]
    elif change=='duplicate':source['relations'].append(deepcopy(item))
    elif change=='id':item['id']=[]
    elif change=='text':item['text']='x'*501
    elif change=='item-field':item['answer']=100
    elif change=='return-in-guard':item['precondition']='left_result == right_result'
    elif change=='unknown':item['assertion']='result == 0'
    elif change=='call':item['assertion']='eval("True")'
    elif change=='attribute':item['assertion']='left_result.real == 0'
    elif change=='integer-assertion':item['assertion']='left_result'
    elif change=='mixed-types':item['assertion']='left_arg2 == right_result'
    elif change=='division':item['precondition']='left_arg0 // 0 > 0'
    elif change=='overflow':item['precondition']=f'left_arg0 + {oracle.HIGH} >= 0'
    elif change=='no-coverage':item['precondition']='False'
    elif change=='conflict':item['assertion']='left_result > right_result'
    else:source['domains']['quantity']['min']=True
    with pytest.raises(ValueError):api().validate_contract(source,SIG,EXAMPLES)


def test_no_known_answer_for_one_side_is_not_inferred_from_candidate():
    source=raw();source['relations'][0]['precondition']='left_arg0 == 9 and right_arg0 == 10 and left_arg1 == right_arg1'
    source['relations'][0]['assertion']='left_result > right_result'
    assert api().validate_contract(source,SIG,EXAMPLES)['relations'][0]['assertion']=='left_result > right_result'


def test_exclusions_filter_both_sides_include_outside_domain_and_forbid_public_overlap():
    module=api();source=raw();source['excluded_inputs']=[[9,100,False],[-100,0,True]]
    contract=module.validate_contract(source,SIG,EXAMPLES)
    sampled=module.generate_pairs(contract)
    assert sampled['pairs']
    for item in sampled['pairs']:
        assert item['left']!=[9,100,False] and item['right']!=[9,100,False]
    for item in (pair([9,100,False],[10,100,False]),pair([8,100,False],[9,100,False])):
        with pytest.raises(ValueError):module.applicable(contract,item)
    for excluded in ([[1,100,False]],[[1,100,0]],[[1,100,False],[1,100,False]],[[1,2]],[[0,1,False]]*129):
        source['excluded_inputs']=excluded
        with pytest.raises(ValueError):module.validate_contract(source,SIG,EXAMPLES)


def test_pair_generation_is_bounded_deterministic_unique_and_covers_each_relation():
    module=api();source=raw();source['relations'].append(dict(id='REL-SAME',text='相同输入的两个实际返回相同',precondition='left_arg0 == right_arg0 and left_arg1 == right_arg1 and left_arg2 == right_arg2',assertion='left_result == right_result'))
    contract=module.validate_contract(source,SIG,EXAMPLES);first=module.generate_pairs(contract)
    assert first==module.generate_pairs(contract) and 1<=len(first['pairs'])<=32
    assert 0<first['candidate_checks']<=8192 and first['regression_pairs']==0
    keys=[module.pair_key(p) for p in first['pairs']];assert len(keys)==len(set(keys))
    assert {i for p in first['pairs'] for i in module.applicable(contract,p)}=={'REL-MONOTONE','REL-SAME'}
    assert any(p['left']==p['right'] for p in first['pairs'])
    with pytest.raises(ValueError):module.generate_pairs(contract,axes=[[0],[1],[False,True]])
    assert module.pair_key(pair([True],[False]))!=module.pair_key(pair([1],[0]))
    for item in ({},dict(left=[],right=[],extra=0),pair([None],[0])):
        with pytest.raises(ValueError):module.pair_key(item)


def test_required_regressions_take_priority_and_cannot_be_silently_dropped():
    module=api();source=raw();source['max_pairs']=16;contract=module.validate_contract(source,SIG,EXAMPLES)
    inputs=[pair([q,100,False],[q+1,100,False]) for q in range(17)]
    result=module.generate_pairs(contract,cumulative=inputs[:16]+inputs[:2])
    assert result['pairs']==inputs[:16] and result['regression_pairs']==16
    with pytest.raises(ValueError):module.generate_pairs(contract,cumulative=inputs)
    source['relations'].append(dict(id='REL-SPECIAL',text='覆盖另外一个价格',precondition='left_arg1 == 1 and right_arg1 == 1',assertion='True'))
    contract=module.validate_contract(source,SIG,EXAMPLES)
    with pytest.raises(ValueError):module.generate_pairs(contract,cumulative=inputs[:16])


def test_all_relations_get_coverage_before_budget_fill_and_same_pair_may_cover_several():
    module=api();source=raw();source['max_pairs']=16
    # Explicit critical points make these eight narrow guards part of the
    # bounded search; no arbitrary-predicate completeness is assumed.
    source['domains']['quantity']['points']=list(range(8))
    source['relations']=[dict(id='REL-Q'+str(q),text='覆盖指定数量',precondition=f'left_arg0 == {q} and right_arg0 == {q+1} and left_arg1 == right_arg1',assertion='left_result <= right_result') for q in range(8)]
    contract=module.validate_contract(source,SIG,EXAMPLES);result=module.generate_pairs(contract)
    assert len({i for p in result['pairs'] for i in module.applicable(contract,p)})==8
    assert len(result['pairs'])<=16


def test_shrink_preserves_price_promotion_and_relation_guard_with_coordinated_changes():
    module=api();contract=module.validate_contract(raw(),SIG,EXAMPLES);original=pair([9,100,False],[10,100,False])
    items=module.shrink_pairs(contract,original,'REL-MONOTONE')
    assert 1<=len(items)<=16 and len({module.pair_key(p) for p in items})==len(items)
    assert any(p['left'][1]==p['right'][1]==1 for p in items),'equal fixed prices must be shrinkable together'
    for item in items:
        assert 'REL-MONOTONE' in module.applicable(contract,item)
        assert sum(abs(int(v)) for side in item.values() for v in side)<219
        assert item['left'][2] is False and item['right'][2] is False
    with pytest.raises(ValueError):module.shrink_pairs(contract,original,'REL-UNKNOWN')
    source=raw();source['excluded_inputs']=[[9,1,False]];contract=module.validate_contract(source,SIG,EXAMPLES)
    assert all(p['left']!=[9,1,False] and p['right']!=[9,1,False] for p in module.shrink_pairs(contract,original,'REL-MONOTONE'))


def test_zero_argument_bool_return_and_int64_lower_bound_are_type_exact():
    module=api();signature=dict(name='constant',params=[],return_type='Bool')
    source=dict(version=1,kind='relation',function='constant',domains={},relations=[dict(id='REL-SAME',text='两次返回相同',precondition='True',assertion='left_result == right_result')],seed=0,max_pairs=16,excluded_inputs=[])
    contract=module.validate_contract(source,signature,[])
    assert module.generate_pairs(contract)['pairs']==[pair([],[])]
    assert module.evaluate_pair(contract,pair([],[]),True,False)['state']=='FAIL'
    with pytest.raises(ValueError):module.evaluate_pair(contract,pair([],[]),True,0)
    source['excluded_inputs']=[[]]
    with pytest.raises(ValueError):module.validate_contract(source,signature,[])
    signature=dict(name='identity',params=[dict(name='value',type='Int64')],return_type='Int64')
    source.update(function='identity',domains=dict(value=dict(min=oracle.LOW,max=oracle.LOW+1)),excluded_inputs=[])
    contract=module.validate_contract(source,signature,[])
    assert module.evaluate_pair(contract,pair([oracle.LOW],[oracle.LOW]),oracle.LOW,oracle.LOW)['state']=='PASS'


def test_evaluation_error_is_not_reclassified_as_an_inapplicable_guard():
    module=api();contract=module.validate_contract(raw(),SIG,EXAMPLES)
    contract['relations'][0]['precondition']='left_arg0 // (right_arg0 - left_arg0) >= 0'
    with pytest.raises(ValueError):module.applicable(contract,pair([1,100,False],[1,100,False]))
