"""Four-model derived probe materials, distinct from the candidate/original graph.

The service caller must rederive the signature from its frozen uploaded source.
This module never writes the candidate or synthesizes missing namespace files.
"""
from copy import deepcopy
import hashlib
from nexus.contracts import digest
from nexus.projects.index import inspect_project
from nexus.projects.scopes import build_scopes
from nexus.repair.scoped_signature import validate
from nexus.repair.scoped_material import material
from nexus.repair import oracle,properties,relations,sequences,property_trace,relation_trace,scoped_trace,scoped_sequence


def prepare(files,signature,token,mode,items,*,contract):
    signature=validate(signature)
    if (type(contract) is not dict or contract.get('signature')!=signature or
            mode not in ('oracle','single','relation','sequence') or
            type(contract.get('version')) is not int or contract['version']!=(6 if mode=='oracle' else 5)):
        raise ValueError('Scoped probe requires matching frozen contract and signature')
    original=inspect_project(files);derived=material(files,signature,token);binding=derived['binding']
    if mode=='sequence':
        # _traces/reference execution also validates reserved inputs and bounds.
        from nexus.repair.sequence_trace import _traces
        _traces(contract,items)
        rendered=scoped_sequence.render(signature,items,nonce=token,binding=binding,contract=contract)
    else:
        flat=relation_trace.flatten(items) if mode=='relation' else items
        sampler=contract if mode=='oracle' else properties.sampler(contract) if mode=='single' else relations.sampler(contract)
        if any(not oracle.permitted_input(sampler,args) for args in flat):raise ValueError('Probe contains reserved inputs')
        if mode=='oracle':
            for args in flat:oracle.expected(contract,args)
        rendered=scoped_trace.render(signature,flat,nonce=token,mode=mode,binding=binding)
        if mode=='single':
            if property_trace.harness(contract,items,binding['package'],token,binding=binding)!=rendered['source']:
                raise ValueError('Property renderer disagreement')
        elif mode=='relation':
            if relation_trace.harness(contract,items,binding['package'],token,binding=binding)!=rendered['source']:
                raise ValueError('Relation renderer disagreement')
    # Build only a header graph for compiler scans, never a permissive typed index.
    # Original bodies were admitted above; the sole new production declaration is
    # the controller-owned bridge. The synthetic test leaf is not a user package.
    declarations=[]
    for function in original['functions']:
        declarations.append({key:deepcopy(function[key]) for key in ('name','local_name','package','path','public') }|{'kind':'function'})
    for name,path in original.get('type_paths',{}).items():
        package,local=name.rsplit('.',1)
        declarations.append(dict(name=name,local_name=local,package=package,path=path,public=True,kind='type'))
    if binding['private']:
        package,local=binding['target'].rsplit('.',1)
        declarations.append(dict(name=binding['target'],local_name=local,package=package,path=binding['bridge_path'],public=True,kind='function'))
    scopes=build_scopes(derived['files'],original['package'],declarations)
    scan_index=dict(version=2,package=original['package'],packages=scopes['packages'],
        graph_hash=scopes['graph_hash'],dependency_graph=scopes['dependency_graph'])
    output={**derived['files'],rendered['path']:rendered['source']}
    return dict(files=output,binding=deepcopy(binding),original_graph_hash=original['graph_hash'],scan_index=scan_index,
        original_manifest=deepcopy(derived['original_manifest']),production_manifest=deepcopy(derived['production_manifest']),
        derived_manifest=deepcopy(derived['derived_manifest']),derivation_hash=derived['derivation_hash'],
        harness_path=rendered['path'],harness_sha256=hashlib.sha256(rendered['source']).hexdigest(),
        case_ids=rendered['case_ids'],manifest={name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(output.items())})
