import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "exercise" / "release.yml"
DIGEST_EXPRESSION = re.compile(r"needs\.[^.]+\.outputs\.image_ref")


def load_workflow() -> dict[str, Any]:
    return yaml.load(WORKFLOW_PATH.read_text(), Loader=yaml.BaseLoader)


def job_for_environment(
    workflow: dict[str, Any], environment: str
) -> tuple[str, dict[str, Any]]:
    matches = [
        (job_id, job)
        for job_id, job in workflow["jobs"].items()
        if job.get("environment") == environment
    ]
    assert len(matches) == 1, f"expected exactly one {environment} deployment job"
    return matches[0]


def rendered_job(job: dict[str, Any]) -> str:
    return yaml.safe_dump(job, sort_keys=True)


@pytest.mark.acceptance
def test_builds_once_and_promotes_one_immutable_artifact() -> None:
    workflow = load_workflow()
    all_steps = [
        step for job in workflow["jobs"].values() for step in job.get("steps", [])
    ]
    build_steps = [
        step for step in all_steps if "docker build" in step.get("run", "")
    ]
    assert len(build_steps) == 1, "the image must be built exactly once"

    output_producers = [
        job
        for job in workflow["jobs"].values()
        if "image_ref" in job.get("outputs", {})
    ]
    assert len(output_producers) == 1, "the build job must publish an image_ref output"
    producer_text = rendered_job(output_producers[0])
    assert "sha256:" in producer_text and "@" in producer_text, (
        "image_ref must be captured as a repository@sha256 digest"
    )

    _, staging = job_for_environment(workflow, "staging")
    _, production = job_for_environment(workflow, "production")
    staging_refs = set(DIGEST_EXPRESSION.findall(rendered_job(staging)))
    production_refs = set(DIGEST_EXPRESSION.findall(rendered_job(production)))
    assert len(staging_refs) == 1
    assert staging_refs == production_refs, (
        "staging and production must consume the same build output"
    )


@pytest.mark.acceptance
def test_mutable_image_tags_are_not_deployed() -> None:
    workflow = load_workflow()
    for environment in ("staging", "production"):
        _, job = job_for_environment(workflow, environment)
        job_text = rendered_job(job)
        assert ":latest" not in job_text, f"{environment} still deploys a mutable tag"
        assert DIGEST_EXPRESSION.search(job_text), (
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

    concurrency = production.get("concurrency")
    assert isinstance(concurrency, dict), "production needs an explicit concurrency policy"
    assert concurrency.get("group"), "production concurrency must define a stable group"
    assert concurrency.get("cancel-in-progress") == "false", (
        "an in-progress production deployment must not be cancelled"
    )


@pytest.mark.acceptance
def test_failures_cannot_silently_promote() -> None:
    workflow_text = WORKFLOW_PATH.read_text()
    workflow = load_workflow()
    assert "|| true" not in workflow_text
    for job_id, job in workflow["jobs"].items():
        assert job.get("continue-on-error") != "true", f"{job_id} ignores failures"
        for step in job.get("steps", []):
            assert step.get("continue-on-error") != "true", (
                f"{job_id} step {step.get('name', '<unnamed>')} ignores failures"
            )


@pytest.mark.acceptance
def test_terraform_rejects_mutable_image_references() -> None:
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
    assert result.returncode == 0, result.stdout + result.stderr
