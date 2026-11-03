"""Registered examples have their own source scope and frozen test mapping."""
from pathlib import Path

import pytest

from nexus.demo.cases import load_cases
from nexus.requirements.service import RequirementService
from nexus.store import RunStore

ROOT=Path(__file__).resolve().parents[1]
REPAIRS=['order-demo-bug','order-price','order-discount','cross-validation','cross-discount','cross-stock']


def test_nine_cases_cover_three_categories_with_real_source_files():
    cases=load_cases()
    assert len(cases)==9
    assert {c.get('group') for c in cases.values()}=={'order','cross','policy'}
    assert all(sum(c['group']==group for c in cases.values())==3 for group in ['order','cross','policy'])
    assert all(c['files'] and all(f['path'].endswith('.cj') for f in c['files']) for c in cases.values())
    assert {c['project_id'] for c in cases.values() if c['kind']=='repair'}==set(REPAIRS)


@pytest.mark.parametrize('project',REPAIRS)
def test_each_registered_repair_has_frozen_requirements_and_tests(tmp_path,project):
    service=RequirementService(RunStore(tmp_path))
    draft=service.prepare_requirement(project,'修复本案例，保留测试')
    assert draft['requirements'] and draft['allowed_paths']
    spec=service.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=1,
        requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='TEST_OPERATOR')
    plan=service.build_verification_plan(spec.id,baseline_hash='a'*64,toolchain_id='pinned')
    assert all(plan.requirement_test_map[r.id] for r in spec.requirements)
    assert all(plan.suite_tests[name] for name in plan.required_suites)
    assert all(not path.endswith('_test.cj') for path in draft['allowed_paths'])


def test_profiles_do_not_accept_another_cases_requirements(tmp_path):
    service=RequirementService(RunStore(tmp_path))
    price=service.prepare_requirement('order-price','price')
    stock=service.prepare_requirement('cross-stock','stock')
    with pytest.raises(ValueError):
        service.confirm_requirement(price['id'],dict(schema_version=1,expected_version=1,
            requirements=stock['requirements'],allowed_paths=price['allowed_paths']),actor_id='TEST_OPERATOR')
