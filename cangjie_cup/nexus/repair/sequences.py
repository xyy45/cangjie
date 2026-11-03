"""Bounded, confirmed Markov models and reachable primitive-state paths.

This module never executes candidates. Model errors are distinct from filtered
initial conditions or reserved calls; actual failures require SDK observations.
"""
from copy import deepcopy
import itertools
import json
import random
import re

from nexus.repair import oracle,properties,values as primitive_values,object_values

ALGORITHM='state-sequences-v1'
FIELDS={'version','kind','function','state_param','domains','initial_states','initial_precondition','context_params','operations','invariants','seed','max_sequences','max_steps','excluded_inputs'}


def _primitive(value,kind,types=None):
    return primitive_values.primitive(value,kind,types)


def _within(contract,index,value):
    param=contract['signature']['params'][index];_primitive(value,param['type'],contract['signature'].get('types'))
    domain=contract['domains'][param['name']]
    if param['type'] in ('String','Array<Int64>') or param['type'] in contract['signature'].get('types',{}):return value in domain['values']
    return param['type']=='Bool' or domain['min']<=value<=domain['max']


def _same(a,b):return type(a) is type(b) and a==b


def _tree(text,names,kind,allow_strings=False,allow_arrays=False,allow_objects=False,types=None):
    if type(text) is not str:raise ValueError('序列表达式必须为字符串')
    tree=oracle.expression_tree(text,tuple(names),allow_strings=allow_strings,allow_arrays=allow_arrays,allow_objects=allow_objects,types=types)
    if properties._type(tree,names,allow_strings=allow_strings,allow_arrays=allow_arrays,allow_objects=allow_objects,types=types)!=kind:raise ValueError('序列表达式类型不匹配')
    return tree


def _names(contract):
    return {f'arg{i}':p['type'] for i,p in enumerate(contract['signature']['params'])}


def _invariant_names(contract):
    kind=contract['signature']['return_type']
    return {**_names(contract),'initial_state':kind,'before_state':kind,'step_index':'Int64'}


def sampler(contract):
    # These are source values for model planning, not executed candidate inputs.
    return dict(signature=deepcopy(contract['signature']),domains=deepcopy(contract['domains']),seed=contract['seed'],max_cases=128,excluded_inputs=[])


def trace_key(trace):
    if type(trace) is not dict or set(trace)!={'initial_state','context','steps'}:raise ValueError('轨迹字段无效')
    primitive_values.typed_key(trace['initial_state'])
    if type(trace['context']) is not list or len(trace['context'])>3:raise ValueError('轨迹上下文无效')
    steps=trace['steps']
    if type(steps) is not list or not 1<=len(steps)<=8:raise ValueError('轨迹步骤限1至8项')
    for value in trace['context']:
        primitive_values.typed_key(value)
    for step in steps:
        if (type(step) is not dict or set(step)!={'operation_id','args'} or type(step['operation_id']) is not str or
                not re.fullmatch(r'OP-[A-Z][A-Z0-9-]{0,31}',step['operation_id']) or type(step['args']) is not list or len(step['args'])>3):
            raise ValueError('轨迹操作无效')
        for value in step['args']:primitive_values.typed_key(value)
    return json.dumps(trace,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def trace_score(trace):
    trace_key(trace)
    values=[trace['initial_state'],*trace['context'],*(a for step in trace['steps'] for a in step['args'])]
    strings=any(type(value) in (str,list,dict) for value in values)
    return (len(trace['steps']),sum(primitive_values.primitive_weight(v) if strings else abs(int(v)) for v in values),trace_key(trace))


def _operation(contract,identity):
    found=next((op for op in contract['operations'] if op['id']==identity),None)
    if found is None:raise ValueError('轨迹引用未知操作')
    return found


def _context(contract,values):
    indices=contract['context_indices']
    if type(values) is not list or len(values)!=len(indices):raise ValueError('上下文参数数量无效')
    for index,value in zip(indices,values):
        if not _within(contract,index,value):raise ValueError('上下文值超出模型域')
    return dict(zip(indices,values))


def _arguments(contract,op,state,concrete,context):
    params=contract['signature']['params'];nonstate=contract['nonstate_indices']
    if type(concrete) is not list or len(concrete)!=len(nonstate):raise ValueError('序列非状态参数数量无效')
    args=[None]*len(params);args[contract['state_index']]=state
    for index,template,value in zip(nonstate,op['args'],concrete):
        if not _within(contract,index,value):raise ValueError('序列参数超出模型域')
        if type(template) is dict and '$type' not in template:
            if 'context' in template and not _same(value,context[index]):raise ValueError('同一轨迹上下文必须保持不变')
        elif not _same(value,template):raise ValueError('具体操作参数与冻结常量不符')
        args[index]=value
    return deepcopy(args)


def _applicable(contract,step):
    names=_invariant_names(contract);env={f'arg{i}':v for i,v in enumerate(step['args'])}
    env.update(initial_state=step['initial_state'],before_state=step['before_state'],step_index=step['step_index'])
    return [item['id'] for item in contract['invariants'] if oracle.boolean(oracle.evaluate(_tree(item['precondition'],names,'Bool',**properties.model_options(contract)),env,**properties.model_options(contract)))]


def evaluate_step(contract,reference_step,actual):
    kind=contract['signature']['return_type'];actual=_primitive(actual,kind,contract['signature'].get('types'))
    step=reference_step;applicable=_applicable(contract,step)
    env={f'arg{i}':v for i,v in enumerate(step['args'])};env.update(initial_state=step['initial_state'],before_state=step['before_state'],step_index=step['step_index'],result=actual,expected_state=step['expected_state'])
    names={**_invariant_names(contract),'result':kind,'expected_state':kind};failures=[]
    if not _same(actual,step['expected_state']):failures.append(dict(failure_id='MODEL-'+step['operation_id'],kind='model_transition',operation_id=step['operation_id'],actual_return=actual,expected_state=step['expected_state']))
    for item in contract['invariants']:
        if item['id'] in applicable and not oracle.boolean(oracle.evaluate(_tree(item['assertion'],names,'Bool',**properties.model_options(contract)),env,**properties.model_options(contract))):
            failures.append(dict(failure_id=item['id'],kind='sequence_invariant',invariant_text=item['text'],actual_return=actual,expected_state=step['expected_state']))
    return deepcopy(dict(state='FAIL' if failures else 'PASS',applicable=applicable,failures=failures))


def _reference_after(contract,args,context):
    """Operation labels are not function inputs: every matching model must agree."""
    kind=contract['signature']['return_type'];state=args[contract['state_index']]
    concrete=[args[i] for i in contract['nonstate_indices']];names={**_names(contract),'state':kind}
    env={f'arg{i}':v for i,v in enumerate(args)};env['state']=state;expected=None
    for operation in contract['operations']:
        try:_arguments(contract,operation,state,concrete,context)
        except ValueError:continue
        after=_primitive(oracle.evaluate(_tree(operation['transition'],names,kind,**properties.model_options(contract)),env,**properties.model_options(contract)),kind,contract['signature'].get('types'))
        if not _within(contract,contract['state_index'],after):raise ValueError('参考状态转移超出已确认状态域')
        if expected is not None and not _same(after,expected):raise ValueError('相同完整输入匹配的操作转移互相矛盾')
        expected=after
    if expected is None:raise ValueError('完整输入没有匹配的状态转移')
    return expected


def reference_trace(contract,trace):
    trace_key(trace)
    if len(trace['steps'])>contract['max_steps']:raise ValueError('轨迹超过已确认步数预算')
    initial=trace['initial_state'];state_index=contract['state_index'];kind=contract['signature']['return_type']
    if not _within(contract,state_index,initial) or not any(_same(initial,x) for x in contract['initial_states']):raise ValueError('轨迹初始状态未确认')
    context=_context(contract,trace['context']);names={'initial_state':kind,**{f'ctx{i}':contract['signature']['params'][i]['type'] for i in contract['context_indices']}}
    env={'initial_state':initial,**{f'ctx{i}':v for i,v in context.items()}}
    if not oracle.boolean(oracle.evaluate(_tree(contract['initial_precondition'],names,'Bool',**properties.model_options(contract)),env,**properties.model_options(contract))):
        return dict(eligible=False,steps=[],reason='INITIAL_PRECONDITION_FALSE')
    state=initial;result=[]
    for index,concrete in enumerate(trace['steps']):
        op=_operation(contract,concrete['operation_id']);args=_arguments(contract,op,state,concrete['args'],context)
        if not oracle.permitted_input(contract,args):return dict(eligible=False,steps=[],reason='RESERVED_INPUT')
        after=_reference_after(contract,args,context)
        step=dict(step_index=index,initial_state=deepcopy(initial),operation_id=op['id'],operation_text=op['text'],args=deepcopy(args),before_state=deepcopy(state),reference_before=deepcopy(state),expected_state=deepcopy(after))
        evaluated=evaluate_step(contract,step,after)
        if evaluated['state']!='PASS':raise ValueError('参考转移与已确认不变量矛盾')
        step['applicable']=evaluated['applicable'];result.append(step);state=after
    return dict(eligible=True,steps=result,reason='')


def _variant_pools(contract,context,rows):
    pools={}
    for op in contract['operations']:
        items=[];seen=set()
        for row in rows:
            values=[]
            for index,template in zip(contract['nonstate_indices'],op['args']):
                values.append(context[index] if type(template) is dict and 'context' in template else row[index] if type(template) is dict and 'domain' in template else template)
            key=oracle.input_key(values)
            if key not in seen:seen.add(key);items.append(dict(operation_id=op['id'],args=values))
        pools[op['id']]=items
    return pools


def generate_traces(contract,axes=None,cumulative=None):
    cumulative=[] if cumulative is None else cumulative
    if type(cumulative) is not list:raise ValueError('累计轨迹必须为数组')
    settings=sampler(contract);oracle.checked_axes(settings,axes);rows=oracle.generate_inputs(settings,axes)
    contexts=[];seen_context=set()
    for row in rows:
        values=[row[i] for i in contract['context_indices']];key=oracle.input_key(values)
        if key not in seen_context:seen_context.add(key);contexts.append(values)
    ids=[op['id'] for op in contract['operations']];wanted={'OP:'+i for i in ids}|{'INV:'+i['id'] for i in contract['invariants']}
    covered=set();selected=[];fillers=[];seen=set();checks=[0,0];limit=contract['max_sequences']
    def coverage(plan):
        return {'OP:'+s['operation_id'] for s in plan['steps']}|{'INV:'+identity for s in plan['steps'] for identity in s['applicable']}
    for trace in cumulative:
        checks[0]+=1
        if checks[0]>4096:raise ValueError('累计输入检查超出候选条件预算')
        key=trace_key(trace)
        if key in seen:continue
        if len(selected)>=limit:raise ValueError('必需累计轨迹超出执行预算')
        plan=reference_trace(contract,trace)
        if not plan['eligible']:raise ValueError('必需累计轨迹不再满足初始条件或保留过滤')
        selected.append(deepcopy(trace));seen.add(key);covered.update(coverage(plan))
    regression=len(selected)
    def add(trace,channel):
        if checks[channel]>=4096:return
        checks[channel]+=1;key=trace_key(trace)
        if key in seen:return
        plan=reference_trace(contract,trace)
        if not plan['eligible']:return
        seen.add(key);new=coverage(plan)-covered
        if new:
            if len(selected)>=limit:raise ValueError('执行预算不足以覆盖必需操作或不变量')
            selected.append(deepcopy(trace));covered.update(new)
        elif len(fillers)<limit:fillers.append(deepcopy(trace))
    def enough():return wanted<=covered and len(selected)+len(fillers)>=limit
    def structured():
        for context_values in contexts:
            pools=_variant_pools(contract,_context(contract,context_values),rows)
            for initial in contract['initial_states']:
                for variant in range(max(len(p) for p in pools.values())):
                    for identity in ids:
                        step=pools[identity][variant%len(pools[identity])]
                        for depth in dict.fromkeys((2,contract['max_steps'])):
                            yield dict(initial_state=initial,context=context_values,steps=[deepcopy(step) for _ in range(depth)])
                    for left,right in itertools.product(ids,repeat=2):
                        pair=[pools[left][variant%len(pools[left])],pools[right][variant%len(pools[right])]]
                        yield dict(initial_state=initial,context=context_values,steps=deepcopy(pair))
                        if contract['max_steps']>2:
                            yield dict(initial_state=initial,context=context_values,steps=[deepcopy(pair[i%2]) for i in range(contract['max_steps'])])
    if not enough():
        for trace in structured():
            if checks[0]>=4096:break
            add(trace,0)
            if enough():break
    rng=random.Random(contract['seed'])
    if not enough():
        for _ in range(4096):
            values=rng.choice(contexts);pools=_variant_pools(contract,_context(contract,values),rows)
            steps=[deepcopy(rng.choice(pools[rng.choice(ids)])) for _ in range(rng.randint(2,contract['max_steps']))]
            add(dict(initial_state=rng.choice(contract['initial_states']),context=list(values),steps=steps),1)
            if enough():break
    if not selected or not wanted<=covered:raise ValueError('有限序列采样没有覆盖全部操作或不变量，请调整模型域或条件')
    selected.extend(fillers[:limit-len(selected)])
    return dict(traces=selected,candidate_checks=sum(checks),regression_traces=regression)


def _target(contract,plan,failure_id):
    if failure_id.startswith('MODEL-'):
        identity=failure_id[len('MODEL-'):]
        if identity not in {op['id'] for op in contract['operations']}:raise ValueError('未知转移失败ID')
        return any(s['operation_id']==identity for s in plan['steps'])
    if failure_id not in {p['id'] for p in contract['invariants']}:raise ValueError('未知不变量失败ID')
    return any(failure_id in s['applicable'] for s in plan['steps'])


def shrink_traces(contract,trace,failure_id,axes=None):
    if type(failure_id) is not str:raise ValueError('失败ID必须为字符串')
    original=reference_trace(contract,trace)
    if not original['eligible'] or not _target(contract,original,failure_id):raise ValueError('原始轨迹不适用于缩减目标')
    original_score=trace_score(trace);items=[];seen=set();axis=oracle.checked_axes(sampler(contract),axes)
    def add(candidate):
        if not candidate['steps']:return
        key=trace_key(candidate)
        if key in seen or trace_score(candidate)>=original_score:return
        plan=reference_trace(contract,candidate)
        if plan['eligible'] and _target(contract,plan,failure_id):seen.add(key);items.append(candidate)
    length=len(trace['steps'])
    for start in range(length):
        for end in range(start+1,length+1):
            candidate=deepcopy(trace);candidate['steps']=candidate['steps'][:start]+candidate['steps'][end:];add(candidate)
    for initial in contract['initial_states']:
        candidate=deepcopy(trace);candidate['initial_state']=initial;add(candidate)
    for slot,index in enumerate(contract['context_indices']):
        for value in axis[index]:
            candidate=deepcopy(trace);candidate['context'][slot]=value
            nonstate=contract['nonstate_indices'].index(index)
            for step in candidate['steps']:step['args'][nonstate]=value
            add(candidate)
    for step_index,step in enumerate(trace['steps']):
        op=_operation(contract,step['operation_id'])
        for slot,(index,template) in enumerate(zip(contract['nonstate_indices'],op['args'])):
            if type(template) is not dict or 'domain' not in template:continue
            values=list(axis[index]);value=step['args'][slot]
            if type(value) is int:values.extend([value//2,value-1,value+1])
            for smaller in values:
                if type(smaller) is int and not oracle.LOW<=smaller<=oracle.HIGH:continue
                if not _within(contract,index,smaller):continue
                candidate=deepcopy(trace);candidate['steps'][step_index]['args'][slot]=smaller;add(candidate)
    return deepcopy(sorted(items,key=trace_score)[:8])


def validate_contract(value,signature,examples):
    if type(value) is not dict or set(value)!=FIELDS:raise ValueError('序列契约字段无效')
    try:encoded=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
    except (ValueError,TypeError,RecursionError):raise ValueError('序列契约不是有效JSON数据') from None
    if len(encoded)>16384:raise ValueError('序列JSON最多16KiB')
    if type(value['version']) is not int or value['version']!=properties.version(signature) or value['kind']!='sequence' or value['function']!=signature['name']:raise ValueError('序列版本、类型或函数无效')
    signature=oracle.stable_signature(signature);params=signature['params'];kind=signature['return_type'];kinds=object_values.LEAVES|set(signature.get('types',{}))
    if (not 1<=len(params)<=4 or kind not in kinds or any(p['type'] not in kinds for p in params) or
            type(value['state_param']) is not str or value['state_param'] not in [p['name'] for p in params]):raise ValueError('需要1至4参数及显式原始类型状态')
    state_index=[p['name'] for p in params].index(value['state_param'])
    if params[state_index]['type']!=kind:raise ValueError('函数返回类型必须与状态参数相同')
    if type(value['seed']) is not int or not 0<=value['seed']<2**32 or type(value['max_sequences']) is not int or not 8<=value['max_sequences']<=16 or type(value['max_steps']) is not int or not 2<=value['max_steps']<=8:
        raise ValueError('序列seed或调用预算无效')
    domains=oracle.normalize_domains(value['domains'],params,signature.get('types'));context=value['context_params']
    if type(context) is not list or len(context)>3 or any(type(n) is not str for n in context) or len(set(context))!=len(context) or any(n not in [p['name'] for i,p in enumerate(params) if i!=state_index] for n in context):raise ValueError('序列上下文参数无效')
    context_indices=[i for i,p in enumerate(params) if p['name'] in context];nonstate=[i for i in range(len(params)) if i!=state_index]
    result={k:deepcopy(v) for k,v in value.items()};result.update(domains=domains,signature=oracle.stable_signature(signature),state_index=state_index,context_indices=context_indices,nonstate_indices=nonstate,
        context_params=[params[i]['name'] for i in context_indices],algorithm='state-sequences-packages-v5' if value['version']==5 else 'state-sequences-object-v4' if value['version']==4 else 'state-sequences-array-v3' if value['version']==3 else 'state-sequences-string-v2' if value['version']==2 else ALGORITHM,
        aliases={**{f'arg{i}':p['name'] for i,p in enumerate(params)},**{f'ctx{i}':params[i]['name'] for i in context_indices},'state':value['state_param']})
    initials=value['initial_states']
    if type(initials) is not list or not 1<=len(initials)<=16 or any(not _within(result,state_index,v) for v in initials) or len({oracle.input_key([v]) for v in initials})!=len(initials):raise ValueError('初始状态限1至16个域内不重复原始值')
    _tree(value['initial_precondition'],{'initial_state':kind,**{f'ctx{i}':params[i]['type'] for i in context_indices}},'Bool',**properties.model_options(result))
    operations=value['operations']
    if type(operations) is not list or not 1<=len(operations)<=4:raise ValueError('序列操作限1至4项')
    seen=set()
    for op in operations:
        if type(op) is not dict or set(op)!={'id','text','args','transition'}:raise ValueError('操作字段无效')
        if type(op['id']) is not str or not re.fullmatch(r'OP-[A-Z][A-Z0-9-]{0,31}',op['id']) or op['id'] in seen:raise ValueError('操作ID无效或重复')
        if type(op['text']) is not str or not 1<=len(op['text'])<=500 or type(op['args']) is not list or len(op['args'])!=len(nonstate):raise ValueError('操作说明或参数无效')
        for index,template in zip(nonstate,op['args']):
            if index in context_indices:
                if type(template) is not dict or template!={'context':params[index]['name']}:raise ValueError('上下文槽必须使用同名context引用')
            elif type(template) is dict and '$type' not in template:
                if template!={'domain':params[index]['name']}:raise ValueError('采样槽必须使用同名domain引用')
            elif not _within(result,index,template):raise ValueError('操作常量超出模型域')
        _tree(op['transition'],{**_names(result),'state':kind},kind,**properties.model_options(result));seen.add(op['id'])
    invariants=value['invariants']
    if type(invariants) is not list or not 1<=len(invariants)<=8:raise ValueError('序列不变量限1至8项')
    seen=set()
    for inv in invariants:
        if type(inv) is not dict or set(inv)!={'id','text','precondition','assertion'}:raise ValueError('不变量字段无效')
        if type(inv['id']) is not str or not re.fullmatch(r'INV-[A-Z][A-Z0-9-]{0,31}',inv['id']) or inv['id'] in seen:raise ValueError('不变量ID无效或重复')
        if type(inv['text']) is not str or not 1<=len(inv['text'])<=500:raise ValueError('不变量说明限1至500字符')
        _tree(inv['precondition'],_invariant_names(result),'Bool',**properties.model_options(result));_tree(inv['assertion'],{**_invariant_names(result),'result':kind,'expected_state':kind},'Bool',**properties.model_options(result));seen.add(inv['id'])
    excluded=value['excluded_inputs']
    if type(excluded) is not list or len(excluded)>128:raise ValueError('序列保留输入最多128项')
    keys=set()
    for args in excluded:
        if type(args) is not list or len(args)!=len(params):raise ValueError('保留输入参数数目无效')
        for p,v in zip(params,args):_primitive(v,p['type'],signature.get('types'))
        key=oracle.input_key(args)
        if key in keys:raise ValueError('序列保留输入重复')
        keys.add(key)
    for example in examples:
        args=example['args']
        if type(args) is not list or len(args)!=len(params):raise ValueError('公开例子参数无效')
        _primitive(example['expected'],kind,signature.get('types'))
        within=[_within(result,i,v) for i,v in enumerate(args)]
        if not oracle.permitted_input(result,args):raise ValueError('公开例子不能列为保留输入')
        if not all(within):continue
        contexts={i:args[i] for i in context_indices}
        for op in result['operations']:
            concrete=[args[i] for i in nonstate]
            try:_arguments(result,op,args[state_index],concrete,contexts)
            except ValueError:continue
            env={f'arg{i}':v for i,v in enumerate(args)};env['state']=args[state_index]
            expected=_primitive(oracle.evaluate(_tree(op['transition'],{**_names(result),'state':kind},kind,**properties.model_options(result)),env,**properties.model_options(result)),kind,signature.get('types'))
            if not _same(expected,example['expected']):raise ValueError('状态转移与已确认公开示例冲突')
    generate_traces(result)
    return result
