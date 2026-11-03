"""Actual compiler proof for derived private bridges; not V5/business evidence."""
import asyncio,hashlib,json
from copy import deepcopy
import pytest

from nexus.adapters.cangjie.sdk import SDK
from nexus.contracts import source_manifest
from nexus.execution.runner import run_command
from nexus.repair.scoped_material import material
from tests.test_package_material import selected,NONCE
from tests.test_package_index import project,record

pytestmark=pytest.mark.sdk


@pytest.mark.parametrize('control',['private-root','private-subpackage','public'])
def test_derived_bridge_compiles_and_executes_without_changing_original(tmp_path,control):
    files=project();name='bench.apply'
    if control=='private-subpackage':
        files['src/ops/order.cj']=files.pop('src/order.cj').replace(b'package bench\n',b'package bench.ops\n',1)
        files['src/ops/cases_test.cj']=files.pop('src/cases_test.cj').replace(b'package bench\n',b'package bench.ops\n',1)
        name='bench.ops.apply'
    if control!='public':
        # Unneeded State importing the root would cycle if a bridge imported all types.
        files['src/anchor.cj']=b'package bench\npublic func anchor(x: Int64): Int64 { x }'
        files['src/unused/state.cj']=record('bench.unused').replace(b'package bench.unused',b'package bench.unused\nimport bench.anchor')
    else:name='bench.sale.fee'
    before=deepcopy(files);sig=selected(files,name);derived=material(files,sig,NONCE);binding=derived['binding']
    assert files==before
    root=tmp_path/'project';root.mkdir()
    for path,raw in derived['files'].items():
        target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    expression=(binding['target_alias']+'(2), 3') if control=='public' else (binding['target_alias']+'('+binding['type_names']['bench.sale.State']+'(10), 2).amount, 16')
    source='\n'.join(['package '+binding['package'],*binding['imports'],'import std.unittest.*','import std.unittest.testmacro.*',
        '@Test class Cases { @TestCase func case0() { @Expect('+expression+') } }',''])
    test=root/('src/'+binding['package'].split('.',1)[1]+'/bridge_test.cj');test.parent.mkdir(parents=True);test.write_text(source)
    manifest=source_manifest(root);argv=[]
    code,log,problem=asyncio.run(run_command(root,['cjpm','test'],private_root=tmp_path,test_output='all',execution_argv=argv))
    (tmp_path/'sdk.log').write_text(log)
    (tmp_path/'input.json').write_text(json.dumps(dict(signature=sig,binding=binding,original_manifest=derived['original_manifest'],
        derived_manifest=derived['derived_manifest'],source_manifest=manifest),ensure_ascii=False,indent=2))
    (tmp_path/'result.json').write_text(json.dumps(dict(exit_code=code,problem=problem,execution_argv=argv,source_after=source_manifest(root),
        sdk_tools={p:hashlib.sha256((SDK/p).read_bytes()).hexdigest() for p in ('bin/cjc','bin/cjc-frontend','tools/bin/cjpm')}),indent=2))
    assert problem is None and code==0,log
    assert manifest==source_manifest(root) and files==before
    assert all(path not in before for path in derived['derived_manifest'])
