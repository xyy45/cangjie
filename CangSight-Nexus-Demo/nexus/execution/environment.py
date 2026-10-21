"""Local read-only readiness, never a model/API health probe."""
from pathlib import Path
from scripts.doctor import inspect_environment
from nexus.adapters.cangjie.sdk import MACOS_SDK
from nexus.policy.client import PolicyClient


def readiness() -> dict:
    report=inspect_environment()
    missing=[]
    if report['sdk']['state']!='available' or not MACOS_SDK.is_dir():
        missing.append(dict(code='SDK_NOT_READY',message='仓颉 SDK 未就绪，请安装固定工具链和 macOS 15.4 开发 SDK。'))
    try:
        PolicyClient(Path(__file__).resolve().parents[2]).component_identity()
    except (OSError,ValueError,KeyError):
        missing.append(dict(code='POLICY_NOT_READY',message='仓颉策略程序未就绪，请先编译 Policy。'))
    if not all(report['model_config'].values()):
        missing.append(dict(code='MODEL_NOT_CONFIGURED',message='模型未配置，请在本机 .env 填写获准配置。'))
    return dict(ready=not missing,missing=missing,model_connectivity='NOT_PROBED',
                compiler_version=report['sdk']['tools']['cjc']['version'],
                package_manager_version=report['sdk']['tools']['cjpm']['version'])
