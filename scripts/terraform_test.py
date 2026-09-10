"""Run terraform test and fail unless at least one run block passed.

An empty filter or a test file without run blocks otherwise reports success.
Extra arguments are passed through to terraform test.
"""

import json
import subprocess
import sys


def main(arguments: list[str]) -> int:
    command = ["terraform", "-chdir=infra", "test", "-json", *arguments]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    summary: dict[str, int | str] | None = None
    for line in result.stdout.splitlines():
        event = json.loads(line)
        kind = event.get("type")
        if kind == "test_run" and event["test_run"].get("progress") == "complete":
            run = event["test_run"]
            print(f'{run["path"]}: run "{run["run"]}" {run["status"]}')
        elif kind == "diagnostic":
            diagnostic = event["diagnostic"]
            print(f"{diagnostic['severity']}: {diagnostic['summary']}", file=sys.stderr)
            if diagnostic.get("detail"):
                print(diagnostic["detail"], file=sys.stderr)
        elif kind == "test_summary":
            summary = event["test_summary"]

    if result.returncode != 0:
        print(f"terraform test exited with {result.returncode}", file=sys.stderr)
        return result.returncode
    if summary is None:
        print("terraform test produced no summary", file=sys.stderr)
        return 1
    print(
        f"{summary['passed']} passed, {summary['failed']} failed, "
        f"{summary['errored']} errored"
    )
    if summary["failed"] or summary["errored"] or summary["status"] != "pass":
        return 1
    if summary["passed"] == 0:
        print(
            "no Terraform run block executed; check the test file and filter",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
