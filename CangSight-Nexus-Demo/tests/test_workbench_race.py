"""Run controlled async races against the actual plain-JS workbench in Node."""
from pathlib import Path
import shutil
import subprocess


def test_workbench_async_response_races():
    node = shutil.which('node')
    assert node, 'Node.js 18+ is required for the workbench race tests (no npm install)'
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, '--test', 'tests/workbench-race.test.cjs','tests/operator-auth.test.cjs'], cwd=root,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
