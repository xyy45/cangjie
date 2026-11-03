"""Strict V4 nominal object wire and trusted SDK field encoders.

Only public readonly fields are read; user equality/toString are never called.
"""
import re
from nexus.repair import object_values,array_trace,string_trace,values

PROTOCOLS={kind:('NEXUS_'+prefix+'_V4|',name+'V4') for kind,prefix,name in (
    ('oracle','ORACLE','NexusOracle'),('single','PROPERTY','NexusProperties'),('relation','RELATION','NexusRelations'))}
SEQUENCE='NEXUS_SEQUENCE_V4|'
END='NEXUS_SEQUENCE_END_V4|'
ERROR='NEXUS_VALUE_ERROR_V4|'
PREFIXES=tuple(p[0] for p in PROTOCOLS.values())+(SEQUENCE,END,ERROR)
NL=chr(10)
MAX_WIRE=2141


def encode(value,kind,types):
    types=object_values.registry(types);value=values.primitive(value,kind,types)
    if kind not in types:return array_trace.encode(value,kind)
    fields=types[kind]['fields'];parts=[array_trace.encode(value['fields'][f['name']],f['type']) for f in fields]
    return 'o:'+kind+':'+str(len(parts))+':'+''.join(str(len(part))+':'+part for part in parts)


def decode(text,kind,types):
    return _decode(text,kind,types,MAX_WIRE)


def _decode(text,kind,types,max_wire):
    types=object_values.registry(types)
    if kind not in types:return array_trace.decode(text,kind)
    if type(text) is not str or len(text)>max_wire:raise ValueError('对象观测必须为有界规范文本')
    fields=types[kind]['fields'];prefix='o:'+kind+':'+str(len(fields))+':'
    if not text.startswith(prefix):raise ValueError('对象观测名义类型或字段数量不符')
    offset=len(prefix);result={}
    for field in fields:
        end=text.find(':',offset)
        if end<0:raise ValueError('对象字段长度缺失')
        length=text[offset:end]
        if not re.fullmatch(r'(?:0|[1-9][0-9]{0,2})',length):raise ValueError('对象字段长度不是规范文本')
        count=int(length);offset=end+1
        if count>514 or offset+count>len(text):raise ValueError('对象字段长度越界')
        result[field['name']]=array_trace.decode(text[offset:offset+count],field['type']);offset+=count
    if offset!=len(text):raise ValueError('对象观测包含尾随文本')
    return object_values.value({'$type':kind,'fields':result},kind,types)


def reserved_names(signature):
    types=object_values.registry(signature.get('types',{}));names={signature['name'],*types}
    names.update(p['name'] for p in signature['params'])
    for item in types.values():
        names.update(f['name'] for f in item['fields']);names.update(m['name'] for m in item['methods'])
        names.update(p['name'] for m in item['methods'] for p in m['params'])
    return names


def constructors(types,reserved):
    """Resolve nominal constructors at package scope, before caseN methods."""
    source='';names={}
    for index,(kind,definition) in enumerate(object_values.registry(types).items()):
        name=string_trace._fresh('__nexusObjectCtor'+str(index),reserved);names[kind]=name
        fields=definition['fields'];args=[string_trace._fresh('__nexusCtorField'+str(i),reserved) for i in range(len(fields))]
        source+='private func '+name+'('+', '.join(a+': '+f['type'] for a,f in zip(args,fields))+'): '+kind+' { return '+kind+'('+', '.join(args)+') }'+NL
    return source,names


def input_literal(value,types,names):
    from nexus.uploads.language import literal
    text=literal(value,types)
    return names[value['$type']]+text[len(value['$type']):] if type(value) is dict else text


def header(signature,package,token,cls,*,sequence=False):
    if (any(type(value) is not str for value in (package,token,cls,signature.get('name'))) or
            not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*',package) or not re.fullmatch('[0-9a-f]{16}',token) or
            not re.fullmatch(r'[A-Za-z_]\w*',cls) or not re.fullmatch(r'[A-Za-z_]\w*',signature['name'])):raise ValueError('V4 harness名称无效')
    types=object_values.registry(signature['types']);reserved=reserved_names(signature)|{cls};fresh=lambda stem:string_trace._fresh(stem,reserved)
    output=fresh(('__nexusSeqPrint' if sequence else '__nexusPrint')+token);target=fresh('__nexusV4Bound'+token)
    encoder=fresh('__nexusObjectEncode'+token);kind=signature['return_type'];parameters=', '.join(p['type'] for p in signature['params'])
    factory_source,factories=constructors(types,reserved)
    source=NL.join(['package '+package,'import std.core.println as '+output,'import std.unittest.*','import std.unittest.testmacro.*',
        'private let '+target+': ('+parameters+') -> '+kind+' = '+signature['name'],factory_source,'@Test','class '+cls+' {',''])
    if kind in types:
        fields=types[kind]['fields'];string_encoder=fresh('__nexusFieldString'+token);array_encoder=fresh('__nexusFieldArray'+token)
        if any(f['type']=='String' for f in fields):source+=string_trace.encoder_method(string_encoder)
        if any(f['type']=='Array<Int64>' for f in fields):source+=array_trace.encoder_method(array_encoder)
        variable=fresh('__nexusObjectValue');result=fresh('__nexusObjectWire')
        source+=NL.join(['private func '+encoder+'('+variable+': '+kind+'): String {','var '+result+' = "o:'+kind+':'+str(len(fields))+':"',''])
        for index,field in enumerate(fields):
            part=fresh('__nexusObjectFieldWire'+str(index));access=variable+'.'+field['name'];leaf_encoder=string_encoder if field['type']=='String' else array_encoder
            source+=NL.join(['let '+part+' = "${'+array_trace.wire(field['type'],access,leaf_encoder)+'}"',result+' = '+result+' + "${'+part+'.size}:" + '+part,''])
        source+='return '+result+NL+'}'+NL
    elif kind=='String':source+=string_trace.encoder_method(encoder)
    elif kind=='Array<Int64>':source+=array_trace.encoder_method(encoder)
    return dict(source=source,output=output,target=target,encoder=encoder,reserved=reserved,constructors=factories)


def wire(kind,variable,encoder):
    return variable if kind in ('Int64','Bool') else encoder+'('+variable+')'


def limit_guard(kind,variable,output,token,case,types):
    types=object_values.registry(types)
    checks=[(variable+'.'+f['name'],16 if f['type']=='Array<Int64>' else 256) for f in types[kind]['fields'] if f['type'] in ('Array<Int64>','String')] if kind in types else [(variable,16 if kind=='Array<Int64>' else 256)] if kind in ('Array<Int64>','String') else []
    return ''.join(NL.join(['if ('+access+'.size > '+str(limit)+') {',output+'("'+ERROR+token+'|case'+str(case)+'|VALUE_LIMIT")','return','}','']) for access,limit in checks)
