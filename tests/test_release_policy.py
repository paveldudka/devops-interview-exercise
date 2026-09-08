"""Checks of the checker: the policy must reject unsafe shapes and accept any
coherent safe one, whatever the job, step, output, or variable names are.

Snippets are deliberately partial. They exercise one tracing or gating rule
each and are not release designs.
"""

from textwrap import dedent
from typing import Any

import pytest

from release_policy import (
    check_failures_stop_promotion,
    check_image_is_built_once,
    check_production_does_not_race,
    check_same_immutable_artifact,
    deployments,
    parse_workflow,
)


def workflow(text: str) -> dict[str, Any]:
    return parse_workflow(dedent(text))


def passes(check: Any, flow: dict[str, Any]) -> bool:
    try:
        check(flow)
    except AssertionError:
        return False
    return True


def promotion(second_run: str) -> dict[str, Any]:
    """A recorded value forwarded through two jobs, three different ways."""
    return workflow(
        f"""
        jobs:
          record:
            outputs:
              handle: ${{{{ steps.note.outputs.handle }}}}
            steps:
              - id: note
                run: echo "handle=registry.invalid/app@${{DIGEST}}" >> "$GITHUB_OUTPUT"
          first:
            needs: record
            outputs:
              forwarded: ${{{{ needs.record.outputs.handle }}}}
            env:
              TF_VAR_image_ref: ${{{{ needs.record.outputs.handle }}}}
            steps:
              - run: terraform -chdir=infra apply -auto-approve -var-file=staging.tfvars
          second:
            needs: first
            environment: production
            env:
              ARTIFACT: ${{{{ needs.first.outputs.forwarded }}}}
            steps:
              - run: {second_run}
        """
    )


@pytest.mark.baseline
@pytest.mark.parametrize(
    "second_run",
    [
        'terraform apply -var-file=production.tfvars -var="image_ref=${ARTIFACT}"',
        "terraform apply -var-file=production.tfvars -var=image_ref=$ARTIFACT",
        "terraform apply -var-file=production.tfvars -var 'image_ref=${{ env.ARTIFACT }}'",
        "terraform apply -var-file=production.tfvars "
        "-var='image_ref=${{ needs.first.outputs.forwarded }}'",
        "terraform apply -var-file=infra/production.tfvars "
        "-var='image_ref=${{ needs.record.outputs.handle }}'",
        "terraform -chdir=infra apply -var image_ref=$ARTIFACT",
    ],
)
def test_traces_one_recorded_value_through_outputs_env_and_shell(
    second_run: str,
) -> None:
    flow = promotion(second_run)
    assert [d.image_ref for d in deployments(flow)] == ["«record/note/handle»"] * 2
    check_same_immutable_artifact(flow)


@pytest.mark.baseline
def test_accepts_a_reference_composed_around_a_recorded_digest() -> None:
    flow = promotion(
        "terraform apply -var-file=production.tfvars "
        '-var="image_ref=registry.invalid/app@${{ needs.record.outputs.handle }}"'
    )
    flow["jobs"]["first"]["env"]["TF_VAR_image_ref"] = (
        "registry.invalid/app@${{ needs.record.outputs.handle }}"
    )
    check_same_immutable_artifact(flow)


@pytest.mark.baseline
@pytest.mark.parametrize(
    ("second_run", "reason"),
    [
        (
            "terraform apply -var-file=production.tfvars "
            "-var='image_ref=registry.invalid/app:${{ github.sha }}'",
            "do not deploy the same",
        ),
        (
            "terraform apply -var-file=production.tfvars "
            "-var='image_ref=registry.invalid/app:${{ needs.record.outputs.handle }}'",
            "do not deploy the same",
        ),
        (
            "terraform apply -var-file=production.tfvars -var=image_ref=$FROM_A_FILE",
            "cannot tell",
        ),
        ("terraform apply -var-file=production.tfvars", "cannot tell"),
        ("terraform plan -var-file=production.tfvars", "no terraform apply"),
    ],
)
def test_rejects_untraceable_or_diverging_references(
    second_run: str, reason: str
) -> None:
    with pytest.raises(AssertionError, match=reason):
        check_same_immutable_artifact(promotion(second_run))


@pytest.mark.baseline
def test_rejects_a_unique_tag_as_the_promoted_identity() -> None:
    flow = promotion(
        "terraform apply -var-file=production.tfvars "
        "-var='image_ref=registry.invalid/app:${{ needs.record.outputs.handle }}'"
    )
    flow["jobs"]["first"]["env"]["TF_VAR_image_ref"] = (
        "registry.invalid/app:${{ needs.record.outputs.handle }}"
    )
    with pytest.raises(AssertionError, match="not an immutable identity"):
        check_same_immutable_artifact(flow)


@pytest.mark.baseline
def test_rejects_a_recorded_value_with_no_digest_behind_it() -> None:
    flow = promotion(
        "terraform apply -var-file=production.tfvars "
        "-var='image_ref=${{ needs.record.outputs.handle }}'"
    )
    flow["jobs"]["record"]["steps"][0]["run"] = (
        'echo "handle=registry.invalid/app@${IDENTITY}" >> "$GITHUB_OUTPUT"'
    )
    with pytest.raises(AssertionError, match="without any sign of the registry digest"):
        check_same_immutable_artifact(flow)


@pytest.mark.baseline
@pytest.mark.parametrize(
    ("build_steps", "ok"),
    [
        (["run: docker build -t registry.invalid/app ."], True),
        (["run: docker buildx build --push -t registry.invalid/app ."], True),
        (["uses: docker/build-push-action@v6"], True),
        (["run: docker build .", "uses: docker/build-push-action@v6"], False),
        (["run: docker pull registry.invalid/app@sha256:abc"], False),
    ],
)
def test_counts_every_way_of_building_the_image(
    build_steps: list[str], ok: bool
) -> None:
    listed = "\n".join(f"      - {step}" for step in build_steps)
    flow = parse_workflow(f"jobs:\n  one:\n    steps:\n{listed}\n")
    assert passes(check_image_is_built_once, flow) is ok


def gated(
    production_needs: str = "verify",
    production_extra: str = "",
    staging_step_extra: str = "",
) -> dict[str, Any]:
    return workflow(
        f"""
        jobs:
          prepare:
            steps:
              - run: echo prepare
          first:
            needs: prepare
            steps:
              - run: terraform apply -var-file=staging.tfvars -var=image_ref=$X
                {staging_step_extra}
          verify:
            needs: first
            steps:
              - run: echo verify
          second:
            needs: {production_needs}
            {production_extra}
            steps:
              - run: terraform apply -var-file=production.tfvars -var=image_ref=$X
        """
    )


@pytest.mark.baseline
def test_transitive_dependency_on_staging_is_enough() -> None:
    check_failures_stop_promotion(gated())


@pytest.mark.baseline
@pytest.mark.parametrize(
    ("production_needs", "production_extra", "staging_step_extra", "reason"),
    [
        ("prepare", "", "", "can start before staging"),
        ("verify", "if: always()", "", "after an upstream failure"),
        ("verify", "if: ${{ !cancelled() }}", "", "after an upstream failure"),
        ("verify", "continue-on-error: true", "", "ignores failures"),
        ("verify", "", "continue-on-error: true", "ignores failures"),
        ("verify", "", "if: always()", "runs even after an earlier step failed"),
    ],
)
def test_rejects_bypassed_gates(
    production_needs: str, production_extra: str, staging_step_extra: str, reason: str
) -> None:
    flow = gated(production_needs, production_extra, staging_step_extra)
    with pytest.raises(AssertionError, match=reason):
        check_failures_stop_promotion(flow)


@pytest.mark.baseline
@pytest.mark.parametrize(
    "command",
    [
        "terraform apply -var-file=staging.tfvars || true",
        "terraform apply -var-file=staging.tfvars ||:",
        "terraform apply -var-file=staging.tfvars || exit 0",
        "set +e\nterraform apply -var-file=staging.tfvars",
    ],
)
def test_rejects_discarded_command_failures(command: str) -> None:
    flow = gated()
    flow["jobs"]["first"]["steps"][0]["run"] = command
    with pytest.raises(AssertionError, match="discards a command failure"):
        check_failures_stop_promotion(flow)


def racing(workflow_level: str = "", job_level: str = "") -> dict[str, Any]:
    return parse_workflow(
        f"{workflow_level}\n"
        "jobs:\n"
        "  ship:\n"
        f"    {job_level.replace(chr(10), chr(10) + '    ')}\n"
        "    steps:\n"
        "      - run: terraform apply -var-file=production.tfvars\n"
    )


@pytest.mark.baseline
@pytest.mark.parametrize(
    ("workflow_level", "job_level", "ok"),
    [
        ("", "", False),
        ("concurrency: release", "", True),
        ("concurrency:\n  group: release\n  cancel-in-progress: false", "", True),
        ("", "concurrency: production", True),
        ("", "concurrency:\n  group: production-${{ github.repository }}", True),
        ("", "concurrency:\n  group: production\n  cancel-in-progress: true", False),
        ("concurrency:\n  group: release\n  cancel-in-progress: true", "", False),
        ("", "concurrency:\n  group: production-${{ github.run_id }}", False),
        ("", "concurrency:\n  group: production-${{ github.ref }}", False),
        ("concurrency: run-${{ github.run_id }}", "concurrency: production", True),
        (
            "concurrency:\n  group: run-${{ github.run_id }}\n  cancel-in-progress: true",
            "concurrency: production",
            False,
        ),
    ],
)
def test_accepts_only_stable_non_cancelling_concurrency(
    workflow_level: str, job_level: str, ok: bool
) -> None:
    flow = racing(workflow_level, job_level)
    assert passes(check_production_does_not_race, flow) is ok
