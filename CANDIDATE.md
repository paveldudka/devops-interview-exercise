# Candidate brief

## The task

This repository models a proposed AWS ECS release process. Assess whether it is
ready for production, document and prioritize the material risks you find, then
implement one focused improvement you believe delivers the most value. Validate
your change and explain your rollout and rollback approach, the risks that
remain, and what you would address next.

You are not expected to find or fix every issue. We evaluate the quality of your
judgment, prioritization and rationale, implementation, validation, and
communication—not the number of findings or lines changed.

## System context

- [`exercise/release.yml`](exercise/release.yml) models a GitHub Actions release
  of a worker through staging and production.
- [`infra/`](infra/) models the relevant ECS task definition and service. The
  surrounding network, cluster, IAM, and registry infrastructure already exist
  and are supplied as variables.
- The release workflow is an inactive fixture outside `.github/workflows/`.
- Everything runs locally with a mocked Terraform provider. There is no AWS
  account, credential, remote backend, state, or live deployment.

See [docs/architecture.md](docs/architecture.md) for the model and validation
boundaries.

## Deliverables

1. Use [`NOTES.md`](NOTES.md) to record and prioritize the material risks you
   find. Include impact and repository evidence for each finding.
2. Choose one focused improvement, explain why it is the best use of the
   implementation time, and implement it.
3. Validate your change. Explain what your checks prove and what they cannot
   prove.
4. Describe how you would roll the change out, roll it back, and address the
   most important residual risks.

You may change `exercise/release.yml`, `infra/`, and `NOTES.md`, and may add
focused tests or supporting code. Keep the workflow inactive and do not add AWS
credentials, a remote backend, or a real deployment path.

## Timing (75 minutes)

- 15 minutes: assess the proposal and prioritize your findings.
- 35 minutes: implement and validate one focused improvement.
- 10 minutes: respond to an additional change or scenario from the interviewer.
- 15 minutes: AI-free walkthrough and defense.

## Setup and baseline

Use the included devcontainer. Docker plus a devcontainer-capable editor or CLI
are the only host prerequisites; initial setup should take under 10 minutes.

```bash
make verify-env  # confirm the supported toolchain is available
make baseline    # check formatting, syntax, and the local model boundaries
```

The baseline must remain green. You may add your own focused tests and should
explain their evidence and limitations. There is no hidden automated pass/fail
gate for a preferred solution; interviewer-only evaluator checks are evidence
aids, not a hidden contract.

## AI and documentation policy

You may use AI tools and public documentation during the assessment and
implementation phases. Record in `NOTES.md` what you used, notable suggestions
you accepted or rejected, and how you verified them. You are accountable for
every submitted line, and the final walkthrough is AI-free.

## Submission

Commit your changes and be ready to show:

- your prioritized assessment in `NOTES.md`;
- the focused implementation and its rationale;
- the validation you ran and its limits;
- your rollout, rollback, residual risks, and next steps; and
- any incomplete work or assumptions.
