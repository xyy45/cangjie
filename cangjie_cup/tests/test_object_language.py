"""Closed object declarations and readonly methods; not general Cangjie parsing."""
import importlib
import importlib.util
import pytest
from nexus.uploads.language import inspect_source,validate_candidate


def source(kind='struct'):
    return '''package bench
public '''+kind+''' OrderState {
 public let amount: Int64
 public let items: Array<Int64>
 public init(amount: Int64, items: Array<Int64>) {
  this.amount = amount
  this.items = items
 }
 public func net(): Int64 { return this.amount - this.items.size }
 public func refund(n: Int64): OrderState { return OrderState(this.amount - n, this.items) }
}
public func apply(state: OrderState, n: Int64): OrderState { return state.refund(n) }
'''


def collector():
    assert importlib.util.find_spec('nexus.uploads.object_types') is not None,'object declaration collector missing'
    return importlib.import_module('nexus.uploads.object_types').collect


@pytest.mark.parametrize('kind',['struct','class'])
def test_collect_closed_declarations_preserves_type_and_source_coordinates(kind):
    result=collector()(source(kind));t=result['types']['OrderState']
    assert t['kind']==kind and t['constructor']==t['fields']
    assert [f['name'] for f in t['fields']]==['amount','items']
    assert [m['name'] for m in t['methods']]==['net','refund']
    assert result['declarations']['OrderState']['line']==2 and result['declarations']['OrderState']['end_line']==11
    assert {m['owner']+'.'+m['name'] for m in result['methods']}=={'OrderState.net','OrderState.refund'}
    tokens=[v for v,_ in result['top_items']];assert tokens[:2]==['package','bench'] and 'apply' in tokens and 'struct' not in tokens and 'class' not in tokens


@pytest.mark.parametrize('change',['var','field-default','nested-field','constructor-call','constructor-math','constructor-swapped','constructor-missing','constructor-double','private-method','mut','inherit','duplicate-type','duplicate-field','unknown-field-type','fifth-field','fifth-method'])
def test_collect_rejects_unsupported_declaration_or_constructor(change):
    text=source()
    if change=='var':text=text.replace('public let amount','public var amount')
    elif change=='field-default':text=text.replace('amount: Int64\n','amount: Int64 = 0\n',1)
    elif change=='nested-field':text=text.replace('public let amount: Int64','public let amount: OrderState')
    elif change=='constructor-call':text=text.replace('this.amount = amount','this.amount = apply(amount)')
    elif change=='constructor-math':text=text.replace('this.amount = amount','this.amount = amount + 1')
    elif change=='constructor-swapped':text=text.replace('init(amount: Int64, items: Array<Int64>)','init(items: Array<Int64>, amount: Int64)')
    elif change=='constructor-missing':text=text.replace('  this.items = items\n','')
    elif change=='constructor-double':text=text.replace('  this.items = items','  this.amount = amount\n  this.items = items')
    elif change=='private-method':text=text.replace('public func net','private func net')
    elif change=='mut':text=text.replace('public func net','public mut func net')
    elif change=='inherit':text=text.replace('OrderState {','OrderState <: Other {',1)
    elif change=='duplicate-type':text+=source().split('package bench\n')[1].split('public func apply')[0]
    elif change=='duplicate-field':text=text.replace(' public let items: Array<Int64>',' public let amount: Int64\n public let items: Array<Int64>')
    elif change=='unknown-field-type':text=text.replace('public let amount: Int64','public let amount: Secret')
    elif change=='fifth-field':text=text.replace(' public init',' public let a: Int64\n public let b: Int64\n public let c: Int64\n public init',1)
    else:text=text.replace(' public func net',' public func a(): Int64 { 0 }\n public func b(): Int64 { 0 }\n public func c(): Int64 { 0 }\n public func net',1)
    with pytest.raises(ValueError):collector()(text)


def test_collect_does_not_treat_comment_or_string_type_words_as_declarations():
    info=collector()('package bench\n// public class Fake { }\npublic func text(): String { "class struct" }\n')
    assert info['types']=={} and info['methods']==[]


@pytest.mark.parametrize('kind',['struct','class'])
def test_readonly_objects_and_methods_are_typed_and_indexed(kind):
    info=inspect_source(source(kind));assert info['types']['OrderState']['kind']==kind
    assert [f['name'] for f in info['functions']]==['apply']
    method=next(m for m in info['methods'] if m['name']=='OrderState.refund');assert method['receiver_type']=='OrderState'
    assert any(c['name']=='OrderState.refund' for c in info['functions'][0]['calls'])
    assert info['functions'][0]['types']==info['types']


@pytest.mark.parametrize('body',['this.amount = 1; return 0','this.items[0] = 1; return 0','return this.missing','return this.amount.size','return this.refund(true).amount','return OrderState(1, true).amount','return this == this','return println(this.amount)'])
def test_every_object_method_is_checked_even_when_entry_does_not_call_it(body):
    text=source().replace('return this.amount - this.items.size',body)
    with pytest.raises(ValueError):inspect_source(text)


def test_candidate_freezes_object_kind_field_and_method_interfaces():
    original=source();info=inspect_source(original)
    validate_candidate(original.replace('this.amount - n','this.amount - n - 1'),info)
    for modified in (original.replace('public struct','public class'),original.replace('amount: Int64','amount: Bool'),original.replace('refund(n: Int64)','refund(n: Bool)')):
        with pytest.raises(ValueError):validate_candidate(modified,info)


def test_object_method_parameter_cannot_shadow_a_declared_constructor():
    text=source().replace('refund(n: Int64)','refund(OrderState: Int64)').replace('this.amount - n','this.amount - OrderState')
    with pytest.raises(ValueError):inspect_source(text)


def test_method_call_coordinates_use_member_name_line_not_closing_parenthesis():
    text=source().replace('state.refund(n)','state.\n refund(\n n\n )')
    info=inspect_source(text);call=next(c for c in info['functions'][0]['calls'] if c['name']=='OrderState.refund')
    assert call['line']==next(i for i,line in enumerate(text.splitlines(),1) if line.strip()=='refund(')


def test_instance_method_cannot_silently_resolve_an_unqualified_same_named_global():
    text=source().replace('return this.amount - this.items.size','return refund(1)')
    text+='public func refund(n: Int64): Int64 { return n }\n'
    with pytest.raises(ValueError):inspect_source(text)
