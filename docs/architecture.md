# Architecture and test boundary

## What is modeled

The repository models only the release decision boundary:

- a GitHub Actions workflow builds and promotes a worker image;
- a Terraform module renders an ECS Fargate task definition and service; and
- external infrastructure is supplied through variables.

The VPC, ECS cluster, IAM roles, ECR repository, load balancer, and DNS are
intentionally absent. They do not contribute useful signal to this exercise.

## What is mocked

Terraform's native `mock_provider "aws"` replaces provider behavior during
`terraform test`. The workflow is parsed and evaluated by visible local policy
tests. Neither path authenticates to AWS, reads AWS data sources, maintains state,
or applies resources. `exercise/release.yml` is outside `.github/workflows`, so
GitHub never registers or executes it.

## Starter baseline

Before candidate changes, the baseline checks provide evidence that:

- the Terraform configuration is syntactically and structurally valid;
- the task definition receives the image reference supplied to the module;
- the release fixture cannot be executed automatically; and
- the repository contains no credential-shaped values.

## Solution acceptance

After the exercise is solved, the acceptance checks provide evidence that one
digest-derived build output is passed to both Terraform deployment commands,
production waits for staging, production releases are serialized, common
failure-swallowing patterns are absent, and the Terraform input rejects mutable
image references. These are static policy checks, not a deployment simulation.

## What the tests cannot prove

These local checks do not prove that AWS permissions are correct, an ECS rollout
will stabilize, health checks reflect application readiness, the container runs,
or rollback is safe under real traffic. A production rollout still needs an
isolated staging deployment, observability, bounded waits, failure handling, and
a tested rollback procedure. Candidates should call out this boundary rather
than representing a mocked plan as deployment proof.
