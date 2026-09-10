"""A skipped or xfailed baseline check proves nothing, so it fails the run."""

import pytest


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if "baseline" not in report.keywords:
        return
    if report.skipped or (report.when == "call" and hasattr(report, "wasxfail")):
        pytest.exit(
            f"baseline check {report.nodeid} was skipped or xfailed; "
            "baseline checks must run and pass",
            returncode=1,
        )
