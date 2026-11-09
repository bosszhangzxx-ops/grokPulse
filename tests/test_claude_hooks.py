"""Provas da config e dos hooks do Claude Code do repositório (sdlc-gates: C26, C27, C29, C41-C43; AC 9, 20, 22, 23, 32).

Cada hook é alimentado com o JSON do evento em stdin, como o Claude Code faz.
"""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
SESSION = ROOT / ".claude" / "hooks" / "session-start.sh"
CLAUDE_MD_WARNING = "CLAUDE.md or CLAUDE.local.md found: AGENTS.md is not loaded; move its content to AGENTS.md"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def repo_on(tmp_path: Path, branch: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", branch)
    return repo


ASK = [
    "Bash(gh pr merge *)",
    "Bash(gh release *)",
    "Bash(git push --tags *)",
    "Bash(git push * --tags *)",
    "Bash(git push * --follow-tags *)",
    "Bash(git push --follow-tags *)",
    "Bash(git push * v*)",
    "Bash(git push * refs/tags/*)",
    "Bash(git push *:refs/tags/*)",
    "Bash(git push *:v*)",
    "Bash(git push *--mirror*)",
    "Bash(git push *+v*)",
    "Bash(git push *+refs/tags/*)",
    "Bash(gh api *protection*)",
    "Bash(gh api *environments*)",
    "Bash(gh api *merge*)",
    "Bash(gh api *releases*)",
]
ALLOW = ["Bash(git push *)", "Bash(gh pr create *)"]


def settings() -> dict[str, Any]:
    return json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))


def matches(rule: str, command: str) -> bool:
    """Casa uma regra `Bash(<padrão>)` como o Claude Code: `*` é qualquer texto, e ` *` no fim aceita o comando sem
    argumento."""
    pattern = rule.removeprefix("Bash(").removesuffix(")")
    regex = re.escape(pattern).replace(r"\*", ".*")
    if pattern.endswith(" *"):
        regex = regex[: -len(r"\ .*")] + r"(\ .*)?"
    return re.fullmatch(regex, command) is not None


# C26 - AC 23, door 6
def test_settings_registers_hooks() -> None:
    hooks = settings()["hooks"]

    def commands(event: str, matcher: str | None) -> list[str]:
        return [
            h["command"]
            for entry in hooks.get(event, [])
            if entry.get("matcher") == matcher
            for h in entry["hooks"]
            if h["type"] == "command"
        ]

    assert not commands("PreToolUse", "Bash")
    assert any("gate-worktree.sh" in c for c in commands("PreToolUse", "Edit|Write|MultiEdit|NotebookEdit"))
    session = [h["command"] for entry in hooks.get("SessionStart", []) for h in entry["hooks"]]
    assert any("session-start.sh" in c for c in session)
    assert not (ROOT / ".claude" / "hooks" / "gate-humano.sh").exists()


# C27 - AC 20, door 6
def test_settings_permissions_ask() -> None:
    assert settings()["permissions"]["ask"] == ASK
    for command in ("git tag", "git tag -l 'v0.0.0*'", "git tag --list"):
        assert not any(matches(rule, command) for rule in ASK), command


@pytest.mark.parametrize(
    "command",
    [
        "gh pr merge 34 --squash",
        "gh release create v0.6.0",
        "git push --tags",
        "git push origin --tags",
        "git push origin v0.6.0",
        "git push origin refs/tags/v0.6.0",
        "git push origin HEAD:refs/tags/v9.9.9",
        "git push origin :refs/tags/v0.6.0",
        "git push origin :v0.6.0",
        "git push --mirror origin",
        "git push --follow-tags",
        "git push --follow-tags origin",
        "git push origin --follow-tags",
        "git push origin +v0.6.0",
        "git push origin +refs/tags/v0.6.0",
        "gh api -X PUT repos/o/r/branches/main/protection",
        "gh api repos/o/r/environments/pypi",
        "gh api -X PUT repos/o/r/pulls/34/merge",
        "gh api graphql -f query=mutation{mergePullRequest}",
        "gh api repos/o/r/releases",
    ],
)
def test_settings_permissions_ask_covers(command: str) -> None:
    assert any(matches(rule, command) for rule in ASK), command


# C29 - AC 22, door 6
def test_settings_permissions_allow() -> None:
    allow = settings()["permissions"]["allow"]
    assert allow == ALLOW
    for command in ("gh pr merge 34", "git tag v1", "gh release create v1"):
        assert not any(matches(rule, command) for rule in allow), command
    assert matches("Bash(git push *)", "git push -u origin feat/31/x")
    assert not any(matches(rule, "git push -u origin feat/31/x") for rule in ASK)


# ---------------------------------------------------------------------------- SessionStart


def stub_uv(tmp_path: Path, exit_code: int) -> tuple[Path, Path]:
    """Um `uv` falso no PATH que registra a chamada em `calls`."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls"
    uv = bin_dir / "uv"
    uv.write_text(f'#!/bin/sh\necho "$PWD $*" >> "{calls}"\nexit {exit_code}\n', encoding="utf-8")
    uv.chmod(0o755)
    return bin_dir, calls


def session(repo: Path, bin_dir: Path) -> tuple[subprocess.CompletedProcess[str], str]:
    payload = {"hook_event_name": "SessionStart", "source": "startup", "cwd": str(repo)}
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "CLAUDE_PROJECT_DIR": str(repo)}
    result = subprocess.run(
        ["bash", str(SESSION)],
        input=json.dumps(payload),
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    context = ""
    if result.stdout.strip():
        out: dict[str, Any] = json.loads(result.stdout)["hookSpecificOutput"]
        assert out["hookEventName"] == "SessionStart"
        context = out["additionalContext"]
    return result, context


# C41 - AC 9
def test_session_start_installs_hooks(tmp_path: Path) -> None:
    repo = repo_on(tmp_path, "feat/31/x")
    bin_dir, calls = stub_uv(tmp_path, 0)
    result, context = session(repo, bin_dir)
    assert result.returncode == 0, result.stderr
    assert calls.read_text(encoding="utf-8").split() == [str(repo), "run", "pre-commit", "install"]
    assert context.strip() and "install" in context

    calls.unlink()
    (repo / ".git" / "hooks" / "commit-msg").write_text("#!/bin/sh\n", encoding="utf-8")
    again, _ = session(repo, bin_dir)
    assert again.returncode == 0
    assert not calls.exists(), "reinstalou com o hook já presente"


# C42 - AC 32
@pytest.mark.parametrize("name", ["CLAUDE.md", "CLAUDE.local.md"])
def test_session_start_warns_claude_md(tmp_path: Path, name: str) -> None:
    repo = repo_on(tmp_path, "feat/31/x")
    (repo / ".git" / "hooks" / "commit-msg").write_text("#!/bin/sh\n", encoding="utf-8")
    bin_dir, _ = stub_uv(tmp_path, 0)
    _, clean = session(repo, bin_dir)
    assert CLAUDE_MD_WARNING not in clean
    (repo / name).write_text("# x\n", encoding="utf-8")
    result, context = session(repo, bin_dir)
    assert result.returncode == 0
    assert CLAUDE_MD_WARNING in context.splitlines()


# C43 - AC 9
def test_session_start_install_failure(tmp_path: Path) -> None:
    repo = repo_on(tmp_path, "feat/31/x")
    bin_dir, calls = stub_uv(tmp_path, 1)
    result, context = session(repo, bin_dir)
    assert result.returncode == 0
    assert calls.exists()
    assert "fail" in context.lower()
