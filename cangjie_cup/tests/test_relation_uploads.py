"""Optional relation confirmation is immutable, private, owned, and bounded."""
from copy import deepcopy
import io
import json

import pytest

from nexus.contracts import digest,source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_relations import raw,EXAMPLES
from tests.test_project_service import prepare as prepare_project,confirm as confirm_project
from tests.test_rule_drafts import prepared as rule_prepared
from tests.test_upload_routes import page

SOURCE=b'public func amount(quantity: Int64, price: Int64, promotion: Bool): Int64 { return quantity * price }\n'


def prepared(tmp_path):
    service=UploadService(RunStore(tmp_path));draft=service.prepare('amount.cj',SOURCE,'固定正价无优惠时增加数量不得降低总额',actor_id='alice',request_key='one')
    return service,draft,dict(expected_version=1,function='amount',examples_json=json.dumps(EXAMPLES),consent=True,actor_id='alice')


def test_confirmed_relation_is_private_importable_and_reconfirmation_is_immutable(tmp_path):
    service,draft,args=prepared(tmp_path);value=service.confirm(draft['id'],**args,relations_json=json.dumps(raw()))
    root=service.source(draft['id'],actor_id='alice');stored=json.loads((root/'verification/relations.json').read_bytes())
    assert value['relations_contract']==stored and value['relations_hash']==digest(stored)
    assert value['relations_origin']=='USER_CONFIRMED'
    assert service.profile(draft['id'])['context_visibility']['verification/relations.json']=='VERIFICATION_ONLY'
    assert service.case(draft['id'],actor_id='alice')['independent_relations'] is True
    assert WorkspaceStore(tmp_path,registered=[root]).import_project(root,'.').startswith('b_')
    assert service.confirm(draft['id'],**args,relations_json=json.dumps(raw(),indent=2))==value
    changed=raw();changed['seed']+=1
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,relations_json=json.dumps(changed))
    with pytest.raises(ValueError):service.confirm(draft['id'],**args)
    (root/'verification/relations.json').write_text('{}')
    with pytest.raises(ValueError):service.profile(draft['id'])


def test_absent_or_empty_relation_does_not_change_old_confirmation_hash(tmp_path):
    service,draft,args=prepared(tmp_path);value=service.confirm(draft['id'],**args,relations_json='  ')
    assert value['confirmation_hash']==digest(dict(function='amount',examples=EXAMPLES,consent=True))
    assert 'relations_contract' not in value
    assert 'verification/relations.json' not in value['manifest']
    assert service.confirm(draft['id'],**args)==value


@pytest.mark.parametrize('bad',['null','[]','{}','{"version":1,"version":1}', ' '*16385, '\u3000'*5462, 0,False,[],None],ids=['null','array','empty','duplicate','space-bytes','unicode-bytes','integer','bool','list','none'])
def test_bad_relation_cannot_create_frozen_project(tmp_path,bad):
    service,draft,args=prepared(tmp_path)
    if bad is None:
        # None is deliberately the backward compatible absent field.
        assert service.confirm(draft['id'],**args,relations_json=bad)['status']=='CONFIRMED'
        return
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,relations_json=bad)
    assert service.get(draft['id'],actor_id='alice')['status']=='DRAFT'
    assert not (tmp_path/'uploads'/draft['id']/'project').exists()


@pytest.mark.parametrize('change',['nested-duplicate','nan','wrong-function','wrong-type','public-conflict'])
def test_nested_invalid_or_contradictory_relation_is_rejected_before_freezing(tmp_path,change):
    service,draft,args=prepared(tmp_path);source=raw()
    if change=='nested-duplicate':text=json.dumps(source).replace('"id": "REL-MONOTONE"','"id":"REL-MONOTONE","id":"REL-OTHER"')
    elif change=='nan':text=json.dumps(source).replace('"seed": 1234','"seed": NaN')
    else:
        if change=='wrong-function':source['function']='other'
        elif change=='wrong-type':source['relations'][0]['assertion']='left_arg2 == right_result'
        else:source['relations'][0]['assertion']='left_result > right_result'
        text=json.dumps(source)
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,relations_json=text)
    assert service.get(draft['id'],actor_id='alice')['status']=='DRAFT'


def test_relations_require_identical_full_reserved_sets_across_all_enabled_contracts(tmp_path):
    service,draft,args=prepared(tmp_path);relation=raw();reserved=[[9,100,False],[-1,0,True]];relation['excluded_inputs']=reserved
    rule=dict(version=2,function='amount',domains=deepcopy(relation['domains']),expression='quantity * price',seed=0,max_cases=32,excluded_inputs=reserved)
    # Legacy oracle-v2 permits exclusions only in its own domain. Keep that
    # behavior while testing equality of complete sets outside relation scope.
    rule['domains']['quantity']['min']=-1;rule['domains']['price']['min']=0
    single=dict(version=1,kind='single',function='amount',domains=deepcopy(relation['domains']),properties=[dict(id='PROP-NONNEGATIVE',text='金额非负',precondition='True',assertion='result >= 0')],seed=0,max_cases=16,excluded_inputs=reserved)
    wrong=deepcopy(relation);wrong['excluded_inputs']=reserved[:1]
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,oracle_json=json.dumps(rule),relations_json=json.dumps(wrong))
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,properties_json=json.dumps(single),relations_json=json.dumps(wrong))
    old={k:v for k,v in rule.items() if k!='excluded_inputs'};old['version']=1
    with pytest.raises(ValueError):service.confirm(draft['id'],**args,oracle_json=json.dumps(old),relations_json=json.dumps(relation))
    value=service.confirm(draft['id'],**args,oracle_json=json.dumps(rule),properties_json=json.dumps(single),relations_json=json.dumps(relation))
    assert value['relations_contract']['excluded_inputs']==reserved
    assert value['properties_contract']['excluded_inputs']==reserved
    assert value['oracle_contract']['excluded_inputs']==reserved
    assert service.profile(draft['id'])['context_visibility']['verification/relations.json']=='VERIFICATION_ONLY'


def test_project_relation_keeps_original_material_scope_and_exact_json_whitelist(tmp_path):
    from tests.test_project_index import project
    service=UploadService(RunStore(tmp_path));draft=prepare_project(service)
    relation=dict(version=1,kind='relation',function='total',domains=dict(x=dict(min=0,max=8)),relations=[
        dict(id='REL-MONOTONE',text='输入增加总额不降',precondition='left_arg0 < right_arg0',assertion='left_result <= right_result')],seed=0,max_pairs=16,excluded_inputs=[])
    value=confirm_project(service,draft,allowed_paths=['src/fee.cj'],relations_json=json.dumps(relation))
    root=service.source(draft['id'],actor_id='alice');assert value['allowed_paths']==['src/fee.cj']
    for name,data in project().items():assert (root/name).read_bytes()==data
    ws=WorkspaceStore(tmp_path,registered=[root]);assert ws.import_project(root,'.')
    (root/'verification/unexpected.json').write_text('{}')
    with pytest.raises(ValueError,match='unregistered'):ws.import_project(root,'.')


def test_original_project_cannot_supply_or_collide_with_system_relation_contract(tmp_path):
    from tests.test_project_index import project
    files=project();files['verification/relations.json']=b'{}'
    with pytest.raises(ValueError):prepare_project(UploadService(RunStore(tmp_path)),files=files)


def test_relation_route_rejects_csrf_foreign_actor_and_malformed_contract(tmp_path):
    app,alice,headers=page(tmp_path)
    draft=alice.post('/api/uploads/repair',data={'file':(io.BytesIO(SOURCE),'amount.cj'),'goal':'固定价格数量增加总额不降','request_key':'one'},headers=headers).json
    url='/api/uploads/repair/'+draft['id']+'/confirm'
    body=dict(expected_version=1,function='amount',examples_json=json.dumps(EXAMPLES),consent=True,relations_json=json.dumps(raw()))
    assert alice.post(url,json=body).status_code==403
    bob=app.test_client();bob.get('/')
    with bob.session_transaction() as session:foreign={'Origin':'http://localhost','X-CSRF-Token':session['csrf']}
    assert bob.post(url,json=body,headers=foreign).status_code==404
    assert alice.post(url,json={**body,'relations_json':'{"seed":NaN}'},headers=headers).status_code==400
    response=alice.post(url,json=body,headers=headers)
    assert response.status_code==200,response.json
    assert alice.get('/demo/cases/'+draft['id']).json['independent_relations'] is True


def test_manual_relations_do_not_change_old_model_draft_provenance(rule_prepared):
    from tests.test_rule_draft_confirmation import ready
    from tests.test_rule_drafts import RULE
    _,job,preview=ready(rule_prepared);service,draft=rule_prepared
    relation=dict(version=1,kind='relation',function='fee',domains=deepcopy(RULE['domains']),relations=[
        dict(id='REL-MONOTONE',text='同价增加数量不能降费',precondition='left_arg1 == right_arg1 and left_arg0 < right_arg0',assertion='left_result <= right_result')],seed=0,max_pairs=16,excluded_inputs=[])
    value=service.confirm(draft['id'],actor_id='alice',expected_version=1,function='fee',examples_json=preview['examples_json'],oracle_json=preview['oracle_json'],
        consent=True,rule_draft_ref=preview['rule_draft_ref'],relations_json=json.dumps(relation))
    assert value['relations_origin']=='USER_CONFIRMED' and value['rule_draft_provenance']['rule_draft_id']==job['id']
    assert value['rule_draft_provenance']['confirmed_payload_hash']==digest(dict(examples=value['examples'],oracle=value['oracle_contract']))
    assert value['relations_hash'] not in value['rule_draft_provenance'].values()


def test_generated_relation_counts_toward_project_material_budget(tmp_path):
    from tests.test_project_index import project
    files=project();files.update({f'note{i}.md':b'note' for i in range(99-len(files))})
    service=UploadService(RunStore(tmp_path));draft=prepare_project(service,files=files)
    relation=dict(version=1,kind='relation',function='total',domains={'x':dict(min=0,max=8)},relations=[
        dict(id='REL-SAME',text='相同输入返回一致',precondition='left_arg0 == right_arg0',assertion='left_result == right_result')],seed=0,max_pairs=16,excluded_inputs=[])
    with pytest.raises(ValueError,match='预算'):confirm_project(service,draft,relations_json=json.dumps(relation))
    assert service.get(draft['id'],actor_id='alice')['status']=='DRAFT'
    assert not (tmp_path/'uploads'/draft['id']/'project').exists()
    confirm_project(service,draft)
    root=service.source(draft['id'],actor_id='alice');assert len(source_manifest(root))==100
