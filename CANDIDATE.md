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
deployment.

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

All executable checks are visible. They verify outcomes and a few documented
workflow contracts; there are no hidden tests.

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

You may change `exercise/release.yml`, `infra/`, and supporting documentation or
tests when justified. Do not move the release fixture into `.github/workflows/`.

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
