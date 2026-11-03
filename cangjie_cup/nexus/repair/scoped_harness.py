"""Trusted V5 fragments built from controller-derived material bindings.

Shape checks prevent interpolation; source ownership additionally requires the
caller to rebuild the entire material and compare manifests at every gate.
"""
from pathlib import PurePosixPath
import re

from nexus.contracts import digest
from nexus.projects.names import local_name
from nexus.repair import scoped_values,string_trace,array_trace,values,scoped_imports
from nexus.repair.scoped_material import fresh,nonce
from nexus.repair.scoped_signature import validate
from nexus.uploads.language import literal

BINDING_KEYS={'version','nonce','package','signature_hash','source_tree_hash','graph_hash','private','target','target_alias','type_names','imports','bridge_path','bridge_sha256'}
NL='\n'


def checked_binding(signature,binding,token):
    token=nonce(token);signature=validate(signature)
    if (type(binding) is not dict or set(binding)!=BINDING_KEYS or type(binding['version']) is not int or
            binding['version']!=1 or binding['nonce']!=token or binding['signature_hash']!=digest(signature) or
            binding['graph_hash']!=signature['scope']['graph_hash'] or
            binding['package']!=signature['scope']['root_package']+'.nexus_verify_'+token or type(binding['private']) is not bool):
        raise ValueError('V5材料绑定与源码签名不一致')
    if type(binding['source_tree_hash']) is not str or not re.fullmatch('[0-9a-f]{64}',binding['source_tree_hash']):
        raise ValueError('V5材料源摘要无效')
    needed={p['type'] for p in signature['params']}|{signature['return_type']}
    needed={t for t in needed if t in signature.get('types',{})}
    names=binding['type_names']
    if type(names) is not dict or set(names)!=needed:raise ValueError('V5类型别名范围无效')
    if binding['private']:
        prefix=signature['scope']['package']+'.__nexusBridge_'+token
        if type(binding['target']) is not str or not re.fullmatch(re.escape(prefix)+r'(?:_[0-9a-f]+)?',binding['target']):
            raise ValueError('V5私有入口桥接身份无效')
        directory=str(PurePosixPath(signature['scope']['path']).parent)
        expected=directory+'/nexus_verify_bridge_'+token
        if type(binding['bridge_path']) is not str or not re.fullmatch(re.escape(expected)+r'(?:_[0-9a-f]+)?\.cj',binding['bridge_path']):
            raise ValueError('V5桥接文件不属于入口包')
        if type(binding['bridge_sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',binding['bridge_sha256']):
            raise ValueError('V5桥接原件摘要无效')
    elif binding['target']!=signature['name'] or binding['bridge_path'] is not None or binding['bridge_sha256'] is not None:
        raise ValueError('V5公开入口不能替换目标函数')
    references={kind:names[kind] for kind in sorted(names)}
    references[binding['target']]=binding['target_alias']
    expected_imports=scoped_imports.imports(references)
    if binding['imports']!=expected_imports:raise ValueError('V5材料不能增加导入或改变来源')
    return signature


def header(signature,binding,token,cls):
    signature=checked_binding(signature,binding,token);local_name(cls)
    types=signature.get('types',{});type_names=binding['type_names']
    reserved={ref.split('.')[0] for ref in (*type_names.values(),binding['target_alias'])}|{cls}
    reserved.update(p['name'] for p in signature['params'])
    for definition in types.values():
        reserved.update(f['name'] for f in definition['fields'])
        reserved.update(m['name'] for m in definition['methods'])
    allocate=lambda stem:fresh(stem+'_'+token,reserved)
    output=allocate('__nexusPrint');target=allocate('__nexusBound');encoder=allocate('__nexusEncode')
    cj_type=lambda kind:type_names.get(kind,kind)
    source=NL.join(['package '+binding['package'],*binding['imports'],'import std.core.println as '+output,
        'import std.unittest.*','import std.unittest.testmacro.*',
        'private let '+target+': ('+', '.join(cj_type(p['type']) for p in signature['params'])+') -> '+cj_type(signature['return_type'])+' = '+binding['target_alias'],''])
    constructors={}
    for i,kind in enumerate(sorted(type_names)):
        factory=allocate('__nexusCtor'+str(i));constructors[kind]=factory;fields=types[kind]['fields']
        params=[allocate('__nexusCtorArg'+str(i)+'_'+str(j)) for j in range(len(fields))]
        source+='private func '+factory+'('+', '.join(p+': '+f['type'] for p,f in zip(params,fields))+'): '+cj_type(kind)+' { return '+cj_type(kind)+'('+', '.join(params)+') }'+NL
    returned=signature['return_type']
    if returned in types:
        fields=types[returned]['fields'];string_encoder=allocate('__nexusString');array_encoder=allocate('__nexusArray')
        if any(f['type']=='String' for f in fields):source+=string_trace.encoder_method(string_encoder)
        if any(f['type']=='Array<Int64>' for f in fields):source+=array_trace.encoder_method(array_encoder)
        variable=allocate('__nexusObject');result=allocate('__nexusWire')
        source+='private func '+encoder+'('+variable+': '+cj_type(returned)+'): String {'+NL+'var '+result+' = "o:'+returned+':'+str(len(fields))+':"'+NL
        for i,field in enumerate(fields):
            part=allocate('__nexusField'+str(i));access=variable+'.'+field['name']
            leaf_encoder=string_encoder if field['type']=='String' else array_encoder
            source+='let '+part+' = "${'+array_trace.wire(field['type'],access,leaf_encoder)+'}"'+NL
            source+=result+' = '+result+' + "${'+part+'.size}:" + '+part+NL
        source+='return '+result+NL+'}'+NL
    elif returned=='String':source+=string_trace.encoder_method(encoder)
    elif returned=='Array<Int64>':source+=array_trace.encoder_method(encoder)
    source+='@Test'+NL+'class '+cls+' {'+NL
    return dict(source=source,output=output,target=target,encoder=encoder,constructors=constructors,
        types=types,cj_types=type_names,reserved=reserved)


def input_literal(value,kind,parts):
    value=values.primitive(value,kind,parts['types'])
    if type(value) is dict:
        text=literal(value,parts['types'])
        return parts['constructors'][kind]+text[len(kind):]
    return literal(value)


def wire(kind,variable,parts):
    return variable if kind in ('Int64','Bool') else parts['encoder']+'('+variable+')'


def limit_guard(kind,variable,parts,token,identity):
    types=parts['types']
    if kind in types:
        checks=[(variable+'.'+f['name'],16 if f['type']=='Array<Int64>' else 256) for f in types[kind]['fields'] if f['type'] in ('Array<Int64>','String')]
    else:checks=[(variable,16 if kind=='Array<Int64>' else 256)] if kind in ('Array<Int64>','String') else []
    return ''.join('if ('+access+'.size > '+str(limit)+') {'+NL+parts['output']+'("'+scoped_values.ERROR+token+'|'+identity+'|VALUE_LIMIT")'+NL+'return'+NL+'}'+NL for access,limit in checks)
