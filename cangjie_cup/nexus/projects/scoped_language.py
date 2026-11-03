"""File-scoped names on the existing closed typed expression parser."""
from copy import deepcopy

from nexus.projects.names import local_name
from nexus.projects.scopes import resolve
from nexus.repair.object_values import LEAVES, registry
from nexus.uploads.language import Parser


class ScopedParser(Parser):
    def __init__(self, *, scope, types, object_headers, declared):
        self.scope=deepcopy(scope); self.items=deepcopy(object_headers['top_items']); self.pos=0
        self.locals={}; self.calls=[]; self.call_sites=[]; self.depth=0
        self.declared=declared; self.types=registry(types); self.receiver_type=None
        self.object_headers=deepcopy(object_headers)

    def forbidden_local(self, identifier):
        binding=self.scope['bindings'].get(identifier)
        return binding and (binding['kind'] in ('package','type') or
                            binding['target'].rsplit('.',1)[0] != self.scope['package'])

    def name(self):
        identifier=local_name(self.take())
        if self.forbidden_local(identifier): raise ValueError('局部名称不能遮蔽导入或对象类型')
        return identifier

    def function_name(self):
        identifier=local_name(self.take()); canonical=self.scope['package']+'.'+identifier
        if resolve(self.scope,identifier,kind='function')!=canonical:
            raise ValueError('函数声明与本包符号表不一致')
        return canonical

    def reference(self, value):
        if value in self.locals: return value
        binding=self.scope['bindings'].get(value)
        if binding and binding['kind']=='package':
            self.take('.'); value+='.'+local_name(self.take())
        return resolve(self.scope,value)

    def type(self):
        value=self.take()
        if value=='Array':
            self.take('<'); self.take('Int64'); self.take('>'); return 'Array<Int64>'
        if value in LEAVES: return value
        if self.accept('.'): value+='.'+local_name(self.take())
        return resolve(self.scope,value,kind='type')

    def method_record(self, method, headers_only):
        if any(self.forbidden_local(p['name']) for p in method['params']):
            raise ValueError('方法参数不能遮蔽导入或对象类型')
        result=super().method_record(method,headers_only)
        result['package']=self.scope['package']
        return result

    def program(self,headers_only=False):
        if self.peek()=='<eof>' and not self.object_headers.get('types'):
            if self.scope['imports']:raise ValueError('空命名空间文件只允许package声明')
            return dict(package=self.scope['package'],functions=[])
        info=super().program(headers_only)
        info['package']=self.scope['package']
        for function in info['functions']:
            local=function['name'].rsplit('.',1)[-1]
            function.update(local_name=local,package=self.scope['package'],scope=dict(
                version=1,root_package=self.scope['root_package'],package=self.scope['package'],
                local_name=local,path=self.scope['path'],graph_hash=self.scope['graph_hash']))
        return info
