"""Shared scoped execution/evidence adapter; existing search algorithms stay in services."""
import asyncio
from copy import deepcopy
from pathlib import Path
import re
import time

from nexus.contracts import digest,source_manifest
from nexus.repair.scoped_signature import validate
from nexus.repair.scoped_probe import prepare
from nexus.repair.package_evidence import subject_context,capture,rebuild
from nexus.execution import package_validation
from nexus.store import uid

FOLDERS={'oracle':'explorations','single':'properties','relation':'relations','sequence':'sequences'}
KEYS=('binding','original_graph_hash','original_manifest','production_manifest','derived_manifest',
      'derivation_hash','harness_path','harness_sha256','case_ids')


def signature(store,task,candidate_id,contract):
    context=subject_context(store,task,candidate_id)
    if context is None:raise ValueError('Scoped service has no source-bound project')
    selected=next((f for f in context['index']['functions'] if f['name']==contract['function']),None)
    if selected is None or validate(selected)!=contract['signature']:raise ValueError('Frozen scoped contract differs from candidate signature')
    return validate(selected)


def materials(service,path,contract,candidate_id,token,mode,items):
    candidate=service.ws.candidate(candidate_id);task=service.store.get_task(candidate.task_id)
    context=subject_context(service.store,task,candidate_id)
    if context is None or context['project']!=path:raise ValueError('Scoped probe source ownership changed')
    checked=signature(service.store,task,candidate_id,contract)
    files={name:(path/name).read_bytes() for name in context['index']['manifest']}
    return prepare(files,checked,token,mode,items,contract=contract)


def _metadata(derived,mode):
    return dict(version=1,mode=mode,scan_index_hash=digest(derived['scan_index']),
                **{key:deepcopy(derived[key]) for key in KEYS})


async def batch(service,path,contract,items,deadline_at,label,report,*,mode,token,required_ids=None):
    original=source_manifest(path);derived=materials(service,path,contract,report['candidate_id'],token,mode,items)
    folder=FOLDERS[mode];project=service.store.root/folder/uid();project.mkdir(parents=True)
    for name,raw in derived['files'].items():
        dest=project/name;dest.parent.mkdir(exist_ok=True,parents=True);dest.write_bytes(raw);dest.chmod(0o644)
    harness=derived['files'][derived['harness_path']]
    h_ref,h_hash=service.write_record(harness,'.'+folder+'.cj');l_ref,l_hash=service.write_record(b'','.'+folder+'.log')
    derived_ref=derived_hash=None
    if derived['binding']['private']:
        derived_ref,derived_hash=service.write_record(derived['files'][derived['binding']['bridge_path']],'.scoped-derived.cj')
    key='traces' if mode=='sequence' else 'pairs' if mode=='relation' else 'inputs'
    row=dict(label=label,token=token,**{key:deepcopy(items)},exit_code=None,problem='BATCH_PENDING',execution_argv=[],
        project_path=project.relative_to(service.store.root).as_posix(),project_manifest=derived['manifest'],
        harness_ref=h_ref,harness_sha256=h_hash,log_ref=l_ref,log_sha256=l_hash,scoped=_metadata(derived,mode))
    if required_ids is not None:row['required_ids']=list(required_ids)
    row['scoped'].update(derived_source_ref=derived_ref,derived_source_sha256=derived_hash)
    report['batches'].append(row)
    service.store.append_record(report['binding']['task_id'],'event',dict(type='SCOPED_BATCH_STARTED',mode=mode,
        candidate_id=report['candidate_id'],index=len(report['batches'])-1,token=token,harness_ref=h_ref,
        project_path=row['project_path'],original_graph_hash=derived['original_graph_hash'],derived_graph_hash=derived['scan_index']['graph_hash'],derived_source_ref=derived_ref))
    scanned=dict(state='UNKNOWN',diagnostics='BATCH_NOT_SCANNED',source_before=derived['manifest'],source_after={},
                 tool_before={},tool_after={},scans=[])
    executed=None;raw=b''
    try:
        remaining=min(60,max(0,(deadline_at-int(time.time()*1000))/1000));deadline=time.monotonic()+remaining
        if remaining<=0:row['problem']='SEARCH_DEADLINE_EXCEEDED'
        else:
            scanned=await package_validation.scan(project,derived['scan_index'],deadline=deadline,private_root=service.store.root)
            if scanned['state']!='PASS':row['problem']=scanned['diagnostics'] or 'SCOPED_SCAN_INCOMPLETE'
            else:
                budget=2*1024*1024-sum(len(s['stdout'])+len(s['stderr']) for s in scanned['scans'])
                executed=await package_validation.run_scoped_tests(project,expected=derived['case_ids'],deadline=deadline,
                    private_root=service.store.root,output_limit=budget)
                raw=executed['stdout'];row.update(exit_code=executed['exit_code'],execution_argv=executed['execution_argv'])
                row['problem']=executed['problem'] or (None if executed['parsed']['state']=='PASS' else 'SCOPED_XML_INCOMPLETE')
    except asyncio.CancelledError:
        row['problem']='CANCELLED';raise
    finally:
        row['log_ref'],row['log_sha256']=service.write_record(raw,'.'+folder+'.log')
        row['scoped'].update(package_evidence=capture(service.store.root,project=project,index=derived['scan_index'],
            scanned=scanned,execution=executed),framework_state=executed['parsed']['state'] if executed else 'UNKNOWN')
        row['result']=service.string_interpret(row,contract) if mode=='oracle' else service.interpret_batch(row,contract)
    if source_manifest(project)!=derived['manifest'] or source_manifest(path)!=original:raise ValueError('Scoped probe changed candidate or derived sources')
    return row['result']


def verify(service,path,contract,row,candidate_id,*,mode,items,token):
    derived=materials(service,path,contract,candidate_id,token,mode,items)
    metadata=row.get('scoped')
    if (type(metadata) is not dict or set(metadata)!=set(_metadata(derived,mode))|{'package_evidence','framework_state','derived_source_ref','derived_source_sha256'} or
            any(metadata[key]!=value for key,value in _metadata(derived,mode).items())):
        raise ValueError('Scoped derivation metadata changed')
    if derived['binding']['private']:
        if service.read_record(metadata['derived_source_ref'],metadata['derived_source_sha256'])!=derived['files'][derived['binding']['bridge_path']]:
            raise ValueError('Scoped derived source original changed')
    elif metadata['derived_source_ref'] is not None or metadata['derived_source_sha256'] is not None:
        raise ValueError('Public scoped target has unexpected bridge original')
    relative=Path(row['project_path'])
    if (relative.is_absolute() or len(relative.parts)!=2 or relative.parts[0]!=FOLDERS[mode] or
            not re.fullmatch('[0-9a-f]{32}',relative.name)):raise ValueError('Scoped probe reference invalid')
    project=service.store.root/relative
    if project.is_symlink() or project.parent.is_symlink() or row['project_manifest']!=derived['manifest'] or source_manifest(project)!=derived['manifest']:
        raise ValueError('Scoped derived project changed')
    harness=service.read_record(row['harness_ref'],row['harness_sha256'])
    if harness!=derived['files'][derived['harness_path']]:raise ValueError('Scoped harness original changed')
    raw=service.read_record(row['log_ref'],row['log_sha256']);proof=metadata['package_evidence']
    rebuilt=rebuild(service.store.root,project=project,index=derived['scan_index'],evidence=proof,
                    expected=derived['case_ids'],tools=package_validation.tool_identity())
    if rebuilt['state']!=metadata['framework_state']:raise ValueError('Scoped XML evidence changed')
    executed=proof['test']
    if executed is not None:
        if (executed['stdout']['sha256']!=row['log_sha256'] or executed['stdout']['bytes']!=len(raw) or
                executed['execution_argv']!=row['execution_argv'] or executed['exit_code']!=row['exit_code']):
            raise ValueError('Scoped observation/log binding changed')
    elif raw or row['execution_argv'] or row['exit_code'] is not None:raise ValueError('Unexecuted scoped probe has observations')
    if rebuilt['state']=='PASS' and row['problem'] is not None or rebuilt['state']!='PASS' and row['problem'] is None:
        raise ValueError('Scoped framework status differs')
