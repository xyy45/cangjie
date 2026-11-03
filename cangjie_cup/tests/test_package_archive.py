"""Archive reference guard tests; byte packets are explicit non-SDK fixtures."""
import hashlib
import os
from copy import deepcopy
from types import SimpleNamespace

import pytest

from nexus.contracts import CheckResult
from nexus.execution.workspace import WorkspaceStore
from nexus.repair.package_evidence import PARSER
from nexus.repair.scoped_archive import references
from nexus.store import RunStore


def fixture(root):
    store = RunStore(root)
    task = store.create_task('b_'+'a'*32, 'archive guard fixture', ['src/one.cj'])
    ref = 'records/'+'b'*32+'.scan'
    raw = b'EXPLICIT ORIGINAL FIXTURE'
    (root/ref).write_bytes(raw)
    descriptor = dict(ref=ref, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    proof = dict(version=1, parser=PARSER, scans=[dict(stdout=descriptor, stderr=deepcopy(descriptor))], test=None)
    return store, task, proof, descriptor


def append(store, task, proof, subject=None):
    store.append_record(task.id, 'check', CheckResult(state='UNKNOWN', subject_id=subject or task.baseline_id,
        package_evidence=proof).model_dump())


def test_collect_only_exact_descriptor_bytes_and_ignore_remote_json_ref_fields(tmp_path):
    store, task, proof, item = fixture(tmp_path)
    # Arbitrary remote JSON is not traversed by the scoped descriptor collector.
    proof['remote_payload'] = dict(ref='records/other-task-secret.json')
    append(store, task, proof)
    assert references(store, task) == {item['ref']}


@pytest.mark.parametrize('control', ['sha', 'length', 'traversal', 'foreign-extension', 'symlink', 'hardlink', 'oversize', 'many', 'version', 'parser', 'foreign-owner'])
def test_bad_or_foreign_originals_stop_archive_collection(tmp_path, monkeypatch, control):
    store, task, proof, item = fixture(tmp_path)
    target = tmp_path/item['ref']
    subject = None
    if control == 'sha':
        target.write_bytes(b'changed')
    elif control == 'length':
        item['bytes'] += 1
    elif control == 'traversal':
        item['ref'] = 'records/../secret.scan'
    elif control == 'foreign-extension':
        item['ref'] = 'records/'+'b'*32+'.response.json'
    elif control == 'symlink':
        raw = target.read_bytes()
        target.unlink()
        (tmp_path/'other-original').write_bytes(raw)
        target.symlink_to(tmp_path/'other-original')
    elif control == 'hardlink':
        os.link(target, tmp_path/'other-link')
    elif control == 'oversize':
        item['bytes'] = 2*1024*1024+1
    elif control == 'many':
        proof['scans'] *= 17
    elif control == 'version':
        proof['version'] = True
    elif control == 'parser':
        proof['parser'] = 'other-parser'
    else:
        subject = 'c_'+'f'*32
    if control == 'foreign-owner':
        # Simulate a damaged controller record below RunStore's own earlier guard.
        monkeypatch.setattr(store, 'records', lambda *_: [CheckResult(state='UNKNOWN', subject_id=subject, package_evidence=proof).model_dump()])
        monkeypatch.setattr(WorkspaceStore, 'candidate', lambda *_: SimpleNamespace(task_id='other-task'))
    else:
        append(store, task, proof, subject)
    with pytest.raises((ValueError, OSError)):
        references(store, task)
