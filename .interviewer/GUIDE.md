# Interviewer guide

This file and this branch are confidential interviewer material. Never send the
canonical repository, a branch URL, a PR URL, or this guide to a candidate.
Candidates receive a new private repository whose only branch is the candidate
starter commit.

## Before the session

1. Generate an isolated candidate repository using the procedure below.
2. Ask the candidate to open its devcontainer and run `make verify-env` before
   the interview. Do not start the timer until the environment is ready.
3. Confirm screen sharing. Remind them that AI and documentation are allowed
   during implementation, while the final walkthrough is AI-free.
4. Keep this guide and the reference branch out of shared screens and chat.

## Facilitation script (75 minutes)

- **0–10 — orientation:** Have the candidate read `CANDIDATE.md`, inspect the
  fixture and tests, and ask questions. Clarify that nothing should contact AWS
  and `example.invalid` will never resolve.
- **10–50 — implementation:** Observe prioritization, validation, tool use, and
  scope control. Answer environment questions without volunteering the design.
- **50–60 — requirement twist:** “Rollback must redeploy the previously promoted
  artifact without rebuilding it. Show or explain the smallest change you would
  make.” Code is optional if the base task consumed the time.
- **60–75 — AI-free defense:** Ask them to stop AI use and explain the diff,
  failure behavior, rollout, rollback, test boundary, and residual risks.

## What the candidate is asked

`CANDIDATE.md` states outcomes only and prescribes no implementation. The
candidate must change `exercise/release.yml` and `infra/` so that:

1. one release builds the image once;
2. staging and production deploy the same immutable reference to that image;
3. production starts only after staging succeeded and no failure can be
   ignored;
4. a second production release waits for the first and never cancels it; and
5. Terraform rejects tags and bare image names.

Job, step, output, and variable names are explicitly the candidate's choice.
The brief does not require a separate build job, a job output named
`image_ref`, or any particular number of jobs. Do not describe the reference
design below as “the expected answer” when clarifying the task.

## Reference design (interviewer-only)

This branch's `exercise/release.yml` is one calibrated solution: a `build` job
publishes once with `docker/build-push-action`, records
`repository@sha256:...` from the action's digest output as a job output, and
staging and production jobs both pass that output to `terraform apply`.
Production needs staging and sets a stable, non-cancelling concurrency group.
`infra/variables.tf` validates the digest form. `NOTES.md` on this branch is a
reference write-up, not the candidate template.

Use this as a mental model for probing questions, not as a diff to match.

## Hints ladder

Give at most one hint at a time and record the level used. Hints 3 and 4 steer
toward the reference shape; accept any equivalent shape the candidate reaches.

1. **Orient:** “What identity should cross the environment boundary: source,
   tag, or registry-resolved content?”
2. **Locate:** “Look at how the value passed to each Terraform apply is
   produced, and how it reaches the second environment.”
3. **Structure:** “A small solution builds in one place and hands a single
   recorded value to both deployments, with production waiting on staging.”
4. **Concrete:** “Record a `repository@sha256:...` value from the pushed image,
   pass it unchanged to both applies, and add a stable production concurrency
   group that does not cancel in-progress runs.”

One orienting hint is normal. Needing hint 3 or 4 for core requirements is a
concern for a senior candidate, though recovery quality still matters.

## Acceptable alternatives

`make acceptance` runs an outcome-based static policy (`tests/release_policy.py`)
whose behaviour is pinned by `tests/test_release_policy.py`. It passes for any
of the following, so none of them is a deduction:

- **Any names.** Jobs, steps, outputs, env keys, and shell variables may be
  called anything. Only the Terraform variable `image_ref` is fixed by the
  module.
- **Any build mechanism it recognises.** `docker build`, `docker buildx
  build`/`bake`, `podman`/`buildah`/`nerdctl`, `docker/build-push-action`, or
  `docker/bake-action`, as long as exactly one build occurs per release.
- **Any traceable hand-off.** The reference may flow through job outputs,
  `env` at workflow/job/step scope, shell variables expanded from that env,
  `TF_VAR_image_ref`, or `-var` on the apply line, and may be composed as
  `repository@<recorded digest>` or recorded whole. A `terraform plan -out`
  followed by `terraform apply <plan>` in the same job is also understood.
- **Transitive staging gates.** Production may depend on staging through
  intermediate jobs (smoke tests, approvals, soak) rather than directly.
- **Single ordered deploy job.** One job that applies staging and then
  production in step order passes, provided it keeps the failure and
  concurrency outcomes. Probe what is lost: per-environment GitHub environment
  protection and approvals, and the ability to rerun production alone.
- **Concurrency at either level.** A workflow-level or job-level group is fine
  when its expressions use only stable contexts (`github.workflow`,
  `github.repository`, and similar) and `cancel-in-progress` is not true.
- **Scalar or mapped GitHub environments**, and environment inferred from the
  `-var-file` name when no GitHub environment is declared.

## The policy checker is not the rubric

The checker is a visible safety net for the candidate, not the scoring
instrument. Score with the rubric below and the candidate's explanation.

- Do not penalize a coherent design solely because static analysis cannot
  follow it. Known blind spots: values written to `GITHUB_ENV` or a file at
  runtime, digests produced by a helper script whose text the workflow never
  shows (the recording step must visibly mention `digest` or `@sha256:`), and
  anything that only exists inside a shell command. If the candidate hits one
  of these, ask them to explain the data flow and judge the design on its
  merits; a candidate who then adapts to make the value traceable, without
  weakening the design, is showing good judgement rather than fixing a defect.
- Conversely, a green `make check` is not proof of a safe release. The checks
  cannot see whether the recorded digest matches the pushed manifest, whether
  ECS stabilises, or whether rollback works. Candidates who present a passing
  check as deployment proof have missed the boundary documented in
  `docs/architecture.md`.
- A candidate who edits `tests/`, `infra/tests/`, or the Makefile to make
  checks pass has weakened the supplied checks; that is a concern signal, not
  an alternative.

## Expected findings

Core findings:

- staging and production independently rebuild source;
- both deploy a mutable `:latest` reference;
- production releases can overlap;
- `continue-on-error` and `|| true` allow unsafe progress; and
- Terraform accepts any image string.

Strong candidates also discuss registry digest capture, propagation of a single
recorded value without re-derivation, bounded deployment waits, health
evidence, auditability, and why mocked tests do not prove a live ECS rollout.

Do not score by issue count. The core signal is a small coherent change, useful
validation, and understanding of the operational boundary.

## Rollback twist

An acceptable design records the digest promoted to each environment and invokes
the existing deployment path with a selected known-good digest. It may use a
manual workflow input, deployment-record lookup, or automated controller. It
must preserve approvals and serialization, validate the digest, produce an audit
trail, and avoid rebuilding old source. Ask how the candidate selects a
known-good version, prevents forward/rollback races, and confirms recovery.

## Evidence-based rubric

Score each dimension from 1–4 using observed evidence, then record one overall
score. A candidate meets the bar only with an overall **3 or 4**, no dimension at
1, and at least 3 in artifact integrity and operational safety.

### Artifact integrity

- **1:** Still rebuilds per environment or deploys a mutable/bare reference.
- **2:** Recognizes the risk but propagation is incomplete or not validated.
- **3:** Builds once, derives a registry digest, and passes the same immutable
  reference to both environment deployments by whatever mechanism.
- **4:** Meets 3 and explains registry identity, provenance, auditability, and
  artifact retention for rollback.

### Operational safety

- **1:** Promotion can ignore failure or overlapping production changes remain.
- **2:** Adds partial sequencing or concurrency with material unsafe gaps.
- **3:** Production waits for successful staging, failure propagates, and stable
  concurrency queues production deployments without cancellation.
- **4:** Meets 3 and reasons concretely about bounded waits, health checks,
  partial failure, approvals, and recovery.

### Validation and execution

- **1:** Does not run checks or weakens supplied tests to pass.
- **2:** Runs some checks but cannot explain failures or introduces broad churn.
- **3:** Uses baseline and acceptance feedback, keeps changes focused, and leaves
  coherent notes.
- **4:** Meets 3, adds useful focused evidence, and distinguishes static/mock
  proof from live-system proof.

### Communication and AI judgment

- **1:** Cannot explain submitted code or conceals material AI reliance.
- **2:** Explanation is mostly tool-led or misses key tradeoffs.
- **3:** Owns every line, documents tool use, explains tradeoffs, and responds to
  the twist without AI.
- **4:** Meets 3 and communicates a crisp production rollout/rollback plan while
  rejecting unnecessary complexity.

### Overall anchors

- **1 — no hire:** Core artifact or failure-safety invariant remains broken.
- **2 — below bar:** Directionally correct but needs substantial guidance or
  leaves a material safety gap.
- **3 — meets bar:** Focused passing solution, sound operational reasoning, clear
  ownership, and a credible digest-based rollback response.
- **4 — strong hire:** All meets-bar evidence plus unusually strong prioritization,
  test-boundary awareness, recovery design, and clear senior-level tradeoffs.

Concern signals include performing real AWS actions, introducing credentials,
moving the fixture into active workflows, weakening tests, broad Terraform
rewrites, treating a Git SHA tag as immutable registry identity, cancelling an
in-flight production rollout, or being unable to defend AI-produced code.

## Calibration

Before using the exercise, two interviewers should independently work from fresh
candidate copies without reading this branch. Record setup time, time to the base
acceptance pass, hints used, ambiguity, and rubric evidence. Target 20–25 minutes
for an engineer already familiar with the fixture, leaving a candidate roughly
40 minutes. Revise the fixture if both dry runs hit the same accidental syntax or
environment problem. Recalibrate after substantive test or toolchain changes.

The automated reference dry run is recorded in the branch handoff. It proves the
reference passes the commands, not human completion time; no actual human timing
has been established yet.

## Safe per-candidate repository copy

Use an opaque candidate identifier. Never fork the canonical repository and
never push the reference branch. From a clean temporary directory:

```bash
git clone --single-branch --branch pasha/build-interview-exercise \
  git@github.com:paveldudka/devops-interview-exercise.git candidate-repo
cd candidate-repo
git remote remove origin
git branch -M main
gh repo create paveldudka/devops-interview-<opaque-id> \
  --private --source=. --remote=origin
git push --set-upstream origin main
git ls-remote --heads origin
```

Verify the final command lists only `refs/heads/main`, `.interviewer/` does not
exist, and visibility is private. Grant access only to the candidate and assigned
interviewers. Archive or delete the candidate copy according to the recruiting
retention policy after the loop closes.
