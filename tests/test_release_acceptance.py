"""Visible acceptance checks. Each one fails on the starter for one unsafe property.

The checks are static: see docs/architecture.md for what they observe and
what they cannot prove.
"""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from release_policy import (
    check_failures_stop_promotion,
    check_image_is_built_once,
    check_production_does_not_race,
    check_same_immutable_artifact,
    parse_workflow,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "exercise" / "release.yml"


@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    return parse_workflow(WORKFLOW_PATH.read_text(encoding="utf-8"))


@pytest.mark.acceptance
def test_image_is_built_once(workflow: dict[str, Any]) -> None:
    check_image_is_built_once(workflow)


@pytest.mark.acceptance
def test_staging_and_production_deploy_the_same_immutable_artifact(
    workflow: dict[str, Any],
) -> None:
    check_same_immutable_artifact(workflow)


@pytest.mark.acceptance
def test_failures_stop_promotion(workflow: dict[str, Any]) -> None:
    check_failures_stop_promotion(workflow)


@pytest.mark.acceptance
def test_production_deployments_do_not_race(workflow: dict[str, Any]) -> None:
    check_production_does_not_race(workflow)


@pytest.mark.acceptance
def test_terraform_rejects_mutable_image_references() -> None:
    test_file = ROOT / "infra" / "tests" / "immutable_image.tftest.hcl"
    assert test_file.is_file(), "immutable image Terraform test is missing"
    try:
        result = subprocess.run(
            [
                "terraform",
                f"-chdir={ROOT / 'infra'}",
                "test",
                "-filter=tests/immutable_image.tftest.hcl",
                "-no-color",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        pytest.fail("terraform is missing; run this exercise in the devcontainer")
    assert result.returncode == 0, result.stdout + result.stderr
