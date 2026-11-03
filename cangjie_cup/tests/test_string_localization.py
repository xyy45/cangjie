"""Pure projections of already verified String facts; no execution or MCP."""
import json
import pytest
from nexus.contracts import file_hash
from nexus.repair import localization,values


def material(kind):
    source='package uploaded\npublic func ticket(code: String): String {\nreturn code + "a"\n}\n'
    sources={'src/uploaded.cj':dict(content=source,file_hash=file_hash(source))}
    case=dict(test_id='Fixture.case0',function='ticket',args=['中'],log_ref='records/source.log',requirement_refs=['REQ-UPLOAD'])
    failure=dict(kind=kind,test_id=case['test_id'],args=['中'],source=dict(log_ref='records/source.log'),actual_return='',requirement_refs=['REQ-UPLOAD'])
    if kind=='independent_rule':
        case['expected']='中a';failure.update(expected_value='中a',actual='""',expected=json.dumps('中a',ensure_ascii=False))
    if kind=='business_property':failure.update(property_id='PROP-LENGTH',property_text='length',assertion_value=False,expected_property=True)
    if kind=='business_relation_call':failure.update(pair_id='pair',relation_role='left',relation_id='REL-SPLIT',relation_text='distinct',assertion_value=False,expected_relation=True)
    if kind=='business_sequence_call':
        case.update(call_id='seq.step1',expected_state='中a');failure.update(call_id='seq.step1',sequence_id='seq',step_index=1,sequence_role='failure',initial_state='',context=[],operation_id='OP-APPEND',operation_text='append',before_state='中',reference_before='中',expected_state='中a',failure_ids=['MODEL'])
    return sources,[case],[failure],{},dict(baseline_id='baseline')


@pytest.mark.parametrize('kind',['independent_rule','business_property','business_relation_call','business_sequence_call'])
def test_string_observations_keep_empty_actual_and_typed_values_in_focus(kind):
    args=material(kind);result=localization.build_focus(*args);target=result['targets'][0]
    assert target['mapping']=='CONFIRMED_CASE' and target['args']==['中']
    if kind=='independent_rule':assert target['expected_value']=='中a' and target['actual_return']==''
    else:assert target['actual_return']==''
    assert target['failure_source']['log_ref']=='records/source.log' and target['locations'][0]['function']=='ticket'


@pytest.mark.parametrize('value',['','中😀',chr(0)+'|Summary:'+chr(10),'${data}'])
def test_only_trusted_string_literal_call_can_be_mapped(value):
    assert localization.literal_call('ticket('+values.string_literal(value)+')')==('ticket',[value])


@pytest.mark.parametrize('field,value',[('expected_value','wrong'),('actual','null'),('actual_return',None)])
def test_string_oracle_projection_rejects_inconsistent_typed_and_text_values(field,value):
    args=material('independent_rule');args[2][0][field]=value
    with pytest.raises(ValueError):localization.build_focus(*args)
