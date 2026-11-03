"""Verification derivation preserves original project and signature bindings."""
from copy import deepcopy
import importlib
import pytest

from nexus.contracts import digest
from nexus.projects.index import inspect_project
from nexus.repair.scoped_signature import validate
from tests.test_package_index import project,record

NONCE='0123456789abcdef'


def material(files,signature,nonce=NONCE):
    return importlib.import_module('nexus.repair.scoped_material').material(files,signature,nonce)


def selected(files,name='bench.apply'):
    return validate(next(f for f in inspect_project(files)['functions'] if f['name']==name))


def test_private_bridge_is_derived_only_and_original_tests_are_removed():
    files=project();before=deepcopy(files);sig=selected(files);result=material(files,sig)
    assert files==before and result==material(files,sig)
    assert all(not p.endswith('_test.cj') for p in result['files'])
    for p,b in files.items():
        if not p.endswith('_test.cj'):assert result['files'][p]==b
    bridge=result['binding']['bridge_path'];assert bridge not in files
    source=result['files'][bridge].decode()
    assert source.startswith('package bench\n') and 'public func ' in source
    assert 'apply(' in source and 'bench.apply(' not in source
    assert result['binding']['private'] is True
    assert result['binding']['signature_hash']==digest(sig)
    assert set(result['derived_manifest'])=={bridge} and result['signature']==sig
    assert result['binding']['package']=='bench.nexus_verify_'+NONCE


def test_public_function_requires_no_production_bridge():
    files=project();sig=selected(files,'bench.sale.fee');result=material(files,sig)
    assert result['binding']['private'] is False and result['binding']['bridge_path'] is None
    assert result['derived_manifest']=={} and result['binding']['target']=='bench.sale.fee'
    assert result['binding']['type_names']=={}
    assert result['files']=={p:b for p,b in files.items() if not p.endswith('_test.cj')}


def test_only_signature_types_are_imported_so_unrelated_package_cannot_add_cycle():
    files=project();files['src/order.cj']+=b'public func anchor(x: Int64): Int64 { x }\n'
    files['src/unused/state.cj']=record('bench.unused').replace(b'package bench.unused',b'package bench.unused\nimport bench.anchor')
    sig=selected(files);assert len(sig['types'])==3
    result=material(files,sig);binding=result['binding']
    assert set(binding['type_names'])=={'bench.sale.State','bench.refund.State'}
    assert all('bench.unused' not in value for value in binding['imports'])
    assert b'bench.unused' not in result['files'][binding['bridge_path']]
    assert result['files']['src/unused/state.cj']==files['src/unused/state.cj']


def test_bridge_names_and_paths_are_fresh_against_original_declarations():
    files=project();first=material(files,selected(files));local=first['binding']['target'].rsplit('.',1)[-1]
    files['src/order.cj']+=('public func '+local+'(x: Int64): Int64 { x }\n').encode()
    # Casefold conflict with generated file is preserved instead of overwritten.
    path=first['binding']['bridge_path'].upper().replace('SRC/','src/').replace('.CJ','.cj')
    files[path]=b'package bench\npublic func other(x: Int64): Int64 { x }'
    second=material(files,selected(files))
    assert second['binding']['target']!=first['binding']['target']
    assert second['binding']['bridge_path'].casefold()!=path.casefold()
    assert second['files'][path]==files[path]


@pytest.mark.parametrize('change',['graph','path','name','params','registry'])
def test_signature_must_be_rebuilt_from_exact_original_project(change):
    files=project();sig=selected(files)
    if change=='graph':sig['scope']['graph_hash']='f'*64
    elif change=='path':sig['scope']['path']='src/other.cj'
    elif change=='name':sig['name']='bench.other';sig['scope']['local_name']='other'
    elif change=='params':sig['params'][0]['type']='bench.refund.State'
    else:sig['types']['bench.sale.State']['kind']='struct'
    with pytest.raises(ValueError):material(files,sig)


@pytest.mark.parametrize('nonce',[None,True,'x'*16,'A'*16,'0'*15,'0'*17])
def test_nonce_is_exact_lowercase_hex_before_source_generation(nonce):
    files=project()
    with pytest.raises(ValueError):material(files,selected(files),nonce)
