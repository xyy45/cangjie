#!/bin/zsh
set -eu
DEMO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$DEMO_ROOT"
if [[ -x "$DEMO_ROOT/.venv/bin/python" ]]; then
  DEMO_PYTHON="$DEMO_ROOT/.venv/bin/python"
else
  DEMO_PYTHON="$(command -v python3)"
fi
exec "$DEMO_PYTHON" -m nexus.demo.app --port 8877
