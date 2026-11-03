"""Real fixed SDK scans/XML originals; no model or remote analysis calls."""
import asyncio,hashlib,json,time
import pytest
from nexus.contracts import source_manifest
from nexus.execution.package_validation import scan,run_scoped_tests,tool_identity
from nexus.projects.index import inspect_project
from tests.test_package_index import project,cases

pytestmark=pytest.mark.sdk


def save(directory,name,value):
    def normalize(item):
        if type(item) is bytes:
            identity=hashlib.sha256(item).hexdigest();path=directory/(identity+'.raw')
            if not path.exists():path.write_bytes(item)
            return dict(original_ref=path.name,sha256=identity,bytes=len(item))
        if type(item) is dict:return {k:normalize(v) for k,v in item.items()}
        if type(item) is list:return [normalize(v) for v in item]
        return item
    (directory/(name+'.json')).write_text(json.dumps(normalize(value),ensure_ascii=False,indent=2)+'\n')


@pytest.mark.parametrize('control',['valid','mixed','empty-root','test-only-leaf'])
def test_fixed_scans_and_complete_xml_distinguish_package_cases(tmp_path,control):
    files=project()
    if control=='mixed':files['src/cases_test.cj']=files['src/cases_test.cj'].replace(b'amount, 16',b'amount, 17')
    elif control=='empty-root':files.pop('src/order.cj');files.pop('src/cases_test.cj')
    elif control=='test-only-leaf':files['src/checks/cases_test.cj']=cases('bench.checks','cost(2), 3','import bench.sale.fee as cost')
    index=inspect_project(files);expected=[c['id'] for c in index['test_cases']]
    root=tmp_path/'project';root.mkdir()
    for name,raw in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    before=source_manifest(root)
    scanned=asyncio.run(scan(root,index,deadline=time.monotonic()+90,private_root=tmp_path))
    save(tmp_path,'scans',scanned);save(tmp_path,'index',index)
    assert scanned['state']=='PASS',scanned['diagnostics']
    remaining=2*1024*1024-sum(len(s['stdout'])+len(s['stderr']) for s in scanned['scans'])
    result=asyncio.run(run_scoped_tests(root,expected=expected,deadline=time.monotonic()+90,
        private_root=tmp_path,output_limit=remaining))
    save(tmp_path,'test',result)
    from nexus.repair.package_evidence import capture,rebuild
    (tmp_path/'records').mkdir()
    proof=capture(tmp_path,project=root,index=index,scanned=scanned,execution=result)
    save(tmp_path,'package-evidence',proof)
    rebuilt=rebuild(tmp_path,project=root,index=index,evidence=proof,expected=expected,tools=tool_identity())
    save(tmp_path,'rebuilt',rebuilt)
    assert rebuilt['state']==result['parsed']['state'],(rebuilt,result)
    save(tmp_path,'identities',dict(source_before=before,source_after=source_manifest(root),tools=tool_identity(),
        test_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
        model_requests=0,remote_analysis_requests=0))
    assert source_manifest(root)==before
    if control=='empty-root':
        assert result['parsed']['state']=='UNKNOWN'
    else:
        assert result['problem'] is None,result
        assert result['parsed']['state']==('FAIL' if control=='mixed' else 'PASS'),result
        assert set(result['parsed']['case_results'])==set(expected)
        assert result['binary_before']==result['binary_after'] and result['binary_before']
        assert len(result['reports'])==len(expected)


@pytest.mark.parametrize('control',['multiple-failures','runtime-error','escaped-text'])
def test_real_sdk_diagnostic_xml_remains_complete_or_unknown(tmp_path,control):
    from nexus.benchmark.corpus import CONFIG,LOCK
    body={'multiple-failures':'@Expect(1, 2)\n@Expect(3, 4)',
          'runtime-error':'@Expect(overflow(9223372036854775807), 0)',
          'escaped-text':'@Expect("<x>&text", "safe")'}[control]
    files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,
           'src/entry.cj':b'package bench\npublic func overflow(x: Int64): Int64 { x+1 }\n',
           'src/cases_test.cj':('package bench\nimport std.unittest.*\nimport std.unittest.testmacro.*\n'
             '@Test class Cases { @TestCase func case0() {\n'+body+'\n} }\n').encode()}
    root=tmp_path/'project';root.mkdir()
    for name,raw in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    result=asyncio.run(run_scoped_tests(root,expected=['bench.Cases.case0'],deadline=time.monotonic()+90,private_root=tmp_path))
    save(tmp_path,'test',result)
    if control=='runtime-error':assert result['parsed']['state']=='UNKNOWN',result
    elif control=='multiple-failures':
        assert result['parsed']['state']=='FAIL',result
        text='\n'.join(item['text'] for item in result['parsed']['failures']['bench.Cases.case0'])
        assert 'left: 1' in text and 'right: 2' in text and 'left: 3' in text and 'right: 4' in text
    else:
        # Malformed XML escaping by the pinned SDK is an original UNKNOWN, never repaired into PASS.
        assert result['parsed']['state'] in ('FAIL','UNKNOWN'),result


@pytest.mark.parametrize('control',['valid','mixed'])
def test_actual_scoped_verifier_cache_rechecks_original_xml(tmp_path,monkeypatch,control):
    from nexus.adapters.cangjie.verifier import CangjieVerifier
    from nexus.execution.workspace import WorkspaceStore
    from nexus.store import RunStore
    files=project()
    if control=='mixed':files['src/cases_test.cj']=files['src/cases_test.cj'].replace(b'amount, 16',b'amount, 17')
    original=tmp_path/'input';original.mkdir()
    for name,raw in files.items():
        path=original/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    runtime=tmp_path/'runtime';ws=WorkspaceStore(runtime,registered=[original]);baseline=ws.import_project(original,'.')
    store=RunStore(runtime);task=store.create_task(baseline,'real scoped verifier SDK control',['src/order.cj'])
    def context(self,task,subject):
        path=ws.verify_baseline(subject);index=inspect_project({p:(path/p).read_bytes() for p in source_manifest(path)})
        return dict(project=path,index=index,expected=sorted(c['id'] for c in index['test_cases']))
    # This isolates verifier dispatch from Task5 upload confirmation, still using actual SDK bytes.
    monkeypatch.setattr(CangjieVerifier,'_scoped_context',context)
    async def run():
        verifier=CangjieVerifier(runtime,task.id)
        built=await verifier.build(baseline);assert built.state=='PASS',built
        tested=await verifier.test(baseline)
        assert tested.state==('PASS' if control=='valid' else 'FAIL'),tested
        assert (await verifier.test(baseline)).model_dump()==tested.model_dump()
        save(tmp_path,'immutable-check-originals',{p.name:p.read_bytes() for p in (runtime/'records').iterdir() if p.is_file()})
        report=next(iter(tested.package_evidence['test']['reports'].values()))
        (runtime/report['ref']).write_bytes(b'<tampered/>')
        assert (await verifier.test(baseline)).state=='UNKNOWN'
        save(tmp_path,'checks',store.records(task.id,'check'))
    asyncio.run(run())


@pytest.mark.parametrize('entry',['private-root','private-subpackage','primitive'])
def test_public_examples_execute_in_entry_package_without_production_bridge(tmp_path,entry):
    from nexus.uploads.scoped_public_tests import render
    from tests.test_package_public_tests import examples
    files=project();function='bench.apply';values=examples()
    if entry=='private-subpackage':
        files['src/ops/order.cj']=files.pop('src/order.cj').replace(b'package bench\n',b'package bench.ops\n')
        files['src/ops/cases_test.cj']=files.pop('src/cases_test.cj').replace(b'package bench\n',b'package bench.ops\n')
        files['src/anchor.cj']=b'package bench\npublic func anchor(x: Int64): Int64 { x }'
        function='bench.ops.apply'
    elif entry=='primitive':
        function='bench.sale.fee';values=[dict(args=[2],expected=3,suite='target'),dict(args=[0],expected=1,suite='regression')]
    index=inspect_project(files);source,metadata=render(index,function,values)
    assert 'public func ' not in source
    root=tmp_path/'project';root.mkdir()
    for name,raw in {**files,metadata['public_test_path']:source.encode()}.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    scanned=asyncio.run(scan(root,index,deadline=time.monotonic()+90,private_root=tmp_path));save(tmp_path,'scans',scanned)
    assert scanned['state']=='PASS',scanned
    expected=sorted([c['id'] for c in index['test_cases']]+[c for cases in metadata['public_test_case_ids'].values() for c in cases])
    remaining=2*1024*1024-sum(len(s['stdout'])+len(s['stderr']) for s in scanned['scans'])
    tested=asyncio.run(run_scoped_tests(root,expected=expected,deadline=time.monotonic()+90,private_root=tmp_path,output_limit=remaining))
    save(tmp_path,'test',tested);save(tmp_path,'public-metadata',metadata);save(tmp_path,'index',index)
    assert tested['parsed']['state']=='PASS',tested
    assert {p:raw for p,raw in files.items() if not p.endswith('_test.cj')}=={p:(root/p).read_bytes() for p in files if not p.endswith('_test.cj')}
