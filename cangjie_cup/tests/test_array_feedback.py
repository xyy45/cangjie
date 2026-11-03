"""Pure Array fact projections and explicit no-model context fixtures."""
import asyncio,json
import pytest
from nexus.contracts import file_hash
from nexus.repair import localization
from nexus.llm.provider import ProviderUnavailable
from nexus.repair.cegis_loop import RepairLoop
from tests.test_repair_loop import Client
from tests.test_array_services import setup


def material(kind):
    source='package uploaded\npublic func items(values: Array<Int64>): Array<Int64> {\nreturn values\n}\n'
    sources={'src/uploaded.cj':dict(content=source,file_hash=file_hash(source))}
    case=dict(test_id='Fixture.case0',function='items',args=[[]],log_ref='records/source.log',requirement_refs=['REQ-UPLOAD'])
    failure=dict(kind=kind,test_id=case['test_id'],args=[[]],source=dict(log_ref='records/source.log'),actual_return=[0],requirement_refs=['REQ-UPLOAD'])
    if kind=='independent_rule':case['expected']=[];failure.update(expected_value=[],expected='[]',actual='[0]')
    if kind=='business_property':failure.update(property_id='PROP-ITEMS',property_text='exact items',assertion_value=False,expected_property=True)
    if kind=='business_relation_call':failure.update(pair_id='pair',relation_role='left',relation_id='REL-ITEMS',relation_text='distinct items',assertion_value=False,expected_relation=True)
    if kind=='business_sequence_call':
        case.update(call_id='seq.step1',expected_state=[]);failure.update(call_id='seq.step1',sequence_id='seq',step_index=1,sequence_role='failure',initial_state=[],context=[],operation_id='OP-RESET',operation_text='clear',before_state=[1],reference_before=[1],expected_state=[],failure_ids=['MODEL-OP-RESET'])
    return sources,[case],[failure],{},dict(baseline_id='baseline')


@pytest.mark.parametrize('kind',['independent_rule','business_property','business_relation_call','business_sequence_call'])
def test_array_focus_preserves_typed_empty_expected_and_real_return(kind):
    args=material(kind);result=localization.build_focus(*args);target=result['targets'][0]
    assert target['mapping']=='CONFIRMED_CASE' and target['args']==[[]] and json.loads(target['args_text'])==[[]]
    assert target['actual_return']==[0] and target['failure_source']['log_ref']=='records/source.log' and target['locations'][0]['function']=='items'
    if kind=='independent_rule':assert target['expected_value']==[] and target['expected']=='[]'
    args[2][0]['actual_return'].append(99);assert target['actual_return']==[0]


@pytest.mark.parametrize('items',[[],[0],[-(1<<63),(1<<63)-1],[0]*16])
def test_array_compiler_literal_call_maps_only_closed_values(items):
    text='items(['+', '.join(str(v) for v in items)+'])'
    assert localization.literal_call(text)==('items',[items])


@pytest.mark.parametrize('text',['items([true])','items([[1]])','items([1.0])','items([9223372036854775808])','items(['+','.join('0' for _ in range(17))+'])','items(values)','items([1][0])','items(Array<Int64>([]))'])
def test_array_call_projection_rejects_nonliteral_nested_or_invalid_data(text):
    with pytest.raises(ValueError):localization.literal_call(text)


def test_nested_bool_never_matches_int64_array_arguments():
    assert not localization.same_args([[True]],[[1]])
    assert not localization.same_args([[[1]]],[[[1]]])
    assert localization.same_args([[],[0,-1]],[[],[0,-1]])


@pytest.mark.parametrize('kind',['independent_rule','business_property','business_relation_call','business_sequence_call'])
def test_array_invalid_typed_return_is_rejected_in_projection(kind):
    args=material(kind);args[2][0]['actual_return']=[True]
    if kind=='independent_rule':args[2][0]['actual']='[true]'
    with pytest.raises(ValueError):localization.build_focus(*args)


def test_array_generation_context_describes_readonly_grammar_without_model_call(tmp_path):
    store,ws,task,_,_=setup(tmp_path,'oracle');contexts=[]
    class Stop:
        async def propose(self,context):contexts.append(context);raise ProviderUnavailable('EXPLICIT STOP BEFORE MODEL REQUEST')
    result=asyncio.run(RepairLoop(store,provider_factory=lambda *_:Stop(),client_factory=Client).run(task.id))
    assert result.status=='BLOCKED' and len(contexts)==1
    c=contexts[0]['upload_constraints']
    assert 'Array<Int64>' in c['types'] and c['array_max_length']==16 and c['readonly_arrays'] is True
    assert 'for' in c['allowed'] and '.size' in c['allowed'] and '下标读取' in c['allowed']
    assert '数组元素赋值' in c['forbidden'] and 'Array构造器' in c['forbidden']
    assert 'verification/oracle.json' not in contexts[0]['files']


def test_explicit_model_http_transport_is_recorded_as_test_not_live(tmp_path,monkeypatch):
    import httpx
    from nexus.demo.deepseek import DeepSeekProvider
    from nexus.store import RunStore
    from tests.test_deepseek_demo import context,content
    for key,value in dict(DEEPSEEK_API_KEY='test-only',DEEPSEEK_BASE_URL='https://fixture.invalid',DEEPSEEK_MODEL='test-model').items():monkeypatch.setenv(key,value)
    store=RunStore(tmp_path);task=store.create_task('base','fixture only',['src/quantity.cj']);calls=[]
    def reply(request):
        calls.append(request)
        return httpx.Response(200,json=dict(model='test-model',usage=dict(prompt_tokens=1,completion_tokens=1,total_tokens=2),choices=[dict(finish_reason='stop',message=dict(content=json.dumps(content())))]))
    provider=DeepSeekProvider(store,task.id,transport=httpx.MockTransport(reply));asyncio.run(provider.propose(context()))
    assert len(calls)==1 and provider.origin=='TEST'
    assert {r['origin'] for r in store.records(task.id,'model_call')}=={'TEST'}
    assert next(e for e in store.records(task.id,'event') if e['type']=='MODEL_SUGGESTION')['origin']=='TEST'
    assert DeepSeekProvider(store,task.id).origin=='LIVE'
