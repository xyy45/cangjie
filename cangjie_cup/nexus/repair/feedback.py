"""Construct feedback from an identified MCP candidate and its real failed checks."""
from nexus.contracts import CandidateRecord, CheckResult, RepairFeedback
from nexus.repair.counterexamples import failure_cases,ANSI
from copy import deepcopy
from nexus.repair import values


def build_feedback(candidate: CandidateRecord, diff: dict, build: dict, test: dict, *,
                   remaining_budget: int, requirement_refs: list[str],
                   diagnostics_public: bool, suite_tests: dict | None = None,
                   requirement_test_map: dict | None = None,
                   public_failure_cases: list[dict] | None = None) -> RepairFeedback:
    if diff['tree_hash'] != candidate.tree_hash:
        raise ValueError('Feedback diff belongs to a different candidate tree')
    if not ((build['state'] == 'FAIL' and test['state'] == 'NOT_RUN') or
            (build['state'] == 'PASS' and test['state'] == 'FAIL')):
        raise ValueError('Feedback requires an attributable build or test failure')
    xml_fields=public_failure_cases is not None and test.get('package_evidence') is not None
    if public_failure_cases is not None and not ((diagnostics_public or xml_fields) and build['state']=='PASS' and test['state']=='FAIL'):
        raise ValueError('字段反馈必须属于公开失败测试')
    failed, snippets, cases = [], [], []
    for raw in (build, test):
        if raw['state'] == 'NOT_RUN':
            continue
        check = CheckResult.model_validate(raw)
        if check.subject_id != candidate.id or check.tree_hash != candidate.tree_hash:
            raise ValueError('Feedback check belongs to a different candidate')
        if check.state != 'FAIL':
            continue
        if check.kind=='test' and public_failure_cases is not None and (diagnostics_public or xml_fields):
            cases.extend(_public_fields(public_failure_cases,check))
        elif diagnostics_public and check.kind == 'test':
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


def _public_fields(cases,check):
    if type(cases) is not list or not 1<=len(cases)<=50:raise ValueError('字段反馈数量无效')
    length=len(ANSI.sub('',check.diagnostics));seen=set()
    for case in cases:
        if type(case) is not dict or case.get('kind')!='public_field' or 'actual_return' in case or check.case_results.get(case.get('test_id'))!='FAIL':raise ValueError('字段反馈不可宣称完整返回或引用其他测试')
        source=case.get('source',{})
        if source.get('coordinate')=='XML_FAILURE_TEXT':
            try:reference=check.package_evidence['test']['reports']['test-'+case['test_id'].rsplit('.',1)[0]+'.xml']
            except (TypeError,KeyError) as exc:raise ValueError('字段反馈缺少原XML绑定') from exc
            if (case.get('visibility')!='PUBLIC' or case.get('mapping_basis')!='FROZEN_SCOPED_XML_FIELD' or
                    source.get('log_ref')!=check.log_ref or source.get('case_id')!=case['test_id'] or
                    source.get('report')!='test-'+case['test_id'].rsplit('.',1)[0]+'.xml' or
                    source.get('xml_ref')!=reference['ref'] or source.get('xml_sha256')!=reference['sha256'] or
                    type(source.get('failure_index')) is not int or source['failure_index']<0 or
                    type(source.get('start_char')) is not int or type(source.get('end_char')) is not int or
                    not 0<=source['start_char']<source['end_char']<=reference['bytes']):
                raise ValueError('字段反馈XML原件、公开性或坐标不符')
        elif (source.get('log_ref')!=check.log_ref or source.get('coordinate')!='ANSI_STRIPPED_CHECK_DIAGNOSTICS' or
                type(source.get('start_char')) is not int or type(source.get('end_char')) is not int or not 0<=source['start_char']<source['end_char']<=length):raise ValueError('字段反馈日志坐标无效')
        identity=case.get('call_id')
        if type(identity) is not str or identity in seen:raise ValueError('字段反馈ID无效或重复')
        seen.add(identity);kind=case.get('value_type');values.primitive(case.get('expected_value'),kind)
        if case.get('value_state')=='TYPED':values.primitive(case.get('actual_value'),kind)
        elif not (case.get('value_state')=='TEXT_ONLY' and kind=='String' and case.get('actual_value') is None):raise ValueError('字段实际值语义无效')
    return deepcopy(cases)
