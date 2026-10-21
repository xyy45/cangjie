import os
from pathlib import Path
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.sdk
ROOT = Path(__file__).resolve().parents[2]


def run_sdk(project, command):
    sdk = ROOT / '.runtime/sdk/cangjie'
    assert (sdk / 'bin/cjc').is_file(), 'SDK unavailable; real verification required'
    env = {key: os.environ[key] for key in ("HOME", "PATH", "TMPDIR") if key in os.environ}
    env['CANGJIE_HOME'] = str(sdk)
    env['PATH'] = f"{sdk}/bin:{sdk}/tools/bin:" + env['PATH']
    env['DYLD_LIBRARY_PATH'] = f"{sdk}/runtime/lib/darwin_aarch64_cjnative:{sdk}/tools/lib"
    env['SDKROOT'] = '/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk'
    return subprocess.run(command, cwd=project, env=env, capture_output=True, text=True, timeout=90)


def test_normal_and_defective_order_demo(tmp_path):
    project = tmp_path / 'order'
    shutil.copytree(ROOT / 'fixtures/order-demo', project,
                    ignore=shutil.ignore_patterns('target', '.git', 'cjpm.lock'))
    build = run_sdk(project, ['cjpm', 'build', '-V'])
    assert build.returncode == 0, build.stdout + build.stderr
    result = run_sdk(project, ['cjpm', 'test'])
    (ROOT / f'docs/evidence/order-normal-{tmp_path.name}-{tmp_path.parent.name}.txt').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASSED' in result.stdout
    source = project / 'src/quantity.cj'
    source.write_text(source.read_text().replace('quantity >= 1', 'quantity >= 0'))
    broken = run_sdk(project, ['cjpm', 'test'])
    (ROOT / f'docs/evidence/order-defective-{tmp_path.name}-{tmp_path.parent.name}.txt').write_text(broken.stdout + broken.stderr)
    assert broken.returncode != 0
    assert 'FAILED' in broken.stdout
