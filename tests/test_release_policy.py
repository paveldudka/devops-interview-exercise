"""Checks of the checker: the policy must reject unsafe shapes and accept safe
ones regardless of job, step, output, or variable names.

Each snippet shows one mechanism the policy can follow or one gap it must
catch; none is a complete release.
"""

from collections.abc import Callable
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

Check = Callable[[dict[str, Any]], None]


def workflow(text: str) -> dict[str, Any]:
    return parse_workflow(dedent(text))


def expect(check: Check, flow: dict[str, Any], reason: str | None) -> None:
    """Run ``check``; ``reason`` is the expected failure text, or None to pass."""
    if reason is None:
        check(flow)
        return
    with pytest.raises(AssertionError, match=reason):
        check(flow)


def promotion(second_run: str) -> dict[str, Any]:
    """Step output in ``record``, forwarded to ``first`` as a job output and as
    ``TF_VAR_image_ref``, then to ``second`` as env ``ARTIFACT``. ``second_run``
    decides how the production apply consumes it."""
    flow = workflow(
        """
        jobs:
          record:
            outputs:
              handle: ${{ steps.note.outputs.handle }}
            steps:
              - id: note
                run: echo "handle=registry.invalid/app@${DIGEST}" >> "$GITHUB_OUTPUT"
          first:
            needs: record
            outputs:
              forwarded: ${{ needs.record.outputs.handle }}
            env:
              TF_VAR_image_ref: ${{ needs.record.outputs.handle }}
            steps:
              - run: terraform -chdir=infra apply -auto-approve -var-file=staging.tfvars
          second:
            needs: first
            environment: production
            env:
              ARTIFACT: ${{ needs.first.outputs.forwarded }}
            steps:
              - run: placeholder
        """
    )
    flow["jobs"]["second"]["steps"][0]["run"] = second_run
    return flow


@pytest.mark.baseline
@pytest.mark.parametrize(
    "second_run",
    [
        'terraform apply -var-file=production.tfvars -var="image_ref=${ARTIFACT}"',
        "terraform apply -var-file=production.tfvars -var=image_ref=$ARTIFACT",
        "terraform apply -var-file=production.tfvars -var 'image_ref=${{ env.ARTIFACT }}'",
        "terraform apply -var-file=production.tfvars "
        "-var='image_ref=${{ needs.first.outputs.forwarded }}'",
        "terraform apply -var-file=production.tfvars "
        "-var=image_ref=${{ needs.first.outputs.forwarded }}",
        "terraform apply -var-file=production.tfvars "
        '-var=image_ref="${{ needs.first.outputs.forwarded }}"',
        "terraform apply -var-file=infra/production.tfvars "
        "-var='image_ref=${{ needs.record.outputs.handle }}'",
        "terraform apply -var-file=common.tfvars -var-file=production.tfvars "
        "-var=image_ref=$ARTIFACT",
        "terraform -chdir=infra apply -var image_ref=$ARTIFACT",
        "terraform -chdir=infra apply \\\n  -var image_ref=$ARTIFACT",
        "terraform plan -out=tfplan -var=image_ref=$ARTIFACT\nterraform apply tfplan",
    ],
)
def test_traces_one_recorded_value_through_outputs_env_and_shell(
    second_run: str,
) -> None:
    flow = promotion(second_run)
    assert [d.image_ref for d in deployments(flow)] == ["«record/note/handle»"] * 2
    check_same_immutable_artifact(flow)


@pytest.mark.baseline
def test_plan_in_an_earlier_step_supplies_the_apply() -> None:
    flow = promotion("terraform apply -auto-approve tfplan")
    flow["jobs"]["second"]["steps"].insert(
        0, {"run": "terraform plan -out=tfplan -var-file=production.tfvars"}
    )
    flow["jobs"]["second"]["env"]["TF_VAR_image_ref"] = "${{ env.ARTIFACT }}"
    assert [d.image_ref for d in deployments(flow)] == ["«record/note/handle»"] * 2
    check_same_immutable_artifact(flow)


@pytest.mark.baseline
@pytest.mark.parametrize(
    "reference",
    [
        "registry.invalid/app@${{ needs.record.outputs.handle }}",
        "${{ needs.record.outputs.handle }}",
    ],
)
def test_accepts_a_reference_composed_around_a_recorded_digest(reference: str) -> None:
    flow = promotion(
        f"terraform apply -var-file=production.tfvars -var='image_ref={reference}'"
    )
    flow["jobs"]["first"]["env"]["TF_VAR_image_ref"] = reference
    check_same_immutable_artifact(flow)


@pytest.mark.baseline
def test_accepts_a_literal_digest_recorded_by_a_step() -> None:
    flow = promotion(
        "terraform apply -var-file=production.tfvars "
        "-var='image_ref=${{ needs.record.outputs.handle }}'"
    )
    flow["jobs"]["record"]["steps"][0]["run"] = (
        'echo "handle=registry.invalid/app@sha256:0123" >> "$GITHUB_OUTPUT"'
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
            "terraform apply -var-file=production.tfvars -var=image_ref=$ARTIFACT "
            "-var=image_ref=registry.invalid/app:latest",
            "do not deploy the same",
        ),
        (
            "terraform apply -var-file=production.tfvars -var=image_ref=$FROM_A_FILE",
            "cannot tell",
        ),
        (
            "terraform apply -var-file=production.tfvars "
            "-var='image_ref=${{ env.FROM_GITHUB_ENV }}'",
            "cannot tell",
        ),
        ("terraform apply -var-file=production.tfvars", "cannot tell"),
        ("terraform plan -var-file=production.tfvars", "no terraform apply"),
        (
            "terraform apply -var-file=production.tfvars "
            "-var='image_ref=${{ needs.ghost.outputs.handle }}'",
            "does not exist",
        ),
        (
            "terraform apply -var-file=production.tfvars "
            "-var='image_ref=${{ needs.record.outputs.nope }}'",
            "declares no output",
        ),
    ],
)
def test_rejects_missing_untraceable_or_diverging_references(
    second_run: str, reason: str
) -> None:
    expect(check_same_immutable_artifact, promotion(second_run), reason)


@pytest.mark.baseline
def test_environment_comes_from_var_file_then_github_environment() -> None:
    flow = promotion("terraform apply -var-file=prod.tfvars -var=image_ref=$ARTIFACT")
    check_same_immutable_artifact(flow)
    del flow["jobs"]["second"]["environment"]
    expect(check_same_immutable_artifact, flow, "neither staging nor production")


@pytest.mark.baseline
def test_rejects_a_var_file_that_contradicts_the_github_environment() -> None:
    flow = promotion(
        "terraform apply -var-file=staging.tfvars -var=image_ref=$ARTIFACT"
    )
    expect(check_same_immutable_artifact, flow, "GitHub environment 'production'")


@pytest.mark.baseline
def test_rejects_a_unique_tag_as_the_promoted_identity() -> None:
    flow = promotion(
        "terraform apply -var-file=production.tfvars "
        "-var='image_ref=registry.invalid/app:${{ needs.record.outputs.handle }}'"
    )
    flow["jobs"]["first"]["env"]["TF_VAR_image_ref"] = (
        "registry.invalid/app:${{ needs.record.outputs.handle }}"
    )
    expect(check_same_immutable_artifact, flow, "not an immutable identity")


@pytest.mark.baseline
@pytest.mark.parametrize(
    "unrelated_step",
    [None, {"name": "Print digest", "run": "echo digest"}],
)
def test_rejects_a_recorded_value_with_no_digest_behind_it(
    unrelated_step: dict[str, str] | None,
) -> None:
    flow = promotion(
        "terraform apply -var-file=production.tfvars "
        "-var='image_ref=${{ needs.record.outputs.handle }}'"
    )
    flow["jobs"]["record"]["steps"][0]["run"] = (
        'echo "handle=registry.invalid/app@${IDENTITY}" >> "$GITHUB_OUTPUT"'
    )
    if unrelated_step:
        flow["jobs"]["record"]["steps"].append(unrelated_step)
    expect(
        check_same_immutable_artifact, flow, "without any sign of the registry digest"
    )


@pytest.mark.baseline
def test_rejects_an_output_that_names_a_missing_step() -> None:
    flow = promotion(
        "terraform apply -var-file=production.tfvars "
        "-var='image_ref=${{ needs.record.outputs.handle }}'"
    )
    flow["jobs"]["record"]["outputs"]["handle"] = "${{ steps.ghost.outputs.handle }}"
    expect(check_same_immutable_artifact, flow, "no step with id 'ghost'")


@pytest.mark.baseline
@pytest.mark.parametrize(
    ("build_steps", "reason"),
    [
        ([{"run": "docker build -t registry.invalid/app ."}], None),
        ([{"run": "docker image build -t registry.invalid/app ."}], None),
        ([{"run": "docker buildx build --push -t registry.invalid/app ."}], None),
        ([{"uses": "docker/build-push-action@v6"}], None),
        (
            [{"run": "docker build ."}, {"uses": "docker/build-push-action@v6"}],
            "2 times",
        ),
        ([{"run": "docker build -t a .\ndocker build -t b ."}], "2 times"),
        ([{"run": "docker pull registry.invalid/app@sha256:abc"}], "0 times"),
    ],
)
def test_counts_recognised_build_commands(
    build_steps: list[dict[str, str]], reason: str | None
) -> None:
    flow = parse_workflow("jobs:\n  one:\n    steps: []\n")
    flow["jobs"]["one"]["steps"] = build_steps
    expect(check_image_is_built_once, flow, reason)


def gated(
    production_needs: str = "verify",
    production_extra: str = "",
    staging_step_extra: str = "",
    verify_extra: str = "",
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
            {verify_extra}
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
    (
        "production_needs",
        "production_extra",
        "staging_step_extra",
        "verify_extra",
        "reason",
    ),
    [
        ("prepare", "", "", "", "can start before staging"),
        ("verify", "if: always()", "", "", "after an upstream failure"),
        ("verify", "if: ${{ !cancelled() }}", "", "", "after an upstream failure"),
        ("verify", "", "", "if: always()", "after an upstream failure"),
        ("verify", "continue-on-error: true", "", "", "ignores failures"),
        ("verify", "", "continue-on-error: true", "", "ignores failures"),
        ("verify", "", "if: always()", "", "runs even after an earlier step failed"),
        ("verify", "", "shell: bash {0}", "", "keeps going after a failure"),
    ],
)
def test_rejects_bypassed_gates(
    production_needs: str,
    production_extra: str,
    staging_step_extra: str,
    verify_extra: str,
    reason: str,
) -> None:
    flow = gated(production_needs, production_extra, staging_step_extra, verify_extra)
    expect(check_failures_stop_promotion, flow, reason)


@pytest.mark.baseline
def test_fail_fast_shells_and_workflow_defaults_are_understood() -> None:
    flow = gated(staging_step_extra="shell: bash -e {0}")
    check_failures_stop_promotion(flow)
    flow["defaults"] = {"run": {"shell": "bash {0}"}}
    flow["jobs"]["second"]["steps"][0]["shell"] = "bash -eo pipefail {0}"
    expect(check_failures_stop_promotion, flow, "keeps going after a failure")


@pytest.mark.baseline
@pytest.mark.parametrize(
    ("command", "reason"),
    [
        ("terraform apply -var-file=staging.tfvars || true", "discards"),
        ("terraform apply -var-file=staging.tfvars ||:", "discards"),
        ("terraform apply -var-file=staging.tfvars || exit 0", "discards"),
        ("set +e\nterraform apply -var-file=staging.tfvars", "discards"),
        ("set +ex\nterraform apply -var-file=staging.tfvars", "discards"),
        (
            "terraform apply -var-file=staging.tfvars || echo failed",
            "hides the outcome",
        ),
        ("terraform apply -var-file=staging.tfvars &", "hides the outcome"),
        ("if ! terraform apply -var-file=staging.tfvars; then echo no; fi", "hides"),
        ("terraform apply -var-file=staging.tfvars || { echo no; exit 1; }", None),
        ("terraform apply -var-file=staging.tfvars || exit 1", None),
    ],
)
def test_rejects_discarded_command_failures(command: str, reason: str | None) -> None:
    flow = gated()
    flow["jobs"]["first"]["steps"][0]["run"] = command
    expect(check_failures_stop_promotion, flow, reason)


@pytest.mark.baseline
@pytest.mark.parametrize(
    ("order", "reason"),
    [(("staging", "production"), None), (("production", "staging"), "before staging")],
)
def test_one_job_may_deploy_both_in_order(
    order: tuple[str, str], reason: str | None
) -> None:
    flow = workflow(
        f"""
        jobs:
          ship:
            steps:
              - run: terraform apply -var-file={order[0]}.tfvars -var=image_ref=$X
              - run: terraform apply -var-file={order[1]}.tfvars -var=image_ref=$X
        """
    )
    expect(check_failures_stop_promotion, flow, reason)


def racing(workflow_level: str = "", job_level: str = "") -> dict[str, Any]:
    return parse_workflow(
        f"{workflow_level}\n"
        "jobs:\n"
        "  ship:\n"
        f"    {job_level.replace(chr(10), chr(10) + '    ')}\n"
        "    environment:\n"
        "      name: production\n"
        "    steps:\n"
        "      - run: terraform apply -auto-approve\n"
    )


@pytest.mark.baseline
@pytest.mark.parametrize(
    ("workflow_level", "job_level", "reason"),
    [
        ("", "", "nothing stops two releases"),
        ("concurrency: release", "", None),
        ("concurrency:\n  group: release\n  cancel-in-progress: false", "", None),
        ("", "concurrency: production", None),
        ("", "concurrency:\n  group: production-${{ github.repository }}", None),
        ("", "concurrency:\n  group: production\n  cancel-in-progress: true", "cancel"),
        ("concurrency:\n  group: release\n  cancel-in-progress: true", "", "cancel"),
        ("", "concurrency:\n  group: production-${{ github.run_id }}", "overlap"),
        ("", "concurrency:\n  group: production-${{ github.ref }}", "overlap"),
        ("", "concurrency:\n  group: production-${{ github.actor }}", "overlap"),
        ("", "concurrency: production-${{ inputs.version }}", "overlap"),
        ("concurrency: run-${{ github.run_id }}", "concurrency: production", None),
        (
            "concurrency:\n  group: run-${{ github.run_id }}\n  cancel-in-progress: true",
            "concurrency: production",
            "cancel",
        ),
    ],
)
def test_accepts_only_stable_non_cancelling_concurrency(
    workflow_level: str, job_level: str, reason: str | None
) -> None:
    expect(check_production_does_not_race, racing(workflow_level, job_level), reason)
