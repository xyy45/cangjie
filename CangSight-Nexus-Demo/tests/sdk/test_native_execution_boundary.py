"""Real OS enforcement probe using an owned native executable, never a model."""
import subprocess
import shutil
import pytest

from nexus.adapters.cangjie.sdk import SDK, sdk_environment
from nexus.execution.runner import execution_profile

pytestmark=pytest.mark.sdk


def test_frozen_native_code_cannot_exec_shell_write_artifacts_or_hardlink_alias(tmp_path):
    project=tmp_path/'project';unit=project/'target/release/unittest_bin'
    unit.mkdir(parents=True)
    temporary=project/'target/.runner-tmp';temporary.mkdir()
    sentinel=unit/'sentinel';sentinel.write_text('owned frozen sentinel')
    source=temporary/'probe.c'
    source.write_text(r'''
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
int main(int argc,char **argv){
 if(argc!=4)return 10;
 int fd=open(argv[1],O_WRONLY|O_APPEND);
 if(fd>=0){close(fd);return 11;}
 if(link(argv[1],argv[2])==0)return 12;
 if(system("printf UNEXPECTED_SHELL_EXECUTION")==0)return 13;
 fd=open(argv[3],O_WRONLY|O_CREAT,0600);
 if(fd<0)return 14;
 close(fd);puts("FROZEN_NATIVE_BOUNDARY_DENIED");return 0;
}
''')
    executable=unit/'owned-probe'
    compiled=subprocess.run(['/usr/bin/clang',str(source),'-o',str(executable)],
        capture_output=True,text=True,timeout=30)
    assert compiled.returncode==0,compiled.stderr
    args=[str(executable),str(sentinel),str(temporary/'alias'),str(unit/'tmpFileABC123')]
    result=subprocess.run(['/usr/bin/sandbox-exec','-p',execution_profile(project,
        phase='test',executables=[executable]),*args],cwd=project,env=sdk_environment(),
        capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stdout+result.stderr
    assert result.stdout.strip()=='FROZEN_NATIVE_BOUNDARY_DENIED'
    assert sentinel.read_text()=='owned frozen sentinel'
    assert not (temporary/'alias').exists()
    assert (unit/'tmpFileABC123').is_file()
    compile_phase=subprocess.run(['/usr/bin/sandbox-exec','-p',execution_profile(project,
        phase='compile'),*args],cwd=project,env=sdk_environment(),
        capture_output=True,text=True,timeout=10)
    assert compile_phase.returncode==71
    assert 'Operation not permitted' in compile_phase.stderr
    copied=temporary/'copied-probe'
    shutil.copyfile(executable,copied);copied.chmod(0o700)
    for command in ([str(copied),*args[1:]], [str(SDK/'third_party/llvm/bin/lldb'),'--version']):
        blocked=subprocess.run(['/usr/bin/sandbox-exec','-p',execution_profile(project,
            phase='test',executables=[executable]),*command],cwd=project,env=sdk_environment(),
            capture_output=True,text=True,timeout=10)
        assert blocked.returncode==71,blocked.stdout+blocked.stderr
        assert 'Operation not permitted' in blocked.stderr
