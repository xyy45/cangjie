from pathlib import Path
import pytest
from nexus.adapters.cangjie.report_parser import parse_test_report

ROOT = Path(__file__).resolve().parents[1]


def test_real_sdk_reports():
    good = parse_test_report((ROOT/'tests/data/cjpm-1.0.5-pass.txt').read_text())
    bad = parse_test_report((ROOT/'tests/data/cjpm-1.0.5-fail.txt').read_text())
    assert good.state == 'PASS' and good.counts['total'] == 11
    assert bad.state == 'FAIL' and bad.counts['failed'] == 1


def test_zero_or_skipped_tests_not_pass():
    for text in ('Summary: TOTAL: 0\n PASSED: 0, SKIPPED: 0, ERROR: 0\n FAILED: 0\ncjpm test success',
                 'Summary: TOTAL: 1\n PASSED: 0, SKIPPED: 1, ERROR: 0\n FAILED: 0\ncjpm test success',
                 'Summary: TOTAL: 1\n PASSED: 1, SKIPPED: 0, ERROR: 0\n FAILED: 0'):
        assert parse_test_report(text).state == 'UNKNOWN'



def test_sdk_process_error_is_unknown_not_repairable_failure():
    text='Summary: TOTAL: 1\n PASSED: 0, SKIPPED: 0, ERROR: 1\n FAILED: 0\nError: cjpm test failed'
    assert parse_test_report(text).state=='UNKNOWN'


def test_success_counts_with_failure_footer_are_unknown():
    text = 'Summary: TOTAL: 1\n PASSED: 1, SKIPPED: 0, ERROR: 0\n FAILED: 0\nError: cjpm test failed'
    assert parse_test_report(text).state == 'UNKNOWN'
