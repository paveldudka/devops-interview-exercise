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

BUILD_COMMAND = re.compile(
    r"\b(?:docker\s+(?:image\s+)?build|docker\s+buildx\s+(?:build|bake)"
    r"|docker\s+compose\s+build|podman\s+build|buildah\s+(?:bud|build)"
    r"|nerdctl\s+build)\b"
)
BUILD_ACTIONS = ("docker/build-push-action@", "docker/bake-action@")
TERRAFORM_COMMAND = re.compile(r"\bterraform\b(?:\s+-\S+)*\s+(?P<sub>plan|apply)\b")
VAR_FILE = re.compile(r"-var-file[= ]+['\"]?(?:[\w./-]*/)?(?P<env>\w+)\.tfvars")
IMAGE_VAR = re.compile(
    r"-var[= ]+(?:'image_ref=(?P<sq>[^']*)'|\"image_ref=(?P<dq>[^\"]*)\""
    r"|image_ref=(?P<bare>(?:\$\{\{.*?\}\}|\"[^\"]*\"|'[^']*'|[^\s'\"])+))"
)
NEEDS_OUTPUT = re.compile(
    r"\$\{\{\s*needs\.(?P<job>[\w-]+)\.outputs\.(?P<name>[\w-]+)\s*\}\}"
)
STEP_OUTPUT = re.compile(
    r"\$\{\{\s*steps\.(?P<step>[\w-]+)\.outputs\.(?P<name>[\w-]+)\s*\}\}"
)
ENV_EXPRESSION = re.compile(r"\$\{\{\s*env\.(?P<name>\w+)\s*\}\}")
SHELL_VARIABLE = re.compile(r"\$\{(?P<braced>\w+)\}|\$(?P<bare>\w+)")
RECORDED_OUTPUT = re.compile(r"«(?P<job>[\w-]+)/(?P<step>[\w-]+)/(?P<name>[\w-]+)»")
IMMUTABLE_REFERENCE = re.compile(rf"^(?:[^\s@]+@)?{RECORDED_OUTPUT.pattern}$")
DIGEST_EVIDENCE = re.compile(r"digest|@sha256:", re.IGNORECASE)
EXPRESSION = re.compile(r"\$\{\{(?P<body>.*?)\}\}")
STABLE_CONTEXT = re.compile(
    r"^\s*github\.(?:workflow|repository|repository_id|repository_owner)\s*$"
)
STATUS_OVERRIDE = re.compile(r"\b(?:always|failure|cancelled)\s*\(")
IGNORED_FAILURE = re.compile(r"\|\|\s*(?:true|:|exit\s+0)(?![\w-])|\bset\s+\+[a-z]*e")
UNGUARDED_COMMAND = re.compile(
    r"\|\|(?!\s*(?:exit\s+[1-9]|return\s+[1-9]|false\b|[{(]))|&\s*$|^\s*(?:if\s+)?!\s"
)
FAIL_FAST_DISABLED = re.compile(r"\{0\}")
FAIL_FAST_FLAG = re.compile(r"(?:^|\s)-\w*e\w*(?:\s|$)")
MAX_TRACE_DEPTH = 32


@dataclass(frozen=True)
class Deployment:
    environment: str | None
    job_id: str
    step_name: str
    image_ref: str | None


def parse_workflow(text: str) -> dict[str, Any]:
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    if not isinstance(workflow, dict) or not isinstance(workflow.get("jobs"), dict):
        raise ValueError("workflow must be a mapping with a 'jobs' mapping")
    for job_id, job in workflow["jobs"].items():
        if not isinstance(job, dict):
            raise ValueError(f"jobs.{job_id} must be a mapping")
        for index, step in enumerate(job.get("steps") or []):
            if not isinstance(step, dict):
                raise ValueError(f"jobs.{job_id}.steps[{index}] must be a mapping")
            for key in ("run", "uses", "if", "shell"):
                if key in step and not isinstance(step[key], str):
                    raise ValueError(
                        f"jobs.{job_id}.steps[{index}].{key} must be a string"
                    )
    return workflow


def jobs(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return workflow["jobs"]


def steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return job.get("steps") or []


def step_label(job_id: str, step: dict[str, Any]) -> str:
    return f"job '{job_id}' step '{step.get('name') or step.get('id') or '<unnamed>'}'"


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


def commands(step: dict[str, Any]) -> list[str]:
    """Logical shell lines of a step, with backslash continuations joined."""
    return step.get("run", "").replace("\\\n", " ").splitlines()


def build_count(step: dict[str, Any]) -> int:
    action = str(step.get("uses", ""))
    return len(BUILD_COMMAND.findall(step.get("run", ""))) + int(
        action.startswith(BUILD_ACTIONS)
    )


def is_deploy_or_build(step: dict[str, Any]) -> bool:
    return build_count(step) > 0 or any(
        TERRAFORM_COMMAND.search(line) for line in commands(step)
    )


def merged_env(
    workflow: dict[str, Any], job: dict[str, Any], step: dict[str, Any] | None
) -> dict[str, str]:
    env: dict[str, str] = {}
    for scope in (workflow, job, step or {}):
        scope_env = scope.get("env")
        if isinstance(scope_env, dict):
            env.update({str(k): str(v) for k, v in scope_env.items()})
    return env


def effective_shell(
    workflow: dict[str, Any], job: dict[str, Any], step: dict[str, Any]
) -> str | None:
    if "shell" in step:
        return step["shell"]
    for scope in (job, workflow):
        defaults = scope.get("defaults") or {}
        run_defaults = defaults.get("run") if isinstance(defaults, dict) else None
        if isinstance(run_defaults, dict) and "shell" in run_defaults:
            return str(run_defaults["shell"])
    return None


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

    Job outputs are followed into the producing job until a step output is
    reached, which becomes a ``«job/step/output»`` marker. ``env`` expressions
    expand from workflow, job, and step env; shell variables only when
    ``shell`` is set. Anything else stays literal.
    """
    assert depth <= MAX_TRACE_DEPTH, f"gave up tracing '{text}' (circular outputs?)"
    job = jobs(workflow).get(job_id, {})
    env = merged_env(workflow, job, step)

    def follow_output(match: re.Match[str]) -> str:
        producer, name = match.group("job"), match.group("name")
        assert producer in jobs(workflow), (
            f"job '{job_id}' reads needs.{producer}.outputs.{name} but job "
            f"'{producer}' does not exist"
        )
        outputs = jobs(workflow)[producer].get("outputs") or {}
        assert name in outputs, (
            f"job '{job_id}' reads needs.{producer}.outputs.{name} but job "
            f"'{producer}' declares no output '{name}'"
        )
        return trace(workflow, str(outputs[name]), producer, depth=depth + 1)

    def mark_step_output(match: re.Match[str]) -> str:
        step_id = match.group("step")
        assert any(s.get("id") == step_id for s in steps(job)), (
            f"job '{job_id}' reads steps.{step_id}.outputs.{match.group('name')} "
            f"but has no step with id '{step_id}'"
        )
        return f"«{job_id}/{step_id}/{match.group('name')}»"

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


def image_var(line: str) -> str | None:
    """The last ``image_ref`` passed with ``-var`` on a line; Terraform keeps the last."""
    matches = list(IMAGE_VAR.finditer(line))
    if not matches:
        return None
    value = next(group for group in matches[-1].groups() if group is not None)
    return value.strip("'\"")


def known_environment(line: str) -> str | None:
    for match in VAR_FILE.finditer(line):
        if match.group("env") in ENVIRONMENTS:
            return match.group("env")
    return None


def deployments(workflow: dict[str, Any]) -> list[Deployment]:
    """Every ``terraform apply``, in job and step order.

    Environment and image reference come from the apply line, else from the
    nearest earlier ``terraform plan`` in the job, else from the job's GitHub
    environment and ``TF_VAR_image_ref``.
    """
    found: list[Deployment] = []
    for job_id, job in jobs(workflow).items():
        plan_environment: str | None = None
        plan_image: str | None = None
        for step in steps(job):
            for line in commands(step):
                command = TERRAFORM_COMMAND.search(line)
                if command is None:
                    continue
                environment = known_environment(line)
                raw = image_var(line)
                if command.group("sub") == "plan":
                    plan_environment, plan_image = environment, raw
                    continue
                environment = environment or plan_environment
                job_environment = environment_name(job)
                if environment is None:
                    environment = job_environment
                else:
                    assert job_environment in (None, environment), (
                        f"{step_label(job_id, step)} runs in GitHub environment "
                        f"'{job_environment}' but applies {environment}.tfvars"
                    )
                raw = raw or plan_image
                if raw is None:
                    raw = merged_env(workflow, job, step).get("TF_VAR_image_ref")
                image_ref = None
                if raw is not None:
                    image_ref = trace(workflow, raw, job_id, step, shell=True)
                    # Shell variables and env not defined in the file are opaque.
                    if SHELL_VARIABLE.search(image_ref) or ENV_EXPRESSION.search(
                        image_ref
                    ):
                        image_ref = None
                found.append(
                    Deployment(
                        environment=environment,
                        job_id=job_id,
                        step_name=step_label(job_id, step),
                        image_ref=image_ref,
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
    builds = [
        (build_count(step), step_label(job_id, step))
        for job_id, job in jobs(workflow).items()
        for step in steps(job)
        if build_count(step)
    ]
    total = sum(count for count, _ in builds)
    where = ", ".join(label for _, label in builds) or "none"
    assert total == 1, (
        f"the release builds the image {total} times ({where}); "
        "one release must produce exactly one artifact"
    )


def check_same_immutable_artifact(workflow: dict[str, Any]) -> None:
    found = deployments(workflow)
    for deployment in found:
        assert deployment.environment in ENVIRONMENTS, (
            f"{deployment.step_name} applies to '{deployment.environment}', which is "
            "neither staging nor production"
        )
    for environment in ENVIRONMENTS:
        assert any(d.environment == environment for d in found), (
            f"no terraform apply deploys {environment}"
        )
    for deployment in found:
        assert deployment.image_ref is not None, (
            f"cannot tell which image reference {deployment.step_name} deploys to "
            f"{deployment.environment}; the checks trace values through workflow "
            "expressions, env, and job outputs only"
        )
    refs = {d.image_ref for d in found}
    assert len(refs) == 1, (
        "staging and production do not deploy the same image reference: "
        + "; ".join(f"{d.environment} -> {d.image_ref}" for d in found)
    )
    ref = refs.pop()
    recorded = IMMUTABLE_REFERENCE.match(ref)
    assert recorded, (
        f"'{ref}' is not an immutable identity recorded from this workflow's own "
        "build, so the bytes it resolves to can change"
    )
    producer_job, step_id, output = recorded.group("job", "step", "name")
    producer = next(
        s for s in steps(jobs(workflow)[producer_job]) if s.get("id") == step_id
    )
    evidence = rendered({k: v for k, v in producer.items() if k != "name"}) + output
    assert DIGEST_EVIDENCE.search(evidence), (
        f"job '{producer_job}' step '{step_id}' records '{output}' without any sign "
        "of the registry digest of the pushed image"
    )


def check_failures_stop_promotion(workflow: dict[str, Any]) -> None:
    for job_id, job in jobs(workflow).items():
        assert is_false(job.get("continue-on-error")), (
            f"job '{job_id}' ignores failures"
        )
        for step in steps(job):
            label = step_label(job_id, step)
            assert is_false(step.get("continue-on-error")), f"{label} ignores failures"
            assert not IGNORED_FAILURE.search(step.get("run", "")), (
                f"{label} discards a command failure"
            )
            shell = effective_shell(workflow, job, step)
            if shell and FAIL_FAST_DISABLED.search(shell):
                assert FAIL_FAST_FLAG.search(shell), (
                    f"{label} uses shell '{shell}', which keeps going after a failure"
                )
            if is_deploy_or_build(step):
                assert not STATUS_OVERRIDE.search(str(step.get("if", ""))), (
                    f"{label} runs even after an earlier step failed"
                )
                for line in commands(step):
                    if BUILD_COMMAND.search(line) or TERRAFORM_COMMAND.search(line):
                        assert not UNGUARDED_COMMAND.search(line), (
                            f"{label} hides the outcome of: {line.strip()}"
                        )

    found = deployments(workflow)
    staging_jobs = {d.job_id for d in found if d.environment == "staging"}
    production_jobs = {d.job_id for d in found if d.environment == "production"}
    assert staging_jobs and production_jobs, "staging and production must both deploy"
    for job_id in production_jobs:
        gate = upstream_jobs(workflow, job_id) | {job_id}
        missing = staging_jobs - gate
        assert not missing, (
            f"production job '{job_id}' can start before staging "
            f"({', '.join(sorted(missing))}) has succeeded"
        )
        if job_id in staging_jobs:
            order = [d.environment for d in found if d.job_id == job_id]
            assert order.index("staging") < order.index("production"), (
                f"job '{job_id}' deploys production before staging"
            )
        for gate_job in sorted(gate):
            condition = str(jobs(workflow)[gate_job].get("if", ""))
            assert not STATUS_OVERRIDE.search(condition), (
                f"job '{gate_job}' runs after an upstream failure, so production "
                f"'{job_id}' no longer waits for staging to succeed"
            )


def concurrency_policy(node: Any) -> tuple[str, Any]:
    if isinstance(node, dict):
        return str(node.get("group", "")), node.get("cancel-in-progress")
    return str(node), None


def is_stable_group(group: str) -> bool:
    return all(
        STABLE_CONTEXT.match(m.group("body")) for m in EXPRESSION.finditer(group)
    )


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
        assert any(is_stable_group(group) for _, (group, _) in policies), (
            f"the concurrency group covering '{job_id}' can differ between releases, "
            "so two production deployments can still overlap"
        )
