"""Versioned, bounded business-rule interpreter. Never executes Python source.

The expression notation uses Python AST syntax, with explicit primitive semantics.
A candidate/model cannot supply or edit the confirmed rule used by verification.
"""
import ast
from copy import deepcopy
import itertools
import random
from functools import lru_cache
from nexus.repair import values as primitive_values, object_values

LOW=-(2**63)
HIGH=2**63-1
ALGORITHM='boundary-search-v1'
ARRAY_ARITY={'array_len':1,'array_sum':1,'array_at':2,'array_append':2,'array_replace':3}


def input_key(args):return tuple((type(x).__name__,primitive_values.typed_key(x) if type(x) is dict else tuple(primitive_values.array(x)) if type(x) is list else x) for x in args)


def permitted_input(contract,args):
    return input_key(args) not in {input_key(a) for a in contract.get('excluded_inputs',[])}


def integer(value):
    if type(value) is not int or not LOW<=value<=HIGH:
        raise ValueError('规则整数必须为Int64，运算不能溢出')
    return value


def boolean(value):
    if type(value) is not bool:raise ValueError('规则条件必须为Bool')
    return value


def expression_tree(text,names,allow_strings=False,allow_arrays=False,allow_objects=False,types=None):
    if allow_objects:
        from nexus.repair.object_values import registry
        registry(types or {})
    return _expression_tree(text,names,allow_strings,allow_arrays or allow_objects,allow_objects)


@lru_cache(maxsize=128)
def _expression_tree(text,names,allow_strings=False,allow_arrays=False,allow_objects=False):
    allow_strings=allow_strings or allow_arrays
    if not isinstance(text,str) or not 1<=len(text)<=1024:raise ValueError('规则表达式限1024字符')
    try:tree=ast.parse(text,mode='eval')
    except (SyntaxError,RecursionError) as exc:raise ValueError('规则表达式语法无效') from exc
    allowed=(ast.Expression,ast.Constant,ast.Name,ast.Load,ast.BinOp,ast.Add,ast.Sub,ast.Mult,
        ast.FloorDiv,ast.Mod,ast.UnaryOp,ast.USub,ast.UAdd,ast.Not,ast.BoolOp,ast.And,ast.Or,
        ast.Compare,ast.Eq,ast.NotEq,ast.Lt,ast.LtE,ast.Gt,ast.GtE,ast.IfExp,ast.Call)
    if allow_arrays:allowed+=(ast.List,)
    helpers=('min','max','ceil_div')+(('byte_len','rune_len') if allow_strings else ())+tuple(ARRAY_ARITY if allow_arrays else ())+(('object_get','object_with','object_new') if allow_objects else ())
    def visit(node,depth=0):
        if depth>24 or not isinstance(node,allowed):raise ValueError('规则包含不支持的表达式')
        if isinstance(node,ast.List) and len(node.elts)>16:raise ValueError('数组表达式最多16项')
        if isinstance(node,ast.Constant):
            if allow_strings and type(node.value) is str:primitive_values.string(node.value)
            elif type(node.value) not in (int,bool):raise ValueError('规则仅支持当前版本的原始类型')
        if isinstance(node,ast.Name) and node.id not in names+helpers:raise ValueError('规则引用了未知参数')
        if isinstance(node,ast.Call):
            if (not isinstance(node.func,ast.Name) or node.keywords or
                    node.func.id not in helpers):
                raise ValueError('规则辅助调用无效')
            count=len(node.args);name=node.func.id
            if name in ('object_get','object_with','object_new'):
                if count not in ({2} if name=='object_get' else {3} if name=='object_with' else {2,3,4,5}):raise ValueError('对象辅助调用参数数量无效')
                marker=node.args[0] if name=='object_new' else node.args[1]
                if not isinstance(marker,ast.Constant) or type(marker.value) is not str:raise ValueError('对象类型和字段必须为常量String')
            if name in ARRAY_ARITY and count!=ARRAY_ARITY[name]:raise ValueError('数组辅助调用参数数量无效')
            if (name in ('byte_len','rune_len') and count!=1 or name=='ceil_div' and count!=2 or
                    name in ('min','max') and not 2<=count<=4):raise ValueError('规则辅助调用参数数量无效')
        for child in ast.iter_child_nodes(node):visit(child,depth+1)
    if len(list(ast.walk(tree)))>120:raise ValueError('规则表达式过于复杂')
    visit(tree)
    return tree.body


def evaluate(node,env,allow_strings=False,allow_arrays=False,allow_objects=False,types=None):
    if allow_objects:
        from nexus.repair.object_expressions import evaluate as evaluate_objects
        return evaluate_objects(node,env,types)
    allow_strings=allow_strings or allow_arrays
    if isinstance(node,ast.Constant):
        if allow_strings and type(node.value) is str:return primitive_values.string(node.value)
        return node.value if type(node.value) is bool else integer(node.value)
    if allow_arrays and isinstance(node,ast.List):return primitive_values.array([evaluate(n,env,allow_arrays=True) for n in node.elts])
    if isinstance(node,ast.Name):
        if node.id not in env:raise ValueError('辅助函数仅可在调用中使用')
        return primitive_values.array(env[node.id]) if allow_arrays and type(env[node.id]) is list else env[node.id]
    if isinstance(node,ast.IfExp):return evaluate(node.body if boolean(evaluate(node.test,env,allow_strings=allow_strings,allow_arrays=allow_arrays)) else node.orelse,env,allow_strings=allow_strings,allow_arrays=allow_arrays)
    if isinstance(node,ast.BoolOp):
        for item in node.values:
            value=boolean(evaluate(item,env,allow_strings=allow_strings,allow_arrays=allow_arrays))
            if isinstance(node.op,ast.And) and not value:return False
            if isinstance(node.op,ast.Or) and value:return True
        return isinstance(node.op,ast.And)
    if isinstance(node,ast.UnaryOp):
        # Int64's negative minimum cannot be represented as a positive literal.
        if isinstance(node.op,ast.USub) and isinstance(node.operand,ast.Constant) and type(node.operand.value) is int:
            return integer(-node.operand.value)
        value=evaluate(node.operand,env,allow_strings=allow_strings,allow_arrays=allow_arrays)
        if isinstance(node.op,ast.Not):return not boolean(value)
        return integer(-integer(value) if isinstance(node.op,ast.USub) else integer(value))
    if isinstance(node,ast.BinOp):
        left=evaluate(node.left,env,allow_strings=allow_strings,allow_arrays=allow_arrays);right=evaluate(node.right,env,allow_strings=allow_strings,allow_arrays=allow_arrays)
        if allow_strings and isinstance(node.op,ast.Add) and type(left) is type(right) is str:
            return primitive_values.string(left+right)
        a=integer(left);b=integer(right)
        if isinstance(node.op,ast.Add):return integer(a+b)
        if isinstance(node.op,ast.Sub):return integer(a-b)
        if isinstance(node.op,ast.Mult):return integer(a*b)
        if b==0:raise ValueError('规则除数不能为0')
        quotient=integer((abs(a)//abs(b))*(-1 if (a<0)!=(b<0) else 1))
        return quotient if isinstance(node.op,ast.FloorDiv) else integer(a-quotient*b)
    if isinstance(node,ast.Compare):
        a=evaluate(node.left,env,allow_strings=allow_strings,allow_arrays=allow_arrays)
        for op,item in zip(node.ops,node.comparators):
            b=evaluate(item,env,allow_strings=allow_strings,allow_arrays=allow_arrays)
            if type(a) is not type(b):raise ValueError('规则比较类型不一致')
            if not isinstance(op,(ast.Eq,ast.NotEq)):integer(a);integer(b)
            ok= a==b if isinstance(op,ast.Eq) else a!=b if isinstance(op,ast.NotEq) else a<b if isinstance(op,ast.Lt) else a<=b if isinstance(op,ast.LtE) else a>b if isinstance(op,ast.Gt) else a>=b
            if not ok:return False
            a=b
        return True
    if isinstance(node,ast.Call):
        if allow_arrays and node.func.id in ARRAY_ARITY:
            args=[evaluate(n,env,allow_arrays=True) for n in node.args]
            if len(args)!=ARRAY_ARITY[node.func.id]:raise ValueError('数组辅助调用参数数量无效')
            items=primitive_values.array(args[0]);name=node.func.id
            if name=='array_len':return len(items)
            if name=='array_sum':
                total=0
                for item in items:total=integer(total+item)
                return total
            if name=='array_append':return primitive_values.array(items+[integer(args[1])])
            index=integer(args[1])
            if not 0<=index<len(items):raise ValueError('数组辅助调用下标越界')
            if name=='array_at':return items[index]
            items[index]=integer(args[2]);return items
        if allow_strings and node.func.id in ('byte_len','rune_len'):
            if len(node.args)!=1:raise ValueError('字符串长度调用需要一个参数')
            value=evaluate(node.args[0],env,allow_strings=True,allow_arrays=allow_arrays)
            return (primitive_values.byte_len if node.func.id=='byte_len' else primitive_values.rune_len)(value)
        args=[integer(evaluate(n,env,allow_strings=allow_strings,allow_arrays=allow_arrays)) for n in node.args]
        if node.func.id=='min':return min(args)
        if node.func.id=='max':return max(args)
        a,b=args
        if a<0 or b<=0:raise ValueError('ceil_div要求非负被除数和正除数')
        return integer(a//b+(a%b!=0))
    raise ValueError('规则语法无效')


def expected(contract,args):
    sig=contract['signature'];params=sig['params']
    if 'scope' in sig:return _object_expected(contract,args)
    if object_values.has_objects(sig):return _object_expected(contract,args)
    if primitive_values.has_arrays(sig):return _array_expected(contract,args)
    if primitive_values.has_strings(sig):return _string_expected(contract,args)
    if not isinstance(args,list) or len(args)!=len(params):raise ValueError('规则参数数量不符')
    env={}
    for p,value in zip(params,args):
        domain=contract['domains'][p['name']]
        if p['type']=='Bool':boolean(value)
        else:
            integer(value)
            if not domain['min']<=value<=domain['max']:raise ValueError('输入超出已确认规则参数域')
        env[p['name']]=value
    result=evaluate(expression_tree(contract['expression'],tuple(env)),env)
    if sig['return_type']=='Bool':return boolean(result)
    return integer(result)


def axis_values(domain,kind,types=None):
    if kind in (types or {}):return [primitive_values.primitive(v,kind,types) for v in domain['values']]
    if kind=='Bool':return [False,True]
    if kind=='Array<Int64>':return [primitive_values.array(v) for v in domain['values']]
    if kind=='String':return list(domain['values'])
    lo,hi=domain['min'],domain['max'];values=[max(lo,min(0,hi)),lo,hi]
    for point in domain.get('points',[])+[lo,hi,0]:values.extend(p for p in (point,point-1,point+1) if lo<=p<=hi)
    return list(dict.fromkeys(values))


def checked_axes(contract,axes=None):
    expected_axes=[axis_values(contract['domains'][p['name']],p['type'],contract['signature'].get('types')) for p in contract['signature']['params']]
    if axes is None:return expected_axes
    # A reference check is not a runtime fallback: the supplied native result
    # must be complete and type-exact, including Bool versus Int64.
    if (type(axes) is not list or len(axes)!=len(expected_axes) or
            any(type(axis) is not list or len(axis)!=len(want) or
                any(type(a) is not type(b) or primitive_values.typed_key(a)!=primitive_values.typed_key(b) for a,b in zip(axis,want))
                for axis,want in zip(axes,expected_axes))):
        raise ValueError('原生边界轴类型、顺序或参数域不符')
    return deepcopy(axes)


def generate_inputs(contract,axes=None):
    params=contract['signature']['params'];axes=checked_axes(contract,axes)
    limit=contract['max_cases'];items=[];seen=set()
    def add(values):
        key=input_key(values)
        if key not in seen and len(items)<limit and permitted_input(contract,values):seen.add(key);items.append(deepcopy(list(values)))
    base=[a[0] for a in axes];add(base)
    # One-axis boundary coverage first, then bounded interactions and random search.
    for i,axis in enumerate(axes):
        for v in axis:
            row=list(base);row[i]=v;add(row)
    for row in itertools.islice(itertools.product(*axes),max(0,limit*2)):
        if len(items)>=limit*3//4:break
        add(row)
    rng=random.Random(contract['seed'])
    for _ in range(limit*8):
        add([bool(rng.getrandbits(1)) if p['type']=='Bool' else rng.choice(contract['domains'][p['name']]['values']) if p['type'] in ('String','Array<Int64>') or p['type'] in contract['signature'].get('types',{}) else rng.randint(contract['domains'][p['name']]['min'],contract['domains'][p['name']]['max']) for p in params])
        if len(items)>=limit:break
    return items


def shrink_inputs(contract,args,axes=None):
    params=contract['signature']['params'];strings=primitive_values.has_strings(contract['signature']) or primitive_values.has_arrays(contract['signature']) or object_values.has_objects(contract['signature'])
    score=lambda row:sum(primitive_values.primitive_weight(v) if strings else abs(int(v)) for v in row)
    axes=checked_axes(contract,axes)
    items=[];seen=set();original=score(args)
    for i,p in enumerate(params):
        domain=contract['domains'][p['name']]
        values=list(axes[i])
        if p['type']=='Int64':values.extend([args[i]//2,args[i]-1,args[i]+1])
        for v in values:
            if p['type']=='Int64' and not domain['min']<=v<=domain['max']:continue
            row=deepcopy(args);row[i]=deepcopy(v);key=input_key(row)
            if key not in seen and score(row)<original and permitted_input(contract,row):seen.add(key);items.append(row)
    return sorted(items,key=lambda row:(score(row),tuple(primitive_values.typed_key(x) for x in row) if strings else tuple(int(x) for x in row)))[:32]


def normalize_domains(domains,params,types=None):
    declarations=object_values.registry(types or {})
    """Shared primitive domains; preserves the existing v1/v2 normalization."""
    if not isinstance(domains,dict) or set(domains)!={p['name'] for p in params}:raise ValueError('请为全部参数设置规则域')
    clean={}
    for p in params:
        d=domains[p['name']]
        if not isinstance(d,dict):raise ValueError('参数域必须为对象')
        if p['type'] in declarations:
            if set(d)!={'values'} or type(d['values']) is not list or not 1<=len(d['values'])<=16:raise ValueError('对象域需要1至16个明确完整values')
            values=[primitive_values.primitive(v,p['type'],declarations) for v in d['values']]
            if len({primitive_values.typed_key(v,declarations) for v in values})!=len(values):raise ValueError('对象域不能重复')
            clean[p['name']]=dict(values=values);continue
        if p['type']=='Array<Int64>':
            if set(d)!={'values'} or type(d['values']) is not list or not 1<=len(d['values'])<=16:raise ValueError('Array域需要1至16个明确values')
            values=[primitive_values.array(value) for value in d['values']]
            if len({primitive_values.typed_key(value) for value in values})!=len(values):raise ValueError('Array域不能重复')
            clean[p['name']]=dict(values=values);continue
        if p['type']=='String':
            if set(d)!={'values'} or type(d['values']) is not list or not 1<=len(d['values'])<=16:
                raise ValueError('String域需要1至16个明确values')
            values=[primitive_values.string(value) for value in d['values']]
            if len(set(values))!=len(values):raise ValueError('String域不能重复')
            clean[p['name']]=dict(values=values);continue
        if p['type']=='Bool':
            if d:raise ValueError('Bool参数域为{}，自动覆盖true/false')
            clean[p['name']]={};continue
        if set(d)-{'min','max','points'} or not {'min','max'}<=set(d):raise ValueError('整数参数域需要min/max，可选points')
        lo=integer(d['min']);hi=integer(d['max']);points=d.get('points',[])
        if lo>hi or not isinstance(points,list) or len(points)>8 or any(type(x) is not int or not lo<=x<=hi for x in points):raise ValueError('规则参数域或临界点无效')
        clean[p['name']]=dict(min=lo,max=hi,points=list(dict.fromkeys(points)))
    return clean


def validate_contract(value,signature,examples):
    from nexus.repair.scoped_signature import reject_qualified_legacy
    reject_qualified_legacy(signature)
    if 'scope' in signature or type(value) is dict and value.get('version')==6:
        return _validate_object_contract(value,signature,examples)
    if object_values.has_objects(signature) or type(value) is dict and value.get('version')==5:
        return _validate_object_contract(value,signature,examples)
    if primitive_values.has_arrays(signature) or type(value) is dict and value.get('version')==4:
        return _validate_array_contract(value,signature,examples)
    if primitive_values.has_strings(signature) or type(value) is dict and value.get('version')==3:
        return _validate_string_contract(value,signature,examples)
    fields={'version','function','domains','expression','seed','max_cases'}
    if isinstance(value,dict) and value.get('version')==2:fields.add('excluded_inputs')
    if not isinstance(value,dict) or set(value)!=fields:raise ValueError('规则字段或保留输入契约无效')
    if type(value['version']) is not int or value['version'] not in (1,2) or value['function']!=signature['name']:
        raise ValueError('规则版本或函数不匹配')
    if not isinstance(value['expression'],str):raise ValueError('规则表达式必须为字符串')
    params=signature['params'];domains=value['domains']
    # Keep the legacy validation order and accepted values unchanged.
    if not isinstance(domains,dict) or set(domains)!={p['name'] for p in params}:raise ValueError('请为全部参数设置规则域')
    if type(value['seed']) is not int or not 0<=value['seed']<2**32 or type(value['max_cases']) is not int or not 16<=value['max_cases']<=256:
        raise ValueError('规则seed范围0..2^32-1，max_cases范围16..256')
    clean=normalize_domains(domains,params)
    stable_signature={k:signature[k] for k in ('name','params','return_type')}
    result={**value,'domains':clean,'signature':stable_signature,'algorithm':ALGORITHM if value['version']==1 else 'boundary-search-reserved-v2'}
    if value['version']==2:
        excluded=value['excluded_inputs']
        if not isinstance(excluded,list) or not 1<=len(excluded)<=128:raise ValueError('保留输入限1至128项')
        keys=[]
        for args in excluded:
            expected(result,args);keys.append(input_key(args))
        if len(set(keys))!=len(keys):raise ValueError('保留输入重复')
        if any(not permitted_input(result,e['args']) for e in examples):raise ValueError('公开示例不能列为保留输入')
    expression_tree(result['expression'],tuple(p['name'] for p in params))
    generated=generate_inputs(result)
    if not generated:raise ValueError('规则没有可搜索输入')
    for args in generated:expected(result,args)
    for example in examples:
        answer=expected(result,example['args'])
        if type(answer) is not type(example['expected']) or answer!=example['expected']:raise ValueError('规则与已确认公开示例的预期值不一致')
    return result


def expression_type(node,names,types=None):
    """Static types for explicitly versioned String models; never evaluates data."""
    def infer(child):return expression_type(child,names,types)
    def require(actual,want):
        if actual!=want:raise ValueError('String规则表达式类型不匹配')
    if isinstance(node,ast.Constant):
        if type(node.value) is str:primitive_values.string(node.value);return 'String'
        if type(node.value) is bool:return 'Bool'
        integer(node.value);return 'Int64'
    if isinstance(node,ast.List):
        if len(node.elts)>16:raise ValueError('数组常量最多16项')
        for value in node.elts:require(infer(value),'Int64')
        return 'Array<Int64>'
    if isinstance(node,ast.Name):
        if node.id not in names:raise ValueError('表达式引用未知变量或未调用辅助函数')
        return names[node.id]
    if isinstance(node,ast.UnaryOp):
        if isinstance(node.op,ast.USub) and isinstance(node.operand,ast.Constant) and type(node.operand.value) is int:
            integer(-node.operand.value);return 'Int64'
        kind='Bool' if isinstance(node.op,ast.Not) else 'Int64';require(infer(node.operand),kind);return kind
    if isinstance(node,ast.BinOp):
        left=infer(node.left);right=infer(node.right)
        if isinstance(node.op,ast.Add) and left==right=='String':return 'String'
        require(left,'Int64');require(right,'Int64');return 'Int64'
    if isinstance(node,ast.BoolOp):
        for child in node.values:require(infer(child),'Bool')
        return 'Bool'
    if isinstance(node,ast.IfExp):
        require(infer(node.test),'Bool');kind=infer(node.body);require(infer(node.orelse),kind);return kind
    if isinstance(node,ast.Compare):
        previous=infer(node.left)
        for op,value in zip(node.ops,node.comparators):
            kind=infer(value);require(kind,previous)
            if not isinstance(op,(ast.Eq,ast.NotEq)):require(kind,'Int64')
            previous=kind
        return 'Bool'
    if isinstance(node,ast.Call):
        if node.func.id in ('object_get','object_with','object_new'):
            from nexus.repair.object_expressions import expression_type as object_type
            return object_type(node,names,types)
        if node.func.id in ARRAY_ARITY:
            name=node.func.id
            if len(node.args)!=ARRAY_ARITY[name]:raise ValueError('数组辅助调用参数数量无效')
            require(infer(node.args[0]),'Array<Int64>')
            for value in node.args[1:]:require(infer(value),'Int64')
            return 'Array<Int64>' if name in ('array_append','array_replace') else 'Int64'
        kind='String' if node.func.id in ('byte_len','rune_len') else 'Int64'
        for value in node.args:require(infer(value),kind)
        return 'Int64'
    raise ValueError('String规则表达式无效')


def _string_expected(contract,args):
    if contract.get('version')!=3:raise ValueError('String规则必须使用version3')
    sig=contract['signature'];params=sig['params']
    if type(args) is not list or len(args)!=len(params):raise ValueError('String规则参数数量不符')
    env={}
    for p,value in zip(params,args):
        primitive_values.primitive(value,p['type']);domain=contract['domains'][p['name']]
        if p['type']=='String' and value not in domain['values'] or p['type']=='Int64' and not domain['min']<=value<=domain['max']:
            raise ValueError('输入超出已确认String规则参数域')
        env[p['name']]=value
    node=expression_tree(contract['expression'],tuple(env),allow_strings=True)
    return primitive_values.primitive(evaluate(node,env,allow_strings=True),sig['return_type'])


def _validate_string_contract(value,signature,examples):
    fields={'version','function','domains','expression','seed','max_cases','excluded_inputs'}
    if type(value) is not dict or set(value)!=fields:raise ValueError('String规则字段无效')
    if type(value['version']) is not int or value['version']!=3 or value['function']!=signature['name'] or not primitive_values.has_strings(signature):
        raise ValueError('String规则需要匹配String签名与version3')
    params=signature['params'];kinds=[signature['return_type'],*[p['type'] for p in params]]
    if len(params)>4 or any(kind not in ('Int64','Bool','String') for kind in kinds):raise ValueError('String规则签名无效')
    if type(value['seed']) is not int or not 0<=value['seed']<2**32 or type(value['max_cases']) is not int or not 16<=value['max_cases']<=256:raise ValueError('String规则搜索预算无效')
    clean=normalize_domains(value['domains'],params)
    result={**value,'domains':clean,'signature':{k:signature[k] for k in ('name','params','return_type')},'algorithm':'boundary-string-v3'}
    names={p['name']:p['type'] for p in params};node=expression_tree(value['expression'],tuple(names),allow_strings=True)
    if expression_type(node,names)!=signature['return_type']:raise ValueError('String规则返回类型不匹配')
    excluded=value['excluded_inputs']
    if type(excluded) is not list or len(excluded)>128:raise ValueError('String保留输入最多128项')
    for args in excluded:_string_expected(result,args)
    if len({input_key(a) for a in excluded})!=len(excluded):raise ValueError('String保留输入重复')
    if any(not permitted_input(result,e['args']) for e in examples):raise ValueError('公开示例不能列为保留输入')
    generated=generate_inputs(result)
    if not generated:raise ValueError('String规则没有可搜索输入')
    for args in generated:_string_expected(result,args)
    for example in examples:
        answer=_string_expected(result,example['args']);primitive_values.primitive(example['expected'],signature['return_type'])
        if type(answer) is not type(example['expected']) or answer!=example['expected']:raise ValueError('String规则与公开示例不一致')
    return result



def _array_expected(contract,args):
    if contract.get('version')!=4:raise ValueError('Array规则必须使用version4')
    sig=contract['signature'];params=sig['params']
    if type(args) is not list or len(args)!=len(params):raise ValueError('Array规则参数数量不符')
    env={}
    for p,value in zip(params,args):
        clean=primitive_values.primitive(value,p['type']);domain=contract['domains'][p['name']]
        if (p['type'] in ('String','Array<Int64>') and clean not in domain['values'] or
                p['type']=='Int64' and not domain['min']<=clean<=domain['max']):raise ValueError('输入超出已确认Array规则域')
        env[p['name']]=clean
    return primitive_values.primitive(evaluate(expression_tree(contract['expression'],tuple(env),allow_arrays=True),env,allow_arrays=True),sig['return_type'])


def _validate_array_contract(value,signature,examples):
    fields={'version','function','domains','expression','seed','max_cases','excluded_inputs'}
    if type(value) is not dict or set(value)!=fields:raise ValueError('Array规则字段无效')
    if type(value['version']) is not int or value['version']!=4 or value['function']!=signature['name'] or not primitive_values.has_arrays(signature):raise ValueError('Array规则需要匹配Array签名与version4')
    params=signature['params'];kinds=[signature['return_type'],*[p['type'] for p in params]]
    if len(params)>4 or any(kind not in ('Int64','Bool','String','Array<Int64>') for kind in kinds):raise ValueError('Array规则签名无效')
    if type(value['seed']) is not int or not 0<=value['seed']<2**32 or type(value['max_cases']) is not int or not 16<=value['max_cases']<=256:raise ValueError('Array规则搜索预算无效')
    result=deepcopy(value);result.update(domains=normalize_domains(value['domains'],params),signature={k:deepcopy(signature[k]) for k in ('name','params','return_type')},algorithm='boundary-array-v4')
    names={p['name']:p['type'] for p in params};node=expression_tree(value['expression'],tuple(names),allow_arrays=True)
    if expression_type(node,names)!=signature['return_type']:raise ValueError('Array规则返回类型不匹配')
    excluded=result['excluded_inputs']
    if type(excluded) is not list or len(excluded)>128:raise ValueError('Array保留输入最多128项')
    for args in excluded:_array_expected(result,args)
    if len({input_key(a) for a in excluded})!=len(excluded):raise ValueError('Array保留输入重复')
    if any(not permitted_input(result,e['args']) for e in examples):raise ValueError('公开示例不能列为保留输入')
    generated=generate_inputs(result)
    if not generated:raise ValueError('Array规则没有可搜索输入')
    for args in generated:_array_expected(result,args)
    for example in examples:
        answer=_array_expected(result,example['args']);observed=primitive_values.primitive(example['expected'],signature['return_type'])
        if primitive_values.typed_key(answer)!=primitive_values.typed_key(observed):raise ValueError('Array规则与公开示例不一致')
    return result


def stable_signature(signature):
    """Keep only frozen callable metadata; registry is never model-supplied."""
    from nexus.repair.scoped_signature import validate,reject_qualified_legacy
    if 'scope' in signature:return validate(signature)
    reject_qualified_legacy(signature)
    result={k:deepcopy(signature[k]) for k in ('name','params','return_type')}
    if object_values.has_objects(signature):
        import re
        declarations=object_values.registry(signature.get('types',{}));kinds=object_values.LEAVES|set(declarations)
        if type(signature.get('name')) is not str or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',signature['name']):raise ValueError('对象函数名无效')
        params=object_values.parameters(signature['params'],kinds,4)
        if signature['return_type'] not in kinds:raise ValueError('对象函数返回类型无效')
        result.update(params=params,types=declarations)
    return result


def _object_expected(contract,args):
    sig=contract['signature']
    if contract.get('version')!=(6 if 'scope' in sig else 5):raise ValueError('对象或Scoped规则版本不匹配')
    params=sig['params'];declarations=sig.get('types',{})
    if type(args) is not list or len(args)!=len(params):raise ValueError('对象规则参数数量不符')
    env={}
    for p,value in zip(params,args):
        clean=primitive_values.primitive(value,p['type'],declarations);domain=contract['domains'][p['name']]
        if (p['type'] in declarations or p['type'] in ('String','Array<Int64>')) and clean not in domain['values'] or p['type']=='Int64' and not domain['min']<=clean<=domain['max']:raise ValueError('输入超出已确认对象规则域')
        env[p['name']]=clean
    options=dict(allow_objects=True,types=declarations)
    node=expression_tree(contract['expression'],tuple(env),**options)
    return primitive_values.primitive(evaluate(node,env,**options),sig['return_type'],declarations)


def _validate_object_contract(value,signature,examples):
    import json
    fields={'version','function','domains','expression','seed','max_cases','excluded_inputs'}
    if type(value) is not dict or set(value)!=fields:raise ValueError('对象规则字段无效')
    try:size=len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())
    except (TypeError,ValueError,RecursionError):raise ValueError('对象规则不是有效JSON数据') from None
    if size>8192:raise ValueError('对象规则JSON最多8KiB')
    scoped='scope' in signature;version=6 if scoped else 5
    if type(value['version']) is not int or value['version']!=version or value['function']!=signature['name'] or not scoped and not object_values.has_objects(signature):raise ValueError('对象或Scoped规则签名与版本不匹配')
    sig=stable_signature(signature);declarations=sig.get('types',{});params=sig['params']
    if type(value['seed']) is not int or not 0<=value['seed']<2**32 or type(value['max_cases']) is not int or not 16<=value['max_cases']<=256:raise ValueError('对象规则搜索预算无效')
    result=deepcopy(value);result.update(domains=normalize_domains(value['domains'],params,declarations),signature=sig,algorithm='boundary-packages-v6' if scoped else 'boundary-object-v5')
    names={p['name']:p['type'] for p in params};node=expression_tree(value['expression'],tuple(names),allow_objects=True,types=declarations)
    if expression_type(node,names,types=declarations)!=sig['return_type']:raise ValueError('对象规则返回类型不匹配')
    excluded=result['excluded_inputs']
    if type(excluded) is not list or len(excluded)>128:raise ValueError('对象保留输入最多128项')
    for args in excluded:_object_expected(result,args)
    if len({input_key(a) for a in excluded})!=len(excluded):raise ValueError('对象保留输入重复')
    if any(not permitted_input(result,e['args']) for e in examples):raise ValueError('公开示例不能列为保留输入')
    generated=generate_inputs(result)
    if not generated:raise ValueError('对象规则没有可搜索输入')
    for args in generated:_object_expected(result,args)
    for example in examples:
        answer=_object_expected(result,example['args']);observed=primitive_values.primitive(example['expected'],sig['return_type'],declarations)
        if primitive_values.typed_key(answer,declarations)!=primitive_values.typed_key(observed,declarations):raise ValueError('对象规则与公开示例不一致')
    return result
