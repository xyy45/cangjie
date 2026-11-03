"""Bounded value wire format and trusted V2 harness fragments.

String data is UTF-8 hex, never a line of the control protocol. No evaluation.
"""
import re
from nexus.repair import oracle,values

PROTOCOLS={'oracle':('NEXUS_ORACLE_V2|','NexusOracleV2'),
           'single':('NEXUS_PROPERTY_V2|','NexusPropertiesV2'),
           'relation':('NEXUS_RELATION_V2|','NexusRelationsV2')}
SEQUENCE='NEXUS_SEQUENCE_V2|'
END='NEXUS_SEQUENCE_END_V2|'
ERROR='NEXUS_VALUE_ERROR_V2|'
PREFIXES=tuple(p[0] for p in PROTOCOLS.values())+(SEQUENCE,END,ERROR)
NL=chr(10)


def encode(value,kind):
    values.primitive(value,kind)
    if kind=='String':return 's:'+value.encode('utf-8').hex()
    return str(value).lower() if kind=='Bool' else str(value)


def decode(text,kind):
    if type(text) is not str:raise ValueError('观测值必须为规范文本')
    if kind=='String':
        if not text.startswith('s:'):raise ValueError('String观测缺少编码标识')
        raw=text[2:]
        if len(raw)>512 or len(raw)%2 or not re.fullmatch('[0-9a-f]*',raw):raise ValueError('String观测不是有界小写十六进制')
        try:return values.string(bytes.fromhex(raw).decode('utf-8',errors='strict'))
        except UnicodeError:raise ValueError('String观测不是合法UTF-8') from None
    if kind=='Bool':
        if text not in ('true','false'):raise ValueError('Bool观测文本无效')
        return text=='true'
    if kind!='Int64' or not re.fullmatch(r'-?(?:0|[1-9][0-9]*)',text):raise ValueError('Int64观测文本无效')
    result=oracle.integer(int(text))
    if str(result)!=text:raise ValueError('Int64观测不是规范文本')
    return result


def _fresh(stem,reserved):
    name=stem
    while name in reserved:name+='Value'
    reserved.add(name);return name


def encoder_method(name):
    digits=', '.join('"'+c+'"' for c in '0123456789abcdef')
    return NL.join(['private func '+name+'(value: String): String {','let digits = ['+digits+']','var result = "s:"',
        'for (byte in value.toArray()) {','let high = Int64(byte) / 16','let low = Int64(byte) % 16',
        'result = result + digits[high] + digits[low]','}','return result','}',''])


def header(signature,package,token,cls,*,sequence=False):
    if (not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*',package) or not re.fullmatch('[0-9a-f]{16}',token) or
            not re.fullmatch(r'[A-Za-z_]\w*',cls) or not re.fullmatch(r'[A-Za-z_]\w*',signature['name'])):raise ValueError('V2 harness名称无效')
    reserved={signature['name'],cls};reserved.update(p['name'] for p in signature['params'] if type(p.get('name')) is str)
    output=_fresh(('__nexusSeqPrint' if sequence else '__nexusPrint')+token,reserved)
    target=_fresh('__nexusV2Bound'+token,reserved);encoder=_fresh('__nexusStringEncode'+token,reserved)
    kind=signature['return_type'];parameters=', '.join(p['type'] for p in signature['params'])
    # Bind at package scope, before a test method named case0 can shadow the target.
    source=NL.join(['package '+package,'import std.core.println as '+output,'import std.unittest.*','import std.unittest.testmacro.*',
        'private let '+target+': ('+parameters+') -> '+kind+' = '+signature['name'],'@Test','class '+cls+' {',''])
    if kind=='String':source+=encoder_method(encoder)
    return dict(source=source,output=output,target=target,encoder=encoder,reserved=reserved)


def wire(kind,variable,encoder):return encoder+'('+variable+')' if kind=='String' else variable


def limit_guard(kind,variable,output,token,case):
    if kind!='String':return ''
    return NL.join(['if ('+variable+'.size > 256) {',output+'("'+ERROR+token+'|case'+str(case)+'|VALUE_LIMIT")','return','}',''])
