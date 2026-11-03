"""Explicit source inventories and selected diagnostics, without runtime copies."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid
import zipfile

MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_FILES = 4096
CONFIG_TEMPLATE = b'# Local configuration; fill only after explicit model-call authorization.\nDEEPSEEK_API_KEY=\nDEEPSEEK_BASE_URL=\nDEEPSEEK_MODEL=\n'
CHECK_CODES = ('ENVIRONMENT_PROBE','PYTHON','PLATFORM','DEPENDENCIES','SDK_TOOLCHAIN',
               'MACOS_DEVELOPER_SDK','STDX_LAYOUT','CORE','MODEL_CONFIGURATION','PORT')
REQUIRED_FILES = frozenset({
    'deployment-files.json','.env.example','requirements.lock','pyproject.toml',
    'nexus/demo/app.py','nexus/demo/cases.py','cang_sight_server/server.py',
    'cangjie/core/src/main.cj','scripts/install_runtime.py','scripts/build_core.py',
    'scripts/doctor.py','scripts/diagnostics.py','scripts/package_app.py',
    'docs/runbook.md','docs/third-party-and-ai.md','docs/third-party/sympas/LICENSE',
    'fixtures/repair-cases/catalog.json',
})
SKIP = {'.git','.runtime','.superpowers','.venv','venv','__pycache__','.pytest_cache',
        '.DS_Store','node_modules'}
KNOWN_PREFIXES = {'nexus','cang_sight_server','scripts','fixtures','cangjie','docs'}
VERSION = re.compile(r'[0-9][A-Za-z0-9.!+_-]{0,63}\Z')
HEX = re.compile(r'[0-9a-f]{64}\Z')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def canonical(name):
    if type(name) is not str or not name or len(name)>256:
        raise ValueError('Invalid artifact member')
    path=PurePosixPath(name)
    if (not path.parts or path.is_absolute() or path.as_posix()!=name or '..' in path.parts or
            any(ord(c)<32 for c in name) or '\\' in name or ':' in name):
        raise ValueError('Noncanonical artifact member')
    return path


def private(name):
    parts=canonical(name).parts
    return parts[0] in {'uploads','records'} or any(p in SKIP or (p.startswith('.env') and name!='.env.example') or
               p.startswith('.controller') or p in ('.session-key','.operator-key') for p in parts)


def read_regular(root, name):
    """Open each selected component without following symlinks or special files."""
    parts=canonical(name).parts
    descriptors=[]
    try:
        directory=os.open(Path(root),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        descriptors.append(directory)
        for part in parts[:-1]:
            directory=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            descriptors.append(directory)
        descriptor=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        descriptors.append(descriptor)
        before=os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>MAX_FILE:
            raise ValueError('Selected member is not a bounded regular file')
        with os.fdopen(os.dup(descriptor),'rb') as stream:raw=stream.read(MAX_FILE+1)
        after=os.fstat(descriptor)
        if (len(raw)>MAX_FILE or len(raw)!=before.st_size or
                (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns)):
            raise ValueError('Selected member changed during reading')
        return raw
    except OSError as exc:
        raise ValueError('Selected member unavailable or linked') from exc
    finally:
        for descriptor in reversed(descriptors):os.close(descriptor)


def loads(raw):
    def pairs(rows):
        result={}
        for key,value in rows:
            if key in result:raise ValueError('Duplicate JSON field')
            result[key]=value
        return result
    try:return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except (TypeError,UnicodeError,json.JSONDecodeError) as exc:raise ValueError('Invalid JSON material') from exc


def inventory_items(root):
    specification=loads(read_regular(root,'deployment-files.json'))
    if type(specification) is not dict or set(specification)!={'schema_version','files'} or type(specification['schema_version']) is not int or specification['schema_version']!=1:
        raise ValueError('Unsupported source inventory')
    names=specification['files']
    if (type(names) is not list or not 1<=len(names)<=MAX_FILES or
            any(type(n) is not str for n in names) or names!=sorted(set(names)) or not REQUIRED_FILES.issubset(names)):
        raise ValueError('Incomplete or duplicate source inventory')
    for name in names:
        path=canonical(name)
        if (private(name) or name.startswith('nexus/demo/data/') or
                len(path.parts)>1 and path.parts[0] not in KNOWN_PREFIXES):
            raise ValueError('Private or foreign source inventory member')
    # Do not admit a newly appeared source file merely because its suffix fits.
    for prefix in ('nexus','cang_sight_server'):
        actual=set()
        for folder,dirs,files in os.walk(Path(root)/prefix,followlinks=False):
            relative=Path(folder).relative_to(root)
            dirs[:]=[d for d in dirs if d not in SKIP and not private((relative/d).as_posix())
                     and (relative/d).as_posix()!='nexus/demo/data']
            for directory in dirs:
                if (Path(folder)/directory).is_symlink():raise ValueError('Linked production directory')
            for name in files:
                member=(relative/name).as_posix()
                if name in SKIP or private(member):continue
                actual.add(member)
        if actual!={n for n in names if n.startswith(prefix+'/')}:
            raise ValueError('Unexpected or missing production resource')
    total=0
    for name in names:
        raw=read_regular(root,name)
        total+=len(raw)
        if total>MAX_TOTAL:raise ValueError('Source byte budget exceeded')
        if name=='.env.example' and raw!=CONFIG_TEMPLATE:
            raise ValueError('Configuration template must contain only the declared empty values')
        yield name,raw


def inventory(root):
    return dict(inventory_items(root))


def write_archive(path, files, manifest):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,raw in sorted({**files,'manifest.json':encoded(manifest)}.items()):
            entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));entry.external_attr=(stat.S_IFREG|0o644)<<16
            entry.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(entry,raw)


def verify(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_TOTAL:
        raise ValueError('Invalid archive file')
    try:
        with zipfile.ZipFile(path) as archive:
            entries=archive.infolist();names=[i.filename for i in entries]
            if len(names)!=len(set(names)) or not 2<=len(names)<=MAX_FILES+1 or 'manifest.json' not in names:
                raise ValueError('Invalid archive inventory')
            if sum(i.file_size for i in entries)>MAX_TOTAL:
                raise ValueError('Archive expanded budget exceeded')
            for entry in entries:
                canonical(entry.filename)
                if (entry.is_dir() or entry.file_size>MAX_FILE or entry.flag_bits&1 or
                        stat.S_IFMT(entry.external_attr>>16)==stat.S_IFLNK or private(entry.filename)):
                    raise ValueError('Unsafe archive member')
            manifest=loads(archive.read('manifest.json'))
            if (type(manifest) is not dict or set(manifest)!={'schema_version','kind','files','source_hash'} or
                    type(manifest['schema_version']) is not int or manifest['schema_version']!=1 or
                    manifest['kind'] not in ('SOURCE_APPLICATION','DIAGNOSTIC') or type(manifest['files']) is not dict or
                    set(names)!=set(manifest['files'])|{'manifest.json'}):
                raise ValueError('Invalid archive manifest')
            for name,expected in manifest['files'].items():
                if (type(expected) is not dict or set(expected)!={'sha256','bytes'} or
                        type(expected['bytes']) is not int or not 0<=expected['bytes']<=MAX_FILE or
                        type(expected['sha256']) is not str or not HEX.fullmatch(expected['sha256'])):
                    raise ValueError('Invalid member metadata')
                raw=archive.read(name)
                if expected!={'sha256':sha(raw),'bytes':len(raw)}:raise ValueError('Archive member changed')
            if manifest['source_hash']!=sha(encoded(manifest['files'])):raise ValueError('Archive identity changed')
            if manifest['kind']=='DIAGNOSTIC':
                if set(manifest['files'])!={'diagnostic.json'}:raise ValueError('Unexpected diagnostic contents')
            else:
                specification=loads(archive.read('deployment-files.json'))
                if (type(specification) is not dict or set(specification)!={'schema_version','files'} or
                        type(specification['schema_version']) is not int or specification['schema_version']!=1 or
                        type(specification['files']) is not list or
                        specification['files']!=sorted(manifest['files']) or
                        not REQUIRED_FILES.issubset(specification['files']) or
                        any(name.startswith('nexus/demo/data/') for name in specification['files']) or
                        archive.read('.env.example')!=CONFIG_TEMPLATE):
                    raise ValueError('Unexpected source application contents')
            return manifest
    except (OSError,zipfile.BadZipFile,KeyError,TypeError) as exc:raise ValueError('Invalid artifact archive') from exc


def publish(output, files, kind, recheck):
    output=Path(output).absolute()
    if output.exists() or output.is_symlink():raise FileExistsError('Artifact output already exists')
    if not output.parent.is_dir() or output.parent.is_symlink():raise ValueError('Artifact output parent unavailable')
    table={name:dict(sha256=sha(raw),bytes=len(raw)) for name,raw in sorted(files.items())}
    manifest=dict(schema_version=1,kind=kind,files=table,source_hash=sha(encoded(table)))
    part=output.with_name(output.name+'.'+uuid.uuid4().hex+'.part')
    descriptor=os.open(part,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(descriptor)
    # Failed temporary output is retained for inspection; never publish it.
    write_archive(part,files,manifest)
    if verify(part)!=manifest:raise ValueError('Written archive differs')
    recheck()
    os.link(part,output)  # Atomic no-overwrite publication, including a racing writer.
    part.unlink()
    return dict(path=str(output),sha256=sha(output.read_bytes()),bytes=output.stat().st_size,
                kind=kind,source_hash=manifest['source_hash'],files=len(files))


def application(root, output):
    root=Path(root);files=inventory(root)
    def unchanged():
        seen=set()
        for name,raw in inventory_items(root):
            if name not in files or raw!=files[name]:raise ValueError('Source changed while packaging')
            seen.add(name)
        if seen!=set(files):raise ValueError('Source inventory changed while packaging')
    return publish(output,files,'SOURCE_APPLICATION',unchanged)


def safe_version(value):
    return value if type(value) is str and VERSION.fullmatch(value) else None


def selected_report(raw):
    source=loads(raw)
    if (type(source) is not dict or type(source.get('schema_version')) is not int or source['schema_version']!=1 or
            source.get('provider') not in ('rule','deepseek') or type(source.get('port')) is not int or
            not 1<=source['port']<=65535 or type(source.get('checks')) is not list or len(source['checks'])!=len(CHECK_CODES)):
        raise ValueError('Invalid supplied self-check report')
    checks=[];seen=set()
    for row in source['checks']:
        if type(row) is not dict or row.get('code') not in CHECK_CODES or row['code'] in seen or row.get('state') not in ('PASS','FAIL','UNKNOWN'):
            raise ValueError('Invalid supplied check collection')
        code=row['code'];seen.add(code);details=row.get('details',{})
        if type(details) is not dict:raise ValueError('Invalid supplied check details')
        clean={}
        if code=='PYTHON':clean['version']=safe_version(details.get('version'))
        elif code=='DEPENDENCIES':
            clean['mismatches']=[]
            mismatches=details.get('mismatches',[])
            if type(mismatches) is not list or len(mismatches)>40:raise ValueError('Invalid dependency differences')
            for mismatch in mismatches:
                name=mismatch.get('distribution') if type(mismatch) is dict else None
                if type(name) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',name):raise ValueError('Invalid distribution name')
                clean['mismatches'].append(dict(distribution=name,expected=safe_version(mismatch.get('expected')),actual=safe_version(mismatch.get('actual'))))
        elif code=='CORE':
            component=details.get('component')
            clean['component']={key:component[key] for key in ('core_source_hash','core_component_hash','core_compiler_hash')
                if type(component.get(key)) is str and HEX.fullmatch(component[key])} if type(component) is dict else None
        elif code=='MODEL_CONFIGURATION':
            present=details.get('present',{})
            clean=dict(required=source['provider']=='deepseek',present={key:present.get(key) is True for key in
                ('api_key_present','base_url_present','model_present')} if type(present) is dict else {})
        checks.append(dict(code=code,state=row['state'],details=clean))
    return dict(schema_version=1,origin='SUPPLIED_SELF_CHECK_REPORT_NOT_REPROBED',input_sha256=sha(raw),
                provider=source['provider'],port=source['port'],checks=checks,
                ready=all(row['state']=='PASS' for row in checks),model_connectivity='NOT_PROBED')


def diagnostic(root, output, *, report='selfcheck.json'):
    if report!='selfcheck.json':raise ValueError('Only local selfcheck.json is a diagnostic input')
    raw=read_regular(root,report)
    producer_root=Path(__file__).parent
    producer=read_regular(producer_root,'artifacts.py')
    selected=selected_report(raw);selected['producer_sha256']=sha(producer)
    files={'diagnostic.json':encoded(selected)}
    def unchanged():
        if read_regular(root,report)!=raw:raise ValueError('Self-check report changed while packaging')
        if read_regular(producer_root,'artifacts.py')!=producer:raise ValueError('Diagnostic producer changed while packaging')
    return publish(output,files,'DIAGNOSTIC',unchanged)
