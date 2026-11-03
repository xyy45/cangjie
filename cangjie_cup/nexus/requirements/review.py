"""Finite requirement projection, not a semantic correctness proof."""
from nexus.contracts import CheckResult, RequirementSpec, VerificationPlan


def assess_requirements(spec: RequirementSpec, plan: VerificationPlan, test: CheckResult, *, build_state: str) -> list[dict]:
    results=[]
    for requirement in spec.requirements:
        names=plan.requirement_test_map.get(requirement.id,[])
        states=[test.suite_results.get(name,{}).get('state','UNKNOWN') for name in names]
        status='UNKNOWN'
        if not names or any(name not in plan.required_suites for name in names):
            status='UNMAPPED'
        elif build_state=='PASS' and test.state in ('PASS','FAIL'):
            if any(s=='FAIL' for s in states):
                status='FAILED'
            elif states and all(s=='PASS' for s in states):
                status='SATISFIED_BY_TESTS'
        results.append(dict(id=requirement.id,text=requirement.text,status=status,suites=names))
    return results
