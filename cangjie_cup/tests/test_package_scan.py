"""Fixed scanner orchestration with explicit in-process transport fixtures."""
import asyncio,hashlib,importlib,json,time
from copy import deepcopy
import pytest

from tests.test_package_dependencies import fixture


def api():return importlib.import_module('nexus.execution.package_validation')


def index_for(graph):
    from nexus.contracts import digest
    return dict(version=2,package='bench',graph_hash=digest(graph),dependency_graph=graph,
        packages={'bench':dict(directory='src',production_paths=['src/order.cj','src/wild.cj','src/qualified.cj']),
                  'bench.money':dict(directory='src/money',production_paths=['src/money/fee.cj']),
                  'bench.empty':dict(directory='src/empty',production_paths=['src/empty/namespace.cj'])})


def test_fixed_scan_collects_complete_packages_and_originals_without_source_changes(tmp_path,monkeypatch):
    root,graph,packet=fixture(tmp_path);module=api();calls=[]
    async def transport(project,directory,*,deadline,private_root,output_limit):
        calls.append(directory.relative_to(root).as_posix())
        package='bench'+('.'+directory.name if directory.name!='src' else '')
        value=packet if package=='bench' else dict(package=package,isMacro=False,accessLevel='public',dependencies=[])
        return dict(exit_code=0,problem=None,stdout=json.dumps(value).encode(),stderr=b'',argv=['FIXED_TEST_TRANSPORT'],profile_sha256='f'*64)
    monkeypatch.setattr(module,'_scan_process',transport)
    result=asyncio.run(module.scan(root,index_for(graph),deadline=time.monotonic()+30,private_root=tmp_path))
    assert result['state']=='PASS' and set(calls)=={'src','src/money','src/empty'}
    assert result['source_before']==result['source_after'] and len(result['scans'])==3
    assert all(s['stdout_sha256']==hashlib.sha256(s['stdout']).hexdigest() for s in result['scans'])


@pytest.mark.parametrize('change',['partial-json','stderr-limit','exit','deadline','source-change','bad-directory','wrong-graph-hash'])
def test_unknown_scan_cannot_claim_complete_dependency_evidence(tmp_path,monkeypatch,change):
    root,graph,packet=fixture(tmp_path);module=api();index=index_for(graph)
    if change=='bad-directory':index['packages']['bench']['directory']='../escape'
    elif change=='wrong-graph-hash':index['graph_hash']='f'*64
    async def transport(project,directory,*,deadline,private_root,output_limit):
        package='bench'+('.'+directory.name if directory.name!='src' else '')
        value=packet if package=='bench' else dict(package=package,isMacro=False,accessLevel='public',dependencies=[])
        if change=='source-change':(root/'src/order.cj').write_bytes((root/'src/order.cj').read_bytes()+b'\n// mutated by explicit fixture')
        return dict(exit_code=1 if change=='exit' else 0,problem=None,stdout=b'{}' if change=='partial-json' else json.dumps(value).encode(),
            stderr=b'x'*(2*1024*1024+1) if change=='stderr-limit' else b'',argv=['FIXED_TEST_TRANSPORT'],profile_sha256='f'*64)
    monkeypatch.setattr(module,'_scan_process',transport)
    result=asyncio.run(module.scan(root,index,deadline=time.monotonic()+(-1 if change=='deadline' else 30),private_root=tmp_path))
    assert result['state']=='UNKNOWN'
