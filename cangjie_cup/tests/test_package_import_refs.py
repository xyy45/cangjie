"""Long canonical identities use actual SDK package/member reference syntax."""
import importlib
import pytest


def api():return importlib.import_module('nexus.repair.scoped_imports')


def test_long_types_and_functions_share_one_package_alias_without_truncation():
    package='.'.join(['a'*23]*8);type_id=package+'.'+'b'*64;function_id=package+'.'+'c'*64
    refs,imports=api().references([(type_id,'__Type'),(function_id,'__Target')],set())
    assert refs[type_id]=='__Type.'+'b'*64 and refs[function_id]=='__Type.'+'c'*64
    assert imports==['import '+package+' as __Type']
    assert api().imports(refs)==imports


def test_short_symbols_keep_explicit_import_alias_and_invalid_member_injection_is_rejected():
    m=api();refs,imports=m.references([('bench.model.State','__Type'),('bench.apply','__Target')],set())
    assert refs=={'bench.model.State':'__Type','bench.apply':'__Target'}
    assert imports==['import bench.model.State as __Type','import bench.apply as __Target']
    for bad in ('Name; println(0)','Name.Wrong','A.B.C'):
        with pytest.raises(ValueError):m.imports({'bench.model.State':bad})


def test_alias_cannot_refer_to_different_packages_or_collide_with_plain_symbol():
    m=api();package='.'.join(['a'*23]*8);other='.'.join(['d'*23]*8)
    with pytest.raises(ValueError):m.imports({package+'.'+'b'*64:'Pkg.'+'b'*64,other+'.'+'c'*64:'Pkg.'+'c'*64})
    with pytest.raises(ValueError):m.imports({package+'.'+'b'*64:'Pkg.'+'b'*64,'bench.fee':'Pkg'})
