"""Scoped evidence must survive record reload and reject stale/tampered bytes."""
import asyncio,importlib,json,time
from copy import deepcopy
import pytest
from nexus.contracts import CheckResult,source_manifest,digest
from tests.test_package_dependencies import fixture
from tests.test_package_scan import index_for
from tests.test_package_runner import transport
from tests.test_package_reports import IDS


def api():return importlib.import_module('nexus.repair.package_evidence')


def test_legacy_check_dump_omits_optional_package_evidence_even_nested():
    record=CheckResult(state='PASS')
    assert 'package_evidence' not in record.model_dump()
    assert 'package_evidence' not in json.loads(record.model_dump_json())
    scoped=CheckResult(state='UNKNOWN',package_evidence={'version':1})
    assert scoped.model_dump()['package_evidence']=={'version':1}
    assert CheckResult.model_validate(scoped.model_dump()).model_dump()==scoped.model_dump()


def evidence_fixture(tmp_path,monkeypatch,*,passed=False):
    from nexus.execution import runner,package_validation as execution
    root,graph,packet=fixture(tmp_path);index=index_for(graph)
    async def scan_transport(project,directory,*,deadline,private_root,output_limit):
        name='bench'+('.'+directory.name if directory.name!='src' else '')
        value=packet if name=='bench' else dict(package=name,isMacro=False,accessLevel='public',dependencies=[])
        from nexus.adapters.cangjie.sdk import SDK
        from nexus.execution.runner import execution_profile
        import hashlib
        return dict(exit_code=0,problem=None,stdout=json.dumps(value).encode(),stderr=b'',
            argv=[str(SDK/'bin/cjc'),'--scan-dependency','-p',str(directory)],
            profile_sha256=hashlib.sha256(execution_profile(root,phase='compile',private_root=tmp_path).encode()).hexdigest())
    monkeypatch.setattr(execution,'_scan_process',scan_transport)
    monkeypatch.setattr(runner,'_run_original_phase',transport(root))
    scanned=asyncio.run(execution.scan(root,index,deadline=time.monotonic()+30,private_root=tmp_path))
    result=asyncio.run(execution.run_scoped_tests(root,expected=IDS,deadline=time.monotonic()+30,private_root=tmp_path))
    if passed:
        from xml.etree import ElementTree as ET
        from tests.test_package_reports import summary
        from nexus.adapters.cangjie.scoped_reports import tests
        for name,raw in result['reports'].items():
            tree=ET.fromstring(raw);tree.set('failures','0')
            for case in tree:
                for child in list(case):
                    if child.tag=='failure':case.remove(child)
            result['reports'][name]=ET.tostring(tree,encoding='utf-8')
        result.update(exit_code=0,stdout=('EXPLICIT COMPILE/SDK FIXTURE\n'+summary(passed=2,failed=0)).encode())
        result['parsed']=tests(result['reports'],expected=IDS,stdout=result['stdout'].decode(),exit_code=0)
    (tmp_path/'records').mkdir()
    proof=api().capture(tmp_path,project=root,index=index,scanned=scanned,execution=result)
    return root,index,proof


def rebuild(root,index,proof):
    from nexus.execution.package_validation import tool_identity
    return api().rebuild(root.parent,project=root,index=index,evidence=proof,expected=IDS,tools=tool_identity())


def test_saved_scans_and_xml_rebuild_real_failure_before_reporting_failure(tmp_path,monkeypatch):
    root,index,proof=evidence_fixture(tmp_path,monkeypatch)
    parsed=rebuild(root,index,proof)
    assert parsed['state']=='FAIL' and parsed['case_results']==dict(zip(IDS,['FAIL','PASS']))
    assert parsed['failures'][IDS[0]][0]['source']['report']=='test-bench.Cases.xml'
    assert proof['graph_hash']==index['graph_hash']
    assert proof['input_manifest']==source_manifest(root)


@pytest.mark.parametrize('change',['graph','index','source','scan-stdout','scan-stderr','xml','xml-path','xml-link',
    'xml-hardlink','xml-missing','xml-extra','scan-missing','scan-argv','test-argv','tools','binary','scope-mode','case-coverage'])
def test_evidence_rebuild_invalidates_every_changed_dependency_even_for_failed_check(tmp_path,monkeypatch,change):
    root,index,proof=evidence_fixture(tmp_path,monkeypatch);proof=deepcopy(proof)
    if change=='graph':proof['graph_hash']='f'*64
    elif change=='index':index={**index,'package':'other'}
    elif change=='source':(root/'src/order.cj').write_bytes(b'changed')
    elif change=='scan-stdout':(tmp_path/proof['scans'][0]['stdout']['ref']).write_bytes(b'{}')
    elif change=='scan-stderr':(tmp_path/proof['scans'][0]['stderr']['ref']).write_bytes(b'changed')
    elif change=='xml':(tmp_path/next(iter(proof['test']['reports'].values()))['ref']).write_bytes(b'<bad/>')
    elif change=='xml-path':next(iter(proof['test']['reports'].values()))['ref']='../outside'
    elif change=='xml-link':
        path=tmp_path/next(iter(proof['test']['reports'].values()))['ref'];other=tmp_path/'elsewhere';path.replace(other);path.symlink_to(other)
    elif change=='xml-hardlink':
        import os
        os.link(tmp_path/next(iter(proof['test']['reports'].values()))['ref'],tmp_path/'elsewhere')
    elif change=='xml-missing':proof['test']['reports'].pop(next(iter(proof['test']['reports'])))
    elif change=='xml-extra':proof['test']['reports']['test-bench.Foreign.xml']=next(iter(proof['test']['reports'].values()))
    elif change=='scan-missing':proof['scans'].pop()
    elif change=='scan-argv':proof['scans'][0]['argv'].append('--arbitrary')
    elif change=='test-argv':proof['test']['execution_argv'][1].append('--arbitrary')
    elif change=='tools':proof['tools']['bin/cjc']='0'*64
    elif change=='binary':proof['test']['binary_after']={}
    elif change=='scope-mode':proof['parser']='LEGACY_COUNTS_ONLY'
    elif change=='case-coverage':proof['expected']=IDS[:1]
    assert rebuild(root,index,proof)['state']=='UNKNOWN'


def test_capture_creates_distinct_immutable_record_files_and_rejects_record_directory_link(tmp_path,monkeypatch):
    root,index,proof=evidence_fixture(tmp_path,monkeypatch)
    refs=[s[k]['ref'] for s in proof['scans'] for k in ('stdout','stderr')]
    refs.extend(r['ref'] for r in proof['test']['reports'].values())
    assert len(refs)==len(set(refs))
    directory=tmp_path/'records';outside=tmp_path/'outside-records';directory.replace(outside);directory.symlink_to(outside,target_is_directory=True)
    assert rebuild(root,index,proof)['state']=='UNKNOWN'


def test_record_rebuild_binds_report_log_cases_and_suites_before_reusing_failed_cache(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from nexus.repair.verification_evidence import public_evidence
    from nexus.execution.package_validation import tool_identity
    root,index,proof=evidence_fixture(tmp_path,monkeypatch)
    tools=tool_identity();toolchain=digest({'cjc':tools['bin/cjc'],'cjpm':tools['tools/bin/cjpm']})
    record=CheckResult(schema_version=2,id='check',subject_id='subject',state='FAIL',exit_code=1,
        argv=['cjpm','test'],working_root='.',spec_hash='spec',verification_plan_hash='plan',toolchain_hash=toolchain,
        package_evidence=proof,counts=rebuild(root,index,proof)['counts'],case_results=dict(zip(IDS,['FAIL','PASS'])),
        tree_hash=digest(source_manifest(root)),execution_argv=proof['test']['execution_argv'],
        log_ref='records/check.log',report_ref='records/check.report.json')
    # Record log is the exact merged compile/test SDK output, separately retained.
    raw=(tmp_path/proof['test']['stdout']['ref']).read_bytes();record.diagnostics=raw.decode()[-16000:]
    (tmp_path/record.log_ref).write_bytes(raw);(tmp_path/record.report_ref).write_text(record.model_dump_json())
    store=SimpleNamespace(root=tmp_path)
    task=SimpleNamespace(spec_hash='spec',verification_plan_hash='plan')
    plan=SimpleNamespace(toolchain_id=toolchain,suite_tests={'target':IDS[:1],'regression':IDS[1:]},required_suites=['target','regression'])
    from nexus.adapters.cangjie.report_parser import project_suites
    record.suite_results=project_suites(record,plan.suite_tests)
    (tmp_path/record.report_ref).write_text(record.model_dump_json())
    monkeypatch.setattr(api(),'subject_context',lambda *_:dict(project=root,index=index,expected=IDS))
    result=public_evidence(store,record.model_dump(),task,plan)
    assert result['state']=='FAIL'
    (tmp_path/proof['test']['reports']['test-bench.Cases.xml']['ref']).write_bytes(b'<bad/>')
    assert public_evidence(store,record.model_dump(),task,plan)['state']=='UNKNOWN'
