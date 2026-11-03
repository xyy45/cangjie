from pathlib import Path
from nexus.adapters.cangjie.report_parser import parse_test_report, project_suites

ROOT=Path(__file__).resolve().parents[1]


def test_pinned_sdk_case_items_support_real_suite_projection():
    passed=parse_test_report((ROOT/'tests/data/cjpm-1.0.5-pass.txt').read_text())
    failed=parse_test_report((ROOT/'tests/data/cjpm-1.0.5-fail.txt').read_text())
    assert len(passed.case_results)==11
    assert failed.case_results['OrderTests.zeroQuantity']=='FAIL'
    expected={'target':['OrderTests.zeroQuantity','OrderTests.upperQuantity'],
              'regression':['OrderTests.three','OrderTests.differentPrice']}
    assert project_suites(passed,expected)['target']['state']=='PASS'
    suites=project_suites(failed,expected)
    assert suites['target']['state']=='FAIL' and suites['regression']['state']=='PASS'


def test_summary_alone_missing_cases_or_duplicate_items_do_not_prove_a_suite():
    log=(ROOT/'tests/data/cjpm-1.0.5-pass.txt').read_text()
    summary='Summary: TOTAL: 11\n PASSED: 11, SKIPPED: 0, ERROR: 0\n FAILED: 0\ncjpm test success'
    for text in (summary,log.replace('CASE: zeroQuantity','CASE: unknown'),
                 log.replace('CASE: zeroQuantity','CASE: three')):
        check=parse_test_report(text)
        assert project_suites(check,{'target':['OrderTests.zeroQuantity']})['target']['state']=='UNKNOWN'
