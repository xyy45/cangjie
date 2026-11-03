from copy import deepcopy
import pytest
from nexus.requirements.service import RequirementService
from nexus.store import RunStore


def setup(tmp_path):
    service=RequirementService(RunStore(tmp_path))
    draft=service.prepare_requirement('order-demo-bug','修复数量边界，保持价格和总额计算')
    confirmation=dict(schema_version=1, expected_version=draft['version'],
                      requirements=deepcopy(draft['requirements']), allowed_paths=draft['allowed_paths'])
    return service,draft,confirmation


def test_confirmation_freezes_original_requirements_actor_and_plan(tmp_path):
    service,draft,confirmation=setup(tmp_path)
    spec=service.confirm_requirement(draft['id'],confirmation,actor_id='local-session-1')
    assert spec.source_text == draft['source_text'] and spec.confirmed_by == 'local-session-1'
    assert spec.spec_hash == service.get_spec(spec.id).spec_hash
    plan=service.build_verification_plan(spec.id,baseline_hash='a'*64,toolchain_id='pinned-sdk')
    assert plan.spec_hash == spec.spec_hash
    assert set(plan.requirement_test_map)=={'REQ-QTY','REQ-PRICE','REQ-TOTAL'}
    assert all(plan.requirement_test_map.values())
    assert plan.context_visibility['src/order_test.cj']=='PUBLIC_TEST'
    assert service.get_plan(plan.id)==plan
    confirmation['requirements'][0]['text']='changed after confirmation'
    assert service.get_spec(spec.id)==spec


def test_empty_goal_unknown_project_and_unconfirmed_spec_are_rejected(tmp_path):
    service=RequirementService(RunStore(tmp_path))
    for project,goal in [('order-demo-bug','  '),('unknown','fix')]:
        with pytest.raises(ValueError): service.prepare_requirement(project,goal)
    draft=service.prepare_requirement('order-demo-bug','fix')
    with pytest.raises(ValueError):
        service.build_verification_plan(draft['id'],baseline_hash='a'*64,toolchain_id='sdk')


def test_unknown_versions_permissions_paths_duplicates_and_unmapped_behavior_rejected(tmp_path):
    service,draft,valid=setup(tmp_path)
    cases=[]
    for field,value in [('schema_version',2),('confirmed_by','attacker'),
                        ('allowed_paths',['src/order_test.cj']),('allowed_paths',['src/missing.cj'])]:
        cases.append({**deepcopy(valid),field:value})
    duplicate=deepcopy(valid);duplicate['requirements'][1]=duplicate['requirements'][0];cases.append(duplicate)
    missing=deepcopy(valid);missing['requirements'].pop();cases.append(missing)
    changed=deepcopy(valid);changed['requirements'][0]['observable_behavior']='Allow quantity zero';cases.append(changed)
    for invalid in cases:
        with pytest.raises(ValueError):service.confirm_requirement(draft['id'],invalid,actor_id='local-user')
    assert service.confirm_requirement(draft['id'],valid,actor_id='local-user')


def test_stale_confirmation_and_revision_leave_previous_spec_immutable(tmp_path):
    service,draft,valid=setup(tmp_path)
    original=service.confirm_requirement(draft['id'],valid,actor_id='local-user')
    with pytest.raises(ValueError,match='already confirmed'):
        service.confirm_requirement(draft['id'],valid,actor_id='local-user')
    revised=service.prepare_requirement('order-demo-bug','new source text',previous_spec_id=original.id)
    assert revised['version']==2
    with pytest.raises(ValueError,match='version'):
        service.confirm_requirement(revised['id'],valid,actor_id='local-user')
    valid['expected_version']=2
    newer=service.confirm_requirement(revised['id'],valid,actor_id='local-user')
    assert newer.version==2 and newer.spec_hash!=original.spec_hash
    assert service.get_spec(original.id)==original


def test_stored_spec_and_plan_tampering_are_not_silently_accepted(tmp_path):
    import json
    service,draft,valid=setup(tmp_path)
    spec=service.confirm_requirement(draft['id'],valid,actor_id='local-user')
    plan=service.build_verification_plan(spec.id,baseline_hash='a'*64,toolchain_id='sdk')
    with service.store.connect() as db:
        changed=plan.model_dump();changed['suite_tests']['order-target']=[]
        db.execute('UPDATE verification_plans SET payload=? WHERE id=?',(json.dumps(changed),plan.id))
    with pytest.raises(ValueError,match='plan changed'):service.get_plan(plan.id)
    with service.store.connect() as db:
        changed=spec.model_dump();changed['source_text']='tampered'
        db.execute('UPDATE requirement_specs SET payload=? WHERE id=?',(json.dumps(changed),spec.id))
    with pytest.raises(ValueError,match='content changed'):service.get_spec(spec.id)
