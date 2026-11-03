"""Fixed SDK dependency scans for an already admitted scoped project.

Original byte streams are returned for immutable recording by the verifier.
An SDK JSON envelope alone never establishes successful compilation or tests.
"""
import asyncio
import hashlib
import math
import os
from pathlib import Path
import signal
import time

from nexus.adapters.cangjie.sdk import SDK,sdk_environment
from nexus.adapters.cangjie.scoped_reports import dependencies,MAX_BYTES
from nexus.contracts import digest,source_manifest
from nexus.execution.runner import _workspace_paths,execution_profile
from nexus.projects.names import package_name


def tool_identity():
    return {name:hashlib.sha256((SDK/name).read_bytes()).hexdigest()
            for name in ('bin/cjc','bin/cjc-frontend','tools/bin/cjpm')}


def _snapshot(project):
    """Already admitted inputs plus at most bridge/harness, not upload admission.

    Original admission remains 100 files/2MiB. Trusted observation literals can
    expand escaped UTF-8; this internal snapshot has its own finite 102/8MiB cap.
    """
    files=[]
    for directory,dirs,names in os.walk(project,followlinks=False):
        current=Path(directory)
        if current==project:dirs[:]=[d for d in dirs if d not in ('target','.git')]
        for name in dirs:
            if (current/name).is_symlink():raise ValueError('Linked source directory')
        for name in names:
            path=current/name
            if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1:
                raise ValueError('Linked or nonregular source')
            files.append(path)
            if len(files)>102 or path.stat().st_size>8*1024*1024:
                raise ValueError('Source snapshot exceeds project bounds')
    if sum(p.stat().st_size for p in files)>8*1024*1024:
        raise ValueError('Source snapshot exceeds project bounds')
    return source_manifest(project)


async def _scan_process(project,directory,*,deadline,private_root,output_limit):
    """Only cjc --scan-dependency, in the existing compilation sandbox."""
    process=None;tasks=[];streams=[bytearray(),bytearray()];code=None;problem=None
    argv=[str(SDK/'bin/cjc'),'--scan-dependency','-p',str(directory)]
    profile_hash=None
    try:
        project,target,temporary,home=_workspace_paths(project)
        for path in (target,temporary,home):path.mkdir(exist_ok=True)
        profile=execution_profile(project,phase='compile',private_root=private_root)
        profile_hash=hashlib.sha256(profile.encode()).hexdigest()
        environment={**sdk_environment(),'HOME':str(home),'TMPDIR':str(temporary)}
        remaining=deadline-time.monotonic()
        if remaining<=0:raise asyncio.TimeoutError()
        process=await asyncio.create_subprocess_exec('/usr/bin/sandbox-exec','-p',profile,*argv,
            cwd=project,env=environment,stdin=asyncio.subprocess.DEVNULL,close_fds=True,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,start_new_session=True)
        async def collect(reader,output):
            while chunk:=await reader.read(8192):
                if sum(map(len,streams))+len(chunk)>output_limit:raise OverflowError('OUTPUT_LIMIT')
                output.extend(chunk)
        tasks=[asyncio.create_task(collect(process.stdout,streams[0])),
               asyncio.create_task(collect(process.stderr,streams[1]))]
        async def finish():
            await asyncio.gather(*tasks)
            return await process.wait()
        code=await asyncio.wait_for(finish(),remaining)
    except (OSError,ValueError,asyncio.TimeoutError,OverflowError) as exc:
        problem=type(exc).__name__
    finally:
        if process is not None:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            await process.wait()
        for task in tasks:
            if not task.done():task.cancel()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
    return dict(exit_code=code,problem=problem,stdout=bytes(streams[0]),stderr=bytes(streams[1]),
                argv=argv,profile_sha256=profile_hash)


def _packages(project,index):
    if (type(index) is not dict or type(index.get('version')) is not int or index['version']!=2 or
            type(index.get('packages')) is not dict or not 1<=len(index['packages'])<=16):
        raise ValueError('Scoped index required')
    root=package_name(index['package']);graph=index['dependency_graph']
    if '.' in root or index.get('graph_hash')!=digest(graph) or set(graph['packages'])!=set(index['packages']):
        raise ValueError('Frozen dependency graph identity changed')
    result=[]
    for name,info in sorted(index['packages'].items()):
        package_name(name)
        if name!=root and not name.startswith(root+'.'):raise ValueError('Foreign package')
        relative='/'.join(['src',*name.split('.')[1:]])
        if info['directory']!=relative:raise ValueError('Package directory changed')
        directory=project/relative
        if directory.is_symlink() or not directory.is_dir() or directory.resolve()!=directory:
            raise ValueError('Invalid package directory')
        paths=info['production_paths']
        actual=sorted(p.relative_to(project).as_posix() for p in directory.glob('*.cj') if not p.name.endswith('_test.cj'))
        if type(paths) is not list or sorted(paths)!=actual or len(set(paths))!=len(paths):
            raise ValueError('Package source collection changed')
        if paths:result.append((name,directory))
    actual={p.relative_to(project).as_posix() for p in (project/'src').rglob('*.cj') if not p.name.endswith('_test.cj')}
    frozen={p for info in index['packages'].values() for p in info['production_paths']}
    if actual!=frozen:raise ValueError('Unindexed production package')
    if not result:raise ValueError('No production packages')
    return result


async def scan(project:Path,index:dict,*,deadline:float,private_root:Path)->dict:
    result=dict(state='UNKNOWN',source_before={},source_after={},tool_before={},tool_after={},scans=[],diagnostics='')
    try:
        if type(deadline) not in (int,float) or not math.isfinite(deadline) or deadline<=time.monotonic():
            raise ValueError('REQUEST_DEADLINE_EXCEEDED')
        project,*_=_workspace_paths(Path(project))
        # Validate controller-read exclusions even when a transport fixture is used.
        execution_profile(project,phase='compile',private_root=Path(private_root))
        result['source_before']=_snapshot(project);result['tool_before']=tool_identity()
        packages=_packages(project,index);remaining=MAX_BYTES
        for package,directory in packages:
            if deadline<=time.monotonic():raise ValueError('REQUEST_DEADLINE_EXCEEDED')
            item=await _scan_process(project,directory,deadline=deadline,private_root=private_root,output_limit=remaining)
            for key in ('stdout','stderr'):
                if type(item.get(key)) is not bytes:raise ValueError('Scanner original bytes missing')
            item={**item,'package':package,'stdout_sha256':hashlib.sha256(item['stdout']).hexdigest(),
                  'stderr_sha256':hashlib.sha256(item['stderr']).hexdigest()}
            result['scans'].append(item)
            remaining-=len(item['stdout'])+len(item['stderr'])
            if remaining<0:raise ValueError('Scanner originals exceed 2MiB')
            if item['problem'] or type(item['exit_code']) is not int or item['exit_code']!=0:
                raise ValueError('SDK_DEPENDENCY_SCAN_FAILED')
            item['parsed']=dependencies(item['stdout'],package=package,source_root=project,graph=index['dependency_graph'])
            if item['parsed']['state']!='PASS':raise ValueError(item['parsed']['diagnostics'])
        result['source_after']=_snapshot(project);result['tool_after']=tool_identity()
        if result['source_after']!=result['source_before']:raise ValueError('SOURCE_CHANGED')
        if result['tool_after']!=result['tool_before']:raise ValueError('TOOLCHAIN_CHANGED')
        if deadline<=time.monotonic():raise ValueError('REQUEST_DEADLINE_EXCEEDED')
        result['state']='PASS'
    except (ValueError,OSError,TypeError,KeyError,OverflowError,RecursionError) as exc:
        result['diagnostics']=str(exc)
    return result


async def run_scoped_tests(project:Path,*,expected:list[str],deadline:float,private_root:Path,
                           output_limit:int=MAX_BYTES)->dict:
    """Budget is the remainder after scans; all originals share one 2MiB cap."""
    from nexus.execution.runner import run_scoped_command
    from nexus.adapters.cangjie.scoped_reports import tests
    result=dict(parsed=dict(state='UNKNOWN',counts={},case_results={},failures={},diagnostics=''),
        expected=list(expected) if type(expected) is list else [],
        source_before={},source_after={},tool_before={},tool_after={},reports={},report_hashes={},
        stdout=b'',stdout_sha256=hashlib.sha256(b'').hexdigest(),binary_before={},binary_after={},
        execution_argv=[],profiles=[],report_directory=None,exit_code=None,problem=None)
    try:
        if (type(output_limit) is not int or not 1<=output_limit<=MAX_BYTES or
                type(deadline) not in (int,float) or not math.isfinite(deadline) or deadline<=time.monotonic()):
            raise ValueError('Invalid scoped execution budget')
        # Validate the frozen case collection before any candidate execution.
        from nexus.adapters.cangjie.scoped_reports import _case_id
        if type(expected) is not list or not 1<=len(expected)<=288 or len(set(expected))!=len(expected):
            raise ValueError('Invalid frozen XML case collection')
        for identity in expected:_case_id(identity)
        project,*_=_workspace_paths(Path(project))
        result['source_before']=_snapshot(project);result['tool_before']=tool_identity()
        result.update(await run_scoped_command(project,deadline=deadline,private_root=private_root,output_limit=output_limit))
        result['stdout_sha256']=hashlib.sha256(result['stdout']).hexdigest()
        result['report_hashes']={name:hashlib.sha256(raw).hexdigest() for name,raw in result['reports'].items()}
        result['source_after']=_snapshot(project);result['tool_after']=tool_identity()
        if result['source_before']!=result['source_after']:raise ValueError('SOURCE_CHANGED')
        if result['tool_before']!=result['tool_after']:raise ValueError('TOOLCHAIN_CHANGED')
        if result['problem']:raise ValueError(result['problem'])
        if deadline<=time.monotonic():raise ValueError('REQUEST_DEADLINE_EXCEEDED')
        result['parsed']=tests(result['reports'],expected=expected,
            stdout=result['stdout'].decode('utf-8',errors='strict'),exit_code=result['exit_code'])
    except (OSError,ValueError,TypeError,KeyError,UnicodeError,OverflowError,RecursionError) as exc:
        result['problem']=str(exc)
        result['parsed']['diagnostics']=str(exc)
    return result
