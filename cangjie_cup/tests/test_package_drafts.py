"""Scoped rule drafts use oracle6 and frozen scope; no HTTP/model execution."""
import json
import httpx
import pytest
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.uploads.rule_contract import draft_snapshot,validate_suggestion
from nexus.demo.rule_draft_provider import RuleDraftProvider
from tests.sdk.test_package_services_sdk import material,rule,state


def fixture(tmp_path,kind):
    u=UploadService(RunStore(tmp_path))
    if kind=='object':
        files=material();files['src/model/state.cj']+=b'\n// READONLY_BODY_NOT_SENT\n';function='bench.step';allowed=['src/step.cj']
        examples=[dict(args=[state(0),1],expected=state(1),suite='target'),dict(args=[state(1,[]),1],expected=state(2,[]),suite='regression')];oracle=rule('oracle')
    else:
        files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,'src/entry.cj':b'package bench\npublic func add(n: Int64): Int64 { n }',
               'src/helper/anchor.cj':b'package bench.helper\npublic func anchor(n: Int64): Int64 { n }'}
        function='bench.add';allowed=['src/entry.cj'];examples=[dict(args=[0],expected=1,suite='target'),dict(args=[1],expected=2,suite='regression')]
        oracle=dict(version=6,function=function,domains=dict(n=dict(min=0,max=2,points=[])),expression='n+1',seed=7,max_cases=16,excluded_inputs=[])
    d=u.prepare_project('scoped',None,'按已确认的增量业务语义提出草案',actor_id='alice',request_key='one',entries=files)
    snap=draft_snapshot(u,d['id'],actor_id='alice',expected_version=1,function=function,allowed_paths=allowed)
    raw=dict(schema_version=1,summary='跨包业务草案',assumptions=[],questions=[],examples=examples,oracle=oracle)
    return snap,raw


@pytest.mark.parametrize('kind',['object','primitive'])
def test_scoped_suggestion_requires_version6_even_for_only_primitive_values(tmp_path,kind):
    snap,raw=fixture(tmp_path,kind);result=validate_suggestion(json.dumps(raw),snap)
    assert result['status']=='DRAFT_READY' and result['normalized_oracle']['signature']['scope']==snap['signature']['scope']
    assert 'READONLY_BODY_NOT_SENT' not in json.dumps(snap) and 'ORIGINAL_TEST_BODY_NOT_FOR_MODEL' not in json.dumps(snap)
    raw['oracle']['scope']=snap['signature']['scope']
    assert validate_suggestion(json.dumps(raw),snap)['status']=='INVALID'


@pytest.mark.parametrize('kind',['object','primitive'])
def test_scoped_prompt_uses_canonical_names_empty_exclusions_and_never_sends(tmp_path,monkeypatch,kind):
    from nexus.demo import rule_draft_provider as provider
    monkeypatch.setattr(provider,'model_config',lambda:dict(DEEPSEEK_API_KEY='fixture-key',DEEPSEEK_MODEL='fixture-model',DEEPSEEK_BASE_URL='https://fixture.invalid'))
    calls=[];client=RuleDraftProvider(transport=httpx.MockTransport(lambda request:calls.append(request)))
    snap,_=fixture(tmp_path,kind);body=client.prepare(snap);text=body['messages'][0]['content']
    assert 'rule-draft-packages-prompt-v1' in text and 'oracle仅允许version=6' in text
    assert 'excluded_inputs必须为[]' in text and 'scope' in text and '规范' in text
    assert 'max_cases、excluded_inputs；' in text
    assert not calls
