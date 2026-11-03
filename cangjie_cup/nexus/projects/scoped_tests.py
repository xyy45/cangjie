"""Literal-only original tests resolved through their own file imports."""
from copy import deepcopy

from nexus.projects.index import TestParser
from nexus.projects.names import local_name, suite_name, case_name
from nexus.projects.scopes import resolve, SDK_IMPORTS
from nexus.repair.object_values import value as object_value
from nexus.repair.values import primitive
from nexus.uploads.language import NAME


class ScopedTestParser(TestParser):
    def __init__(self,*,scope,declared,types):
        self.scope=deepcopy(scope); self.items=self.scope['body_items']; self.pos=0
        self.declared=declared; self.types=types; self.package=scope['package']; self.path=scope['path']

    def name(self): return local_name(self.take())

    def callable(self,kind):
        spelling=self.name(); binding=self.scope['bindings'].get(spelling)
        if binding and binding['kind']=='package':
            self.take('.'); spelling+='.'+self.name()
        return resolve(self.scope,spelling,kind=kind),spelling

    def primitive(self):
        if NAME.fullmatch(self.peek()) and self.peek() not in ('true','false'):
            kind,_=self.callable('type'); self.take('('); fields={}
            for index,field in enumerate(self.types[kind]['fields']):
                if index:self.take(',')
                fields[field['name']]=primitive(self.primitive(),field['type'])
            self.take(')')
            return object_value({'$type':kind,'fields':fields},kind,self.types)
        return super().primitive()

    def cases(self):
        actual={i['specifier'] for i in self.scope['imports'] if i['origin']=='FIXED_SDK'}
        if actual!=SDK_IMPORTS: raise ValueError('工程测试须显式导入标准单测和testmacro')
        output=[]; classes=set()
        while self.peek()!='<eof>':
            self.take('@'); self.take('Test'); self.take('class'); cls=self.name()
            if cls in classes or cls in self.scope['bindings']: raise ValueError('测试类重复或与作用域符号冲突')
            suite=suite_name(self.package+'.'+cls); classes.add(cls); self.take('{'); names=set()
            while self.peek()!='}':
                self.take('@');self.take('TestCase');self.take('func');line=self.items[self.pos][1];name=self.name()
                if name in names: raise ValueError('工程测试标识重复')
                names.add(name);self.take('(');self.take(')');self.take('{')
                self.take('@');self.take('Expect');self.take('(');start=self.pos
                function,spelling=self.callable('function'); self.take('('); args=[]
                if self.peek()!=')':
                    while True:
                        args.append(self.primitive())
                        if len(args)>4: raise ValueError('测试调用参数过多')
                        if not self.accept(','):break
                self.take(')');call_tokens=[v for v,_ in self.items[start:self.pos]];projection=None
                if self.accept('.'):projection=self.name()
                self.take(',');expected=self.primitive();self.take(')');self.accept(';');self.take('}')
                signature=self.declared[function]
                if len(args)!=len(signature['params']): raise ValueError('测试参数个数与签名不一致')
                for argument,param in zip(args,signature['params']):primitive(argument,param['type'],self.types)
                expected_type=signature['return_type']
                if projection is not None:
                    definition=self.types.get(expected_type)
                    field=next((f for f in definition['fields'] if f['name']==projection),None) if definition else None
                    if field is None: raise ValueError('测试投影须为已声明对象字段')
                    expected_type=field['type']
                elif expected_type in self.types: raise ValueError('对象返回须逐字段投影')
                primitive(expected,expected_type,self.types)
                item=dict(id=case_name(suite+'.'+name),function=function,function_spelling=spelling,
                    call_tokens=call_tokens,args=args,expected=expected,path=self.path,line=line)
                if projection is not None:item.update(projection=[projection],expected_type=expected_type)
                output.append(item)
                if len(output)>256:raise ValueError('工程最多256条原测试')
            self.take('}')
            if not names:raise ValueError('工程测试类不能为空')
        if not output:raise ValueError('工程测试文件缺少可识别测试')
        return output
