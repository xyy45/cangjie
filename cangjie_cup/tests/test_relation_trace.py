"""Two SDK case fixtures must precede every relation judgment."""
import importlib
import importlib.util

import pytest

from nexus.repair import relations
from tests.test_relations import raw,SIG,EXAMPLES,pair
from tests.test_primitive_trace import log,TOKEN


def api():
    assert importlib.util.find_spec('nexus.repair.relation_trace') is not None,'paired relation observation interpreter missing'
    return importlib.import_module('nexus.repair.relation_trace')


def contract():
    source=raw();source['relations'].append(dict(id='REL-SAME',text='相同输入返回一致',precondition='left_arg0 == right_arg0 and left_arg1 == right_arg1 and left_arg2 == right_arg2',assertion='left_result == right_result'))
    return relations.validate_contract(source,SIG,EXAMPLES)


PAIRS=[pair([9,100,False],[10,100,False]),pair([9,100,False],[9,100,False])]


def test_two_returns_and_independent_duplicate_occurrences_are_attributed_to_real_cases():
    module=api();value=contract();text=log('relation',('900','0','900','901'))
    result=module.interpret(value,PAIRS,TOKEN,text,0,None)
    assert result['state']=='FAIL' and result['execution_state']=='PASS'
    first,second=result['failures']
    assert first['relation_id']=='REL-MONOTONE' and first['left_actual_return']==900 and first['right_actual_return']==0
    assert second['relation_id']=='REL-SAME' and second['left_actual_return']==900 and second['right_actual_return']==901
    assert first['left_test_id']=='NexusRelations'+TOKEN+'.case0' and first['right_test_id']=='NexusRelations'+TOKEN+'.case1'
    assert second['left_test_id'].endswith('.case2') and second['right_test_id'].endswith('.case3')
    assert first['pair_id']!=second['pair_id'] and 'expected' not in first
    assert first['assertion_value'] is False and first['expected_relation'] is True
    for failure in result['failures']:
        for side in ('left','right'):
            source=failure[side+'_source']
            assert 'NEXUS_RELATION_V1|' in text[source['start_char']:source['end_char']]
            assert source['coordinate']=='ANSI_STRIPPED_FULL_LOG'
    assert [(r['id'],r['observed'],r['failed']) for r in result['per_relation']]==[('REL-MONOTONE',1,1),('REL-SAME',1,1)]
    program=module.harness(value,PAIRS,'bench',TOKEN).decode()
    assert program.count('__nexusTarget'+TOKEN+'(9, 100, false)')==3
    assert 'func case3()' in program and 'NEXUS_PROPERTY_V1' not in program


@pytest.mark.parametrize('change',['missing-side','cross-side','type','nonce','summary','exception','truncated'])
def test_absent_or_wrong_side_cannot_be_completed_by_other_observations(change):
    module=api();text=log('relation',('900','0','900','900'));problem=None
    marker='NEXUS_RELATION_V1|'+TOKEN+'|case1|Int64|0'
    if change=='missing-side':text=text.replace(marker,'')
    elif change=='cross-side':text=text.replace('|case1|','|case0|')
    elif change=='type':text=text.replace('|Int64|0','|Bool|false')
    elif change=='nonce':text=text.replace(marker,marker.replace(TOKEN,'f'*16))
    elif change=='summary':text=text.split('Summary:',1)[0]
    elif change=='exception':problem='TimeoutError'
    else:text=text[:text.index(marker)]
    result=module.interpret(contract(),PAIRS,TOKEN,text,0,problem)
    assert result['state']=='UNKNOWN' and result['observations']==[] and result['failures']==[]


def test_required_relation_coverage_and_unique_pairs_remain_outer_invariants():
    module=api();value=contract();text=log('relation',('900','0'))
    assert module.interpret(value,PAIRS[:1],TOKEN,text,0,None)['state']=='UNKNOWN'
    narrowed=module.interpret(value,PAIRS[:1],TOKEN,text,0,None,required_ids=['REL-MONOTONE'])
    assert narrowed['state']=='FAIL' and narrowed['per_relation'][1]['observed']==0
    for scope in ([],['REL-UNKNOWN'],['REL-MONOTONE','REL-MONOTONE'],{}):
        with pytest.raises(ValueError):module.interpret(value,PAIRS[:1],TOKEN,text,0,None,required_ids=scope)
    for inputs in ([],PAIRS[:1]*2,PAIRS*33,[pair([1,100,True],[2,100,True])]):
        with pytest.raises(ValueError):module.harness(value,inputs,'bench',TOKEN)


def test_zero_argument_bool_relation_observes_twice_and_expression_errors_are_unknown():
    module=api();signature=dict(name='constant',params=[],return_type='Bool')
    source=dict(version=1,kind='relation',function='constant',domains={},relations=[dict(id='REL-SAME',text='两次相同',precondition='True',assertion='left_result == right_result')],seed=0,max_pairs=16,excluded_inputs=[])
    value=relations.validate_contract(source,signature,[])
    result=module.interpret(value,[pair([],[])],TOKEN,log('relation',('true','false'),'Bool'),0,None)
    assert result['state']=='FAIL' and len(result['observations'])==1
    value=contract();value['relations'][0]['assertion']='left_result // 0 > right_result'
    assert module.interpret(value,PAIRS,TOKEN,log('relation',('900','0','900','900')),0,None)['state']=='UNKNOWN'
