from pathlib import Path
import pytest
from nexus.execution.workspace import WorkspaceStore


def project(path):
    path.mkdir()
    (path / 'cjpm.toml').write_text('[package]\nname="a"')
    (path / 'src').mkdir()
    (path / 'src/a.cj').write_text('package a')
    return path


def test_ambiguous_build_roots_require_selection(tmp_path):
    source = project(tmp_path / 'source')
    project(source / 'nested')
    ws = WorkspaceStore(tmp_path / 'work', registered=[source])
    with pytest.raises(ValueError):
        ws.import_project(source, '')
    assert ws.import_project(source, '.')


def test_symlinks_and_unregistered_projects_rejected(tmp_path):
    source = project(tmp_path / 'source')
    ws = WorkspaceStore(tmp_path / 'work', registered=[source])
    (source / 'src/linked.cj').symlink_to(source / 'src/a.cj')
    with pytest.raises(ValueError):
        ws.import_project(source, '.')
    with pytest.raises(ValueError):
        ws.import_project(project(tmp_path / 'other'), '.')


def test_read_outside_baseline_and_changed_baseline_rejected(tmp_path):
    source = project(tmp_path / 'source')
    ws = WorkspaceStore(tmp_path / 'work', registered=[source])
    baseline = ws.import_project(source, '.')
    for path in ('../secret', '/etc/passwd', 'src/../../secret'):
        with pytest.raises(ValueError):
            ws.read_file(baseline, path)
    assert ws.read_file(baseline, 'src/a.cj') == 'package a'
    (ws.subject_path(baseline) / 'src/a.cj').write_text('tampered')
    with pytest.raises(ValueError):
        ws.read_file(baseline, 'src/a.cj')
