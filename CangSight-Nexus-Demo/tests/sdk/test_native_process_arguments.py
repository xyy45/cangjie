"""Owned synthetic peer/ancestor process data, never real controller secrets."""
import subprocess
import sys
import pytest

from nexus.adapters.cangjie.sdk import sdk_environment
from nexus.execution.runner import execution_profile

pytestmark=pytest.mark.sdk
MARKER='SYNTHETIC_PROCESS_ARGUMENT_MARKER'


def test_candidate_cannot_read_owned_peer_or_ancestor_arguments(tmp_path):
    project=tmp_path/'project';unit=project/'target/release/unittest_bin'
    unit.mkdir(parents=True)
    reader=unit/'owned-reader';target=unit/'owned-target'
    reader_source=unit/'owned-reader.c'
    reader_source.write_text(r'''
#include <sys/types.h>
#include <sys/sysctl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
int main(int argc,char **argv){
 if(argc!=2)return 10;
 int mib[3]={CTL_KERN,KERN_PROCARGS2,atoi(argv[1])};size_t size=262144;
 char *data=malloc(size);if(!data)return 11;
 if(sysctl(mib,3,data,&size,NULL,0)){
  int e=errno;free(data);
  if(e==EPERM||e==EACCES){puts("PROCESS_ARGUMENT_READ_DENIED");return 0;}
  printf("UNEXPECTED_READ_ERROR=%d\n",e);return 12;
 }
 const char *marker="SYNTHETIC_PROCESS_ARGUMENT_MARKER";int found=0;
 for(size_t i=0;i+strlen(marker)<=size;i++)if(memcmp(data+i,marker,strlen(marker))==0)found=1;
 free(data);
 if(found){puts("SYNTHETIC_ARGUMENT_VISIBLE");return 23;}
 puts("POSITIVE_CONTROL_MARKER_NOT_FOUND");return 13;
}
''')
    target_source=unit/'owned-target.c'
    target_source.write_text('#include <stdio.h>\n#include <unistd.h>\n'
        'int main(int argc,char **argv){puts("READY");fflush(stdout);sleep(30);return 0;}\n')
    for source,binary in [(reader_source,reader),(target_source,target)]:
        built=subprocess.run(['/usr/bin/clang',str(source),'-o',str(binary)],
            capture_output=True,text=True,timeout=30)
        assert built.returncode==0,built.stderr
    profile=execution_profile(project,phase='test',executables=[reader],private_root=tmp_path)
    env=sdk_environment()
    peer=subprocess.Popen([str(target),MARKER],env={'PATH':'/usr/bin:/bin'},stdout=subprocess.PIPE,text=True)
    try:
        assert peer.stdout.readline().strip()=='READY'
        positive=subprocess.run([str(reader),str(peer.pid)],env=env,cwd=project,
            capture_output=True,text=True,timeout=10)
        assert positive.returncode==23 and positive.stdout.strip()=='SYNTHETIC_ARGUMENT_VISIBLE'
        restricted=subprocess.run(['/usr/bin/sandbox-exec','-p',profile,str(reader),str(peer.pid)],
            env=env,cwd=project,capture_output=True,text=True,timeout=10)
        assert restricted.returncode==0,restricted.stdout+restricted.stderr
        assert restricted.stdout.strip()=='PROCESS_ARGUMENT_READ_DENIED'
        assert peer.poll() is None
    finally:
        peer.terminate();peer.wait(timeout=5);peer.stdout.close()
    # The controller is an ancestor of candidate execution, so also test that
    # relationship with a disposable parent containing only synthetic arguments.
    parent_code='''import os,subprocess,sys
args=[sys.argv[2],str(os.getpid())]
if sys.argv[1]!='UNRESTRICTED':args=['/usr/bin/sandbox-exec','-p',sys.argv[1],*args]
raise SystemExit(subprocess.run(args).returncode)
'''
    for rule,expected,text in [('UNRESTRICTED',23,'SYNTHETIC_ARGUMENT_VISIBLE'),
                              (profile,0,'PROCESS_ARGUMENT_READ_DENIED')]:
        parent=subprocess.run([sys.executable,'-c',parent_code,rule,str(reader),MARKER],
            env=env,cwd=project,capture_output=True,text=True,timeout=10)
        assert parent.returncode==expected,parent.stdout+parent.stderr
        assert parent.stdout.strip()==text
