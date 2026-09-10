"""Run terraform test and fail unless at least one run block passed.

A filter that matches no file, or a file without run blocks, otherwise
reports success. Extra arguments are passed through to terraform test.
"""

import json
import subprocess
import sys
from typing import TypedDict


class Summary(TypedDict):
    status: str
    passed: int
    failed: int
    errored: int
    skipped: int


def evaluate(stdout: str, returncode: int) -> int:
    """Turn terraform test -json output into an exit code, printing progress."""
    summary: Summary | None = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            print(
                f"unexpected non-JSON output from terraform test (wrapper enabled?): "
                f"{line!r}",
                file=sys.stderr,
            )
            return 1
        kind = event.get("type")
        if kind == "test_run" and event["test_run"].get("progress") == "complete":
            run = event["test_run"]
            print(f'{run["path"]}: run "{run["run"]}" {run.get("status", "unknown")}')
        elif kind == "diagnostic":
            diagnostic = event["diagnostic"]
            print(
                f"{diagnostic.get('severity', 'error')}: {diagnostic.get('summary', '')}",
                file=sys.stderr,
            )
            if diagnostic.get("detail"):
                print(diagnostic["detail"], file=sys.stderr)
        elif kind == "test_summary":
            summary = event["test_summary"]

    if returncode != 0:
        print(f"terraform test exited with {returncode}", file=sys.stderr)
        return returncode
    if summary is None:
        print("terraform test produced no summary", file=sys.stderr)
        return 1
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    errored = summary.get("errored", 0)
    skipped = summary.get("skipped", 0)
    print(f"{passed} passed, {failed} failed, {errored} errored, {skipped} skipped")
    if failed or errored or skipped or summary.get("status") != "pass":
        return 1
    if passed == 0:
        print(
            "no Terraform run block executed; check the test file and filter",
            file=sys.stderr,
        )
        return 1
    return 0


def main(arguments: list[str]) -> int:
    command = ["terraform", "-chdir=infra", "test", "-json", *arguments]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    code = evaluate(result.stdout, result.returncode)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
