"""Mock HTTP is protocol evidence, not a paid LIVE model evaluation."""
import asyncio
import json

import httpx
import pytest

from nexus.demo.deepseek import DeepSeekProvider
from nexus.llm.provider import ProviderUnavailable
from nexus.store import RunStore


def context():
    return dict(goal='修复数量下界',allowed_paths=['src/quantity.cj'],
        files={'src/quantity.cj':{'content':'quantity >= 0','file_hash':'a'*64}},
        requirements={'requirements':[{'id':'REQ-QTY'}]},feedback=[])


def content():
    return dict(schema_version=1,summary='数量下界应为1。',
        suggestions=[{'path':'src/quantity.cj','reason':'拒绝零数量，保留上界。'}],
        proposal={'edits':[{'path':'src/quantity.cj','before_hash':'a'*64,'content':'quantity >= 1'}],
                  'requirement_refs':['REQ-QTY']})


@pytest.fixture
def setup(tmp_path,monkeypatch):
    for key,value in {'DEEPSEEK_API_KEY':'test-secret','DEEPSEEK_BASE_URL':'https://model.example',
                      'DEEPSEEK_MODEL':'test-model'}.items():monkeypatch.setenv(key,value)
    store=RunStore(tmp_path);task=store.create_task('base','fix',['src/quantity.cj'])
    return store,task


def transport(monkeypatch,payload):
    real_client=httpx.AsyncClient;calls=[]
    def reply(request):
        calls.append(request)
        return httpx.Response(200,json={'model':'test-model','usage':{'prompt_tokens':80,'completion_tokens':20,'total_tokens':100},
            'choices':[{'finish_reason':'stop','message':{'content':json.dumps(payload,ensure_ascii=False)}}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(reply),**kwargs))
    return calls


def test_model_returns_dynamic_code_and_separate_advice_without_recording_key(setup,monkeypatch):
    store,task=setup;calls=transport(monkeypatch,content())
    result=asyncio.run(DeepSeekProvider(store,task.id).propose(context()))
    assert result.edits[0].content=='quantity >= 1'
    events=store.records(task.id,'event')
    assert events[-1]['type']=='MODEL_SUGGESTION'
    assert events[-1]['summary']=='数量下界应为1。'
    request=json.loads(calls[0].content)
    assert request['response_format']=={'type':'json_object'}
    assert request['max_tokens']<=6000
    assert all('test-secret' not in p.read_text() for p in (store.root/'records').iterdir())


def test_same_round_cannot_issue_a_second_paid_request(setup,monkeypatch):
    store,task=setup;calls=transport(monkeypatch,content())
    asyncio.run(DeepSeekProvider(store,task.id).propose(context()))
    with pytest.raises(ProviderUnavailable):asyncio.run(DeepSeekProvider(store,task.id).propose(context()))
    assert len(calls)==1


def advance_failed_round(store,task,ctx):
    attempt=store.get_task(task.id).attempt_count+1
    call=store.records(task.id,'model_call')[-1]
    candidate=dict(id=f'candidate-{attempt}',task_id=task.id,attempt=attempt,
        baseline_hash='b'*64,tree_hash=str(attempt)*64,diff_ref='records/test.diff',
        edits=content()['proposal']['edits'],model_call_id=call['id'])
    store.append_record(task.id,'candidate',candidate)
    feedback=dict(previous_candidate_id=candidate['id'],tree_hash=candidate['tree_hash'],
        failed_checks=[dict(state='FAIL')],diagnostic_snippets=[dict(text='zeroQuantity failed')])
    store.append_record(task.id,'event',dict(repair_feedback=feedback))
    store.update_task(task.id,attempt_count=attempt,status='GENERATING')
    ctx['feedback'].append(feedback)


def test_three_attributable_rounds_allowed_but_fourth_is_not(setup,monkeypatch):
    store,task=setup;calls=transport(monkeypatch,content());ctx=context()
    for _ in range(3):
        asyncio.run(DeepSeekProvider(store,task.id).propose(ctx))
        advance_failed_round(store,task,ctx)
    with pytest.raises(ProviderUnavailable):
        asyncio.run(DeepSeekProvider(store,task.id).propose(ctx))
    assert len(calls)==3
    suggestions=[e for e in store.records(task.id,'event') if e['type']=='MODEL_SUGGESTION']
    assert [e['round'] for e in suggestions]==[1,2,3]


def test_next_round_requires_bound_failed_feedback_and_successful_previous_call(setup,monkeypatch):
    store,task=setup;calls=transport(monkeypatch,content());ctx=context()
    asyncio.run(DeepSeekProvider(store,task.id).propose(ctx))
    advance_failed_round(store,task,ctx)
    ctx['feedback'][-1]['previous_candidate_id']='foreign'
    with pytest.raises(ProviderUnavailable):
        asyncio.run(DeepSeekProvider(store,task.id).propose(ctx))
    assert len(calls)==1


def test_legacy_reservation_stays_spent(setup,monkeypatch):
    store,task=setup;calls=transport(monkeypatch,content())
    with store.connect() as db:
        db.execute('CREATE TABLE demo_model_budget(task_id TEXT PRIMARY KEY,call_id TEXT NOT NULL)')
        db.execute('INSERT INTO demo_model_budget VALUES (?,?)',(task.id,'legacy'))
    with pytest.raises(ProviderUnavailable):asyncio.run(DeepSeekProvider(store,task.id).propose(context()))
    assert not calls


def test_analysis_evidence_ids_are_bound_to_submitted_valid_context(setup,monkeypatch):
    store,task=setup;payload=content();payload['analysis_refs']=['job:sympas_dep_graph']
    calls=transport(monkeypatch,payload);ctx=context()
    ctx['analysis']={'files':[{'tools':[{'evidence_id':'job:sympas_dep_graph','included':True,'status':'VALID','data':{'graphs':[]}}]}]}
    asyncio.run(DeepSeekProvider(store,task.id).propose(ctx))
    suggestion=store.records(task.id,'event')[-1]
    assert suggestion['analysis_refs']==['job:sympas_dep_graph']
    assert suggestion['analysis_context_hash']
    assert json.loads(calls[0].content)['messages'][1]['content'].find('job:sympas_dep_graph')>=0


def test_model_cannot_cite_failed_or_unknown_analysis(setup,monkeypatch):
    store,task=setup;payload=content();payload['analysis_refs']=['unknown:sympas_slice']
    transport(monkeypatch,payload);ctx=context()
    ctx['analysis']={'files':[{'tools':[{'evidence_id':'unknown:sympas_slice','included':False,'status':'FAILED'}]}]}
    with pytest.raises(ProviderUnavailable):asyncio.run(DeepSeekProvider(store,task.id).propose(ctx))
    assert not any(e['type']=='MODEL_SUGGESTION' for e in store.records(task.id,'event'))


@pytest.mark.parametrize('payload',[{},dict(content(),proposal={'edits':[], 'requirement_refs':['REQ-QTY']})])
def test_invalid_model_output_never_falls_back_to_a_fixed_answer(setup,monkeypatch,payload):
    store,task=setup;calls=transport(monkeypatch,payload)
    with pytest.raises(ProviderUnavailable):asyncio.run(DeepSeekProvider(store,task.id).propose(context()))
    assert len(calls)==1 and not store.records(task.id,'candidate')

@pytest.mark.parametrize('path',['src/cases_test.cj','cjpm.toml','../outside.cj'])
def test_model_cannot_smuggle_protected_edits(setup,monkeypatch,path):
    store,task=setup;payload=content()
    payload['suggestions'][0]['path']=path;payload['proposal']['edits'][0]['path']=path
    transport(monkeypatch,payload)
    with pytest.raises(ProviderUnavailable):asyncio.run(DeepSeekProvider(store,task.id).propose(context()))
    assert not store.records(task.id,'candidate')


def test_http_timeout_is_uncertain_and_never_replayed(setup,monkeypatch):
    store,task=setup;real_client=httpx.AsyncClient;calls=[]
    def fail(request):
        calls.append(request);raise httpx.ReadTimeout('test timeout')
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(fail),**kwargs))
    with pytest.raises(ProviderUnavailable) as first:asyncio.run(DeepSeekProvider(store,task.id).propose(context()))
    assert first.value.state=='IN_DOUBT'
    with pytest.raises(ProviderUnavailable):asyncio.run(DeepSeekProvider(store,task.id).propose(context()))
    assert len(calls)==1 and store.records(task.id,'model_call')[-1]['status']=='IN_DOUBT'


def test_json_escaped_credential_echo_is_redacted_in_both_layers(setup,monkeypatch):
    store,task=setup;payload=content();payload['summary']='test-secret'
    nested=json.dumps(payload).replace('test-secret',r'\u0074est-secret')
    envelope={'model':'test-model','usage':{'completion_tokens':20},
              'choices':[{'finish_reason':'stop','message':{'content':nested}}]}
    raw=json.dumps(envelope).replace('test-model',r'\u0074est-model')
    real_client=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real_client(
        transport=httpx.MockTransport(lambda request:httpx.Response(200,text=raw)),**kwargs))
    asyncio.run(DeepSeekProvider(store,task.id).propose(context()))
    assert store.records(task.id,'event')[-1]['summary']=='[REDACTED]'
    for p in (store.root/'records').iterdir():
        assert 'test-secret' not in p.read_text()
        if p.name.endswith('.response.json'):
            persisted=json.loads(p.read_text())
            assert json.loads(persisted['choices'][0]['message']['content'])['summary']=='[REDACTED]'
