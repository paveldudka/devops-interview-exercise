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

# The live-command scan skips everything under these directories (the assessed
# fixture; Python tests whose literals describe commands) and Markdown prose.
SCAN_EXEMPT_PREFIXES = ("exercise", "tests")
SCAN_EXEMPT_SUFFIXES = (".md",)

# GNU make would read these before Makefile and bypass its targets.
MAKE_OVERRIDES = ("GNUmakefile", "makefile")

HCL_SUFFIXES = (".tf", ".tfvars", ".hcl")

LINE_CONTINUATION = re.compile(r"\\\r?\n\s*")
# A `#` comment, full-line or trailing, only when no quote precedes it on the
# line; shells treat `#` inside quotes as data.
HASH_COMMENT = re.compile(r"^([^\"'\n]*?)(?:^|(?<=\s))#.*$", re.MULTILINE)
HCL_LINE_COMMENT = re.compile(r"^([^\"\n]*?)(?:^|(?<=\s))(?:#|//).*$", re.MULTILINE)
HCL_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
HCL_HEREDOC = re.compile(r"<<[-~]?(\w+)\r?\n.*?^[ \t]*\1\b", re.DOTALL | re.MULTILINE)
HCL_STRING = re.compile(r'"(?:\\.|[^"\\\n])*"')

# Commands that authenticate to, publish to, or mutate a live environment.
LIVE_COMMAND = re.compile(
    r"\b(?:"
    r"(?:terraform|terragrunt|tofu)(?:\s+(?:-\S+|run-all))*\s+(?:apply|destroy|import)"
    r"|(?:docker|podman|nerdctl|crane)\s+(?:image\s+|compose\s+|manifest\s+)?push"
    r"|(?:docker|podman|nerdctl)\s+(?:buildx\s+)?build\b[^\n]*\s"
    r"(?:--push\b|(?:--output[= ]|-o[= ]?)type=(?:registry|image\S*push=true))"
    r"|(?:docker|podman|nerdctl)\s+(?:-\S+(?:\s+[^-\s]\S*)?\s+)*login"
    r"|skopeo\s+copy"
    r"|aws\s+ecr(?:-public)?\s+get-login-password"
    r"|aws\s+ecs\s+(?:update-service|register-task-definition|run-task|deploy)"
    r"|aws\s+deploy\s+"
    r"|kubectl\s+(?:apply|rollout|set|scale)"
    r"|helm\s+(?:install|upgrade|rollback)"
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
    "AWS secret access key": re.compile(
        r"aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}\b", re.IGNORECASE
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
# An aliased mock leaves the default aws provider real.
DEFAULT_MOCK_PROVIDER_BLOCK = re.compile(
    r'^\s*mock_provider\s+"aws"\s*\{(?![^}]*\balias\s*=)', re.MULTILINE
)


def is_ignored(path: Path, root: Path) -> bool:
    return not IGNORED_DIRECTORIES.isdisjoint(path.relative_to(root).parts)


def read_text(path: Path) -> str:
    """Decode UTF-8 (lossy) or BOM-prefixed UTF-16; the patterns are ASCII."""
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8", errors="replace")


def strip_hcl_comments(text: str) -> str:
    return HCL_LINE_COMMENT.sub(r"\1", HCL_BLOCK_COMMENT.sub("", text))


def strip_prose(text: str, *, hcl: bool = False) -> str:
    """Drop comments; for HCL also heredocs and quoted strings, so prose cannot
    look like a command. Shell and YAML keep their quoted strings."""
    if not hcl:
        return HASH_COMMENT.sub(r"\1", text)
    text = HCL_BLOCK_COMMENT.sub("", text)
    text = HCL_HEREDOC.sub('""', text)
    text = HCL_STRING.sub('""', text)
    return HCL_LINE_COMMENT.sub(r"\1", text)


def repository_files(root: Path) -> list[Path]:
    """Every non-ignored file and symlink under root, in a stable order."""
    return sorted(
        path
        for path in root.rglob("*")
        if (path.is_file() or path.is_symlink()) and not is_ignored(path, root)
    )


def is_scan_exempt(relative: Path) -> bool:
    return relative.parts[0] in SCAN_EXEMPT_PREFIXES or relative.suffix in (
        SCAN_EXEMPT_SUFFIXES
    )


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
        if not DEFAULT_MOCK_PROVIDER_BLOCK.search(content):
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
