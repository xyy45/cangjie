"""Configuration loading only: synthetic values, no HTTP/model requests."""
import subprocess
import pytest
from pathlib import Path

from nexus.llm.provider import ModelProvider
from nexus.store import RunStore

KEYS = ('DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_MODEL')


def configured_root(tmp_path, monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    (tmp_path / '.env').write_text(
        'DEEPSEEK_API_KEY=synthetic-not-a-key\n'
        'DEEPSEEK_BASE_URL=https://example.invalid\n'
        'DEEPSEEK_MODEL=synthetic-config-model\n')
    monkeypatch.setattr('nexus.llm.provider.ROOT', tmp_path)
    store = RunStore(tmp_path / 'runs')
    task = store.create_task('base', 'configuration test', ['src/a.cj'])
    return store, task


def test_dotenv_loads_from_project_root_independent_of_cwd(tmp_path, monkeypatch):
    store, task = configured_root(tmp_path, monkeypatch)
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    provider = ModelProvider(store, task.id)
    assert provider.key == 'synthetic-not-a-key'
    assert provider.url == 'https://example.invalid'
    assert provider.model == 'synthetic-config-model'
    assert store.records(task.id, 'model_call') == []


def test_explicit_environment_takes_precedence_over_dotenv(tmp_path, monkeypatch):
    store, task = configured_root(tmp_path, monkeypatch)
    monkeypatch.setenv('DEEPSEEK_MODEL', 'environment-config-model')
    assert ModelProvider(store, task.id).model == 'environment-config-model'


def assert_dotenv_excluded(root):
    # Release directories have no Git metadata; their exclusion rule still applies.
    rules = (root / '.gitignore').read_text().splitlines()
    assert '.env' in [line.strip() for line in rules], '.env exclusion rule missing'
    if (root / '.git').exists():
        result = subprocess.run(['git', 'check-ignore', '--no-index', '.env'],
                                cwd=root, capture_output=True, text=True)
        assert result.returncode == 0 and result.stdout.strip() == '.env'
        tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', '.env'],
                                 cwd=root, capture_output=True, text=True)
        assert tracked.returncode == 1, '.env is tracked or Git check failed'


def test_project_dotenv_is_excluded():
    assert_dotenv_excluded(Path(__file__).resolve().parents[1])


def test_release_exclusion_without_git_metadata(tmp_path, monkeypatch):
    (tmp_path / '.gitignore').write_text('.env\n')
    (tmp_path / '.env').write_text('synthetic local configuration')
    def no_git(*args, **kwargs):
        raise AssertionError('release-directory check must not require Git')
    monkeypatch.setattr(subprocess, 'run', no_git)
    assert_dotenv_excluded(tmp_path)
    (tmp_path / '.gitignore').write_text('.runtime/\n')
    with pytest.raises(AssertionError, match='exclusion rule missing'):
        assert_dotenv_excluded(tmp_path)


def test_real_git_check_rejects_force_tracked_dotenv(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / '.gitignore').write_text('.env\n')
    (tmp_path / '.env').write_text('synthetic-not-a-key')
    assert_dotenv_excluded(tmp_path)
    subprocess.run(['git', 'add', '-f', '.env'], cwd=tmp_path, check=True)
    with pytest.raises(AssertionError, match='is tracked'):
        assert_dotenv_excluded(tmp_path)
