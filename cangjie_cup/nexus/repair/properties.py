"""Versioned single-call invariants over genuine observed primitive returns.

This module parses/validates/evaluates bounded data only. It never runs the
candidate, a model, Python eval, or user-supplied Cangjie verification source.
"""
import ast
from copy import deepcopy
import json
import re

from nexus.repair import oracle,values as primitive_values,object_values

ALGORITHM='single-properties-v1'
FIELDS={'version','kind','function','domains','properties','seed','max_cases','excluded_inputs'}


def _type(node,names,allow_strings=False,allow_arrays=False,allow_objects=False,types=None):
    if allow_strings or allow_arrays or allow_objects:return oracle.expression_type(node,names,types=types)
    def require(actual,want):
        if actual!=want:raise ValueError('属性表达式类型不匹配')
    if isinstance(node,ast.Constant):
        if type(node.value) is bool:return 'Bool'
        oracle.integer(node.value);return 'Int64'
    if isinstance(node,ast.Name):
        if node.id not in names:raise ValueError('属性引用未知变量或未调用辅助函数')
        return names[node.id]
    if isinstance(node,ast.UnaryOp):
        if isinstance(node.op,ast.USub) and isinstance(node.operand,ast.Constant) and type(node.operand.value) is int:
            oracle.integer(-node.operand.value);return 'Int64'
        kind='Bool' if isinstance(node.op,ast.Not) else 'Int64'
        require(_type(node.operand,names),kind);return kind
    if isinstance(node,ast.BinOp):
        require(_type(node.left,names),'Int64');require(_type(node.right,names),'Int64');return 'Int64'
    if isinstance(node,ast.BoolOp):
        for value in node.values:require(_type(value,names),'Bool')
        return 'Bool'
    if isinstance(node,ast.IfExp):
        require(_type(node.test,names),'Bool');kind=_type(node.body,names)
        require(_type(node.orelse,names),kind);return kind
    if isinstance(node,ast.Compare):
        previous=_type(node.left,names)
        for op,value in zip(node.ops,node.comparators):
            kind=_type(value,names);require(kind,previous)
            if not isinstance(op,(ast.Eq,ast.NotEq)):require(kind,'Int64')
            previous=kind
        return 'Bool'
    if isinstance(node,ast.Call):
        for value in node.args:require(_type(value,names),'Int64')
        return 'Int64'
    raise ValueError('不支持的属性表达式')


def _tree(text,names,allow_strings=False,allow_arrays=False,allow_objects=False,types=None):
    if type(text) is not str:raise ValueError('属性前置条件与断言必须为字符串')
    tree=oracle.expression_tree(text,tuple(names),allow_strings=allow_strings,allow_arrays=allow_arrays,allow_objects=allow_objects,types=types)
    if _type(tree,names,allow_strings=allow_strings,allow_arrays=allow_arrays,allow_objects=allow_objects,types=types)!='Bool':raise ValueError('属性前置条件与断言必须为Bool')
    return tree


def model_options(contract):
    options=dict(allow_strings=contract['version']>=2,allow_arrays=contract['version']>=3)
    if contract['version'] in (4,5):options.update(allow_objects=True,types=contract['signature'].get('types',{}))
    return options


def version(signature):
    from nexus.repair.scoped_signature import validate,reject_qualified_legacy
    if 'scope' in signature:validate(signature);return 5
    reject_qualified_legacy(signature)
    return 4 if object_values.has_objects(signature) else 3 if primitive_values.has_arrays(signature) else 2 if primitive_values.has_strings(signature) else 1


def sampler(contract):
    return {k:deepcopy(contract[k]) for k in ('signature','domains','seed','max_cases','excluded_inputs')}


def _arguments(contract,args,*,domain_required=True,reserved_allowed=False):
    params=contract['signature']['params']
    if type(args) is not list or len(args)!=len(params):raise ValueError('属性参数数量无效')
    env={};within=True
    for index,(p,value) in enumerate(zip(params,args)):
        if p['type']=='Bool':oracle.boolean(value)
        elif p['type'] in ('String','Array<Int64>') or p['type'] in contract['signature'].get('types',{}):
            value=primitive_values.primitive(value,p['type'],contract['signature'].get('types'));within&=value in contract['domains'][p['name']]['values']
        else:
            oracle.integer(value);domain=contract['domains'][p['name']]
            within&=domain['min']<=value<=domain['max']
        env['arg'+str(index)]=value
    if domain_required and not within:raise ValueError('输入超出已确认属性域')
    if not reserved_allowed and not oracle.permitted_input(contract,args):raise ValueError('不能执行保留输入')
    return env,within


def applicable(contract,args):
    env,_=_arguments(contract,args);types={a:p['type'] for a,p in zip(env,contract['signature']['params'])}
    return [p['id'] for p in contract['properties'] if oracle.boolean(oracle.evaluate(_tree(p['precondition'],types,**model_options(contract)),env,**model_options(contract)))]


def evaluate_result(contract,args,result):
    env,_=_arguments(contract,args)
    result=primitive_values.primitive(result,contract['signature']['return_type'],contract['signature'].get('types'))
    ids=applicable(contract,args);env['result']=result
    types={f'arg{i}':p['type'] for i,p in enumerate(contract['signature']['params'])};types['result']=contract['signature']['return_type']
    failures=[];passed=[]
    for prop in contract['properties']:
        if prop['id'] not in ids:continue
        holds=oracle.boolean(oracle.evaluate(_tree(prop['assertion'],types,**model_options(contract)),env,**model_options(contract)))
        if holds:passed.append(prop['id'])
        else:failures.append(dict(kind='business_property',property_id=prop['id'],property_text=prop['text'],
            args=deepcopy(args),actual_return=deepcopy(result),assertion_value=False,expected_property=True))
    return dict(state='UNKNOWN' if not ids else 'FAIL' if failures else 'PASS',applicable=ids,passed=passed,failures=failures)


def validate_contract(value,signature,examples):
    if type(value) is not dict or set(value)!=FIELDS:raise ValueError('属性契约字段无效')
    try:size=len(json.dumps(value,ensure_ascii=False).encode())
    except (TypeError,ValueError,RecursionError):raise ValueError('属性契约不是有效JSON数据') from None
    if size>16*1024:raise ValueError('属性JSON最多16KiB')
    if type(value['version']) is not int or value['version']!=version(signature) or value['kind']!='single' or value['function']!=signature['name']:
        raise ValueError('属性版本、类型或函数不匹配')
    signature=oracle.stable_signature(signature);params=signature['params'];kinds=object_values.LEAVES|set(signature.get('types',{}))
    if len(params)>4 or signature['return_type'] not in kinds or any(p['type'] not in kinds for p in params):
        raise ValueError('属性仅支持最多4参数的Int64/Bool函数')
    if type(value['seed']) is not int or not 0<=value['seed']<2**32 or type(value['max_cases']) is not int or not 16<=value['max_cases']<=128:
        raise ValueError('属性seed范围0..2^32-1，max_cases范围16..128')
    domains=oracle.normalize_domains(value['domains'],params,signature.get('types'))
    types={f'arg{i}':p['type'] for i,p in enumerate(params)};with_result={**types,'result':signature['return_type']}
    props=value['properties']
    if type(props) is not list or not 1<=len(props)<=8:raise ValueError('属性需1至8项')
    clean=[];seen=set()
    for prop in props:
        if type(prop) is not dict or set(prop)!={'id','text','precondition','assertion'}:raise ValueError('属性项字段无效')
        identity=prop['id']
        if not isinstance(identity,str) or not re.fullmatch(r'PROP-[A-Z][A-Z0-9-]{0,31}',identity) or identity in seen:raise ValueError('属性ID无效或重复')
        if not isinstance(prop['text'],str) or not 1<=len(prop['text'])<=500:raise ValueError('属性说明限1至500字符')
        _tree(prop['precondition'],types,**model_options(dict(version=value['version'],signature=signature)));_tree(prop['assertion'],with_result,**model_options(dict(version=value['version'],signature=signature)))
        clean.append(dict(prop));seen.add(identity)
    excluded=value['excluded_inputs']
    if type(excluded) is not list or len(excluded)>128:raise ValueError('属性保留输入最多128项')
    contract=dict(version=value['version'],kind='single',function=value['function'],domains=domains,properties=clean,seed=value['seed'],
        max_cases=value['max_cases'],excluded_inputs=deepcopy(excluded),signature=oracle.stable_signature(signature),
        aliases={f'arg{i}':p['name'] for i,p in enumerate(params)},algorithm='single-properties-packages-v5' if value['version']==5 else 'single-properties-object-v4' if value['version']==4 else 'single-properties-array-v3' if value['version']==3 else 'single-properties-string-v2' if value['version']==2 else ALGORITHM)
    for args in excluded:_arguments(contract,args,domain_required=False,reserved_allowed=True)
    if len({oracle.input_key(a) for a in excluded})!=len(excluded):raise ValueError('属性保留输入重复')
    generated=oracle.generate_inputs(sampler(contract));coverage={p['id']:0 for p in clean}
    for args in generated:
        for identity in applicable(contract,args):coverage[identity]+=1
    if not generated or not all(coverage.values()):raise ValueError('属性在有限采样域中没有适用输入，请调整域或条件')
    for example in examples:
        _,within=_arguments(contract,example['args'],domain_required=False)
        primitive_values.primitive(example['expected'],signature['return_type'],signature.get('types'))
        if within and evaluate_result(contract,example['args'],example['expected'])['state']=='FAIL':raise ValueError('属性与已确认公开示例冲突')
    return contract
