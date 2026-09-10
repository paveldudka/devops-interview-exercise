#!/usr/bin/env bash
set -euo pipefail

missing=0
for command_name in make terraform actionlint python; do
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
import re
import sys

match = re.match(r"(\d+)\.(\d+)", sys.argv[1])
version = tuple(int(part) for part in match.groups()) if match else ()
if not (1, 7) <= version < (2, 0):
    raise SystemExit(f"Terraform >=1.7,<2.0 is required; found {sys.argv[1]}")
PY

python - <<'PY'
import sys

if not (3, 12) <= sys.version_info[:2] < (3, 13):
    raise SystemExit(f"Python >=3.12,<3.13 is required; found {sys.version.split()[0]}")
try:
    import pytest  # noqa: F401
    import ruff  # noqa: F401
    import yaml  # noqa: F401
except ImportError as error:
    raise SystemExit(
        "Python dependencies are missing; run: pip install --require-hashes -r requirements.lock"
    ) from error
PY

python -m ruff --version >/dev/null || {
  echo "ruff is not runnable; run: pip install --require-hashes -r requirements.lock" >&2
  exit 1
}

# The AWS provider download is large; it must not eat into the timed exercise.
# validate is offline; it fails on a missing, partial, or mismatched provider
# and on any configuration error, so show its diagnostics and classify.
if ! validate_output="$(terraform -chdir=infra validate -no-color 2>&1)"; then
  echo "${validate_output}" >&2
  if grep -qiE 'no package for|does not match any of the checksums|missing required provider|\.terraform/providers|terraform init|module not installed' <<<"${validate_output}"; then
    echo "Terraform providers or modules are not initialized; run: make init" >&2
  else
    echo "infra/ does not validate; this looks like a configuration error, see the diagnostics above" >&2
  fi
  exit 1
fi

echo "terraform ${terraform_version}"
actionlint -version | head -n 1
python --version
python -m ruff --version
echo "environment ready"
