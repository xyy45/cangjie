"""Frozen public assertion mapping. A leaf observation is never a whole object.

String diff output is retained as text: it does not reveal a canonical actual
String. This module performs no SDK, model, native IPC or file writes.
"""
from copy import deepcopy
import re
from nexus.contracts import digest,file_hash
from nexus.repair import object_values,values
from nexus.repair.counterexamples import ANSI,CASE
from nexus.projects.index import TestParser,TEST_TOKEN,inspect_project
from nexus.uploads.language import inspect_source,tokens,literal
from nexus.uploads.public_tests import render
from nexus.adapters.cangjie.report_parser import control_text,SUMMARY,SUITE

EQUALITY=re.compile(r'^\s*Expect Failed: `\(([^\n`]{1,8192}) == ([^\n`]{1,4096})\)`\s*\n[ \t]*left: ([^\n]{1,4096})\n[ \t]*right: ([^\n]{1,4096})',re.M)
STRING=re.compile(r'^[ \t]*Expect Failed: ([^\n]{1,8192}) != ([^\n]{1,4096}) \(multiline difference below\)\n((?:[ \t]{8}[+ \-][^\n]*\n){1,1024})',re.M)
HEAD=re.compile(SUITE.pattern+r'|^[ \t]*\[\s*(?:PASSED|FAILED|SKIPPED|ERROR)\s*\] CASE:\s*\w+\s+\([^)]*\)[ \t]*$',re.M)


def token_key(text):return tuple(t[0] for t in tokens(text,pattern=TEST_TOKEN) if t[0]!='<eof>')


def leaf(text,kind,types):
    parser=TestParser(text,{},'','',types=types);value=parser.primitive();parser.take('<eof>')
    return values.primitive(value,kind,types)


def projected(text,types):
    """Only entry(Constructor(literals...),...).field, never member calls."""
    parser=TestParser(text,{},'','',types=types);name=parser.name();parser.take('(');args=[]
    if parser.peek()!=')':
        while True:
            args.append(parser.primitive())
            if len(args)>4:raise ValueError('公开调用参数过多')
            if not parser.accept(','):break
    parser.take(')');path=[]
    if parser.accept('.'):path.append(parser.name())
    parser.take('<eof>');return name,args,path


def _mapping(value,info,files):
    project=value.get('kind')=='PROJECT';test_path='src/nexus_uploaded_test.cj' if project else 'src/cases_test.cj'
    scoped=project and info.get('version')==2
    actual=inspect_project({n:files[n] for n in info['manifest']}) if project else inspect_source(files['src/uploaded.cj'].decode('utf-8'))
    if actual!=info:raise ValueError('公开字段索引与冻结源码不符')
    types=object_values.registry(actual.get('types',{}))
    if not types and not scoped:return None
    function=value['function'];signature=next(f for f in info['functions'] if f['name']==function);original=value.get('original_tests',[])
    if scoped:
        from nexus.uploads.scoped_public_tests import render as scoped_render
        program,metadata=scoped_render(info,function,value['examples']);test_path=metadata['public_test_path']
    else:program,metadata=render(info['package'] or 'uploadedrepair',function,signature,value['examples'],types,info['functions'],original)
    if files.get(test_path)!=program.encode() or any(value.get(k)!=v for k,v in metadata.items()):raise ValueError('公开字段测试模板或名称绑定变化')
    mapping={};orig={}
    def add(identity,expression,args,path,expected,kind):
        mapping[(identity,token_key(expression))]=dict(function=function,args=deepcopy(args),field_path=path,expected_value=deepcopy(expected),value_type=kind,public_test=dict(path=test_path,sha256=file_hash(program)))
    for index,e in enumerate(value['examples']):
        identity=(metadata['public_test_package']+'.' if scoped else '')+metadata['public_test_class']+'.case'+str(index);returned=signature['return_type'];expected=values.primitive(e['expected'],returned,types)
        if returned not in types:
            from nexus.repair.object_trace import input_literal
            expression=metadata['public_test_target']+'('+', '.join(input_literal(a,types,metadata['public_test_constructors']) for a in e['args'])+')'
            add(identity,expression,e['args'],[],expected,returned);continue
        local=metadata['public_test_locals'][str(index)]
        for field in types[returned]['fields']:
            name=field['name'];kind=field['type'];part=expected['fields'][name];expression=local+'.'+name
            if kind!='Array<Int64>':add(identity,expression,e['args'],[name],part,kind)
            else:
                add(identity,expression+'.size',e['args'],[name,'$size'],len(part),'Int64')
                for i,n in enumerate(part):add(identity,expression+'['+str(i)+']',e['args'],[name,i],n,'Int64')
    for entry in original:
        if info.get('test_cases') is None or entry not in info['test_cases']:raise ValueError('原工程测试索引变化')
        orig[entry['id']]=entry
    return types,mapping,orig


def resolve(check,value,info,files):
    bound=_mapping(value,info,files)
    if bound is None:return None
    types,mapping,original=bound;text=ANSI.sub('',check.diagnostics);controls=control_text(text);summary=SUMMARY.search(controls)
    stop=summary.start() if summary else len(text);detail=text[:stop];sections={};suite=None;parts=list(HEAD.finditer(controls[:stop]))
    for index,part in enumerate(parts):
        if part.group(1):suite=part.group(1);continue
        case=CASE.fullmatch(part.group())
        if suite and case and case.group(1)=='FAILED':sections.setdefault(suite+'.'+case.group(2),(part.end(),parts[index+1].start() if index+1<len(parts) else len(detail)))
    cases=[];failures=[];seen=set();truncated=False
    for identity,state in check.case_results.items():
        if state!='FAIL':continue
        if identity not in sections:raise ValueError('公开失败缺少对应SDK用例区段')
        begin,end=sections[identity];section=detail[begin:end]
        found=sorted([(m.start(),m,'TYPED') for m in EQUALITY.finditer(control_text(section))]+[(m.start(),m,'TEXT_ONLY') for m in STRING.finditer(section)],key=lambda x:x[0])
        if not found:raise ValueError('公开失败没有可绑定字段断言')
        for _,match,mode in found:
            expression=match.group(1).strip();binding=mapping.get((identity,token_key(expression)))
            if binding is None and identity in original:
                entry=original[identity];name,args,path=projected(expression,types)
                if name!=entry['function'] or len(args)!=len(entry['args']) or any(values.typed_key(a)!=values.typed_key(b) for a,b in zip(args,entry['args'])):
                    raise ValueError('原工程公开调用输入不符')
                if path!=entry.get('projection',[]):raise ValueError('原工程公开字段投影不符')
                returned=next(f['return_type'] for f in info['functions'] if f['name']==name)
                kind=entry['expected_type'] if path else returned
                if kind in types:raise ValueError('原工程对象返回必须逐字段投影')
                binding=dict(function=name,args=deepcopy(args),field_path=path,expected_value=deepcopy(entry['expected']),value_type=kind,public_test=dict(path=entry['path'],sha256=file_hash(files[entry['path']].decode('utf-8'))))
            if binding is None:raise ValueError('SDK断言表达式不在冻结公开模板中')
            kind=binding['value_type'];expected=binding['expected_value'];right=leaf(match.group(2),kind,types)
            if values.typed_key(right)!=values.typed_key(expected):raise ValueError('SDK断言预期与冻结字段不符')
            if mode=='TYPED':
                actual=leaf(match.group(3).strip(),kind,types);printed_expected=leaf(match.group(4).strip(),kind,types)
                if values.typed_key(printed_expected)!=values.typed_key(expected):raise ValueError('SDK右值与冻结字段不符')
                actual_text=match.group(3).strip()
            else:
                if kind!='String':raise ValueError('差异文本只用于String字段')
                actual=None;actual_text=match.group(3)
            key=(identity,tuple(binding['field_path']))
            if key in seen:raise ValueError('同一公开字段断言重复')
            seen.add(key);start=begin+match.start();stop=begin+match.end();call_id='PUBLIC_FIELD-'+digest(dict(test_id=identity,field_path=binding['field_path'],log_ref=check.log_ref,start_char=start))[:16]
            fact=dict(kind='public_field',test_id=identity,call_id=call_id,**deepcopy(binding),actual_value=deepcopy(actual),value_state=mode,actual_text=actual_text[:1024],text_truncated=len(actual_text)>1024,
                actual=actual_text[:1024],expected=json_text(expected),requirement_refs=['REQ-UPLOAD'],mapping_basis='FROZEN_PUBLIC_FIELD',source=dict(log_ref=check.log_ref,coordinate='ANSI_STRIPPED_CHECK_DIAGNOSTICS',start_char=start,end_char=stop))
            failures.append(fact);cases.append(dict(test_id=identity,call_id=call_id,function=binding['function'],args=deepcopy(binding['args']),field_path=deepcopy(binding['field_path']),expected_value=deepcopy(expected),value_type=kind,requirement_refs=['REQ-UPLOAD']))
            if len(failures)==50:truncated=True;break
        if truncated:break
    return dict(cases=cases,failures=failures,truncated=truncated)


def json_text(value):
    import json
    return json.dumps(value,ensure_ascii=False,separators=(',',':'))


def for_task(store,task,check,*,spec=None):
    if task.schema_version!=2:return None
    from nexus.requirements.service import RequirementService
    from nexus.execution.workspace import WorkspaceStore
    from nexus.uploads.service import UploadService
    from nexus.contracts import source_manifest
    if spec is None:spec,_=RequirementService(store).task_context(task)
    if not spec.project_id.startswith('upload_'):return None
    uploads=UploadService(store);value=uploads._read(spec.project_id);uploads.profile(spec.project_id)
    root=WorkspaceStore(store.root).verify_baseline(task.baseline_id);files={n:(root/n).read_bytes() for n in source_manifest(root)}
    info=value['project_index'] if value.get('kind')=='PROJECT' else inspect_source(files['src/uploaded.cj'].decode('utf-8'))
    if value.get('kind')=='PROJECT' and info['version']==2:
        from nexus.repair.package_evidence import subject_context,checked_record
        from nexus.repair.scoped_public_fields import resolve as scoped_resolve
        _,plan=RequirementService(store).task_context(task)
        from nexus.adapters.cangjie.verifier import CangjieVerifier
        _,tree,check_plan=CangjieVerifier(store.root,task.id).identity(check.subject_id)
        if check.tree_hash!=tree or check.plan_hash!=check_plan:raise ValueError('Scoped字段检查执行身份已变化')
        parsed=checked_record(store,check.model_dump(),context=subject_context(store,task,check.subject_id),plan=plan)
        if parsed['state']!=check.state or parsed['state']!='FAIL':raise ValueError('Scoped公开字段缺少已绑定XML失败原件')
        return scoped_resolve(check,value,info,files,parsed)
    return resolve(check,value,info,files)
