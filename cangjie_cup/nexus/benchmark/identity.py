"""Read-only execution snapshot; no private config or model connectivity probes."""
from importlib.metadata import version,PackageNotFoundError
import platform
from pathlib import Path
import sys

from nexus.benchmark.corpus import sha
from nexus.benchmark.quality import toolchain_identity
from nexus.contracts import digest
from nexus.policy.core import NativeCoreClient,PROJECT_ROOT,VERSION


def implementation_identity():
    root=PROJECT_ROOT
    paths=[root/'requirements.lock',root/'scripts/doctor.py',root/'scripts/build_core.py']
    for package in ('nexus','cang_sight_server'):
        directory=root/package
        if directory.is_symlink() or any(p.is_symlink() for p in directory.rglob('*')):raise ValueError('执行源码目录及文件不得为链接')
        paths.extend(sorted(directory.rglob('*.py')))
    if any(p.is_symlink() or not p.is_file() or any(parent.is_symlink() for parent in p.parents if parent.is_relative_to(root)) for p in paths):
        raise ValueError('执行身份源码无效')
    lock=(root/'requirements.lock').read_bytes();dependencies={}
    for line in lock.decode().splitlines():
        if '==' not in line or line.startswith('#'):continue
        name=line.split('==',1)[0]
        try:dependencies[name]=version(name)
        except PackageNotFoundError:dependencies[name]='UNAVAILABLE'
    return dict(schema_version=1,python=sys.version,platform=platform.platform(),dependencies=dependencies,
                requirements_lock=sha(lock),source_hashes={p.relative_to(root).as_posix():sha(p.read_bytes()) for p in paths},
                toolchain=toolchain_identity(),core_version=VERSION,core=NativeCoreClient(root).component_identity())


def implementation_hash():return digest(implementation_identity())
