"""Versioned nominal-object business models; no candidate or network execution."""
from copy import deepcopy
import pytest
from nexus.repair import oracle,properties,relations,sequences
from tests.test_object_values import types,obj


def state(amount=0):
    value=obj();value['fields'].update(amount=amount,items=[]);return value


def signature(returned='OrderState'):
    return dict(name='adjust',params=[dict(name='state',type='OrderState'),dict(name='n',type='Int64')],return_type=returned,types=types())


def raw_oracle():
    return dict(version=5,function='adjust',domains=dict(state=dict(values=[state(0),state(1),state(2),state(3)]),n=dict(min=0,max=1,points=[])),
                expression='object_with(state,"amount",object_get(state,"amount") + n)',seed=7,max_cases=16,excluded_inputs=[])


def raw_property():
    return dict(version=4,kind='single',function='adjust',domains=raw_oracle()['domains'],properties=[dict(id='PROP-AMOUNT',text='累计量与输入相符',precondition='True',assertion='object_get(result,"amount") == object_get(arg0,"amount") + arg1')],seed=7,max_cases=16,excluded_inputs=[])


def raw_relation():
    return dict(version=4,kind='relation',function='adjust',domains=raw_oracle()['domains'],relations=[dict(id='REL-IDENTITY',text='同样输入必须给出相同对象字段',precondition='left_arg0 == right_arg0 and left_arg1 == right_arg1',assertion='left_result == right_result')],seed=7,max_pairs=16,excluded_inputs=[])


def sequence_raw():
    sig=dict(name='advance',params=[dict(name='mode',type='Int64'),dict(name='state',type='OrderState'),dict(name='label',type='String')],return_type='OrderState',types=types())
    raw=dict(version=4,kind='sequence',function='advance',state_param='state',domains=dict(mode=dict(min=0,max=0,points=[]),state=dict(values=[state(0),state(1)]),label=dict(values=['a','中'])),initial_states=[state(0)],initial_precondition='True',context_params=['label'],
             operations=[dict(id='OP-FLIP',text='切换状态字段',args=[0,{'context':'label'}],transition='object_with(state,"amount",1-object_get(state,"amount"))')],
             invariants=[dict(id='INV-BOUNDS',text='状态字段为0或1',precondition='True',assertion='0 <= object_get(result,"amount") <= 1')],seed=7,max_sequences=8,max_steps=4,excluded_inputs=[])
    return raw,sig


def test_object_oracle_v5_returns_typed_copied_object_and_keeps_registry():
    raw=raw_oracle();sig=signature();c=oracle.validate_contract(raw,sig,[]);assert c['version']==5 and c['algorithm']=='boundary-object-v5' and c['signature']['types']==types()
    value=oracle.expected(c,[state(1),1]);assert value==state(2)
    value['fields']['items'].append(99);assert oracle.expected(c,[state(1),1])==state(2)
    raw['domains']['state']['values'][0]['fields']['amount']=99;sig['types']['OrderState']['fields'][0]['name']='other';assert c['domains']['state']['values'][0]==state(0) and c['signature']['types']==types()


@pytest.mark.parametrize('version',[1,2,3,4])
def test_object_signatures_require_object_oracle_version(version):
    raw=raw_oracle();raw['version']=version
    with pytest.raises(ValueError):oracle.validate_contract(raw,signature(),[])


@pytest.mark.parametrize('expression,expected_type,answer',[
 ('object_get(s,"amount")','Int64',1),
 ('object_with(s,"amount",2)','OrderState',state(2)),
 ('object_new("OrderState",2,"中",True,[])','OrderState',state(2)),
 ('array_len(object_get(s,"items")) + byte_len(object_get(s,"label"))','Int64',3),
 ('object_with(s,"items",array_append(object_get(s,"items"),3))','OrderState',dict(state(1),fields={**state(1)['fields'],'items':[3]})),
 ('s == object_new("OrderState",1,"中",True,[])','Bool',True),
])
def test_object_expression_helpers_are_typed_closed_and_copied(expression,expected_type,answer):
    t=types();node=oracle.expression_tree(expression,('s',),allow_objects=True,types=t)
    assert oracle.expression_type(node,{'s':'OrderState'},types=t)==expected_type
    supplied=state(1);before=deepcopy(supplied);result=oracle.evaluate(node,{'s':supplied},allow_objects=True,types=t);assert result==answer and supplied==before
    if type(result) is dict:result['fields']['items'].append(99);assert supplied==before


@pytest.mark.parametrize('text',[
 's.amount','{"amount":1}','object_get(s,k)','object_with(s,k,0)','object_new(k,1,"",True,[])',
 'object_get(s,"missing")','object_with(s,"amount",True)','object_new("Unknown",1)',
 'object_new("OrderState",1)','object_get(1,"amount")','object_with(s,"items",[True])',
])
def test_object_helpers_reject_untyped_members_dynamic_fields_and_wrong_values(text):
    with pytest.raises(ValueError):
        node=oracle.expression_tree(text,('s','k'),allow_objects=True,types=types());oracle.expression_type(node,{'s':'OrderState','k':'String'},types=types())


def test_object_helpers_not_enabled_in_legacy_expression_versions():
    for flags in ({},{'allow_strings':True},{'allow_arrays':True}):
        with pytest.raises(ValueError):oracle.expression_tree('object_get(s,"amount")',('s',),**flags)


def test_nominally_different_objects_cannot_compare_as_same_type():
    t=types();t['OtherState']=deepcopy(t['OrderState']);node=oracle.expression_tree('a == b',('a','b'),allow_objects=True,types=t)
    with pytest.raises(ValueError):oracle.expression_type(node,{'a':'OrderState','b':'OtherState'},types=t)


@pytest.mark.parametrize('text',['object_with(s,"amount",9223372036854775807 + 1)','array_at(object_get(s,"items"),0)','object_with(s,"items",array_append([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],1))'])
def test_object_intermediate_overflow_index_and_size_errors_are_rejected(text):
    node=oracle.expression_tree(text,('s',),allow_objects=True,types=types())
    with pytest.raises(ValueError):oracle.evaluate(node,{'s':state(0)},allow_objects=True,types=types())


def test_object_property_and_relation_versions_keep_typed_observations():
    p=properties.validate_contract(raw_property(),signature(),[]);assert p['algorithm']=='single-properties-object-v4'
    assert properties.evaluate_result(p,[state(1),1],state(2))['state']=='PASS'
    failed=properties.evaluate_result(p,[state(1),1],state(3));assert failed['state']=='FAIL' and failed['failures'][0]['actual_return']==state(3)
    r=relations.validate_contract(raw_relation(),signature(),[]);assert r['algorithm']=='paired-relations-object-v4'
    pair=dict(left=[state(1),1],right=[state(1),1]);assert relations.evaluate_pair(r,pair,state(2),state(3))['state']=='FAIL'


def test_object_sequence_nonfirst_state_and_fixed_string_context_model():
    raw,sig=sequence_raw();c=sequences.validate_contract(raw,sig,[]);assert c['algorithm']=='state-sequences-object-v4' and c['state_index']==1
    trace=dict(initial_state=state(0),context=['中'],steps=[dict(operation_id='OP-FLIP',args=[0,'中']) for _ in range(3)])
    plan=sequences.reference_trace(c,trace);assert [s['expected_state'] for s in plan['steps']]==[state(1),state(0),state(1)]
    assert sequences.evaluate_step(c,plan['steps'][0],state(0))['state']=='FAIL'
