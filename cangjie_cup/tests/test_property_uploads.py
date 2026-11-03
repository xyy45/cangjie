"""User-confirmed properties freeze separately from model-generated rules."""
from copy import deepcopy
import io
import json

import pytest

from nexus.contracts import digest
from nexus.execution.workspace import WorkspaceStore
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_property_contract import raw,EXAMPLES
from tests.test_upload_routes import page
from tests.test_project_service import prepare as prepare_project,confirm as confirm_project
from tests.test_rule_drafts import prepared as rule_prepared

SOURCE=b'public func refundState(paid: Int64, refunded: Int64, requested: Int64): Int64 { return refunded + requested }\n'


def prepared(tmp_path,key='one'):
    service=UploadService(RunStore(tmp_path));draft=service.prepare('refund.cj',SOURCE,'合法退款不得超过实付，非法申请保持旧累计',actor_id='alice',request_key=key)
    args=dict(expected_version=1,function='refundState',examples_json=json.dumps(EXAMPLES),consent=True,actor_id='alice')
    return service,draft,args


def test_single_property_confirmation_freezes_importable_private_contract(tmp_path):
    service,draft,args=prepared(tmp_path);value=service.confirm(draft['id'],**args,properties_json=json.dumps(raw()))
    root=service.source(draft['id'],actor_id='alice');stored=json.loads((root/'verification/properties.json').read_bytes())
    assert stored==value['properties_contract'] and value['properties_hash']==digest(stored)
    assert value['properties_origin']=='USER_CONFIRMED'
    assert service.profile(draft['id'])['context_visibility']['verification/properties.json']=='VERIFICATION_ONLY'
    assert service.case(draft['id'],actor_id='alice')['independent_properties'] is True
    ws=WorkspaceStore(tmp_path,registered=[root]);assert ws.import_project(root,'.').startswith('b_')
    assert service.confirm(draft['id'],**args,properties_json=json.dumps(raw(),indent=2))==value
    changed=raw();changed['seed']+=1
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,properties_json=json.dumps(changed))
    with pytest.raises(ValueError):service.confirm(draft['id'],**args)
    (root/'verification/properties.json').write_text('{}')
    with pytest.raises(ValueError):service.profile(draft['id'])


def test_no_properties_keeps_old_confirmation_hash_and_material(tmp_path):
    service,draft,args=prepared(tmp_path)
    value=service.confirm(draft['id'],**args,properties_json='  ')
    assert value['confirmation_hash']==digest(dict(function='refundState',examples=EXAMPLES,consent=True))
    assert 'properties_contract' not in value
    assert not (service.source(draft['id'],actor_id='alice')/'verification/properties.json').exists()
    assert service.confirm(draft['id'],**args)==value


@pytest.mark.parametrize('bad',['null','{}','[]','{"version":1,"version":1}', ' '*16385,0],ids=['null','empty-object','array','duplicate-key','oversized-space','integer'])
def test_invalid_or_oversized_property_input_never_creates_frozen_project(tmp_path,bad):
    service,draft,args=prepared(tmp_path)
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,properties_json=bad)
    assert service.get(draft['id'],actor_id='alice')['status']=='DRAFT'
    assert not (tmp_path/'uploads'/draft['id']/'project').exists()


def test_nested_duplicate_keys_and_conflicting_confirmed_behavior_are_rejected(tmp_path):
    service,draft,args=prepared(tmp_path);text=json.dumps(raw()).replace('"id": "PROP-RANGE"','"id":"PROP-RANGE","id":"PROP-OTHER"')
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,properties_json=text)
    wrong=raw();wrong['properties'][0]['assertion']='result < 0'
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,properties_json=json.dumps(wrong))


def test_properties_cannot_weaken_oracle_reserved_input_set(tmp_path):
    service,draft,args=prepared(tmp_path);props=raw();reserved=[[1000,900,200]]
    rule=dict(version=2,function='refundState',domains=deepcopy(props['domains']),expression='refunded + requested if requested <= paid - refunded else refunded',seed=0,max_cases=32,excluded_inputs=reserved)
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,oracle_json=json.dumps(rule),properties_json=json.dumps(props))
    props['excluded_inputs']=reserved
    old={k:v for k,v in rule.items() if k!='excluded_inputs'};old['version']=1
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,oracle_json=json.dumps(old),properties_json=json.dumps(props))
    value=service.confirm(draft['id'],**args,oracle_json=json.dumps(rule),properties_json=json.dumps(props))
    assert value['properties_contract']['excluded_inputs']==value['oracle_contract']['excluded_inputs']


def test_project_properties_keep_production_scope_and_private_file_whitelist(tmp_path):
    service=UploadService(RunStore(tmp_path));draft=prepare_project(service)
    props=dict(version=1,kind='single',function='total',domains={'x':dict(min=0,max=8)},
        properties=[dict(id='PROP-NONNEGATIVE',text='总额非负',precondition='True',assertion='result >= 0')],seed=0,max_cases=16,excluded_inputs=[])
    value=confirm_project(service,draft,allowed_paths=['src/fee.cj'],properties_json=json.dumps(props))
    assert value['allowed_paths']==['src/fee.cj']
    root=service.source(draft['id'],actor_id='alice')
    ws=WorkspaceStore(tmp_path,registered=[root]);assert ws.import_project(root,'.')
    (root/'verification/unexpected.json').write_text('{}')
    with pytest.raises(ValueError,match='unregistered'):ws.import_project(root,'.')


def test_original_project_cannot_supply_generated_properties_json(tmp_path):
    from tests.test_project_index import project
    from tests.test_project_service import payload
    files=project();files['verification/properties.json']=b'{}'
    with pytest.raises(ValueError):UploadService(RunStore(tmp_path)).prepare_project('bad.zip',payload(files),'原件不能占用验证文件',actor_id='alice',request_key='one')


def test_property_route_and_owner_boundary_are_enforced(tmp_path):
    app,alice,headers=page(tmp_path)
    draft=alice.post('/api/uploads/repair',data={'file':(io.BytesIO(SOURCE),'refund.cj'),'goal':'退款不得超额','request_key':'one'},headers=headers).json
    body=dict(expected_version=1,function='refundState',examples_json=json.dumps(EXAMPLES),consent=True,properties_json=json.dumps(raw()))
    assert alice.post('/api/uploads/repair/'+draft['id']+'/confirm',json=body).status_code==403
    bob=app.test_client();bob.get('/')
    with bob.session_transaction() as session:foreign={'Origin':'http://localhost','X-CSRF-Token':session['csrf']}
    assert bob.post('/api/uploads/repair/'+draft['id']+'/confirm',json=body,headers=foreign).status_code==404
    response=alice.post('/api/uploads/repair/'+draft['id']+'/confirm',json=body,headers=headers)
    assert response.status_code==200,response.json
    assert alice.get('/demo/cases/'+draft['id']).json['independent_properties'] is True


def test_manual_properties_do_not_relabel_old_model_draft_provenance(rule_prepared):
    from tests.test_rule_draft_confirmation import ready
    from tests.test_rule_drafts import RULE
    _,job,preview=ready(rule_prepared);service,draft=rule_prepared
    props=dict(version=1,kind='single',function='fee',domains=deepcopy(RULE['domains']),properties=[
        dict(id='PROP-NONNEGATIVE',text='非负参数不得产生负费用',precondition='True',assertion='result >= 0')],seed=0,max_cases=16,excluded_inputs=[])
    value=service.confirm(draft['id'],actor_id='alice',expected_version=1,function='fee',examples_json=preview['examples_json'],oracle_json=preview['oracle_json'],
        consent=True,rule_draft_ref=preview['rule_draft_ref'],properties_json=json.dumps(props))
    assert value['properties_origin']=='USER_CONFIRMED'
    proof=value['rule_draft_provenance']
    assert proof['rule_draft_id']==job['id'] and proof['edited_by_user'] is False
    assert proof['confirmed_payload_hash']==digest(dict(examples=value['examples'],oracle=value['oracle_contract']))
    assert value['properties_hash'] not in proof.values()


def test_generated_properties_count_toward_final_project_budget(tmp_path):
    from tests.test_project_index import project
    files=project();files.update({f'note{i}.md':b'note' for i in range(99-len(files))})
    service=UploadService(RunStore(tmp_path));draft=prepare_project(service,files=files)
    props=dict(version=1,kind='single',function='total',domains={'x':dict(min=0,max=8)},properties=[
        dict(id='PROP-RANGE',text='总额非负',precondition='True',assertion='result >= 0')],seed=0,max_cases=16,excluded_inputs=[])
    with pytest.raises(ValueError,match='预算'):confirm_project(service,draft,properties_json=json.dumps(props))
    assert service.get(draft['id'],actor_id='alice')['status']=='DRAFT'
    assert not (tmp_path/'uploads'/draft['id']/'project').exists()
    confirm_project(service,draft)
    root=service.source(draft['id'],actor_id='alice');assert WorkspaceStore(tmp_path,registered=[root]).import_project(root,'.')
