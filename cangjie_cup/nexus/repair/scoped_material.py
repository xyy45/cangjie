"""Derive a private verification copy; never writes the uploaded candidate.

The caller supplies the original project manifest's current candidate bytes.
Generated files/bindings are verification artifacts, not model-editable sources.
"""
from copy import deepcopy
import hashlib
from pathlib import PurePosixPath
import re
import unicodedata

from nexus.contracts import digest
from nexus.projects.archive import read_entries
from nexus.projects.index import inspect_project
from nexus.projects.names import fresh_name as fresh
from nexus.repair import scoped_imports
from nexus.repair.scoped_signature import validate
from nexus.uploads.language import tokens


def nonce(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{16}',value):
        raise ValueError('Scoped验证nonce必须为16位小写十六进制')
    return value


def _manifest(files):
    return {p:hashlib.sha256(raw).hexdigest() for p,raw in sorted(files.items())}


def material(files,signature,token):
    token=nonce(token);signature=validate(signature);files=read_entries(files)
    index=inspect_project(files)
    if index['version']!=2:raise ValueError('Scoped验证材料须来自真实跨包索引2')
    selected=next((f for f in index['functions'] if f['name']==signature['name']),None)
    if selected is None or validate(selected)!=signature:
        raise ValueError('Scoped签名与冻结工程重建不一致')
    production={p:raw for p,raw in files.items() if not p.endswith('_test.cj')}
    reserved={value for path in index['production_paths'] for value,_ in tokens(files[path].decode())}
    needed=sorted({p['type'] for p in signature['params']}|{signature['return_type']})
    needed=[kind for kind in needed if kind in signature.get('types',{})]
    target=signature['name'];bridge_path=None;derived={};private=not selected['public']
    if private:
        scope=signature['scope'];package=scope['package']
        bridge=fresh('__nexusBridge_'+token,reserved);target=package+'.'+bridge
        external=[(kind,'__NexusBridgeType'+str(i)+'_'+token) for i,kind in enumerate(needed) if kind.rsplit('.',1)[0]!=package]
        bridge_types,imports=scoped_imports.references(external,reserved)
        bridge_types.update({kind:kind.rsplit('.',1)[-1] for kind in needed if kind.rsplit('.',1)[0]==package})
        params=[fresh('__nexusArg'+str(i)+'_'+token,reserved) for i in range(len(signature['params']))]
        cj_type=lambda kind:bridge_types.get(kind,kind)
        source='\n'.join(['package '+package,*imports,
            'public func '+bridge+'('+', '.join(a+': '+cj_type(p['type']) for a,p in zip(params,signature['params']))+'): '+cj_type(signature['return_type'])+' {',
            'return '+scope['local_name']+'('+', '.join(params)+')','}','']).encode()
        directory=str(PurePosixPath(scope['path']).parent)
        existing={unicodedata.normalize('NFC',p).casefold() for p in files}
        for number in range(len(files)+1):
            path=directory+'/nexus_verify_bridge_'+token+('_'+format(number,'x') if number else '')+'.cj'
            if path.casefold() not in existing:bridge_path=path;break
        if bridge_path is None:raise ValueError('无法分配验证桥接路径')
        derived[bridge_path]=source
    symbols=[(kind,'__NexusType'+str(i)+'_'+token) for i,kind in enumerate(needed)]+[(target,'__nexusImported_'+token)]
    refs,imports=scoped_imports.references(symbols,reserved)
    type_names={kind:refs[kind] for kind in needed};target_alias=refs[target]
    binding=dict(version=1,nonce=token,package=index['package']+'.nexus_verify_'+token,
        signature_hash=digest(signature),source_tree_hash=digest(index['manifest']),graph_hash=index['graph_hash'],
        private=private,target=target,target_alias=target_alias,type_names=type_names,imports=imports,
        bridge_path=bridge_path,bridge_sha256=hashlib.sha256(derived[bridge_path]).hexdigest() if bridge_path else None)
    return dict(files={**production,**derived},signature=deepcopy(signature),binding=binding,
        original_manifest=deepcopy(index['manifest']),production_manifest=_manifest(production),
        derived_manifest=_manifest(derived),derivation_hash=digest(binding))
