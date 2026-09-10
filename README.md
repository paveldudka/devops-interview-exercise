# ECS Release Review — Senior DevOps / Platform Exercise

This repository contains a 75-minute live exercise centered on reviewing
and improving a proposed AWS ECS release process. It is intentionally small,
synthetic, and fully local: **local validation uses no AWS account, credentials,
backend, state, or infrastructure**.

Start with [CANDIDATE.md](CANDIDATE.md).

## Quick start

The supported environment is the included devcontainer. Open the repository in a
devcontainer, then run:

```bash
make verify-env
make baseline
make test
```

The devcontainer's post-create step installs dependencies and initializes the
Terraform provider before `make verify-env` runs. The baseline checks only the
repository's formatting, syntax, basic Terraform model, inactive workflow
boundary, and absence of live-cloud dependencies. `make test` runs every Python
test under `tests/` and every Terraform test file in `infra/` or `infra/tests/`,
including candidate-authored ones. Neither grades a candidate's proposed
solution, and there is no hidden automated pass/fail gate.

See [docs/architecture.md](docs/architecture.md) for the model, mocking, and
local-validation boundaries.
