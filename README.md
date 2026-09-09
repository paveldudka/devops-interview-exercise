# ECS Release Review — Senior DevOps / Platform Exercise

This private repository contains a 75-minute live exercise centered on reviewing
and improving a proposed AWS ECS release process. It is intentionally small,
synthetic, and fully local: **no AWS account, credentials, backend, state, or
infrastructure are used**.

Start with [CANDIDATE.md](CANDIDATE.md).

## Quick start

The supported environment is the included devcontainer. Open the repository in a
devcontainer, then run:

```bash
make verify-env
make baseline
```

The baseline checks only the repository's formatting, syntax, basic Terraform
model, inactive workflow boundary, and absence of live-cloud dependencies. It
does not grade a candidate's proposed solution, and there is no hidden automated
pass/fail gate.

See [docs/architecture.md](docs/architecture.md) for the model, mocking, and
local-validation boundaries.
