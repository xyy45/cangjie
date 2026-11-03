"""Bounded real HTTP-client protocol with labelled MockTransport, never paid calls."""
import asyncio
import copy
import importlib
import importlib.util
import json

import httpx
import pytest

from tests.test_rule_drafts import prepared,snapshot,suggestion


def provider_module():
    assert importlib.util.find_spec('nexus.demo.rule_draft_provider') is not None,'rule draft model adapter missing'
    return importlib.import_module('nexus.demo.rule_draft_provider')


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    for key,value in dict(DEEPSEEK_API_KEY='draft-test-secret',DEEPSEEK_BASE_URL='https://model.example/v1',DEEPSEEK_MODEL='draft-test-model').items():monkeypatch.setenv(key,value)


def envelope():return dict(model='draft-test-model',usage=dict(prompt_tokens=50,completion_tokens=20,total_tokens=70),choices=[dict(finish_reason='stop',message={'content':json.dumps(suggestion())})])


def client(transport):return provider_module().RuleDraftProvider(transport=httpx.MockTransport(transport))


def test_exact_bounded_request_and_response_provenance(prepared):
    calls=[]
    def reply(request):calls.append(request);return httpx.Response(200,json=envelope())
    p=client(reply);body=p.prepare(snapshot(prepared));r=asyncio.run(p.complete(body))
    assert p.origin=='HTTP_FIXTURE_NOT_LIVE' and r['model_id']=='draft-test-model'
    assert json.loads(r['raw_text'])['examples'][0]['expected']==300
    sent=json.loads(calls[0].content)
    assert sent==body and sent['max_tokens']==6000 and sent['temperature']==.2 and sent['stream'] is False
    assert sent['response_format']=={'type':'json_object'}
    assert json.loads(sent['messages'][1]['content'])['signature']['name']=='fee'
    assert 'draft-test-secret' not in json.dumps(sent) and calls[0].headers['Authorization']=='Bearer draft-test-secret'
    with pytest.raises(ValueError):asyncio.run(p.complete(body))
    assert len(calls)==1


def test_changed_prepared_body_is_rejected_before_wire(prepared):
    calls=[];p=client(lambda request:calls.append(request));body=p.prepare(snapshot(prepared));body['max_tokens']=999999
    with pytest.raises(ValueError):asyncio.run(p.complete(body))
    assert calls==[]


@pytest.mark.parametrize('status',[401,429,500])
def test_known_http_error_preserves_sanitized_evidence(prepared,status):
    calls=[]
    def reply(request):
        calls.append(request);return httpx.Response(status,json={'error':{'message':json.dumps({'leak':'draft-test-secret'})}})
    p=client(reply);body=p.prepare(snapshot(prepared))
    from nexus.uploads.rule_drafts import DraftCallError
    with pytest.raises(DraftCallError) as error:asyncio.run(p.complete(body))
    assert error.value.uncertain is False and error.value.evidence['http_status']==status
    assert 'draft-test-secret' not in json.dumps(error.value.evidence)
    assert len(calls)==1


def test_unknown_transport_cannot_be_retried_on_same_adapter(prepared):
    calls=[]
    def timeout(request):calls.append(request);raise httpx.ReadTimeout('secret draft-test-secret',request=request)
    p=client(timeout);body=p.prepare(snapshot(prepared))
    from nexus.uploads.rule_drafts import DraftCallError
    with pytest.raises(DraftCallError) as error:asyncio.run(p.complete(body))
    assert error.value.uncertain and 'draft-test-secret' not in str(error.value)
    with pytest.raises(ValueError):asyncio.run(p.complete(body))
    assert len(calls)==1


@pytest.mark.parametrize('change',['no-usage','list-usage','bool-usage','over-budget','bad-total','incomplete','missing-model','empty-choices','non-json','huge'])
def test_invalid_upstream_envelopes_never_form_success(prepared,change):
    payload=envelope()
    if change=='no-usage':payload.pop('usage')
    elif change=='list-usage':payload['usage']=[]
    elif change=='bool-usage':payload['usage']['completion_tokens']=True
    elif change=='over-budget':payload['usage']['completion_tokens']=6001
    elif change=='bad-total':payload['usage']['total_tokens']=1
    elif change=='incomplete':payload['choices'][0]['finish_reason']='length'
    elif change=='missing-model':payload.pop('model')
    elif change=='empty-choices':payload['choices']=[]
    def reply(request):
        if change=='non-json':return httpx.Response(200,text='secret draft-test-secret')
        if change=='huge':return httpx.Response(200,content=b'x'*(1024*1024+1))
        return httpx.Response(200,json=payload)
    p=client(reply);body=p.prepare(snapshot(prepared))
    from nexus.uploads.rule_drafts import DraftCallError
    with pytest.raises(DraftCallError) as error:asyncio.run(p.complete(body))
    assert 'draft-test-secret' not in str(error.value)
    assert 'draft-test-secret' not in json.dumps(error.value.evidence)


def test_non_json_model_content_is_returned_for_strict_draft_rejection(prepared):
    payload=envelope();payload['choices'][0]['message']['content']='not a rule'
    p=client(lambda request:httpx.Response(200,json=payload));body=p.prepare(snapshot(prepared))
    r=asyncio.run(p.complete(body))
    from nexus.uploads.rule_contract import validate_suggestion
    assert validate_suggestion(r['raw_text'],snapshot(prepared))['status']=='INVALID'


@pytest.mark.parametrize('url',['http://model.example','https://user:password@model.example','https://model.example?token=bad','file:///tmp/model'])
def test_invalid_config_does_not_make_a_request(prepared,monkeypatch,url):
    monkeypatch.setenv('DEEPSEEK_BASE_URL',url)
    with pytest.raises(ValueError):client(lambda request:pytest.fail('invalid endpoint must not be used')).prepare(snapshot(prepared))
