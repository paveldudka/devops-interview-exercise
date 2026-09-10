# Interviewer guide

This file and this branch are confidential interviewer material. Never send the
canonical repository, a branch URL, a PR URL, this guide, the solved workflow,
or the evaluator sources to a candidate. Candidates receive a new private
repository whose only branch is the neutral candidate starter commit.

## Before the session

1. Generate an isolated candidate repository using the procedure below.
2. Ask the candidate to open its devcontainer and run `make verify-env` before
   the interview. Do not start the timer until the environment is ready.
3. Confirm screen sharing. Remind them that assessment, the interviewer twist,
   and the final walkthrough are AI-free. AI and public documentation are
   allowed only during implementation.
4. During orientation, explain that the surrounding platform supplies a runner
   with the required tools, working registry and AWS authentication, registry
   access, Terraform initialization, and remote state. These prerequisites work
   as intended and are outside scope. Do not use them to volunteer findings.
5. Keep this guide and the reference branch out of shared screens and chat.

## Facilitation script (75 minutes)

- **0–15 — AI-free assessment and prioritization:** Ask the candidate to inspect
  the proposal and record material findings in `NOTES.md`, ranked by priority
  with impact and repository evidence. Have them explain the ranking before
  they start implementation. Do not volunteer planted findings or steer them
  toward the reference design before this assessment is captured.
- **15–50 — implementation (AI/docs allowed):** The candidate selects and
  implements one focused improvement. Observe whether the choice follows from
  their assessment, whether it addresses a material risk, and how they control
  scope and gather evidence. They are not expected to identify or fix
  everything.
- **50–60 — AI-free requirement/incident twist:** “Rollback must redeploy the
  previously promoted artifact without rebuilding it. Show or explain the
  smallest change you would make.” Code is optional if the base task consumed
  the time.
- **60–75 — AI-free defense:** Ask them to stop AI use and defend their
  assessment, chosen priority, diff, validation evidence, rollout, rollback,
  residual risks, and next step.

Answer environment and model-boundary questions directly. Before the assessment
is recorded, redirect design questions with “What does the repository evidence
suggest?” Afterward, use the bounded hints ladder only when progress is blocked.

## What the candidate is asked

The candidate receives a neutral proposed ECS release process. They must:

1. assess whether it is production-ready and prioritize material risks;
2. support findings with impact and repository evidence;
3. choose one focused improvement and explain why it is the best use of time;
4. implement and validate that improvement; and
5. explain rollout, rollback, residual risks, and what they would address next.

The prompt intentionally does not identify the planted defects or require a
particular fix. Do not convert it back into a checklist during facilitation.
Candidates are not expected to identify or fix every issue, and issue count is
not a scoring dimension.

## Expected findings (interviewer-only)

The central artifact-integrity risk is that staging and production independently
rebuild source and both deploy a mutable `:latest` reference. Production can
therefore run bytes that staging never validated. This is normally the strongest
first priority because it invalidates the purpose of staged promotion.

Other material findings include:

- `continue-on-error` and `|| true` allow failures to be ignored;
- production releases can overlap;
- Terraform accepts any image string, allowing callers to bypass immutability;
- the flow does not wait for or verify ECS/application health;
- the model has no demonstrated provenance, deployment record, retention, or
  tested rollback mechanism; and
- mocked/static validation cannot establish live registry, AWS, networking,
  application, observability, or traffic behavior.

Do not score by how many of these the candidate lists. Score the evidence,
impact/blast-radius reasoning, dependencies between risks, and priority order.
A different first priority can meet the bar when it is supported by convincing
production-risk reasoning. Cosmetic IaC cleanup is not an adequate focus if the
candidate has not identified a material release risk.

## Preferred reference solution

This branch's `exercise/release.yml` is one calibrated, deliberately broad
solution: a `build` job publishes once with `docker/build-push-action`, records
`repository@sha256:...` from the action's digest output as a job output, and
staging and production both deploy that recorded value. Production needs
staging and uses a stable, non-cancelling concurrency group.
`infra/variables.tf` validates the digest form. `NOTES.md` is a completed
reference assessment and write-up rather than the candidate template.

The reference addresses artifact integrity plus closely coupled promotion
safeguards. A candidate is asked to implement only one focused improvement and
may produce a smaller diff. Use the reference for probing and calibration, not
as an expected patch to match.

## Acceptable choices and alternatives

A coherent implementation should follow from the candidate's prioritized
assessment. Examples that can be valid include:

- **Artifact integrity:** build once, capture the pushed registry digest, and
  propagate the same immutable identity through staging and production.
- **Failure safety:** remove discarded failures and establish a clear successful
  staging gate before production.
- **Release serialization:** use stable, non-cancelling concurrency around the
  production deployment.
- **Terraform boundary:** reject mutable or bare image references at plan time,
  ideally with focused tests and a clear explanation of why this is the selected
  enforcement point.
- **Deployment evidence:** add bounded stabilization/health verification and
  make failure behavior explicit, within the inactive/local boundary.

For an artifact-integrity solution, do not require particular job, step, output,
env, or shell-variable names. Reasonable mechanisms include job outputs, env,
`TF_VAR_image_ref`, `-var`, a saved Terraform plan, transitive staging gates,
or a single ordered deploy job. Probe the operational tradeoffs rather than
deducting for a different shape. Likewise, concurrency may live at workflow or
job level if it uses a stable key and does not cancel an in-flight production
deployment.

Reward a focused, coherent improvement with a clear rationale. Probe whether it
actually addresses the most material risk the candidate identified and whether
the claimed evidence supports the claim. Broadly patching every visible issue is
not inherently stronger than a well-reasoned focused change.

## Hints ladder

Use at most one hint at a time, record the highest level used, and stop when the
candidate resumes productive work. Do not use this ladder before their initial
assessment and ranking are recorded unless they cannot navigate the repository.

1. **Process:** “Which finding has the largest production impact or blast radius,
   and what repository evidence supports that?”
2. **Boundary:** “Compare what staging validates with what production deploys.
   Where is that identity created and preserved?”
3. **Identity:** “What should cross the environment boundary: source, tag, or
   registry-resolved content?”
4. **Concrete:** “One option is to build once, record a
   `repository@sha256:...` value from the pushed image, and pass it unchanged to
   both deployments.”

Levels 1–2 test recovery without prescribing the implementation. Levels 3–4
materially reveal the central finding; needing them lowers the evidence for
independent diagnosis, though the quality of recovery still matters.

## The evaluator is an interviewer aid, not a contract

This branch retains `make acceptance` and `make check`, backed by
`tests/release_policy.py`, `tests/test_release_acceptance.py`,
`tests/test_release_policy.py`, and
`infra/tests/immutable_image.tftest.hcl`. These files are confidential. They are
useful for checking the worked reference and for giving interviewers additional
evidence; they are not exposed to candidates, a hidden pass/fail gate, or the
rubric.

A valid candidate solution may fail the static policy because the candidate is
only asked to implement one improvement or because the analyzer cannot trace its
runtime data flow. Known blind spots include `GITHUB_ENV`, file-based handoffs,
helper scripts, and values that exist only inside shell execution. Judge the
design and explanation on their merits. Never tell a candidate they failed an
undisclosed check, and never alter their repository to install this evaluator.

Conversely, a green reference `make check` does not prove a safe deployment. The
checker cannot establish that a recorded digest matches a pushed manifest, ECS
stabilizes, health checks are meaningful, permissions are correct, or rollback
works under traffic.

## Rollback twist

An acceptable design records the digest promoted to each environment and invokes
the existing deployment path with a selected known-good digest. It may use a
manual workflow input, deployment-record lookup, or automated controller. It
must preserve approvals and serialization, validate the digest, produce an audit
trail, and avoid rebuilding old source. Ask how the candidate selects a
known-good version, prevents forward/rollback races, and confirms recovery.

For a candidate who chose a different improvement, the twist also tests whether
they now connect rollback reliability to immutable artifact identity without
discarding the value of their original prioritization.

## Evidence-based rubric

Score each dimension from 1–4 using observed evidence, then record one overall
score. Diagnosis and prioritization are the leading signal. A candidate meets the
bar only with an overall **3 or 4**, no dimension at 1, and at least 3 in
assessment and prioritization.

### Assessment and prioritization

- **1:** Misses material release risk, offers unsupported opinions, or focuses on
  cosmetic IaC without identifying operational impact.
- **2:** Finds a material concern but gives weak evidence, impact analysis, or
  priority rationale; depends on substantial prompting.
- **3:** Independently recognizes the central artifact-integrity risk or presents
  an equally well-supported production-risk prioritization; ranks findings using
  evidence, impact, and blast radius.
- **4:** Meets 3 and explains interactions among artifact identity, failure
  propagation, concurrency, validation boundaries, and recovery while keeping a
  crisp priority order.

### Chosen improvement and execution

- **1:** The change is unrelated to the assessment, unsafe, or cannot be
  explained.
- **2:** Directionally improves the chosen risk but has a material design gap or
  unjustified churn.
- **3:** Implements one coherent improvement that materially reduces the chosen
  risk, controls scope, and clearly explains tradeoffs and residual exposure.
- **4:** Meets 3 with unusually clean boundaries, deliberate failure behavior,
  and a compelling explanation of why this was the best use of time.

### Validation and operational reasoning

- **1:** Does not validate the change, weakens supplied baseline checks, or
  treats local output as proof of production safety.
- **2:** Runs basic checks but cannot connect results to claims or misses major
  rollout/rollback consequences.
- **3:** Uses focused evidence, states its limits, and gives a credible rollout,
  rollback, and next-step plan for the selected change.
- **4:** Meets 3 and reasons concretely about provenance, bounded waits, health,
  partial failure, approvals, observability, auditability, and recovery where
  relevant.

### Communication and AI judgment

- **1:** Cannot defend submitted work or conceals material AI reliance.
- **2:** Explanation is mostly tool-led or tradeoffs remain unclear.
- **3:** Owns the assessment and every changed line, documents tool use, and
  responds coherently to the twist without AI.
- **4:** Meets 3 and communicates a concise, evidence-led production decision
  while rejecting unnecessary complexity.

### Overall anchors

- **1 — no hire:** Does not identify material production risk or produces an
  unsafe/unowned change.
- **2 — below bar:** Finds something real but needs substantial guidance, cannot
  justify the priority, or spends the exercise on cosmetic IaC while material
  release risk goes unidentified.
- **3 — meets bar:** Independently identifies artifact integrity as central, or
  defends an equally strong priority with evidence; delivers one coherent
  improvement and credible operational reasoning.
- **4 — strong hire:** All meets-bar evidence plus unusually sharp blast-radius
  reasoning, prioritization, validation-boundary awareness, and recovery design.

Concern signals include performing real AWS actions, introducing credentials,
moving the fixture into active workflows, broad Terraform rewrites without a
priority rationale, treating a Git SHA tag as immutable registry identity,
cancelling an in-flight production rollout, counting findings instead of
prioritizing them, or being unable to defend AI-produced work.

## Calibration

Before using the exercise, two interviewers should independently work from fresh
candidate copies without reading this branch. Record setup time, findings and
ranking captured by minute 15, evidence used, selected improvement, completion
time, hints used, ambiguity, and rubric evidence. Do not use time to a hidden
evaluator pass as a calibration target. Revise the fixture if both dry runs hit
the same accidental syntax, environment, or prompt ambiguity. Recalibrate after
substantive task, test, or toolchain changes.

The automated reference dry run proves only that the worked solution and
confidential evaluator remain internally consistent. No human assessment-first
timing has been established yet.

## Safe per-candidate repository copy

Use an opaque candidate identifier. Never fork, clone into the destination, or
share the canonical repository: even a single-branch clone carries reachable
starter history containing earlier answer material. Instead, export the current
candidate tree and create a new repository with one unrelated root commit.

From a trusted local checkout of the canonical repository:

```bash
canonical_repo=/absolute/path/to/devops-interview-exercise
candidate_ref=origin/main
candidate_id=<opaque-id>
snapshot_dir="$(mktemp -d)"

git -C "${canonical_repo}" fetch --prune origin
candidate_sha="$(git -C "${canonical_repo}" rev-parse "${candidate_ref}^{commit}")"
git -C "${canonical_repo}" archive "${candidate_sha}" | tar -x -C "${snapshot_dir}"

git -C "${snapshot_dir}" init -b main
git -C "${snapshot_dir}" add --all
git -C "${snapshot_dir}" \
  -c user.name='TinyFish Recruiting' \
  -c user.email='recruiting@tinyfish.io' \
  commit -m 'Initialize DevOps interview exercise'

gh repo create "paveldudka/devops-interview-${candidate_id}" \
  --private --source="${snapshot_dir}" --remote=origin
git -C "${snapshot_dir}" push --set-upstream origin main
```

Before granting access, verify the destination is private, exposes only `main`,
and has exactly one reachable commit which is also its only root:

```bash
test "$(gh repo view "paveldudka/devops-interview-${candidate_id}" \
  --json visibility --jq '.visibility')" = 'PRIVATE'
test "$(git -C "${snapshot_dir}" ls-remote --heads origin | awk '{print $2}')" \
  = 'refs/heads/main'
test "$(git -C "${snapshot_dir}" rev-list --all --count)" -eq 1
test "$(git -C "${snapshot_dir}" rev-list --max-parents=0 --all --count)" -eq 1
test "$(git -C "${snapshot_dir}" rev-list --all)" \
  = "$(git -C "${snapshot_dir}" rev-parse HEAD)"
```

Verify the tree contains none of the confidential evaluator or solution files:

```bash
for candidate_path in \
  .interviewer \
  tests/release_policy.py \
  tests/test_release_acceptance.py \
  tests/test_release_policy.py \
  infra/tests/immutable_image.tftest.hcl
do
  test ! -e "${snapshot_dir}/${candidate_path}"
done
! grep -Eq '^(acceptance|check):' "${snapshot_dir}/Makefile"
! grep -q 'sha256' "${snapshot_dir}/infra/variables.tf"
grep -q 'Complete this file during the exercise' "${snapshot_dir}/NOTES.md"
```

Finally, prove that no old solution/evaluator blob from the canonical reference
is reachable in the snapshot. The exact path list includes files whose candidate
and solution versions share a name:

```bash
test -z "$(
  comm -12 \
    <(git -C "${canonical_repo}" ls-tree -r --format='%(objectname)' \
      origin/pasha/reference-solution -- \
      .interviewer tests/release_policy.py tests/test_release_acceptance.py \
      tests/test_release_policy.py infra/tests/immutable_image.tftest.hcl \
      exercise/release.yml infra/variables.tf NOTES.md | sort -u) \
    <(git -C "${snapshot_dir}" rev-list --objects --all | \
      awk '{print $1}' | sort -u)
)"
```

The single-root checks prove that no old canonical commit is reachable; the
object intersection check proves that known answer-key blobs are not reachable.
If any verification fails, delete the destination repository before granting
access and rebuild it from a fresh snapshot. Never “fix” the destination by
deleting branches alone.

The candidate tree must not contain:

- `.interviewer/`;
- `tests/release_policy.py`;
- `tests/test_release_acceptance.py`;
- `tests/test_release_policy.py`;
- `infra/tests/immutable_image.tftest.hcl`;
- `make acceptance` or `make check` targets;
- the solved workflow, immutable Terraform validation, or completed reference
  notes.

Grant access only to the candidate and assigned interviewers after all checks
pass. Archive or delete the candidate copy according to the recruiting retention
policy after the loop closes.
