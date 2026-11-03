"""Pairs are interpreted only after both independent SDK cases complete."""
from nexus.contracts import digest
from nexus.repair import relations,primitive_trace


def _pairs(contract,pairs):
    if type(pairs) is not list or not 1<=len(pairs)<=64:raise ValueError('关系观测输入限1至64对')
    seen=set()
    for pair in pairs:
        if not relations.applicable(contract,pair):raise ValueError('不能执行无适用关系的输入对')
        key=relations.pair_key(pair)
        if key in seen:raise ValueError('关系观测输入对重复')
        seen.add(key)


def flatten(pairs):return [pair[side] for pair in pairs for side in ('left','right')]


def harness(contract,pairs,package,token,*,binding=None):
    _pairs(contract,pairs)
    options={} if binding is None else {'binding':binding}
    return primitive_trace.harness(contract['signature'],flatten(pairs),package,token,'relation',version=contract['version'],**options)


def interpret(contract,pairs,token,log,exit_code,problem,*,required_ids=None):
    _pairs(contract,pairs);ids=[r['id'] for r in contract['relations']]
    required=ids if required_ids is None else required_ids
    if type(required) is not list or not required or any(type(i) is not str or i not in ids for i in required) or len(set(required))!=len(required):raise ValueError('关系观测覆盖范围无效')
    observed=primitive_trace.read(contract['signature'],flatten(pairs),token,'relation',log,exit_code,problem,version=contract['version'])
    unknown=dict(state='UNKNOWN',execution_state=observed['execution_state'],counts=observed['counts'],observations=[],failures=[],per_relation=[],reason='双侧观测不完整或执行未成功')
    if observed['state']!='PASS':return unknown
    observations=[];failures=[];totals={r['id']:dict(id=r['id'],generated=len(pairs),applicable=0,observed=0,failed=0) for r in contract['relations']}
    try:
        for i,pair in enumerate(pairs):
            left,right=observed['observations'][2*i:2*i+2]
            evaluated=relations.evaluate_pair(contract,pair,left['actual_return'],right['actual_return'])
            identity='PAIR-'+digest(dict(token=token,index=i,pair=pair))[:16]
            for relation in evaluated['applicable']:totals[relation]['applicable']+=1;totals[relation]['observed']+=1
            observations.append(dict(pair_id=identity,left=left,right=right,applicable=evaluated['applicable']))
            for failure in evaluated['failures']:
                totals[failure['relation_id']]['failed']+=1
                failures.append({**failure,'pair_id':identity,'left_test_id':left['test_id'],'right_test_id':right['test_id'],
                    'left_source':dict(left['source']),'right_source':dict(right['source'])})
    except ValueError:return {**unknown,'reason':'关系解释失败或双侧实际返回类型无效'}
    if not all(totals[i]['observed']>0 for i in required):return {**unknown,'reason':'存在无实际适用双侧观测的关系'}
    return dict(state='FAIL' if failures else 'PASS',execution_state='PASS',counts=observed['counts'],
        observations=observations,failures=failures,per_relation=list(totals.values()),reason='')
