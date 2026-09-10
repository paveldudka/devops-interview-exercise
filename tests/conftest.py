"""A skipped, xfailed, or xpassed baseline check proves nothing, so it fails the run."""

import pytest

BASELINE_MODULE = "tests/test_repository_baseline.py"
baseline_nodeids: set[str] = set()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    baseline_nodeids.update(
        item.nodeid for item in items if item.get_closest_marker("baseline")
    )


def pytest_collectreport(report: pytest.CollectReport) -> None:
    if report.skipped and report.nodeid.startswith(BASELINE_MODULE):
        pytest.exit(
            f"baseline module {report.nodeid} was skipped during collection; "
            "baseline checks must run and pass",
            returncode=1,
        )


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.nodeid not in baseline_nodeids:
        return
    if report.skipped or (report.when == "call" and hasattr(report, "wasxfail")):
        pytest.exit(
            f"baseline check {report.nodeid} was skipped, xfailed, or xpassed; "
            "baseline checks must run and pass",
            returncode=1,
        )
