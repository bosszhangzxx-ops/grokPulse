"""Provas do S0 sobre os arquivos do repositório (checks C3-C8, C11, C12, C16-C18, C21-C23, C39)."""

import json
import re
import subprocess
import tomllib
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def pyproject() -> dict[str, Any]:
    return tomllib.loads(read("pyproject.toml"))


def tracked(rel: str) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


# C3 - AC 2, door 9
def test_license_mit() -> None:
    text = read("LICENSE")
    assert text.startswith("MIT License")
    assert "Copyright (c) 2026 Rodrigo Pasini" in text.splitlines()
    assert "Permission is hereby granted, free of charge, to any person obtaining a copy" in text
    assert 'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND' in text
    assert pyproject()["project"]["license"] == "MIT"


# C4 - AC 2
def test_notice_credits_tlc_skills() -> None:
    text = read("NOTICE")
    assert "tech-leads-club/agent-skills" in text
    assert "CC-BY-4.0" in text
    assert ".claude/skills/" in text
    tlc = sorted(p.name for p in (ROOT / ".claude/skills").iterdir() if p.name.startswith("tlc-"))
    assert tlc, "nenhuma skill tlc-* em .claude/skills/"
    for name in tlc:
        assert name in text, f"NOTICE não credita {name}"


# C5 - AC 3
README_SECTIONS = [
    "What it is",
    "Install",
    "Quick start",
    "Grok Bot skill",
    "Configuration",
    "Security",
    "Contributing",
    "License",
]


@pytest.mark.parametrize("section", README_SECTIONS)
def test_readme_sections(section: str) -> None:
    headings = [line.lstrip("#").strip() for line in read("README.md").splitlines() if line.startswith("## ")]
    assert section in headings


def test_readme_sections_link_pt_br() -> None:
    assert "](docs/pt-BR/README.md)" in read("README.md")
    assert (ROOT / "docs/pt-BR/README.md").is_file()


# C6 - AC 4, door 6
def test_pyproject_fields() -> None:
    data = pyproject()
    project = data["project"]
    assert project["name"] == "grokbot-kit"
    assert project["requires-python"] == ">=3.11"
    assert project["dependencies"] == []
    assert project["scripts"] == {"grokbot-kit": "grokbot_kit.cli:main"}
    assert data["build-system"]["build-backend"] == "uv_build"
    assert any(req.startswith("uv_build") for req in data["build-system"]["requires"])
    assert (ROOT / "src/grokbot_kit/__init__.py").is_file()
    assert (ROOT / "src/grokbot_kit/cli.py").is_file()


# C7 - AC 5
def test_python_version_and_lock() -> None:
    assert read(".python-version").strip() == "3.11"
    assert tracked("uv.lock")
    assert tracked(".python-version")


# C8 - AC 6
def test_ruff_config() -> None:
    ruff = pyproject()["tool"]["ruff"]
    assert ruff["target-version"] == "py311"
    assert ruff["extend-exclude"] == [".claude", ".agents"]
    assert ruff["force-exclude"] is True


# C11 - AC 8 (sdlc-gates: `tools` entra no mypy, Impact do plano)
def test_mypy_strict_config() -> None:
    mypy = pyproject()["tool"]["mypy"]
    assert mypy["strict"] is True
    assert mypy["files"] == ["src", "tools"]


# C12 - AC 9
PRECOMMIT_EXCLUDE = r"^(\.claude|\.agents)/"


def precommit_hooks() -> list[dict[str, Any]]:
    config = yaml.safe_load(read(".pre-commit-config.yaml"))
    return [hook for repo in config["repos"] for hook in repo["hooks"]]


def test_precommit_hooks() -> None:
    hooks = precommit_hooks()
    by_id = {hook["id"]: hook for hook in hooks}
    ruff_check = by_id.get("ruff-check") or by_id.get("ruff")
    assert ruff_check is not None, "hook ruff check ausente"
    assert "--fix" in ruff_check.get("args", [])
    for hook_id in ["ruff-format", "check-toml", "check-yaml", "end-of-file-fixer", "trailing-whitespace"]:
        assert hook_id in by_id, f"hook {hook_id} ausente"
    mypy = [hook for hook in hooks if hook.get("language") == "system" and hook.get("entry") == "uv run mypy"]
    assert len(mypy) == 1, "hook local `uv run mypy` ausente"
    for hook in hooks:
        assert hook.get("exclude") == PRECOMMIT_EXCLUDE, f"hook {hook['id']} sem exclude"


# sdlc-gates C2 - AC 1, door 1
def test_sdlc_hooks_stages() -> None:
    by_id = {hook["id"]: hook for hook in precommit_hooks()}
    for hook_id, stage, command in [
        ("sdlc-pre-commit", "pre-commit", "tools/sdlc.py pre-commit"),
        ("sdlc-commit-msg", "commit-msg", "tools/sdlc.py commit-msg"),
        ("sdlc-pre-push", "pre-push", "tools/sdlc.py branch"),
    ]:
        assert hook_id in by_id, f"hook {hook_id} ausente"
        hook = by_id[hook_id]
        assert hook["stages"] == [stage], hook_id
        assert command in hook["entry"], hook_id
        assert hook.get("exclude") == PRECOMMIT_EXCLUDE, hook_id


# C16 - AC 13
IGNORED = [
    ".venv/",
    "__pycache__/",
    "dist/",
    "build/",
    "pkg.egg-info/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".pytest_cache/",
    ".coverage",
    ".env",
]


def check_ignore(path: str) -> bool:
    result = subprocess.run(["git", "check-ignore", "--no-index", "-q", path], cwd=ROOT, check=False)
    assert result.returncode in (0, 1), f"git check-ignore falhou em {path}"
    return result.returncode == 0


@pytest.mark.parametrize("path", IGNORED)
def test_gitignore_entries(path: str) -> None:
    assert check_ignore(path)


@pytest.mark.parametrize("path", [".claude/settings.json", ".claude/skills/x/SKILL.md", ".agents/.skill-lock.json"])
def test_gitignore_entries_keep_agent_tooling(path: str) -> None:
    assert not check_ignore(path)


# C17 - AC 14
def test_contributing_and_changelog() -> None:
    text = read("CONTRIBUTING.md")
    for needle in [
        "uv sync",
        "pre-commit install",
        "uv run ruff check",
        "uv run ruff format --check",
        "uv run mypy",
        "uv run pytest",
        "pull request",
        ".claude/hooks/gate-worktree.sh",
        "GROKBOT_KIT_ALLOW_MAIN_EDIT=1",
    ]:
        assert needle in text, f"CONTRIBUTING.md não documenta {needle!r}"
    changelog = read("CHANGELOG.md")
    assert "https://keepachangelog.com/" in changelog
    assert "## [Unreleased]" in changelog.splitlines()


# C18 - AC 15
def test_issue_and_pr_templates() -> None:
    assert (ROOT / ".github/ISSUE_TEMPLATE/feature_request.yml").is_file()
    assert (ROOT / ".github/pull_request_template.md").is_file()
    yaml.safe_load(read(".github/ISSUE_TEMPLATE/feature_request.yml"))
    bug = yaml.safe_load(read(".github/ISSUE_TEMPLATE/bug_report.yml"))
    ids = {item.get("id") for item in bug["body"]}
    assert "grokbot-kit-version" in ids
    assert "cli-version" in ids
    required = {item["id"]: item.get("validations", {}).get("required") for item in bug["body"] if "id" in item}
    assert required["grokbot-kit-version"] is True
    assert required["cli-version"] is True
    texts = " ".join(json.dumps(item) for item in bug["body"]).lower()
    assert "do not paste" in texts and "secret" in texts


# C21 - AC 18, door 11
MAIN_PROTECTION = {
    "required_status_checks": {
        "strict": True,
        "checks": [
            {"context": "lint", "app_id": 15368},
            {"context": "typecheck", "app_id": 15368},
            {"context": "test (3.11)", "app_id": 15368},
            {"context": "test (3.12)", "app_id": 15368},
            {"context": "test (3.13)", "app_id": 15368},
            # sdlc-gates C24 (door 4): o 6º check obrigatório
            {"context": "process", "app_id": 15368},
        ],
    },
    "enforce_admins": True,
    "required_pull_request_reviews": {
        "dismiss_stale_reviews": True,
        "require_code_owner_reviews": False,
        "required_approving_review_count": 0,
        "require_last_push_approval": False,
    },
    "restrictions": None,
    "required_linear_history": True,
    "allow_force_pushes": False,
    "allow_deletions": False,
    "required_conversation_resolution": True,
    "lock_branch": False,
    "allow_fork_syncing": False,
}

PYPI_ENVIRONMENT = {
    "wait_timer": 0,
    "prevent_self_review": False,
    "reviewers": [{"type": "User", "id": 17571964}],
    "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
}


def test_repo_settings_payloads_match_door_11() -> None:
    assert json.loads(read(".github/repo-settings/main-protection.json")) == MAIN_PROTECTION
    assert json.loads(read(".github/repo-settings/pypi-environment.json")) == PYPI_ENVIRONMENT


# C22 - AC 19
ASSETS = ["grokbot_kit/assets/opencode/grokbot-kit.ts", "grokbot_kit/assets/event.v1.json"]


def test_assets_in_wheel(tmp_path: Path) -> None:
    assert (ROOT / "skills/grokbot-kit/SKILL.md").is_file()
    for asset in ASSETS:
        assert (ROOT / "src" / asset).is_file()
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(tmp_path)], cwd=ROOT, check=True, capture_output=True)
    wheels = list(tmp_path.glob("grokbot_kit-*.whl"))
    assert len(wheels) == 1
    names = zipfile.ZipFile(wheels[0]).namelist()
    for asset in ASSETS:
        assert asset in names, f"{asset} fora do wheel"


# C23 - door 10 (sdlc-gates C46, AD-052: `AGENTS.md` no lugar do `CLAUDE.md`)
DOOR_10_FILES = [
    "LICENSE",
    "README.md",
    "docs/pt-BR/README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".gitignore",
    ".pre-commit-config.yaml",
    "src/grokbot_kit/cli.py",
    "src/grokbot_kit/emit.py",
    "skills/grokbot-kit/SKILL.md",
    "docs/.specs/STATE.md",
    "docs/.specs/DECISOES.md",
    "docs/.specs/features/agent-run-notify/plan.md",
    "NOTICE",
    "AGENTS.md",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    ".github/dependabot.yml",
    ".github/pull_request_template.md",
]

DOOR_10_DIRS = ["src/grokbot_kit/assets", "tests", ".claude", ".agents", ".github/ISSUE_TEMPLATE"]


@pytest.mark.parametrize("rel", DOOR_10_FILES)
def test_door_10_tree_files(rel: str) -> None:
    assert tracked(rel), f"{rel} não versionado"


@pytest.mark.parametrize("rel", DOOR_10_DIRS)
def test_door_10_tree_dirs(rel: str) -> None:
    files = subprocess.run(["git", "ls-files", "--", rel], cwd=ROOT, capture_output=True, text=True, check=True)
    assert files.stdout.strip(), f"nenhum arquivo versionado em {rel}/"


# C39 - AC 36
def test_contributing_pypi_pending_publisher() -> None:
    text = read("CONTRIBUTING.md")
    assert "https://pypi.org/manage/account/publishing/" in text
    assert "pending publisher" in text.lower()
    for field, value in [
        ("PyPI Project Name", "grokbot-kit"),
        ("Owner", "rodrigo-pasini"),
        ("Repository name", "grokbot-kit"),
        ("Workflow name", "release.yml"),
        ("Environment name", "pypi"),
    ]:
        assert f"{field}: `{value}`" in text, f"pending publisher sem {field}: {value}"


# C41 - AC 38
S0_REPORT = "docs/.specs/features/agent-run-notify/s0-report.md"
SECRET_PATTERN = (
    r"crsr_[0-9a-f]{8}|gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}"
    r"|sk-ant-[A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|pypi-AgEI[A-Za-z0-9_-]{20,}"
)
S0_REPORT_OUTPUTS = {
    "AC 29": [
        '"checks":["lint","typecheck","test (3.11)","test (3.12)","test (3.13)"]',
        '"strict":true',
        '"approvals":0',
        '"admins":true',
        '"force":false',
        '"deletions":false',
        '"linear":true',
    ],
    "AC 30": ["vulnerability-alerts: exit 0 (HTTP 204)", "automated-security-fixes .enabled: true"],
    "AC 31": [
        '{"name":"pypi","rules":["required_reviewers","branch_policy"]}',
        '[{"name":"v*","type":"tag"}]',
    ],
    "AC 33": [
        '"visibility":"PUBLIC"',
        '"hasIssuesEnabled":true',
        '"hasWikiEnabled":false',
        '"hasProjectsEnabled":false',
        '"hasDiscussionsEnabled":false',
        '"squashMergeAllowed":true',
        '"mergeCommitAllowed":false',
        '"rebaseMergeAllowed":false',
        '"deleteBranchOnMerge":true',
        '"licenseInfo":{"key":"mit"',
        '"defaultBranchRef":{"name":"main"}',
        *[
            f'{{"name":"{topic}"}}'
            for topic in ["grokbot", "ai-agents", "coding-agents", "cli", "python", "webhooks"]
            + ["opencode", "claude-code", "codex", "automation"]
        ],
        '"allow_auto_merge":true',
        '"allow_update_branch":true',
        '"push_protection":"enabled"',
        '"secret_scanning":"enabled"',
        *[
            f"\n{label}\n"
            for label in ["area:cli", "area:hooks", "area:skill", "area:webhook"]
            + ["cli:opencode", "cli:claude", "cli:codex", "security", "needs-triage"]
        ],
    ],
}


def report_sections(text: str) -> dict[str, str]:
    parts = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    return {part.split("\n", 1)[0].strip(): part for part in parts}


def test_s0_report_has_outputs_and_no_token() -> None:
    text = read(S0_REPORT)
    sections = report_sections(text)
    for ac, needles in S0_REPORT_OUTPUTS.items():
        assert ac in sections, f"relatório sem a seção {ac}"
        for needle in needles:
            assert needle in sections[ac], f"{ac}: saída sem {needle!r}"
    assert re.search(SECRET_PATTERN, text) is None
    assert "Bearer " not in text


# model-setup-docs C43 - AC 41 (emendado na release: a seção é a da 0.5.0)
def test_changelog_unreleased_model_setup() -> None:
    text = read("CHANGELOG.md")
    start = text.index("## [0.5.0]")
    end = text.index("\n## [", start + 1)
    release = text[start:end]
    for needle in ("setup providers", "--json", "model_fallbacks", "summary"):
        assert needle in release, needle


# sdlc-gates C31, C40 - AC 24, 31
def test_worktree_handoff_config() -> None:
    config = json.loads(read(".claude/worktree-handoff.json"))
    assert config["branch_pattern"] == "<tipo>/<issue>/<slug>"
    assert config["handoff_skill"] == "tlc-spec-lean"
    assert "CLAUDE.local.md" not in config["copy"]


def handoff_section() -> str:
    lines = read("docs/.specs/STATE.md").splitlines()
    start = lines.index("## Handoff")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


# sdlc-gates C33 - AC 25 (issues 32: limites do webhook; 33: sandbox do Codex no box)
def test_state_handoff_cites_issues() -> None:
    handoff = handoff_section()
    for issue in ("#32", "#33"):
        assert re.search(rf"{issue}(?!\d)", handoff), issue
    assert "bwrap" not in handoff
    assert "limites do webhook" not in handoff


# sdlc-gates C38 - AC 29
def test_state_handoff_within_limit() -> None:
    result = subprocess.run(
        ["python3", "tools/sdlc.py", "state"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


# sdlc-gates C39 - AC 30, door 8
def test_no_claude_md_tracked() -> None:
    files = subprocess.run(
        ["git", "ls-files", "CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert files.stdout == ""
