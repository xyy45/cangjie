import pytest
from nexus.contracts import CandidateRecord, Edit
from nexus.repair.feedback import build_feedback


def records():
    candidate = CandidateRecord(id='c_'+'a'*32, task_id='task', baseline_hash='b'*64,
        edits=[Edit(path='src/a.cj', before_hash='c'*64, content='package changed')],
        tree_hash='d'*64, diff_ref='records/changes.diff', attempt=1)
    diff = {'tree_hash': candidate.tree_hash, 'diff': '--- a/src/a.cj\n+++ b/src/a.cj\n+package changed\n'}
    build = {'kind':'build','state':'PASS','tree_hash':candidate.tree_hash,'subject_id':candidate.id}
    test = {'kind':'test','state':'FAIL','tree_hash':candidate.tree_hash,'subject_id':candidate.id,
            'diagnostics':'zeroQuantity failed at src/a.cj:3', 'log_ref':'records/test.log',
            'counts':{'total':11,'passed':10,'failed':1}, 'exit_code':1}
    return candidate, diff, build, test


def test_feedback_contains_same_candidate_diff_code_baseline_hash_and_failure():
    c,d,b,t = records()
    feedback = build_feedback(c,d,b,t,remaining_budget=2,requirement_refs=['REQ-QTY'],diagnostics_public=True)
    assert feedback.schema_version == 1
    assert feedback.previous_candidate_id == c.id and feedback.tree_hash == c.tree_hash
    assert feedback.baseline_hash == c.baseline_hash and feedback.diff == d['diff']
    assert feedback.edited_files == c.edits
    assert feedback.edited_files[0].before_hash == 'c'*64  # Still the baseline, not the previous candidate.
    assert feedback.failed_checks[0]['kind'] == 'test'
    assert feedback.diagnostic_snippets[0]['text'] == t['diagnostics']
    assert feedback.requirement_refs == ['REQ-QTY'] and feedback.remaining_budget == 2


def test_feedback_rejects_foreign_diff_checks_or_unreliable_failure():
    c,d,b,t = records()
    for altered_diff, altered_test in [({**d,'tree_hash':'0'*64},t),
        (d,{**t,'tree_hash':'0'*64}),(d,{**t,'subject_id':'foreign'}),
        (d,{**t,'state':'UNKNOWN'}),(d,{**t,'state':'NOT_RUN'}),(d,{**t,'state':'PASS'})]:
        with pytest.raises(ValueError):
            build_feedback(c,altered_diff,b,altered_test,remaining_budget=2,
                           requirement_refs=['REQ-QTY'],diagnostics_public=True)


def test_private_diagnostics_are_withheld_and_public_snippet_range_is_recorded():
    c,d,b,t = records()
    private = build_feedback(c,d,b,{**t,'diagnostics':'hidden expected answer'},remaining_budget=2,
                             requirement_refs=['REQ-QTY'],diagnostics_public=False)
    assert 'hidden expected answer' not in private.model_dump_json()
    assert private.diagnostic_snippets[0]['visibility'] == 'WITHHELD'
    long = 'a'*10000+'\nzeroQuantity failed'
    public = build_feedback(c,d,b,{**t,'diagnostics':long},remaining_budget=2,
                            requirement_refs=['REQ-QTY'],diagnostics_public=True)
    snippet = public.diagnostic_snippets[0]
    assert len(snippet['text']) <= 8192
    assert snippet['end_char'] == len(long) and snippet['start_char'] > 0
    assert snippet['text'].endswith('zeroQuantity failed')
    assert 'diagnostics' not in public.failed_checks[0]


FAILURE_LOG = '''TCS: OrderTests, time elapsed: 10 ns, RESULT:
    [ FAILED ] CASE: zeroQuantity (5 ns)
    Expect Failed: `(processOrder(0, 100) == - 1)`
       left: 0
      right: -1
    [ PASSED ] CASE: normal (5 ns)
Summary: TOTAL: 2 PASSED: 1, SKIPPED: 0, ERROR: 0 FAILED: 1
Error: cjpm test failed'''


def test_real_assertion_values_and_suite_mapping_are_sent_as_bound_feedback():
    c,d,b,t=records()
    t.update(case_results={'OrderTests.zeroQuantity':'FAIL','OrderTests.normal':'PASS'},diagnostics=FAILURE_LOG)
    feedback=build_feedback(c,d,b,t,remaining_budget=2,requirement_refs=['REQ-QTY'],diagnostics_public=True,
        suite_tests={'target':['OrderTests.zeroQuantity'],'regression':['OrderTests.normal']},
        requirement_test_map={'REQ-QTY':['target'],'REQ-OTHER':['regression']})
    item=feedback.failure_cases[0]
    assert item['test_id']=='OrderTests.zeroQuantity'
    assert item['input']=='processOrder(0, 100)' and item['actual']=='0' and item['expected']=='-1'
    assert item['requirement_refs']==['REQ-QTY'] and item['mapping_basis']=='TEST_SUITE'
    assert item['source']['log_ref']=='records/test.log'
    raw=FAILURE_LOG[item['source']['start_char']:item['source']['end_char']]
    assert 'left: 0' in raw and 'right: -1' in raw
    assert feedback.previous_candidate_id==c.id and feedback.tree_hash==c.tree_hash


def test_unknown_assertion_format_keeps_case_without_inventing_values_and_hides_private_data():
    c,d,b,t=records()
    t.update(case_results={'OrderTests.zeroQuantity':'FAIL'},diagnostics='unknown test failure')
    public=build_feedback(c,d,b,t,remaining_budget=1,requirement_refs=['REQ-QTY'],diagnostics_public=True)
    item=public.failure_cases[0]
    assert item['input'] is None and item['expected'] is None and item['actual'] is None
    assert item['requirement_refs']==[] and item['mapping_basis']=='UNMAPPED'
    private=build_feedback(c,d,b,{**t,'diagnostics':FAILURE_LOG},remaining_budget=1,
        requirement_refs=['REQ-QTY'],diagnostics_public=False)
    assert private.failure_cases==[] and 'zeroQuantity' not in private.model_dump_json()


def test_summary_duplicates_ansi_and_unverified_cases_cannot_invent_extra_counterexamples():
    c,d,b,t=records()
    t.update(case_results={'OrderTests.zeroQuantity':'FAIL'},diagnostics=FAILURE_LOG.replace('FAILED','\x1b[31mFAILED\x1b[0m')+
        '\nTCS: Fake,\n [ FAILED ] CASE: invented (1 ns)\n Expect Failed: `(evil(1) == 2)`\n left: 1\n right: 2')
    feedback=build_feedback(c,d,b,t,remaining_budget=0,requirement_refs=['REQ-QTY'],diagnostics_public=True)
    assert len(feedback.failure_cases)==1 and feedback.failure_cases[0]['actual']=='0'


def test_variable_expressions_are_not_reported_as_observed_runtime_inputs():
    c,d,b,t=records()
    t.update(case_results={'OrderTests.zeroQuantity':'FAIL'},diagnostics=FAILURE_LOG.replace('processOrder(0, 100)','processOrder(quantity, price)'))
    feedback=build_feedback(c,d,b,t,remaining_budget=1,requirement_refs=['REQ-QTY'],diagnostics_public=True)
    item=feedback.failure_cases[0]
    assert item['input'] is None and item['expression']=='processOrder(quantity, price)'
    assert item['expected']=='-1' and item['actual']=='0'
