"""Closed object operations; primitive arithmetic delegates to the existing engine."""
import ast
from nexus.repair import object_values,values

HELPERS={'object_get','object_with','object_new'}


def constant(node):
    if not isinstance(node,ast.Constant) or type(node.value) is not str:raise ValueError('对象类型和字段必须为常量String')
    return node.value


def field(kind,key,types):
    if kind not in types:raise ValueError('字段读取要求已声明对象')
    selected=next((f for f in types[kind]['fields'] if f['name']==key),None)
    if selected is None:raise ValueError('对象字段未声明')
    return selected


def expression_type(node,names,types):
    from nexus.repair import oracle
    types=object_values.registry(types or {});helper=node.func.id
    if helper=='object_new':
        kind=constant(node.args[0])
        if kind not in types:raise ValueError('构造模型对象的类型未声明')
        fields=types[kind]['fields']
        if len(node.args)!=len(fields)+1:raise ValueError('构造模型对象字段数量不符')
        for supplied,declared in zip(node.args[1:],fields):
            if oracle.expression_type(supplied,names,types)!=declared['type']:raise ValueError('构造模型对象字段类型不符')
        return kind
    if len(node.args)!=(2 if helper=='object_get' else 3):raise ValueError('对象辅助参数数量无效')
    kind=oracle.expression_type(node.args[0],names,types);selected=field(kind,constant(node.args[1]),types)
    if helper=='object_get':return selected['type']
    if oracle.expression_type(node.args[2],names,types)!=selected['type']:raise ValueError('替换对象字段的类型不符')
    return kind


def evaluate(node,env,types):
    from nexus.repair import oracle
    types=object_values.registry(types or {});clean={};names={}
    for name,value in env.items():
        kind=value.get('$type') if type(value) is dict else {int:'Int64',bool:'Bool',str:'String',list:'Array<Int64>'}.get(type(value))
        clean[name]=values.primitive(value,kind,types);names[name]=kind
    oracle.expression_type(node,names,types)
    def delegated(tree,items):
        bindings={'__value'+str(i):v for i,v in enumerate(items)}
        return oracle.evaluate(tree,bindings,allow_arrays=True)
    def argument(index):return ast.Name(id='__value'+str(index),ctx=ast.Load())
    def run(child):
        if isinstance(child,ast.Constant):return oracle.evaluate(child,{},allow_arrays=True)
        if isinstance(child,ast.Name):return values.primitive(clean[child.id],names[child.id],types)
        if isinstance(child,ast.List):return values.array([run(n) for n in child.elts])
        if isinstance(child,ast.IfExp):return run(child.body if oracle.boolean(run(child.test)) else child.orelse)
        if isinstance(child,ast.BoolOp):
            for value in child.values:
                truth=oracle.boolean(run(value))
                if isinstance(child.op,ast.And) and not truth:return False
                if isinstance(child.op,ast.Or) and truth:return True
            return isinstance(child.op,ast.And)
        if isinstance(child,ast.UnaryOp):
            if isinstance(child.op,ast.USub) and isinstance(child.operand,ast.Constant) and type(child.operand.value) is int:return oracle.integer(-child.operand.value)
            return delegated(ast.UnaryOp(op=child.op,operand=argument(0)),[run(child.operand)])
        if isinstance(child,ast.BinOp):return delegated(ast.BinOp(left=argument(0),op=child.op,right=argument(1)),[run(child.left),run(child.right)])
        if isinstance(child,ast.Compare):
            previous=run(child.left)
            for op,other in zip(child.ops,child.comparators):
                current=run(other)
                if type(previous) is dict or type(current) is dict:
                    a=object_values.typed_key(previous,types);b=object_values.typed_key(current,types)
                    if a[0]!=b[0] or not isinstance(op,(ast.Eq,ast.NotEq)):raise ValueError('对象比较类型或运算无效')
                    truth=a==b if isinstance(op,ast.Eq) else a!=b
                else:truth=delegated(ast.Compare(left=argument(0),ops=[op],comparators=[argument(1)]),[previous,current])
                if not truth:return False
                previous=current
            return True
        if isinstance(child,ast.Call):
            helper=child.func.id
            if helper in HELPERS:
                if helper=='object_new':
                    kind=constant(child.args[0]);fields=types[kind]['fields']
                    return object_values.value({'$type':kind,'fields':{f['name']:run(n) for f,n in zip(fields,child.args[1:])}},kind,types)
                result=run(child.args[0]);kind=result['$type'];selected=field(kind,constant(child.args[1]),types)
                if helper=='object_get':return values.primitive(result['fields'][selected['name']],selected['type'])
                result['fields'][selected['name']]=run(child.args[2]);return object_values.value(result,kind,types)
            items=[run(n) for n in child.args]
            return delegated(ast.Call(func=child.func,args=[argument(i) for i in range(len(items))],keywords=[]),items)
        raise ValueError('对象规则语法无效')
    return run(node)
