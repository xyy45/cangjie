"""Construct feedback from an identified MCP candidate and its real failed checks."""
from nexus.contracts import CandidateRecord, CheckResult, RepairFeedback
from nexus.repair.counterexamples import failure_cases


def build_feedback(candidate: CandidateRecord, diff: dict, build: dict, test: dict, *,
                   remaining_budget: int, requirement_refs: list[str],
                   diagnostics_public: bool, suite_tests: dict | None = None,
                   requirement_test_map: dict | None = None) -> RepairFeedback:
    if diff['tree_hash'] != candidate.tree_hash:
        raise ValueError('Feedback diff belongs to a different candidate tree')
    if not ((build['state'] == 'FAIL' and test['state'] == 'NOT_RUN') or
            (build['state'] == 'PASS' and test['state'] == 'FAIL')):
        raise ValueError('Feedback requires an attributable build or test failure')
    failed, snippets, cases = [], [], []
    for raw in (build, test):
        if raw['state'] == 'NOT_RUN':
            continue
        check = CheckResult.model_validate(raw)
        if check.subject_id != candidate.id or check.tree_hash != candidate.tree_hash:
            raise ValueError('Feedback check belongs to a different candidate')
        if check.state != 'FAIL':
            continue
        if diagnostics_public and check.kind == 'test':
            cases.extend(failure_cases(check, suite_tests=suite_tests or {},
                requirement_test_map=requirement_test_map or {}))
        failed.append(check.model_dump(include={'id','subject_id','tree_hash','plan_hash','kind',
            'state','counts','exit_code','log_ref'}))
        text = check.diagnostics if diagnostics_public else ''
        start = max(0, len(text)-8192)
        snippets.append(dict(kind=check.kind, log_ref=check.log_ref, source='check.diagnostics',
            visibility='PUBLIC' if diagnostics_public else 'WITHHELD',
            start_char=start, end_char=len(text), text=text[start:]))
    return RepairFeedback(previous_candidate_id=candidate.id, baseline_hash=candidate.baseline_hash,
        tree_hash=candidate.tree_hash, diff=diff['diff'], edited_files=candidate.edits,
        failed_checks=failed, diagnostic_snippets=snippets, requirement_refs=requirement_refs,
        failure_cases=cases, remaining_budget=remaining_budget)
