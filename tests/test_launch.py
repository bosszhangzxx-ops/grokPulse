"""Provas do lançamento do agente pelo `run` (checks C42-C45; AC 39-42, door 7)."""

import itertools
import json
import os
import shlex
import shutil
from pathlib import Path

import pytest
from conftest import MODELS, Kit

from grokbot_kit import launch


def has_pair(argv: list[str], flag: str, value: str) -> bool:
    return any(a == flag and b == value for a, b in itertools.pairwise(argv))


def kit_exe() -> str:
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    return exe


# C42 - AC 39
@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_child_stdin_is_devnull(kit: Kit, tool: str) -> None:
    result = kit.run("--tool", tool, "--target", "bot-a", "--label", "stdin", "--", "oi")
    assert result.returncode == 0, result.stderr
    launched = kit.launched()
    assert launched["stdin_target"] == "/dev/null"
    assert launched["stdin_read"] == ""


# C43 - AC 40
def test_claude_argv_and_settings(kit: Kit) -> None:
    result = kit.run("--tool", "claude", "--target", "bot-a", "--label", "cl", "--", "oi")
    assert result.returncode == 0, result.stderr
    task_dir = kit.task_dir()
    argv = kit.launched()["argv"]
    settings_path = task_dir / "claude-settings.json"
    assert "-p" in argv
    assert has_pair(argv, "--output-format", "json")
    assert has_pair(argv, "--model", MODELS["claude"])
    assert has_pair(argv, "--settings", str(settings_path))

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    commands = [h["command"] for group in settings["hooks"]["PermissionRequest"] for h in group["hooks"]]
    assert len(commands) == 1
    parts = shlex.split(commands[0])
    assert os.path.isabs(parts[0])
    assert Path(parts[0]).samefile(kit_exe())
    assert parts[1:] == ["emit", "--from", "claude"]


def test_claude_argv_and_settings_layer(tmp_path: Path) -> None:
    argv = launch.agent_argv("claude", "/bin/claude", "opus", tmp_path, "/opt/gk/grokbot-kit", ["x"])
    assert argv == [
        "/bin/claude",
        "-p",
        "--output-format",
        "json",
        "--model",
        "opus",
        "--settings",
        str(tmp_path / "claude-settings.json"),
        "x",
    ]
    settings = launch.claude_settings("/opt/gk/grokbot-kit")
    emit = {"type": "command", "command": "/opt/gk/grokbot-kit emit --from claude"}
    expected: dict = {
        "hooks": {
            "PermissionRequest": [{"matcher": "*", "hooks": [emit]}],
        }
    }
    for name in launch.PROGRESS_HOOK_EVENTS:
        handler = {"timeout": launch.SESSION_END_TIMEOUT, **emit} if name == "SessionEnd" else dict(emit)
        group: dict = {"hooks": [handler]}
        if name not in launch.NO_MATCHER_EVENTS:
            group["matcher"] = "*"
        expected["hooks"][name] = [group]
    assert settings == expected


# C44 - AC 41
def test_opencode_argv(kit: Kit) -> None:
    result = kit.run("--tool", "opencode", "--target", "bot-a", "--label", "oc", "--", "oi")
    assert result.returncode == 0, result.stderr
    argv = kit.launched()["argv"]
    assert argv[0] == "run"
    assert has_pair(argv, "--format", "json")
    assert has_pair(argv, "-m", MODELS["opencode"])
    assert argv[-1] == "oi"


def test_opencode_argv_layer(tmp_path: Path) -> None:
    argv = launch.agent_argv("opencode", "/bin/opencode", "opencode/m", tmp_path, "/opt/gk/grokbot-kit", ["oi"])
    assert argv == ["/bin/opencode", "run", "--format", "json", "-m", "opencode/m", "oi"]


# C45 - AC 42, door 7
@pytest.mark.parametrize("codex_home", [None, "/srv/outro-codex-home"])
def test_codex_argv_env_and_inline_hooks(kit: Kit, codex_home: str | None) -> None:
    if codex_home is not None:
        config = (kit.home / ".config" / "grokbot-kit" / "config.toml").read_text(encoding="utf-8")
        kit.write_config(config.replace('"~/.grokbot-kit/codex-home"', json.dumps(codex_home)))
    result = kit.run("--tool", "codex", "--target", "bot-a", "--label", "cx", "--", "oi")
    assert result.returncode == 0, result.stderr
    task_dir = kit.task_dir()
    launched = kit.launched()
    argv = launched["argv"]
    expected_home = codex_home or str(kit.home / ".grokbot-kit" / "codex-home")
    assert launched["env"]["CODEX_HOME"] == expected_home
    assert argv[0] == "exec"
    assert "--json" in argv
    assert has_pair(argv, "-m", MODELS["codex"])
    assert has_pair(argv, "-o", str(task_dir / "last-message.txt"))
    assert "--dangerously-bypass-hook-trust" in argv
    exe = str(Path(kit_exe()))
    hooks = f'hooks.PermissionRequest=[{{hooks=[{{type="command",command="{exe} emit --from codex"}}]}}]'
    assert has_pair(argv, "-c", hooks)


def test_codex_argv_env_and_inline_hooks_layer(tmp_path: Path) -> None:
    argv = launch.agent_argv("codex", "/bin/codex", "gpt-x", tmp_path, "/opt/gk/grokbot-kit", ["oi"])
    assert argv == [
        "/bin/codex",
        "exec",
        "--json",
        "-m",
        "gpt-x",
        "-o",
        str(tmp_path / "last-message.txt"),
        "--dangerously-bypass-hook-trust",
        "-c",
        'hooks.PermissionRequest=[{hooks=[{type="command",command="/opt/gk/grokbot-kit emit --from codex"}]}]',
        "oi",
    ]


SURFACE_COMMANDS = {
    "run",
    "emit",
    "reply",
    "redeliver",
    "gc",
    "setup",
    "login",
    "secret",
    "route",
    "doctor",
    "install",
    "uninstall",
    "update",
    "plugin",
}


# C125 - door 1
def test_env_contract_and_commands(kit: Kit) -> None:
    result = kit.run("--tool", "opencode", "--target", "bot-a", "--label", "contrato", "--", "oi")
    assert result.returncode == 0, result.stderr
    task_dir = kit.task_dir()
    env = kit.launched()["env"]
    assert {k: v for k, v in env.items() if k.startswith("GROKBOT_KIT_")} == {
        "GROKBOT_KIT_TASK_ID": task_dir.name,
        "GROKBOT_KIT_TARGET": "bot-a",
        "GROKBOT_KIT_LABEL": "contrato",
        "GROKBOT_KIT_TASK_DIR": str(task_dir),
    }

    help_text = kit.cli("--help")
    assert help_text.returncode == 0
    listed = help_text.stdout.split("{", 1)[1].split("}", 1)[0].split(",")
    assert set(listed) == SURFACE_COMMANDS
    assert len(listed) == 14


# os hooks TaskCreated/TaskCompleted precisam das Task tools; em modelos de gateway elas só vêm com o opt-in
def test_claude_env_enables_task_tools(kit: Kit) -> None:
    result = kit.run("--tool", "claude", "--target", "bot-a", "--label", "tt", "--", "oi")
    assert result.returncode == 0, result.stderr
    assert kit.launched()["env"]["CLAUDE_CODE_ENABLE_TODO_TOOLS"] == "1"
    result = kit.run("--tool", "claude", "--target", "bot-a", "--label", "tt", "--", "oi", CLAUDE_CODE_ENABLE_TODO_TOOLS="0")
    assert result.returncode == 0, result.stderr
    assert kit.launched()["env"]["CLAUDE_CODE_ENABLE_TODO_TOOLS"] == "0"  # o valor do usuário tem precedência
    result = kit.run("--tool", "opencode", "--target", "bot-a", "--label", "tt", "--", "oi")
    assert result.returncode == 0, result.stderr
    assert "CLAUDE_CODE_ENABLE_TODO_TOOLS" not in kit.launched()["env"]


# C1 - AC 1 da needs-input-reply
@pytest.mark.parametrize(("wait", "timeout"), [(600, 660), (30, 90), (0, None)])
def test_claude_settings_hook_timeout(kit: Kit, wait: int, timeout: int | None) -> None:
    flag = [] if wait == 600 else ["--ask-wait", f"{wait}s" if wait else "0"]
    result = kit.run("--tool", "claude", "--target", "bot-a", "--label", "cl", *flag, "--", "oi")
    assert result.returncode == 0, result.stderr
    settings = json.loads((kit.task_dir() / "claude-settings.json").read_text(encoding="utf-8"))
    [hook] = [h for group in settings["hooks"]["PermissionRequest"] for h in group["hooks"]]
    assert hook.get("timeout") == timeout
    assert ("timeout" in hook) is (timeout is not None)


def test_claude_settings_hook_timeout_layer() -> None:
    hook = launch.claude_settings("/opt/gk/grokbot-kit", 600)["hooks"]["PermissionRequest"][0]["hooks"][0]
    assert hook == {"type": "command", "command": "/opt/gk/grokbot-kit emit --from claude", "timeout": 660}
    assert (
        "timeout" not in launch.claude_settings("/opt/gk/grokbot-kit", 0)["hooks"]["PermissionRequest"][0]["hooks"][0]
    )


# C59 - door 9 da needs-input-reply
@pytest.mark.parametrize(("version", "standalone"), [("opencode v2.2.4", True), ("opencode v1.19.3", False)])
def test_opencode_standalone_by_major(kit: Kit, version: str, standalone: bool) -> None:
    result = kit.run("--tool", "opencode", "--target", "bot-a", "--label", "oc", "--", "oi", FAKE_VERSION=version)
    assert result.returncode == 0, result.stderr
    flag = ["--standalone"] if standalone else []
    assert kit.launched()["argv"] == ["run", "--format", "json", "-m", MODELS["opencode"], *flag, "oi"]
