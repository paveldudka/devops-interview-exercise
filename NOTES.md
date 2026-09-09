# Reference solution notes

This is a worked example, not the only acceptable solution.

## Prioritized assessment

| Priority | Risk | Impact | Evidence |
| --- | --- | --- | --- |
| 1 | Staging and production do not share an artifact identity | Production can run bytes that staging never validated | Each deploy job rebuilds source and applies `:latest` |
| 2 | Failures do not reliably stop promotion | A failed build or deployment can be followed by production work | `continue-on-error` and `|| true` discard failures |
| 3 | Production releases can overlap | Concurrent applies and ECS rollouts can race | The production job has no stable concurrency group |
| 4 | Terraform accepts mutable image references | Other callers can bypass workflow-level safeguards | `image_ref` has no validation |

## Chosen improvement and rationale

Artifact integrity is the highest-impact boundary: production should receive the
exact registry content staging validated. The reference implements that fix and
the closely coupled promotion safeguards as one coherent release path.

## Implementation

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

## Residual risks and next steps

Static checks cannot prove registry push behavior, AWS permissions, container
health, or traffic safety. Next add bounded ECS stabilization and application
health gates, then exercise the path in an isolated environment with telemetry.

## AI and documentation use

The assessment and prioritization were completed without AI. AI assistance was
used only during implementation to draft and review this synthetic reference.
Suggestions were checked against the reference-only evaluator and local
commands; the author remains accountable for the final code and documented
boundaries.
