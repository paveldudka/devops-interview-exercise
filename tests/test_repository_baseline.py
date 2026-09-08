from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.baseline
def test_release_fixture_is_not_an_active_workflow() -> None:
    fixture = (ROOT / "exercise" / "release.yml").resolve()
    active_workflows = (ROOT / ".github" / "workflows").resolve()
    assert active_workflows not in fixture.parents


@pytest.mark.baseline
def test_release_fixture_has_no_automatic_trigger() -> None:
    workflow = yaml.load(
        (ROOT / "exercise" / "release.yml").read_text(), Loader=yaml.BaseLoader
    )
    assert set(workflow["on"]) == {"workflow_dispatch"}


@pytest.mark.baseline
def test_terraform_has_no_remote_backend_or_aws_data_sources() -> None:
    terraform = "\n".join(path.read_text() for path in (ROOT / "infra").glob("*.tf"))
    assert 'backend "' not in terraform
    assert 'data "aws_' not in terraform


@pytest.mark.baseline
def test_repository_contains_no_credential_values() -> None:
    text_suffixes = {".md", ".py", ".tf", ".hcl", ".yaml", ".yml"}
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
    content = "\n".join(path.read_text() for path in text_files)
    assert "AK" + "IA" not in content
    assert "aws_secret" + "_access_key" not in content.lower()
