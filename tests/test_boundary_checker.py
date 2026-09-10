"""Regression tests for the boundary checks themselves."""

from pathlib import Path

import pytest

from boundary import (
    find_live_automation,
    find_live_automation_in_repository,
    find_secrets,
    find_terraform_live_declarations,
    find_undiscoverable_terraform_tests,
    find_unmocked_terraform_tests,
)

# Built at runtime so this file never contains a credential-shaped literal.
FAKE_ACCESS_KEY = "AKIA" + "EXAMPLEKEY123456"
FAKE_PRIVATE_KEY = "-----BEGIN " + "RSA PRIVATE KEY-----"


@pytest.mark.parametrize(
    "snippet",
    [
        "terraform -chdir=infra apply -auto-approve",
        "terraform -chdir=infra \\\n  apply -auto-approve",
        "terragrunt run-all apply",
        "docker push example.invalid/worker:1",
        "docker image push example.invalid/worker:1",
        "docker compose push",
        "podman push example.invalid/worker:1",
        "crane push image.tar example.invalid/worker:1",
        "skopeo copy docker-archive:w.tar docker://example.invalid/worker:1",
        "docker buildx build --push -t example.invalid/worker:1 .",
        "docker buildx build \\\n  -t example.invalid/worker:1 \\\n  --push .",
        "docker buildx build --output=type=registry -t example.invalid/worker:1 .",
        "aws ecs update-service --cluster c --service s",
        "aws ecr get-login-password | docker login --password-stdin r",
        "kubectl rollout restart deployment/worker",
        "helm upgrade --install worker ./chart",
        "      - uses: aws-actions/configure-aws-credentials@v4",
        "      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2",
        "      - uses: docker/build-push-action@v6\n        with:\n          push: true",
        "          push: True",
        "          push: true # publish",
        "          push: ${{ github.event_name != 'pull_request' }}",
        "run: docker build . && docker push x # not a comment",
        "curl https://example.invalid//x && docker push y",
    ],
)
def test_live_automation_is_detected(snippet: str) -> None:
    assert find_live_automation(snippet)


@pytest.mark.parametrize(
    "snippet",
    [
        "terraform -chdir=infra init -backend=false",
        "terraform -chdir=infra validate",
        "terraform -chdir=infra test -filter=tests/baseline.tftest.hcl",
        "terraform -chdir=infra plan -var-file=staging.tfvars",
        "docker build -t example.invalid/worker:1 .",
        "docker buildx build --load -t example.invalid/worker:1 .",
        "on:\n  push:\n    branches: [main]",
        "on:\n  push: # only main\n    branches: [main]",
        "on:\n  push: { branches: [main] }",
        "on: [push, pull_request]",
        "      - uses: actions/checkout@v4",
        "      - uses: docker/build-push-action@v6\n        with:\n          push: false",
        "          push: false # local only",
        "          push: false\r\n",
        "# never docker push from here\nbuild:\n\tdocker build .",
        "docker build . # CI runs terraform apply only after approval",
        "// terraform apply happens elsewhere",
    ],
)
def test_local_automation_is_allowed(snippet: str) -> None:
    assert find_live_automation(snippet) == []


@pytest.mark.parametrize(
    "snippet",
    [
        'description = "Digest pinned by docker push in CI"',
        'error_message = "terraform apply must never see a mutable tag"',
        '# terraform apply is the platform\'s job\nimage = "x"',
    ],
)
def test_hcl_prose_is_allowed(snippet: str) -> None:
    assert find_live_automation(snippet, hcl=True) == []


def test_hcl_command_outside_strings_is_detected() -> None:
    snippet = 'run "x" {\n  command = apply\n}\nlocal-exec terraform apply\n'
    assert find_live_automation(snippet, hcl=True) == ["terraform apply"]


def test_repository_scan_covers_all_but_fixture_prose_and_tests(
    tmp_path: Path,
) -> None:
    for relative in [
        ".github/workflows/deploy.yml",
        "Makefile",
        "deploy/apply.sh",
        "exercise/release.yml",
        "exercise/apply.sh",
        "README.md",
        "tests/test_release.py",
        "tests/deploy.sh",
    ]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("run: terraform apply\n", encoding="utf-8")
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "note.tf").write_text(
        'variable "x" {\n  description = "set by terraform apply in CI"\n}\n',
        encoding="utf-8",
    )

    assert find_live_automation_in_repository(tmp_path) == [
        ".github/workflows/deploy.yml: terraform apply",
        "Makefile: terraform apply",
        "deploy/apply.sh: terraform apply",
    ]


def test_repository_scan_flags_make_overrides_and_symlinks(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("baseline:\n\t@true\n", encoding="utf-8")
    (tmp_path / "GNUmakefile").write_text("baseline:\n\t@true\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "outside").mkdir()
    (tmp_path / "scripts" / "elsewhere").symlink_to(tmp_path / "outside")

    assert find_live_automation_in_repository(tmp_path) == [
        "GNUmakefile: overrides Makefile targets",
        "scripts/elsewhere: symlink",
    ]


def test_repository_scan_decodes_non_utf8_and_utf16_files(tmp_path: Path) -> None:
    (tmp_path / "latin.sh").write_bytes(b'echo "d\xe9ploy"\nterraform apply\n')
    (tmp_path / "wide.ps1").write_bytes("terraform apply\n".encode("utf-16"))

    assert find_live_automation_in_repository(tmp_path) == [
        "latin.sh: terraform apply",
        "wide.ps1: terraform apply",
    ]


def test_secret_scan_covers_any_file(tmp_path: Path) -> None:
    (tmp_path / "config.txt").write_text(f"key={FAKE_ACCESS_KEY}\n", encoding="utf-8")
    (tmp_path / "id_rsa").write_text(f"{FAKE_PRIVATE_KEY}\nabc\n", encoding="utf-8")
    (tmp_path / "blob.bin").write_bytes(b"\0\xff" + FAKE_ACCESS_KEY.encode())
    (tmp_path / "wide.txt").write_bytes(FAKE_ACCESS_KEY.encode("utf-16"))
    (tmp_path / "clean.yml").write_text(
        "env:\n  AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}\n"
        f"  short: {FAKE_ACCESS_KEY[:-1]}\n  lower: {FAKE_ACCESS_KEY.lower()}\n",
        encoding="utf-8",
    )

    assert find_secrets(tmp_path) == [
        "blob.bin: AWS access key id",
        "config.txt: AWS access key id",
        "id_rsa: private key",
        "wide.txt: AWS access key id",
    ]


def test_secret_scan_ignores_generated_directories_by_relative_path(
    tmp_path: Path,
) -> None:
    # The checkout itself may live under a directory named like an ignored one.
    root = tmp_path / ".venv" / "checkout"
    (root / ".venv").mkdir(parents=True)
    (root / ".terraform").mkdir()
    (root / ".venv" / "site.py").write_text(FAKE_ACCESS_KEY, encoding="utf-8")
    (root / ".terraform" / "plugin").write_text(FAKE_ACCESS_KEY, encoding="utf-8")
    (root / "notes.md").write_text(FAKE_ACCESS_KEY, encoding="utf-8")

    assert find_secrets(root) == ["notes.md: AWS access key id"]


def test_terraform_live_declarations_are_found_recursively(tmp_path: Path) -> None:
    nested = tmp_path / "modules" / "worker"
    nested.mkdir(parents=True)
    vendored = tmp_path / ".terraform" / "modules" / "x"
    vendored.mkdir(parents=True)
    (tmp_path / "main.tf").write_text(
        'terraform {\n  backend "s3" {}\n}\n', encoding="utf-8"
    )
    (nested / "lookup.tf").write_text(
        'data "aws_caller_identity" "me" {}\n', encoding="utf-8"
    )
    (nested / "state.tf").write_text(
        'data "terraform_remote_state" "net" {}\n', encoding="utf-8"
    )
    (tmp_path / "clean.tf").write_bytes(
        b'# d\xe9ploy\n# backend "s3" {}\n'
        b'data "aws_iam_policy_document" "assume" {}\n'
        b'resource "aws_ecs_service" "w" {}\n'
    )
    (vendored / "main.tf").write_text('backend "s3" {}\n', encoding="utf-8")

    assert find_terraform_live_declarations(tmp_path) == [
        "main.tf: backend block",
        "modules/worker/lookup.tf: data source",
        "modules/worker/state.tf: data source",
        "modules/worker/state.tf: remote state",
    ]


def test_terraform_tests_must_mock_the_default_provider(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "mocked.tftest.hcl").write_text(
        'mock_provider "aws" {\n  # alias = "commented"\n}\nrun "a" { command = plan }\n',
        encoding="utf-8",
    )
    (tests / "aliased.tftest.hcl").write_text(
        'mock_provider "aws" {\n  alias = "other"\n}\n', encoding="utf-8"
    )
    (tests / "real.tftest.hcl").write_text(
        'provider "aws" {}\nrun "a" { command = plan }\n', encoding="utf-8"
    )

    assert find_unmocked_terraform_tests(tmp_path) == [
        'tests/aliased.tftest.hcl: missing mock_provider "aws"',
        'tests/real.tftest.hcl: missing mock_provider "aws"',
        "tests/real.tftest.hcl: declares a real aws provider",
    ]


def test_nested_terraform_tests_are_reported(tmp_path: Path) -> None:
    (tmp_path / "tests" / "deep").mkdir(parents=True)
    (tmp_path / "root.tftest.hcl").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "top.tftest.hcl").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "deep" / "hidden.tftest.hcl").write_text("", encoding="utf-8")

    assert find_undiscoverable_terraform_tests(tmp_path) == [
        "tests/deep/hidden.tftest.hcl"
    ]
