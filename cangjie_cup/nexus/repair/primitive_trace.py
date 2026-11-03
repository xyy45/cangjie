"""Bounded typed SDK observations, independent of business assertions."""
import re
from copy import deepcopy

from nexus.adapters.cangjie.report_parser import ANSI,parse_test_report
from nexus.repair import oracle,string_trace,array_trace,object_trace,scoped_values,object_values,values as primitive_values
from nexus.uploads.language import literal

PROTOCOLS={'single':('NEXUS_PROPERTY_V1|','NexusProperties'),
           'relation':('NEXUS_RELATION_V1|','NexusRelations')}
OBSERVATION_PREFIXES=tuple(p[0] for p in PROTOCOLS.values())+('NEXUS_SEQUENCE_V1|','NEXUS_SEQUENCE_END_V1|')+string_trace.PREFIXES+array_trace.PREFIXES+object_trace.PREFIXES+scoped_values.PREFIXES
SUITE_HEADER=re.compile(r'^\s*TCS:\s*(\w+),\s*(?:time elapsed:\s*\d+(?:\.\d+)?\s*(?:ns|[μµu]s|ms|s),\s*)?RESULT:\s*$')
CASE=re.compile(r'^\s*\[\s*(PASSED|FAILED|SKIPPED|ERROR)\s*\] CASE:\s*(\w+)\s+\([^)]*\)\s*$')


def protocol(kind,version=1):
    if type(version) is not int or version not in (1,2,3,4,5):raise ValueError('观测协议版本无效')
    protocols=PROTOCOLS if version==1 else string_trace.PROTOCOLS if version==2 else array_trace.PROTOCOLS if version==3 else object_trace.PROTOCOLS if version==4 else scoped_values.PROTOCOLS
    if type(kind) is not str or kind not in protocols:raise ValueError('观测协议类型无效')
    return protocols[kind]


def case_ids(token,count,kind,version=1,signature=None):
    _,name=protocol(kind,version)
    if version==5:
        from nexus.repair import scoped_trace
        return scoped_trace.case_ids(signature,count,token,kind)
    if type(token) is not str or not re.fullmatch(r'[0-9a-f]{16}',token):raise ValueError('观测token无效')
    limit=256 if version>=2 and kind=='oracle' else 128
    if type(count) is not int or not 1<=count<=limit:raise ValueError('观测输入超过当前协议预算')
    cls=name+token
    if version==4 and signature is not None:
        while cls in object_trace.reserved_names(signature):cls+='Value'
    if version>=2 and signature is not None:
        if type(signature) is not dict or type(signature.get('name')) is not str:raise ValueError('观测函数签名无效')
        if cls==signature['name']:cls+='Value'
    return [cls+'.case'+str(i) for i in range(count)]


def validate_inputs(signature,inputs,version=1):
    protocol('single',version)
    if version==5:
        from nexus.repair import scoped_trace
        return scoped_trace.validate_inputs(signature,inputs)
    if 'scope' in signature:raise ValueError('Scoped签名不能使用旧观测协议')
    if version==4:
        signature=oracle.stable_signature(signature)
        if not object_values.has_objects(signature):raise ValueError('V4观测需要对象签名')
    kinds=('Int64','Bool') if version==1 else ('Int64','Bool','String') if version==2 else ('Int64','Bool','String','Array<Int64>')+tuple(signature.get('types',{}) if version==4 else ())
    if (type(signature) is not dict or type(signature.get('name')) is not str or
            not re.fullmatch(r'[A-Za-z_]\w*',signature['name']) or
            type(signature.get('params')) is not list or len(signature['params'])>4 or
            signature.get('return_type') not in kinds):raise ValueError('观测函数签名无效')
    if any(type(p) is not dict or p.get('type') not in kinds for p in signature['params']):raise ValueError('观测参数类型无效')
    if version==2 and not primitive_values.has_strings(signature):raise ValueError('V2观测需要String签名')
    if version==3 and not primitive_values.has_arrays(signature):raise ValueError('V3观测需要Array签名')
    if type(inputs) is not list or not 1<=len(inputs)<=(128 if version==1 else 256):raise ValueError('观测输入超出协议预算')
    for args in inputs:
        if type(args) is not list or len(args)!=len(signature['params']):raise ValueError('观测参数数目无效')
        for arg,p in zip(args,signature['params']):
            primitive_values.primitive(arg,p['type'],signature.get('types') if version==4 else None)


def harness(signature,inputs,package,token,kind,version=1,*,binding=None):
    validate_inputs(signature,inputs,version);identities=case_ids(token,len(inputs),kind,version,signature)
    if version==5:
        from nexus.repair import scoped_trace
        if type(binding) is not dict or binding.get('package')!=package:raise ValueError('V5需要来源绑定的验证包')
        return scoped_trace.render(signature,inputs,nonce=token,mode=kind,binding=binding)['source']
    if binding is not None:raise ValueError('旧协议不接受Scoped来源绑定')
    if version>=2:return _harness_v2(signature,inputs,package,token,kind,identities[0].split('.')[0],version=version)
    if type(package) is not str or not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*',package):raise ValueError('观测包名无效')
    prefix,cls=protocol(kind);name=signature['name'];variable='__nexusObserved'
    while variable==name:variable+='Value'
    output='__nexusPrint'+token
    while output==name:output+='Value'
    target='__nexusTarget'+token
    while target==name:target+='Value'
    text='package '+package+'\nimport std.core.println as '+output+'\nimport std.unittest.*\nimport std.unittest.testmacro.*\n@Test\nclass '+cls+token+' {\n'
    primitive=signature['return_type']
    for i,args in enumerate(inputs):
        text+='@TestCase\nfunc case'+str(i)+'() {\n'
        text+='let '+target+': ('+', '.join(p['type'] for p in signature['params'])+') -> '+primitive+' = '+name+'\n'
        text+='let '+variable+' = '+target+'('+', '.join(literal(a,signature.get('types') if version==4 else None) for a in args)+')\n'
        text+=output+'("'+prefix+token+'|case'+str(i)+'|'+primitive+'|${'+variable+'}")\n}\n'
    return (text+'}\n').encode()


def read(signature,inputs,token,kind,log,exit_code,problem,version=1):
    validate_inputs(signature,inputs,version);expected=case_ids(token,len(inputs),kind,version,signature)
    if version==5:
        from nexus.repair import scoped_trace
        result=scoped_trace.read(log,signature,expected,nonce=token,mode=kind,exit_code=exit_code,problem=problem)
        if result['state']=='PASS':
            for item,args in zip(result['observations'],inputs):item['args']=deepcopy(args)
        return result
    prefix,_=protocol(kind,version);parsed=parse_test_report(log);codec=object_trace if version==4 else array_trace if version==3 else string_trace
    unknown=dict(state='UNKNOWN',execution_state=parsed.state,counts=parsed.counts,observations=[],reason='原始类型观测不完整或执行未成功')
    if (problem is not None or exit_code!=0 or parsed.state!='PASS' or
            set(parsed.case_results)!=set(expected) or any(v!='PASS' for v in parsed.case_results.values())):return unknown
    clean=ANSI.sub('',log);detail=clean.split('Summary:',1)[0];suite=None;case=None;stdout=False;found={};offset=0
    if any(line.strip().startswith(OBSERVATION_PREFIXES) for line in clean[len(detail):].splitlines()):return unknown
    for line in detail.splitlines(keepends=True):
        stripped=line.strip();reserved=stripped.startswith(OBSERVATION_PREFIXES)
        header=None if reserved else SUITE_HEADER.fullmatch(line.rstrip('\r\n'))
        match=None if reserved else CASE.fullmatch(line.rstrip('\r\n'))
        if header:suite=header.group(1);case=None;stdout=False
        elif match:case=suite+'.'+match.group(2) if suite else None;stdout=False
        elif stripped in ('STDOUT:','STDERR:'):stdout=stripped=='STDOUT:'
        elif stripped.startswith(OBSERVATION_PREFIXES):
            fields=(line.lstrip().rstrip(chr(13)+chr(10)) if version>=2 else stripped).split('|')
            if (not stripped.startswith(prefix) or not stdout or case not in expected or case in found or len(fields)!=5 or
                    fields[1]!=token or fields[2]!=case.split('.')[-1] or fields[3]!=signature['return_type']):return unknown
            value=fields[4]
            try:actual=codec.decode(value,fields[3],signature['types']) if version==4 else codec.decode(value,fields[3])
            except ValueError:return unknown
            found[case]=dict(actual_return=actual,source=dict(coordinate='ANSI_STRIPPED_FULL_LOG',start_char=offset,end_char=offset+len(line.rstrip('\r\n'))))
        offset+=len(line)
    if set(found)!=set(expected):return unknown
    observations=[dict(test_id=identity,args=deepcopy(args),**found[identity]) for identity,args in zip(expected,inputs)]
    return dict(state='PASS',execution_state='PASS',counts=parsed.counts,observations=observations,reason='')


def _harness_v2(signature,inputs,package,token,kind,cls,version=2):
    codec=string_trace if version==2 else array_trace if version==3 else object_trace
    prefix,_=protocol(kind,version);parts=codec.header(signature,package,token,cls)
    output,target,encoder=(parts[k] for k in ('output','target','encoder'));text=parts['source'];primitive=signature['return_type']
    variable='__nexusObserved'
    while variable in parts['reserved']:variable+='Value'
    for i,args in enumerate(inputs):
        text+='@TestCase'+chr(10)+'func case'+str(i)+'() {'+chr(10)
        text+='let '+variable+' = '+target+'('+', '.join(object_trace.input_literal(a,signature['types'],parts['constructors']) if version==4 else literal(a) for a in args)+')'+chr(10)
        text+=codec.limit_guard(primitive,variable,output,token,i,signature['types']) if version==4 else codec.limit_guard(primitive,variable,output,token,i)
        text+=output+'("'+prefix+token+'|case'+str(i)+'|'+primitive+'|${'+codec.wire(primitive,variable,encoder)+'}")'+chr(10)+'}'+chr(10)
    return (text+'}'+chr(10)).encode()
