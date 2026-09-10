"""Run terraform test; fail unless every run block passed and at least one ran.

terraform test itself exits 0 with "0 passed" for a filter that matches no
file or a file without run blocks. Extra arguments are passed through.
"""

import json
import subprocess
import sys

COUNTERS = ("passed", "failed", "errored", "skipped")


def as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def counters(summary: dict[str, object]) -> dict[str, int] | None:
    """The four run counters, or None if any is missing an integer value."""
    counts: dict[str, int] = {}
    for key in COUNTERS:
        value = summary.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        counts[key] = value
    return counts


def evaluate(stdout: str, returncode: int) -> int:
    """Turn terraform test -json output into an exit code, printing progress."""
    summary: dict[str, object] | None = None
    unexpected: list[str] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            event = None
        if not isinstance(event, dict):
            unexpected.append(line)
            continue
        kind = event.get("type")
        run = as_dict(event.get("test_run"))
        if kind == "test_run" and run.get("progress") == "complete":
            print(
                f'{run.get("path", "?")}: run "{run.get("run", "?")}" '
                f"{run.get('status', 'unknown')}"
            )
        elif kind == "diagnostic":
            diagnostic = as_dict(event.get("diagnostic"))
            where = as_dict(diagnostic.get("range"))
            start = as_dict(where.get("start"))
            location = f"{where.get('filename', '')}:{start.get('line', '')}"
            print(
                f"{diagnostic.get('severity', 'error')}: {diagnostic.get('summary', '')}"
                f"{f' ({location})' if location != ':' else ''}",
                file=sys.stderr,
            )
            if diagnostic.get("detail"):
                print(diagnostic["detail"], file=sys.stderr)
        elif kind == "test_summary":
            summary = as_dict(event.get("test_summary"))

    if unexpected:
        print(
            "unexpected output from terraform test; expected one JSON event per line"
            " (wrapper enabled?):",
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
    counts = counters(summary)
    if counts is None:
        print(
            f"terraform test summary has non-integer counters: {summary}",
            file=sys.stderr,
        )
        return 1
    print(", ".join(f"{count} {key}" for key, count in counts.items()))
    if counts["failed"] or counts["errored"] or counts["skipped"]:
        return 1
    if summary.get("status") != "pass":
        print(
            f"terraform test summary status is {summary.get('status')!r}",
            file=sys.stderr,
        )
        return 1
    if counts["passed"] == 0:
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
