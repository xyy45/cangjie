"""Closed, non-executing index for primitive same-package Cangjie projects.

Tests are preserved verbatim. Only literal @Expect cases are accepted initially;
arbitrary setup, imports and build options are intentionally outside this gate.
The fixed SDK remains the authority for compilation and actual test execution.
"""
import hashlib
import re
import tomllib

from nexus.repair.values import decode_string_literal,array,primitive
from nexus.projects.archive import read_entries
from nexus.uploads.language import Parser, TOKEN, NAME, RESERVED, tokens

TEST_TOKEN=re.compile(TOKEN.pattern+r'|[@.]')


def _config(files):
    try:
        config=tomllib.loads(files['cjpm.toml'].decode('utf-8'))
        lock=tomllib.loads(files.get('cjpm.lock',b'version=0\n[requires]\n').decode('utf-8'))
    except (UnicodeError,ValueError) as exc:raise ValueError('cjpm配置或锁文件不是有效UTF-8 TOML') from exc
    if set(config)-{'package','dependencies','test-dependencies'} or config.get('dependencies',{})!={} or config.get('test-dependencies',{})!={}:
        raise ValueError('工程只允许静态包配置，不支持外部依赖、脚本或目标覆盖')
    package=config.get('package')
    allowed={'name','version','cjc-version','output-type','description','target-dir','compile-option','override-compile-option','link-option','package-configuration'}
    if not isinstance(package,dict) or set(package)-allowed:raise ValueError('工程package配置含不支持的选项')
    name=package.get('name')
    if not isinstance(name,str) or not NAME.fullmatch(name) or name in RESERVED:raise ValueError('工程包名须为简单仓颉标识符')
    if package.get('cjc-version')!='1.0.5' or package.get('output-type')!='static':raise ValueError('工程须使用固定1.0.5工具链和static输出类型')
    if not isinstance(package.get('version'),str) or not re.fullmatch(r'\d+\.\d+\.\d+',package['version']):raise ValueError('工程版本须为三段数字')
    for key in ('target-dir','compile-option','override-compile-option','link-option'):
        if package.get(key,'')!='':raise ValueError('工程不支持自定义'+key)
    if package.get('package-configuration',{})!={}:raise ValueError('工程不支持子包配置')
    if set(lock)-{'version','requires'} or type(lock.get('version')) is not int or lock['version']!=0 or lock.get('requires',{})!={}:
        raise ValueError('工程锁文件含不支持的依赖或版本')
    return name


class TestParser(Parser):
    def __init__(self,source,declared,package,path,types=None):
        self.items=tokens(source,pattern=TEST_TOKEN);self.pos=0
        self.declared=declared;self.package=package;self.path=path
        from nexus.repair.object_values import registry
        self.types=registry(types or {})

    def primitive(self):
        if self.peek() in self.types:
            from nexus.repair.object_values import value
            kind=self.take();self.take('(');fields={}
            for index,field in enumerate(self.types[kind]['fields']):
                if index:self.take(',')
                fields[field['name']]=primitive(self.primitive(),field['type'],self.types)
            self.take(')');return value({'$type':kind,'fields':fields},kind,self.types)
        if self.accept('['):
            items=[]
            if self.peek()!=']':
                while True:
                    if self.peek()=='[':raise ValueError('工程测试不支持嵌套数组')
                    item=self.primitive();primitive(item,'Int64');items.append(item)
                    if len(items)>16:raise ValueError('工程测试数组最多16项')
                    if not self.accept(','):break
            self.take(']');return array(items)
        negative=self.accept('-');value=self.take()
        if value in ('true','false') and not negative:return value=='true'
        if value.startswith('"') and not negative:return decode_string_literal(value)
        if not value.isascii() or not value.isdigit() or len(value)>19:raise ValueError('工程测试只支持Int64/Bool字面量')
        result=int(value)*(-1 if negative else 1)
        if not -(1<<63)<=result<(1<<63):raise ValueError('工程测试整数超出Int64')
        return result

    def cases(self):
        self.take('package')
        if self.name()!=self.package:raise ValueError('测试包名与工程不一致')
        self.accept(';');imports=set()
        while self.accept('import'):
            self.take('std');self.take('.');self.take('unittest');self.take('.')
            module='std.unittest'
            if self.accept('testmacro'):self.take('.');module+='.testmacro'
            self.take('*');self.accept(';')
            if module in imports:raise ValueError('工程测试导入重复')
            imports.add(module)
        if imports!={'std.unittest','std.unittest.testmacro'}:raise ValueError('工程测试须显式导入标准单测和testmacro')
        output=[];classes=set()
        while self.peek()!='<eof>':
            self.take('@');self.take('Test');self.take('class');cls=self.name()
            if cls in classes or cls in self.declared:raise ValueError('工程测试类名称重复或与生产函数冲突')
            classes.add(cls);self.take('{');names=set()
            while self.peek()!='}':
                self.take('@');self.take('TestCase');self.take('func');line=self.items[self.pos][1];name=self.name()
                if name in names:raise ValueError('工程测试标识重复')
                names.add(name);self.take('(');self.take(')');self.take('{')
                self.take('@');self.take('Expect');self.take('(');function=self.name();self.take('(');args=[]
                if self.peek()!=')':
                    while True:
                        args.append(self.primitive())
                        if len(args)>4:raise ValueError('工程测试调用参数过多')
                        if not self.accept(','):break
                self.take(')');projection=None
                if self.accept('.'):
                    from nexus.repair.object_values import name as object_name
                    projection=object_name(self.take())
                self.take(',');expected=self.primitive();self.take(')');self.accept(';');self.take('}')
                signature=self.declared.get(function)
                if not signature or len(args)!=len(signature['params']):raise ValueError('工程测试参数与入口签名不匹配')
                for actual,param in zip(args,signature['params']):primitive(actual,param['type'],self.types)
                expected_type=signature['return_type']
                if projection is not None:
                    definition=self.types.get(expected_type)
                    field=next((f for f in definition['fields'] if f['name']==projection),None) if definition else None
                    if field is None:raise ValueError('测试投影必须为返回对象的已声明字段')
                    expected_type=field['type']
                elif expected_type in self.types:raise ValueError('对象返回测试须逐字段投影，不能使用默认对象相等比较')
                try:primitive(expected,expected_type,self.types)
                except ValueError:
                    raise ValueError('工程测试函数或字面量类型与签名不匹配')
                item=dict(id=cls+'.'+name,function=function,args=args,expected=expected,path=self.path,line=line)
                if projection is not None:item.update(projection=[projection],expected_type=expected_type)
                output.append(item)
                if len(output)>256:raise ValueError('工程最多256个公开测试')
            self.take('}')
            if not names:raise ValueError('工程测试类不能为空')
        if not output:raise ValueError('工程测试文件缺少可识别测试')
        return output


def inspect_project(files):
    files=read_entries(files);package=_config(files)
    for path,raw in files.items():
        try:text=raw.decode('utf-8')
        except UnicodeError as exc:raise ValueError('工程材料必须使用UTF-8：'+path) from exc
        if '\0' in text:raise ValueError('工程材料包含空字节：'+path)
    production=sorted(p for p in files if p.endswith('.cj') and not p.endswith('_test.cj'))
    tests=sorted(p for p in files if p.endswith('_test.cj'))
    scoped=any(p.count('/')!=1 for p in production+tests)
    if not scoped:
        scoped=any(value=='import' for p in production for value,_ in tokens(files[p].decode()))
    if not scoped:
        for path in tests:
            items=tokens(files[path].decode(),pattern=TEST_TOKEN)
            if any(value=='import' and items[i+1][0]==package for i,(value,_) in enumerate(items[:-1])):
                scoped=True;break
    if scoped:
        from nexus.projects.scoped_index import inspect_scoped
        try:return inspect_scoped(files,package)
        except (RecursionError,IndexError) as exc:raise ValueError('工程语法或嵌套超出支持范围') from exc
    functions=[];declared={};types={};methods=[];type_paths={}
    try:
        from nexus.uploads.object_types import collect
        from nexus.repair.object_values import registry
        for path in production:
            headers=collect(files[path].decode(),validate=False)
            for name,definition in headers['types'].items():
                if name in types:raise ValueError('工程对象类型名称重复：'+name)
                types[name]=definition;type_paths[name]=path
        types=registry(types)
        for path in production:
            info=Parser(files[path].decode(),types=types if types else None).program(headers_only=True)
            if info['package']!=package:raise ValueError('生产源码包名与cjpm不一致：'+path)
            for f in info['functions']:
                if f['name'] in declared:raise ValueError('工程函数名称重复：'+f['name'])
                declared[f['name']]=f;functions.append({**f,'path':path})
        if len(functions)>128:raise ValueError('工程最多128个生产函数')
        validated=[]
        for path in production:
            parser=Parser(files[path].decode(),types=types if types else None);parser.declared=declared;info=parser.program()
            validated.extend({**f,'path':path} for f in info['functions'])
            methods.extend({**m,'path':path} for m in info.get('methods',[]))
        if len(functions)+len(methods)>128:raise ValueError('工程顶层函数与实例方法共最多128个函数体')
        if types:functions=validated
        cases=[];test_classes=set()
        for path in tests:
            items=TestParser(files[path].decode(),declared,package,path,types=types).cases()
            classes={c['id'].split('.')[0] for c in items}
            if classes&test_classes:raise ValueError('工程不同文件中存在重复测试类')
            test_classes.update(classes);cases.extend(items)
    except (RecursionError,IndexError) as exc:raise ValueError('工程语法或嵌套超出支持范围') from exc
    ids=[c['id'] for c in cases]
    if len(ids)>256 or len(set(ids))!=len(ids):raise ValueError('工程测试超过256项或存在重复标识')
    manifest={p:hashlib.sha256(data).hexdigest() for p,data in sorted(files.items())}
    result=dict(version=1,package=package,production_paths=production,test_paths=tests,functions=functions,
        test_cases=cases,manifest=manifest,frozen_manifest={p:h for p,h in manifest.items() if p not in production})
    if types:result.update(types=types,type_paths=type_paths,methods=methods)
    return result


def validate_project_candidate(files,baseline_index):
    current=inspect_project(files)
    def interfaces(info):
        return {f['name']:(f['path'],f['params'],f['return_type'],f['public']) for f in info['functions']}
    if (current['package']!=baseline_index['package'] or set(current['manifest'])!=set(baseline_index['manifest']) or
            current['production_paths']!=baseline_index['production_paths'] or current['frozen_manifest']!=baseline_index['frozen_manifest'] or
            interfaces(current)!=interfaces(baseline_index) or current.get('types')!=baseline_index.get('types') or
            current.get('type_paths')!=baseline_index.get('type_paths') or
            current.get('graph_hash')!=baseline_index.get('graph_hash') or current.get('version')!=baseline_index.get('version')):
        raise ValueError('候选不能改变工程包、文件范围、函数接口或冻结测试/配置')
