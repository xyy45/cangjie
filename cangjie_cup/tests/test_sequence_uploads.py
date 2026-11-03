"""User-confirmed sequence models are immutable, private and owned."""
from copy import deepcopy
import io
import json

import pytest

from nexus.contracts import digest,source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_sequences import refund_raw
from tests.test_project_service import prepare as prepare_project,confirm as confirm_project
from tests.test_project_index import project
from tests.test_rule_drafts import prepared as rule_prepared
from tests.test_upload_routes import page

SOURCE=b'public func refund(state: Int64, amount: Int64, paid: Int64): Int64 { return state + amount }\n'
EXAMPLES=[dict(args=[0,3,10],expected=3,suite='target'),dict(args=[5,2,10],expected=7,suite='regression')]


def prepared(tmp_path):
    service=UploadService(RunStore(tmp_path));draft=service.prepare('refund.cj',SOURCE,'累计退款不能超过实付，非法请求保持原状态',actor_id='alice',request_key='one')
    return service,draft,dict(expected_version=1,function='refund',examples_json=json.dumps(EXAMPLES),consent=True,actor_id='alice')


def sequence():return refund_raw()[0]


def project_sequence():
    return dict(version=1,kind='sequence',function='total',state_param='x',domains=dict(x=dict(min=0,max=1000)),initial_states=[0],initial_precondition='True',context_params=[],
        operations=[dict(id='OP-ADD',text='增加一百',args=[],transition='state + 100')],invariants=[dict(id='INV-INCREASE',text='单调增加',precondition='True',assertion='result >= before_state')],seed=0,max_sequences=8,max_steps=2,excluded_inputs=[])


def test_confirmed_sequence_is_private_importable_and_reconfirmation_is_immutable(tmp_path):
    service,draft,args=prepared(tmp_path);text=json.dumps(sequence(),indent=2,ensure_ascii=False)
    value=service.confirm(draft['id'],**args,sequences_json=text);root=service.source(draft['id'],actor_id='alice');stored=json.loads((root/'verification/sequences.json').read_bytes())
    assert value['sequences_contract']==stored and value['sequences_hash']==digest(stored) and value['sequences_json']==text
    assert value['sequences_origin']=='USER_CONFIRMED'
    assert service.profile(draft['id'])['context_visibility']['verification/sequences.json']=='VERIFICATION_ONLY'
    case=service.case(draft['id'],actor_id='alice');assert case['independent_sequences'] is True and 'sequences_contract' not in case
    assert WorkspaceStore(tmp_path,registered=[root]).import_project(root,'.').startswith('b_')
    assert service.confirm(draft['id'],**args,sequences_json=json.dumps(sequence()))==value
    changed=sequence();changed['seed']+=1
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,sequences_json=json.dumps(changed))
    with pytest.raises(ValueError):service.confirm(draft['id'],**args)
    (root/'verification/sequences.json').write_text('{}')
    with pytest.raises(ValueError):service.profile(draft['id'])


@pytest.mark.parametrize('empty',[None,'','  '])
def test_absent_or_empty_sequence_does_not_change_old_confirmation_hash(tmp_path,empty):
    service,draft,args=prepared(tmp_path);value=service.confirm(draft['id'],**args,sequences_json=empty)
    assert value['confirmation_hash']==digest(dict(function='refund',examples=EXAMPLES,consent=True))
    assert 'sequences_contract' not in value and 'verification/sequences.json' not in value['manifest']
    assert service.case(draft['id'],actor_id='alice')['independent_sequences'] is False
    assert service.confirm(draft['id'],**args)==value


@pytest.mark.parametrize('bad',['null','[]','{}','{"version":1,"version":1}',' '*16385,'\u3000'*5462,0,False,[]])
def test_invalid_sequence_json_never_creates_a_frozen_project(tmp_path,bad):
    service,draft,args=prepared(tmp_path)
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,sequences_json=bad)
    assert service.get(draft['id'],actor_id='alice')['status']=='DRAFT'
    assert not (tmp_path/'uploads'/draft['id']/'project').exists()


@pytest.mark.parametrize('change',['duplicate-nested','nan','infinity','wrong-function','wrong-state','hidden-history','public-conflict'])
def test_invalid_or_contradictory_model_is_rejected_before_freezing(tmp_path,change):
    service,draft,args=prepared(tmp_path);source=sequence()
    if change=='duplicate-nested':text=json.dumps(source).replace('"id": "OP-REFUND"','"id":"OP-REFUND","id":"OP-OTHER"')
    elif change in ('nan','infinity'):text=json.dumps(source).replace('"seed": 1','"seed": '+('NaN' if change=='nan' else 'Infinity'))
    else:
        if change=='wrong-function':source['function']='other'
        elif change=='wrong-state':source['state_param']='missing'
        elif change=='hidden-history':source['operations'][0]['transition']='state + step_index'
        else:source['operations'][0]['transition']='0'
        text=json.dumps(source)
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,sequences_json=text)
    assert service.get(draft['id'],actor_id='alice')['status']=='DRAFT'


def test_all_four_enabled_contracts_require_identical_complete_reserved_sets(tmp_path):
    service,draft,args=prepared(tmp_path);source=sequence();reserved=[[9,2,10]];source['excluded_inputs']=reserved
    rule=dict(version=2,function='refund',domains=deepcopy(source['domains']),expression='min(paid, state + amount)',seed=0,max_cases=32,excluded_inputs=reserved)
    single=dict(version=1,kind='single',function='refund',domains=deepcopy(source['domains']),properties=[dict(id='PROP-NONNEGATIVE',text='退款非负',precondition='True',assertion='result >= 0')],seed=0,max_cases=16,excluded_inputs=reserved)
    relation=dict(version=1,kind='relation',function='refund',domains=deepcopy(source['domains']),relations=[dict(id='REL-NONNEGATIVE',text='两个返回非负',precondition='True',assertion='left_result >= 0 and right_result >= 0')],seed=0,max_pairs=16,excluded_inputs=reserved)
    wrong=deepcopy(source);wrong['excluded_inputs']=[]
    for name,contract in [('oracle_json',rule),('properties_json',single),('relations_json',relation)]:
        with pytest.raises(ValueError):service.confirm(draft['id'],**args,sequences_json=json.dumps(wrong),**{name:json.dumps(contract)})
    old={k:v for k,v in rule.items() if k!='excluded_inputs'};old['version']=1
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,sequences_json=json.dumps(source),oracle_json=json.dumps(old))
    value=service.confirm(draft['id'],**args,oracle_json=json.dumps(rule),properties_json=json.dumps(single),relations_json=json.dumps(relation),sequences_json=json.dumps(source))
    for name in ('oracle_contract','properties_contract','relations_contract','sequences_contract'):assert value[name]['excluded_inputs']==reserved


def test_nonmatching_state_return_type_original_source_and_foreign_actor_are_rejected(tmp_path):
    service,draft,args=prepared(tmp_path)
    with pytest.raises(LookupError):service.confirm(draft['id'],**{**args,'actor_id':'bob'},sequences_json=json.dumps(sequence()))
    (tmp_path/'uploads'/draft['id']/'source.cj').write_bytes(SOURCE+b'// replaced\n')
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,sequences_json=json.dumps(sequence()))
    second=service.prepare('bool.cj',b'public func refund(state: Int64, amount: Int64, paid: Int64): Bool { return state > 0 }\n','测试类型',actor_id='alice',request_key='two')
    examples=[dict(args=[1,0,10],expected=True,suite='target'),dict(args=[0,0,10],expected=False,suite='regression')]
    with pytest.raises(ValueError):service.confirm(second['id'],**{**args,'examples_json':json.dumps(examples)},sequences_json=json.dumps(sequence()))


def test_same_package_project_preserves_original_scope_and_exact_json_whitelist(tmp_path):
    service=UploadService(RunStore(tmp_path));draft=prepare_project(service);value=confirm_project(service,draft,allowed_paths=['src/fee.cj'],sequences_json=json.dumps(project_sequence()))
    root=service.source(draft['id'],actor_id='alice');assert value['allowed_paths']==['src/fee.cj']
    for name,data in project().items():assert (root/name).read_bytes()==data
    ws=WorkspaceStore(tmp_path,registered=[root]);assert ws.import_project(root,'.')
    (root/'verification/unexpected.json').write_text('{}')
    with pytest.raises(ValueError,match='unregistered'):ws.import_project(root,'.')


def test_original_project_cannot_supply_system_sequence_contract(tmp_path):
    files=project();files['verification/sequences.json']=b'{}'
    with pytest.raises(ValueError):prepare_project(UploadService(RunStore(tmp_path)),files=files)


def test_sequence_confirmation_route_keeps_csrf_actor_and_model_boundaries(tmp_path):
    app,alice,headers=page(tmp_path)
    draft=alice.post('/api/uploads/repair',data=dict(file=(io.BytesIO(SOURCE),'refund.cj'),goal='累计退款封顶实付',request_key='one'),headers=headers).json
    url='/api/uploads/repair/'+draft['id']+'/confirm';body=dict(expected_version=1,function='refund',examples_json=json.dumps(EXAMPLES),consent=True,sequences_json=json.dumps(sequence()))
    assert alice.post(url,json=body).status_code==403
    bob=app.test_client();bob.get('/')
    with bob.session_transaction() as session:foreign={'Origin':'http://localhost','X-CSRF-Token':session['csrf']}
    assert bob.post(url,json=body,headers=foreign).status_code==404
    assert alice.post(url,json={**body,'sequences_json':'{"seed":NaN}'},headers=headers).status_code==400
    response=alice.post(url,json=body,headers=headers);assert response.status_code==200,response.json
    assert alice.get('/demo/cases/'+draft['id']).json['independent_sequences'] is True
    with RunStore(tmp_path).connect() as db:assert db.execute('SELECT count(*) FROM tasks').fetchone()[0]==0


def test_manual_sequence_does_not_claim_model_draft_provenance(rule_prepared):
    from tests.test_rule_draft_confirmation import ready
    from tests.test_rule_drafts import RULE
    _,job,preview=ready(rule_prepared);service,draft=rule_prepared
    source=dict(version=1,kind='sequence',function='fee',state_param='quantity',domains=deepcopy(RULE['domains']),initial_states=[0],initial_precondition='True',context_params=['price'],
        operations=[dict(id='OP-FEE',text='按固定单价计算',args=[dict(context='price')],transition='state * arg1')],invariants=[dict(id='INV-NONNEGATIVE',text='金额非负',precondition='True',assertion='result >= 0')],seed=0,max_sequences=8,max_steps=2,excluded_inputs=[])
    value=service.confirm(draft['id'],actor_id='alice',expected_version=1,function='fee',examples_json=preview['examples_json'],oracle_json=preview['oracle_json'],consent=True,rule_draft_ref=preview['rule_draft_ref'],sequences_json=json.dumps(source))
    assert value['sequences_origin']=='USER_CONFIRMED' and value['rule_draft_provenance']['rule_draft_id']==job['id']
    assert value['rule_draft_provenance']['confirmed_payload_hash']==digest(dict(examples=value['examples'],oracle=value['oracle_contract']))
    assert value['sequences_hash'] not in value['rule_draft_provenance'].values()


def test_sequence_file_counts_toward_total_project_file_budget(tmp_path):
    files=project();files.update({f'note{i}.md':b'note' for i in range(99-len(files))})
    service=UploadService(RunStore(tmp_path));draft=prepare_project(service,files=files)
    with pytest.raises(ValueError,match='预算'):confirm_project(service,draft,sequences_json=json.dumps(project_sequence()))
    assert service.get(draft['id'],actor_id='alice')['status']=='DRAFT'
    assert not (tmp_path/'uploads'/draft['id']/'project').exists()
    confirm_project(service,draft);assert len(source_manifest(service.source(draft['id'],actor_id='alice')))==100


def test_sequence_file_counts_toward_total_project_byte_budget(tmp_path):
    files=project();remaining=2*1024*1024-1024-sum(len(v) for v in files.values());i=0
    while remaining:
        size=min(remaining,128*1024);files[f'padding{i}.md']=b'x'*size;remaining-=size;i+=1
    service=UploadService(RunStore(tmp_path));draft=service.prepare_project('billing-directory',None,'计算订单',actor_id='alice',request_key='bytes',entries=files)
    source=project_sequence();source['operations'][0]['text']='状态模型'*100
    with pytest.raises(ValueError,match='预算'):confirm_project(service,draft,sequences_json=json.dumps(source))
    assert service.get(draft['id'],actor_id='alice')['status']=='DRAFT'
    confirm_project(service,draft);assert sum((service.source(draft['id'],actor_id='alice')/p).stat().st_size for p in service.get(draft['id'],actor_id='alice')['manifest'])<=2*1024*1024
