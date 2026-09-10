# Architecture and validation boundary

## What is modeled

This repository contains only the release decision boundary:

- an inactive GitHub Actions workflow fixture for releasing a worker through
  staging and production;
- a Terraform module that renders an ECS Fargate task definition and service;
  and
- references to existing external infrastructure supplied through variables.

The VPC, ECS cluster, IAM roles, container registry, load balancer, DNS, and
application dependencies are intentionally outside the model.

## Supplied-platform assumptions

Assume the surrounding platform provides a runner with the required tools,
working registry and AWS authentication, registry access, Terraform
initialization, and remote state. Those capabilities work as intended and their
setup is outside the assessment scope.

## What is mocked or inactive

Terraform's native `mock_provider "aws"` replaces provider behavior during
`terraform test`. Nothing authenticates to AWS, reads AWS data sources, retains
state, or applies resources. `exercise/release.yml` lives outside
`.github/workflows`, so GitHub does not register or run it. The example registry
hostname does not resolve locally; in the modeled system it stands in for the
reachable registry supplied by the surrounding platform.

## What local validation cannot prove

The supplied baseline checks formatting, syntax, basic Terraform rendering, and
the repository's local-only boundaries: the fixture stays outside
`.github/workflows` and `ci.yml` is the only active workflow; no live
deployment, publishing, or cloud-login commands or actions appear in any file
outside `exercise/`, `tests/`, and Markdown (comments and HCL strings are
ignored; symlinks and a `GNUmakefile` or `makefile` are rejected because they
cannot be scanned or would bypass the Makefile); Terraform declares no backend,
cloud block, import, provisioner, remote state, or data source other than
`aws_iam_policy_document`, and uses HCL only; every Terraform test file is
discoverable and mocks the default `aws` provider; and no credential values are
present. `make test` additionally runs every Python test under `tests/` and
every Terraform test file directly in `infra/` or `infra/tests/`. None of this
assesses whether a proposed release design is production-ready or
can demonstrate real registry, GitHub Actions, AWS, ECS, networking,
application, observability, or traffic behavior. Candidates should explain the
evidence their own validation provides and the uncertainty that remains.
