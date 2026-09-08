# Architecture and test boundary

## What is modeled

Only the release decision boundary:

- a GitHub Actions workflow that builds and promotes a worker image;
- a Terraform module that renders an ECS Fargate task definition and service; and
- external infrastructure supplied through variables.

The VPC, ECS cluster, IAM roles, ECR repository, load balancer, and DNS are
intentionally absent. They add no signal to this exercise.

## What is mocked

Terraform's native `mock_provider "aws"` replaces provider behavior during
`terraform test`. Nothing authenticates to AWS, reads AWS data sources, keeps
state, or applies resources. `exercise/release.yml` lives outside
`.github/workflows`, so GitHub never registers or runs it, and `example.invalid`
never resolves.

## How the local checks work

`make baseline` proves the starter is well-formed and safe to hand out:
Terraform validates, actionlint and ruff pass, the mocked module renders the
image reference it is given, the fixture has no automatic trigger, and the
repository holds no credential-shaped values. It also runs the checks of the
checker in `tests/test_release_policy.py`, which pin down what the acceptance
policy accepts and rejects.

`make acceptance` is a static policy over `exercise/release.yml` plus one
Terraform test. The policy in `tests/release_policy.py`:

- parses the workflow and treats every `terraform apply` as a deployment,
  identifying its environment from the tfvars file it passes or the job's
  GitHub environment;
- finds the `image_ref` value each deployment passes (as a `-var` or through
  `TF_VAR_image_ref`) and traces it through workflow expressions, `env`, and job
  and step outputs defined in the file. Values produced at runtime, such as
  variables written to `GITHUB_ENV`, are opaque to it;
- counts image builds, compares the traced references, and inspects job
  ordering, run conditions, error handling, and concurrency settings for the
  observable properties listed in `CANDIDATE.md`.

It does not care what jobs, steps, outputs, or variables are called, or how
many jobs exist.

## What the checks cannot prove

Static checks cannot prove that an image is actually pushed, that a recorded
digest matches the pushed manifest, that AWS permissions are correct, that an
ECS rollout stabilizes, that health checks reflect application readiness, that
the container runs, or that rollback is safe under real traffic. A production
rollout still needs an isolated staging deployment, observability, bounded
waits, failure handling, and a rehearsed rollback. Call out this boundary rather
than presenting a mocked plan as deployment proof.
