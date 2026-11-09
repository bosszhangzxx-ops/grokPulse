"""Provas do harness por CLI (checks C36 e C39; AC 34-38 e 40, door 8).

C39: sem `--plugin`, o argv e o `claude-settings.json` são os de antes desta feature, literais. C36: o harness de cada
CLI a partir das capacidades, literal, como na linha da door 8 (o Codex não tem harness: a matriz o tira dos plugins).
"""

import json
from pathlib import Path

import pytest

from grokbot_kit import launch

EXE = "/opt/gk/grokbot-kit"


# C39 - AC 40
def test_argv_without_plugin_matches_baseline(tmp_path: Path) -> None:
    assert launch.agent_argv("claude", "/bin/claude", "sonnet", tmp_path, EXE, ["oi"]) == [
        "/bin/claude",
        "-p",
        "--output-format",
        "json",
        "--model",
        "sonnet",
        "--settings",
        str(tmp_path / "claude-settings.json"),
        "oi",
    ]
    assert launch.agent_argv("opencode", "/bin/opencode", "opencode/m", tmp_path, EXE, ["oi"]) == [
        "/bin/opencode",
        "run",
        "--format",
        "json",
        "-m",
        "opencode/m",
        "oi",
    ]
    assert launch.agent_argv("codex", "/bin/codex", "gpt-x", tmp_path, EXE, ["oi"]) == [
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
    # baseline inalterado exceto pelos 9 hooks de progresso agora inerentes ao kit (nada do plugin vaza)
    emit = {"type": "command", "command": f"{EXE} emit --from claude"}
    expected: dict = {"hooks": {"PermissionRequest": [{"matcher": "*", "hooks": [emit]}]}}
    for name in launch.PROGRESS_HOOK_EVENTS:
        handler = {"timeout": launch.SESSION_END_TIMEOUT, **emit} if name == "SessionEnd" else dict(emit)
        group: dict = {"hooks": [handler]}
        if name not in launch.NO_MATCHER_EVENTS:
            group["matcher"] = "*"
        expected["hooks"][name] = [group]
    assert launch.claude_settings(EXE) == expected


CAPS = {"write": "task-dir", "network": "off", "commands": ["git", "gh pr view"]}


# C36 - AC 34-38, door 8
def test_harness_per_cli_and_capability_claude(tmp_path: Path) -> None:
    h = launch.plugin_harness("claude", CAPS, tmp_path, tmp_path / "plugin", None)
    assert h.args == [
        "--restricted",
        "--strict-mcp-config",
        "--tools",
        "Read,Glob,Grep,Edit,Write,Skill,Bash",
        "--add-dir",
        str(tmp_path),
        "--plugin-dir",
        str(tmp_path / "plugin"),
        "--permission-mode",
        "dontAsk",
    ]
    assert h.permissions == {
        "allow": [
            f"Edit(/{tmp_path}/**)",
            f"Write(/{tmp_path}/**)",
            "Bash(git)",
            "Bash(git *)",
            "Bash(gh pr view)",
            "Bash(gh pr view *)",
        ],
        "deny": [
            f"Edit(/{tmp_path}/plugin/**)",
            f"Write(/{tmp_path}/plugin/**)",
            "WebFetch",
            "WebSearch",
            "Bash(*--output*)",
        ],
    }
    assert h.env == {}

    none = launch.plugin_harness("claude", {**CAPS, "write": "none", "commands": []}, tmp_path, tmp_path, None)
    assert "Read,Glob,Grep,Edit,Write,Skill" in none.args
    assert none.permissions["allow"] == [f"Edit(/{tmp_path}/result.json)", f"Write(/{tmp_path}/result.json)"]
    assert "Bash(*--output*)" not in none.permissions["deny"]


# C36 - AC 34-38, AC 68, AC 70, doors 8, 10 e 11
@pytest.mark.parametrize(("major", "args"), [(2, ["--standalone"]), (1, []), (None, [])])
def test_harness_per_cli_and_capability_opencode(tmp_path: Path, major: int | None, args: list[str]) -> None:
    h = launch.plugin_harness("opencode", CAPS, tmp_path, tmp_path / "plugin", major)
    assert h.args == args
    assert h.permissions == {}
    assert {k: v for k, v in h.env.items() if k != "OPENCODE_CONFIG_CONTENT"} == {
        "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
        "OPENCODE_DISABLE_CLAUDE_CODE_SKILLS": "1",
    }
    assert json.loads(h.env["OPENCODE_CONFIG_CONTENT"]) == {
        "permission": {
            "edit": {"*": "allow", f"{tmp_path}/plugin/*": "deny"},
            "external_directory": {"*": "deny", f"{tmp_path}/*": "allow"},
            "bash": {
                "*": "deny",
                "git": "allow",
                "git *": "allow",
                "gh pr view": "allow",
                "gh pr view *": "allow",
                "*>*": "deny",
                "*--output*": "deny",
            },
            "skill": "allow",
            "webfetch": "deny",
            "websearch": "deny",
        },
        "skills": {"paths": [str(tmp_path / "plugin" / "skills")]},
    }
    # no opencode vale a última regra que casa: as negações do `>` e do `--output` vêm depois dos prefixos (doors 10 e 11)
    bash = json.loads(h.env["OPENCODE_CONFIG_CONTENT"])["permission"]["bash"]
    assert list(bash.items())[-2:] == [("*>*", "deny"), ("*--output*", "deny")]
    on = launch.plugin_harness("opencode", {**CAPS, "write": "none", "network": "on"}, tmp_path, tmp_path, major)
    permission = json.loads(on.env["OPENCODE_CONFIG_CONTENT"])["permission"]
    assert permission["edit"] == {"*": "deny", str(tmp_path / "result.json"): "allow"}
    assert "webfetch" not in permission


# C36 - door 8: o Codex não confina a escrita neste host (sandbox `bwrap`), então não tem harness
def test_harness_per_cli_and_capability_codex(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="codex has no plugin harness"):
        launch.plugin_harness("codex", CAPS, tmp_path, tmp_path, None)
