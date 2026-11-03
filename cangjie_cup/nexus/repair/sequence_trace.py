"""One genuine SDK case per trajectory, one typed observation per real step."""
from copy import deepcopy
import re

from nexus.adapters.cangjie.report_parser import ANSI,parse_test_report
from nexus.contracts import digest
from nexus.repair import oracle,sequences,string_trace,array_trace,object_trace,scoped_values
from nexus.repair.primitive_trace import CASE,OBSERVATION_PREFIXES,SUITE_HEADER
from nexus.uploads.language import literal

PREFIX='NEXUS_SEQUENCE_V1|'
END='NEXUS_SEQUENCE_END_V1|'


def _class(signature,token,version=1):
    if type(version) is not int or version not in (1,2,3,4,5):raise ValueError('序列观测版本无效')
    if version==5:
        from nexus.repair import scoped_trace
        return scoped_trace.case_ids(signature,1,token,'sequence')[0].rsplit('.',2)[1]
    if 'scope' in signature:raise ValueError('Scoped序列不能使用旧观测协议')
    if type(token) is not str or not re.fullmatch(r'[0-9a-f]{16}',token):raise ValueError('序列观测token无效')
    name=signature.get('name')
    if type(name) is not str or not re.fullmatch(r'[A-Za-z_]\w*',name):raise ValueError('序列目标函数名无效')
    cls=('NexusSequencesV4' if version==4 else 'NexusSequencesV3' if version==3 else 'NexusSequencesV2' if version==2 else 'NexusSequences')+token
    if version==4:
        while cls in object_trace.reserved_names(signature):cls+='Value'
    return cls+'Value' if cls==name else cls


def _traces(contract,traces):
    if type(traces) is not list or not 1<=len(traces)<=16:raise ValueError('序列观测限1至16轨迹')
    plans=[];seen=set()
    for trace in traces:
        key=sequences.trace_key(trace)
        if key in seen:raise ValueError('观测轨迹不得重复')
        plan=sequences.reference_trace(contract,trace)
        if not plan['eligible']:raise ValueError('轨迹不满足初始前提或命中保留输入')
        seen.add(key);plans.append(plan)
    if sum(len(p['steps']) for p in plans)>128:raise ValueError('序列计划调用超过128项')
    return plans


def harness(contract,traces,package,token,*,binding=None):
    version=contract['version']
    signature=contract['signature'];cls=_class(signature,token,version);plans=_traces(contract,traces)
    if version==5:
        from nexus.repair import scoped_trace
        if type(binding) is not dict or binding.get('package')!=package:raise ValueError('V5序列需要来源绑定的验证包')
        return scoped_trace.render(signature,traces,nonce=token,mode='sequence',binding=binding,contract=contract)['source']
    if binding is not None:raise ValueError('旧序列不接受Scoped来源绑定')
    if version>=2:return _harness_v2(contract,traces,package,token,cls,plans,version=version)
    if type(package) is not str or not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*',package):raise ValueError('观测包名无效')
    name=signature['name'];kind=signature['return_type'];output='__nexusSeqPrint'+token;target='__nexusSeqTarget'+token
    while output==name:output+='Value'
    while target==name or target==output:target+='Value'
    text='package '+package+'\nimport std.core.println as '+output+'\nimport std.unittest.*\nimport std.unittest.testmacro.*\n@Test\nclass '+cls+' {\n'
    for case,(trace,plan) in enumerate(zip(traces,plans)):
        text+='@TestCase\nfunc case'+str(case)+'() {\n'
        text+='let '+target+': ('+', '.join(p['type'] for p in signature['params'])+') -> '+kind+' = '+name+'\n'
        previous=literal(trace['initial_state'],signature.get('types') if version==4 else None)
        for index,step in enumerate(plan['steps']):
            before='__nexusSeqBefore'+str(index);after='__nexusSeqAfter'+str(index)
            text+='let '+before+': '+kind+' = '+previous+'\n'
            args=[before if i==contract['state_index'] else literal(value,signature.get('types') if version==4 else None) for i,value in enumerate(step['args'])]
            text+='let '+after+' = '+target+'('+', '.join(args)+')\n'
            text+=output+'("'+PREFIX+token+'|case'+str(case)+'|step'+str(index)+'|'+kind+'|${'+before+'}|${'+after+'}")\n'
            text+='if ('+after+' != '+literal(step['expected_state'])+') {\n'+output+'("'+END+token+'|case'+str(case)+'|'+str(index+1)+'|MODEL_MISMATCH")\nreturn\n}\n'
            previous=after
        text+=output+'("'+END+token+'|case'+str(case)+'|'+str(len(plan['steps']))+'|COMPLETE")\n}\n'
    return (text+'}\n').encode()


def _value(text,kind,version=1,types=None):
    if version==5:return scoped_values.decode(text,kind,types or {})
    if version==4:return object_trace.decode(text,kind,types)
    return (array_trace if version==3 else string_trace).decode(text,kind)


def interpret(contract,traces,token,log,exit_code,problem,*,require_coverage=True):
    if type(require_coverage) is not bool:raise ValueError('覆盖检查标记必须为Bool')
    version=contract['version']
    codec=scoped_values if version==5 else object_trace if version==4 else array_trace if version==3 else string_trace
    prefix,end_prefix=(codec.SEQUENCE,codec.END) if version>=2 else (PREFIX,END)
    plans=_traces(contract,traces);cls=_class(contract['signature'],token,version);kind=contract['signature']['return_type']
    planned_calls=sum(len(p['steps']) for p in plans)
    if version==5:
        from nexus.repair import scoped_trace
        expected=scoped_trace.case_ids(contract['signature'],len(traces),token,'sequence')
        checked=scoped_trace.execution(log,contract['signature'],expected,nonce=token,mode='sequence',exit_code=exit_code,problem=problem)
        execution_state=checked['execution_state'];counts=checked['counts'];invalid=checked['state']!='PASS'
        clean=checked.get('clean','');detail=checked.get('detail','')
    else:
        expected=[cls+'.case'+str(i) for i in range(len(traces))];parsed=parse_test_report(log)
        execution_state=parsed.state;counts=parsed.counts
        invalid=(problem is not None or exit_code!=0 or parsed.state!='PASS' or set(parsed.case_results)!=set(expected) or any(state!='PASS' for state in parsed.case_results.values()))
        clean=ANSI.sub('',log);detail=clean.split('Summary:',1)[0]
    unknown=dict(state='UNKNOWN',execution_state=execution_state,counts=counts,planned_calls=planned_calls,observed_calls=0,unexecuted_calls=None,
        observations=[],failures=[],per_operation=[],per_invariant=[],reason='逐步SDK观测不完整或绑定无效')
    if invalid:return unknown
    suite=None;case=None;stdout=False;offset=0
    if any(line.strip().startswith(OBSERVATION_PREFIXES) for line in clean[len(detail):].splitlines()):return unknown
    values={identity:[] for identity in expected};endings={}
    try:
        for line in detail.splitlines(keepends=True):
            stripped=line.strip();reserved=stripped.startswith(OBSERVATION_PREFIXES)
            header=None if reserved else SUITE_HEADER.fullmatch(line.rstrip('\r\n'))
            match=None if reserved else CASE.fullmatch(line.rstrip('\r\n'))
            if header:suite=(checked['package']+'.' if version==5 else '')+header.group(1);case=None;stdout=False
            elif match:case=suite+'.'+match.group(2) if suite else None;stdout=False
            elif stripped in ('STDOUT:','STDERR:'):stdout=stripped=='STDOUT:'
            elif stripped.startswith(OBSERVATION_PREFIXES):
                if not stdout or case not in values:raise ValueError('观测不属于对应SDK stdout')
                fields=(line.lstrip().rstrip(chr(13)+chr(10)) if version>=2 else stripped).split('|');case_index=expected.index(case);plan=plans[case_index];observed=values[case]
                source=dict(coordinate='ANSI_STRIPPED_FULL_LOG',start_char=offset,end_char=offset+len(line.rstrip('\r\n')))
                if stripped.startswith(prefix):
                    index=len(observed)
                    if (case in endings or len(fields)!=7 or fields[1]!=token or fields[2]!=(case if version==5 else case.split('.')[-1]) or fields[3]!='step'+str(index) or fields[4]!=kind or index>=len(plan['steps'])):
                        raise ValueError('步骤、nonce、case或原始类型不符')
                    before=_value(fields[5],kind,version,contract['signature'].get('types'));actual=_value(fields[6],kind,version,contract['signature'].get('types'))
                    wanted_before=traces[case_index]['initial_state'] if not observed else observed[-1]['actual_return']
                    if type(before) is not type(wanted_before) or before!=wanted_before:raise ValueError('前态不是前一步真实返回')
                    if observed and observed[-1]['actual_return']!=plan['steps'][index-1]['expected_state']:raise ValueError('首次模型偏离后仍继续调用')
                    observed.append(dict(actual_return=actual,before_state=before,source=source))
                elif stripped.startswith(end_prefix):
                    if (case in endings or len(fields)!=5 or fields[1]!=token or fields[2]!=(case if version==5 else case.split('.')[-1]) or
                            not re.fullmatch(r'[1-9][0-9]*',fields[3]) or int(fields[3])!=len(observed) or fields[4] not in ('COMPLETE','MODEL_MISMATCH')):
                        raise ValueError('结束标记重复、缺失或计数无效')
                    mismatches=[i for i,item in enumerate(observed) if item['actual_return']!=plan['steps'][i]['expected_state']]
                    if fields[4]=='COMPLETE':
                        if len(observed)!=len(plan['steps']) or mismatches:raise ValueError('未完成或偏离模型不能标完整')
                    elif not observed or mismatches!=[len(observed)-1]:raise ValueError('结束点不是首次模型偏离')
                    endings[case]=dict(mode=fields[4],source=source)
                else:raise ValueError('混入其它观测协议')
            offset+=len(line)
        if set(endings)!=set(expected):raise ValueError('缺少结束标记')
        operations={op['id']:dict(id=op['id'],planned=0,observed=0,model_mismatches=0) for op in contract['operations']}
        invariants={inv['id']:dict(id=inv['id'],planned_applicable=0,observed=0,violations=0) for inv in contract['invariants']}
        observations=[];failures=[]
        for index,(trace,plan,identity) in enumerate(zip(traces,plans,expected)):
            sequence_id='SEQUENCE-'+digest(dict(token=token,index=index,trace=trace))[:16]
            for step in plan['steps']:
                operations[step['operation_id']]['planned']+=1
                for inv in step['applicable']:invariants[inv]['planned_applicable']+=1
            steps=[];violations=[]
            for reference,actual in zip(plan['steps'],values[identity]):
                evaluated=sequences.evaluate_step(contract,reference,actual['actual_return'])
                step={**deepcopy(reference),**deepcopy(actual),**dict(test_id=identity,sequence_id=sequence_id,violations=deepcopy(evaluated['failures']))}
                steps.append(step);operations[step['operation_id']]['observed']+=1
                if actual['actual_return']!=reference['expected_state']:operations[step['operation_id']]['model_mismatches']+=1
                for inv in evaluated['applicable']:invariants[inv]['observed']+=1
                for failure in evaluated['failures']:
                    if failure['failure_id'] in invariants:invariants[failure['failure_id']]['violations']+=1
                violations.extend(evaluated['failures'])
            path=dict(sequence_id=sequence_id,test_id=identity,initial_state=deepcopy(trace['initial_state']),context=deepcopy(trace['context']),steps=steps,
                planned_steps=len(plan['steps']),observed_steps=len(steps),unexecuted_steps=len(plan['steps'])-len(steps),stop_reason=endings[identity]['mode'],end_source=endings[identity]['source'])
            observations.append(path)
            if violations:
                final=steps[-1]
                failures.append({**deepcopy(path),**dict(kind='business_sequence',step_index=final['step_index'],operation_id=final['operation_id'],operation_text=final['operation_text'],
                    before_state=deepcopy(final['before_state']),actual_return=deepcopy(final['actual_return']),expected_state=deepcopy(final['expected_state']),model_mismatch=final['actual_return']!=final['expected_state'],
                    failure_ids=[v['failure_id'] for v in violations],violations=deepcopy(violations),source=deepcopy(final['source']))})
        if not failures and require_coverage and (not all(op['observed'] for op in operations.values()) or not all(inv['observed'] for inv in invariants.values())):
            return {**unknown,'reason':'存在没有完整实际观测的操作或不变量'}
        observed_calls=sum(len(path['steps']) for path in observations)
        return dict(state='FAIL' if failures else 'PASS',execution_state='PASS',counts=counts,planned_calls=planned_calls,observed_calls=observed_calls,unexecuted_calls=planned_calls-observed_calls,
            observations=observations,failures=failures,per_operation=list(operations.values()),per_invariant=list(invariants.values()),reason='')
    except (ValueError,KeyError,TypeError,IndexError):return unknown


def _harness_v2(contract,traces,package,token,cls,plans,version=2):
    codec=string_trace if version==2 else array_trace if version==3 else object_trace
    signature=contract['signature'];kind=signature['return_type'];parts=codec.header(signature,package,token,cls,sequence=True)
    output,target,encoder=(parts[k] for k in ('output','target','encoder'));text=parts['source'];nl=chr(10)
    for case,(trace,plan) in enumerate(zip(traces,plans)):
        text+='@TestCase'+nl+'func case'+str(case)+'() {'+nl;previous=object_trace.input_literal(trace['initial_state'],signature['types'],parts['constructors']) if version==4 else literal(trace['initial_state'])
        for index,step in enumerate(plan['steps']):
            before='__nexusSeqBefore'+str(index);after='__nexusSeqAfter'+str(index)
            if version==4:
                before=string_trace._fresh(before,parts['reserved']);after=string_trace._fresh(after,parts['reserved'])
            text+='let '+before+': '+kind+' = '+previous+nl
            args=[before if i==contract['state_index'] else object_trace.input_literal(value,signature['types'],parts['constructors']) if version==4 else literal(value) for i,value in enumerate(step['args'])]
            text+='let '+after+' = '+target+'('+', '.join(args)+')'+nl
            text+=codec.limit_guard(kind,after,output,token,case,signature['types']) if version==4 else codec.limit_guard(kind,after,output,token,case)
            text+=output+'("'+codec.SEQUENCE+token+'|case'+str(case)+'|step'+str(index)+'|'+kind+'|${'+codec.wire(kind,before,encoder)+'}|${'+codec.wire(kind,after,encoder)+'}")'+nl
            comparison=(codec.wire(kind,after,encoder)+' != "'+codec.encode(step['expected_state'],kind,signature['types'])+'"') if version==4 and kind in signature['types'] else after+' != '+literal(step['expected_state'])
            text+='if ('+comparison+') {'+nl+output+'("'+codec.END+token+'|case'+str(case)+'|'+str(index+1)+'|MODEL_MISMATCH")'+nl+'return'+nl+'}'+nl
            previous=after
        text+=output+'("'+codec.END+token+'|case'+str(case)+'|'+str(len(plan['steps']))+'|COMPLETE")'+nl+'}'+nl
    return (text+'}'+nl).encode()
