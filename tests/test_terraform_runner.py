"""Regression tests for the terraform test runner's exit decisions."""

import json

import pytest

from run_terraform_tests import evaluate


def summary(**counts: int | str) -> str:
    fields: dict[str, int | str] = {
        "status": "pass",
        "passed": 0,
        "failed": 0,
        "errored": 0,
        "skipped": 0,
    }
    fields.update(counts)
    return json.dumps({"type": "test_summary", "test_summary": fields})


def run_event(status: str) -> str:
    return json.dumps(
        {
            "type": "test_run",
            "test_run": {
                "path": "tests/x.tftest.hcl",
                "run": "r",
                "progress": "complete",
                "status": status,
            },
        }
    )


def test_passing_run_succeeds() -> None:
    assert evaluate("\n".join([run_event("pass"), summary(passed=1)]), 0) == 0


def test_zero_passed_runs_fail_even_when_terraform_reports_success() -> None:
    # terraform test exits 0 with "0 passed" for an unmatched filter.
    assert evaluate(summary(passed=0), 0) == 1


@pytest.mark.parametrize(
    "counts",
    [
        {"passed": 1, "failed": 1, "status": "fail"},
        {"passed": 1, "errored": 1, "status": "fail"},
        {"passed": 1, "skipped": 1},
        {"passed": 1, "status": "fail"},
    ],
)
def test_failed_errored_or_skipped_runs_fail(counts: dict[str, int | str]) -> None:
    assert evaluate(summary(**counts), 0) == 1


def test_missing_summary_fails() -> None:
    assert evaluate(run_event("pass"), 0) == 1


def test_terraform_exit_code_propagates() -> None:
    assert evaluate(summary(passed=1), 1) == 1


def test_non_json_output_fails_with_explanation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert evaluate("Terraform v1.9.8\n" + summary(passed=1), 0) == 1
    assert "non-JSON" in capsys.readouterr().err


def test_diagnostics_are_shown(capsys: pytest.CaptureFixture[str]) -> None:
    diagnostic = json.dumps(
        {
            "type": "diagnostic",
            "diagnostic": {"severity": "error", "summary": "boom", "detail": "why"},
        }
    )
    assert evaluate("\n".join([diagnostic, summary(errored=1, status="fail")]), 0) == 1
    captured = capsys.readouterr()
    assert "error: boom" in captured.err
    assert "why" in captured.err
