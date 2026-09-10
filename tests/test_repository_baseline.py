from pathlib import Path

import pytest

from boundary import (
    ROOT,
    find_live_automation_in_repository,
    find_secrets,
    find_terraform_live_declarations,
    find_undiscoverable_terraform_tests,
    find_unmocked_terraform_tests,
    terraform_files,
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
    assert (ROOT / "Makefile").is_file()
    findings = find_live_automation_in_repository(ROOT)
    assert findings == [], (
        "live deployment commands, actions, or publishing inputs are not allowed "
        "outside YAML fixtures under exercise/, Python files under tests/, and "
        "Markdown. This is a plain-text scan with comments, HCL quoted strings, "
        "and heredocs removed, so reword other prose "
        "or move it to Markdown. Symlinks and a GNUmakefile/makefile are rejected "
        "outright:\n" + "\n".join(findings)
    )


@pytest.mark.baseline
def test_terraform_model_exists_and_stays_local() -> None:
    infra = ROOT / "infra"
    assert terraform_files(infra, "*.tf"), "infra/ must contain the Terraform model"
    assert terraform_files(infra, "*.tf.json") == [], "use HCL, not JSON"
    assert terraform_files(infra, "*.tftest.json") == [], "use HCL, not JSON"
    assert find_terraform_live_declarations(ROOT) == []


@pytest.mark.baseline
def test_terraform_tests_are_discoverable_and_mocked() -> None:
    infra = ROOT / "infra"
    assert terraform_files(infra, "*.tftest.hcl"), "infra/tests must contain a test"
    assert find_undiscoverable_terraform_tests(infra) == []
    assert find_unmocked_terraform_tests(infra) == []


@pytest.mark.baseline
def test_repository_contains_no_credential_values() -> None:
    assert find_secrets(ROOT) == []
