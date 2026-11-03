"""Bounded relations over two genuine calls; parsing never executes source."""
from copy import deepcopy
import itertools
import json
import random
import re

from nexus.repair import oracle,properties,values as primitive_values,object_values

ALGORITHM='paired-relations-v1'
FIELDS={'version','kind','function','domains','relations','seed','max_pairs','excluded_inputs'}


def sampler(contract):
    return {**{k:deepcopy(contract[k]) for k in ('signature','domains','seed','excluded_inputs')},'max_cases':128}


def pair_key(pair):
    if type(pair) is not dict or set(pair)!={'left','right'}:raise ValueError('关系输入对字段无效')
    for side in ('left','right'):
        args=pair[side]
        if type(args) is not list or len(args)>4:raise ValueError('关系参数数组无效')
        for value in args:
            primitive_values.typed_key(value)
    return (oracle.input_key(pair['left']),oracle.input_key(pair['right']))


def pair_score(pair):
    pair_key(pair)
    items=[v for side in ('left','right') for v in pair[side]]
    if any(type(v) in (str,list,dict) for v in items):return (sum(primitive_values.primitive_weight(v) for v in items),tuple(primitive_values.typed_key(v) for v in items))
    return (sum(abs(int(v)) for v in items),tuple(int(v) for v in items))


def _environment(contract,pair):
    pair_key(pair);env={}
    for side in ('left','right'):
        args,_=properties._arguments(contract,pair[side])
        env.update({side+'_'+name:value for name,value in args.items()})
    return env


def _types(contract,*,results=False):
    names={side+'_arg'+str(i):p['type'] for side in ('left','right') for i,p in enumerate(contract['signature']['params'])}
    if results:names.update({side+'_result':contract['signature']['return_type'] for side in ('left','right')})
    return names


def applicable(contract,pair):
    env=_environment(contract,pair);types=_types(contract)
    return [r['id'] for r in contract['relations'] if oracle.boolean(oracle.evaluate(properties._tree(r['precondition'],types,**properties.model_options(contract)),env,**properties.model_options(contract)))]


def evaluate_pair(contract,pair,left_result,right_result):
    env=_environment(contract,pair);kind=contract['signature']['return_type']
    for side,value in (('left',left_result),('right',right_result)):
        env[side+'_result']=primitive_values.primitive(value,kind,contract['signature'].get('types'))
    ids=applicable(contract,pair);types=_types(contract,results=True);failures=[];passed=[]
    for relation in contract['relations']:
        if relation['id'] not in ids:continue
        holds=oracle.boolean(oracle.evaluate(properties._tree(relation['assertion'],types,**properties.model_options(contract)),env,**properties.model_options(contract)))
        if holds:passed.append(relation['id'])
        else:failures.append(dict(kind='business_relation',relation_id=relation['id'],relation_text=relation['text'],
            left_args=list(pair['left']),right_args=list(pair['right']),left_actual_return=left_result,
            right_actual_return=right_result,assertion_value=False,expected_relation=True))
    return deepcopy(dict(state='UNKNOWN' if not ids else 'FAIL' if failures else 'PASS',applicable=ids,passed=passed,failures=failures))


def generate_pairs(contract,axes=None,cumulative=None):
    primitive=sampler(contract);axes=oracle.checked_axes(primitive,axes)
    pool=oracle.generate_inputs(primitive,axes);limit=contract['max_pairs']
    if type(cumulative) not in (list,type(None)):raise ValueError('累计关系反例必须为数组')
    required=[];required_keys=set()
    for pair in cumulative or []:
        key=pair_key(pair)
        if not applicable(contract,pair):raise ValueError('累计输入对无适用关系')
        if key not in required_keys:required_keys.add(key);required.append(deepcopy(pair))
        if len(required)>limit:raise ValueError('累计关系反例超过执行预算')
    candidates=[];seen=set();checks=0
    def add(pair):
        nonlocal checks
        checks+=1;key=pair_key(pair)
        if key in seen:return
        seen.add(key)
        if any(not oracle.permitted_input(contract,pair[side]) for side in ('left','right')):return
        ids=applicable(contract,pair)
        if ids:candidates.append((deepcopy(pair),set(ids)))
    def structured():
        for args in pool:yield dict(left=args,right=args)
        for args in pool:
            for i,axis in enumerate(axes):
                for value in axis:
                    other=list(args);other[i]=value
                    yield dict(left=args,right=other)
                    yield dict(left=other,right=args)
    # Mandatory entries count against the first half of the condition-check budget.
    for pair in required:add(pair)
    for pair in itertools.islice(structured(),4096-checks):add(pair)
    rng=random.Random(contract['seed'])
    if pool:
        if len(pool)**2<=4096:
            combinations=list(itertools.product(pool,pool));rng.shuffle(combinations)
            for left,right in combinations:add(dict(left=left,right=right))
        else:
            for _ in range(4096):add(dict(left=rng.choice(pool),right=rng.choice(pool)))
    chosen=deepcopy(required);selected=set(required_keys)
    covered={i for pair in chosen for i in applicable(contract,pair)}
    wanted={r['id'] for r in contract['relations']}
    while covered!=wanted:
        best=max(candidates,key=lambda item:len(item[1]-covered),default=None)
        if best is None or not best[1]-covered:raise ValueError('关系在有限采样域中没有适用输入对')
        if len(chosen)>=limit:raise ValueError('关系覆盖与累计反例超过执行预算')
        chosen.append(deepcopy(best[0]));selected.add(pair_key(best[0]));covered.update(best[1])
    for pair,ids in candidates:
        key=pair_key(pair)
        if len(chosen)>=limit:break
        if key not in selected:chosen.append(deepcopy(pair));selected.add(key)
    return dict(pairs=chosen,candidate_checks=checks,regression_pairs=len(required))


def shrink_pairs(contract,pair,relation_id,axes=None):
    if type(relation_id) is not str or relation_id not in applicable(contract,pair):raise ValueError('缩减关系必须适用原输入对')
    primitive=sampler(contract);axes=oracle.checked_axes(primitive,axes)
    original=pair_score(pair);items=[];seen=set();params=contract['signature']['params']
    def add(value):
        key=pair_key(value)
        if key in seen or pair_score(value)>=original:return
        seen.add(key)
        if any(not oracle.permitted_input(contract,value[side]) for side in ('left','right')):return
        if relation_id in applicable(contract,value):items.append(deepcopy(value))
    for side in ('left','right'):
        for args in oracle.shrink_inputs(primitive,pair[side],axes):add({**pair,side:args})
    if 'scope' in contract['signature']:
        # Distinct nominal values can encode a coupled premise (e.g. amounts
        # differ by one). Each closed object axis has at most16 admitted values;
        # at most4*16*16 combinations, still filtered by score/guard/reservations.
        types=contract['signature'].get('types',{})
        for i,param in enumerate(params):
            if param['type'] not in types or pair['left'][i]==pair['right'][i]:continue
            for left,right in itertools.product(axes[i],repeat=2):
                candidate=deepcopy(pair);candidate['left'][i]=left;candidate['right'][i]=right;add(candidate)
    # Equal arguments often encode the business premise (fixed price). Shrink both.
    for i,p in enumerate(params):
        left,right=pair['left'][i],pair['right'][i]
        if type(left) is not type(right) or left!=right:continue
        values=list(axes[i])
        if p['type']=='Int64':values.extend([left//2,left-1,left+1])
        for value in values:
            if p['type']=='Int64' and not contract['domains'][p['name']]['min']<=value<=contract['domains'][p['name']]['max']:continue
            candidate=deepcopy(pair);candidate['left'][i]=value;candidate['right'][i]=value;add(candidate)
    return sorted(items,key=pair_score)[:16]


def validate_contract(value,signature,examples):
    if type(value) is not dict or set(value)!=FIELDS:raise ValueError('关系契约字段无效')
    try:size=len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())
    except (TypeError,ValueError,RecursionError):raise ValueError('关系契约不是有效JSON数据') from None
    if size>16*1024:raise ValueError('关系JSON最多16KiB')
    signature=oracle.stable_signature(signature);kinds=object_values.LEAVES|set(signature.get('types',{}))
    if (type(signature) is not dict or type(signature.get('name')) is not str or 'scope' not in signature and not re.fullmatch(r'[A-Za-z_]\w*',signature['name']) or
        type(signature.get('params')) is not list or len(signature['params'])>4 or signature.get('return_type') not in kinds):raise ValueError('关系函数签名无效')
    params=signature['params']
    if any(type(p) is not dict or type(p.get('name')) is not str or not re.fullmatch(r'[A-Za-z_]\w*',p['name']) or p.get('type') not in kinds for p in params) or len({p['name'] for p in params})!=len(params):raise ValueError('关系参数签名无效')
    if type(value['version']) is not int or value['version']!=properties.version(signature) or value['kind']!='relation' or value['function']!=signature['name']:raise ValueError('关系版本、类型或函数不匹配')
    if type(value['seed']) is not int or not 0<=value['seed']<2**32 or type(value['max_pairs']) is not int or not 16<=value['max_pairs']<=64:raise ValueError('关系seed范围0..2^32-1，max_pairs范围16..64')
    domains=oracle.normalize_domains(value['domains'],params,signature.get('types'));items=value['relations']
    if type(items) is not list or not 1<=len(items)<=8:raise ValueError('关系需1至8项')
    contract=dict(version=value['version'],kind='relation',function=value['function'],domains=domains,relations=[],seed=value['seed'],max_pairs=value['max_pairs'],
        excluded_inputs=deepcopy(value['excluded_inputs']),signature=oracle.stable_signature(signature),
        aliases={side+'_arg'+str(i):p['name'] for side in ('left','right') for i,p in enumerate(params)},algorithm='paired-relations-packages-v5' if value['version']==5 else 'paired-relations-object-v4' if value['version']==4 else 'paired-relations-array-v3' if value['version']==3 else 'paired-relations-string-v2' if value['version']==2 else ALGORITHM)
    seen=set()
    for item in items:
        if type(item) is not dict or set(item)!={'id','text','precondition','assertion'}:raise ValueError('关系项字段无效')
        identity=item['id']
        if type(identity) is not str or not re.fullmatch(r'REL-[A-Z][A-Z0-9-]{0,31}',identity) or identity in seen:raise ValueError('关系ID无效或重复')
        if type(item['text']) is not str or not 1<=len(item['text'])<=500:raise ValueError('关系说明限1至500字符')
        properties._tree(item['precondition'],_types(contract),**properties.model_options(contract));properties._tree(item['assertion'],_types(contract,results=True),**properties.model_options(contract))
        contract['relations'].append(deepcopy(item));seen.add(identity)
    excluded=contract['excluded_inputs']
    if type(excluded) is not list or len(excluded)>128:raise ValueError('关系保留输入最多128项')
    for args in excluded:properties._arguments(contract,args,domain_required=False,reserved_allowed=True)
    if len({oracle.input_key(args) for args in excluded})!=len(excluded):raise ValueError('关系保留输入重复')
    known=[]
    if type(examples) is not list or len(examples)>12:raise ValueError('关系公开示例最多12项')
    for example in examples:
        _,within=properties._arguments(contract,example['args'],domain_required=False)
        primitive_values.primitive(example['expected'],signature['return_type'],signature.get('types'))
        if within:known.append(example)
    for left,right in itertools.product(known,known):
        if evaluate_pair(contract,dict(left=left['args'],right=right['args']),left['expected'],right['expected'])['state']=='FAIL':raise ValueError('关系与已确认公开示例冲突')
    generate_pairs(contract)
    return contract
