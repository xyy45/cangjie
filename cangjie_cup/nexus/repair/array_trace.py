"""Strict V3 Array wire values and trusted bounded SDK harness fragments.

The candidate never controls the protocol, token, test identities or encoder.
"""
import re
from nexus.repair import string_trace,values

PROTOCOLS={'oracle':('NEXUS_ORACLE_V3|','NexusOracleV3'),
           'single':('NEXUS_PROPERTY_V3|','NexusPropertiesV3'),
           'relation':('NEXUS_RELATION_V3|','NexusRelationsV3')}
SEQUENCE='NEXUS_SEQUENCE_V3|'
END='NEXUS_SEQUENCE_END_V3|'
ERROR='NEXUS_VALUE_ERROR_V3|'
PREFIXES=tuple(p[0] for p in PROTOCOLS.values())+(SEQUENCE,END,ERROR)
NL=chr(10)


def encode(value,kind):
    value=values.primitive(value,kind)
    if kind=='Array<Int64>':return 'a:'+str(len(value))+':'+','.join(str(n) for n in value)
    return string_trace.encode(value,kind)


def decode(text,kind):
    if kind!='Array<Int64>':return string_trace.decode(text,kind)
    if type(text) is not str or len(text)>340:raise ValueError('Array观测必须为有界规范文本')
    fields=text.split(':')
    if len(fields)!=3 or fields[0]!='a' or not re.fullmatch(r'(?:0|[1-9]|1[0-6])',fields[1]):raise ValueError('Array观测标识或长度无效')
    parts=[] if fields[2]=='' else fields[2].split(',')
    if len(parts)!=int(fields[1]):raise ValueError('Array观测长度与项目数不符')
    return values.array([string_trace.decode(item,'Int64') for item in parts])


def encoder_method(name):
    return NL.join(['private func '+name+'(value: Array<Int64>): String {','var result = "a:${value.size}:"',
        'var first = true','for (item in value) {','if (!first) { result = result + "," }',
        'result = result + "${item}"','first = false','}','return result','}',''])


def header(signature,package,token,cls,*,sequence=False):
    if (any(type(value) is not str for value in (package,token,cls,signature.get('name'))) or
            not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*',package) or not re.fullmatch('[0-9a-f]{16}',token) or
            not re.fullmatch(r'[A-Za-z_]\w*',cls) or not re.fullmatch(r'[A-Za-z_]\w*',signature['name'])):raise ValueError('V3 harness名称无效')
    reserved={signature['name'],cls};reserved.update(p['name'] for p in signature['params'] if type(p.get('name')) is str)
    output=string_trace._fresh(('__nexusSeqPrint' if sequence else '__nexusPrint')+token,reserved)
    target=string_trace._fresh('__nexusV3Bound'+token,reserved)
    kind=signature['return_type'];encoder=string_trace._fresh(('__nexusArrayEncode' if kind=='Array<Int64>' else '__nexusStringEncode')+token,reserved)
    parameters=', '.join(p['type'] for p in signature['params'])
    source=NL.join(['package '+package,'import std.core.println as '+output,'import std.unittest.*','import std.unittest.testmacro.*',
        'private let '+target+': ('+parameters+') -> '+kind+' = '+signature['name'],'@Test','class '+cls+' {',''])
    if kind=='Array<Int64>':source+=encoder_method(encoder)
    elif kind=='String':source+=string_trace.encoder_method(encoder)
    return dict(source=source,output=output,target=target,encoder=encoder,reserved=reserved)


def wire(kind,variable,encoder):return encoder+'('+variable+')' if kind in ('Array<Int64>','String') else variable


def limit_guard(kind,variable,output,token,case):
    if kind not in ('Array<Int64>','String'):return ''
    limit=16 if kind=='Array<Int64>' else 256
    return NL.join(['if ('+variable+'.size > '+str(limit)+') {',output+'("'+ERROR+token+'|case'+str(case)+'|VALUE_LIMIT")','return','}',''])
