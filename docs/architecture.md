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

## What the tests prove

The tests provide evidence that:

- the Terraform configuration is syntactically and structurally valid;
- the task definition receives the image reference supplied to the module;
- mutable image references are rejected by the module;
- one build output is passed unchanged to staging and production;
- production depends on successful staging;
- production releases are serialized rather than cancelled mid-deployment; and
- common failure-swallowing patterns are absent.

## What the tests cannot prove

These local checks do not prove that AWS permissions are correct, an ECS rollout
will stabilize, health checks reflect application readiness, the container runs,
or rollback is safe under real traffic. A production rollout still needs an
isolated staging deployment, observability, bounded waits, failure handling, and
a tested rollback procedure. Candidates should call out this boundary rather
than representing a mocked plan as deployment proof.
