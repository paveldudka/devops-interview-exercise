import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "exercise" / "release.yml"
DIGEST_EXPRESSION = re.compile(r"needs\.[^.]+\.outputs\.image_ref")
BUILD_COMMAND = re.compile(r"\bdocker\s+(?:build|buildx\s+build)\b")
IGNORED_FAILURE = re.compile(r"\|\|\s*(?:true|:|exit\s+0)\b|\bset\s+\+e\b")


def load_workflow() -> dict[str, Any]:
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def environment_name(job: dict[str, Any]) -> str | None:
    environment = job.get("environment")
    if isinstance(environment, dict):
        return environment.get("name")
    return environment


def job_for_environment(
    workflow: dict[str, Any], environment: str
) -> tuple[str, dict[str, Any]]:
    matches = [
        (job_id, job)
        for job_id, job in workflow["jobs"].items()
        if environment_name(job) == environment
    ]
    assert len(matches) == 1, f"expected exactly one {environment} deployment job"
    return matches[0]


def rendered_job(job: dict[str, Any]) -> str:
    return yaml.safe_dump(job, sort_keys=True)


def terraform_apply_text(job: dict[str, Any]) -> str:
    commands = [
        step.get("run", "")
        for step in job.get("steps", [])
        if re.search(r"\bterraform\b.*\bapply\b", step.get("run", ""), re.DOTALL)
    ]
    assert commands, "deployment jobs must pass image_ref to a terraform apply command"
    return "\n".join(commands)


@pytest.mark.acceptance
def test_builds_once_and_promotes_one_immutable_artifact() -> None:
    workflow = load_workflow()
    all_steps = [
        step for job in workflow["jobs"].values() for step in job.get("steps", [])
    ]
    build_steps = [
        step
        for step in all_steps
        if BUILD_COMMAND.search(step.get("run", ""))
        or step.get("uses", "").startswith("docker/build-push-action@")
    ]
    assert len(build_steps) == 1, (
        "the image must be built exactly once (docker build/buildx or "
        "docker/build-push-action)"
    )

    output_producers = [
        job
        for job in workflow["jobs"].values()
        if "image_ref" in job.get("outputs", {})
    ]
    assert len(output_producers) == 1, "the build job must publish an image_ref output"
    producer_text = rendered_job(output_producers[0]).lower()
    assert "digest" in producer_text or "repodigests" in producer_text, (
        "image_ref must be derived from a registry digest"
    )

    _, staging = job_for_environment(workflow, "staging")
    _, production = job_for_environment(workflow, "production")
    staging_refs = set(DIGEST_EXPRESSION.findall(terraform_apply_text(staging)))
    production_refs = set(DIGEST_EXPRESSION.findall(terraform_apply_text(production)))
    assert len(staging_refs) == 1
    assert staging_refs == production_refs, (
        "staging and production must consume the same build output"
    )


@pytest.mark.acceptance
def test_mutable_image_tags_are_not_deployed() -> None:
    workflow = load_workflow()
    for environment in ("staging", "production"):
        _, job = job_for_environment(workflow, environment)
        apply_text = terraform_apply_text(job)
        assert ":latest" not in apply_text, f"{environment} still deploys a mutable tag"
        assert DIGEST_EXPRESSION.search(apply_text), (
            f"{environment} must deploy the immutable build output"
        )


@pytest.mark.acceptance
def test_production_waits_for_staging_and_serializes_releases() -> None:
    workflow = load_workflow()
    staging_id, _ = job_for_environment(workflow, "staging")
    _, production = job_for_environment(workflow, "production")
    needs = production.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    assert staging_id in needs, "production must depend on successful staging"

    condition = str(production.get("if", "")).lower()
    assert "always()" not in condition, "production must not run after staging fails"

    concurrency = production.get("concurrency")
    assert concurrency, "production needs an explicit concurrency policy"
    group = concurrency.get("group") if isinstance(concurrency, dict) else concurrency
    assert group, "production concurrency must define a stable group"
    assert not re.search(r"github\.(?:run_id|run_number|run_attempt)", str(group)), (
        "production concurrency group must be stable across workflow runs"
    )
    cancel_in_progress = (
        concurrency.get("cancel-in-progress", "false")
        if isinstance(concurrency, dict)
        else "false"
    )
    assert str(cancel_in_progress).lower() == "false", (
        "an in-progress production deployment must not be cancelled"
    )


@pytest.mark.acceptance
def test_failures_cannot_silently_promote() -> None:
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    workflow = load_workflow()
    assert not IGNORED_FAILURE.search(workflow_text)
    for job_id, job in workflow["jobs"].items():
        assert str(job.get("continue-on-error", "false")).lower() == "false", (
            f"{job_id} ignores failures"
        )
        for step in job.get("steps", []):
            assert str(step.get("continue-on-error", "false")).lower() == "false", (
                f"{job_id} step {step.get('name', '<unnamed>')} ignores failures"
            )


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
    assert 'run "rejects_mutable_image"... pass' in result.stdout
