"""Bounded nominal records, independent of source parsing and model execution.

An unregistered structural key is an ordering tool, never boundary validation.
"""
import re
from nexus.repair import values

LEAVES={'Int64','Bool','String','Array<Int64>'}
NAME=re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}')
RESERVED=set('package public private protected func let var if else while return break continue for in true false Int64 Bool String Array import class struct init this mut main unsafe static open override interface extend prop foreign throw try catch finally match case enum type'.split())
RESERVED.update('print println eprint eprintln readln panic exit sleep Int8 Int16 Int32 IntNative UInt8 UInt16 UInt32 UInt64 UIntNative Float16 Float32 Float64 Rune Unit Nothing CString Any Object'.split())


def name(value):
    if type(value) is not str or not NAME.fullmatch(value) or value in RESERVED:
        raise ValueError('对象标识符必须为非预留ASCII名称，最多64字符')
    return value


def type_name(value):
    if type(value) is str and '.' in value:
        from nexus.projects.names import symbol_name
        return symbol_name(value)
    return name(value)


def parameters(raw,kinds,limit,minimum=0):
    if type(raw) is not list or not minimum<=len(raw)<=limit:raise ValueError('字段或参数数量越界')
    result=[];seen=set()
    for item in raw:
        if type(item) is not dict or set(item)!={'name','type'}:raise ValueError('字段或参数声明键无效')
        identifier=name(item['name']);kind=item['type']
        if identifier in seen or type(kind) is not str or kind not in kinds:raise ValueError('字段或参数名称重复或类型无效')
        seen.add(identifier);result.append(dict(name=identifier,type=kind))
    return result


def registry(raw):
    if type(raw) is not dict or len(raw)>4:raise ValueError('对象类型注册表最多4项')
    for identifier in raw:type_name(identifier)
    kinds=LEAVES|set(raw);result={}
    for identifier in sorted(raw):
        item=raw[identifier]
        if type(item) is not dict or set(item)!={'kind','fields','constructor','methods'} or item['kind'] not in ('struct','class'):
            raise ValueError('对象声明键或种类无效')
        fields=parameters(item['fields'],LEAVES,4,1)
        constructor=parameters(item['constructor'],LEAVES,4,1)
        if constructor!=fields:raise ValueError('构造参数必须按声明顺序完整绑定字段')
        methods=item['methods'];seen={f['name'] for f in fields}|{identifier.rsplit('.',1)[-1]};checked=[]
        if type(methods) is not list or len(methods)>4:raise ValueError('对象最多4个实例方法')
        for method in methods:
            if type(method) is not dict or set(method)!={'name','params','return_type'}:raise ValueError('实例方法声明键无效')
            method_name=name(method['name']);returned=method['return_type']
            if method_name in seen or type(returned) is not str or returned not in kinds:raise ValueError('实例方法重复、遮蔽或返回类型无效')
            params=parameters(method['params'],kinds,4)
            seen.add(method_name);checked.append(dict(name=method_name,params=params,return_type=returned))
        result[identifier]=dict(kind=item['kind'],fields=fields,constructor=constructor,methods=sorted(checked,key=lambda m:m['name']))
    return result


def is_object_type(kind,types):
    return type(kind) is str and kind in registry(types)


def has_objects(signature):
    types=registry(signature.get('types',{}))
    return signature.get('return_type') in types or any(p.get('type') in types for p in signature.get('params',[]))


def shape(raw):
    if type(raw) is not dict or set(raw)!={'$type','fields'}:raise ValueError('对象必须恰含$type与fields')
    identifier=type_name(raw['$type']);fields=raw['fields']
    if type(fields) is not dict or not 1<=len(fields)<=4:raise ValueError('对象fields必须含1至4个字段')
    for key in fields:name(key)
    return identifier,fields


def value(raw,kind,types):
    declarations=registry(types)
    if type(kind) is not str or kind not in declarations:raise ValueError('对象类型必须由冻结注册表声明')
    identifier,fields=shape(raw);declared=declarations[kind]['fields']
    if identifier!=kind or set(fields)!={f['name'] for f in declared}:raise ValueError('对象tag或字段集合与声明不符')
    return {'$type':kind,'fields':{f['name']:values.primitive(fields[f['name']],f['type']) for f in declared}}


def typed_key(raw,types=None):
    identifier,_=shape(raw)
    if types is not None:raw=value(raw,identifier,types)
    # Only known primitive leaves; nested records are deliberately rejected.
    fields=[]
    for field,item in sorted(raw['fields'].items()):
        if type(item) not in (int,bool,str,list):raise ValueError('对象键不接受嵌套对象或其他值')
        fields.append((field,values.typed_key(item)))
    return identifier,tuple(fields)


def weight(raw,types=None):
    identifier,_=shape(raw)
    if types is not None:raw=value(raw,identifier,types)
    typed_key(raw)
    return sum(values.primitive_weight(item) for item in raw['fields'].values())


def literal(raw,kind,types):
    checked=value(raw,kind,types);parts=[]
    for item in checked['fields'].values():
        if type(item) is str:parts.append(values.string_literal(item))
        elif type(item) is list:parts.append('['+', '.join(str(n) for n in item)+']')
        else:parts.append(str(item).lower() if type(item) is bool else str(item))
    return kind+'('+', '.join(parts)+')'
