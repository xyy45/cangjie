"""Array confirmation and draft provenance; all model transports are fixtures."""
import io,json
import httpx
import pytest
from nexus.contracts import source_manifest
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.uploads.rule_contract import draft_snapshot,validate_suggestion
from tests.test_array_contracts import raw_oracle,raw_property,raw_relation,examples,signature,sequence_raw
from tests.test_upload_routes import page

SOURCE=b'''public func orderTotal(values: Array<Int64>, bonus: Int64): Int64 {
 var total = bonus
 for (value in values) { total = total + value }
 return total
}
'''


def prepare(root):
    uploads=UploadService(RunStore(root));draft=uploads.prepare('order.cj',SOURCE,'逐项累加订单项目并加附加费，不能漏项',actor_id='alice',request_key='k')
    return uploads,draft,dict(expected_version=1,function='orderTotal',examples_json=json.dumps(examples()),consent=True,actor_id='alice')


def test_array_confirm_freezes_raw_json_and_shared_exclusions(tmp_path):
    u,d,args=prepare(tmp_path);rule=raw_oracle();prop=raw_property();rel=raw_relation()
    for raw in (rule,prop,rel):raw['excluded_inputs']=[[[],2]]
    kwargs=dict(oracle_json=json.dumps(rule,indent=2),properties_json=json.dumps(prop),relations_json=json.dumps(rel))
    value=u.confirm(d['id'],**args,**kwargs);source=u.source(d['id'],actor_id='alice');before=source_manifest(source)
    assert value['oracle_contract']['version']==4 and value['properties_contract']['version']==value['relations_contract']['version']==3
    assert value['oracle_json']==kwargs['oracle_json'] and value['examples_json']==args['examples_json']
    assert u.confirm(d['id'],**args,**kwargs)==value and source_manifest(source)==before
    assert all(u.profile(d['id'])['context_visibility']['verification/'+n+'.json']=='VERIFICATION_ONLY' for n in ('oracle','properties','relations'))
    with pytest.raises(LookupError):u.get(d['id'],actor_id='bob')
    with pytest.raises(ValueError):u.confirm(d['id'],**{**args,'examples_json':json.dumps(examples()[::-1])},**kwargs)
    rule['domains']['values']['values'][0].append(99)
    assert u.get(d['id'],actor_id='alice')['oracle_contract']['domains']['values']['values'][0]==[]


def test_array_oracle4_reserved_set_cannot_silently_differ_from_property(tmp_path):
    u,d,args=prepare(tmp_path);rule=raw_oracle();rule['excluded_inputs']=[[[],2]]
    with pytest.raises(ValueError):u.confirm(d['id'],**args,oracle_json=json.dumps(rule),properties_json=json.dumps(raw_property()))
    assert u.get(d['id'],actor_id='alice')['status']=='DRAFT'

@pytest.mark.parametrize('change',['consent','version','expected','function','bool-element','oversize'])
def test_array_confirmation_rejects_invalid_or_stale_material(tmp_path,change):
    u,d,args=prepare(tmp_path)
    if change=='consent':args['consent']=False
    elif change=='version':args['expected_version']=2
    elif change=='function':args['function']='missing'
    else:
        items=examples()
        if change=='expected':items[0]['expected']=None
        elif change=='bool-element':items[0]['args'][0]=[True]
        else:items[0]['args'][0]=[0]*17
        args['examples_json']=json.dumps(items)
    with pytest.raises(ValueError):u.confirm(d['id'],**args,oracle_json=json.dumps(raw_oracle()))
    assert u.get(d['id'],actor_id='alice')['status']=='DRAFT'


def test_http_array_confirmation_keeps_actor_csrf_and_idempotence(tmp_path):
    app,alice,headers=page(tmp_path);response=alice.post('/api/uploads/repair',data=dict(file=(io.BytesIO(SOURCE),'order.cj'),goal='逐项计费',request_key='k'),headers=headers);assert response.status_code==201
    identity=response.json['id'];body=dict(expected_version=1,function='orderTotal',examples_json=json.dumps(examples()),oracle_json=json.dumps(raw_oracle()),properties_json=json.dumps(raw_property()),consent=True)
    assert alice.post('/api/uploads/repair/'+identity+'/confirm',json=body).status_code==403
    assert alice.post('/api/uploads/repair/'+identity+'/confirm',json=body,headers=headers).status_code==200
    assert alice.post('/api/uploads/repair/'+identity+'/confirm',json=body,headers=headers).status_code==200
    bob=app.test_client();bob.get('/');assert bob.get('/api/uploads/repair/'+identity).status_code==404
    assert alice.get('/demo/cases/'+identity).json['project_id']==identity


def suggestion(rule=None):return json.dumps(dict(schema_version=1,summary='数组自建草案',assumptions=[],questions=[],examples=examples(),oracle=raw_oracle() if rule is None else rule))


def test_array_draft_v4_remains_data_until_explicit_confirmation(tmp_path):
    u,d,args=prepare(tmp_path);before=source_manifest(tmp_path);snapshot=draft_snapshot(u,d['id'],actor_id='alice',expected_version=1,function='orderTotal')
    result=validate_suggestion(suggestion(),snapshot)
    assert result['status']=='DRAFT_READY' and result['normalized_oracle']['version']==4 and result['business_verified'] is False
    assert u.get(d['id'],actor_id='alice')['status']=='DRAFT' and source_manifest(tmp_path)==before
    value=u.confirm(d['id'],**{**args,'examples_json':result['examples_json']},oracle_json=result['oracle_json'])
    assert value['oracle_contract']==result['normalized_oracle']


def test_array_draft_cannot_invent_private_excluded_inputs(tmp_path):
    u,d,_=prepare(tmp_path);snapshot=draft_snapshot(u,d['id'],actor_id='alice',expected_version=1,function='orderTotal');rule=raw_oracle();rule['excluded_inputs']=[[[],2]]
    result=validate_suggestion(suggestion(rule),snapshot)
    assert result['status']=='EXAMPLES_READY' and result['code']=='RULE_INVALID'
    assert result['oracle_json'] is None and result['normalized_oracle'] is None
    assert result['suggestion']['oracle'] is None


def test_array_schema_and_prompt_match_server_v4_and_readonly_subset(tmp_path,monkeypatch):
    from nexus.demo.rule_draft_provider import RuleDraftProvider,response_schema
    for key,value in dict(DEEPSEEK_API_KEY='test-only',DEEPSEEK_BASE_URL='https://model.example',DEEPSEEK_MODEL='test-model').items():monkeypatch.setenv(key,value)
    u,d,_=prepare(tmp_path);snapshot=draft_snapshot(u,d['id'],actor_id='alice',expected_version=1,function='orderTotal')
    def deny(request):raise AssertionError('prepare must not send model request')
    body=RuleDraftProvider(transport=httpx.MockTransport(deny)).prepare(snapshot);text=body['messages'][0]['content']
    assert 'version=4' in text and 'Array<Int64>' in text and '16' in text and 'array_sum' in text and 'array_replace' in text and '只读' in text
    schema=response_schema(signature());items=next(v for v in schema['properties']['examples']['anyOf'] if v.get('type')=='array')['items'];param=items['properties']['args']['prefixItems'][0]
    assert param['type']=='array' and param['maxItems']==16 and param['items']['type']=='integer' and param['items']['minimum']==-(1<<63)
    s=signature();s['return_type']='Array<Int64>';items=next(v for v in response_schema(s)['properties']['examples']['anyOf'] if v.get('type')=='array')['items']
    assert items['properties']['expected']['type']=='array' and items['properties']['expected']['maxItems']==16
