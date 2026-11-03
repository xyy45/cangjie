"""Nonexecuting package-header metadata, not a typed source admission gate.

Declarations come from the caller's closed header collection pass. Every file
gets its own imports; canonical IDs are never treated as Cangjie expressions.
"""
from copy import deepcopy
import heapq
from pathlib import PurePosixPath
import re

from nexus.contracts import digest
from nexus.projects.archive import safe_name
from nexus.projects.names import local_name, package_name, symbol_name
from nexus.uploads.language import TOKEN, tokens

TEST_TOKEN = re.compile(TOKEN.pattern + r'|@')
SDK_IMPORTS = {'std.unittest.*', 'std.unittest.testmacro.*'}


def read_header(source, path, root_package):
    root = package_name(root_package)
    if '.' in root:
        raise ValueError('构建根包名必须为简单标识符')
    safe_name(path)
    p = PurePosixPath(path)
    if not path.startswith('src/') or p.suffix != '.cj':
        raise ValueError('包源码必须位于src目录')
    expected = package_name('.'.join([root, *p.parts[1:-1]]))
    items = tokens(source, pattern=TEST_TOKEN); pos = 0

    def take(expected_token=None):
        nonlocal pos
        token = items[pos][0]
        if token == '<eof>' or expected_token is not None and token != expected_token:
            raise ValueError('包或导入声明语法无效')
        pos += 1
        return token

    def qualified(*, wildcard=False):
        parts = [local_name(take())]
        while items[pos][0] == '.':
            take('.')
            if wildcard and items[pos][0] == '*':
                take('*'); parts.append('*'); break
            parts.append(local_name(take()))
            if len(parts) > 9:
                raise ValueError('导入限定名过长')
        return '.'.join(parts)

    take('package'); package = package_name(qualified())
    if package != expected:
        raise ValueError('包声明与源码目录不一致：' + path)
    if items[pos][0] == ';': take(';')
    imports = []
    while items[pos][0] == 'import':
        line = items[pos][1]; take('import'); specifier = qualified(wildcard=True)
        alias = None
        if items[pos][0] == 'as':
            take('as'); alias = local_name(take())
            if specifier.endswith('.*'):
                raise ValueError('通配导入不支持别名')
        if items[pos][0] == ';': take(';')
        imports.append(dict(specifier=specifier, alias=alias, line=line))
    # The rest is retained for the typed gate. It is NOT accepted as a body here.
    if (items[pos][0] not in ('public', 'func', 'struct', 'class', '@', '<eof>') or
            items[pos][0] == 'public' and items[pos + 1][0] == 'import'):
        raise ValueError('导入声明后必须是受支持的顶层声明')
    return dict(package=package, imports=imports, body_items=items[pos:])


def _topological(packages, edges):
    dependencies = {p: set() for p in packages}
    users = {p: set() for p in packages}
    for source, target in edges:
        dependencies[source].add(target); users[target].add(source)
    ready = [p for p in packages if not dependencies[p]]; heapq.heapify(ready)
    order = []
    while ready:
        current = heapq.heappop(ready); order.append(current)
        for user in sorted(users[current]):
            dependencies[user].remove(current)
            if not dependencies[user]: heapq.heappush(ready, user)
    if len(order) != len(packages):
        raise ValueError('包依赖图存在环')
    return order


def build_scopes(files, root_package, declarations):
    root = package_name(root_package)
    if '.' in root or type(files) is not dict or not 1 <= len(files) <= 100:
        raise ValueError('作用域须来自一个有界构建根')
    packages = {root: dict(directory='src', production_paths=[], test_paths=[])}
    headers = {}
    for path, raw in sorted(files.items()):
        safe_name(path)
        if not path.endswith('.cj'): continue
        if type(raw) is not bytes: raise ValueError('源码须为原始UTF-8字节')
        try: source = raw.decode('utf-8')
        except UnicodeError: raise ValueError('源码须为UTF-8') from None
        header = read_header(source, path, root); headers[path] = header
        package = header['package']
        info = packages.setdefault(package, dict(directory=str(PurePosixPath(path).parent), production_paths=[], test_paths=[]))
        info['test_paths' if path.endswith('_test.cj') else 'production_paths'].append(path)
    if len(packages) > 16: raise ValueError('工程最多16个包（含构建根）')
    if not any(p['production_paths'] for p in packages.values()): raise ValueError('缺少生产包源码')
    packages = dict(sorted(packages.items()))
    symbols = {p: {} for p in packages}
    if type(declarations) is not list: raise ValueError('声明表须为已收集的列表')
    for declaration in declarations:
        if (type(declaration) is not dict or set(declaration) != {'name', 'local_name', 'package', 'path', 'kind', 'public'} or
                type(declaration['public']) is not bool or declaration['kind'] not in ('function', 'type')):
            raise ValueError('符号声明结构无效')
        name = symbol_name(declaration['name']); local = local_name(declaration['local_name'])
        package = package_name(declaration['package']); path = declaration['path']
        if (name != package + '.' + local or type(path) is not str or path not in headers or
                path.endswith('_test.cj') or headers[path]['package'] != package or local in symbols[package]):
            raise ValueError('符号身份／文件归属无效或重复')
        if declaration['kind'] == 'type' and not declaration['public']:
            raise ValueError('对象声明须为public')
        symbols[package][local] = dict(kind=declaration['kind'], target=name, public=declaration['public'])
    scopes = {}; graph_imports = []; production_edges = set(); test_edges = set()
    for path, header in sorted(headers.items()):
        package = header['package']; bindings = deepcopy(symbols[package]); imports = []; seen = set()

        def bind(local, value):
            if local in bindings: raise ValueError('导入名称重复或遮蔽同包符号：' + local)
            bindings[local] = deepcopy(value)

        for item in header['imports']:
            specifier = item['specifier']; alias = item['alias']
            if specifier in seen: raise ValueError('导入声明重复')
            seen.add(specifier)
            origin = 'WORKSPACE'; target = None
            if specifier in SDK_IMPORTS:
                if not path.endswith('_test.cj') or alias is not None:
                    raise ValueError('标准单测导入仅限测试文件')
                target = specifier[:-2]; kind = 'wildcard'; origin = 'FIXED_SDK'
            elif specifier.endswith('.*'):
                target = specifier[:-2]; kind = 'wildcard'
                if target not in symbols or not packages[target]['production_paths']:
                    raise ValueError('导入必须来自工作区生产包')
                for local, value in sorted(symbols[target].items()):
                    if value['public']: bind(local, value)
            elif specifier in packages:
                target = specifier; kind = 'package'
                if not packages[target]['production_paths']: raise ValueError('不能导入测试专用包')
                members = {n: deepcopy(s) for n, s in sorted(symbols[target].items()) if s['public']}
                bind(alias or target.rsplit('.', 1)[-1], dict(kind='package', target=target, members=members))
            else:
                if '.' not in specifier: raise ValueError('不支持外部导入')
                target, local = specifier.rsplit('.', 1); kind = 'symbol'
                symbol = symbols.get(target, {}).get(local)
                if symbol is None or not symbol['public']:
                    raise ValueError('导入符号不存在或非公开：' + specifier)
                bind(alias or local, symbol)
            record = dict(specifier=specifier, kind=kind, alias=alias, target_package=target,
                          path=path, line=item['line'], origin=origin)
            imports.append(record); graph_imports.append(deepcopy(record))
            if origin == 'WORKSPACE':
                (test_edges if path.endswith('_test.cj') else production_edges).add((package, target))
        scopes[path] = dict(package=package, imports=imports, bindings=dict(sorted(bindings.items())),
                            body_items=deepcopy(header['body_items']))
    order = _topological(packages, production_edges | test_edges)
    graph = dict(version=1, packages=list(packages), production_edges=[list(e) for e in sorted(production_edges)],
                 test_edges=[list(e) for e in sorted(test_edges)], imports=graph_imports, topological_order=order)
    return dict(packages=packages, scopes=scopes, dependency_graph=graph, graph_hash=digest(graph))


def resolve(scope, spelling, *, kind=None):
    if type(spelling) is not str or kind not in (None, 'function', 'type'):
        raise ValueError('符号拼写或类别无效')
    parts = spelling.split('.')
    if not 1 <= len(parts) <= 2: raise ValueError('调用须使用文件内名称或包别名')
    for part in parts: local_name(part)
    binding = scope['bindings'].get(parts[0])
    if len(parts) == 2:
        binding = binding.get('members', {}).get(parts[1]) if binding and binding['kind'] == 'package' else None
    if binding is None or binding['kind'] not in ('function', 'type') or kind and binding['kind'] != kind:
        raise ValueError('符号未在本文件作用域中声明：' + spelling)
    return binding['target']
