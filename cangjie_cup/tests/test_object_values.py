"""Closed nominal object values; no SDK/model/network execution."""
from copy import deepcopy
import importlib
import importlib.util
import pytest
from nexus.repair import values


def module():
    assert importlib.util.find_spec('nexus.repair.object_values') is not None,'object value contract missing'
    return importlib.import_module('nexus.repair.object_values')


def types():
    fields=[dict(name='amount',type='Int64'),dict(name='label',type='String'),dict(name='active',type='Bool'),dict(name='items',type='Array<Int64>')]
    return {'OrderState':dict(kind='struct',fields=fields,constructor=deepcopy(fields),methods=[dict(name='net',params=[],return_type='Int64')])}


def obj():return {'$type':'OrderState','fields':dict(amount=10,label='中',active=True,items=[1,2])}


def test_registry_canonical_independent_and_empty_compatible():
    m=module();raw=types();result=m.registry(raw);assert result==raw and m.registry({})=={}
    raw['OrderState']['fields'][0]['name']='changed';assert result['OrderState']['fields'][0]['name']=='amount'
    assert m.is_object_type('OrderState',result) and not m.is_object_type('Missing',result)
    assert m.has_objects(dict(params=[dict(type='OrderState')],return_type='Bool',types=result))
    assert not m.has_objects(dict(params=[dict(type='Int64')],return_type='Bool'))


@pytest.mark.parametrize('change',['kind','extra','no-fields','five-fields','duplicate-field','nested-field','constructor-order','method-params','method-return','invalid-name','reserved-name','five-types'])
def test_registry_rejects_unsupported_declarations(change):
    m=module();raw=types();d=raw['OrderState']
    if change=='kind':d['kind']='interface'
    elif change=='extra':d['base']='Other'
    elif change=='no-fields':d['fields']=[];d['constructor']=[]
    elif change=='five-fields':d['fields'].append(dict(name='extra',type='Int64'));d['constructor']=deepcopy(d['fields'])
    elif change=='duplicate-field':d['fields'][1]=deepcopy(d['fields'][0]);d['constructor']=deepcopy(d['fields'])
    elif change=='nested-field':d['fields'][0]['type']='OrderState';d['constructor']=deepcopy(d['fields'])
    elif change=='constructor-order':d['constructor'].reverse()
    elif change=='method-params':d['methods'][0]['params']=[dict(name='p'+str(i),type='Int64') for i in range(5)]
    elif change=='method-return':d['methods'][0]['return_type']='Unknown'
    elif change=='invalid-name':raw={'非标识符':d}
    elif change=='reserved-name':raw={'Int64':d}
    else:raw={'Type'+str(i):deepcopy(d) for i in range(5)}
    with pytest.raises(ValueError):m.registry(raw)


def test_values_tagged_deep_copied_and_canonical_field_order():
    m=module();raw=obj();raw['fields']=dict(reversed(list(raw['fields'].items())));original=deepcopy(raw)
    result=m.value(raw,'OrderState',types());assert list(result['fields'])==['amount','label','active','items'] and raw==original
    raw['fields']['items'].append(99);assert result['fields']['items']==[1,2]
    result['fields']['items'].append(88);assert raw['fields']['items']==[1,2,99]


@pytest.mark.parametrize('change',['tag','missing-tag','extra-top','missing-field','extra-field','bool-int','float-int','overflow','array-bool','array17','string257','nested','null','tuple'])
def test_object_boundary_rejects_invalid_values(change):
    m=module();raw=obj()
    if change=='tag':raw['$type']='Other'
    elif change=='missing-tag':raw.pop('$type')
    elif change=='extra-top':raw['extra']=0
    elif change=='missing-field':raw['fields'].pop('amount')
    elif change=='extra-field':raw['fields']['extra']=0
    elif change=='bool-int':raw['fields']['amount']=True
    elif change=='float-int':raw['fields']['amount']=1.0
    elif change=='overflow':raw['fields']['amount']=1<<63
    elif change=='array-bool':raw['fields']['items']=[True]
    elif change=='array17':raw['fields']['items']=list(range(17))
    elif change=='string257':raw['fields']['label']='x'*257
    elif change=='nested':raw['fields']['items']=[obj()]
    elif change=='null':raw=None
    elif change=='tuple':raw['fields']['items']=(1,2)
    with pytest.raises(ValueError):m.value(raw,'OrderState',types())


def test_key_is_hashable_nominal_order_independent_and_a_snapshot():
    m=module();a=obj();b=deepcopy(a);b['fields']=dict(reversed(list(b['fields'].items())))
    key=m.typed_key(a,types());assert key==m.typed_key(b,types()) and hash(key)==hash(m.typed_key(b))
    a['fields']['items'].append(99);assert key!=m.typed_key(a,types())
    t=types();t['OtherState']=deepcopy(t['OrderState']);b['$type']='OtherState';assert key!=m.typed_key(b,t)
    assert m.typed_key({'$type':'T','fields':{'x':True}})!=m.typed_key({'$type':'T','fields':{'x':1}})
    with pytest.raises(ValueError):m.value({'$type':'Unregistered','fields':{'x':1}},'Unregistered',{})


def test_weight_literal_and_shared_values_preserve_legacy_contracts():
    m=module();raw=obj();t=types();assert m.weight(raw,t)==10+3+1+2+1+2
    literal=m.literal(raw,'OrderState',t);assert literal.startswith('OrderState(10, ') and 'true' in literal and '[1, 2]' in literal
    assert values.primitive(raw,'OrderState',t)==raw
    assert values.typed_key(raw,t)==m.typed_key(raw,t) and values.primitive_weight(raw,t)==m.weight(raw,t)
    with pytest.raises(ValueError):values.primitive(raw,'OrderState')
    assert values.primitive(7,'Int64')==7 and values.typed_key(True)==('Bool',True)


@pytest.mark.parametrize('identifier',['println','readln','Int8','UInt64','Float64','Rune','Unit','Nothing'])
def test_registry_rejects_other_builtin_or_prelude_type_names(identifier):
    raw=types();declaration=raw.pop('OrderState');raw[identifier]=declaration
    with pytest.raises(ValueError):module().registry(raw)
