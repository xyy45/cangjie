"""Actor-scoped local route integration, model transport fixture only."""
import io,json

import pytest

from tests.test_upload_routes import page
from tests.test_rule_drafts import SOURCE,FixtureDraftProvider


@pytest.fixture
def web(tmp_path):
    app,alice,headers=page(tmp_path);app.config['RUN_RULE_DRAFTS']=False
    assert 'rule_draft_service' in app.extensions,'draft routes/service are not registered'
    service=app.extensions['rule_draft_service'];service.provider_factory=FixtureDraftProvider
    FixtureDraftProvider.calls=[];FixtureDraftProvider.inspect_before_send=None
    uploaded=alice.post('/api/uploads/repair',data=dict(file=(io.BytesIO(SOURCE),'fee.cj'),goal='quantity与price均在0..1000，返回二者乘积',request_key='upload'),headers=headers).json
    return app,alice,headers,uploaded,service


def job_body(**extra):return dict(expected_version=1,function='fee',request_key='generate',consent=True,**extra)


def test_create_poll_apply_stays_private_and_does_not_confirm_upload(web):
    app,alice,headers,uploaded,service=web;base='/api/uploads/repair/'+uploaded['id']
    assert alice.post(base+'/rule-drafts',json=job_body()).status_code==403
    start=alice.post(base+'/rule-drafts',json=job_body(),headers=headers)
    assert start.status_code==202,start.json
    job=start.json;assert job['call_state']=='CREATED' and FixtureDraftProvider.calls==[]
    assert alice.get(base+'/rule-drafts/'+job['id']).json['call_state']=='CREATED'
    service.run(job['id'])
    done=alice.get(base+'/rule-drafts/'+job['id']);assert done.json['result']['status']=='DRAFT_READY'
    preview=alice.post(base+'/rule-drafts/'+job['id']+'/apply-preview',json=dict(expected_version=1,function='fee'),headers=headers)
    assert preview.status_code==200 and json.loads(preview.json['examples_json'])[0]['expected']==300
    assert alice.get(base).json['status']=='DRAFT'
    bob=app.test_client();bob.get('/')
    with bob.session_transaction() as s:foreign={'Origin':'http://localhost','X-CSRF-Token':s['csrf']}
    assert bob.get(base+'/rule-drafts/'+job['id']).status_code==404
    assert bob.post(base+'/rule-drafts',json=job_body(),headers=foreign).status_code==404
    assert bob.post(base+'/rule-drafts/'+job['id']+'/apply-preview',json=dict(expected_version=1,function='fee'),headers=foreign).status_code==404
    assert len(FixtureDraftProvider.calls)==1


@pytest.mark.parametrize('extra',[dict(consent=False),dict(consent=1),dict(expected_version=True),dict(actor_id='bob'),dict(source_sha256='forged'),dict(model='other')])
def test_invalid_input_never_dispatches_model(web,extra):
    _,alice,headers,uploaded,_=web;body=job_body();body.update(extra)
    r=alice.post('/api/uploads/repair/'+uploaded['id']+'/rule-drafts',json=body,headers=headers)
    assert r.status_code==400 and FixtureDraftProvider.calls==[]


def test_route_checks_job_upload_binding_and_known_conflict(web):
    _,alice,headers,uploaded,service=web;base='/api/uploads/repair/'+uploaded['id']
    job=alice.post(base+'/rule-drafts',json=job_body(),headers=headers).json
    other=service.uploads.prepare('other.cj',SOURCE,'another goal',actor_id=service._row(job['id'])[0],request_key='other')
    assert alice.get('/api/uploads/repair/'+other['id']+'/rule-drafts/'+job['id']).status_code==404
    repeat=job_body();repeat['request_key']='new-key'
    assert alice.post(base+'/rule-drafts',json=repeat,headers=headers).status_code==409


def test_main_reconciles_pending_draft_requests_without_network(tmp_path,monkeypatch):
    import nexus.demo.app as demo
    from nexus.store import RunStore
    from nexus.uploads.rule_drafts import RuleDraftService
    store=RunStore(tmp_path/'.runtime/demo-workbench');service=RuleDraftService(store,provider_factory=FixtureDraftProvider)
    upload=service.uploads.prepare('fee.cj',SOURCE,'multiplication',actor_id='alice',request_key='upload')
    job=service.create(upload['id'],actor_id='alice',**job_body())
    with store.connect() as db:db.execute("UPDATE rule_draft_requests SET call_state='STARTED' WHERE id=?",(job['id'],))
    monkeypatch.setattr(demo,'ROOT',tmp_path);monkeypatch.setattr('sys.argv',['demo','--provider','rule'])
    captured=[]
    monkeypatch.setattr('flask.Flask.run',lambda app,**kwargs:captured.append(app.extensions['rule_draft_service'].get(job['id'],actor_id='alice')['call_state']))
    demo.main()
    assert captured==['IN_DOUBT']


def test_known_model_error_retains_redacted_original_and_unknowns_are_distinct(web,monkeypatch):
    import httpx
    from nexus.demo.rule_draft_provider import RuleDraftProvider
    app,alice,headers,uploaded,service=web
    for name,value in dict(DEEPSEEK_API_KEY='draft-secret',DEEPSEEK_BASE_URL='https://model.example',DEEPSEEK_MODEL='fixture').items():monkeypatch.setenv(name,value)
    def reply(request):return httpx.Response(401,json={'error':{'message':'credential draft-secret rejected'}})
    service.provider_factory=lambda:RuleDraftProvider(transport=httpx.MockTransport(reply))
    job=alice.post('/api/uploads/repair/'+uploaded['id']+'/rule-drafts',json=job_body(),headers=headers).json
    service.run(job['id']);state=alice.get('/api/uploads/repair/'+uploaded['id']+'/rule-drafts/'+job['id']).json
    assert state['call_state']=='FAILED' and state['error_code']=='MODEL_HTTP_401' and state['response_sha256']
    assert all('draft-secret' not in p.read_text() for p in service.directory(job['id']).glob('*.json'))


def test_missing_configuration_returns_unavailable_without_creating_a_job(web,monkeypatch):
    _,alice,headers,uploaded,service=web;service.provider_factory=None
    monkeypatch.setattr('nexus.demo.rule_draft_provider.model_config',lambda:{k:'' for k in ('DEEPSEEK_API_KEY','DEEPSEEK_BASE_URL','DEEPSEEK_MODEL')})
    result=alice.post('/api/uploads/repair/'+uploaded['id']+'/rule-drafts',json=job_body(),headers=headers)
    assert result.status_code==503
    with service.store.connect() as db:assert db.execute('SELECT count(*) FROM rule_draft_requests').fetchone()[0]==0


def test_draft_history_is_read_only_and_scoped_to_owned_upload(web):
    app,alice,headers,uploaded,service=web;base='/api/uploads/repair/'+uploaded['id']
    job=alice.post(base+'/rule-drafts',json=job_body(),headers=headers).json
    listed=alice.get(base+'/rule-drafts')
    assert listed.status_code==200 and listed.json['jobs'][0]['id']==job['id']
    assert listed.json['jobs'][0]['call_state']=='CREATED' and FixtureDraftProvider.calls==[]
    bob=app.test_client();bob.get('/')
    assert bob.get(base+'/rule-drafts').status_code==404


def test_final_confirm_freezes_actual_preview_and_retains_generated_source(web):
    _,alice,headers,uploaded,service=web;base='/api/uploads/repair/'+uploaded['id']
    job=alice.post(base+'/rule-drafts',json=job_body(),headers=headers).json;service.run(job['id'])
    preview=alice.post(base+'/rule-drafts/'+job['id']+'/apply-preview',json=dict(expected_version=1,function='fee'),headers=headers).json
    result=alice.post(base+'/confirm',json=dict(expected_version=1,function='fee',examples_json=preview['examples_json'],oracle_json=preview['oracle_json'],rule_draft_ref=preview['rule_draft_ref'],consent=True),headers=headers)
    assert result.status_code==200,result.json
    assert result.json['status']=='CONFIRMED' and result.json['rule_draft_provenance']['rule_draft_id']==job['id']
    assert alice.post(base+'/rule-drafts',json=job_body(),headers=headers).status_code==400
    assert len(FixtureDraftProvider.calls)==1


def test_bounded_large_upstream_metadata_keeps_known_success_and_original(web,monkeypatch):
    import httpx
    from nexus.demo.rule_draft_provider import RuleDraftProvider
    from tests.test_rule_drafts import suggestion
    from nexus.uploads.rule_contract import MAX_RESPONSE
    app,alice,headers,uploaded,service=web
    for key,value in dict(DEEPSEEK_API_KEY='size-test-secret',DEEPSEEK_BASE_URL='https://model.example',DEEPSEEK_MODEL='fixture').items():monkeypatch.setenv(key,value)
    payload=dict(model='fixture',usage=dict(prompt_tokens=50,completion_tokens=20,total_tokens=70),choices=[dict(finish_reason='stop',message={'content':json.dumps(suggestion())})],metadata='')
    payload['metadata']='x'*(MAX_RESPONSE-len(json.dumps(payload).encode())-4)
    raw=json.dumps(payload).encode();assert len(raw)<MAX_RESPONSE
    service.provider_factory=lambda:RuleDraftProvider(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=raw)))
    base='/api/uploads/repair/'+uploaded['id'];job=alice.post(base+'/rule-drafts',json=job_body(),headers=headers).json
    service.run(job['id']);state=alice.get(base+'/rule-drafts/'+job['id']).json
    assert state['call_state']=='SUCCEEDED' and state['result']['status']=='DRAFT_READY'
    assert state['response_sha256'] and len(json.dumps(state).encode())<65536


@pytest.mark.parametrize('invalid_rule',[True,False])
def test_fill_examples_only_and_confirm_without_a_rule(web,invalid_rule):
    from tests.test_rule_drafts import EXAMPLES,suggestion
    app,alice,headers,uploaded,service=web;base='/api/uploads/repair/'+uploaded['id']
    class Provider(FixtureDraftProvider):
        async def complete(self,body):
            response=await super().complete(body)
            raw=suggestion()
            if invalid_rule:raw['oracle']['domains']['quantity']['max']=1
            response['raw_text']=json.dumps(raw)
            return response
    service.provider_factory=Provider
    job=alice.post(base+'/rule-drafts',json=job_body(),headers=headers).json
    service.run(job['id'])
    done=alice.get(base+'/rule-drafts/'+job['id']).json
    assert done['result']['status']==('EXAMPLES_READY' if invalid_rule else 'DRAFT_READY')
    preview_url=base+'/rule-drafts/'+job['id']+'/apply-preview'
    response=alice.post(preview_url,json=dict(expected_version=1,function='fee',examples_only=True),headers=headers)
    assert response.status_code==200,response.json
    preview=response.json
    assert json.loads(preview['examples_json'])==EXAMPLES
    assert preview['oracle_json'] is None and preview['rule_draft_ref']['examples_only'] is True
    response=alice.post(base+'/confirm',json=dict(expected_version=1,function='fee',examples_json=preview['examples_json'],rule_draft_ref=preview['rule_draft_ref'],consent=True),headers=headers)
    assert response.status_code==200,response.json
    assert response.json['examples']==EXAMPLES and not response.json.get('oracle_contract')
    assert response.json['rule_draft_provenance']['edited_by_user'] is False
