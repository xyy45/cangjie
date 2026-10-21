from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import zipfile
import pytest
from nexus.contracts import CheckResult, file_hash, CandidateProposal
from nexus.execution.delivery import DeliveryService
from nexus.execution.workspace import WorkspaceStore
from nexus.store import RunStore
from nexus.adapters.cangjie.verifier import CangjieVerifier

ROOT = Path(__file__).resolve().parents[1]


def checked(tmp_path):
    ws = WorkspaceStore(tmp_path, registered=[ROOT/'fixtures/order-demo'])
    baseline = ws.import_project(ROOT/'fixtures/order-demo', '.')
    store = RunStore(tmp_path)
    task = store.create_task(baseline, 'change', ['src/quantity.cj'])
    content = ws.read_file(baseline, 'src/quantity.cj')
    c = ws.apply_candidate(task, CandidateProposal(edits=[dict(path='src/quantity.cj', before_hash=file_hash(content), content=content+'\n// edit\n')], requirement_refs=['goal']))
    _, _, plan = CangjieVerifier(tmp_path, task.id).identity(c.id)
    # Synthetic records are unit-test fixtures only, never LIVE evidence.
    for kind, log in [('build','cjpm build success'), ('test','Summary: TOTAL: 1\n PASSED: 1, SKIPPED: 0, ERROR: 0\n FAILED: 0\ncjpm test success')]:
        ref = f'records/{kind}.log'
        (tmp_path/ref).write_text(log)
        store.append_record(task.id, 'check', CheckResult(id=kind, subject_id=c.id, plan_hash=plan,
            tree_hash=c.tree_hash, kind=kind, state='PASS', exit_code=0, log_ref=ref,
            counts={'total':1,'passed':1,'failed':0,'skipped':0,'errors':0} if kind=='test' else {}).model_dump())
    store.update_task(task.id, status='REVIEW_PENDING')
    store.append_record(task.id, 'event', {'selected_candidate_id':c.id})
    return ws, store, c, DeliveryService(store)


def test_changed_candidate_rejects_old_acceptance(tmp_path):
    ws, store, c, delivery = checked(tmp_path)
    a = delivery.accept(c.id, delivery.check_set_hash(c.id))
    (ws.subject_path(c.id)/'src/quantity.cj').write_text('changed')
    with pytest.raises(ValueError): delivery.export(c.id, a.id)


def test_concurrent_export_reserves_acceptance_once(tmp_path):
    ws, store, c, delivery = checked(tmp_path)
    a = delivery.accept(c.id, delivery.check_set_hash(c.id))
    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(lambda _: delivery.export(c.id,a.id), range(2)))
    assert len({r['export_id'] for r in result}) == 1
    assert len(list((tmp_path/'exports').glob('*.zip'))) == 1


def test_export_contains_checked_tree(tmp_path):
    ws, store, c, delivery = checked(tmp_path)
    a = delivery.accept(c.id, delivery.check_set_hash(c.id))
    result = delivery.export(c.id,a.id)
    with zipfile.ZipFile(tmp_path/result['download_ref']) as archive:
        assert archive.read('src/quantity.cj').decode() == (ws.subject_path(c.id)/'src/quantity.cj').read_text()
        assert not any('target/' in name or '.env' in name for name in archive.namelist())


def test_export_failure_can_be_reconciled(tmp_path, monkeypatch):
    ws, store, c, delivery = checked(tmp_path)
    a = delivery.accept(c.id, delivery.check_set_hash(c.id))
    original = delivery._package
    def fail(*args): raise OSError('unit test disk failure')
    monkeypatch.setattr(delivery, '_package', fail)
    with pytest.raises(OSError): delivery.export(c.id,a.id)
    monkeypatch.setattr(delivery, '_package', original)
    assert delivery.export(c.id,a.id)['status'] == 'DELIVERED'


def test_expired_acceptance_and_changed_logs_rejected(tmp_path):
    import json
    ws, store, c, delivery = checked(tmp_path)
    a = delivery.accept(c.id,delivery.check_set_hash(c.id))
    a.expires_at = 0.0
    with store.connect() as db:
        db.execute('UPDATE acceptances SET payload=? WHERE id=?', (a.model_dump_json(),a.id))
    with pytest.raises(ValueError): delivery.export(c.id,a.id)
    (tmp_path/'records/test.log').write_text('incomplete')
    with pytest.raises(ValueError): delivery.check_set_hash(c.id)


def test_changed_archive_cannot_be_reused_or_downloaded(tmp_path):
    ws,store,c,delivery=checked(tmp_path)
    a=delivery.accept(c.id,delivery.check_set_hash(c.id))
    result=delivery.export(c.id,a.id)
    with zipfile.ZipFile(tmp_path/result['download_ref'],'a') as archive:
        archive.writestr('injected.txt','tampered')
    with pytest.raises(ValueError): delivery.export(c.id,a.id)


def test_selection_change_invalidates_old_acceptance(tmp_path):
    ws,store,c,delivery=checked(tmp_path)
    a=delivery.accept(c.id,delivery.check_set_hash(c.id))
    store.append_record(c.task_id,'event',{'selected_candidate_id':'another-candidate'})
    with pytest.raises(ValueError): delivery.export(c.id,a.id)
