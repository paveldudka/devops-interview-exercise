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
  surrounding network, cluster, and IAM infrastructure already exist and are
  referenced through variables; the container registry is supplied by the
  platform.
- The release workflow is an inactive fixture outside `.github/workflows/`.
- Local validation uses a mocked Terraform provider. It does not access an AWS
  account, credential, remote backend, state, or live deployment.
- For this exercise, assume the surrounding platform provides a runner with the
  required tools, working registry and AWS authentication, registry access,
  Terraform initialization, and remote state. Those platform capabilities work
  as intended and are outside the assessment scope.

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

You may change the release fixture, `infra/`, the worker's `Dockerfile` and
`worker.py`, `tests/`, and `NOTES.md`, and may add focused tests or supporting
code. Keep the workflow inactive and do not add AWS credentials, a remote
backend, or a real deployment path.

## Timing (75 minutes)

- 15 minutes: assess the proposal and prioritize your findings without AI.
- 35 minutes: implement and validate one focused improvement.
- 10 minutes: respond to an additional change or scenario from the interviewer.
- 15 minutes: AI-free walkthrough and defense.

## Setup and baseline

Use the included devcontainer. Docker with BuildKit plus a devcontainer-capable
editor or CLI are the only host prerequisites; initial setup should take under
10 minutes. The devcontainer's post-create step installs the Python
dependencies, runs `make init` to download the Terraform AWS provider (no
credentials are needed), and then runs `make verify-env`. The 75-minute timer
starts only after that setup and `make verify-env` have succeeded, so the
provider download never counts against your time.

```bash
make verify-env  # confirm the supported toolchain is ready
make baseline    # check formatting, syntax, and the local model boundaries
make test        # run every Python and Terraform test, including yours
```

The baseline must remain green. `make test` runs every Python test under
`tests/` and every Terraform test file directly in `infra/` or `infra/tests/`
(Terraform does not discover nested directories), including any you add, and
fails if none run; explain their evidence and limitations. Terraform test files
must declare an unaliased `mock_provider "aws"`. You may update supporting
files (the Makefile, `scripts/`, the supplied tests, the devcontainer,
`pytest.ini`) when your change calls for it, and should explain why. Python
dependencies are hash-pinned in `requirements.lock`; adding one means
regenerating that file. Terraform must stay local: no backend, cloud block,
import or provisioner blocks, JSON syntax, or data sources that read live AWS
state (the client-rendered `aws_iam_policy_document` is fine). There is no
hidden automated pass/fail gate for a preferred solution.

## AI and documentation policy

The initial 15-minute assessment and prioritization phase is AI-free. You may use
AI tools and public documentation during the 35-minute implementation phase
only. Record in `NOTES.md` what you used, notable suggestions you accepted or
rejected, and how you verified them. You are accountable for every submitted
line. The interviewer change and final walkthrough are also AI-free.

## Submission

Commit your changes and be ready to show:

- your prioritized assessment in `NOTES.md`;
- the focused implementation and its rationale;
- the validation you ran and its limits;
- your rollout, rollback, residual risks, and next steps; and
- any incomplete work or assumptions.
