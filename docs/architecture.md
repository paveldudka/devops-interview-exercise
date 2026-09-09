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
the repository's local-only boundaries. They do not assess whether a proposed
release design is production-ready and cannot demonstrate real registry,
GitHub Actions, AWS, ECS, networking, application, observability, or traffic
behavior. Candidates should explain the evidence their own validation provides
and the uncertainty that remains.
