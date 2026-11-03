"""Versioned native Policy IPC; stale components and invalid replies fail closed."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import signal
import time

from nexus.contracts import PolicyRequest, PolicyResponse


class PolicyClient:
    def __init__(self, project_root: Path):
        self.root = Path(project_root)

    def component_identity(self) -> dict[str,str]:
        metadata=json.loads((self.root/'.runtime/policy-build.json').read_text())
        actual={
            'source_hash':hashlib.sha256((self.root/'cangjie/policy/src/main.cj').read_bytes()).hexdigest(),
            'binary_hash':hashlib.sha256((self.root/'.runtime/policy').read_bytes()).hexdigest(),
            'compiler_hash':hashlib.sha256((self.root/'.runtime/sdk/cangjie/bin/cjc').read_bytes()).hexdigest()}
        if (metadata.get('schema_version')!=1 or metadata.get('policy_version')!='1.1' or
                any(metadata.get(key)!=value for key,value in actual.items())):
            raise ValueError('Native Policy component does not match its build record')
        return {'policy_component_hash':actual['binary_hash'],'policy_source_hash':actual['source_hash']}

    async def decide(self, request: dict[str, object]) -> dict[str, object]:
        def deny(reason):
            return dict(schema_version=1,policy_version='1.1',decision='Deny',reason=reason)
        message=json.dumps(request,separators=(',',':'),ensure_ascii=False).encode('utf-8')+b'\n'
        if len(message)>65536:
            return deny('MESSAGE_LIMIT')
        process=None
        try:
            parsed=PolicyRequest.model_validate(request)
            if parsed.deadline_at<=int(time.time()*1000):
                return deny('REQUEST_DEADLINE_EXCEEDED')
            identity=self.component_identity()
            sdk=self.root/'.runtime/sdk/cangjie'
            env={'PATH':'/usr/bin:/bin','DYLD_LIBRARY_PATH':str(sdk/'runtime/lib/darwin_aarch64_cjnative')}
            # One total two-second IPC budget, including exit, not two per await.
            async with asyncio.timeout(min(2,(parsed.deadline_at-int(time.time()*1000))/1000)):
                process=await asyncio.create_subprocess_exec(str(self.root/'.runtime/policy'),
                    stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,env=env,start_new_session=True,limit=65536)
                process.stdin.write(message)
                await process.stdin.drain()
                process.stdin.close()
                line=await process.stdout.readline()
                await process.wait()
                if process.returncode!=0 or not line or len(line)>65536:
                    raise ValueError('Invalid Policy process result')
                result=PolicyResponse.model_validate_json(line)
            for key in ('request_id','input_tree_hash','arguments_hash','approval_binding'):
                if getattr(result,key)!=getattr(parsed,key):
                    raise ValueError('Policy response binding mismatch')
            if identity!=self.component_identity():
                raise ValueError('Policy component changed during execution')
            if parsed.deadline_at<=int(time.time()*1000):
                return deny('REQUEST_DEADLINE_EXCEEDED')
            return {**result.model_dump(),**identity}
        except (OSError,ValueError,KeyError,asyncio.TimeoutError):
            return deny('POLICY_UNAVAILABLE')
        finally:
            if process is not None and process.returncode is None:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                await process.wait()
