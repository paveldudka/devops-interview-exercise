#!/usr/bin/env bash
set -euo pipefail

missing=0
for command_name in terraform actionlint python; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "missing required command: ${command_name}" >&2
    missing=1
  fi
done

if [[ "${missing}" -ne 0 ]]; then
  exit 1
fi

terraform_version="$(terraform version -json | python -c 'import json,sys; print(json.load(sys.stdin)["terraform_version"])')"
python - "${terraform_version}" <<'PY'
import sys

version = tuple(int(part) for part in sys.argv[1].split(".")[:2])
if not (1, 7) <= version < (2, 0):
    raise SystemExit(f"Terraform >=1.7,<2.0 is required; found {sys.argv[1]}")
PY

python - <<'PY'
import sys

if not (3, 12) <= sys.version_info[:2] < (3, 13):
    raise SystemExit(f"Python >=3.12,<3.13 is required; found {sys.version.split()[0]}")
try:
    import pytest  # noqa: F401
    import yaml  # noqa: F401
except ImportError as error:
    raise SystemExit(
        "Python dependencies are missing; run: pip install --require-hashes -r requirements.lock"
    ) from error
PY

echo "terraform ${terraform_version}"
actionlint -version
python --version
echo "environment ready"
