SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

.PHONY: verify-env init format-check baseline test

verify-env:
	@./scripts/verify-env.sh

init:
	@terraform -chdir=infra init -backend=false -input=false

format-check:
	@terraform fmt -check -recursive infra
	@actionlint -color exercise/release.yml .github/workflows/ci.yml
	@python -m ruff check .
	@python -m ruff format --check .
	@python -m pytest --collect-only -qq

# Supplied environment and boundary proof. Not a solution grade.
# pytest exits non-zero when the baseline marker selects nothing.
baseline: init format-check
	@terraform -chdir=infra validate
	@python scripts/run_terraform_tests.py -filter=tests/baseline.tftest.hcl
	@python -m pytest -q -m baseline

# Every Python test under tests/ and every Terraform test under infra/tests.
test: init
	@python scripts/run_terraform_tests.py
	@python -m pytest -q
