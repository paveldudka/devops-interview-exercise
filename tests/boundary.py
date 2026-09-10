"""Neutral repository boundary checks shared by the baseline tests.

These prove the repository stays local-only and inactive. They do not assess
the modeled release design.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

IGNORED_DIRECTORIES = frozenset(
    {".git", ".pytest_cache", ".ruff_cache", ".terraform", ".venv", "__pycache__"}
)

# Paths whose contents GitHub, the devcontainer, or make execute directly.
EXECUTABLE_AUTOMATION = (".github", ".devcontainer", "scripts", "Makefile")

LINE_CONTINUATION = re.compile(r"\\\r?\n\s*")

# Commands that publish an image or change a live environment.
LIVE_COMMAND = re.compile(
    r"\b(?:"
    r"(?:terraform|terragrunt|tofu)(?:\s+(?:-\S+|run-all))*\s+(?:apply|destroy|import)"
    r"|docker\s+(?:image\s+)?push"
    r"|docker\s+(?:buildx\s+)?build\b[^\n]*\s--push\b"
    r"|docker\s+login"
    r"|aws\s+ecr\s+get-login-password"
    r"|aws\s+ecs\s+(?:update-service|register-task-definition|run-task|deploy)"
    r"|aws\s+deploy\s+"
    r"|kubectl\s+(?:apply|rollout|set|scale)"
    r"|helm\s+(?:install|upgrade|rollback)"
    r")\b",
    re.IGNORECASE,
)

# GitHub Actions that authenticate to AWS or deploy or publish artifacts.
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

# docker/build-push-action publishes only when push is enabled.
PUBLISHING_INPUT = re.compile(r"^\s*push:\s*['\"]?true['\"]?\s*$", re.MULTILINE)

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

# Terraform declarations that reach a backend, live data, or a live host.
TERRAFORM_LIVE_DECLARATIONS = {
    "backend block": re.compile(r'^\s*backend\s+"', re.MULTILINE),
    "cloud block": re.compile(r"^\s*cloud\s*{", re.MULTILINE),
    "data source": re.compile(r'^\s*data\s+"', re.MULTILINE),
    "import block": re.compile(r"^\s*import\s*{", re.MULTILINE),
    "provisioner": re.compile(r'^\s*provisioner\s+"', re.MULTILINE),
    "remote state": re.compile(r"terraform_remote_state"),
}

REAL_PROVIDER_BLOCK = re.compile(r'^\s*provider\s+"aws"', re.MULTILINE)
MOCK_PROVIDER_BLOCK = re.compile(r'^\s*mock_provider\s+"aws"', re.MULTILINE)


def is_ignored(path: Path, root: Path) -> bool:
    return not IGNORED_DIRECTORIES.isdisjoint(path.relative_to(root).parts)


def read_text(path: Path) -> str | None:
    """Return decoded text, or None for binary or non-UTF-8 files."""
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def text_files(root: Path, *, within: tuple[str, ...] = ("",)) -> list[Path]:
    """Text files under root, limited to the given repo-relative prefixes."""
    files: list[Path] = []
    for prefix in within:
        start = root / prefix
        candidates = [start] if start.is_file() else sorted(start.rglob("*"))
        for path in candidates:
            if path.is_file() and not is_ignored(path, root):
                files.append(path)
    return files


def find_secrets(root: Path) -> list[str]:
    findings: list[str] = []
    for path in text_files(root):
        content = read_text(path)
        if content is None:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(root)}: {label}")
    return findings


def find_live_automation(text: str) -> list[str]:
    """Live deployment commands or actions in one automation file."""
    joined = LINE_CONTINUATION.sub(" ", text)
    matches = [match.group(0) for match in LIVE_COMMAND.finditer(joined)]
    matches.extend(match.group(0) for match in LIVE_ACTION.finditer(joined))
    matches.extend(
        match.group(0).strip() for match in PUBLISHING_INPUT.finditer(joined)
    )
    return matches


def find_live_automation_in_repository(root: Path) -> list[str]:
    findings: list[str] = []
    for path in text_files(root, within=EXECUTABLE_AUTOMATION):
        content = read_text(path)
        if content is None:
            continue
        for match in find_live_automation(content):
            findings.append(f"{path.relative_to(root)}: {match}")
    return findings


def find_terraform_live_declarations(infra: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(infra.rglob("*.tf")) + sorted(infra.rglob("*.tftest.hcl")):
        if is_ignored(path, infra):
            continue
        content = path.read_text(encoding="utf-8")
        for label, pattern in TERRAFORM_LIVE_DECLARATIONS.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(infra)}: {label}")
    return findings


def find_unmocked_terraform_tests(infra: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(infra.rglob("*.tftest.hcl")):
        if is_ignored(path, infra):
            continue
        content = path.read_text(encoding="utf-8")
        if not MOCK_PROVIDER_BLOCK.search(content):
            findings.append(f'{path.relative_to(infra)}: missing mock_provider "aws"')
        if REAL_PROVIDER_BLOCK.search(content):
            findings.append(f"{path.relative_to(infra)}: declares a real aws provider")
    return findings
