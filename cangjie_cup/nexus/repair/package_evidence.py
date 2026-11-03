"""Immutable scoped originals and read-only reconstruction of their meaning.

The caller supplies the freshly source-bound index, expected cases and current
tool identities. Metadata inside the saved envelope does not grant authority.
"""
from copy import deepcopy
import hashlib
import os
from pathlib import Path,PurePosixPath
import re
import stat
import uuid

from nexus.adapters.cangjie import scoped_reports
from nexus.adapters.cangjie.sdk import SDK
from nexus.contracts import digest
from nexus.execution.package_validation import _snapshot,_packages
from nexus.execution.runner import execution_profile

PARSER='SCOPED_SDK_XML_V1'
HEX=re.compile(r'[0-9a-f]{64}')


def subject_context(store,task,subject_id):
    """Resolve ownership and rebuild the index from frozen original input paths."""
    if task.schema_version!=2:return None
    from nexus.requirements.service import RequirementService
    from nexus.uploads.service import UploadService
    from nexus.execution.workspace import WorkspaceStore
    from nexus.projects.index import inspect_project
    spec,plan=RequirementService(store).task_context(task)
    if not spec.project_id.startswith('upload_'):return None
    uploads=UploadService(store);value=uploads._read(spec.project_id)
    if value.get('kind')!='PROJECT' or value['project_index']['version']!=2:return None
    ws=WorkspaceStore(store.root)
    if subject_id==task.baseline_id:project=ws.verify_baseline(subject_id)
    else:
        if ws.candidate(subject_id).task_id!=task.id:raise ValueError('Foreign scoped candidate')
        project=ws.subject_path(subject_id)
    uploads.validate_subject(task,project)
    index=inspect_project({name:(project/name).read_bytes() for name in value['project_index']['manifest']})
    if index['graph_hash']!=value['project_index']['graph_hash']:raise ValueError('Scoped graph changed')
    expected=sorted({case for cases in plan.suite_tests.values() for case in cases})
    if not expected or not {case['id'] for case in index['test_cases']}<=set(expected):
        raise ValueError('Original scoped cases missing from frozen plan')
    return dict(project=project,index=index,expected=expected,plan=plan)


def component_identity(index):
    app=Path(__file__).resolve().parents[2]
    names={'nexus/contracts.py','nexus/uploads/language.py','nexus/uploads/object_types.py',
        'nexus/uploads/public_tests.py','nexus/uploads/scoped_public_tests.py','nexus/uploads/scoped_project.py',
        'nexus/execution/package_validation.py','nexus/execution/runner.py',
        'nexus/adapters/cangjie/scoped_reports.py','nexus/repair/package_evidence.py'}
    names.update(p.relative_to(app).as_posix() for folder in ('nexus/projects','nexus/repair')
                 for p in (app/folder).glob('scoped*.py'))
    names.update('nexus/projects/'+name+'.py' for name in ('index','names','scopes'))
    return dict(index_hash=digest(index),graph_hash=index['graph_hash'],
        sources={name:hashlib.sha256((app/name).read_bytes()).hexdigest() for name in sorted(names)})


def _records(root):
    root=Path(root)
    if root.is_symlink() or not root.is_dir() or root.resolve()!=root:raise ValueError('Invalid evidence root')
    directory=root/'records'
    if directory.is_symlink() or not directory.is_dir() or directory.resolve()!=directory:
        raise ValueError('Invalid original record directory')
    return directory


def _write(root,raw,suffix):
    if type(raw) is not bytes or len(raw)>scoped_reports.MAX_BYTES:raise ValueError('Invalid original bytes')
    path=_records(root)/(uuid.uuid4().hex+'.'+suffix)
    with path.open('xb') as stream:stream.write(raw)
    return dict(ref='records/'+path.name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))


def capture(root:Path,*,project:Path,index:dict,scanned:dict,execution:dict|None=None)->dict:
    """Append originals, even failed/unknown ones; never rewrite prior evidence."""
    root=Path(root).absolute();project=Path(project).absolute();_records(root)
    proof=dict(version=1,parser=PARSER,working_root=str(project),private_root=str(root),
        graph_hash=index['graph_hash'],index_hash=digest(index),
        input_manifest=deepcopy(scanned['source_before']),source_after_scan=deepcopy(scanned['source_after']),
        tools=deepcopy(scanned['tool_before']),tools_after_scan=deepcopy(scanned['tool_after']),
        scan_state=scanned['state'],scan_diagnostics=scanned['diagnostics'],scans=[],expected=[],test=None)
    for item in scanned['scans']:
        proof['scans'].append({key:deepcopy(item.get(key)) for key in
            ('package','argv','profile_sha256','exit_code','problem')})
        proof['scans'][-1].update(stdout=_write(root,item['stdout'],'scan'),stderr=_write(root,item['stderr'],'stderr'))
    if execution is not None:
        proof['expected']=deepcopy(execution['expected'])
        proof['test']={key:deepcopy(execution.get(key)) for key in
            ('source_before','source_after','tool_before','tool_after','exit_code','problem',
             'execution_argv','binary_before','binary_after','profiles','report_directory')}
        proof['test'].update(stdout=_write(root,execution['stdout'],'log'),
            reports={name:_write(root,raw,'xml') for name,raw in sorted(execution['reports'].items())})
    return proof


def rebuild(root:Path,*,project:Path,index:dict,evidence:dict,expected:list[str]|None,tools:dict)->dict:
    """Re-read every referenced original for PASS *and* FAIL; no SDK reruns."""
    unknown=dict(state='UNKNOWN',counts={},case_results={},failures={},diagnostics='')
    used=0;refs=set()
    try:
        root=Path(root);project=Path(project);directory=_records(root)
        def original(item):
            nonlocal used
            if type(item) is not dict or set(item)!={'ref','sha256','bytes'}:raise ValueError('Invalid original binding')
            reference=PurePosixPath(item['ref'])
            if (type(item['ref']) is not str or reference.as_posix()!=item['ref'] or
                    len(reference.parts)!=2 or reference.parts[0]!='records' or
                    not re.fullmatch(r'[0-9a-f]{32}\.(scan|stderr|log|xml)',reference.name) or
                    type(item['sha256']) is not str or not HEX.fullmatch(item['sha256']) or
                    type(item['bytes']) is not int or not 0<=item['bytes']<=scoped_reports.MAX_BYTES or item['ref'] in refs):
                raise ValueError('Invalid or reused original reference')
            refs.add(item['ref']);path=directory/reference.name
            descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(descriptor,'rb') as stream:
                before=os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=item['bytes']:
                    raise ValueError('Linked or changed original')
                raw=stream.read(scoped_reports.MAX_BYTES-used+1)
                after=os.fstat(stream.fileno())
            identity=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            used+=len(raw)
            if (used>scoped_reports.MAX_BYTES or len(raw)!=item['bytes'] or identity(before)!=identity(after) or
                    path.is_symlink() or identity(path.stat())!=identity(after) or hashlib.sha256(raw).hexdigest()!=item['sha256']):
                raise ValueError('Original bytes/hash changed')
            return raw
        if (type(evidence) is not dict or set(evidence)!={'version','parser','working_root','private_root','graph_hash','index_hash',
                'input_manifest','source_after_scan','tools','tools_after_scan','scan_state','scan_diagnostics','scans','expected','test'} or
                type(evidence['version']) is not int or evidence['version']!=1 or evidence['parser']!=PARSER or
                evidence['working_root']!=str(project) or evidence['private_root']!=str(root) or
                evidence['graph_hash']!=index['graph_hash'] or evidence['index_hash']!=digest(index)):
            raise ValueError('Scoped evidence ownership or parser binding changed')
        manifest=_snapshot(project)
        if (evidence['input_manifest']!=manifest or evidence['source_after_scan']!=manifest or
                evidence['tools']!=tools or evidence['tools_after_scan']!=tools or
                evidence['scan_state']!='PASS' or evidence['scan_diagnostics']!=''):
            raise ValueError('Source or toolchain binding changed')
        packages=dict(_packages(project,index));scans=evidence['scans']
        if type(scans) is not list or len(scans)!=len(packages):raise ValueError('Incomplete scans')
        seen=set();profile=execution_profile(project,phase='compile',private_root=root)
        for item in scans:
            if type(item) is not dict or set(item)!={'package','argv','profile_sha256','exit_code','problem','stdout','stderr'}:
                raise ValueError('Invalid scan binding')
            name=item['package']
            if name not in packages or name in seen:raise ValueError('Foreign or duplicate scan')
            seen.add(name)
            if (item['argv']!=[str(SDK/'bin/cjc'),'--scan-dependency','-p',str(packages[name])] or
                    type(item['exit_code']) is not int or item['exit_code']!=0 or item['problem'] is not None or
                    item['profile_sha256']!=hashlib.sha256(profile.encode()).hexdigest()):
                raise ValueError('SDK scan execution identity changed')
            raw=original(item['stdout']);original(item['stderr'])
            parsed=scoped_reports.dependencies(raw,package=name,source_root=project,graph=index['dependency_graph'])
            if parsed['state']!='PASS':raise ValueError(parsed['diagnostics'])
        if expected is None:
            if evidence['test'] is not None or evidence['expected']!=[]:raise ValueError('Build has foreign test evidence')
            return dict(state='PASS',counts={},case_results={},failures={},diagnostics='')
        execution=evidence['test']
        if type(execution) is not dict or evidence['expected']!=expected:raise ValueError('Frozen XML case collection changed')
        if set(execution)!={'source_before','source_after','tool_before','tool_after','exit_code','problem','execution_argv',
                'binary_before','binary_after','profiles','report_directory','stdout','reports'}:
            raise ValueError('Invalid test evidence')
        if (execution['source_before']!=manifest or execution['source_after']!=manifest or
                execution['tool_before']!=tools or execution['tool_after']!=tools or execution['problem'] is not None):
            raise ValueError('Test input or tool identity changed')
        binary=execution['binary_before']
        if type(binary) is not dict or not binary or len(binary)>17 or binary!=execution['binary_after']:
            raise ValueError('Compiled binaries changed')
        executables=[]
        for name,identity in sorted(binary.items()):
            path=PurePosixPath(name)
            if (path.as_posix()!=name or path.parts[:3]!=('target','release','unittest_bin') or len(path.parts)!=4 or
                    path.name in ('.','..') or type(identity) is not str or not HEX.fullmatch(identity)):
                raise ValueError('Invalid compiled binary binding')
            executables.append(project/name)
        relative=execution['report_directory']
        if type(relative) is not str or not re.fullmatch(r'target/\.runner-tmp/xml-[0-9a-f]{32}',relative):
            raise ValueError('Invalid XML execution path')
        if execution['execution_argv']!=[['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output',
                '--report-path',str(project/relative),'--report-format','xml']]:
            raise ValueError('SDK XML execution argv changed')
        profiles=[dict(phase=phase,sha256=hashlib.sha256(execution_profile(project,phase=phase,
            executables=executables if phase=='test' else (),private_root=root).encode()).hexdigest()) for phase in ('compile','test')]
        if profiles!=execution['profiles']:raise ValueError('SDK sandbox identity changed')
        if type(execution['reports']) is not dict or len(execution['reports'])>257:raise ValueError('Invalid XML collection')
        reports={name:original(item) for name,item in execution['reports'].items()}
        stdout=original(execution['stdout']).decode('utf-8',errors='strict')
        return scoped_reports.tests(reports,expected=expected,stdout=stdout,exit_code=execution['exit_code'])
    except (OSError,ValueError,TypeError,KeyError,UnicodeError,OverflowError,RecursionError) as exc:
        return {**unknown,'diagnostics':str(exc)}


def checked_record(store,record,*,context,plan=None):
    """Bind the SQLite record, saved report, main log and scoped originals."""
    unknown=dict(state='UNKNOWN',counts={},case_results={},failures={},diagnostics='')
    try:
        from nexus.contracts import CheckResult
        from nexus.policy.core import strict_json
        from nexus.execution.package_validation import tool_identity
        from nexus.adapters.cangjie.report_parser import project_suites
        if context is None:raise ValueError('Scoped record has no source-bound context')
        directory=_records(store.root)
        def saved(reference):
            path=PurePosixPath(reference)
            if (type(reference) is not str or path.as_posix()!=reference or len(path.parts)!=2 or
                    path.parts[0]!='records' or path.name in ('.','..')):raise ValueError('Invalid check record reference')
            target=directory/path.name
            descriptor=os.open(target,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(descriptor,'rb') as stream:
                before=os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>scoped_reports.MAX_BYTES:
                    raise ValueError('Invalid saved check original')
                raw=stream.read(scoped_reports.MAX_BYTES+1);after=os.fstat(stream.fileno())
            identity=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            if (len(raw)>scoped_reports.MAX_BYTES or identity(before)!=identity(after) or target.is_symlink() or
                    identity(target.stat())!=identity(after)):raise ValueError('Saved check original changed')
            return raw
        model=CheckResult.model_validate(record);proof=model.package_evidence
        if proof is None or digest(model.model_dump())!=digest(record):raise ValueError('Invalid scoped check schema')
        if digest(strict_json(saved(model.report_ref)))!=digest(record):raise ValueError('Saved check report changed')
        log=saved(model.log_ref);text=log.decode('utf-8',errors='strict');tools=tool_identity()
        if (model.working_root!='.' or model.tree_hash!=digest(_snapshot(context['project'])) or
                model.toolchain_hash!=digest({'cjc':tools['bin/cjc'],'cjpm':tools['tools/bin/cjpm']})):
            raise ValueError('Check source/tool ownership changed')
        parsed=rebuild(store.root,project=context['project'],index=context['index'],evidence=proof,
                       expected=context['expected'] if model.kind=='test' else None,tools=tools)
        if model.kind=='test':
            test=proof['test']
            if (test is None or hashlib.sha256(log).hexdigest()!=test['stdout']['sha256'] or len(log)!=test['stdout']['bytes'] or
                    model.exit_code!=test['exit_code'] or model.argv!=['cjpm','test'] or
                    model.execution_argv!=test['execution_argv'] or model.state!=parsed['state'] or
                    model.counts!=parsed['counts'] or model.case_results!=parsed['case_results'] or
                    model.diagnostics!=text[-16000:]):
                raise ValueError('Scoped XML, log and check result differ')
            if plan is not None:
                suites=project_suites(model,plan.suite_tests)
                if suites!=model.suite_results:raise ValueError('Scoped suites changed')
                if model.state=='PASS' and any(suites.get(s,{}).get('state')!='PASS' for s in plan.required_suites):
                    raise ValueError('Required scoped suites incomplete')
        else:
            if (parsed['state']!='PASS' or model.argv!=['cjpm','build','-V'] or
                    model.execution_argv!=[['cjpm','build','-V']] or model.diagnostics!=text[-16000:]):
                raise ValueError('Scoped build prerequisites changed')
            state=('PASS' if model.exit_code==0 and 'cjpm build success' in text else
                   'FAIL' if type(model.exit_code) is int and model.exit_code>0 and 'error generated' in text and '.cj:' in text else 'UNKNOWN')
            if model.state!=state:raise ValueError('Scoped build output changed')
            parsed={**parsed,'state':state}
        return parsed
    except (OSError,ValueError,TypeError,KeyError,UnicodeError,OverflowError,RecursionError) as exc:
        return {**unknown,'diagnostics':str(exc)}
