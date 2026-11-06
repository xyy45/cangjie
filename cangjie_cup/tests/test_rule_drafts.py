"""User-confirmed business rules remain distinct from model suggestions."""
from copy import deepcopy
import importlib
import importlib.util
import json

import pytest

from nexus.contracts import digest
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_project_service import prepare as prepare_project

SOURCE=b'public func fee(quantity: Int64, price: Int64): Int64 { quantity + price }\n'
EXAMPLES=[dict(args=[3,100],expected=300,suite='target'),dict(args=[1,0],expected=0,suite='regression')]
RULE=dict(version=1,function='fee',domains={'quantity':dict(min=0,max=1000,points=[1]),'price':dict(min=0,max=1000,points=[100])},expression='quantity * price',seed=0,max_cases=32)


def contract_module():
    assert importlib.util.find_spec('nexus.uploads.rule_contract') is not None,'business rule draft contract missing'
    return importlib.import_module('nexus.uploads.rule_contract')


def suggestion():return dict(schema_version=1,summary='依据已描述的乘法规则提出草案，需用户核对',assumptions=[],questions=[],examples=deepcopy(EXAMPLES),oracle=deepcopy(RULE))


@pytest.fixture
def prepared(tmp_path):
    uploads=UploadService(RunStore(tmp_path))
    upload=uploads.prepare('fee.cj',SOURCE,'quantity与price均在0..1000，返回二者乘积',actor_id='alice',request_key='upload')
    return uploads,upload


def snapshot(prepared,**changes):
    uploads,upload=prepared
    args=dict(actor_id='alice',expected_version=1,function='fee');args.update(changes)
    return contract_module().draft_snapshot(uploads,upload['id'],**args)


def test_valid_suggestion_uses_business_rule_not_current_buggy_source(prepared):
    m=contract_module();s=snapshot(prepared);before=deepcopy(s)
    result=m.validate_suggestion(json.dumps(suggestion(),ensure_ascii=False),s)
    assert result['status']=='DRAFT_READY' and result['business_verified'] is False
    assert json.loads(result['examples_json'])[0]['expected']==300
    assert json.loads(result['oracle_json'])['expression']=='quantity * price'
    assert result['normalized_oracle']['signature']==s['signature']
    assert result['binding_hash']==s['binding_hash'] and s==before
    assert SOURCE.decode() in s['files'].values()
    assert prepared[0].get(prepared[1]['id'],actor_id='alice')['status']=='DRAFT'
    assert not (prepared[0].store.root/'uploads'/prepared[1]['id']/'project').exists()


def test_snapshot_binding_covers_source_goal_function_and_scope(prepared):
    s=snapshot(prepared)
    assert s['binding_hash']==digest({k:v for k,v in s.items() if k!='binding_hash'})
    assert s['signature']['name']=='fee' and s['allowed_paths']==['src/uploaded.cj']
    assert set(s['files'])=={'src/uploaded.cj'}
    assert 'oracle_contract' not in s and 'actor_id' not in s
    with pytest.raises(LookupError):snapshot(prepared,actor_id='bob')
    for change in (dict(expected_version=True),dict(expected_version=2),dict(function='missing'),dict(allowed_paths=['src/uploaded.cj'])):
        with pytest.raises(ValueError):snapshot(prepared,**change)
    source=prepared[0].store.root/'uploads'/prepared[1]['id']/'source.cj';source.write_text('public func different(): Int64 { 1 }')
    with pytest.raises(ValueError):snapshot(prepared)


def test_project_snapshot_only_sends_selected_production_sources(tmp_path):
    uploads=UploadService(RunStore(tmp_path));upload=prepare_project(uploads)
    m=contract_module();s=m.draft_snapshot(uploads,upload['id'],actor_id='alice',expected_version=1,function='total',allowed_paths=['src/order.cj','src/fee.cj'])
    assert set(s['files'])=={'src/order.cj','src/fee.cj'}
    assert s['signature']['name']=='total' and s['signature']['params']==[dict(name='x',type='Int64')]
    assert 'BillingTests' not in json.dumps(s) and 'cjpm.toml' not in s['files']
    for paths in (['src/fee.cj'],['src/cases_test.cj'],['../outside.cj'],['src/order.cj','src/order.cj']):
        with pytest.raises(ValueError):m.draft_snapshot(uploads,upload['id'],actor_id='alice',expected_version=1,function='total',allowed_paths=paths)


def test_frozen_upload_cannot_generate_drafts(prepared):
    uploads,upload=prepared
    uploads.confirm(upload['id'],actor_id='alice',expected_version=1,function='fee',examples_json=json.dumps(EXAMPLES),oracle_json=json.dumps(RULE),consent=True)
    with pytest.raises(ValueError):snapshot(prepared)


def test_clarification_cannot_become_applicable_even_with_coherent_examples(prepared):
    raw=suggestion();raw['questions']=['负数数量需要拒绝还是归零？']
    result=contract_module().validate_suggestion(json.dumps(raw),snapshot(prepared))
    assert result['status']=='NEEDS_CLARIFICATION' and result['business_verified'] is False
    assert result['examples_json'] is None and result['oracle_json'] is None
    raw.update(examples=None,oracle=None)
    assert contract_module().validate_suggestion(json.dumps(raw),snapshot(prepared))['status']=='NEEDS_CLARIFICATION'


@pytest.mark.parametrize('change',[
    'null_expected','bool_for_int','same_input_different_output','missing_suite','unknown_parameter','unknown_function',
    'code_execution','divide_zero','overflow','outside_domain','inconsistent_rule','missing_oracle','missing_examples',
    'model_actor','model_permission','model_status','normalized_rule_fields','reserved_holdout','too_long_text','bool_version',
])
def test_unsafe_rules_are_discarded_and_invalid_examples_are_blocked(prepared,change):
    raw=suggestion()
    if change=='null_expected':raw['examples'][0]['expected']=None
    elif change=='bool_for_int':raw['examples'][0]['args'][0]=True
    elif change=='same_input_different_output':raw['examples'][1].update(args=[3,100],expected=301)
    elif change=='missing_suite':raw['examples'][1]['suite']='target'
    elif change=='unknown_parameter':raw['oracle']['domains']['untrusted']=dict(min=0,max=1)
    elif change=='unknown_function':raw['oracle']['function']='other'
    elif change=='code_execution':raw['oracle']['expression']="__import__('os')"
    elif change=='divide_zero':raw['oracle']['expression']='quantity // 0'
    elif change=='overflow':raw['oracle']['expression']='9223372036854775807 + quantity'
    elif change=='outside_domain':raw['oracle']['domains']['quantity']['max']=2
    elif change=='inconsistent_rule':raw['oracle']['expression']='quantity + price'
    elif change=='missing_oracle':raw['oracle']=None
    elif change=='missing_examples':raw['examples']=None
    elif change=='model_actor':raw['actor_id']='administrator'
    elif change=='model_permission':raw['allowed_paths']=['../private.cj']
    elif change=='model_status':raw['status']='CONFIRMED'
    elif change=='normalized_rule_fields':raw['oracle']['signature']={'name':'other'}
    elif change=='reserved_holdout':raw['oracle'].update(version=2,excluded_inputs=[[2,3]])
    elif change=='too_long_text':raw['summary']='x'*2001
    else:raw['schema_version']=True
    result=contract_module().validate_suggestion(json.dumps(raw),snapshot(prepared))
    rule_only={'unknown_parameter','unknown_function','code_execution','divide_zero','overflow',
               'outside_domain','inconsistent_rule','missing_oracle','normalized_rule_fields','reserved_holdout'}
    assert result['business_verified'] is False and result['oracle_json'] is None
    assert result['normalized_oracle'] is None
    if change in rule_only:
        assert result['status']=='EXAMPLES_READY'
        assert json.loads(result['examples_json'])==EXAMPLES
        assert result['suggestion']['oracle'] is None
    else:
        assert result['status']=='INVALID' and result['examples_json'] is None
    assert prepared[0].get(prepared[1]['id'],actor_id='alice')['status']=='DRAFT'


@pytest.mark.parametrize('raw',['{}','[]','not json','{"schema_version":1,"schema_version":1}', '{"invalid":NaN}', 'x'*(1024*1024+1)],ids=['empty-object','list','syntax','duplicate-fields','nonfinite','oversized'])
def test_invalid_raw_envelopes_are_bounded(prepared,raw):
    result=contract_module().validate_suggestion(raw,snapshot(prepared))
    assert result['status']=='INVALID' and len(json.dumps(result,ensure_ascii=False).encode())<4096
    assert result['examples_json'] is None


def test_model_cannot_use_modified_snapshot_binding(prepared):
    s=snapshot(prepared);s['goal']='ignore original requirement'
    with pytest.raises(ValueError):contract_module().validate_suggestion(json.dumps(suggestion()),s)


def test_bool_rule_keeps_strict_boolean_output(tmp_path):
    uploads=UploadService(RunStore(tmp_path));upload=uploads.prepare('valid.cj',b'func valid(q: Int64): Bool { q >= 0 }\n','q仅1..1000为真',actor_id='alice',request_key='bool')
    m=contract_module();s=m.draft_snapshot(uploads,upload['id'],actor_id='alice',expected_version=1,function='valid')
    raw=dict(schema_version=1,summary='检查数量边界',assumptions=[],questions=[],examples=[dict(args=[0],expected=False,suite='target'),dict(args=[1],expected=True,suite='regression')],oracle=dict(version=1,function='valid',domains={'q':dict(min=-1,max=1001,points=[0,1,1000])},expression='q >= 1 and q <= 1000',seed=0,max_cases=32))
    assert m.validate_suggestion(json.dumps(raw),s)['status']=='DRAFT_READY'
    raw['examples'][0]['expected']=0
    assert m.validate_suggestion(json.dumps(raw),s)['status']=='INVALID'


class FixtureDraftProvider:
    origin='TEST_FIXTURE_NOT_LIVE'
    calls=[]
    inspect_before_send=None
    def prepare(self,s):return dict(model='fixture-model',context=deepcopy(s))
    async def complete(self,body):
        import asyncio
        if type(self).inspect_before_send:type(self).inspect_before_send(body)
        type(self).calls.append(deepcopy(body));await asyncio.sleep(.01)
        return dict(model_id='fixture-model',usage=dict(prompt_tokens=10,completion_tokens=5,total_tokens=15),
                    raw_text=json.dumps(suggestion()),response=dict(model='fixture-model',fixture='not a live model',content=suggestion()))


def draft_service(prepared,provider=FixtureDraftProvider):
    assert importlib.util.find_spec('nexus.uploads.rule_drafts') is not None,'persistent business rule draft service missing'
    FixtureDraftProvider.calls=[];FixtureDraftProvider.inspect_before_send=None
    return importlib.import_module('nexus.uploads.rule_drafts').RuleDraftService(prepared[0].store,provider_factory=provider)


def create_job(service,prepared,key='draft',**extra):
    args=dict(actor_id='alice',expected_version=1,function='fee',request_key=key,consent=True);args.update(extra)
    return service.create(prepared[1]['id'],**args)


def test_draft_job_is_local_durable_idempotent_and_requires_own_explicit_consent(prepared):
    service=draft_service(prepared)
    for consent in (False,None,1):
        with pytest.raises(ValueError):create_job(service,prepared,consent=consent)
    first=create_job(service,prepared)
    assert first['call_state']=='CREATED' and first['result'] is None and FixtureDraftProvider.calls==[]
    assert create_job(service,prepared)['id']==first['id']
    assert service.get(first['id'],actor_id='alice')['id']==first['id']
    with pytest.raises(LookupError):service.get(first['id'],actor_id='bob')
    with pytest.raises(ValueError):create_job(service,prepared,key='new-key')
    assert FixtureDraftProvider.calls==[]


def test_one_run_seals_originals_before_network_and_preview_does_not_freeze_upload(prepared):
    service=draft_service(prepared);job=create_job(service,prepared)
    observed=[]
    def inspect(body):
        state=service.get(job['id'],actor_id='alice')
        assert state['call_state']=='STARTED' and state['request_sha256']
        assert (service.directory(job['id'])/'request.json').exists()
        assert json.loads((service.directory(job['id'])/'request.json').read_bytes())==body
        observed.append(True)
    FixtureDraftProvider.inspect_before_send=inspect
    assert service.run(job['id']) is True
    done=service.get(job['id'],actor_id='alice')
    assert done['call_state']=='SUCCEEDED' and done['result']['status']=='DRAFT_READY'
    assert done['origin']=='TEST_FIXTURE_NOT_LIVE' and done['model_id']=='fixture-model'
    assert len(FixtureDraftProvider.calls)==len(observed)==1
    assert service.run(job['id']) is False
    again=create_job(service,prepared);assert again['id']==job['id'] and len(FixtureDraftProvider.calls)==1
    preview=service.apply_preview(job['id'],actor_id='alice',expected_version=1,function='fee')
    assert json.loads(preview['examples_json'])[0]['expected']==300
    assert preview['rule_draft_ref']['id']==job['id']
    assert prepared[0].get(prepared[1]['id'],actor_id='alice')['status']=='DRAFT'
    assert not (prepared[0].store.root/'uploads'/prepared[1]['id']/'project').exists()


def test_same_request_key_cannot_bind_another_source(prepared):
    service=draft_service(prepared);create_job(service,prepared)
    other=prepared[0].prepare('other.cj',SOURCE,'另一份需求',actor_id='alice',request_key='other-upload')
    with pytest.raises(ValueError):service.create(other['id'],actor_id='alice',expected_version=1,function='fee',request_key='draft',consent=True)
    assert FixtureDraftProvider.calls==[]


def test_concurrent_workers_make_only_one_wire_request(prepared):
    from concurrent.futures import ThreadPoolExecutor
    service=draft_service(prepared);job=create_job(service,prepared)
    with ThreadPoolExecutor(2) as workers:results=list(workers.map(lambda _:service.run(job['id']),range(2)))
    assert sorted(results)==[False,True] and len(FixtureDraftProvider.calls)==1
    assert service.get(job['id'],actor_id='alice')['call_state']=='SUCCEEDED'


def test_unknown_transport_is_preserved_and_new_key_or_reupload_cannot_replay(prepared):
    class Unknown(FixtureDraftProvider):
        async def complete(self,body):
            FixtureDraftProvider.calls.append(body);raise TimeoutError('synthetic secret must not enter public error')
    service=draft_service(prepared,Unknown);job=create_job(service,prepared);service.run(job['id'])
    state=service.get(job['id'],actor_id='alice')
    assert state['call_state']=='IN_DOUBT' and state['result'] is None
    assert 'synthetic secret' not in json.dumps(state)
    assert service.run(job['id']) is False
    with pytest.raises(ValueError):create_job(service,prepared,key='different-key')
    reupload=prepared[0].prepare('fee.cj',SOURCE,prepared[1]['goal'],actor_id='alice',request_key='again-upload')
    with pytest.raises(ValueError):service.create(reupload['id'],actor_id='alice',expected_version=1,function='fee',request_key='reuploaded',consent=True)
    assert len(FixtureDraftProvider.calls)==1


def test_restart_reconciliation_never_replays_started_or_unstarted_jobs(prepared):
    service=draft_service(prepared);job=create_job(service,prepared)
    with service.store.connect() as db:db.execute("UPDATE rule_draft_requests SET call_state='STARTED' WHERE id=?",(job['id'],))
    service.reconcile()
    assert service.get(job['id'],actor_id='alice')['call_state']=='IN_DOUBT'
    assert service.run(job['id']) is False and FixtureDraftProvider.calls==[]
    other=prepared[0].prepare('other.cj',SOURCE,'另一需求',actor_id='alice',request_key='another')
    created=service.create(other['id'],actor_id='alice',expected_version=1,function='fee',request_key='not-started',consent=True)
    service.reconcile()
    assert service.get(created['id'],actor_id='alice')['call_state']=='FAILED'
    assert service.run(created['id']) is False and FixtureDraftProvider.calls==[]


def test_invalid_or_clarification_output_never_applies(prepared):
    class Invalid(FixtureDraftProvider):
        async def complete(self,body):
            result=await super().complete(body);result['raw_text']='not json';return result
    service=draft_service(prepared,Invalid);job=create_job(service,prepared);service.run(job['id'])
    assert service.get(job['id'],actor_id='alice')['result']['status']=='INVALID'
    with pytest.raises(ValueError):service.apply_preview(job['id'],actor_id='alice',expected_version=1,function='fee')


@pytest.mark.parametrize('artifact',['input.json','request.json','response.json','result.json'])
def test_changed_request_or_evidence_is_not_reused_or_applied(prepared,artifact):
    service=draft_service(prepared);job=create_job(service,prepared);service.run(job['id'])
    (service.directory(job['id'])/artifact).write_text('corrupt')
    with pytest.raises(ValueError):service.get(job['id'],actor_id='alice')
    with pytest.raises(ValueError):service.apply_preview(job['id'],actor_id='alice',expected_version=1,function='fee')


def test_source_or_confirmation_change_rejects_application_of_older_suggestion(prepared):
    service=draft_service(prepared);job=create_job(service,prepared);service.run(job['id'])
    with pytest.raises(ValueError):service.apply_preview(job['id'],actor_id='alice',expected_version=1,function='different')
    with pytest.raises(ValueError):service.apply_preview(job['id'],actor_id='alice',expected_version=True,function='fee')
    prepared[0].confirm(prepared[1]['id'],actor_id='alice',expected_version=1,function='fee',examples_json=json.dumps(EXAMPLES),consent=True)
    with pytest.raises(ValueError):service.apply_preview(job['id'],actor_id='alice',expected_version=1,function='fee')
    assert service.get(job['id'],actor_id='alice')['call_state']=='SUCCEEDED'


def test_managed_runtime_without_live_owner_cannot_create_or_claim(prepared):
    service=draft_service(prepared)
    (service.store.root/'.controller-owner.json').write_text(json.dumps(dict(schema_version=1,owner_id='not-held')))
    with pytest.raises(ValueError,match='OWNER_UNCONFIRMED'):create_job(service,prepared)
    assert FixtureDraftProvider.calls==[]


def test_each_upload_has_a_small_independent_generation_limit(prepared):
    service=draft_service(prepared)
    for i in range(3):
        job=create_job(service,prepared,key='generation-'+str(i));service.run(job['id'])
    with pytest.raises(ValueError):create_job(service,prepared,key='generation-4')
    assert len(FixtureDraftProvider.calls)==3
    with service.store.connect() as db:assert db.execute('SELECT count(*) FROM tasks').fetchone()[0]==0


def test_malformed_oracle_does_not_prevent_valid_test_examples(prepared):
    raw=suggestion();raw['oracle']=['not a rule object']
    result=contract_module().validate_suggestion(json.dumps(raw),snapshot(prepared))
    assert result['status']=='EXAMPLES_READY'
    assert json.loads(result['examples_json'])==EXAMPLES
    assert result['oracle_json'] is None


def test_legacy_failed_result_can_still_be_read_from_originals(prepared):
    from nexus.uploads.rule_drafts import sha
    service=draft_service(prepared);job=create_job(service,prepared);service.run(job['id'])
    _,_,payload=service._row(job['id'])
    path=service.directory(job['id'])
    response=json.loads((path/'response.json').read_bytes());raw=suggestion();raw['oracle']=None
    response['raw_text']=json.dumps(raw)
    (path/'response.json').write_text(json.dumps(response))
    legacy=contract_module().validate_suggestion(response['raw_text'],snapshot(prepared),result_version=1)
    assert legacy['schema_version']==1 and legacy['status']=='INVALID'
    (path/'result.json').write_text(json.dumps(legacy))
    payload.update(response_sha256=sha((path/'response.json').read_bytes()),result_sha256=sha((path/'result.json').read_bytes()))
    with service.store.connect() as db:
        db.execute('UPDATE rule_draft_requests SET payload=? WHERE id=?',(json.dumps(payload),job['id']))
    assert service.get(job['id'],actor_id='alice')['result']==legacy
