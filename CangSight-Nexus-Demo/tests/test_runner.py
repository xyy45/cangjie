from pathlib import Path
import subprocess
import pytest
from nexus.execution.runner import sandbox_profile


def test_restricted_profile_denies_outside_write_and_user_read(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'target').mkdir()
    protected = Path(__file__).resolve().parents[1] / '.runtime/sandbox-sentinel'
    # No real credentials are used in the probe.
    protected.write_text('synthetic sentinel')
    outside = tmp_path / 'outside'
    try:
        script = '''import pathlib,sys,socket
for path,mode in [(sys.argv[1],'r'), (sys.argv[2],'w')]:
    try:
        open(path,mode).close()
        raise AssertionError('sandbox unexpectedly allowed file access')
    except PermissionError:
        pass
s=socket.socket()
s.settimeout(1)
try:
    s.connect(('1.1.1.1',443))
    raise AssertionError('external connection allowed')
except PermissionError:
    pass
'''
        result = subprocess.run(['/usr/bin/sandbox-exec', '-p', sandbox_profile(project),
            '/usr/bin/python3', '-c', script, str(protected), str(outside)], capture_output=True, text=True, timeout=5, cwd=project)
        assert result.returncode == 0, result.stdout + result.stderr
        assert not outside.exists()
    finally:
        protected.unlink()


def test_timeout_and_output_limit_are_unknown_and_reap_processes(tmp_path,monkeypatch):
    import asyncio
    import time
    from nexus.execution.runner import run_command
    project=tmp_path/'project'
    project.mkdir()
    fake=project/'cjpm'
    # Only exercise bounded collection/group cleanup with a script fixture.
    # Production phase profiles deny this fake shell-based SDK.
    monkeypatch.setattr('nexus.execution.runner.execution_profile',
        lambda project,**kwargs:sandbox_profile(project))
    monkeypatch.setattr('nexus.execution.runner.sdk_environment',lambda:{'PATH':str(project)+':/usr/bin:/bin'})
    async def run():
        fake.write_text('#!/bin/sh\n/bin/sleep 30 &\necho $! > target/child.pid\nwait\n')
        fake.chmod(0o700)
        # Full-suite macOS sandbox startup can exceed two seconds. The child
        # still sleeps 30 seconds, so this exercises a real bounded timeout.
        started=time.monotonic()
        code,log,problem=await run_command(project,['cjpm','test'],timeout=5)
        assert code is None and problem=='TimeoutError'
        assert time.monotonic()-started<10
        child=(project/'target/child.pid').read_text().strip()
        state=subprocess.run(['/bin/ps','-o','stat=','-p',child],capture_output=True,text=True).stdout.strip()
        assert not state or state.startswith('Z'),state
        fake.write_text('#!/bin/sh\nwhile true; do echo 123456789012345678901234567890; done\n')
        code,log,problem=await run_command(project,['cjpm','test'],output_limit=100)
        assert code is None and problem=='OverflowError' and len(log.encode())<=100
    asyncio.run(run())


@pytest.mark.parametrize('relative',['target','target/.runner-tmp','target/.runner-tmp/home'])
def test_runner_rejects_output_symlinks_before_any_external_write_or_spawn(tmp_path,monkeypatch,relative):
    import asyncio
    from nexus.execution.runner import run_command, sandbox_profile
    project=tmp_path/'project';project.mkdir()
    outside=tmp_path/'outside';outside.mkdir()
    marker=outside/'keep.txt';marker.write_text('unchanged')
    link=project/relative;link.parent.mkdir(parents=True,exist_ok=True)
    link.symlink_to(outside,target_is_directory=True)
    calls=[]
    async def forbidden(*args,**kwargs):
        calls.append(args)
        raise OSError('Reproduction intercepted the unsafe command before launch')
    monkeypatch.setattr('nexus.execution.runner.asyncio.create_subprocess_exec',forbidden)
    code,log,problem=asyncio.run(run_command(project,['cjpm','test']))
    assert {p.relative_to(outside).as_posix() for p in outside.rglob('*')}=={'keep.txt'}
    assert calls==[]
    assert code is None and problem=='UnsafeWorkspace' and log==''
    assert marker.read_text()=='unchanged'
    with pytest.raises(ValueError):sandbox_profile(project)


def test_native_candidate_cannot_signal_unrelated_controller_but_can_reap_own_child(tmp_path):
    project=tmp_path/'project';project.mkdir()
    controller=subprocess.Popen(['/bin/sleep','20'])  # Owned disposable probe, never a real service.
    script='''import os,signal,subprocess,sys
try:
    os.kill(int(sys.argv[1]),signal.SIGUSR1)
except PermissionError:
    pass
else:
    raise AssertionError('Unrelated controller can be signalled')
os.kill(os.getpid(),0)
child=subprocess.Popen(['/bin/sleep','20'])
try:
    child.terminate()
    assert child.wait(timeout=3)==-signal.SIGTERM
finally:
    if child.poll() is None:child.kill();child.wait()
'''
    try:
        result=subprocess.run(['/usr/bin/sandbox-exec','-p',sandbox_profile(project),
            '/usr/bin/python3','-c',script,str(controller.pid)],capture_output=True,text=True,timeout=5,cwd=project)
        assert result.returncode==0,result.stdout+result.stderr
        assert controller.poll() is None
    finally:
        if controller.poll() is None:controller.terminate()
        controller.wait(timeout=3)
