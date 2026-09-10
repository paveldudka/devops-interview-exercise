"""Regression tests for the boundary checks themselves."""

from pathlib import Path

import pytest

from boundary import (
    find_live_automation,
    find_live_automation_in_repository,
    find_secrets,
    find_terraform_live_declarations,
    find_unmocked_terraform_tests,
)

# Built at runtime so this file never contains a credential-shaped literal.
FAKE_ACCESS_KEY = "AKIA" + "EXAMPLEKEY123456"
FAKE_PRIVATE_KEY = "-----BEGIN " + "RSA PRIVATE KEY-----"


@pytest.mark.parametrize(
    "snippet",
    [
        "terraform -chdir=infra apply -auto-approve",
        "terragrunt run-all apply",
        "docker push example.invalid/worker:1",
        "docker image push example.invalid/worker:1",
        "docker buildx build --push -t example.invalid/worker:1 .",
        "docker buildx build \\\n  -t example.invalid/worker:1 \\\n  --push .",
        "aws ecs update-service --cluster c --service s",
        "aws ecr get-login-password | docker login --password-stdin r",
        "kubectl rollout restart deployment/worker",
        "helm upgrade --install worker ./chart",
        "      - uses: aws-actions/configure-aws-credentials@v4",
        "      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2",
        "      - uses: docker/build-push-action@v6\n        with:\n          push: true",
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
        "      - uses: actions/checkout@v4",
        "      - uses: docker/build-push-action@v6\n        with:\n          push: false",
    ],
)
def test_local_automation_is_allowed(snippet: str) -> None:
    assert find_live_automation(snippet) == []


def test_repository_scan_reports_the_offending_automation_file(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "deploy.yml").write_text("run: terraform apply\n", encoding="utf-8")
    (tmp_path / "Makefile").write_text("deploy:\n\tdocker push x\n", encoding="utf-8")
    (tmp_path / "exercise.yml").write_text("run: terraform apply\n", encoding="utf-8")

    findings = find_live_automation_in_repository(tmp_path)

    assert findings == [
        ".github/workflows/deploy.yml: terraform apply",
        "Makefile: docker push",
    ]


def test_secret_scan_covers_any_text_file(tmp_path: Path) -> None:
    (tmp_path / "config.txt").write_text(f"key={FAKE_ACCESS_KEY}\n", encoding="utf-8")
    (tmp_path / "id_rsa").write_text(f"{FAKE_PRIVATE_KEY}\nabc\n", encoding="utf-8")
    (tmp_path / "clean.md").write_text("nothing here\n", encoding="utf-8")
    (tmp_path / "image.bin").write_bytes(b"\0" + FAKE_ACCESS_KEY.encode())

    assert find_secrets(tmp_path) == [
        "config.txt: AWS access key id",
        "id_rsa: private key",
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
    (tmp_path / "main.tf").write_text(
        'terraform {\n  backend "s3" {}\n}\n', encoding="utf-8"
    )
    (nested / "lookup.tf").write_text(
        'data "aws_caller_identity" "me" {}\n', encoding="utf-8"
    )
    (nested / "state.tf").write_text(
        'data "terraform_remote_state" "net" {}\n', encoding="utf-8"
    )
    (tmp_path / "clean.tf").write_text(
        'resource "aws_ecs_service" "w" {}\n', encoding="utf-8"
    )

    assert find_terraform_live_declarations(tmp_path) == [
        "main.tf: backend block",
        "modules/worker/lookup.tf: data source",
        "modules/worker/state.tf: data source",
        "modules/worker/state.tf: remote state",
    ]


def test_terraform_tests_must_mock_the_provider(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "mocked.tftest.hcl").write_text(
        'mock_provider "aws" {}\nrun "a" { command = plan }\n', encoding="utf-8"
    )
    (tests / "real.tftest.hcl").write_text(
        'provider "aws" {}\nrun "a" { command = plan }\n', encoding="utf-8"
    )

    assert find_unmocked_terraform_tests(tmp_path) == [
        'tests/real.tftest.hcl: missing mock_provider "aws"',
        "tests/real.tftest.hcl: declares a real aws provider",
    ]
