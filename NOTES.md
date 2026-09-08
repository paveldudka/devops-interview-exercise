# Reference solution notes

This is a worked example, not the only acceptable solution.

## Approach

- Build and push exactly once, then export the registry digest as `image_ref`.
- Pass that output to both environments. Production waits for staging and uses
  stable concurrency that queues rather than cancels releases.
- Validate the Terraform module boundary so tags and bare names fail at plan time.

## Validation

`make baseline`, `make acceptance`, and `make check`. No AWS command, provider
call, or deployment was executed; the workflow remains an inactive fixture.

## Rollout and rollback

Wait for ECS service stability and application health with bounded timeouts, then
record the promoted digest. Rollback selects a previously recorded known-good
digest and uses the same serialized deployment path; it never rebuilds source.

## Residual risks

Static checks cannot prove registry push behavior, AWS permissions, container
health, or traffic safety. Those require an isolated environment and telemetry.

## AI and documentation use

AI assistance helped draft and review this synthetic reference. Suggestions were
checked against visible tests and local commands; the author remains accountable
for the final code and documented boundaries.
