import pytest
from nexus.store import RunStore


def test_task_reloads_without_resetting_attempts(tmp_path):
    store = RunStore(tmp_path)
    task = store.create_task('base', 'fix', ['src/a.cj'])
    store.update_task(task.id, attempt_count=2, status='GENERATING')
    assert RunStore(tmp_path).get_task(task.id).attempt_count == 2


def test_foreign_reference_and_duplicate_attempt_rejected(tmp_path):
    store = RunStore(tmp_path)
    a = store.create_task('a', 'fix', ['src/a.cj'])
    b = store.create_task('b', 'fix', ['src/a.cj'])
    candidate = dict(id='c', task_id=a.id, attempt=1, baseline_hash='hash',
                     edits=[], tree_hash='tree', diff_ref='diff')
    store.append_record(a.id, 'candidate', candidate)
    with pytest.raises(ValueError):
        store.append_record(a.id, 'candidate', {**candidate, 'id': 'd'})
    with pytest.raises(ValueError):
        store.append_record(b.id, 'check', {'subject_id': 'c', 'state': 'PASS'})


def test_records_are_append_only_and_secrets_not_logged(tmp_path):
    store = RunStore(tmp_path)
    t = store.create_task('base', 'fix', ['src/a.cj'])
    with pytest.raises(ValueError):
        store.append_record(t.id, 'tool_call', {'api_key': 'secret'})
    ref = store.append_record(t.id, 'event', {'message': 'ready'})
    assert (tmp_path / ref).is_file()
    assert store.records(t.id, 'event')[0]['message'] == 'ready'
