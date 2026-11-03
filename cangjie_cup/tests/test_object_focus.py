"""Static object method focus over explicit confirmed field/oracle fixtures."""
import json
from copy import deepcopy
import pytest
from nexus.contracts import file_hash
from nexus.repair import localization
from tests.sdk.test_objects_sdk import declaration
from tests.test_object_contracts import state


def inputs(kind='public_field'):
    codes={'src/state.cj':'package bench\n'+declaration(),'src/order.cj':'package bench\npublic func adjust(state: OrderState, n: Int64): OrderState { return OrderState(state.net() + n, state.label, state.active, state.items) }\n'}
    sources={p:dict(content=s,file_hash=file_hash(s)) for p,s in codes.items()};binding=dict(task_id='task',baseline_id='b_'+'a'*32,baseline_hash='a'*64,spec_hash='b'*64,subject_id='c_'+'c'*32,subject_tree_hash='c'*64)
    case=dict(test_id='UploadedTests.case0',call_id='PUBLIC_FIELD-one',function='adjust',args=[state(1),1],field_path=['amount'],expected_value=2,value_type='Int64',requirement_refs=['REQ-UPLOAD'])
    failure=dict(kind='public_field',test_id=case['test_id'],call_id=case['call_id'],function='adjust',args=[state(1),1],field_path=['amount'],expected_value=2,actual_value=9,value_type='Int64',value_state='TYPED',actual='9',expected='2',expression='__nexusObjectActual0.amount',source=dict(log_ref='records/public.log'))
    if kind=='independent_rule':
        case.pop('call_id');case.pop('field_path');case.pop('expected_value');case.pop('value_type');case['expected']=state(2)
        failure=dict(kind='independent_rule',test_id=case['test_id'],args=case['args'],expected_value=state(2),actual_return=state(9),expected=json.dumps(state(2),ensure_ascii=False,separators=(',',':')),actual=json.dumps(state(9),ensure_ascii=False,separators=(',',':')),source=dict(log_ref='records/oracle.log'))
    return sources,[case],[failure],{},binding


@pytest.mark.parametrize('kind',['public_field','independent_rule'])
def test_object_focus_maps_cross_file_qualified_method_without_fabricated_graph(kind):
    data=inputs(kind);before=deepcopy(data);result=localization.build_focus(*data);assert data==before
    assert result['status']=='PARTIAL';target=result['targets'][0];assert target['mapping']=='CONFIRMED_CASE'
    assert [(f['function'],f['path']) for f in target['locations']]==[('adjust','src/order.cj'),('OrderState.net','src/state.cj')]
    assert all(a['slice']['status']=='UNAVAILABLE' for f in target['locations'] for a in f['anchors'])
    if kind=='public_field':assert target['field_path']==['amount'] and target['actual_value']==9 and 'actual_return' not in target
    else:assert target['actual_return']==state(9)


@pytest.mark.parametrize('change',['actual-type','path','expected','args'])
def test_object_focus_rejects_field_metadata_changes(change):
    data=inputs();failure=data[2][0]
    if change=='actual-type':failure['actual_value']=False
    elif change=='path':failure['field_path']=['active']
    elif change=='expected':failure['expected_value']=3
    else:failure['args'][0]['fields']['amount']=False
    with pytest.raises(ValueError):localization.build_focus(*data)
