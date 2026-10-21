from pathlib import Path
import pytest
from nexus.contracts import CandidateProposal, file_hash, tree_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.store import RunStore

ROOT = Path(__file__).resolve().parents[1]


def setup_workspace(tmp_path):
    ws = WorkspaceStore(tmp_path, registered=[ROOT / 'fixtures/order-demo'])
    baseline = ws.import_project(ROOT / 'fixtures/order-demo', '.')
    store = RunStore(tmp_path)
    task = store.create_task(baseline, 'fix quantity', ['src/quantity.cj', 'src/fee.cj'])
    return ws, store, task


def proposal(ws, task, paths):
    return CandidateProposal(edits=[dict(path=p, before_hash=file_hash(ws.read_file(task.baseline_id, p)),
                                        content=ws.read_file(task.baseline_id, p)+'\n// edit\n') for p in paths],
                             requirement_refs=['goal'])


def test_two_file_edits_publish_all_or_none(tmp_path):
    ws, store, task = setup_workspace(tmp_path)
    p = proposal(ws, task, ['src/quantity.cj', 'src/fee.cj'])
    p.edits[1].before_hash = '0'*64
    with pytest.raises(ValueError):
        ws.apply_candidate(task, p)
    assert not store.records(task.id, 'candidate')
    assert not list((tmp_path / 'candidates').iterdir())


def test_baseline_unchanged_after_candidate(tmp_path):
    ws, store, task = setup_workspace(tmp_path)
    before = tree_hash(ws.subject_path(task.baseline_id))
    c = ws.apply_candidate(task, proposal(ws, task, ['src/quantity.cj']))
    assert before == tree_hash(ws.subject_path(task.baseline_id))
    assert c.tree_hash != before
    assert '+// edit' in ws.diff(c.id)
    assert store.get_task(task.id).attempt_count == 1


def test_duplicate_diff_does_not_create_new_attempt(tmp_path):
    ws, store, task = setup_workspace(tmp_path)
    p = proposal(ws, task, ['src/quantity.cj'])
    ws.apply_candidate(task, p)
    with pytest.raises(ValueError, match='duplicate'):
        ws.apply_candidate(task, p)
    assert store.get_task(task.id).attempt_count == 1


def test_source_modes_normalized_without_modifying_registered_input(tmp_path):
    import shutil
    import stat
    source=tmp_path/'registered'
    shutil.copytree(ROOT/'fixtures/order-demo',source)
    (source/'src/quantity.cj').chmod(0o755)
    ws=WorkspaceStore(tmp_path/'runtime',registered=[source])
    baseline=ws.import_project(source,'.')
    original=source/'src/quantity.cj'
    copied=ws.subject_path(baseline)/'src/quantity.cj'
    assert stat.S_IMODE(original.stat().st_mode)==0o755
    assert stat.S_IMODE(copied.stat().st_mode)==0o644
    identity=tree_hash(ws.subject_path(baseline))
    copied.chmod(0o755)
    assert tree_hash(ws.subject_path(baseline))==identity
    with pytest.raises(ValueError,match='permissions changed'):ws.verify_baseline(baseline)
    copied.chmod(0o644)
    store=RunStore(ws.root)
    task=store.create_task(baseline,'mode check',['src/quantity.cj'])
    candidate=ws.apply_candidate(task,proposal(ws,task,['src/quantity.cj']))
    (ws.subject_path(candidate.id)/'src/quantity.cj').chmod(0o600)
    with pytest.raises(ValueError,match='permissions changed'):ws.candidate(candidate.id)
