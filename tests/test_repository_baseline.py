import re
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_WORKFLOW_COMMAND = re.compile(
    r"\b(?:terraform(?:\s+-\S+)*\s+apply|docker\s+(?:image\s+)?push|"
    r"aws\s+ecs\s+(?:update-service|register-task-definition)|"
    r"kubectl\s+(?:apply|rollout)|helm\s+(?:install|upgrade))\b",
    re.IGNORECASE,
)


@pytest.mark.baseline
def test_release_fixture_is_not_an_active_workflow() -> None:
    fixture = (ROOT / "exercise" / "release.yml").resolve()
    active_workflows = (ROOT / ".github" / "workflows").resolve()
    assert active_workflows not in fixture.parents


@pytest.mark.baseline
def test_only_repository_validation_is_an_active_workflow() -> None:
    workflows = ROOT / ".github" / "workflows"
    active_files = sorted(
        path.relative_to(workflows)
        for path in workflows.rglob("*")
        if path.is_file() and path.suffix in {".yaml", ".yml"}
    )
    assert active_files == [Path("ci.yml")]

    validation = (workflows / "ci.yml").read_text(encoding="utf-8")
    assert ACTIVE_WORKFLOW_COMMAND.search(validation) is None


@pytest.mark.baseline
def test_release_fixture_has_no_automatic_trigger() -> None:
    workflow = yaml.load(
        (ROOT / "exercise" / "release.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert set(workflow["on"]) == {"workflow_dispatch"}


@pytest.mark.baseline
def test_terraform_has_no_remote_backend_or_aws_data_sources() -> None:
    terraform = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "infra").glob("*.tf")
    )
    assert 'backend "' not in terraform
    assert 'data "aws_' not in terraform


@pytest.mark.baseline
def test_repository_contains_no_credential_values() -> None:
    text_suffixes = {
        ".env",
        ".hcl",
        ".json",
        ".md",
        ".py",
        ".sh",
        ".tf",
        ".tfvars",
        ".yaml",
        ".yml",
    }
    ignored_directories = {
        ".git",
        ".pytest_cache",
        ".terraform",
        ".venv",
        "__pycache__",
    }
    text_files = [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix in text_suffixes
        and ignored_directories.isdisjoint(path.parts)
    ]
    content = "\n".join(path.read_text(encoding="utf-8") for path in text_files)
    assert not re.search(r"(?:AK|AS)IA[0-9A-Z]{16}", content)
    assert not re.search(r"gh[pousr]_[A-Za-z0-9]{20,}", content)
