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
    monkeypatch.setattr('nexus.execution.environment.NativePolicyClient.component_identity',stale)
    result=readiness()
    assert result['ready'] is False
    assert any(item['code']=='POLICY_NOT_READY' for item in result['missing'])
    assert result['model_connectivity']=='NOT_PROBED'


def test_readiness_requires_active_core_even_when_legacy_policy_is_healthy(monkeypatch):
    from nexus.execution.environment import readiness
    for key,value in dict(DEEPSEEK_API_KEY='test-placeholder',DEEPSEEK_BASE_URL='https://fixture.invalid',DEEPSEEK_MODEL='test-model').items():
        monkeypatch.setenv(key,value)
    def unavailable(self):raise ValueError('core missing')
    monkeypatch.setattr('nexus.policy.core.NativeCoreClient.component_identity',unavailable)
    report=readiness()
    assert any(item['code']=='POLICY_NOT_READY' for item in report['missing'])
    assert report['ready'] is False


def test_doctor_exposes_verified_core_version_and_build_instruction_without_api_probe():
    report=inspect_environment()
    assert report['core']['state']=='available'
    assert report['core']['version']=='2.0'
    assert len(report['core']['component']['core_component_hash'])==64
    assert report['core']['repair_command']=='python scripts/build_core.py'
    assert report['model_connectivity']=='NOT_PROBED'
