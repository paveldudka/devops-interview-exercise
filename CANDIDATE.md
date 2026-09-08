# Candidate brief

## The task

[`exercise/release.yml`](exercise/release.yml) releases a worker to AWS ECS
through staging and then production. A recent release passed staging, yet
production ran different application bytes. Make the smallest coherent change to
the release workflow and the Terraform module in `infra/` so that production
only ever receives the exact artifact staging validated, any failure stops
promotion, production changes never run concurrently, and Terraform refuses an
image reference that is not immutable. Validate the change locally and be ready
to explain how you would roll it out, how you would roll back, and what remains
unproven.

## What the starter does today

- builds the container separately for staging and for production;
- deploys a mutable image reference to both;
- can carry on after a failed command; and
- lets two production releases run at the same time.

## Outcomes the checks verify

`make acceptance` fails on the starter and passes once all of these hold:

1. One release builds the image once.
2. Staging and production deploy the same immutable reference to that image.
3. Production starts only after staging succeeded, and no failure along the way
   can be ignored.
4. A second production release waits for the first and never cancels it.
5. `terraform test` proves the module rejects tags and bare image names
   (see [`infra/tests/immutable_image.tftest.hcl`](infra/tests/immutable_image.tftest.hcl)).

All checks are visible and static; there are no hidden tests. Job, step, output,
and variable names are yours to choose. [docs/architecture.md](docs/architecture.md)
describes what the checks can observe and what they cannot prove.

## Boundaries

- The workflow is an inactive fixture. Keep it outside `.github/workflows/`.
- Everything is mocked. Add no credentials, remote backend, or real deployment.
  `example.invalid` never resolves: author build, push, and deploy steps, but do
  not run them.
- You may change `exercise/release.yml`, `infra/`, and `NOTES.md`, and add
  tests. Do not weaken or remove the supplied checks.
- Prefer a small, explainable change over breadth.

## Timing (75 minutes)

- 10 minutes: read the repository and ask questions.
- 40 minutes: implement and validate.
- 10 minutes: respond to an additional requirement from the interviewer.
- 15 minutes: AI-free walkthrough and defense.

## Setup and commands

Use the included devcontainer (Docker plus a devcontainer-capable editor or CLI
are the only host prerequisites; setup takes under 10 minutes).

```bash
make verify-env   # confirm the pinned tools are available
make baseline     # must stay green
make acceptance   # fails on the starter
make check        # baseline plus acceptance; passes when you are done
```

## AI and documentation policy

You may use AI tools and public documentation while implementing. Record in
`NOTES.md` which tools you used, notable suggestions you accepted or rejected,
and how you verified them. You are accountable for every submitted line, and the
final walkthrough is AI-free.

## Submission

Commit your changes and be ready to show:

- the diff;
- output from `make check`;
- `NOTES.md` with approach, validation, rollout, rollback, residual risks, and
  AI use; and
- anything incomplete, plus the assumptions you made.
