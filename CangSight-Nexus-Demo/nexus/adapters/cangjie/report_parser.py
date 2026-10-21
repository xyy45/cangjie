"""Parse the complete final summary emitted by pinned cjpm 1.0.5."""
import re
from nexus.contracts import CheckResult

ANSI = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|[78])')
SUMMARY = re.compile(r'Summary: TOTAL:\s*(\d+)\s+PASSED:\s*(\d+),\s*SKIPPED:\s*(\d+),\s*ERROR:\s*(\d+)\s+FAILED:\s*(\d+)')


def parse_test_report(text: str) -> CheckResult:
    clean = ANSI.sub('', text)
    matches = list(SUMMARY.finditer(clean))
    if not matches or not re.search(r'(cjpm test success|Error: cjpm test failed)\s*$', clean):
        return CheckResult(state='UNKNOWN', diagnostics='Incomplete or unrecognized test log')
    total, passed, skipped, errors, failed = map(int, matches[-1].groups())
    counts = dict(total=total, passed=passed, skipped=skipped, errors=errors, failed=failed)
    state = 'UNKNOWN'
    if total > 0 and total == passed + skipped + errors + failed:
        if errors:
            state = 'UNKNOWN'
        elif failed:
            state = 'FAIL'
        elif not skipped and passed == total and clean.rstrip().endswith('cjpm test success'):
            state = 'PASS'
    cases = {}
    suite = None
    valid = True
    # Later summaries repeat failures; only the first detailed package section
    # contributes case items for this pinned small-project profile.
    for line in clean[:matches[0].start()].splitlines():
        header = re.search(r'\bTCS:\s*(\w+),', line)
        if header:
            suite = header.group(1)
        item = re.search(r'^\s*\[\s*(PASSED|FAILED|SKIPPED|ERROR)\s*\] CASE:\s*(\w+)\s+\([^)]*\)\s*$',line)
        if item:
            if not suite or suite+'.'+item.group(2) in cases:
                valid = False
                continue
            cases[suite+'.'+item.group(2)] = {'PASSED':'PASS','FAILED':'FAIL','SKIPPED':'NOT_RUN','ERROR':'UNKNOWN'}[item.group(1)]
    if (not valid or len(cases)!=total or sum(v=='PASS' for v in cases.values())!=passed or
        sum(v=='FAIL' for v in cases.values())!=failed or sum(v=='NOT_RUN' for v in cases.values())!=skipped or
        sum(v=='UNKNOWN' for v in cases.values())!=errors):
        cases = {}
    return CheckResult(state=state, counts=counts, case_results=cases, diagnostics=clean[-16000:])


def project_suites(check: CheckResult, suite_tests: dict[str,list[str]]) -> dict[str,dict]:
    results = {}
    for name, expected in suite_tests.items():
        states = [check.case_results.get(case,'UNKNOWN') for case in expected]
        state = 'UNKNOWN'
        if expected and check.state in ('PASS','FAIL') and not any(s in ('UNKNOWN','NOT_RUN') for s in states):
            state = 'FAIL' if 'FAIL' in states else 'PASS'
        results[name] = dict(state=state,tests=list(expected),passed=states.count('PASS'),
                             failed=states.count('FAIL'),unknown=states.count('UNKNOWN'),skipped=states.count('NOT_RUN'))
    return results
