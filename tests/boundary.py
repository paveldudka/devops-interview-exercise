"""Neutral repository boundary checks shared by the baseline tests.

These check that repository automation stays local-only and the release
fixture stays inactive. They are regex safety nets, not a sandbox, and they
do not assess the modeled release design.
"""

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        ".terraform",
        ".venv",
        "__pycache__",
        "node_modules",
        "venv",
    }
)

# The live-command scan skips the assessed workflow fixture, Python test
# sources (whose literals describe commands), and Markdown prose. Any other
# file under exercise/ or tests/ (shell, make, YAML) is executable automation
# and stays scanned.
SCAN_EXEMPT_BY_DIRECTORY = {"exercise": (".yml", ".yaml"), "tests": (".py",)}
SCAN_EXEMPT_SUFFIXES = (".md",)

# GNU make would read these before Makefile and bypass its targets.
MAKE_OVERRIDES = ("GNUmakefile", "makefile")

HCL_SUFFIXES = (".tf", ".tfvars", ".hcl")

LINE_CONTINUATION = re.compile(r"\\\r?\n\s*")
HCL_HEREDOC_START = re.compile(r"<<[-~]?(\w+)[ \t]*\r?\n")

# Global flags before the subcommand, with an optional value (`--profile prod`).
GLOBAL_FLAGS = r"(?:\s+-\S+(?:\s+[^-\s]\S*)?)*"
# Tokens separated by whitespace or argv-list punctuation (`"terraform", "apply"`).
ARGV_SEPARATOR = r"(?:\s+|['\"]\s*,\s*['\"])"

# Commands that authenticate to, publish to, or mutate a live environment.
LIVE_COMMAND = re.compile(
    r"\b(?:"
    r"(?:terraform|terragrunt|tofu)"
    rf"(?:{ARGV_SEPARATOR}(?:-\S+|run-all))*{ARGV_SEPARATOR}(?:apply|destroy|import)"
    r"|(?:docker|podman|nerdctl|crane)\s+(?:image\s+|compose\s+|manifest\s+)?push"
    r"|(?:docker|podman|nerdctl)\s+(?:buildx\s+)?build\b[^\n]*\s"
    r"(?:--push\b|(?:--output[= ]|-o[= ]?)type=(?:registry|image\S*push=true))"
    r"|(?:docker|podman|nerdctl)\s+(?:-\S+(?:\s+[^-\s]\S*)?\s+)*login"
    r"|skopeo\s+copy"
    rf"|aws{GLOBAL_FLAGS}\s+ecr(?:-public)?\s+get-login-password"
    rf"|aws{GLOBAL_FLAGS}\s+ecs\s+(?:update-service|register-task-definition|run-task|deploy)"
    rf"|aws{GLOBAL_FLAGS}\s+deploy\s+"
    rf"|kubectl{GLOBAL_FLAGS}\s+(?:apply|rollout|set|scale)"
    rf"|helm{GLOBAL_FLAGS}\s+(?:install|upgrade|rollback)"
    r")\b",
    re.IGNORECASE,
)

# GitHub Actions that authenticate to a cloud or registry, deploy, or publish.
LIVE_ACTION = re.compile(
    r"uses:\s*['\"]?(?:"
    r"aws-actions/configure-aws-credentials"
    r"|aws-actions/amazon-ecs-deploy-task-definition"
    r"|aws-actions/amazon-ecr-login"
    r"|docker/login-action"
    r"|hashicorp/tfc-workflows-github"
    r")\b",
    re.IGNORECASE,
)

# A `push:` input with any value other than a literal false (for example
# docker/build-push-action). Bare and flow-style `{...}` trigger keys are not
# inputs; block scalars and anchors are treated as values, the safe direction.
PUBLISHING_INPUT = re.compile(
    r"^[ \t]*push:[ \t]*(?!['\"]?(?:false|no|off|0)['\"]?[ \t\r]*$)[^\s{].*$",
    re.MULTILINE | re.IGNORECASE,
)

SECRET_PATTERNS = {
    "AWS access key id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    # Exactly 40 key characters; `\b` would miss values ending in `=`, `+`, or `/`.
    "AWS secret access key": re.compile(
        r"aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])",
        re.IGNORECASE,
    ),
    "GitHub token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"
    ),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "private key": re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
}

# Terraform block declarations that reach a backend, live data, or a live
# host. aws_iam_policy_document is rendered client-side and stays allowed.
TERRAFORM_LIVE_DECLARATIONS = {
    "backend block": re.compile(r'^\s*backend\s+"', re.MULTILINE),
    "cloud block": re.compile(r"^\s*cloud\s*{", re.MULTILINE),
    "data source": re.compile(
        r'^\s*data\s+"(?!aws_iam_policy_document")', re.MULTILINE
    ),
    "import block": re.compile(r"^\s*import\s*{", re.MULTILINE),
    "provisioner": re.compile(r'^\s*provisioner\s+"', re.MULTILINE),
}

REAL_PROVIDER_BLOCK = re.compile(r'^\s*provider\s+"aws"', re.MULTILINE)
MOCK_PROVIDER_HEADER = re.compile(r'^\s*mock_provider\s+"aws"\s*\{', re.MULTILINE)
# An aliased mock leaves the default aws provider real.
PROVIDER_ALIAS = re.compile(r"^\s*alias\s*=", re.MULTILINE)


def is_ignored(path: Path, root: Path) -> bool:
    return not IGNORED_DIRECTORIES.isdisjoint(path.relative_to(root).parts)


def read_text(path: Path) -> str:
    """Decode UTF-8 (lossy) or BOM-prefixed UTF-16; the patterns are ASCII."""
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8", errors="replace")


def hcl_string_end(text: str, start: int) -> int:
    """Index just past the quoted string opening at start. Handles backslash
    escapes and quotes nested in `${...}` templates; an unterminated string
    ends at the newline so the following lines stay visible."""
    depth = 0
    i = start + 1
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            return i
        if ch == "\\":
            i += 2
        elif ch in "$%" and text.startswith("{", i + 1):
            depth += 1
            i += 2
        elif depth and ch == "}":
            depth -= 1
            i += 1
        elif ch == '"':
            if not depth:
                return i + 1
            i = hcl_string_end(text, i)
        else:
            i += 1
    return len(text)


def hcl_heredoc_end(text: str, start: int) -> int | None:
    """Index just past the heredoc opening at start, or None if it never closes."""
    opening = HCL_HEREDOC_START.match(text, start)
    if opening is None:
        return None
    terminator = re.compile(
        rf"^[ \t]*{re.escape(opening.group(1))}[ \t]*\r?$", re.MULTILINE
    )
    closing = terminator.search(text, opening.end())
    return None if closing is None else closing.end()


def strip_hcl(text: str, *, strings: bool) -> str:
    """Remove comments in one pass so markers inside strings and quotes inside
    comments are never misread. With strings=True, quoted strings and heredocs
    are blanked as well."""
    kept: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "#" or text.startswith("//", i):
            end = text.find("\n", i)
            i = len(text) if end == -1 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end == -1 else end + 2
        elif ch == '"':
            end = hcl_string_end(text, i)
            kept.append('""' if strings else text[i:end])
            i = end
        elif ch == "<" and (end := hcl_heredoc_end(text, i)) is not None:
            kept.append('""' if strings else text[i:end])
            i = end
        else:
            kept.append(ch)
            i += 1
    return "".join(kept)


def strip_hcl_comments(text: str) -> str:
    return strip_hcl(text, strings=False)


def strip_hash_comments(text: str) -> str:
    """Drop `#` comments (at line start or after whitespace) that sit outside
    single or double quotes; shells and YAML treat a quoted `#` as data.
    Quotes are tracked per line, so an unclosed quote keeps its line visible."""
    kept: list[str] = []
    for line in text.split("\n"):
        quote = ""
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\\" and quote != "'":
                i += 2
                continue
            if quote:
                if ch == quote:
                    quote = ""
            elif ch in "\"'":
                quote = ch
            elif ch == "#" and (i == 0 or line[i - 1].isspace()):
                line = line[:i]
                break
            i += 1
        kept.append(line)
    return "\n".join(kept)


def strip_prose(text: str, *, hcl: bool = False) -> str:
    """Drop comments; for HCL also heredocs and quoted strings, so prose cannot
    look like a command. Shell and YAML keep their quoted strings."""
    if hcl:
        return strip_hcl(text, strings=True)
    return strip_hash_comments(text)


def hcl_block_body(text: str, opening: int) -> str:
    """Top-level text of the block whose `{` is at opening: nested blocks and
    objects are dropped, quoted strings are skipped whole."""
    kept: list[str] = []
    depth = 0
    i = opening
    while i < len(text):
        ch = text[i]
        if ch == '"':
            end = hcl_string_end(text, i)
            if depth == 1:
                kept.append(text[i:end])
            i = end
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        elif depth == 1:
            kept.append(ch)
        i += 1
    return "".join(kept)


def has_default_mock_provider(content: str) -> bool:
    return any(
        not PROVIDER_ALIAS.search(hcl_block_body(content, header.end() - 1))
        for header in MOCK_PROVIDER_HEADER.finditer(content)
    )


def repository_files(root: Path) -> list[Path]:
    """Every non-ignored file and symlink under root, in a stable order."""
    return sorted(
        path
        for path in root.rglob("*")
        if (path.is_file() or path.is_symlink()) and not is_ignored(path, root)
    )


def is_scan_exempt(relative: Path) -> bool:
    exempt_suffixes = SCAN_EXEMPT_BY_DIRECTORY.get(relative.parts[0], ())
    return relative.suffix in SCAN_EXEMPT_SUFFIXES or relative.suffix in exempt_suffixes


def find_secrets(root: Path) -> list[str]:
    findings: list[str] = []
    for path in repository_files(root):
        if path.is_symlink():
            continue
        content = read_text(path)
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(root)}: {label}")
    return findings


def find_live_automation(text: str, *, hcl: bool = False) -> list[str]:
    """Live deployment commands or actions in one automation file."""
    joined = LINE_CONTINUATION.sub(" ", strip_prose(text, hcl=hcl))
    matches = [match.group(0) for match in LIVE_COMMAND.finditer(joined)]
    matches.extend(match.group(0) for match in LIVE_ACTION.finditer(joined))
    matches.extend(
        match.group(0).strip() for match in PUBLISHING_INPUT.finditer(joined)
    )
    return matches


def find_live_automation_in_repository(root: Path) -> list[str]:
    """Live deployment paths in any non-exempt file; symlinks are flagged, not followed."""
    findings: list[str] = []
    # Exact names: stat() would resolve `makefile` to Makefile on macOS mounts.
    present = {entry.name for entry in os.scandir(root)}
    for name in MAKE_OVERRIDES:
        if name in present:
            findings.append(f"{name}: overrides Makefile targets")
    for path in repository_files(root):
        relative = path.relative_to(root)
        if path.is_symlink():
            findings.append(f"{relative}: symlink")
            continue
        if is_scan_exempt(relative):
            continue
        hcl = path.name.endswith(HCL_SUFFIXES)
        for match in find_live_automation(read_text(path), hcl=hcl):
            findings.append(f"{relative}: {match}")
    return findings


def terraform_files(root: Path, pattern: str) -> list[Path]:
    return [path for path in sorted(root.rglob(pattern)) if not is_ignored(path, root)]


def find_terraform_live_declarations(root: Path) -> list[str]:
    """Live declarations in every Terraform file under root, comments removed."""
    findings: list[str] = []
    for path in terraform_files(root, "*.tf") + terraform_files(root, "*.tftest.hcl"):
        content = strip_hcl_comments(read_text(path))
        for label, pattern in TERRAFORM_LIVE_DECLARATIONS.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(root)}: {label}")
    return findings


def find_unmocked_terraform_tests(infra: Path) -> list[str]:
    findings: list[str] = []
    for path in terraform_files(infra, "*.tftest.hcl"):
        content = strip_hcl_comments(read_text(path))
        if not has_default_mock_provider(content):
            findings.append(f'{path.relative_to(infra)}: missing mock_provider "aws"')
        if REAL_PROVIDER_BLOCK.search(content):
            findings.append(f"{path.relative_to(infra)}: declares a real aws provider")
    return findings


def find_undiscoverable_terraform_tests(infra: Path) -> list[str]:
    """terraform test only reads *.tftest.hcl in the module root and tests/."""
    return [
        str(path.relative_to(infra))
        for path in terraform_files(infra, "*.tftest.hcl")
        if path.parent not in (infra, infra / "tests")
    ]
