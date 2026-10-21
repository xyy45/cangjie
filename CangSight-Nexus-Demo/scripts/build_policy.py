"""Build native policy with fixed local Cangjie and stdx versions."""
from pathlib import Path
import subprocess
import hashlib
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nexus.adapters.cangjie.sdk import ROOT, sdk_environment

if __name__ == '__main__':
    stdx = ROOT / '.runtime/stdx/darwin_aarch64_cjnative/static'
    temporary=ROOT/'.runtime/policy.next'
    result = subprocess.run(['cjc', 'cangjie/policy/src/main.cj', '-o', str(temporary),
        '--import-path', str(stdx), '-L', str(stdx / 'stdx'), '-lstdx.encoding.json',
        '-lstdx.encoding.jsonFFI', '-lstdx.serialization.serialization'],
        cwd=ROOT, env=sdk_environment(), timeout=90)
    if result.returncode==0:
        temporary.replace(ROOT/'.runtime/policy')
        metadata=dict(schema_version=1,policy_version='1.1',
            source_hash=hashlib.sha256((ROOT/'cangjie/policy/src/main.cj').read_bytes()).hexdigest(),
            binary_hash=hashlib.sha256((ROOT/'.runtime/policy').read_bytes()).hexdigest(),
            compiler_hash=hashlib.sha256((ROOT/'.runtime/sdk/cangjie/bin/cjc').read_bytes()).hexdigest())
        pending=ROOT/'.runtime/policy-build.json.next'
        pending.write_text(json.dumps(metadata,indent=2)+'\n')
        pending.replace(ROOT/'.runtime/policy-build.json')
    temporary.unlink(missing_ok=True)
    raise SystemExit(result.returncode)
