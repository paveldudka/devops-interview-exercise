"""Static safety checks for the release workflow fixture.

The checks parse the workflow, find every ``terraform apply`` that targets
staging or production, and trace the image reference it deploys through
workflow expressions, env, and job outputs. A value recorded by a step output
is represented as ``«job/step/output»`` because its runtime content is unknown.
These are policy checks over YAML, not a deployment simulation.
"""

import re
from dataclasses import dataclass
from typing import Any

import yaml


ENVIRONMENTS = ("staging", "production")

BUILD_COMMAND = re.compile(r"\bdocker\s+(?:build|buildx\s+build)\b")
BUILD_ACTION = "docker/build-push-action@"
APPLY_COMMAND = re.compile(r"\bterraform\b[^\n]*\bapply\b")
VAR_FILE = re.compile(r"-var-file[= ]+['\"]?(?:[\w./-]*/)?(?P<env>\w+)\.tfvars")
IMAGE_VAR = re.compile(r"-var[= ]+(?P<q>['\"]?)image_ref=(?P<value>.*?)(?P=q)(?=\s|$)")
NEEDS_OUTPUT = re.compile(
    r"\$\{\{\s*needs\.(?P<job>[\w-]+)\.outputs\.(?P<name>[\w-]+)\s*\}\}"
)
STEP_OUTPUT = re.compile(
    r"\$\{\{\s*steps\.(?P<step>[\w-]+)\.outputs\.(?P<name>[\w-]+)\s*\}\}"
)
ENV_EXPRESSION = re.compile(r"\$\{\{\s*env\.(?P<name>\w+)\s*\}\}")
SHELL_VARIABLE = re.compile(r"\$\{(?P<braced>\w+)\}|\$(?P<bare>\w+)")
RECORDED_OUTPUT = re.compile(r"«(?P<job>[\w-]+)/(?P<step>[\w-]+)/(?P<name>[\w-]+)»")
IMMUTABLE_REFERENCE = re.compile(r"^(?:[^\s@]+@)?«[^»]+»$")
UNSTABLE_GROUP = re.compile(
    r"github\.(?:run_id|run_number|run_attempt|sha|ref|ref_name|head_ref)\b"
)
STATUS_OVERRIDE = re.compile(r"\b(?:always|failure|cancelled)\s*\(")
IGNORED_FAILURE = re.compile(r"\|\|\s*(?:true|:|exit\s+0)(?![\w-])|\bset\s+\+e\b")
MAX_TRACE_DEPTH = 8


@dataclass(frozen=True)
class Deployment:
    environment: str
    job_id: str
    step_name: str
    image_ref: str | None


def parse_workflow(text: str) -> dict[str, Any]:
    return yaml.load(text, Loader=yaml.BaseLoader)


def jobs(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return workflow.get("jobs") or {}


def steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return job.get("steps") or []


def environment_name(job: dict[str, Any]) -> str | None:
    environment = job.get("environment")
    if isinstance(environment, dict):
        return environment.get("name")
    return environment


def needs_of(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else list(needs)


def upstream_jobs(workflow: dict[str, Any], job_id: str) -> set[str]:
    """Every job that must finish before ``job_id`` starts (transitive needs)."""
    seen: set[str] = set()
    pending = needs_of(jobs(workflow).get(job_id, {}))
    while pending:
        upstream = pending.pop()
        if upstream in seen:
            continue
        seen.add(upstream)
        pending.extend(needs_of(jobs(workflow).get(upstream, {})))
    return seen


def is_build_step(step: dict[str, Any]) -> bool:
    return bool(BUILD_COMMAND.search(step.get("run", ""))) or str(
        step.get("uses", "")
    ).startswith(BUILD_ACTION)


def build_steps(workflow: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (job_id, step)
        for job_id, job in jobs(workflow).items()
        for step in steps(job)
        if is_build_step(step)
    ]


def merged_env(
    workflow: dict[str, Any], job: dict[str, Any], step: dict[str, Any] | None
) -> dict[str, str]:
    env: dict[str, str] = {}
    for scope in (workflow, job, step or {}):
        scope_env = scope.get("env")
        if isinstance(scope_env, dict):
            env.update({str(k): str(v) for k, v in scope_env.items()})
    return env


def trace(
    workflow: dict[str, Any],
    text: str,
    job_id: str,
    step: dict[str, Any] | None = None,
    *,
    shell: bool = False,
    depth: int = 0,
) -> str:
    """Replace expressions in ``text`` with what they resolve to.

    Job outputs are followed into the producing job; step outputs become
    ``«job/step/output»`` markers; env and shell variables are expanded when
    they are defined in the workflow file. Anything else stays literal.
    """
    if depth > MAX_TRACE_DEPTH:
        return text
    job = jobs(workflow).get(job_id, {})
    env = merged_env(workflow, job, step)

    def follow_output(match: re.Match[str]) -> str:
        producer = match.group("job")
        outputs = jobs(workflow).get(producer, {}).get("outputs") or {}
        expression = outputs.get(match.group("name"))
        if expression is None:
            return match.group(0)
        return trace(workflow, str(expression), producer, depth=depth + 1)

    def mark_step_output(match: re.Match[str]) -> str:
        return f"«{job_id}/{match.group('step')}/{match.group('name')}»"

    def expand_env(match: re.Match[str]) -> str:
        name = next(group for group in match.groupdict().values() if group)
        value = env.get(name)
        if value is None:
            return match.group(0)
        return trace(workflow, value, job_id, step, depth=depth + 1)

    text = NEEDS_OUTPUT.sub(follow_output, text)
    text = STEP_OUTPUT.sub(mark_step_output, text)
    text = ENV_EXPRESSION.sub(expand_env, text)
    if shell:
        text = SHELL_VARIABLE.sub(expand_env, text)
    return text


def deployment_environment(job: dict[str, Any], run: str) -> str | None:
    var_file = VAR_FILE.search(run)
    if var_file:
        return var_file.group("env")
    return environment_name(job)


def deployed_image_ref(
    workflow: dict[str, Any], job_id: str, step: dict[str, Any]
) -> str | None:
    run = step.get("run", "")
    match = IMAGE_VAR.search(run)
    if match:
        raw = match.group("value").strip("'\"")
    else:
        raw = merged_env(workflow, jobs(workflow)[job_id], step).get("TF_VAR_image_ref")
    if raw is None:
        return None
    traced = trace(workflow, raw, job_id, step, shell=True)
    # A shell variable that is not defined in the workflow file is opaque.
    return None if SHELL_VARIABLE.search(traced) else traced


def deployments(workflow: dict[str, Any]) -> list[Deployment]:
    """Every ``terraform apply`` that targets a known environment."""
    found: list[Deployment] = []
    for job_id, job in jobs(workflow).items():
        for step in steps(job):
            run = step.get("run", "")
            if not APPLY_COMMAND.search(run):
                continue
            environment = deployment_environment(job, run)
            if environment not in ENVIRONMENTS:
                continue
            found.append(
                Deployment(
                    environment=environment,
                    job_id=job_id,
                    step_name=str(step.get("name") or step.get("id") or "<unnamed>"),
                    image_ref=deployed_image_ref(workflow, job_id, step),
                )
            )
    return found


def jobs_deploying(workflow: dict[str, Any], environment: str) -> set[str]:
    return {d.job_id for d in deployments(workflow) if d.environment == environment}


def rendered(node: Any) -> str:
    return yaml.safe_dump(node, sort_keys=True)


def is_false(value: Any) -> bool:
    return str(value if value is not None else "false").lower() == "false"


# --- checks -----------------------------------------------------------------


def check_image_is_built_once(workflow: dict[str, Any]) -> None:
    builds = build_steps(workflow)
    where = ", ".join(
        f"{job_id}: {step.get('name', '<unnamed>')}" for job_id, step in builds
    )
    assert len(builds) == 1, (
        f"the release builds the image {len(builds)} times ({where or 'none'}); "
        "one release must produce exactly one artifact"
    )


def check_same_immutable_artifact(workflow: dict[str, Any]) -> None:
    found = deployments(workflow)
    for environment in ENVIRONMENTS:
        assert any(d.environment == environment for d in found), (
            f"no terraform apply deploys {environment}"
        )
    for deployment in found:
        assert deployment.image_ref is not None, (
            f"cannot tell which image reference '{deployment.job_id}' deploys to "
            f"{deployment.environment}; the checks trace values through "
            "workflow expressions, env, and job outputs only"
        )
    refs = {d.image_ref for d in found}
    assert len(refs) == 1, (
        "staging and production do not deploy the same image reference: "
        + "; ".join(f"{d.environment} -> {d.image_ref}" for d in found)
    )
    ref = refs.pop()
    assert IMMUTABLE_REFERENCE.match(ref), (
        f"'{ref}' is not an immutable identity recorded from this workflow's own "
        "build; a tag can point at different bytes each time it is resolved"
    )
    recorded = RECORDED_OUTPUT.findall(ref)[-1]
    producer_job, producer_step, output = recorded
    assert "digest" in rendered(jobs(workflow)[producer_job]).lower(), (
        f"job '{producer_job}' records '{output}' from step '{producer_step}' "
        "without any sign of the registry digest of the pushed image"
    )


def check_failures_stop_promotion(workflow: dict[str, Any]) -> None:
    for job_id, job in jobs(workflow).items():
        assert is_false(job.get("continue-on-error")), (
            f"job '{job_id}' ignores failures"
        )
        for step in steps(job):
            label = f"job '{job_id}' step '{step.get('name', '<unnamed>')}'"
            assert is_false(step.get("continue-on-error")), f"{label} ignores failures"
            assert not IGNORED_FAILURE.search(step.get("run", "")), (
                f"{label} discards a command failure"
            )
            if is_build_step(step) or APPLY_COMMAND.search(step.get("run", "")):
                assert not STATUS_OVERRIDE.search(str(step.get("if", ""))), (
                    f"{label} runs even after an earlier step failed"
                )

    staging_jobs = jobs_deploying(workflow, "staging")
    production_jobs = jobs_deploying(workflow, "production")
    assert staging_jobs and production_jobs, "staging and production must both deploy"
    for job_id in production_jobs:
        missing = staging_jobs - upstream_jobs(workflow, job_id)
        assert not missing, (
            f"production job '{job_id}' can start before staging "
            f"({', '.join(sorted(missing))}) has succeeded"
        )
        condition = str(jobs(workflow)[job_id].get("if", ""))
        assert not STATUS_OVERRIDE.search(condition), (
            f"production job '{job_id}' can run after an upstream failure"
        )


def concurrency_policy(node: Any) -> tuple[str, Any]:
    if isinstance(node, dict):
        return str(node.get("group", "")), node.get("cancel-in-progress")
    return str(node), None


def check_production_does_not_race(workflow: dict[str, Any]) -> None:
    production_jobs = jobs_deploying(workflow, "production")
    assert production_jobs, "no terraform apply deploys production"
    for job_id in production_jobs:
        policies = [
            (scope, concurrency_policy(node))
            for scope, node in (
                ("workflow", workflow.get("concurrency")),
                (f"job '{job_id}'", jobs(workflow)[job_id].get("concurrency")),
            )
            if node
        ]
        assert policies, (
            f"nothing stops two releases from deploying production ('{job_id}') "
            "at the same time"
        )
        for scope, (group, cancel) in policies:
            assert group, f"{scope} concurrency has no group"
            assert is_false(cancel), (
                f"{scope} concurrency can cancel an in-progress production deployment"
            )
        assert any(not UNSTABLE_GROUP.search(group) for _, (group, _) in policies), (
            f"the concurrency group covering '{job_id}' differs per run, commit, or "
            "ref, so two production releases can still overlap"
        )
