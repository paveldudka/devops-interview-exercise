# Safe ECS Release — Senior DevOps / Platform Exercise

This private repository contains a 75-minute live exercise about making an unsafe
AWS ECS release process operationally safe. It is intentionally small, synthetic,
and fully local: **no AWS account, credentials, backend, state, or infrastructure
are used**.

Start with [CANDIDATE.md](CANDIDATE.md).

## Quick start

The supported environment is the included devcontainer. Open the repository in a
devcontainer, then run:

```bash
make verify-env
make baseline
make acceptance
```

`make baseline` must pass on the starter branch. `make acceptance` is expected to
fail until the exercise is solved; every acceptance check is visible in
`tests/release_policy.py`, `tests/test_release_acceptance.py`, and
`infra/tests/immutable_image.tftest.hcl`.

See [docs/architecture.md](docs/architecture.md) for the test boundary and
mocking model.
