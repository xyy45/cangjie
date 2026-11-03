"""Clean installations keep business samples without historical approvals."""
from pathlib import Path
import pytest
from nexus.demo import cases
from nexus.demo.app import create_demo_app


def test_no_historical_data_keeps_all_registered_samples_and_app_routes(tmp_path, monkeypatch):
    monkeypatch.setattr(cases, 'DATA', tmp_path / 'no-history')
    current = cases.load_cases()
    assert set(current) == {row['id'] for row in cases.scenarios()}
    assert all(row['origin'] == 'SAMPLE' and not row['can_replay'] for row in current.values())
    assert all(row['real_files'] for row in current.values())
    app = create_demo_app(tmp_path / 'fresh', provider='rule')
    client = app.test_client()
    assert client.get('/').status_code == 200
    assert client.get('/demo/cases/order').json['origin'] == 'SAMPLE'
    assert client.get('/demo/download/order').status_code == 409


def test_partial_history_never_silently_becomes_a_fresh_sample(tmp_path, monkeypatch):
    monkeypatch.setattr(cases, 'DATA', tmp_path)
    (tmp_path / 'order-live-summary.json').write_text('{}')
    with pytest.raises(ValueError, match='incomplete'):
        cases.load_cases()
