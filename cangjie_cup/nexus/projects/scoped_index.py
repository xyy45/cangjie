"""Two-pass closed package index; compilation remains an independent check."""
from copy import deepcopy
import hashlib

from nexus.projects.names import local_name
from nexus.projects.scopes import read_header, build_scopes, resolve
from nexus.projects.scoped_language import ScopedParser
from nexus.repair import object_values
from nexus.uploads.object_types import collect, Cursor


def _function_headers(items):
    cursor=Cursor(items); result=[]
    while cursor.peek()!='<eof>':
        public=cursor.accept('public');cursor.take('func');name=local_name(cursor.take())
        params=cursor.params();cursor.take(':');returned=cursor.type();cursor.block()
        result.append(dict(local_name=name,params=params,return_type=returned,public=public))
    return result


def inspect_scoped(files,root_package):
    production=sorted(p for p in files if p.endswith('.cj') and not p.endswith('_test.cj'))
    tests=sorted(p for p in files if p.endswith('_test.cj'))
    headers={p:read_header(files[p].decode('utf-8'),p,root_package) for p in production+tests}
    collected={p:collect(files[p].decode('utf-8'),validate=False,header=headers[p]) for p in production}
    function_headers={p:_function_headers(collected[p]['top_items']) for p in production}
    declarations=[]
    for path in production:
        package=headers[path]['package']
        for kind,names in [('function',[f['local_name'] for f in function_headers[path]]),('type',list(collected[path]['types']))]:
            for name in names:
                public=kind=='type' or next(f['public'] for f in function_headers[path] if f['local_name']==name)
                declarations.append(dict(name=package+'.'+name,local_name=name,package=package,path=path,kind=kind,public=public))
    metadata=build_scopes(files,root_package,declarations)
    scopes={p:{**s,'root_package':root_package,'path':p,'graph_hash':metadata['graph_hash']} for p,s in metadata['scopes'].items()}

    def kind(spelling,path):
        if spelling in object_values.LEAVES:return spelling
        return resolve(scopes[path],spelling,kind='type')

    def signature(raw,path):
        return {**raw,'params':[{**p,'type':kind(p['type'],path)} for p in raw['params']],
                'return_type':kind(raw['return_type'],path)}

    types={};type_paths={};prepared={}
    for path in production:
        package=headers[path]['package'];info=deepcopy(collected[path]);typed={}
        for local,definition in info['types'].items():
            name=package+'.'+local;definition['methods']=[signature(m,path) for m in definition['methods']]
            types[name]=definition;type_paths[name]=path;typed[name]=definition
        info['types']=typed
        info['methods']=[{**signature(m,path),'owner':package+'.'+m['owner']} for m in info['methods']]
        prepared[path]=info
    types=object_values.registry(types)
    declared={}
    for path in production:
        for raw in function_headers[path]:
            name=headers[path]['package']+'.'+raw['local_name']
            declared[name]={**signature(raw,path),'name':name}
    if len(declared)>128:raise ValueError('工程最多128个生产函数体')
    functions=[];methods=[]
    for path in production:
        info=ScopedParser(scope=scopes[path],types=types,object_headers=prepared[path],declared=declared).program()
        functions.extend({**f,'path':path} for f in info['functions'])
        methods.extend({**m,'path':path} for m in info.get('methods',[]))
    if len(functions)+len(methods)>128:raise ValueError('工程总函数体最多128个')
    from nexus.projects.scoped_tests import ScopedTestParser
    cases=[];classes=set()
    for path in tests:
        items=ScopedTestParser(scope=scopes[path],declared=declared,types=types).cases()
        suites={c['id'].rsplit('.',1)[0] for c in items}
        if classes&suites:raise ValueError('同一包不同文件中测试类重复')
        classes.update(suites);cases.extend(items)
    if len(cases)>256 or len({c['id'] for c in cases})!=len(cases):raise ValueError('原测试重复或超过256项')
    manifest={p:hashlib.sha256(raw).hexdigest() for p,raw in sorted(files.items())}
    result=dict(version=2,package=root_package,production_paths=production,test_paths=tests,functions=functions,
        test_cases=cases,manifest=manifest,frozen_manifest={p:h for p,h in manifest.items() if p not in production},
        packages=metadata['packages'],imports={p:s['imports'] for p,s in metadata['scopes'].items()},
        dependency_graph=metadata['dependency_graph'],graph_hash=metadata['graph_hash'])
    if types:result.update(types=types,type_paths=type_paths,methods=methods)
    return result
