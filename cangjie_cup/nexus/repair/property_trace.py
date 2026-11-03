"""Single-call business predicates over shared pinned SDK observations."""
from nexus.repair import oracle,properties,primitive_trace

PREFIX,CLS=primitive_trace.protocol('single')
CASE=primitive_trace.CASE


def case_ids(token,count,version=1,signature=None):
    return primitive_trace.case_ids(token,count,'single',version,signature)


def _cases(contract,cases):
    if type(cases) is not list or not 1<=len(cases)<=128:raise ValueError('属性观测输入限1至128项')
    seen=set()
    for args in cases:
        if not properties.applicable(contract,args):raise ValueError('不能执行无适用属性的输入')
        key=oracle.input_key(args)
        if key in seen:raise ValueError('属性观测输入重复')
        seen.add(key)


def harness(contract,cases,package,token,*,binding=None):
    _cases(contract,cases)
    options={} if binding is None else {'binding':binding}
    return primitive_trace.harness(contract['signature'],cases,package,token,'single',version=contract['version'],**options)


def interpret(contract,cases,token,log,exit_code,problem,*,required_ids=None):
    _cases(contract,cases)
    ids=[p['id'] for p in contract['properties']]
    required=ids if required_ids is None else required_ids
    if type(required) is not list or not required or any(type(i) is not str or i not in ids for i in required) or len(set(required))!=len(required):raise ValueError('属性观测覆盖范围无效')
    observed=primitive_trace.read(contract['signature'],cases,token,'single',log,exit_code,problem,version=contract['version'])
    unknown=dict(state='UNKNOWN',execution_state=observed['execution_state'],counts=observed['counts'],observations=[],failures=[],per_property=[],reason='属性观测不完整或执行未成功')
    if observed['state']!='PASS':return unknown
    observations=[];failures=[];totals={p['id']:dict(id=p['id'],generated=len(cases),applicable=0,observed=0,failed=0) for p in contract['properties']}
    try:
        for item in observed['observations']:
            evaluation=properties.evaluate_result(contract,item['args'],item['actual_return'])
            for prop in evaluation['applicable']:totals[prop]['applicable']+=1;totals[prop]['observed']+=1
            observations.append(dict(test_id=item['test_id'],args=item['args'],actual_return=item['actual_return'],applicable=evaluation['applicable']))
            if contract['version']>=2:observations[-1]['source']=dict(item['source'])
            for failure in evaluation['failures']:
                totals[failure['property_id']]['failed']+=1
                failures.append({**failure,'test_id':item['test_id'],'source':dict(item['source'])})
    except ValueError:return {**unknown,'reason':'属性解释失败或实际返回类型无效'}
    if not all(totals[i]['observed']>0 for i in required):return {**unknown,'reason':'存在无实际适用观测的属性'}
    return dict(state='FAIL' if failures else 'PASS',execution_state='PASS',counts=observed['counts'],
                observations=observations,failures=failures,per_property=list(totals.values()),reason='')
