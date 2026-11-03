"""Scoped signature shape is data validation, never source authorization."""
from copy import deepcopy
import importlib
import pytest

from nexus.projects.index import inspect_project
from tests.test_package_index import project


def validate(raw):
    return importlib.import_module('nexus.repair.scoped_signature').validate(raw)


def signature():
    return next(f for f in inspect_project(project())['functions'] if f['name']=='bench.apply')


def test_stable_scoped_signature_copies_only_callable_metadata():
    original=signature(); result=validate(original)
    assert set(result)=={'name','params','return_type','types','scope'}
    assert result['scope']==original['scope'] and result['types']==original['types']
    original['scope']['package']='changed'
    original['types']['bench.sale.State']['fields'][0]['name']='changed'
    assert result['scope']['package']=='bench' and result['types']['bench.sale.State']['fields'][0]['name']=='amount'


@pytest.mark.parametrize('field,value',[
    ('version',True),('version',2),('root_package','other'),('root_package','bench.root'),
    ('package','other'),('package','bench..a'),('local_name','other'),
    ('path','src/sale/order.cj'),('path','src/order_test.cj'),('path','../order.cj'),
    ('graph_hash','f'*63),('graph_hash','F'*64),('graph_hash',False),
])
def test_scope_identity_must_agree_with_frozen_callable_location(field,value):
    raw=signature();raw['scope'][field]=value
    with pytest.raises(ValueError):validate(raw)


def test_scope_has_exact_keys_and_is_required():
    for change in ('missing','extra'):
        raw=signature()
        if change=='missing':raw.pop('scope')
        else:raw['scope']['approved']=True
        with pytest.raises(ValueError):validate(raw)


@pytest.mark.parametrize('change',['mixed-type','foreign-type','wrong-param','extra-param-key','five-params','invalid-return','alias-param','bad-fn'])
def test_canonical_registry_params_and_function_name_are_bounded(change):
    raw=signature()
    if change=='mixed-type':raw['types']['State']=raw['types'].pop('bench.sale.State')
    elif change=='foreign-type':raw['types']['other.State']=raw['types'].pop('bench.sale.State')
    elif change=='wrong-param':raw['params'][0]['type']='Missing'
    elif change=='extra-param-key':raw['params'][0]['approved']=True
    elif change=='five-params':raw['params']=[dict(name='p'+str(i),type='Int64') for i in range(5)]
    elif change=='invalid-return':raw['return_type']='Unit'
    elif change=='alias-param':raw['params'][0]['name']='as'
    else:raw['name']='apply'
    with pytest.raises(ValueError):validate(raw)


def test_scoped_primitive_signature_keeps_scope_without_requiring_objects():
    raw=signature();raw['params']=[];raw['return_type']='Bool';raw.pop('types')
    result=validate(raw)
    assert result=={k:deepcopy(raw[k]) for k in ('name','params','return_type','scope')}


def test_subpackage_entry_has_exact_directory_and_rejects_test_file():
    raw=signature();raw['name']='bench.sale.apply'
    raw['scope'].update(package='bench.sale',path='src/sale/entry.cj')
    assert validate(raw)['scope']['path']=='src/sale/entry.cj'
    raw['scope']['path']='src/refund/entry.cj'
    with pytest.raises(ValueError):validate(raw)
