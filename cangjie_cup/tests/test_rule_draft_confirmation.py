"""A model suggestion only becomes a verification basis after explicit confirmation."""
from copy import deepcopy
import json

import pytest

from nexus.contracts import digest,source_manifest
from tests.test_rule_drafts import prepared,draft_service,create_job,EXAMPLES,RULE


def ready(prepared):
    service=draft_service(prepared);job=create_job(service,prepared);service.run(job['id'])
    preview=service.apply_preview(job['id'],actor_id='alice',expected_version=1,function='fee')
    return service,job,preview


def confirm(prepared,preview,**changes):
    args=dict(actor_id='alice',expected_version=1,function='fee',examples_json=preview['examples_json'],oracle_json=preview['oracle_json'],consent=True,rule_draft_ref=preview['rule_draft_ref'])
    args.update(changes)
    return prepared[0].confirm(prepared[1]['id'],**args)


def test_confirmed_provenance_and_exact_originals_are_frozen_and_hidden_from_model(prepared):
    drafts,job,preview=ready(prepared);value=confirm(prepared,preview)
    proof=value['rule_draft_provenance'];root=prepared[0].source(prepared[1]['id'],actor_id='alice')
    assert proof['rule_draft_id']==job['id'] and proof['edited_by_user'] is False
    assert proof['origin']=='TEST_FIXTURE_NOT_LIVE' and proof['business_verified'] is False
    assert json.loads((root/'verification/rule-draft/provenance.json').read_bytes())==proof
    for kind in ('input','request','response','result'):
        assert (root/'verification/rule-draft'/(kind+'.json')).read_bytes()==(drafts.directory(job['id'])/(kind+'.json')).read_bytes()
    profile=prepared[0].profile(prepared[1]['id'])
    assert all(profile['context_visibility']['verification/rule-draft/'+name]=='VERIFICATION_ONLY' for name in ('input.json','request.json','response.json','result.json','provenance.json'))
    assert confirm(prepared,preview)==value
    before=source_manifest(root);(root/'verification/rule-draft/provenance.json').write_text('{}')
    with pytest.raises(ValueError):prepared[0].profile(prepared[1]['id'])
    assert before!=source_manifest(root)


def test_user_edits_bind_actual_confirmed_content_instead_of_original_suggestion(prepared):
    _,_,preview=ready(prepared)
    edited=deepcopy(EXAMPLES)+[dict(args=[2,5],expected=10,suite='regression')]
    value=confirm(prepared,preview,examples_json=json.dumps(edited))
    proof=value['rule_draft_provenance']
    assert value['examples']==edited and proof['edited_by_user'] is True
    assert proof['confirmed_payload_hash']==digest(dict(examples=value['examples'],oracle=value['oracle_contract']))
    assert proof['confirmed_payload_hash']!=proof['generated_payload_hash']
    with pytest.raises(ValueError):confirm(prepared,preview)


@pytest.mark.parametrize('change',['forged-binding','forged-result','extra-field','other-upload','other-actor'])
def test_invalid_provenance_cannot_freeze_or_modify_upload(prepared,change):
    service,job,preview=ready(prepared);forged=deepcopy(preview)
    if change=='forged-binding':forged['rule_draft_ref']['binding_hash']='0'*64
    elif change=='forged-result':forged['rule_draft_ref']['result_sha256']='0'*64
    elif change=='extra-field':forged['rule_draft_ref']['allow']=True
    elif change=='other-upload':
        from tests.test_rule_drafts import SOURCE
        other=prepared[0].prepare('other.cj',SOURCE,'quantity与price均在0..1000，返回二者乘积',actor_id='alice',request_key='other')
        prepared=(prepared[0],other)
    kwargs={'actor_id':'bob'} if change=='other-actor' else {}
    with pytest.raises((ValueError,LookupError)):confirm(prepared,forged,**kwargs)
    assert prepared[0].get(prepared[1]['id'],actor_id='alice')['status']=='DRAFT'
    assert not (prepared[0].store.root/'uploads'/prepared[1]['id']/'project').exists()


def test_whitespace_only_changes_do_not_claim_semantic_user_edit(prepared):
    _,_,preview=ready(prepared)
    value=confirm(prepared,preview,examples_json=json.dumps(json.loads(preview['examples_json']),indent=4))
    assert value['rule_draft_provenance']['edited_by_user'] is False



@pytest.mark.parametrize('name',['unexpected.json','nested/result.json','run.py'])
def test_registered_import_keeps_arbitrary_draft_directory_material_rejected(prepared,name):
    from nexus.execution.workspace import WorkspaceStore
    _,_,preview=ready(prepared);confirm(prepared,preview)
    root=prepared[0].source(prepared[1]['id'],actor_id='alice');target=root/'verification/rule-draft'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('{}')
    with pytest.raises(ValueError,match='unregistered project material'):
        WorkspaceStore(prepared[0].store.root,registered=[root]).import_project(root,'.')
