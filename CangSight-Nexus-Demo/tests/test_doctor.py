from pathlib import Path
from scripts.doctor import inspect_environment


def test_doctor_missing_sdk_is_unavailable_not_pass(monkeypatch, tmp_path):
    monkeypatch.setattr("scripts.doctor.LOCAL_SDK", tmp_path / "missing")
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("CANGJIE_HOME", raising=False)
    report = inspect_environment()
    assert report["sdk"]["state"] == "unavailable"
    assert "PASS" not in str(report)


def test_doctor_does_not_expose_secrets(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sensitive-test-value")
    report = inspect_environment()
    assert report["model_config"]["api_key_present"] is True
    assert "sensitive-test-value" not in str(report)


def test_readiness_rejects_stale_policy_without_probing_model(monkeypatch):
    from nexus.execution.environment import readiness
    def stale(self):
        raise ValueError('stale native binary')
    monkeypatch.setattr('nexus.execution.environment.PolicyClient.component_identity',stale)
    result=readiness()
    assert result['ready'] is False
    assert any(item['code']=='POLICY_NOT_READY' for item in result['missing'])
    assert result['model_connectivity']=='NOT_PROBED'
