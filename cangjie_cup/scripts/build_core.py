"""Compile the complete native core source with the pinned local SDK."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nexus.adapters.cangjie.sdk import ROOT, sdk_environment


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    runtime = ROOT / '.runtime'
    source = ROOT / 'cangjie/core/src/main.cj'
    compiler = runtime / 'sdk/cangjie/bin/cjc'
    stdx = runtime / 'stdx/darwin_aarch64_cjnative/static'
    sources = sorted((ROOT / 'cangjie/core').rglob('*.cj'))
    if sources != [source] or any(p.is_symlink() for p in (source, compiler)):
        raise ValueError('Native core build requires exactly its declared regular source')
    before = {'core_source_hash': sha(source), 'core_compiler_hash': sha(compiler)}
    with tempfile.TemporaryDirectory(prefix='core-build-', dir=runtime) as temporary:
        binary = Path(temporary) / 'core'
        result = subprocess.run([str(compiler), str(source), '-o', str(binary),
            '--import-path', str(stdx), '-L', str(stdx / 'stdx'), '-lstdx.encoding.json',
            '-lstdx.encoding.jsonFFI', '-lstdx.serialization.serialization'],
            cwd=ROOT, env=sdk_environment(), timeout=90)
        if result.returncode:
            return result.returncode
        if before != {'core_source_hash': sha(source), 'core_compiler_hash': sha(compiler)}:
            raise ValueError('Native core source or compiler changed during build')
        metadata = {'schema_version': 1, 'core_version': '2.0', **before,
                    'core_component_hash': sha(binary)}
        record = Path(temporary) / 'core-build.json'
        record.write_text(json.dumps(metadata, indent=2) + '\n')
        # Readers see either a matching pair or fail closed during this switch.
        binary.replace(runtime / 'core')
        record.replace(runtime / 'core-build.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(build())
