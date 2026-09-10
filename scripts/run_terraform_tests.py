"""Run terraform test; fail unless every run block passed and at least one ran.

terraform test itself exits 0 with "0 passed" for a filter that matches no
file or a file without run blocks. Extra arguments are passed through.
"""

import json
import subprocess
import sys
from typing import TypedDict


class Summary(TypedDict, total=False):
    status: str
    passed: int
    failed: int
    errored: int
    skipped: int


def evaluate(stdout: str, returncode: int) -> int:
    """Turn terraform test -json output into an exit code, printing progress."""
    summary: Summary | None = None
    unexpected: list[str] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            unexpected.append(line)
            continue
        kind = event.get("type")
        if (
            kind == "test_run"
            and event.get("test_run", {}).get("progress") == "complete"
        ):
            run = event["test_run"]
            print(
                f'{run.get("path", "?")}: run "{run.get("run", "?")}" '
                f"{run.get('status', 'unknown')}"
            )
        elif kind == "diagnostic":
            diagnostic = event.get("diagnostic", {})
            where = diagnostic.get("range", {})
            location = (
                f"{where.get('filename', '')}:{where.get('start', {}).get('line', '')}"
            )
            print(
                f"{diagnostic.get('severity', 'error')}: {diagnostic.get('summary', '')}"
                f"{f' ({location})' if location != ':' else ''}",
                file=sys.stderr,
            )
            if diagnostic.get("detail"):
                print(diagnostic["detail"], file=sys.stderr)
        elif kind == "test_summary":
            summary = event.get("test_summary", {})

    if unexpected:
        print(
            "unexpected non-JSON output from terraform test (wrapper enabled?):",
            *unexpected,
            sep="\n",
            file=sys.stderr,
        )
    if returncode != 0:
        print(f"terraform test exited with {returncode}", file=sys.stderr)
        return returncode
    if unexpected:
        return 1
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
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        print("terraform not found on PATH; run: make verify-env", file=sys.stderr)
        return 1
    code = evaluate(result.stdout, result.returncode)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
