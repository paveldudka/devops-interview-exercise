"""Regression tests for the terraform test runner's exit decisions."""

import json

import pytest

from run_terraform_tests import evaluate


def summary(**counts: object) -> str:
    fields: dict[str, object] = {
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


def test_blank_lines_are_ignored() -> None:
    output = "\n".join(["", run_event("pass"), "  ", summary(passed=1), "\t", ""])
    assert evaluate(output, 0) == 0


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
def test_failed_errored_or_skipped_runs_fail(counts: dict[str, object]) -> None:
    assert evaluate(summary(**counts), 0) == 1


@pytest.mark.parametrize(
    "counts",
    [
        {"passed": None},
        {"passed": "1"},
        {"passed": 1, "failed": None},
        {"passed": 1, "failed": "0"},
        {"passed": True},
        {"passed": 1.0},
    ],
)
def test_non_integer_counters_fail(
    capsys: pytest.CaptureFixture[str], counts: dict[str, object]
) -> None:
    assert evaluate(summary(**counts), 0) == 1
    assert "non-integer counters" in capsys.readouterr().err


@pytest.mark.parametrize("test_summary", [None, "pass", 1, [], [{"passed": 1}]])
def test_non_object_summary_fails(test_summary: object) -> None:
    line = json.dumps({"type": "test_summary", "test_summary": test_summary})
    assert evaluate("\n".join([run_event("pass"), line]), 0) == 1


def test_missing_summary_fails() -> None:
    assert evaluate(run_event("pass"), 0) == 1


def test_terraform_exit_code_propagates() -> None:
    assert evaluate(summary(passed=1), 1) == 1


@pytest.mark.parametrize("returncode", [0, 2])
@pytest.mark.parametrize(
    "line", ["Terraform v1.9.8", "[]", '"text"', "1", "null", "true", '[{"type": 1}]']
)
def test_non_event_output_fails_with_explanation(
    capsys: pytest.CaptureFixture[str], returncode: int, line: str
) -> None:
    assert evaluate("\n".join([line, summary(passed=1)]), returncode) != 0
    assert "unexpected output" in capsys.readouterr().err


@pytest.mark.parametrize(
    "event",
    [
        {"type": "test_run", "test_run": None},
        {"type": "test_run", "test_run": "complete"},
        {"type": "diagnostic", "diagnostic": None},
        {"type": "diagnostic", "diagnostic": {"range": "here"}},
        {"type": "diagnostic", "diagnostic": {"range": {"start": 3}}},
        {"type": 7},
    ],
)
def test_malformed_events_do_not_crash(event: dict[str, object]) -> None:
    output = "\n".join([json.dumps(event), run_event("pass"), summary(passed=1)])
    assert evaluate(output, 0) == 0


def test_missing_terraform_binary_is_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from run_terraform_tests import main

    monkeypatch.setenv("PATH", "")
    assert main([]) == 1
    assert "terraform not found" in capsys.readouterr().err


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
