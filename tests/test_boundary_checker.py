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
SECRET_KEY_SETTING = "aws_secret" + "_access_key"


def fake_secret_key(last: str) -> str:
    return "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKE" + last


@pytest.mark.parametrize(
    "snippet",
    [
        "terraform -chdir=infra apply -auto-approve",
        "terraform -chdir=infra \\\n  apply -auto-approve",
        "terragrunt run-all apply",
        'subprocess.run(["terraform", "-chdir=infra", "apply", "-auto-approve"])',
        "run(['terraform', 'destroy'])",
        'check_call(("tofu",  "-chdir=infra",  "import", "a.b", "c"))',
        "docker push example.invalid/worker:1",
        "docker image push example.invalid/worker:1",
        "docker compose push",
        "podman push example.invalid/worker:1",
        "crane push image.tar example.invalid/worker:1",
        "skopeo copy docker-archive:w.tar docker://example.invalid/worker:1",
        "docker buildx build --push -t example.invalid/worker:1 .",
        "docker buildx build \\\n  -t example.invalid/worker:1 \\\n  --push .",
        "docker buildx build --output=type=registry -t example.invalid/worker:1 .",
        "docker buildx build -o type=image,push=true .",
        "docker --config /tmp/x login r",
        "aws ecs update-service --cluster c --service s",
        "aws --profile prod ecs update-service --cluster c --service s",
        "aws --region us-west-2 --no-cli-pager ecs run-task --cluster c",
        "aws ecr get-login-password | docker login --password-stdin r",
        "aws --region us-west-2 ecr get-login-password",
        "aws ecr-public get-login-password",
        "aws --profile prod deploy create-deployment",
        "kubectl rollout restart deployment/worker",
        "kubectl --context prod -n workers rollout restart deployment/worker",
        "kubectl --kubeconfig=/tmp/k apply -f deploy.yml",
        "helm upgrade --install worker ./chart",
        "helm --kube-context prod -n workers upgrade --install worker ./chart",
        "helm --namespace workers install worker ./chart",
        "      - uses: aws-actions/configure-aws-credentials@v4",
        "      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2",
        "      - uses: docker/build-push-action@v6\n        with:\n          push: true",
        "          push: True",
        "          push: true # publish",
        "          push: ${{ github.event_name != 'pull_request' }}",
        "          push: >-\n            true",
        "          push: &p true",
        "run: docker build . && docker push x # not a comment",
        'run: echo "build #1" && docker push x',
        "run: echo 'build #1' && docker push x",
        'run: echo "it\'s #1" && docker push x',
        '@echo "### deploying ###" && terraform -chdir=infra apply -auto-approve',
        'echo "#" && terraform apply',
        'echo "unterminated # terraform apply',
        "# build then push \\\n  docker push x",
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
        'subprocess.run(["terraform", "-chdir=infra", "validate"])',
        'subprocess.run(["terraform", "-chdir=infra", "test", "-json"])',
        "docker build -t example.invalid/worker:1 .",
        "docker buildx build --load -t example.invalid/worker:1 .",
        "aws --region us-west-2 ecs describe-services --cluster c",
        "aws --profile prod sts get-caller-identity",
        "kubectl --context prod get pods",
        "kubectl -n workers describe deployment/worker",
        "helm -n workers list",
        "helm --kube-context prod template worker ./chart",
        "on:\n  push:\n    branches: [main]",
        "on:\n  push: # only main\n    branches: [main]",
        "on:\n  push: { branches: [main] }",
        "on: [push, pull_request]",
        "      - uses: actions/checkout@v4",
        "      - uses: docker/build-push-action@v6\n        with:\n          push: false",
        "          push: false # local only",
        "          push: false\r\n",
        "          push: no",
        "# never docker push from here\nbuild:\n\tdocker build .",
        "docker build . # see the runbook before any terraform apply",
        "echo ${#args} # then terraform apply",
        'echo "built" # then terraform apply',
        "echo 'built' # then docker push x",
        'echo "it\'s built" # then docker push x',
        "run: echo 'it''s built' # then docker push x",
        'name: "release" # docker push happens elsewhere',
        "CFLAGS = -O2 # terraform apply is manual",
        '\t@echo "done" # docker push is manual',
        "echo \\# && echo ok # terraform apply",
        'echo "a" && echo "b" # docker push x',
    ],
)
def test_local_automation_is_allowed(snippet: str) -> None:
    assert find_live_automation(snippet) == []


@pytest.mark.parametrize(
    "snippet",
    [
        'description = "the platform team runs docker push"',
        'error_message = "terraform apply runs on the platform runner"',
        'error_message = "run terraform apply # only via the platform"',
        'description = "build #1, never terraform apply"',
        'image = "x" # terraform apply happens elsewhere',
        'image = "x" // docker push happens elsewhere',
        'image = "${var.image == "x" ? "a" : "b"}" # terraform apply',
        '# terraform apply is the platform\'s job\nimage = "x"',
        "// terraform apply happens elsewhere",
        "/*\n  The platform runs terraform apply for us.\n*/",
        'image = "x" /* terraform apply */',
        'description = <<-EOT\n  ops run terraform apply in CI\nEOT\nimage = "x"',
        'description = <<EOT\n  # not a comment, docker push prose\nEOT\nimage = "x"',
    ],
)
def test_hcl_prose_is_allowed(snippet: str) -> None:
    assert find_live_automation(snippet, hcl=True) == []


@pytest.mark.parametrize(
    "snippet",
    [
        'run "x" {\n  command = apply\n}\nlocal-exec terraform apply\n',
        'a = "/*"\nlocal-exec terraform apply\nb = "*/"\n',
        'a = "x" # /*\nlocal-exec terraform apply\n# */\n',
        'a = "unterminated\nlocal-exec terraform apply\n',
        "a = <<EOT\nnever closed\nlocal-exec terraform apply\n",
    ],
)
def test_hcl_command_outside_strings_is_detected(snippet: str) -> None:
    assert find_live_automation(snippet, hcl=True) == ["terraform apply"]


def test_repository_scan_exempts_only_fixture_test_sources_and_prose(
    tmp_path: Path,
) -> None:
    for relative in [
        ".github/workflows/deploy.yml",
        "Makefile",
        "deploy/apply.sh",
        "exercise/release.yml",
        "exercise/reusable.yaml",
        "exercise/apply.sh",
        "exercise/Makefile",
        "README.md",
        "tests/test_release.py",
        "tests/helpers/deploy.py",
        "tests/deploy.sh",
        "tests/fixtures/deploy.yml",
    ]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("run: terraform apply\n", encoding="utf-8")
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "note.tf").write_text(
        'variable "x" {\n  description = "set by terraform apply on the runner"\n}\n',
        encoding="utf-8",
    )

    assert find_live_automation_in_repository(tmp_path) == [
        ".github/workflows/deploy.yml: terraform apply",
        "Makefile: terraform apply",
        "deploy/apply.sh: terraform apply",
        "exercise/Makefile: terraform apply",
        "exercise/apply.sh: terraform apply",
        "tests/deploy.sh: terraform apply",
        "tests/fixtures/deploy.yml: terraform apply",
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


def test_lowercase_makefile_is_matched_by_exact_name(tmp_path: Path) -> None:
    (tmp_path / "makefile").write_text("baseline:\n\t@true\n", encoding="utf-8")
    assert find_live_automation_in_repository(tmp_path) == [
        "makefile: overrides Makefile targets"
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


@pytest.mark.parametrize("last", ["Y", "=", "+", "/"])
@pytest.mark.parametrize(
    "template",
    [
        "{setting} = {value}\n",
        "{setting}: {value}",
        '{setting} = "{value}"\n',
        "{setting}={value}\r\n",
    ],
)
def test_secret_key_values_are_found_whatever_their_last_character(
    tmp_path: Path, template: str, last: str
) -> None:
    (tmp_path / "creds").write_text(
        template.format(setting=SECRET_KEY_SETTING, value=fake_secret_key(last)),
        encoding="utf-8",
    )
    assert find_secrets(tmp_path) == ["creds: AWS secret access key"]


@pytest.mark.parametrize(
    "value",
    ["${{ secrets.AWS_SECRET_ACCESS_KEY }}", fake_secret_key("")[:39], "x" * 41],
)
def test_secret_key_placeholders_and_wrong_lengths_are_allowed(
    tmp_path: Path, value: str
) -> None:
    (tmp_path / "creds").write_text(
        f"{SECRET_KEY_SETTING} = {value}\n", encoding="utf-8"
    )
    assert find_secrets(tmp_path) == []


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
    (nested / "ship.tf").write_text(
        'resource "null_resource" "ship" {\n  provisioner "local-exec" {\n'
        '    command = "echo"\n  }\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "clean.tf").write_bytes(
        b'# d\xe9ploy\n# backend "s3" {}\n/*\nbackend "s3" {}\n*/\n'
        b'data "aws_iam_policy_document" "assume" {}\n'
        b'resource "aws_ecs_service" "w" {\n'
        b'  description = "no terraform_remote_state here"\n}\n'
    )
    (vendored / "main.tf").write_text('backend "s3" {}\n', encoding="utf-8")

    assert find_terraform_live_declarations(tmp_path) == [
        "main.tf: backend block",
        "modules/worker/lookup.tf: data source",
        "modules/worker/ship.tf: provisioner",
    ]


@pytest.mark.parametrize(
    ("content", "label"),
    [
        ('a = "/*"\nbackend "s3" {}\nb = "*/"\n', "backend block"),
        ('a = "/*"\ncloud {}\nb = "*/"\n', "cloud block"),
        ('a = "/*"\ndata "aws_caller_identity" "me" {}\nb = "*/"\n', "data source"),
        ('a = "/*"\nimport {}\nb = "*/"\n', "import block"),
        ('a = "/*"\nprovisioner "local-exec" {}\nb = "*/"\n', "provisioner"),
        ('a = "x" # /*\nimport {}\n# */\n', "import block"),
        ('a = "unterminated /*\nimport {}\n', "import block"),
    ],
)
def test_comment_markers_inside_strings_do_not_hide_declarations(
    tmp_path: Path, content: str, label: str
) -> None:
    (tmp_path / "main.tf").write_text(content, encoding="utf-8")
    assert find_terraform_live_declarations(tmp_path) == [f"main.tf: {label}"]


def test_terraform_tests_must_mock_the_default_provider(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "mocked.tftest.hcl").write_text(
        'mock_provider "aws" {\n  # alias = "commented"\n}\nrun "a" { command = plan }\n',
        encoding="utf-8",
    )
    (tests / "mocked_nested.tftest.hcl").write_text(
        'mock_provider "aws" {\n  mock_data "aws_caller_identity" {\n'
        '    defaults = {\n      alias = "not a provider alias"\n    }\n  }\n}\n',
        encoding="utf-8",
    )
    (tests / "aliased.tftest.hcl").write_text(
        'mock_provider "aws" {\n  alias = "other"\n}\n', encoding="utf-8"
    )
    (tests / "aliased_after_nested.tftest.hcl").write_text(
        'mock_provider "aws" {\n  mock_data "aws_caller_identity" {\n'
        '    defaults = {\n      account_id = "123456789012"\n    }\n  }\n'
        '  alias = "other"\n}\n',
        encoding="utf-8",
    )
    (tests / "aliased_inline.tftest.hcl").write_text(
        'mock_provider "aws" { alias = "}" }\n', encoding="utf-8"
    )
    (tests / "real.tftest.hcl").write_text(
        'provider "aws" {}\nrun "a" { command = plan }\n', encoding="utf-8"
    )

    assert find_unmocked_terraform_tests(tmp_path) == [
        'tests/aliased.tftest.hcl: missing mock_provider "aws"',
        'tests/aliased_after_nested.tftest.hcl: missing mock_provider "aws"',
        'tests/aliased_inline.tftest.hcl: missing mock_provider "aws"',
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
