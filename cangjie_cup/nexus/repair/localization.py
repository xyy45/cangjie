"""Deterministic, version-labelled repair focus; static evidence is a hypothesis.

The caller supplies verified cases/logs and reconstructed analysis originals.
This layer never infers expected business values from a log expression or model.
"""
from copy import deepcopy

from nexus.analysis.point import point_slice
from nexus.contracts import file_hash,digest
import json
from nexus.uploads.language import Parser,literal
from nexus.repair import values

ALGORITHM='confirmed-case-baseline-pdg-v1'
LIMITATIONS=['位置和切片使用冻结基线坐标，失败值属于单独标明的候选版本',
    '静态返回语句与调用关系仅作为定位假设，不证明动态执行路径或缺陷根因',
    '跨文件调用线索来自本地受限源码索引，MCP依赖切片保持逐文件范围']


def literal_call(text):
    """Read a compiler-rendered bare literal call, never evaluate expressions."""
    if not isinstance(text,str) or len(text)>4096:raise ValueError('定位调用表达式无效')
    try:
        parser=Parser(text);name=parser.name();parser.take('(');args=[]
        def read_literal():
            if parser.accept('['):
                items=[]
                if parser.peek()!=']':
                    while True:
                        if parser.peek()=='[':raise ValueError('定位不支持嵌套数组')
                        item=read_literal();values.primitive(item,'Int64');items.append(item)
                        if len(items)>16:raise ValueError('定位数组最多16项')
                        if not parser.accept(','):break
                parser.take(']');return values.array(items)
            negative=parser.accept('-');value=parser.take()
            if value.startswith(chr(34)) and not negative:return values.decode_string_literal(value)
            if value in ('true','false') and not negative:return value=='true'
            if value.isascii() and value.isdigit() and len(value)<=19:return values.primitive(int(value)*(-1 if negative else 1),'Int64')
            raise ValueError('定位调用只接受字面量')
        if parser.peek()!=')':
            while True:
                args.append(read_literal())
                if len(args)>4:raise ValueError('定位参数过多')
                if not parser.accept(','):break
        parser.take(')');parser.take('<eof>')
        return name,args
    except (RecursionError,IndexError) as exc:raise ValueError('定位调用语法无效') from exc


def same_args(left,right):
    if type(left) is not list or type(right) is not list or len(left)!=len(right):return False
    try:return all(values.typed_key(a)==values.typed_key(b) for a,b in zip(left,right))
    except ValueError:return False


def valid_value(value):
    try:values.typed_key(value);return True
    except ValueError:return False


def source_index(source_files,*,scoped_index=None):
    if scoped_index is not None:
        if scoped_index.get('version')!=2 or set(source_files)!=set(scoped_index['production_paths']):
            raise ValueError('Scoped定位源码范围与冻结索引不一致')
        for path,item in source_files.items():
            if file_hash(item['content'])!=item['file_hash'] or item['file_hash']!=scoped_index['manifest'][path]:
                raise ValueError('Scoped定位源码摘要变化')
        functions={}
        for function in [*scoped_index['functions'],*scoped_index.get('methods',[])]:
            name=function['name'];path=function['path']
            if name in functions or path not in source_files:raise ValueError('Scoped定位规范符号重复或来源不符')
            functions[name]={**deepcopy(function),'types':deepcopy(scoped_index.get('types',{})),
                'source_sha256':source_files[path]['file_hash']}
        return functions,{}
    from nexus.uploads.object_types import collect
    from nexus.repair.object_values import registry
    functions={};unavailable={};ambiguous=set();types={};eligible={};declared={}
    for path,item in sorted(source_files.items()):
        source=item['content']
        if file_hash(source)!=item['file_hash']:raise ValueError('定位源码摘要变化')
        try:header=collect(source,validate=False)
        except ValueError as exc:unavailable[path]=str(exc);continue
        if set(types)&set(header['types']):raise ValueError('定位对象声明重复')
        types.update(header['types']);eligible[path]=item
    types=registry(types)
    for path,item in eligible.items():
        try:headers=Parser(item['content'],types=types if types else None).program(headers_only=True)
        except ValueError as exc:unavailable[path]=str(exc);continue
        for f in headers['functions']:
            if f['name'] in declared:ambiguous.add(f['name'])
            declared[f['name']]=f
    for name in ambiguous:del declared[name]
    for path,item in eligible.items():
        if path in unavailable:continue
        try:
            parser=Parser(item['content'],types=types if types else None);parser.declared=declared
            headers=parser.program(headers_only=not bool(types))
        except ValueError as exc:unavailable[path]=str(exc);continue
        for f in headers['functions']+headers.get('methods',[]):
            if f['name'] in ambiguous:continue
            if f['name'] in functions:ambiguous.add(f['name']);continue
            functions[f['name']]={**f,'path':path,'source_sha256':item['file_hash']}
    for name in ambiguous:functions.pop(name,None)
    return functions,unavailable


def public_field_matches(case,failure,function):
    from nexus.repair.object_values import registry
    path=case.get('field_path');kind=case.get('value_type')
    if (type(path) is not list or digest(path)!=digest(failure.get('field_path')) or kind!=failure.get('value_type') or
            case.get('call_id')!=failure.get('call_id')):return False
    if function is not None:
        types=registry(function.get('types',{}));returned=function['return_type']
        if returned in types:
            if not 1<=len(path)<=2:return False
            field=next((f for f in types[returned]['fields'] if f['name']==path[0]),None)
            if field is None:return False
            actual_kind=field['type']
            if len(path)==2:
                if actual_kind!='Array<Int64>' or not (path[1]=='$size' or type(path[1]) is int and 0<=path[1]<16):return False
                actual_kind='Int64'
        else:
            if path:return False
            actual_kind=returned
        if kind!=actual_kind:return False
    expected=values.primitive(case.get('expected_value'),kind)
    if values.typed_key(expected)!=values.typed_key(failure.get('expected_value')):return False
    if failure.get('value_state')=='TYPED':values.primitive(failure.get('actual_value'),kind)
    elif not (failure.get('value_state')=='TEXT_ONLY' and kind=='String' and failure.get('actual_value') is None):return False
    return failure.get('expected')==json.dumps(expected,ensure_ascii=False,separators=(',',':'))


def relation_calls(failures,function):
    """Project a verified pair into two genuine calls, preserving the group."""
    cases=[];calls=[]
    for failure in failures:
        for side in ('left','right'):
            source=deepcopy(failure[side+'_source']);args=deepcopy(failure[side+'_args']);test_id=failure[side+'_test_id']
            refs=list(failure.get('requirement_refs',['REQ-UPLOAD']))
            cases.append(dict(test_id=test_id,log_ref=source['log_ref'],function=function,args=args,requirement_refs=refs))
            calls.append(dict(kind='business_relation_call',test_id=test_id,source=source,args=args,
                actual_return=failure[side+'_actual_return'],relation_role=side,pair_id=failure['pair_id'],
                relation_id=failure['relation_id'],relation_text=failure['relation_text'],
                assertion_value=failure['assertion_value'],expected_relation=failure['expected_relation']))
    return cases,calls


def sequence_calls(failures,function):
    """Prioritize each failed step; preserve SDK case IDs and separate call IDs."""
    cases={};calls={};failed=[];ancestors=[]
    for failure in failures:
        for step in failure['steps']:
            call_id=failure['sequence_id']+'.step'+str(step['step_index']);source=deepcopy(step['source'])
            key=(step['test_id'],source['log_ref'],call_id);is_failure=step['step_index']==failure['step_index']
            case=dict(test_id=step['test_id'],log_ref=source['log_ref'],call_id=call_id,function=function,args=deepcopy(step['args']),
                expected_state=step['expected_state'],requirement_refs=list(failure.get('requirement_refs',['REQ-UPLOAD'])))
            fact=dict(kind='business_sequence_call',test_id=step['test_id'],call_id=call_id,sequence_id=failure['sequence_id'],step_index=step['step_index'],
                sequence_role='failure' if is_failure else 'predecessor',source=source,args=deepcopy(step['args']),initial_state=failure['initial_state'],
                context=deepcopy(failure['context']),operation_id=step['operation_id'],operation_text=step['operation_text'],before_state=step['before_state'],
                actual_return=step['actual_return'],reference_before=step['reference_before'],expected_state=step['expected_state'],
                failure_ids=list(failure['failure_ids']) if is_failure else [])
            if key in cases:
                if digest(case)!=digest(cases[key]) or digest({k:v for k,v in fact.items() if k!='failure_ids'})!=digest({k:v for k,v in calls[key].items() if k!='failure_ids'}):raise ValueError('同一步骤观测映射不唯一')
                calls[key]['failure_ids']=list(dict.fromkeys(calls[key]['failure_ids']+fact['failure_ids']))
            else:
                cases[key]=case;calls[key]=fact;(failed if is_failure else ancestors).append(key)
    ordered=failed+ancestors
    return [cases[k] for k in ordered],[calls[k] for k in ordered]


def build_focus(source_files,confirmed_cases,failures,analysis_reports,binding,*,scoped_index=None):
    functions,unavailable=source_index(source_files,scoped_index=scoped_index)
    for path,report in analysis_reports.items():
        item=source_files.get(path);source=report.get('source',{})
        if not item or source.get('code')!=item['content'] or source.get('source_sha256')!=item['file_hash']:
            raise ValueError('定位图与源码版本不符')
    cases={}
    for c in confirmed_cases:
        key=(c['test_id'],c.get('log_ref'),c.get('call_id'))
        if key in cases and cases[key]!=c:raise ValueError('确认用例映射不唯一')
        cases[key]=c
    targets=[];truncated=len(failures)>8
    for failure in failures[:8]:
        case=cases.get((failure['test_id'],failure.get('source',{}).get('log_ref'),failure.get('call_id')),cases.get((failure['test_id'],None,failure.get('call_id'))))
        expression=failure.get('expression') or failure.get('input')
        public_field=failure.get('kind')=='public_field'
        if case:
            if expression is not None and not public_field:
                called,arguments=literal_call(expression)
                if called!=case['function'] or not same_args(arguments,case['args']):raise ValueError('失败日志调用与确认函数／输入不符')
            elif 'args' not in failure:case=None
        name=case['function'] if case else None
        target=dict(test_id=failure['test_id'],mapping='UNMAPPED',function=name,locations=[],
            actual=failure.get('actual'),expected=failure.get('expected'),args=deepcopy(case['args']) if case else None,
            args_text=json.dumps(case['args'],ensure_ascii=False) if case else None,
            requirement_refs=list(case.get('requirement_refs',[])) if case else [],failure_source=deepcopy(failure.get('source',{})))
        property_failure=failure.get('kind')=='business_property'
        relation_failure=failure.get('kind')=='business_relation_call'
        sequence_failure=failure.get('kind')=='business_sequence_call'
        string_oracle=failure.get('kind')=='independent_rule' and 'expected_value' in failure
        if public_field:
            target.update({k:deepcopy(failure.get(k)) for k in ('call_id','field_path','value_type','value_state','actual_value','expected_value','actual_text','public_test')})
        if string_oracle:
            target.update({k:deepcopy(failure.get(k)) for k in ('expected_value','actual_return')})
        if property_failure:
            target.update({k:deepcopy(failure.get(k)) for k in ('property_id','property_text','actual_return','assertion_value','expected_property')})
        if relation_failure:
            target.update({k:deepcopy(failure.get(k)) for k in ('pair_id','relation_role','relation_id','relation_text','actual_return','assertion_value','expected_relation')})
        if sequence_failure:
            target.update({k:deepcopy(failure.get(k)) for k in ('call_id','sequence_id','step_index','sequence_role','initial_state','context','operation_id','operation_text','before_state','actual_return','reference_before','expected_state','failure_ids')})
        if case:
            if public_field:
                expected_matches=public_field_matches(case,failure,functions.get(name))
            elif sequence_failure:
                expected_matches=('expected' not in case and 'expected' not in failure and
                    valid_value(failure.get('actual_return')) and type(failure.get('expected_state')) is type(failure.get('actual_return')) and
                    same_args([case.get('expected_state')],[failure.get('expected_state')]) and
                    failure.get('call_id')==case.get('call_id') and failure.get('sequence_role') in ('failure','predecessor'))
            elif relation_failure:
                expected_matches=('expected' not in case and 'expected' not in failure and
                    failure.get('assertion_value') is False and failure.get('expected_relation') is True and
                    valid_value(failure.get('actual_return')) and failure.get('relation_role') in ('left','right'))
            elif property_failure:
                expected_matches=('expected' not in case and 'expected' not in failure and
                    failure.get('assertion_value') is False and failure.get('expected_property') is True and
                    valid_value(failure.get('actual_return')) and case.get('property_id',failure.get('property_id'))==failure.get('property_id'))
            elif string_oracle:
                expected=failure.get('expected_value');actual=failure.get('actual_return')
                signature=functions.get(name,{})
                kind=signature.get('return_type') or {str:'String',int:'Int64',bool:'Bool',list:'Array<Int64>'}.get(type(expected))
                values.primitive(expected,kind,signature.get('types'));values.primitive(actual,kind,signature.get('types'))
                expected_matches=(same_args([case['expected']],[expected]) and
                    failure.get('expected')==json.dumps(expected,ensure_ascii=False,separators=(',',':')) and
                    failure.get('actual')==json.dumps(actual,ensure_ascii=False,separators=(',',':')))
            else:expected_matches=failure.get('expected')==literal(case['expected'])
            if not same_args(failure.get('args',case['args']),case['args']) or not expected_matches:
                raise ValueError('失败输入或预期与确认用例不一致')
            if name in functions:
                target['mapping']='CONFIRMED_CASE';queue=[(name,None)];seen=set()
                while queue and len(target['locations'])<8:
                    current,caller=queue.pop(0)
                    if current in seen or current not in functions:continue
                    seen.add(current);f=functions[current];path=f['path'];lines=source_files[path]['content'].splitlines()
                    anchors=f['return_lines'] or [f['final_line']]
                    if len(anchors)>4:truncated=True
                    excerpt=list(range(f['line'],min(f['end_line']+1,f['line']+40)))
                    if f['end_line']-f['line']+1>40:truncated=True
                    points=[]
                    for line in anchors[:4]:
                        report=analysis_reports.get(path)
                        if report is not None and report.get('slice_scope')=='MCP_NATIVE':
                            # Native variable rows are already in analysis context; do not turn them into guessed statement slices.
                            point=dict(status='UNAVAILABLE',reason='MCP返回变量级切片，未提供该语句准则切片',line=line,
                                       origin='MCP_SYMPAS_SLICE',scope='VARIABLE')
                        else:
                            point=point_slice(report,line) if report is not None else dict(status='UNAVAILABLE',reason='该文件没有可校验的MCP程序依赖图',line=line)
                        for key,limit in (('node_ids',32),('seed_nodes',32),('lines',40),('edges',32)):
                            if key in point:
                                point[key+'_count']=len(point[key])
                                if len(point[key])>limit:point['truncated']=True;truncated=True
                                point[key]=point[key][:limit]
                        points.append(dict(line=line,basis='RETURN_STATEMENT' if f['return_lines'] else 'FINAL_EXPRESSION',slice=point))
                    target['locations'].append(dict(function=current,path=path,source_sha256=f['source_sha256'],
                        coordinate_subject_id=binding['baseline_id'],start_line=f['line'],end_line=f['end_line'],
                        call_origin='CONFIRMED_CASE' if caller is None else 'LOCAL_SOURCE_INDEX',caller=caller,
                        anchors=points,source_lines=[dict(line=i,text=lines[i-1][:240],text_truncated=len(lines[i-1])>240) for i in excerpt]))
                    if any(len(lines[i-1])>240 for i in excerpt):truncated=True
                    queue.extend((c['name'],dict(function=current,path=path,line=c['line'])) for c in f['calls'] if c['name'] in functions and c['name'] not in seen)
                if queue:truncated=True
        targets.append(target)
    mapped=[t for t in targets if t['mapping']=='CONFIRMED_CASE']
    points=[a['slice'] for t in mapped for f in t['locations'] for a in f['anchors']]
    status=('NO_FAILURE' if not targets else 'UNMAPPED' if not mapped else
        'COMPLETE' if len(mapped)==len(targets) and points and all(p['status']=='VALID' for p in points) else 'PARTIAL')
    return dict(schema_version=1,algorithm='confirmed-case-scoped-baseline-pdg-v2' if scoped_index is not None else ALGORITHM,binding=deepcopy(binding),status=status,targets=targets,
        unavailable_sources=unavailable,truncated=truncated,limitations=list(LIMITATIONS))


def model_view(report):
    """A bounded projection. Full focus and original graphs remain in evidence."""
    view=deepcopy(report);view['context_hash']=digest(report);view['budget_bytes']=16384
    if len(view['unavailable_sources'])>8:
        view['unavailable_sources']=dict(list(view['unavailable_sources'].items())[:8]);view['truncated']=True
    for target in view['targets']:
        for location in target['locations']:
            if location.pop('source_lines',None):view['truncated']=True
            for anchor in location['anchors']:
                point=anchor['slice']
                if point.pop('edges',None):view['truncated']=True
    while len(json.dumps(view,ensure_ascii=False).encode())>16384:
        view['truncated']=True
        if not view['targets']:
            return dict(schema_version=1,algorithm=report.get('algorithm',ALGORITHM),context_hash=view['context_hash'],
                binding_hash=digest(report['binding']),budget_bytes=16384,status='UNAVAILABLE',targets=[],
                unavailable_sources={},truncated=True,limitations=['定位元数据超出模型预算；完整信息保留于原件'])
        if len(view['targets'])>1:view['targets'].pop();continue
        target=view['targets'][0]
        if not target['locations']:
            target['actual']=None;target['expected']=None
            if len(json.dumps(view,ensure_ascii=False).encode())>16384:
                view['targets']=[];view['omitted_targets_count']=len(report['targets'])
            continue
        if len(target['locations'])>1:target['locations'].pop();continue
        location=target['locations'][0]
        if len(location['anchors'])>1:location['anchors'].pop();continue
        if location['anchors']:
            point=location['anchors'][0]['slice']
            for key in ('node_ids','seed_nodes','lines'):
                if point.get(key):point[key]=point[key][:len(point[key])//2];break
            else:
                location['anchors']=[];location['anchors_omitted']='定位上下文预算，完整结果见原件'
            continue
        # Unmapped text is not needed to generate a patch; retain its identity.
        target['actual']=None;target['expected']=None
        if len(json.dumps(view,ensure_ascii=False).encode())>16384:
            view['targets']=[];view['omitted_targets_count']=len(report['targets'])
    return view
