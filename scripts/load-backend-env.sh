#!/usr/bin/env bash
# Load backend/.env safely (handles special chars in DATABASE_URL).
set -euo pipefail

ENV_FILE="${1:-backend/.env}"

if [ ! -f "$ENV_FILE" ]; then
  return 0 2>/dev/null || exit 0
fi

eval "$(
  python3 - "$ENV_FILE" <<'PY'
import shlex
import sys
from pathlib import Path

path = Path(sys.argv[1])
for raw in path.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    key, _, value = line.partition("=")
    key = key.strip()
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    print(f"export {key}={shlex.quote(value)}")
PY
)"
