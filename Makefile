SHELL := /usr/bin/env bash

.PHONY: verify-env init format-check baseline acceptance check

verify-env:
	@./scripts/verify-env.sh

init:
	@terraform -chdir=infra init -backend=false -input=false

format-check:
	@terraform fmt -check -recursive infra
	@actionlint -color exercise/release.yml .github/workflows/ci.yml
	@python -m compileall -q tests

baseline: init format-check
	@terraform -chdir=infra validate
	@terraform -chdir=infra test -filter=tests/baseline.tftest.hcl
	@python -m pytest -q -m baseline

acceptance: init
	@python -m pytest -q -m acceptance

check: baseline acceptance
