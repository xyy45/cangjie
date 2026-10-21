"""Conservative extraction from pinned cjpm diagnostics; never execute expressions."""
import re

ANSI = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|[78])')
CASE = re.compile(r'^\s*\[\s*(PASSED|FAILED|SKIPPED|ERROR)\s*\] CASE:\s*(\w+)\s+\([^)]*\)\s*$', re.M)
ASSERTION = re.compile(r'^\s*Expect Failed: `\(([^\n`]{1,2000}) == [^\n`]{1,1000}\)`\s*\n[ \t]*left: ([^\n]{1,1000})\n[ \t]*right: ([^\n]{1,1000})', re.M)
LITERAL_CALL = re.compile(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\(\s*(?:-?\s*\d+|true|false)(?:\s*,\s*(?:-?\s*\d+|true|false))*\s*\)')


def failure_cases(check, *, suite_tests, requirement_test_map):
    """Values refer to equality Expect(actual, expected); other formats stay unknown.

    Offsets index ANSI-stripped check.diagnostics, not raw log file bytes.
    Test identifiers must already be confirmed by the verifier's case_results.
    """
    text = ANSI.sub('', check.diagnostics)
    detail = text.split('Summary:', 1)[0]
    sections = {}
    suite = None
    tokens = list(re.finditer(r'^.*\bTCS:\s*(\w+),[^\n]*$|^\s*\[\s*(?:PASSED|FAILED|SKIPPED|ERROR)\s*\] CASE:\s*\w+\s+\([^)]*\)\s*$', detail, re.M))
    for index, token in enumerate(tokens):
        if token.group(1):
            suite = token.group(1)
            continue
        case = CASE.fullmatch(token.group())
        if suite and case and case.group(1) == 'FAILED':
            identity = suite + '.' + case.group(2)
            sections.setdefault(identity, (token.end(), tokens[index+1].start() if index+1<len(tokens) else len(detail)))
    result = []
    for identity, state in check.case_results.items():
        if state != 'FAIL':
            continue
        start, end = sections.get(identity, (0, 0))
        found = ASSERTION.search(detail[start:end]) if end else None
        expression = found.group(1).strip() if found else None
        suites = [name for name, tests in suite_tests.items() if identity in tests]
        refs = [ref for ref, names in requirement_test_map.items() if set(names).intersection(suites)]
        result.append(dict(kind='test', test_id=identity, expression=expression,
            input=expression if expression and LITERAL_CALL.fullmatch(expression) else None,
            actual=found.group(2).strip() if found else None, expected=found.group(3).strip() if found else None,
            requirement_refs=refs, mapping_basis='TEST_SUITE' if refs else 'UNMAPPED',
            source=dict(log_ref=check.log_ref, coordinate='ANSI_STRIPPED_CHECK_DIAGNOSTICS',
                start_char=start+found.start() if found else start, end_char=start+found.end() if found else end)))
        if len(result) == 50:
            break
    return result
