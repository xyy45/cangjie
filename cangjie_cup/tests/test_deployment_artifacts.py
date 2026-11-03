"""Selected source and diagnostic artifacts exclude operational material."""
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from nexus.deployment import artifacts


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    files = sorted(artifacts.REQUIRED_FILES | {'nexus/example.py'})
    for name in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name == '.env.example': raw = artifacts.CONFIG_TEMPLATE
        elif name == 'deployment-files.json': continue
        else: raw = ('sample ' + name + '\n').encode()
        path.write_bytes(raw)
    (root / 'deployment-files.json').write_text(json.dumps(dict(schema_version=1, files=files)))
    return root


def supplied_report():
    checks = [dict(code=code, state='PASS', details={}) for code in artifacts.CHECK_CODES]
    next(row for row in checks if row['code']=='MODEL_CONFIGURATION')['details'] = dict(
        required=False, present=dict(api_key_present=False, base_url_present=False, model_present=False),
        api_key='SECRET_MODEL_KEY', url='https://private.invalid', source='SECRET_SOURCE')
    return dict(schema_version=1, provider='rule', port=8899, ready=True, checks=checks,
                password='SECRET_PASSWORD', python_path='/private/user/SECRET_PATH')


def test_selected_diagnostic_never_copies_raw_report_or_operational_files(project, tmp_path, monkeypatch):
    raw_report = json.dumps(supplied_report())
    (project / 'selfcheck.json').write_text(raw_report)
    poison = [project / '.env', project / '.runtime/runs.sqlite3', project / 'uploads/user.cj',
              project / 'records/model-response.json', project / '.runtime/.session-key']
    for path in poison:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('SECRET_DO_NOT_READ')
    original = artifacts.read_regular
    opened = []
    def guarded(root, name):
        opened.append(name)
        assert name not in {p.relative_to(project).as_posix() for p in poison}
        assert name=='selfcheck.json' and Path(root)==project or name=='artifacts.py' and Path(root)==Path(artifacts.__file__).parent
        return original(root, name)
    monkeypatch.setattr(artifacts, 'read_regular', guarded)
    output = tmp_path / 'diagnostic.zip'
    artifacts.diagnostic(project, output)
    manifest = artifacts.verify(output)
    assert manifest['kind'] == 'DIAGNOSTIC'
    assert set(manifest['files']) == {'diagnostic.json'}
    with zipfile.ZipFile(output) as archive:
        payload = archive.read('diagnostic.json')
        assert b'SECRET_' not in payload and b'private.invalid' not in payload
        report = json.loads(payload)
        assert report['origin'] == 'SUPPLIED_SELF_CHECK_REPORT_NOT_REPROBED'
        assert report['input_sha256'] == hashlib.sha256(raw_report.encode()).hexdigest()
        assert report['producer_sha256']==hashlib.sha256(Path(artifacts.__file__).read_bytes()).hexdigest()
    assert set(opened)=={'selfcheck.json','artifacts.py'}


def test_diagnostic_recomputes_ready_and_rejects_duplicate_or_foreign_check(project, tmp_path):
    data = supplied_report()
    data['checks'][0]['state'] = 'UNKNOWN'
    path = project / 'selfcheck.json'
    path.write_text(json.dumps(data))
    output = tmp_path / 'unknown.zip'
    artifacts.diagnostic(project, output)
    with zipfile.ZipFile(output) as archive:
        assert json.loads(archive.read('diagnostic.json'))['ready'] is False
    for index, replacement in enumerate((data['checks'][0], dict(code='FOREIGN_SECRET', state='PASS'))):
        modified = supplied_report(); modified['checks'].append(replacement)
        path.write_text(json.dumps(modified))
        with pytest.raises(ValueError): artifacts.diagnostic(project, tmp_path / f'bad-{index}.zip')


@pytest.mark.parametrize('name', ['.env', '../selfcheck.json', 'records/model.json', '.runtime/report.json'])
def test_diagnostic_refuses_private_or_nonlocal_report_names(project, tmp_path, name):
    with pytest.raises(ValueError): artifacts.diagnostic(project, tmp_path/'private.zip', report=name)


def test_application_package_contains_only_declared_source_and_no_history(project, tmp_path):
    for name in ('.env','nexus/demo/data/order-live.zip','.runtime/runs.sqlite3','uploads/user.cj','records/model.json'):
        path=project/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'SECRET_DO_NOT_COPY')
    output=tmp_path/'app.zip'
    artifacts.application(project,output)
    manifest=artifacts.verify(output)
    assert manifest['kind']=='SOURCE_APPLICATION'
    assert set(manifest['files'])==set(json.loads((project/'deployment-files.json').read_text())['files'])
    with zipfile.ZipFile(output) as archive:
        assert b'SECRET_' not in b''.join(archive.read(n) for n in archive.namelist())
        assert archive.read('.env.example')==artifacts.CONFIG_TEMPLATE


def test_unknown_source_and_missing_required_resource_are_rejected(project,tmp_path):
    (project/'nexus/unregistered.py').write_text('unregistered source')
    with pytest.raises(ValueError): artifacts.application(project,tmp_path/'unknown.zip')
    (project/'nexus/unregistered.py').unlink()
    (project/'scripts/doctor.py').unlink()
    with pytest.raises(ValueError): artifacts.application(project,tmp_path/'missing.zip')


def test_upload_implementation_is_source_not_an_operational_upload_directory(project,tmp_path):
    name='nexus/uploads/service.py'
    (project/name).parent.mkdir(parents=True)
    (project/name).write_text('implementation source')
    data=json.loads((project/'deployment-files.json').read_text());data['files']=sorted([*data['files'],name])
    (project/'deployment-files.json').write_text(json.dumps(data))
    output=tmp_path/'upload-module.zip'
    artifacts.application(project,output)
    assert name in artifacts.verify(output)['files']


@pytest.mark.parametrize('name',['.','../outside.py','nexus/../outside.py','/absolute.py','nexus\\evil.py','.env','nexus/demo/data/order-live.zip'])
def test_private_or_noncanonical_manifest_member_rejected_before_read(project,tmp_path,name):
    specification=json.loads((project/'deployment-files.json').read_text());specification['files'].append(name)
    specification['files'].sort()
    (project/'deployment-files.json').write_text(json.dumps(specification))
    with pytest.raises(ValueError): artifacts.application(project,tmp_path/'unsafe.zip')


def test_source_symlink_parent_symlink_and_existing_output_never_overwritten(project,tmp_path):
    output=tmp_path/'existing.zip';output.write_bytes(b'ORIGINAL')
    with pytest.raises(FileExistsError): artifacts.application(project,output)
    assert output.read_bytes()==b'ORIGINAL'
    path=project/'nexus/example.py';path.unlink();path.symlink_to(project/'requirements.lock')
    with pytest.raises(ValueError): artifacts.application(project,tmp_path/'link.zip')


def test_linked_production_parent_is_rejected(project,tmp_path):
    original=tmp_path/'outside-nexus'
    (project/'nexus').rename(original)
    (project/'nexus').symlink_to(original,target_is_directory=True)
    with pytest.raises(ValueError): artifacts.application(project,tmp_path/'parent-link.zip')


def test_selected_file_budget_is_enforced(project,tmp_path):
    (project/'nexus/example.py').write_bytes(b'x'*(artifacts.MAX_FILE+1))
    with pytest.raises(ValueError): artifacts.application(project,tmp_path/'too-large.zip')


def test_total_budget_rejects_before_reading_entire_source_collection(project,tmp_path,monkeypatch):
    name='nexus/z_last.py';(project/name).write_bytes(b'x'*300)
    data=json.loads((project/'deployment-files.json').read_text());data['files']=sorted([*data['files'],name])
    (project/'deployment-files.json').write_text(json.dumps(data))
    monkeypatch.setattr(artifacts,'MAX_TOTAL',500)
    original=artifacts.read_regular;opened=[]
    def tracked(root,member):
        opened.append(member)
        return original(root,member)
    monkeypatch.setattr(artifacts,'read_regular',tracked)
    with pytest.raises(ValueError):artifacts.application(project,tmp_path/'too-many-bytes.zip')
    assert name not in opened
    assert not (tmp_path/'too-many-bytes.zip').exists()


def test_source_recheck_compares_incrementally_without_materializing_second_inventory(project,tmp_path,monkeypatch):
    original=artifacts.inventory;calls=[]
    def once(root):
        calls.append(True)
        if len(calls)>1:raise AssertionError('second complete source collection allocated')
        return original(root)
    monkeypatch.setattr(artifacts,'inventory',once)
    artifacts.application(project,tmp_path/'incremental.zip')
    assert len(calls)==1


def test_modified_config_template_or_duplicate_inventory_is_rejected(project,tmp_path):
    (project/'.env.example').write_bytes(b'DEEPSEEK_API_KEY=SECRET_VALUE\n')
    with pytest.raises(ValueError): artifacts.application(project,tmp_path/'bad-template.zip')
    (project/'.env.example').write_bytes(artifacts.CONFIG_TEMPLATE)
    data=json.loads((project/'deployment-files.json').read_text());data['files'].append(data['files'][0])
    (project/'deployment-files.json').write_text(json.dumps(data))
    with pytest.raises(ValueError): artifacts.application(project,tmp_path/'duplicate.zip')


def test_source_changed_while_archive_written_is_not_published(project,tmp_path,monkeypatch):
    original=artifacts.write_archive
    def changed(path,files,manifest):
        original(path,files,manifest)
        (project/'nexus/example.py').write_text('changed during creation')
    monkeypatch.setattr(artifacts,'write_archive',changed)
    output=tmp_path/'changed.zip'
    with pytest.raises(ValueError): artifacts.application(project,output)
    assert not output.exists()


def test_verification_rejects_duplicate_names_extra_member_and_changed_bytes(project,tmp_path):
    good=tmp_path/'good.zip';artifacts.application(project,good)
    with zipfile.ZipFile(good) as archive: entries={n:archive.read(n) for n in archive.namelist()}
    for kind in ('duplicate','extra','changed'):
        bad=tmp_path/(kind+'.zip')
        with zipfile.ZipFile(bad,'w') as archive:
            for n,raw in entries.items():archive.writestr(n,b'changed' if kind=='changed' and n=='nexus/example.py' else raw)
            if kind=='extra':archive.writestr('extra.txt',b'extra')
            if kind=='duplicate':archive.writestr('nexus/example.py',entries['nexus/example.py'])
        with pytest.raises(ValueError):artifacts.verify(bad)


@pytest.mark.parametrize('change',['boolean-byte-count','wrong-kind'])
def test_manifest_metadata_types_and_artifact_kind_are_not_interchangeable(project,tmp_path,change):
    (project/'nexus/example.py').write_bytes(b'x')
    good=tmp_path/'good.zip';artifacts.application(project,good)
    with zipfile.ZipFile(good) as archive:entries={n:archive.read(n) for n in archive.namelist()}
    manifest=json.loads(entries['manifest.json'])
    if change=='boolean-byte-count':
        manifest['files']['nexus/example.py']['bytes']=True
        manifest['source_hash']=artifacts.sha(artifacts.encoded(manifest['files']))
    else:manifest['kind']='DIAGNOSTIC'
    entries['manifest.json']=artifacts.encoded(manifest)
    bad=tmp_path/'invalid-metadata.zip'
    with zipfile.ZipFile(bad,'w') as archive:
        for name,raw in entries.items():archive.writestr(name,raw)
    with pytest.raises(ValueError):artifacts.verify(bad)
