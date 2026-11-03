"""Pure scoped metadata: does not admit/execute source or claim SDK validation."""
from copy import deepcopy
import importlib

import pytest

from nexus.contracts import digest


def api():
    return importlib.import_module('nexus.projects.scopes')


def declaration(package, local, path, *, public=True, kind='function'):
    return dict(name=package+'.'+local, local_name=local, package=package,
                path=path, kind=kind, public=public)


def project():
    files = {
        'src/order.cj': b'package bench\nimport bench.money.fee as cost\nimport bench.refund.State as Refund\npublic func total(x: Int64): Int64 { cost(x) }\n',
        'src/other.cj': b'package bench\nfunc other(x: Int64): Int64 { x }\n',
        'src/money/fee.cj': b'package bench.money\npublic func fee(x: Int64): Int64 { x }\n',
        'src/refund/state.cj': b'package bench.refund\npublic struct State {}\n',
    }
    declarations = [
        declaration('bench', 'total', 'src/order.cj'),
        declaration('bench', 'other', 'src/other.cj', public=False),
        declaration('bench.money', 'fee', 'src/money/fee.cj'),
        declaration('bench.refund', 'State', 'src/refund/state.cj', kind='type'),
    ]
    return files, declarations


def build(files=None, declarations=None):
    defaults = project()
    return api().build_scopes(files if files is not None else defaults[0], 'bench',
                              declarations if declarations is not None else defaults[1])


def test_aliases_are_file_local_and_source_is_unchanged():
    files, decls = project(); before = deepcopy((files, decls)); m = api()
    result = build(files, decls); scope = result['scopes']['src/order.cj']
    assert m.resolve(scope, 'cost', kind='function') == 'bench.money.fee'
    assert m.resolve(scope, 'Refund', kind='type') == 'bench.refund.State'
    assert m.resolve(scope, 'other') == 'bench.other'  # same-package private
    with pytest.raises(ValueError): m.resolve(result['scopes']['src/other.cj'], 'cost')
    with pytest.raises(ValueError): m.resolve(scope, 'Refund', kind='function')
    with pytest.raises(ValueError): m.resolve(scope, 'bench.money.fee')
    assert (files, decls) == before
    graph = result['dependency_graph']
    assert graph['version'] == 1
    assert graph['production_edges'] == [['bench', 'bench.money'], ['bench', 'bench.refund']]
    assert graph['test_edges'] == []
    assert graph['topological_order'] == ['bench.money', 'bench.refund', 'bench']
    assert result['graph_hash'] == digest(graph)
    assert result['packages']['bench.money'] == dict(directory='src/money', production_paths=['src/money/fee.cj'], test_paths=[])
    assert graph['imports'][0] == dict(specifier='bench.money.fee', kind='symbol', alias='cost',
        target_package='bench.money', path='src/order.cj', line=2, origin='WORKSPACE')


def test_package_and_wildcard_bindings_preserve_distinct_same_names():
    files, decls = project()
    files['src/order.cj'] = b'package bench\nimport bench.money\nimport bench.refund.*\nfunc total(x: Int64): Int64 { money.fee(x) }'
    files['src/refund/fee.cj'] = b'package bench.refund\npublic func fee(x: Int64): Int64 { x }'
    decls.append(declaration('bench.refund', 'fee', 'src/refund/fee.cj'))
    scope = build(files, decls)['scopes']['src/order.cj']; m = api()
    assert m.resolve(scope, 'money.fee') == 'bench.money.fee'
    assert m.resolve(scope, 'fee') == 'bench.refund.fee'
    assert m.resolve(scope, 'State', kind='type') == 'bench.refund.State'
    with pytest.raises(ValueError): m.resolve(scope, 'money.Missing')


def test_package_alias_is_resolved_and_graph_retains_original_import():
    files, decls = project()
    files['src/order.cj'] = b'package bench\nimport bench.money as finance\nfunc total(x: Int64): Int64 { finance.fee(x) }'
    result = build(files, decls)
    assert api().resolve(result['scopes']['src/order.cj'], 'finance.fee') == 'bench.money.fee'
    assert result['dependency_graph']['imports'][0]['alias'] == 'finance'


def test_private_symbols_never_escape_via_symbol_wildcard_or_package_imports():
    files, decls = project(); decls[2]['public'] = False
    with pytest.raises(ValueError): build(files, decls)
    for statement, spelling in [('import bench.money', 'money.fee'), ('import bench.money.*', 'fee')]:
        files['src/order.cj'] = ('package bench\n'+statement+'\nfunc total(x: Int64): Int64 { x }').encode()
        result = build(files, decls)
        with pytest.raises(ValueError): api().resolve(result['scopes']['src/order.cj'], spelling)


@pytest.mark.parametrize('statement', [
    'import std.fs.*', 'import cangjie.foo', 'import missing.pkg.fee',
    'import bench.money.Missing', 'import bench.money.{fee}',
    'import bench.money.* as all', 'import bench.money.fee as class',
    'public import bench.money.fee', 'import bench.money.fee extra',
    'import bench.money.fee\nimport bench.money.fee',
    'import bench.money.fee as total',
    'import bench.money.fee as money\nimport bench.money',
])
def test_ambiguous_external_grouped_reexport_and_shadowed_imports_are_rejected(statement):
    files, decls = project()
    files['src/order.cj'] = ('package bench\n'+statement+'\nfunc total(x: Int64): Int64 { x }').encode()
    with pytest.raises(ValueError): build(files, decls)


def test_same_named_symbols_in_different_packages_do_not_conflict():
    files, decls = project()
    files['src/refund/fee.cj'] = b'package bench.refund\npublic func fee(x: Int64): Int64 { x }'
    decls.append(declaration('bench.refund', 'fee', 'src/refund/fee.cj'))
    result = build(files, decls)
    assert api().resolve(result['scopes']['src/refund/fee.cj'], 'fee') == 'bench.refund.fee'
    assert api().resolve(result['scopes']['src/money/fee.cj'], 'fee') == 'bench.money.fee'
    with pytest.raises(ValueError): build(files, decls+[deepcopy(decls[-1])])


def test_prod_or_test_dependency_cycle_is_rejected():
    files, decls = project()
    files['src/money/fee.cj'] = b'package bench.money\nimport bench.total\npublic func fee(x: Int64): Int64 { x }'
    with pytest.raises(ValueError, match='环'): build(files, decls)
    files, decls = project()
    files['src/money/cases_test.cj'] = b'package bench.money\nimport bench.total\nimport std.unittest.*\nimport std.unittest.testmacro.*\n@Test class Cases {}'
    with pytest.raises(ValueError, match='环'): build(files, decls)


def test_test_only_package_and_fixed_sdk_import_origins_are_distinct():
    files, decls = project()
    files['src/checks/cases_test.cj'] = b'package bench.checks\nimport bench.total\nimport std.unittest.*\nimport std.unittest.testmacro.*\n@Test class Cases {}'
    result = build(files, decls); graph = result['dependency_graph']
    assert graph['test_edges'] == [['bench.checks', 'bench']]
    assert result['packages']['bench.checks']['production_paths'] == []
    assert [(i['specifier'], i['origin']) for i in graph['imports'] if i['path'] == 'src/checks/cases_test.cj'] == [
        ('bench.total', 'WORKSPACE'), ('std.unittest.*', 'FIXED_SDK'), ('std.unittest.testmacro.*', 'FIXED_SDK')]
    assert result['packages']['bench.checks']['test_paths'] == ['src/checks/cases_test.cj']
    assert api().resolve(result['scopes']['src/checks/cases_test.cj'], 'total') == 'bench.total'
    with pytest.raises(ValueError): api().resolve(result['scopes']['src/checks/cases_test.cj'], 'other')


def test_header_preserves_crlf_lines_and_ignores_comment_and_string_import_text():
    source = '// import evil.*\r\npackage bench.money\r\n/* import bad.* */\r\npublic func fee(x: Int64): String { "import sneaky.*" }\r\n'
    header = api().read_header(source, 'src/money/fee.cj', 'bench')
    assert header['package'] == 'bench.money' and header['imports'] == []
    assert ('fee', 4) in header['body_items']
    assert ('"import sneaky.*"', 4) in header['body_items']
    source = 'package bench\nimport /* preserved coordinate */ bench.money.fee as cost;\nfunc total(x: Int64): Int64 {cost(x)}'
    header = api().read_header(source, 'src/order.cj', 'bench')
    assert header['imports'][0] == dict(specifier='bench.money.fee', alias='cost', line=2)
    assert header['body_items'][0] == ('func', 3)


@pytest.mark.parametrize('path,source', [
    ('src/Money/fee.cj', 'package bench.money\nfunc fee(x: Int64): Int64 {x}'),
    ('src/money/fee.cj', 'package bench\nfunc fee(x: Int64): Int64 {x}'),
    ('src/fee.cj', 'func fee(x: Int64): Int64 {x}'),
    ('src/a-b/fee.cj', 'package bench.a\nfunc fee(x: Int64): Int64 {x}'),
    ('src/nexus_verify_user/fee.cj', 'package bench.nexus_verify_user\nfunc fee(x: Int64): Int64 {x}'),
    ('src/../fee.cj', 'package bench\nfunc fee(x: Int64): Int64 {x}'),
    ('src/money/fee.cj', 'package other.money\nfunc fee(x: Int64): Int64 {x}'),
])
def test_package_identity_matches_exact_safe_directory(path, source):
    with pytest.raises(ValueError): api().read_header(source, path, 'bench')


def test_header_is_metadata_not_executable_source_admission():
    # A later typed parser must reject this body. Header metadata never says valid=True.
    header = api().read_header('package bench\nfunc evil(x: Int64): Int64 { readln() }', 'src/order.cj', 'bench')
    assert ('readln', 2) in header['body_items']
    assert 'validated' not in header and 'compiler_verified' not in header


def test_declarations_must_be_exact_owned_canonical_headers():
    files, decls = project()
    for key, value in [('name', 'bench.other'), ('package', 'bench.refund'), ('path', 'src/missing.cj'),
                       ('kind', 'macro'), ('public', 1), ('local_name', 'fee.x')]:
        changed = deepcopy(decls); changed[0][key] = value
        with pytest.raises(ValueError): build(files, changed)
    changed = deepcopy(decls); changed[0]['extra'] = 'not-authority'
    with pytest.raises(ValueError): build(files, changed)
    changed = deepcopy(decls); changed[-1]['public'] = False
    with pytest.raises(ValueError): build(files, changed)


def test_graph_is_stable_under_input_order_and_body_only_edits():
    files, decls = project(); first = build(files, decls)
    edited = dict(reversed(list(files.items())))
    edited['src/money/fee.cj'] = edited['src/money/fee.cj'].replace(b'{ x }', b'{ x + 1 }')
    second = build(edited, list(reversed(decls)))
    assert first['dependency_graph'] == second['dependency_graph'] and first['graph_hash'] == second['graph_hash']
    edited['src/order.cj'] = edited['src/order.cj'].replace(b'as cost', b'as expense').replace(b'cost(x)', b'expense(x)')
    assert build(edited, decls)['graph_hash'] != first['graph_hash']


def test_package_count_limit_and_empty_root_metadata():
    files = {f'src/p{i}/code.cj': f'package bench.p{i}\npublic func value(x: Int64): Int64 {{x}}'.encode() for i in range(16)}
    decls = [declaration(f'bench.p{i}', 'value', f'src/p{i}/code.cj') for i in range(16)]
    # Root is a package identity even if it has no production source.
    with pytest.raises(ValueError): build(files, decls)
    files.pop('src/p15/code.cj'); decls.pop()
    result = build(files, decls)
    assert len(result['packages']) == 16 and result['packages']['bench']['production_paths'] == []


def test_bound_names_are_separate_from_source_spellings():
    names = importlib.import_module('nexus.projects.names')
    assert names.local_name('a'*64) == 'a'*64
    package = '.'.join(['a'*23]*8)  # 191 characters
    assert len(package) == 191 and names.package_name(package) == package
    symbol = package+'.'+'b'*64
    assert len(symbol) == 256 and names.symbol_name(symbol) == symbol
    suite = package+'.'+'C'*54
    assert len(suite) == 246 and names.suite_name(suite) == suite
    case = suite+'.'+'d'*64
    assert len(case) == 311 and names.case_name(case) == case
    for validator, bad in [(names.local_name, 'x'*65), (names.local_name, True),
        (names.local_name, 'class'), (names.local_name, 'Int64'), (names.local_name, 'a.b'),
        (names.package_name, package+'x'), (names.package_name, 'a.b.c.d.e.f.g.h.i'),
        (names.package_name, 'std.foo'), (names.package_name, 'cangjie.foo'),
        (names.package_name, 'bench.nexus_verify_foo'), (names.package_name, 'bench..a'),
        (names.symbol_name, 'a'), (names.symbol_name, symbol+'x'),
        (names.suite_name, suite+'x'), (names.case_name, case+'x')]:
        with pytest.raises(ValueError): validator(bad)
