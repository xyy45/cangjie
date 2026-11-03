"""Explicit XML/summary fixtures, not evidence of an SDK execution."""
import importlib
import pytest

IDS=['bench.Cases.case0','bench.money.Cases.case0']


def api():return importlib.import_module('nexus.adapters.cangjie.scoped_reports')


def xml(suite,state='PASS',text='Expect Failed: `(total(3) == 9)`\n   left: 8\n  right: 9\n'):
    status={'PASS':('',0,0,0),'FAIL':('<failure>'+text+'</failure>',1,0,0),
            'ERROR':('<error>runtime error</error>',0,1,0),'SKIPPED':('<skipped/>',0,0,1)}[state]
    body,failed,errors,skipped=status
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<testsuite name="'+suite+'" tests="1" failures="'+str(failed)+'" errors="'+str(errors)+'" skipped="'+str(skipped)+'" time="0.00001" timestamp="2026-10-31T00:00:00Z">\n'
        '<testcase name="case0" classname="'+suite+'" assertions="1" time="0.00001">'+body+'</testcase>\n</testsuite>\n').encode()


def summary(*,passed=1,failed=1,errors=0,skipped=0):
    return f'EXPLICIT SDK SUMMARY FIXTURE\nSummary: TOTAL: {passed+failed+errors+skipped}\n PASSED: {passed}, SKIPPED: {skipped}, ERROR: {errors}\n FAILED: {failed}\n'+('cjpm test success\n' if not failed and not errors else 'Error: cjpm test failed\n')


def reports():return {'test-bench.Cases.xml':xml('bench.Cases','FAIL'),'test-bench.money.Cases.xml':xml('bench.money.Cases')}


def parse(rows=None,expected=None,stdout=None,code=1):
    return api().tests(reports() if rows is None else rows,expected=IDS if expected is None else expected,
                       stdout=summary() if stdout is None else stdout,exit_code=code)


def test_same_class_and_case_names_keep_package_identity_and_failure_text():
    result=parse()
    assert result['state']=='FAIL'
    assert result['case_results']==dict(zip(IDS,['FAIL','PASS']))
    assert result['counts']==dict(total=2,passed=1,failed=1,errors=0,skipped=0)
    failure=result['failures'][IDS[0]][0]
    assert 'left: 8' in failure['text'] and 'right: 9' in failure['text']
    assert failure['source']==dict(report='test-bench.Cases.xml',case_id=IDS[0],failure_index=0,coordinate='XML_FAILURE_TEXT',start_char=0,end_char=len(failure['text']))


def test_all_required_xml_cases_and_process_summary_are_needed_for_pass():
    rows={name:xml(name.removeprefix('test-').removesuffix('.xml')) for name in reports()}
    result=parse(rows,stdout=summary(passed=2,failed=0),code=0)
    assert result['state']=='PASS' and result['case_results']==dict.fromkeys(IDS,'PASS')
    assert result['failures']=={}


@pytest.mark.parametrize('change',['missing-file','extra-file','duplicate-case','wrong-class','wrong-case','foreign-suite','bad-filename','traversal-filename','bad-count','huge-count','duplicate-expected','empty-expected','no-summary','wrong-summary','bad-exit','bool-exit','bad-encoding','bad-declaration','truncated','invalid-control','unknown-root','unknown-child','conflicting-status','empty-reports','too-many-files','too-large'])
def test_incomplete_foreign_malformed_or_unbound_reports_are_unknown(change):
    rows=reports();expected=IDS;out=summary();code=1;root=rows['test-bench.Cases.xml']
    if change=='missing-file':rows.pop('test-bench.money.Cases.xml')
    elif change=='extra-file':rows['test-bench.Other.xml']=xml('bench.Other')
    elif change=='duplicate-case':root=root.replace(b'</testsuite>',b'<testcase name="case0" classname="bench.Cases" assertions="0"/></testsuite>')
    elif change=='wrong-class':root=root.replace(b'classname="bench.Cases"',b'classname="bench.Other"')
    elif change=='wrong-case':root=root.replace(b'name="case0"',b'name="other"')
    elif change=='foreign-suite':root=root.replace(b'bench.Cases',b'other.Cases')
    elif change=='bad-filename':rows['test-other.xml']=rows.pop('test-bench.money.Cases.xml')
    elif change=='traversal-filename':rows['../test-bench.money.Cases.xml']=rows.pop('test-bench.money.Cases.xml')
    elif change=='bad-count':root=root.replace(b'failures="1"',b'failures="0"')
    elif change=='huge-count':root=root.replace(b'tests="1"',b'tests="'+b'9'*5000+b'"')
    elif change=='duplicate-expected':expected=IDS+[IDS[0]]
    elif change=='empty-expected':expected=[]
    elif change=='no-summary':out='cjpm test success\n'
    elif change=='wrong-summary':out=summary(passed=2,failed=0)
    elif change=='bad-exit':code=0
    elif change=='bool-exit':code=True
    elif change=='bad-encoding':root+=b'\xff'
    elif change=='bad-declaration':root=root.replace(b'UTF-8',b'ISO-8859-1')
    elif change=='truncated':root=root[:-15]
    elif change=='invalid-control':root=root.replace(b'Expect Failed',b'\0Expect Failed')
    elif change=='unknown-root':root=root.replace(b'testsuite',b'testsuites')
    elif change=='unknown-child':root=root.replace(b'<failure>',b'<passed><failure>').replace(b'</failure>',b'</failure></passed>')
    elif change=='conflicting-status':root=root.replace(b'</failure>',b'</failure><skipped/>')
    elif change=='empty-reports':rows={}
    elif change=='too-many-files':rows={f'test-bench.C{i}.xml':xml(f'bench.C{i}') for i in range(258)}
    else:root+=b' '*(2*1024*1024)
    if change not in ('empty-reports','too-many-files'):rows['test-bench.Cases.xml']=root
    result=parse(rows,expected,out,code)
    assert result['state']=='UNKNOWN'


@pytest.mark.parametrize('state',['ERROR','SKIPPED'])
def test_real_error_or_skip_remains_unknown_even_with_complete_reports(state):
    rows=reports();rows['test-bench.Cases.xml']=xml('bench.Cases',state)
    result=parse(rows,stdout=summary(passed=1,failed=0,errors=int(state=='ERROR'),skipped=int(state=='SKIPPED')),code=1 if state=='ERROR' else 0)
    assert result['state']=='UNKNOWN' and result['case_results'][IDS[0]] in ('UNKNOWN','NOT_RUN')


def test_actual_dtd_and_entities_are_rejected_but_opaque_failure_text_is_preserved():
    rows=reports();body=rows['test-bench.Cases.xml']
    rows['test-bench.Cases.xml']=body.replace(b'<testsuite ',b'<!DOCTYPE testsuite [<!ENTITY fake "text">]><testsuite ',1)
    assert parse(rows)['state']=='UNKNOWN'
    for text in ('&lt;!DOCTYPE user-text&gt;','<![CDATA[<!DOCTYPE user-text>]]>'):
        rows=reports();rows['test-bench.Cases.xml']=xml('bench.Cases','FAIL',text)
        result=parse(rows)
        assert result['state']=='FAIL' and result['failures'][IDS[0]][0]['text']=='<!DOCTYPE user-text>'


def test_multiple_assertion_failures_count_as_one_failed_case_and_all_messages_survive():
    rows=reports();rows['test-bench.Cases.xml']=rows['test-bench.Cases.xml'].replace(b'</failure>',b'</failure><failure>second assertion</failure>')
    result=parse(rows)
    assert result['state']=='FAIL' and result['counts']['failed']==1
    assert len(result['failures'][IDS[0]])==2


def test_generated_verification_namespace_can_be_decoded_but_never_creates_source_authority():
    suite='bench.nexus_verify_0123456789abcdef.NexusOracleV50123456789abcdef';expected=[suite+'.case0']
    result=parse({'test-'+suite+'.xml':xml(suite)},expected,summary(passed=1,failed=0),0)
    assert result['state']=='PASS' and set(result['case_results'])==set(expected)


def test_nested_xml_and_excessive_expected_cases_are_bounded():
    rows=reports();rows['test-bench.Cases.xml']=rows['test-bench.Cases.xml'].replace(b'<failure>',b'<failure>'+b'<x>'*100).replace(b'</failure>',b'</x>'*100+b'</failure>')
    assert parse(rows)['state']=='UNKNOWN'
    assert parse(expected=[f'bench.Cases.case{i}' for i in range(289)])['state']=='UNKNOWN'
