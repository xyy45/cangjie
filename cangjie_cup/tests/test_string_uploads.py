"""String confirmation/provenance tests; no SDK or model requests."""
from copy import deepcopy
import io,json
import httpx
import pytest
from nexus.contracts import digest,source_manifest
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.uploads.rule_contract import draft_snapshot,validate_suggestion
from tests.test_string_contracts import raw_oracle,raw_property,raw_relation,examples
from tests.test_upload_routes import page

SOURCE=(chr(10).join(['public func ticket(code: String, qty: Int64): String {','if (qty > 0) { return code + ":Y" }','return code + ":N"','}',''])).encode()


def prepare(root):
    uploads=UploadService(RunStore(root));draft=uploads.prepare('ticket.cj',SOURCE,'返回编码加数量类别，保留空串和Unicode',actor_id='alice',request_key='k')
    args=dict(expected_version=1,function='ticket',examples_json=json.dumps(examples(),ensure_ascii=False),consent=True,actor_id='alice')
    return uploads,draft,args


def test_string_confirm_freezes_raw_json_and_shared_reserved_inputs(tmp_path):
    u,d,args=prepare(tmp_path);rule=raw_oracle();prop=raw_property();rel=raw_relation()
    for raw in (rule,prop,rel):raw['excluded_inputs']=[['a',2]]
    kwargs=dict(oracle_json=json.dumps(rule,ensure_ascii=False,indent=2),properties_json=json.dumps(prop),relations_json=json.dumps(rel))
    value=u.confirm(d['id'],**args,**kwargs);source=u.source(d['id'],actor_id='alice');before=source_manifest(source)
    assert value['oracle_contract']['version']==3 and value['properties_contract']['version']==value['relations_contract']['version']==2
    assert value['oracle_json']==kwargs['oracle_json'] and value['examples_json']==args['examples_json']
    assert u.confirm(d['id'],**args,**kwargs)==value and source_manifest(source)==before
    profile=u.profile(d['id']);assert all(profile['context_visibility']['verification/'+name+'.json']=='VERIFICATION_ONLY' for name in ('oracle','properties','relations'))
    with pytest.raises(LookupError):u.get(d['id'],actor_id='bob')
    with pytest.raises(ValueError):u.confirm(d['id'],**{**args,'examples_json':json.dumps(examples()[::-1])},**kwargs)


def test_string_oracle_reserved_set_cannot_silently_differ_from_property(tmp_path):
    u,d,args=prepare(tmp_path);rule=raw_oracle();rule['excluded_inputs']=[['a',2]]
    with pytest.raises(ValueError):u.confirm(d['id'],**args,oracle_json=json.dumps(rule),properties_json=json.dumps(raw_property()))
    assert u.get(d['id'],actor_id='alice')['status']=='DRAFT'


@pytest.mark.parametrize('change',['consent','version','expected','source-interface'])
def test_string_confirmation_rejects_stale_or_invalid_inputs(tmp_path,change):
    u,d,args=prepare(tmp_path)
    if change=='consent':args['consent']=False
    elif change=='version':args['expected_version']=2
    elif change=='expected':args['examples_json']=json.dumps([{**examples()[0],'expected':None},examples()[1]])
    else:args['function']='missing'
    with pytest.raises(ValueError):u.confirm(d['id'],**args,oracle_json=json.dumps(raw_oracle()))
    assert u.get(d['id'],actor_id='alice')['status']=='DRAFT'


def test_http_string_confirm_keeps_csrf_actor_and_reconfirmation_boundaries(tmp_path):
    app,alice,headers=page(tmp_path)
    response=alice.post('/api/uploads/repair',data=dict(file=(io.BytesIO(SOURCE),'ticket.cj'),goal='String票据',request_key='k'),headers=headers);assert response.status_code==201
    identity=response.json['id'];rule=raw_oracle();prop=raw_property();rule['excluded_inputs']=prop['excluded_inputs']=[['a',2]]
    body=dict(expected_version=1,function='ticket',examples_json=json.dumps(examples()),oracle_json=json.dumps(rule),properties_json=json.dumps(prop),consent=True)
    assert alice.post('/api/uploads/repair/'+identity+'/confirm',json=body).status_code==403
    assert alice.post('/api/uploads/repair/'+identity+'/confirm',json=body,headers=headers).status_code==200
    assert alice.post('/api/uploads/repair/'+identity+'/confirm',json=body,headers=headers).status_code==200
    bob=app.test_client();bob.get('/')
    assert bob.get('/api/uploads/repair/'+identity).status_code==404
    assert alice.get('/demo/cases/'+identity).json['project_id']==identity


def suggestion(rule=None):
    return json.dumps(dict(schema_version=1,summary='String自建草案',assumptions=[],questions=[],examples=examples(),oracle=raw_oracle() if rule is None else rule),ensure_ascii=False)


def test_string_draft_v3_is_data_until_explicit_user_confirmation(tmp_path):
    u,d,args=prepare(tmp_path);before=source_manifest(tmp_path)
    snapshot=draft_snapshot(u,d['id'],actor_id='alice',expected_version=1,function='ticket')
    result=validate_suggestion(suggestion(),snapshot)
    assert result['status']=='DRAFT_READY' and result['normalized_oracle']['version']==3 and result['business_verified'] is False
    assert u.get(d['id'],actor_id='alice')['status']=='DRAFT' and source_manifest(tmp_path)==before
    value=u.confirm(d['id'],**{**args,'examples_json':result['examples_json']},oracle_json=result['oracle_json'])
    assert value['oracle_contract']==result['normalized_oracle']


def test_model_string_draft_cannot_invent_private_reserved_acceptance_inputs(tmp_path):
    u,d,_=prepare(tmp_path);snapshot=draft_snapshot(u,d['id'],actor_id='alice',expected_version=1,function='ticket');rule=raw_oracle();rule['excluded_inputs']=[['a',2]]
    result=validate_suggestion(suggestion(rule),snapshot)
    assert result['status']=='EXAMPLES_READY' and result['code']=='RULE_INVALID'
    assert result['oracle_json'] is None and result['normalized_oracle'] is None
    assert result['suggestion']['oracle'] is None


def test_string_draft_schema_and_prompt_match_server_v3_rules(tmp_path,monkeypatch):
    from nexus.demo.rule_draft_provider import RuleDraftProvider,response_schema
    from tests.test_string_contracts import signature
    for key,value in dict(DEEPSEEK_API_KEY='test-only',DEEPSEEK_BASE_URL='https://model.example',DEEPSEEK_MODEL='test-model').items():monkeypatch.setenv(key,value)
    u,d,_=prepare(tmp_path);snapshot=draft_snapshot(u,d['id'],actor_id='alice',expected_version=1,function='ticket')
    def no_call(request):raise AssertionError('prepare must not send any request')
    provider=RuleDraftProvider(transport=httpx.MockTransport(no_call));prepared=provider.prepare(snapshot)
    text=prepared['messages'][0]['content']
    assert 'version=3' in text and 'byte_len' in text and 'rune_len' in text and '256' in text and 'excluded_inputs' in text
    schema=response_schema(signature());items=next(item for item in schema['properties']['examples']['anyOf'] if item.get('type')=='array')['items']
    assert items['properties']['expected']['type']=='string' and items['properties']['args']['prefixItems'][0]['type']=='string'
