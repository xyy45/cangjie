"""Public scoped tests remain in the entry package, never add a bridge."""
import importlib
from pathlib import PurePosixPath
from copy import deepcopy
import pytest
from nexus.projects.index import inspect_project
from tests.test_package_index import project


def render(index,function,examples):
    return importlib.import_module('nexus.uploads.scoped_public_tests').render(index,function,examples)


def examples():
    return [dict(args=[{'$type':'bench.sale.State','fields':{'amount':10}},2],expected={'$type':'bench.refund.State','fields':{'amount':16}},suite='target'),
            dict(args=[{'$type':'bench.sale.State','fields':{'amount':10}},0],expected={'$type':'bench.refund.State','fields':{'amount':12}},suite='regression')]


def test_scoped_public_render_binds_private_target_types_and_all_case_ids():
    files=project();index=inspect_project(files);before=deepcopy(index)
    source,metadata=render(index,'bench.apply',examples())
    assert index==before and files==project()
    assert source.startswith('package bench\n') and 'public func ' not in source
    assert '= apply\n' in source
    assert metadata['public_test_path'].startswith('src/') and metadata['public_test_path'].endswith('_test.cj')
    assert set(metadata['public_test_constructors'])=={'bench.sale.State','bench.refund.State'}
    assert metadata['public_test_case_ids']=={s:['bench.'+metadata['public_test_class']+'.case'+str(i)] for i,s in enumerate(('target','regression'))}
    assert metadata['public_test_target']+'(' in source


def test_subpackage_private_target_stays_in_subpackage_and_collisions_do_not_overwrite_original():
    files=project();files['src/ops/order.cj']=files.pop('src/order.cj').replace(b'package bench\n',b'package bench.ops\n')
    files['src/ops/cases_test.cj']=files.pop('src/cases_test.cj').replace(b'package bench\n',b'package bench.ops\n')
    files['src/anchor.cj']=b'package bench\npublic func anchor(x: Int64): Int64 { x }'
    index=inspect_project(files);_,first=render(index,'bench.ops.apply',examples())
    reserved=first['public_test_path'];files[reserved]=b'package bench.ops\nimport std.unittest.*\nimport std.unittest.testmacro.*\n@Test class UploadedTests { @TestCase func case0() { @Expect(anchor(0), 0) } }'
    # A reserved original path is independently supplied by a frozen index here;
    # this control tests allocation, not admission of the deliberately unresolved call.
    index['manifest'][reserved]='f'*64
    source,second=render(index,'bench.ops.apply',examples())
    assert source.startswith('package bench.ops\n')
    assert PurePosixPath(second['public_test_path']).parent==PurePosixPath('src/ops')
    assert second['public_test_path'].casefold()!=reserved.casefold()


def test_primitive_scoped_target_is_bound_once_and_bad_nominal_examples_are_rejected():
    index=inspect_project(project())
    source,metadata=render(index,'bench.sale.fee',[dict(args=[2],expected=3,suite='target'),dict(args=[0],expected=1,suite='regression')])
    assert source.startswith('package bench.sale\n') and '= fee\n' in source
    assert metadata['public_test_constructors']=={}
    bad=examples();bad[0]['args'][0]['$type']='bench.refund.State'
    with pytest.raises(ValueError):render(index,'bench.apply',bad)
