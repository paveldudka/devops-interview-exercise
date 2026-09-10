from pathlib import Path

import pytest

from boundary import (
    ROOT,
    find_live_automation_in_repository,
    find_secrets,
    find_terraform_live_declarations,
    find_unmocked_terraform_tests,
    is_ignored,
)


@pytest.mark.baseline
def test_release_fixture_is_outside_active_workflows() -> None:
    fixture = ROOT / "exercise" / "release.yml"
    active_workflows = (ROOT / ".github" / "workflows").resolve()
    assert fixture.is_file()
    assert active_workflows not in fixture.resolve().parents


@pytest.mark.baseline
def test_only_repository_validation_is_an_active_workflow() -> None:
    workflows = ROOT / ".github" / "workflows"
    active_files = sorted(
        path.relative_to(workflows) for path in workflows.rglob("*") if path.is_file()
    )
    assert active_files == [Path("ci.yml")]


@pytest.mark.baseline
def test_executable_automation_has_no_live_deployment_path() -> None:
    assert find_live_automation_in_repository(ROOT) == []


@pytest.mark.baseline
def test_terraform_model_exists_and_stays_local() -> None:
    infra = ROOT / "infra"
    configuration = [
        path for path in infra.rglob("*.tf") if not is_ignored(path, infra)
    ]
    assert configuration, "infra/ must contain the Terraform model"
    assert not list(infra.rglob("*.tf.json")), "use HCL, not JSON, for Terraform"
    assert find_terraform_live_declarations(infra) == []


@pytest.mark.baseline
def test_terraform_tests_use_the_mock_provider() -> None:
    infra = ROOT / "infra"
    assert list(infra.rglob("*.tftest.hcl")), "infra/tests must contain a test"
    assert find_unmocked_terraform_tests(infra) == []


@pytest.mark.baseline
def test_repository_contains_no_credential_values() -> None:
    assert find_secrets(ROOT) == []
