"""macOS restricted subprocess runner for registered demos, not arbitrary uploads."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import uuid

from nexus.adapters.cangjie.sdk import SDK, MACOS_SDK, sdk_environment


class UnsafeWorkspace(ValueError):
    pass


def _workspace_paths(project: Path):
    if project.is_symlink() or not project.is_dir():
        raise UnsafeWorkspace('Invalid project directory')
    root=project.resolve(strict=True)
    target=root/'target'
    temporary=target/'.runner-tmp'
    home=temporary/'home'
    for path in (target,temporary,home):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise UnsafeWorkspace('Output directories must remain inside the candidate without symlinks')
    return root,target,temporary,home


async def run_command(project: Path, argv: list[str], *, timeout: float = 90, output_limit: int = 2*1024*1024, private_root: Path | None = None, execution_argv: list[list[str]] | None = None, test_output: str = 'failures') -> tuple[int | None, str, str | None]:
    if argv not in (['cjpm', 'build', '-V'], ['cjpm', 'test']):
        raise ValueError('command is not permitted')
    if type(test_output) is not str or test_output not in ('failures','all') or test_output=='all' and argv!=['cjpm','test']:
        raise ValueError('test output mode is not permitted')
    output=''
    started=asyncio.get_running_loop().time()
    try:
        project,target,temporary,home=_workspace_paths(project)
        for path in (target,temporary,home):path.mkdir(exist_ok=True)
        env=sdk_environment()
        env.update(HOME=str(home),TMPDIR=str(temporary))
        compile_argv=argv if argv[1]=='build' else ['cjpm','test','--no-run']
        phases=[('compile',compile_argv)]
        if argv[1]=='test':phases.append(('test',['cjpm','test','--skip-build']+(['--show-all-output'] if test_output=='all' else [])))
        for phase,command in phases:
            executables=[]
            identities={}
            if phase=='test':
                directory=target/'release/unittest_bin'
                if directory.is_symlink() or not directory.resolve().is_relative_to(target):
                    raise UnsafeWorkspace('Invalid compiled test directory')
                for path in directory.iterdir():
                    if path.is_symlink():raise UnsafeWorkspace('Compiled test symlink')
                    if path.is_file() and os.access(path,os.X_OK):
                        with path.open('rb') as stream:
                            if stream.read(4)!=b'\xcf\xfa\xed\xfe':
                                raise UnsafeWorkspace('Expected pinned ARM64 Mach-O test executable')
                        if path.stat().st_nlink!=1:raise UnsafeWorkspace('Compiled test hardlink')
                        executables.append(path)
                        identities[path]=hashlib.sha256(path.read_bytes()).hexdigest()
                if not executables:raise UnsafeWorkspace('No compiled test executables')
            profile=execution_profile(project,phase=phase,executables=executables,private_root=private_root)
            marker='NEXUS_EXECUTION_PHASE '+phase+': '+json.dumps(command)+'\n'
            if len((output+marker).encode())>output_limit:
                return None,output,'OverflowError'
            output+=marker
            remaining=timeout-(asyncio.get_running_loop().time()-started)
            if remaining<=0:return None,output,'TimeoutError'
            if execution_argv is not None:execution_argv.append(list(command))
            code,log,problem=await _run_phase(project,command,profile,env,
                timeout=remaining,output_limit=output_limit-len(output.encode()))
            output+=log
            for path,identity in identities.items():
                if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=identity:
                    return None,output,'UnsafeWorkspace'
            if code!=0 or problem:return code,output,problem
        return code,output,None
    except (OSError,ValueError) as exc:
        return None,output,type(exc).__name__


async def _run_phase(project, argv, profile, env, *, timeout, output_limit):
    process = None
    output = bytearray()
    problem = None
    try:
        process = await asyncio.create_subprocess_exec('/usr/bin/sandbox-exec', '-p', profile, *argv,
            cwd=project, env=env, stdin=asyncio.subprocess.DEVNULL,close_fds=True,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            start_new_session=True)
        async def collect():
            while chunk := await process.stdout.read(8192):
                if len(output) + len(chunk) > output_limit:
                    raise OverflowError('OUTPUT_LIMIT')
                output.extend(chunk)
            return await process.wait()
        code = await asyncio.wait_for(collect(), timeout)
        return code, output.decode(errors='replace'), None
    except (OSError, ValueError, asyncio.TimeoutError, OverflowError) as exc:
        problem = type(exc).__name__
        return None, output.decode(errors='replace'), problem
    finally:
        if process is not None:
            # Descendants can outlive the parent; always reap the owned process group.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()


async def _run_original_phase(project,argv,profile,env,*,timeout,output_limit):
    """Preserve exact merged SDK bytes; only fixed internal phase callers."""
    process=None;output=bytearray()
    try:
        if timeout<=0:raise asyncio.TimeoutError()
        process=await asyncio.create_subprocess_exec('/usr/bin/sandbox-exec','-p',profile,*argv,
            cwd=project,env=env,stdin=asyncio.subprocess.DEVNULL,close_fds=True,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,start_new_session=True)
        async def collect():
            while chunk:=await process.stdout.read(8192):
                if len(output)+len(chunk)>output_limit:raise OverflowError('OUTPUT_LIMIT')
                output.extend(chunk)
            return await process.wait()
        code=await asyncio.wait_for(collect(),timeout)
        return code,bytes(output),None
    except (OSError,ValueError,asyncio.TimeoutError,OverflowError) as exc:
        return None,bytes(output),type(exc).__name__
    finally:
        if process is not None:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            await process.wait()


def _compiled_tests(target):
    directory=target/'release/unittest_bin'
    if directory.is_symlink() or directory.resolve()!=directory or not directory.is_dir():
        raise UnsafeWorkspace('Invalid compiled test directory')
    identities={}
    for path in sorted(directory.iterdir()):
        if path.is_symlink():raise UnsafeWorkspace('Compiled test symlink')
        if path.is_file() and os.access(path,os.X_OK):
            if path.stat().st_nlink!=1:raise UnsafeWorkspace('Compiled test hardlink')
            raw=path.read_bytes()
            if raw[:4]!=b'\xcf\xfa\xed\xfe':raise UnsafeWorkspace('Expected pinned ARM64 Mach-O test executable')
            identities[path]=hashlib.sha256(raw).hexdigest()
    if not identities:raise UnsafeWorkspace('No compiled test executables')
    return identities


def _xml_originals(directory,*,limit):
    """Read only SDK's immediate tests/*.xml, never links or stale reports."""
    tests=directory/'tests'
    if (directory.is_symlink() or directory.resolve()!=directory or tests.is_symlink() or
            not tests.is_dir() or tests.resolve()!=tests):raise UnsafeWorkspace('Invalid XML report directory')
    if set(p.name for p in directory.iterdir())!={'tests'}:raise UnsafeWorkspace('Unexpected SDK report artifact')
    paths=list(tests.iterdir())
    if not 1<=len(paths)<=257:raise UnsafeWorkspace('XML report count exceeds bounds')
    result={};used=0
    for path in sorted(paths):
        if path.suffix!='.xml' or not path.name.startswith('test-'):raise UnsafeWorkspace('Unexpected SDK XML path')
        descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(descriptor,'rb') as stream:
            before=os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>limit-used:
                raise UnsafeWorkspace('Linked, nonregular or oversized SDK XML')
            raw=stream.read(limit-used+1);after=os.fstat(stream.fileno())
        def identity(value):
            # Reading may update atime; content/ownership/identity must stay frozen.
            return tuple(getattr(value,key) for key in ('st_dev','st_ino','st_mode','st_nlink',
                'st_uid','st_gid','st_size','st_mtime_ns','st_ctime_ns'))
        if len(raw)>limit-used or identity(before)!=identity(after) or path.is_symlink() or identity(path.stat())!=identity(after):
            raise UnsafeWorkspace('SDK XML changed during read')
        used+=len(raw);result[path.name]=raw
    return result


async def run_scoped_command(project,*,deadline,private_root,output_limit):
    """Compile then execute frozen tests with a fresh, fixed XML destination."""
    result=dict(exit_code=None,problem=None,stdout=b'',reports={},execution_argv=[],
                binary_before={},binary_after={},profiles=[],report_directory=None)
    try:
        project,target,temporary,home=_workspace_paths(project)
        for path in (target,temporary,home):path.mkdir(exist_ok=True)
        report=temporary/('xml-'+uuid.uuid4().hex);report.mkdir()
        result['report_directory']=report.relative_to(project).as_posix()
        env={**sdk_environment(),'HOME':str(home),'TMPDIR':str(temporary)}
        identities={}
        for phase,argv in [('compile',['cjpm','test','--no-run']),
                           ('test',['cjpm','test','--skip-build','--show-all-output',
                                    '--report-path',str(report),'--report-format','xml'])]:
            if phase=='test':
                identities=_compiled_tests(target)
                result['binary_before']={p.relative_to(project).as_posix():h for p,h in identities.items()}
            profile=execution_profile(project,phase=phase,executables=identities,private_root=private_root)
            result['profiles'].append(dict(phase=phase,sha256=hashlib.sha256(profile.encode()).hexdigest()))
            remaining=deadline-asyncio.get_running_loop().time()
            if remaining<=0:raise asyncio.TimeoutError()
            result['execution_argv'].append(list(argv))
            code,raw,problem=await _run_original_phase(project,argv,profile,env,
                timeout=remaining,output_limit=output_limit-len(result['stdout']))
            if type(raw) is not bytes:raise UnsafeWorkspace('SDK original bytes missing')
            result['stdout']+=raw;result['exit_code']=code
            if len(result['stdout'])>output_limit:raise OverflowError('OUTPUT_LIMIT')
            if problem:raise UnsafeWorkspace(problem)
            if phase=='compile' and (type(code) is not int or code!=0):
                raise UnsafeWorkspace('SDK_TEST_COMPILE_FAILED')
        after=_compiled_tests(target)
        result['binary_after']={p.relative_to(project).as_posix():h for p,h in after.items()}
        if after!=identities:raise UnsafeWorkspace('Compiled test executable changed')
        result['reports']=_xml_originals(report,limit=output_limit-len(result['stdout']))
    except (OSError,ValueError,asyncio.TimeoutError,OverflowError) as exc:
        result['problem']=str(exc) or type(exc).__name__
    return result


async def run_scoped_build_command(project,*,deadline,private_root,output_limit):
    """Byte-preserving fixed build; no configurable compiler arguments."""
    try:
        project,target,temporary,home=_workspace_paths(project)
        for path in (target,temporary,home):path.mkdir(exist_ok=True)
        profile=execution_profile(project,phase='compile',private_root=private_root)
        env={**sdk_environment(),'HOME':str(home),'TMPDIR':str(temporary)}
        return await _run_original_phase(project,['cjpm','build','-V'],profile,env,
            timeout=deadline-asyncio.get_running_loop().time(),output_limit=output_limit)
    except (OSError,ValueError) as exc:
        return None,b'',str(exc)


def execution_profile(project: Path, *, phase: str, executables=(), private_root=None) -> str:
    """Compile without candidate execution; run only frozen ARM64 test binaries."""
    project,target,temporary,_=_workspace_paths(project)
    quote=lambda path:json.dumps(str(path),ensure_ascii=False)
    allowed=[SDK/'tools/bin/cjpm',SDK/'bin/cjc',SDK/'bin/cjc-frontend']
    tools=['uname','arch','which']
    if phase=='compile':
        tools+=['ar','ld','clang','xcrun','dsymutil','strip','ranlib']
        allowed+=[SDK/'third_party/llvm/bin'/name for name in
                  ('llc','opt','ld.lld','ld64.lld','lld','llvm-ar')]
        allowed+=[Path('/Library/Developer/CommandLineTools/usr/bin')/tool for tool in tools]
    elif phase!='test':raise ValueError('Unknown execution phase')
    exclusions=['(require-not (literal '+quote(path.resolve())+'))' for path in allowed]
    exclusions+=['(require-not (literal '+quote('/usr/bin/'+tool)+'))' for tool in tools]
    exclusions+=['(require-not (literal "/bin/pwd"))']
    exclusions+=['(require-not (literal '+quote(path)+'))' for path in executables]
    profile=sandbox_profile(project,private_root=private_root)
    profile+='(deny process-exec (require-all '+''.join(exclusions)+'))'
    if phase=='test':
        # SBPL does not implement {6}; use six explicit character classes.
        pattern='^'+re.escape(str(target/'release/unittest_bin/tmpFile'))+'[A-Za-z0-9]'*6+'$'
        profile+='(deny file-write* (require-all (subpath '+quote(target)+')'
        profile+='(require-not (subpath '+quote(temporary)+'))'
        profile+='(require-not (literal '+quote(target/'release/unittest_bin/incremental-cache.json')+'))'
        profile+='(require-not (regex '+quote(pattern)+'))))'
    # Darwin permits procargs through alternative checks; both restrictions are
    # needed. SDKs may inspect their own/child processes, never the controller.
    profile+='(deny sysctl-read (sysctl-name-prefix "kern.procargs"))'
    profile+='(deny process-info*)(allow process-info* (target self))(allow process-info* (target children))'
    return profile


def sandbox_profile(project: Path, *, private_root: Path | None = None) -> str:
    project,target,_,_=_workspace_paths(project)
    profile = '(version 1)(allow default)(deny network*)(deny file-write*)'
    profile += '(deny signal)(allow signal (target self))(allow signal (target children))'
    profile += '(allow network-bind)(allow network-inbound (local ip "*:*" ))(allow network-inbound (remote ip "localhost:*"))'
    profile += '(allow network-outbound (remote ip "localhost:*"))'
    profile += '(allow file-write* (subpath '+json.dumps(str(target.resolve()), ensure_ascii=False)+'))'
    profile += '(allow file-write* (literal "/dev/null") (literal '+json.dumps(str((project/'cjpm.toml').resolve()), ensure_ascii=False)+'))'
    # Restrict user data reads while preserving OS runtime and compiler services.
    profile += '(deny file-read-data (require-all (subpath "/Users")'
    for allowed in (project, SDK):
        profile += '(require-not (subpath '+json.dumps(str(allowed.resolve()), ensure_ascii=False)+'))'
    profile += '))'
    if private_root is not None:
        private_root=private_root.resolve()
        if project==private_root or not project.is_relative_to(private_root):
            raise UnsafeWorkspace('Candidate must be inside its private runtime')
        # Controller records are private even when the runtime is outside /Users.
        profile += '(deny file-read-data (require-all (subpath '+json.dumps(str(private_root),ensure_ascii=False)+')'
        for allowed in (project,SDK):
            profile += '(require-not (subpath '+json.dumps(str(allowed.resolve()),ensure_ascii=False)+'))'
        profile += '))'
    profile += '(allow file-write* (literal '+json.dumps(str((project/'cjpm.lock').resolve()), ensure_ascii=False)+'))'
    for directory in [project, project/'src']:
        profile += '(allow file-write* (literal '+json.dumps(str(directory.resolve()), ensure_ascii=False)+'))'
    return profile
