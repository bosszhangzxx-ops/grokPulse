"""Provas de que o kit não toca a configuração pessoal das CLIs (checks C119, C120; AC 98, 99, door 7)."""

import hashlib
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from conftest import Kit, write_secret

from grokbot_kit import config

MODELS = {"claude": "sonnet", "opencode": "opencode/free", "codex": "gpt-test"}


def cli(kit: Kit, *args: str) -> subprocess.CompletedProcess[str]:
    result = kit.cli(*args)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


def snapshot(home: Path) -> dict[str, str]:
    files = [home / ".claude" / "settings.json", *sorted((home / ".codex").rglob("*"))]
    return {
        str(p.relative_to(home)): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir"
        for p in files
        if p.exists()
    }


def user_config(home: Path) -> None:
    (home / ".claude").mkdir()
    (home / ".claude" / "settings.json").write_text('{"permissions": {"allow": ["Bash(ls:*)"]}}\n', encoding="utf-8")
    codex = home / ".codex"
    codex.mkdir()
    (codex / "config.toml").write_text('model = "gpt-pessoal"\n\n[projects."/home/u/repo"]\ntrust_level = "trusted"\n')
    (codex / "hooks.json").write_text('{"hooks": {"PermissionRequest": []}}\n', encoding="utf-8")
    (codex / "auth.json").write_text('{"pessoal": true}\n', encoding="utf-8")


def add_models_and_route(kit: Kit) -> None:
    cfg = kit.config()
    for tool, model in MODELS.items():
        cfg["cli"][tool]["models"] = [model]
    cfg["routes"] = {"bot-a": {"sinks": ["arquivo"]}}
    cfg["sinks"] = {"arquivo": {"type": "file", "path": str(kit.sink)}}
    kit.write_config(config.dump(cfg))


def run_task(kit: Kit, tool: str) -> None:
    result = kit.run("--tool", tool, "--model", MODELS[tool], "--target", "bot-a", "--label", f"iso-{tool}", "--", "oi")
    assert result.returncode == 0, result.stderr


# C119 - AC 98
def test_user_claude_and_codex_untouched(fresh: Kit) -> None:
    user_config(fresh.home)
    before = snapshot(fresh.home)
    assert len(before) == 4

    for tool in MODELS:
        cli(fresh, "setup", "cli", "add", tool)
    cli(fresh, "setup", "default", "opencode")
    for tool in MODELS:
        cli(fresh, "login", tool)
    write_secret(fresh.home, "codex-api-key", "sk-codex\n")
    write_secret(fresh.home, "claude-api-key", "sk-ant\n")
    cli(fresh, "login", "codex", "--method", "api-key")
    cli(fresh, "login", "claude", "--method", "api-key")
    cli(fresh, "install", "opencode")
    add_models_and_route(fresh)
    for tool in MODELS:
        run_task(fresh, tool)
    cli(fresh, "doctor")
    cli(fresh, "gc", "--older-than", "30d")

    assert snapshot(fresh.home) == before
    assert len(fresh.tasks()) == 3
    assert {c["codex_home"] for c in fresh.calls() if c["tool"] == "codex"} == {
        str(fresh.home / ".grokbot-kit" / "codex-home")
    }


def trust_levels(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    found = []
    for path, project in value.get("projects", {}).items():
        if isinstance(project, dict) and "trust_level" in project:
            found.append(path)
    return found


# C120 - AC 99
def test_codex_home_never_trusts_projects(fresh: Kit) -> None:
    codex_home = fresh.home / ".grokbot-kit" / "codex-home"
    codex_home.mkdir(parents=True, mode=0o700)
    (codex_home / "config.toml").write_text('model_reasoning_effort = "medium"\n', encoding="utf-8")

    cli(fresh, "setup", "cli", "add", "codex")
    cli(fresh, "setup", "default", "codex")
    cli(fresh, "login", "codex")
    cfg = fresh.config()
    cfg["cli"]["codex"]["models"] = [MODELS["codex"]]
    cfg["routes"] = {"bot-a": {"sinks": ["arquivo"]}}
    cfg["sinks"] = {"arquivo": {"type": "file", "path": str(fresh.sink)}}
    fresh.write_config(config.dump(cfg))
    work = fresh.home / "repo"
    work.mkdir()
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    result = fresh.run(
        "--model", MODELS["codex"], "--target", "bot-a", "--label", "trust", "--cwd", str(work), "--", "oi"
    )
    assert result.returncode == 0, result.stderr
    assert fresh.launched()["env"]["CODEX_HOME"] == str(codex_home)

    text = (codex_home / "config.toml").read_text(encoding="utf-8")
    assert trust_levels(tomllib.loads(text)) == []
    for path in codex_home.rglob("*"):
        if path.is_file():
            assert "trust_level" not in path.read_text(encoding="utf-8", errors="replace"), path
