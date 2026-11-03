"""Object rule suggestions are source-bound data, never model or tool execution."""
import json
from copy import deepcopy
import httpx
import pytest
from nexus.contracts import digest,source_manifest
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.uploads.rule_contract import draft_snapshot,validate_suggestion
from nexus.demo.rule_draft_provider import response_schema,RuleDraftProvider
from tests.sdk.test_objects_sdk import declaration
from tests.test_object_contracts import state,signature,raw_oracle,raw_property,raw_relation
from tests.test_object_values import types


def examples():return [dict(args=[state(1),1],expected=state(2),suite='target'),dict(args=[state(0),0],expected=state(0),suite='regression')]


def prepare(root):
    uploads=UploadService(RunStore(root));source=declaration()+'public func adjust(state: OrderState, n: Int64): OrderState { state }\n'
    d=uploads.prepare('state.cj',source.encode(),'amount加n，其他字段保持，返回新状态',actor_id='alice',request_key='one')
    return uploads,d,dict(expected_version=1,function='adjust',examples_json=json.dumps(examples()),consent=True,actor_id='alice')


def suggestion(rule=None):return json.dumps(dict(schema_version=1,summary='对象业务草案',assumptions=[],questions=[],examples=examples(),oracle=raw_oracle() if rule is None else rule),ensure_ascii=False)


def test_object_draft_snapshot_freezes_source_registry_and_preserves_upload(tmp_path):
    u,d,args=prepare(tmp_path);before=source_manifest(tmp_path);snapshot=draft_snapshot(u,d['id'],actor_id='alice',expected_version=1,function='adjust')
    assert snapshot['signature']==signature() and snapshot['binding_hash']==digest({k:v for k,v in snapshot.items() if k!='binding_hash'})
    assert u.get(d['id'],actor_id='alice')['status']=='DRAFT' and source_manifest(tmp_path)==before


def test_object_response_schema_closes_nominal_tags_fields_and_leaf_types():
    schema=response_schema(signature());e=next(s for s in schema['properties']['examples']['anyOf'] if s.get('type')=='array')['items'];obj=e['properties']['expected']
    assert obj['type']=='object' and obj['additionalProperties'] is False and set(obj['required'])=={'$type','fields'}
    assert obj['properties']['$type']['const']=='OrderState';fields=obj['properties']['fields'];assert fields['additionalProperties'] is False and fields['required']==['amount','label','active','items']
    assert fields['properties']['amount']['type']=='integer' and fields['properties']['active']['type']=='boolean' and fields['properties']['items']['maxItems']==16


def test_object_oracle5_draft_waits_for_explicit_confirmation(tmp_path):
    u,d,args=prepare(tmp_path);snapshot=draft_snapshot(u,d['id'],actor_id='alice',expected_version=1,function='adjust');result=validate_suggestion(suggestion(),snapshot)
    assert result['status']=='DRAFT_READY' and result['business_verified'] is False and result['normalized_oracle']['signature']['types']==types()
    assert u.get(d['id'],actor_id='alice')['status']=='DRAFT'
    confirmed=u.confirm(d['id'],**{**args,'examples_json':result['examples_json']},oracle_json=result['oracle_json'])
    assert confirmed['oracle_contract']==result['normalized_oracle'] and confirmed['oracle_json']==result['oracle_json']


@pytest.mark.parametrize('change',['tag','field','bool-int','version','model-types','reserved'])
def test_object_draft_rejects_untrusted_types_versions_and_inconsistent_values(tmp_path,change):
    u,d,args=prepare(tmp_path);snapshot=draft_snapshot(u,d['id'],actor_id='alice',expected_version=1,function='adjust');raw=json.loads(suggestion())
    if change=='tag':raw['examples'][0]['expected']['$type']='OtherState'
    elif change=='field':raw['examples'][0]['expected']['fields']['other']=0
    elif change=='bool-int':raw['examples'][0]['expected']['fields']['active']=1
    elif change=='version':raw['oracle']['version']=4
    elif change=='model-types':raw['oracle']['types']=types()
    else:raw['oracle']['excluded_inputs']=[[state(2),0]]
    assert validate_suggestion(json.dumps(raw),snapshot)['status']=='INVALID'


def test_object_confirm_shares_oracle5_reserved_set_and_preserves_raw_json(tmp_path):
    u,d,args=prepare(tmp_path);rule=raw_oracle();prop=raw_property();rel=raw_relation()
    for raw in (rule,prop,rel):raw['excluded_inputs']=[[state(2),0]]
    rawtext=json.dumps(rule,indent=2);kwargs=dict(oracle_json=rawtext,properties_json=json.dumps(prop),relations_json=json.dumps(rel))
    result=u.confirm(d['id'],**args,**kwargs);assert result['oracle_json']==rawtext and result['oracle_contract']['version']==5
    assert result['properties_contract']['version']==result['relations_contract']['version']==4
    assert u.confirm(d['id'],**args,**kwargs)==result


def test_object_confirm_oracle5_cannot_silently_differ_from_properties(tmp_path):
    u,d,args=prepare(tmp_path);rule=raw_oracle();rule['excluded_inputs']=[[state(2),0]]
    with pytest.raises(ValueError):u.confirm(d['id'],**args,oracle_json=json.dumps(rule),properties_json=json.dumps(raw_property()))
    assert u.get(d['id'],actor_id='alice')['status']=='DRAFT'


def test_object_provider_prepare_has_frozen_schema_and_zero_transport_calls(tmp_path,monkeypatch):
    from nexus.demo import rule_draft_provider as module
    monkeypatch.setattr(module,'model_config',lambda:dict(DEEPSEEK_API_KEY='fixture-key',DEEPSEEK_MODEL='fixture-model',DEEPSEEK_BASE_URL='https://fixture.invalid'))
    called=[]
    def transport(request):called.append(request);raise AssertionError('prepare must not send')
    u,d,args=prepare(tmp_path);snapshot=draft_snapshot(u,d['id'],actor_id='alice',expected_version=1,function='adjust');provider=RuleDraftProvider(transport=httpx.MockTransport(transport));body=provider.prepare(snapshot)
    text=body['messages'][0]['content'];assert 'version=5' in text and 'object_get' in text and 'object_with' in text and 'object_new' in text and 'signature.types' in text and 'excluded_inputs必须为[]' in text
    assert provider.origin=='HTTP_FIXTURE_NOT_LIVE' and not called and json.loads(body['messages'][1]['content'])['signature']['types']==types()


def test_object_draft_claimed_registry_mutation_invalidates_original_binding(tmp_path):
    u,d,args=prepare(tmp_path);snapshot=draft_snapshot(u,d['id'],actor_id='alice',expected_version=1,function='adjust');changed=deepcopy(snapshot)
    assert 'types' in changed['signature'];changed['signature']['types']['OrderState']['fields'][0]['type']='Bool'
    with pytest.raises(ValueError):validate_suggestion(suggestion(),changed)
