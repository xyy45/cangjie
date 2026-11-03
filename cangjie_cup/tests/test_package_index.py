"""Bounded typed package admission, separate from nonexecuting scope metadata."""
from copy import deepcopy
import pytest

from nexus.benchmark.corpus import CONFIG, LOCK
from nexus.projects.index import inspect_project, validate_project_candidate


def record(package):
    return f'''package {package}
public class State {{
 public let amount: Int64
 public init(amount: Int64) {{ this.amount = amount }}
 public func net(): Int64 {{ this.amount }}
 public func advance(n: Int64): State {{ State(this.amount + n) }}
}}
public func fee(x: Int64): Int64 {{ x + 1 }}
'''.encode()


def cases(package, expression, imports=''):
    return f'''package {package}
import std.unittest.*
import std.unittest.testmacro.*
{imports}
@Test class Cases {{ @TestCase func case0() {{ @Expect({expression}) }} }}
'''.encode()


def project():
    return {'cjpm.toml': CONFIG, 'cjpm.lock': LOCK,
        'src/order.cj': b'''package bench
import bench.sale.State as SaleState
import bench.refund.State as RefundState
import bench.sale.fee as cost
import bench.refund as refunds
func apply(state: SaleState, n: Int64): RefundState {
 let next = state.advance(n)
 RefundState(next.net() + cost(n) + refunds.fee(0))
}
''',
        'src/sale/state.cj': record('bench.sale'),
        'src/refund/state.cj': record('bench.refund'),
        'src/cases_test.cj': cases('bench', 'apply(SaleState(10), 2).amount, 16', 'import bench.sale.State as SaleState'),
        'src/sale/cases_test.cj': cases('bench.sale', 'fee(2), 3'),
        'src/refund/cases_test.cj': cases('bench.refund', 'fee(2), 3')}


def test_nominal_types_functions_methods_and_cases_have_package_identity():
    files = project(); before = deepcopy(files); info = inspect_project(files)
    assert files == before and info['version'] == 2 and info['package'] == 'bench'
    assert set(info['types']) == {'bench.sale.State', 'bench.refund.State'}
    assert set(info['type_paths']) == set(info['types'])
    assert {m['name'] for m in info['methods']} == {'bench.sale.State.net', 'bench.sale.State.advance', 'bench.refund.State.net', 'bench.refund.State.advance'}
    f = next(f for f in info['functions'] if f['name'] == 'bench.apply')
    assert f['local_name'] == 'apply' and f['package'] == 'bench' and not f['public']
    assert [p['type'] for p in f['params']] == ['bench.sale.State', 'Int64']
    assert f['return_type'] == 'bench.refund.State'
    assert f['scope'] == dict(version=1, root_package='bench', package='bench', local_name='apply', path='src/order.cj', graph_hash=info['graph_hash'])
    assert {c['name'] for c in f['calls']} == {'bench.sale.State.advance', 'bench.sale.State.net', 'bench.sale.fee', 'bench.refund.fee', 'bench.refund.State'}
    assert {c['id'] for c in info['test_cases']} == {'bench.Cases.case0', 'bench.sale.Cases.case0', 'bench.refund.Cases.case0'}
    case = next(c for c in info['test_cases'] if c['id'] == 'bench.Cases.case0')
    assert case['function'] == 'bench.apply' and case['args'] == [{'$type': 'bench.sale.State', 'fields': {'amount': 10}}, 2]
    assert case['function_spelling'] == 'apply' and case['projection'] == ['amount']
    assert case['call_tokens'] == ['apply', '(', 'SaleState', '(', '10', ')', ',', '2', ')']


@pytest.mark.parametrize('change', ['missing-import', 'wrong-nominal', 'private-import', 'unsafe-method', 'shadow-param', 'shadow-let', 'external', 'cycle', 'private-object', 'mutate-field', 'bad-path'])
def test_scoped_gate_rejects_invalid_types_capabilities_visibility_and_alias_shadowing(change):
    files = project()
    if change == 'missing-import': files['src/cases_test.cj'] = files['src/cases_test.cj'].replace(b'import bench.sale.State as SaleState', b'')
    elif change == 'wrong-nominal': files['src/order.cj'] = files['src/order.cj'].replace(b'state.advance(n)', b'RefundState(n)').replace(b'next.net()', b'apply(next, n).amount')
    elif change == 'private-import': files['src/sale/state.cj'] = files['src/sale/state.cj'].replace(b'public func fee', b'func fee')
    elif change == 'unsafe-method': files['src/refund/state.cj'] = files['src/refund/state.cj'].replace(b'{ this.amount }', b'{ println(this.amount); this.amount }')
    elif change == 'shadow-param': files['src/order.cj'] = files['src/order.cj'].replace(b', n: Int64', b', cost: Int64')
    elif change == 'shadow-let': files['src/order.cj'] = files['src/order.cj'].replace(b'let next', b'let cost')
    elif change == 'external': files['src/order.cj'] = files['src/order.cj'].replace(b'package bench', b'package bench\nimport std.fs.*')
    elif change == 'cycle': files['src/refund/state.cj'] = files['src/refund/state.cj'].replace(b'package bench.refund', b'package bench.refund\nimport bench.sale.fee')
    elif change == 'private-object': files['src/refund/state.cj'] = files['src/refund/state.cj'].replace(b'public class', b'class')
    elif change == 'mutate-field': files['src/refund/state.cj'] = files['src/refund/state.cj'].replace(b'{ this.amount }', b'{ this.amount = 4; this.amount }')
    else: files['src/Sale/state.cj'] = files.pop('src/sale/state.cj')
    if change == 'cycle':
        files['src/sale/state.cj'] = files['src/sale/state.cj'].replace(b'package bench.sale', b'package bench.sale\nimport bench.refund.State as RefundState')
    with pytest.raises(ValueError): inspect_project(files)


def test_imports_frozen_but_allowed_function_and_method_bodies_can_change():
    files = project(); baseline = inspect_project(files)
    validate_project_candidate({**files, 'src/sale/state.cj': files['src/sale/state.cj'].replace(b'x + 1', b'x')}, baseline)
    edited = {**files, 'src/order.cj': files['src/order.cj'].replace(b'as cost', b'as price').replace(b'cost(n)', b'price(n)')}
    with pytest.raises(ValueError): validate_project_candidate(edited, baseline)
    edited = {**files, 'src/order.cj': files['src/order.cj'].replace(b'func apply', b'public func apply')}
    with pytest.raises(ValueError): validate_project_candidate(edited, baseline)


def test_canonical_type_values_are_nominal_and_simple_field_names_remain_strict():
    from nexus.repair import object_values as ov
    info = inspect_project(project()); types = info['types']
    item = {'$type': 'bench.sale.State', 'fields': {'amount': 2}}
    assert ov.value(item, 'bench.sale.State', types) == item
    with pytest.raises(ValueError): ov.value(item, 'bench.refund.State', types)
    with pytest.raises(ValueError): ov.name('bench.sale.State')
    assert ov.type_name('bench.sale.State') == 'bench.sale.State'
    with pytest.raises(ValueError): ov.type_name('std.fs.State')


def test_test_only_package_can_import_public_function_and_scoped_primitive_signatures():
    files = {'cjpm.toml': CONFIG, 'cjpm.lock': LOCK,
        'src/value.cj': b'package bench\npublic func value(n: Int64): Int64 { n + 1 }',
        'src/checks/cases_test.cj': cases('bench.checks', 'value(2), 3', 'import bench.value')}
    info = inspect_project(files)
    assert info['version'] == 2 and info['functions'][0]['scope']['graph_hash'] == info['graph_hash']
    assert info['test_cases'][0]['id'] == 'bench.checks.Cases.case0'


def test_legacy_project_without_imports_keeps_its_exact_version_one_shape():
    from tests.test_project_index import project as old_project
    info = inspect_project(old_project())
    assert info['version'] == 1 and 'dependency_graph' not in info
    assert all('scope' not in f for f in info['functions'])


def test_scoped_namespace_marker_is_preserved_without_inventing_functions():
    files=project();files['src/namespace/empty.cj']=b'package bench.namespace\n// explicit SDK traversal marker\n'
    index=inspect_project(files)
    assert index['packages']['bench.namespace']['production_paths']==['src/namespace/empty.cj']
    assert not any(f['path']=='src/namespace/empty.cj' for f in index['functions'])
    validate_project_candidate({**files,'src/namespace/empty.cj':b'package bench.namespace\n// new comment\n'},index)
    with pytest.raises(ValueError):validate_project_candidate({**files,'src/namespace/empty.cj':b'package bench.namespace\npublic func injected(): Int64 { 0 }'},index)
    with pytest.raises(ValueError):inspect_project({**files,'src/namespace/empty.cj':b'package bench.namespace\nimport bench.sale.fee\n'})
