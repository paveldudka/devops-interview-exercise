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

## Hints ladder

Give at most one hint at a time and record the level used.

1. **Orient:** “What identity should cross the environment boundary: source,
   tag, or registry-resolved content?”
2. **Locate:** “Look at job outputs and the value passed to both Terraform apply
   commands.”
3. **Structure:** “A small solution can use one build job followed by staging and
   production jobs.”
4. **Concrete:** “Export a `repository@sha256:...` value, make production depend
   on staging, and add a stable production concurrency group.”

One orienting hint is normal. Needing hint 3 or 4 for core requirements is a
concern for a senior candidate, though recovery quality still matters.

## Expected findings

Core findings:

- staging and production independently rebuild source;
- both deploy a mutable `:latest` reference;
- production releases can overlap;
- `continue-on-error` and `|| true` allow unsafe progress; and
- Terraform accepts any image string.

Strong candidates also discuss registry digest capture, direct propagation of a
single output, bounded deployment waits, health evidence, auditability, and why
mocked tests do not prove a live ECS rollout.

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
- **3:** Builds once, derives a registry digest, and passes the same output to
  both environment deployments.
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
