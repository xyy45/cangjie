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
    return {
        "python": {"path": sys.executable, "version": platform.python_version()},
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "sdk": {"state": "available" if all(t["state"] == "available" for t in tools.values())
                else "unavailable", "tools": tools},
        "model_config": {"api_key_present": configured('DEEPSEEK_API_KEY'),
                         "base_url_present": configured('DEEPSEEK_BASE_URL'),
                         "model_present": configured('DEEPSEEK_MODEL')},
    }


if __name__ == "__main__":
    print(json.dumps(inspect_environment(), indent=2))
