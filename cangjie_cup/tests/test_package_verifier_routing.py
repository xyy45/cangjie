"""Scoped verifier routing/cache with explicit subprocess fixture observations."""
import asyncio,hashlib,json
from pathlib import Path
import pytest
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.adapters.cangjie.sdk import SDK
from nexus.contracts import source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.store import RunStore
from nexus.execution import package_validation,runner
from tests.test_package_dependencies import fixture
from tests.test_package_scan import index_for
from tests.test_package_runner import transport
from tests.test_package_reports import IDS


def setup(tmp_path,monkeypatch):
    original,graph,packet=fixture(tmp_path);index=index_for(graph)
    runtime=tmp_path/'runtime';ws=WorkspaceStore(runtime,registered=[original]);baseline=ws.import_project(original,'.')
    store=RunStore(runtime);task=store.create_task(baseline,'scoped transport fixture',['src/order.cj'])
    path=ws.subject_path(baseline)
    def context(self,task,subject):return dict(project=path,index=index,expected=IDS)
    monkeypatch.setattr(CangjieVerifier,'_scoped_context',context,raising=False)
    async def scan(project,directory,*,deadline,private_root,output_limit):
        name='bench'+('.'+directory.name if directory.name!='src' else '')
        value=json.loads(json.dumps(packet).replace(str(original),str(project))) if name=='bench' else dict(package=name,isMacro=False,accessLevel='public',dependencies=[])
        profile=runner.execution_profile(project,phase='compile',private_root=runtime)
        return dict(exit_code=0,problem=None,stdout=json.dumps(value).encode(),stderr=b'',
            argv=[str(SDK/'bin/cjc'),'--scan-dependency','-p',str(directory)],profile_sha256=hashlib.sha256(profile.encode()).hexdigest())
    monkeypatch.setattr(package_validation,'_scan_process',scan)
    test_transport=transport(path)
    async def phase(project,argv,profile,env,**kwargs):
        if argv==['cjpm','build','-V']:return 0,b'EXPLICIT BUILD FIXTURE\ncjpm build success\n',None
        return await test_transport(project,argv,profile,env,**kwargs)
    monkeypatch.setattr(runner,'_run_original_phase',phase,raising=False)
    async def forbid_legacy(*args,**kwargs):raise AssertionError('Scoped checks must use complete XML, not legacy text parsing')
    monkeypatch.setattr('nexus.adapters.cangjie.verifier.run_command',forbid_legacy)
    return store,task,baseline,path


def test_scoped_verifier_uses_fixed_scan_xml_and_rechecks_cached_failed_originals(tmp_path,monkeypatch):
    store,task,subject,path=setup(tmp_path,monkeypatch)
    async def run():
        verifier=CangjieVerifier(store.root,task.id)
        build=await verifier.build(subject);assert build.state=='PASS',build.diagnostics
        result=await verifier.test(subject)
        assert result.state=='FAIL' and result.case_results==dict(zip(IDS,['FAIL','PASS'])),result
        assert result.package_evidence['parser']=='SCOPED_SDK_XML_V1'
        assert (await verifier.test(subject)).model_dump()==result.model_dump()
        xml=next(iter(result.package_evidence['test']['reports'].values()))['ref']
        (store.root/xml).write_bytes(b'<changed/>')
        assert (await verifier.test(subject)).state=='UNKNOWN'
    asyncio.run(run())


def test_scoped_test_will_not_run_after_cached_build_original_is_modified(tmp_path,monkeypatch):
    store,task,subject,path=setup(tmp_path,monkeypatch)
    async def run():
        verifier=CangjieVerifier(store.root,task.id);build=await verifier.build(subject)
        assert build.state=='PASS',build
        (store.root/build.log_ref).write_bytes(b'forged build')
        result=await verifier.test(subject)
        assert result.state=='UNKNOWN'
        assert not [c for c in store.records(task.id,'check') if c['kind']=='test']
    asyncio.run(run())
