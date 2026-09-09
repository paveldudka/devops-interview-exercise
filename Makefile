SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

.PHONY: verify-env init format-check baseline acceptance check

verify-env:
	@./scripts/verify-env.sh

init:
	@terraform -chdir=infra init -backend=false -input=false

format-check:
	@terraform fmt -check -recursive infra
	@actionlint -color exercise/release.yml .github/workflows/ci.yml
	@python -m ruff check tests
	@python -m ruff format --check tests
	@python -m pytest --collect-only -q >/dev/null

baseline: init format-check
	@terraform -chdir=infra validate
	@test -f infra/tests/baseline.tftest.hcl
	@terraform -chdir=infra test -filter=tests/baseline.tftest.hcl
	@python -m pytest -q -m baseline

# Confidential evaluator targets; these do not exist on the candidate branch.
acceptance: init
	@python -m pytest -q -m acceptance

check: baseline acceptance
