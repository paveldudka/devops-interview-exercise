# Candidate brief

## Scenario

The repository models a worker deployed to AWS ECS through GitHub Actions. The
release workflow in [`exercise/release.yml`](exercise/release.yml) rebuilds the
container for each environment, deploys a mutable image tag, permits overlapping
production releases, and can continue promotion after a failed command.

A recent release passed staging, but production received different application
bytes. Make the **smallest practical change** that ensures production receives
the exact artifact tested in staging and that releases fail safely.

The workflow is an inactive fixture, not a registered GitHub Actions workflow.
All AWS behavior is mocked. Do not add credentials, a remote backend, or a real
deployment. `example.invalid` is deliberately fictional: author the build, push,
and deployment steps, but do not execute them during the interview.

## Acceptance criteria

1. Build the container once and expose one immutable `repository@sha256:...`
   artifact reference.
2. Pass that exact reference through staging and production without rebuilding.
3. Ensure a production deployment only starts after staging succeeds.
4. Prevent overlapping production releases without cancelling an in-progress
   production deployment.
5. Ensure build or deployment failures cannot be ignored while promotion
   continues.
6. Keep the developer workflow and implementation straightforward.
7. Make the Terraform module reject tags and bare image names; it should accept
   only digest-qualified image references.

All executable checks are visible; there are no hidden tests. To keep static
validation deterministic, retain one staging job, one production job, and a
single producer for a job output named `image_ref`. Both deployment jobs must
pass that output to their `terraform apply` command. The tests accept either
shell-based Docker builds or `docker/build-push-action`, scalar or mapped GitHub
environments, and equivalent safe concurrency policies.

## Timing

- 10 minutes: inspect the repository and ask clarifying questions.
- 40 minutes: implement and validate a focused solution. Prioritize working,
  explainable changes over breadth.
- 10 minutes: respond to an additional requirement from the interviewer.
- 15 minutes: AI-free walkthrough and defense.

## Setup and commands

Use the included devcontainer (Docker and a devcontainer-capable editor/CLI are
the only host prerequisites). Setup should take less than 10 minutes on a normal
connection.

```bash
make verify-env   # confirm the pinned tools are available
make baseline     # must remain green
make acceptance   # expected to fail before your changes
make check        # baseline plus acceptance; should pass when finished
```

You may change `exercise/release.yml`, `infra/`, and supporting documentation.
You may add tests, but do not weaken or remove the supplied checks. Do not move
the release fixture into `.github/workflows/`.

## AI and documentation policy

During implementation you may use AI tools and public documentation. Keep a short
record in `NOTES.md` of the tools you used, important suggestions you accepted or
rejected, validation performed, rollout and rollback approach, and residual
risks. You remain responsible for every submitted line.

The final walkthrough and defense are AI-free. The interviewer may ask you to
explain or modify any part of your solution.

## Submission

Commit your changes and be ready to show:

- the diff;
- output from `make baseline` and `make acceptance` (or `make check`);
- `NOTES.md` with rollout, rollback, residual risks, and AI-use notes; and
- any incomplete work or assumptions.
