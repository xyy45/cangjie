"""Read-only local environment probe; never calls the model."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


LOCAL_SDK = Path(__file__).resolve().parents[1] / ".runtime/sdk/cangjie"

def inspect_environment() -> dict[str, object]:
    tools = {}
    for name in ("cjc", "cjpm"):
        local = LOCAL_SDK / ("tools/bin" if name == "cjpm" else "bin") / name
        path = str(local) if local.is_file() else shutil.which(name)
        item = {"path": path, "version": None, "state": "unavailable"}
        if path:
            try:
                result = subprocess.run([path, "--version"], capture_output=True,
                                        text=True, timeout=5, env={"PATH": f"{LOCAL_SDK}/bin:{LOCAL_SDK}/tools/bin:/usr/bin:/bin",
                                        "HOME": str(LOCAL_SDK.parents[1] / "home"),
                                        "DYLD_LIBRARY_PATH": str(LOCAL_SDK / "runtime/lib/darwin_aarch64_cjnative")})
                item["version"] = (result.stdout + result.stderr).strip()
                item["state"] = "available" if result.returncode == 0 else "unavailable"
            except (OSError, subprocess.TimeoutExpired):
                pass
        tools[name] = item
    from dotenv import dotenv_values
    local_config = dotenv_values(Path(__file__).resolve().parents[1] / '.env')
    configured = lambda key: bool(os.getenv(key) or local_config.get(key))
    from nexus.policy.core import NativeCoreClient,VERSION
    core=dict(state='unavailable',version=VERSION,component=None,repair_command='python scripts/build_core.py')
    try:core.update(state='available',component=NativeCoreClient().component_identity())
    except (OSError,ValueError,KeyError):pass
    return {
        "core": core,
        "model_connectivity": "NOT_PROBED",
        "python": {"path": sys.executable, "version": platform.python_version()},
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "sdk": {"state": "available" if all(t["state"] == "available" for t in tools.values())
                else "unavailable", "tools": tools},
        "model_config": {"api_key_present": configured('DEEPSEEK_API_KEY'),
                         "base_url_present": configured('DEEPSEEK_BASE_URL'),
                         "model_present": configured('DEEPSEEK_MODEL')},
    }


if __name__ == "__main__":
    # The direct script entry has scripts/ rather than the project on sys.path.
    # Keep inspect_environment unchanged for existing readiness consumers.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import argparse
    from nexus.deployment.checks import inspect
    parser = argparse.ArgumentParser(description='Read-only local installation checks; no model requests')
    parser.add_argument('--provider', choices=['deepseek', 'rule'], default='deepseek')
    parser.add_argument('--port', type=int, default=8877)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    report = inspect(provider=args.provider, port=args.port)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['ready'] else 1)
