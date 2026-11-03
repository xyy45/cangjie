"""Fixed XML test orchestration; explicit byte/binary transport fixtures."""
import asyncio,hashlib,importlib,time
from pathlib import Path
import pytest
from tests.test_package_dependencies import fixture
from tests.test_package_reports import IDS,reports,summary


def api():return importlib.import_module('nexus.execution.package_validation')


def transport(root,*,change=None):
    async def phase(project,argv,profile,env,*,timeout,output_limit):
        binary=project/'target/release/unittest_bin/bench';binary.parent.mkdir(parents=True,exist_ok=True)
        if '--no-run' in argv:
            binary.write_bytes(b'\xcf\xfa\xed\xfeFIXTURE_NOT_EXECUTED');binary.chmod(0o700)
            return 0,b'compile fixture\n',None
        assert argv[:3]==['cjpm','test','--skip-build']
        assert argv[-2:]==['--report-format','xml']
        directory=Path(argv[argv.index('--report-path')+1])/'tests';directory.mkdir()
        for name,raw in reports().items():(directory/name).write_bytes(raw)
        if change=='missing':(directory/'test-bench.Cases.xml').unlink()
        elif change=='extra':(directory/'other.xml').write_bytes(b'<bad/>')
        elif change=='symlink':
            path=directory/'test-bench.Cases.xml';other=root.parent/'outside.xml';path.replace(other);path.symlink_to(other)
        elif change=='hardlink':
            import os
            os.link(directory/'test-bench.Cases.xml',root.parent/'other.xml')
        elif change=='nested':
            other=directory/'nested';other.mkdir();(other/'unknown.xml').write_bytes(b'<bad/>')
        elif change=='source':(root/'src/order.cj').write_bytes(b'changed')
        elif change=='binary':binary.write_bytes(b'changed')
        elif change=='output':return 1,b'x'*(2*1024*1024+1),None
        elif change=='bad-utf8':return 1,b'\xff'+summary().encode(),None
        return 1,summary().encode(),None
    return phase


def run(root,monkeypatch,*,change=None,budget=2*1024*1024):
    from nexus.execution import runner
    monkeypatch.setattr(runner,'_run_original_phase',transport(root,change=change),raising=False)
    return asyncio.run(api().run_scoped_tests(root,expected=IDS,deadline=time.monotonic()+30,
        private_root=root.parent,output_limit=budget))


def test_fixed_xml_runner_preserves_complete_original_bytes_and_phase_binaries(tmp_path,monkeypatch):
    root,_,_=fixture(tmp_path);result=run(root,monkeypatch)
    assert result['parsed']['state']=='FAIL' and result['parsed']['case_results']==dict(zip(IDS,['FAIL','PASS']))
    assert result['source_before']==result['source_after']
    assert result['reports']==reports() and result['binary_before']==result['binary_after']
    assert result['execution_argv'][0]==['cjpm','test','--no-run']
    assert result['execution_argv'][1][:3]==['cjpm','test','--skip-build']
    assert all(hashlib.sha256(raw).hexdigest()==result['report_hashes'][name] for name,raw in reports().items())


@pytest.mark.parametrize('change',['missing','extra','symlink','hardlink','nested','source','binary','output','bad-utf8'])
def test_linked_partial_or_mutated_originals_cannot_complete_tests(tmp_path,monkeypatch,change):
    root,_,_=fixture(tmp_path);result=run(root,monkeypatch,change=change)
    assert result['parsed']['state']=='UNKNOWN'


def test_scan_and_xml_share_one_remaining_original_byte_budget(tmp_path,monkeypatch):
    root,_,_=fixture(tmp_path);result=run(root,monkeypatch,budget=10)
    assert result['parsed']['state']=='UNKNOWN'


def test_report_path_is_new_per_invocation_and_stale_files_cannot_satisfy_missing_run(tmp_path,monkeypatch):
    root,_,_=fixture(tmp_path);first=run(root,monkeypatch);second=run(root,monkeypatch,change='missing')
    assert first['parsed']['state']=='FAIL' and second['parsed']['state']=='UNKNOWN'
    assert first['report_directory']!=second['report_directory']


def test_read_access_time_changes_do_not_masquerade_as_xml_content_changes(tmp_path,monkeypatch):
    import os
    from types import SimpleNamespace
    from nexus.execution.runner import _xml_originals
    directory=tmp_path/'xml';tests=directory/'tests';tests.mkdir(parents=True)
    for name,raw in reports().items():(tests/name).write_bytes(raw)
    actual=os.fstat;calls=0
    def observed(fd):
        nonlocal calls
        calls+=1;value=actual(fd)
        attrs={key:getattr(value,key) for key in dir(value) if key.startswith('st_')}
        if calls%2==0:attrs['st_atime']+=1;attrs['st_atime_ns']+=1_000_000_000
        return SimpleNamespace(**attrs)
    monkeypatch.setattr(os,'fstat',observed)
    assert _xml_originals(directory,limit=2*1024*1024)==reports()
