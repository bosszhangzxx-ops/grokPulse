"""Provas do `grokbot-kit emit` (checks C63-C66, C70-C75; AC 54-63, doors 5, 6 e 14).

A normalização de cada fonte é provada na própria camada (`emit.normalize`) e na fronteira: a CLI falsa, lançada
por `grokbot-kit run`, chama `grokbot-kit emit --from <tool>` com o JSON do hook, e o evento chega ao sink `file`.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import Kit, default_config

from grokbot_kit import emit

CLAUDE_OK = json.dumps({"type": "result", "is_error": False, "result": "feito", "permission_denials": []})
STDOUT_OK = {"claude": CLAUDE_OK, "opencode": "", "codex": ""}


def claude_hook(**extra: Any) -> dict[str, Any]:
    return {
        "session_id": "6ae1774a",
        "transcript_path": "/home/u/.claude/projects/p/6ae1774a.jsonl",
        "cwd": "/w",
        "permission_mode": "default",
        "hook_event_name": "PermissionRequest",
        "tool_name": "Bash",
        "tool_input": {"command": "touch criado.txt", "description": "cria o arquivo"},
        **extra,
    }


def codex_hook(**extra: Any) -> dict[str, Any]:
    return {
        "session_id": "019a-thread",
        "turn_id": "turn-1",
        "transcript_path": "/srv/codex-home/sessions/rollout.jsonl",
        "cwd": "/w",
        "hook_event_name": "PermissionRequest",
        "model": "gpt-test",
        "permission_mode": "default",
        "tool_name": "Bash",
        "tool_input": {"command": "touch criado.txt"},
        **extra,
    }


def opencode_permission(parent_id: str | None = None, request_id: str = "per_1") -> dict[str, Any]:
    return {
        "type": "permission.asked",
        "properties": {
            "id": request_id,
            "sessionID": "ses_1",
            "permission": "bash",
            "patterns": ["touch criado.txt"],
            "metadata": {},
            "tool": {"messageID": "msg_1", "callID": "call_1"},
        },
        "parentID": parent_id,
    }


def opencode_question(request_id: str = "que_1") -> dict[str, Any]:
    return {
        "type": "question.asked",
        "properties": {
            "id": request_id,
            "sessionID": "ses_1",
            "questions": [{"header": "Arquivo", "question": "Qual nome usar?", "options": []}],
        },
        "parentID": None,
    }


def run_with_emits(kit: Kit, tool: str, payloads: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Roda uma task cuja CLI falsa chama o `emit` com cada payload; devolve os `needs_input` e o terminal do sink."""
    result = kit.run(
        "--tool",
        tool,
        "--target",
        "bot-a",
        "--label",
        "e",
        # o aviso sem espera (needs-input-reply, AC 6), o comportamento que estas provas cobram
        "--ask-wait",
        "0",
        "--",
        "faça",
        FAKE_STDOUT=STDOUT_OK[tool],
        FAKE_EMIT=json.dumps(payloads),
    )
    assert result.returncode == 0, result.stderr
    events = kit.sink_events()
    asked = [e for e in events if e["event"] == "needs_input"]
    terminal = [e for e in events if e["event"] != "needs_input"]
    assert len(terminal) == 1, events
    return asked, terminal[0]


def finished_task(kit: Kit, tool: str = "claude") -> tuple[Path, dict[str, str]]:
    """Uma task já lançada por `run` (task dir e `meta.json` reais) e o env que o agente dela recebeu."""
    result = kit.run("--tool", tool, "--target", "bot-a", "--label", "e", "--", "faça", FAKE_STDOUT=STDOUT_OK[tool])
    assert result.returncode == 0, result.stderr
    task_dir = kit.task_dir()
    env = {
        **kit.env,
        "GROKBOT_KIT_TASK_ID": task_dir.name,
        "GROKBOT_KIT_TARGET": "bot-a",
        "GROKBOT_KIT_LABEL": "e",
        "GROKBOT_KIT_TASK_DIR": str(task_dir),
    }
    return task_dir, env


def kit_exe() -> str:
    exe = shutil.which("grokbot-kit")
    assert exe is not None, "console script grokbot-kit não instalado"
    return exe


def emit_process(env: dict[str, str], tool: str, stdin: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [kit_exe(), "emit", "--from", tool],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        check=False,
        timeout=30,
    )


# C63 - AC 54
def test_claude_permission_request_layer() -> None:
    asked = emit.normalize("claude", claude_hook())
    assert asked is not None
    assert asked["kind"] == "permission"
    assert asked["tool_name"] == "Bash"
    assert asked["session_id"] == "6ae1774a"
    assert asked["transcript_path"] == "/home/u/.claude/projects/p/6ae1774a.jsonl"


def test_claude_permission_request_other_hook_is_ignored_layer() -> None:
    assert emit.normalize("claude", claude_hook(hook_event_name="PreToolUse")) is None


def test_claude_permission_request_cli(kit: Kit) -> None:
    asked, terminal = run_with_emits(kit, "claude", [claude_hook(tool_name="Write")])
    assert len(asked) == 1
    event = asked[0]
    assert (event["event"], event["status"], event["exit_reason"]) == ("needs_input", "permission", "needs_input")
    assert event["needs_input"]["kind"] == "permission"
    assert event["needs_input"]["tool_name"] == "Write"
    assert event["task_id"] == kit.task_dir().name
    assert event["target"] == "bot-a"
    assert event["session_id"] == "6ae1774a"
    assert event["transcript_path"] == "/home/u/.claude/projects/p/6ae1774a.jsonl"
    assert (terminal["event"], terminal["status"]) == ("completed", "denied")


# C64 - AC 55
def test_opencode_permission_asked_root_session_only_layer() -> None:
    asked = emit.normalize("opencode", opencode_permission())
    assert asked is not None
    assert asked["kind"] == "permission"
    assert asked["tool_name"] == "bash"
    assert asked["session_id"] == "ses_1"
    assert emit.normalize("opencode", opencode_permission(parent_id="ses_pai")) is None


def test_opencode_permission_asked_root_session_only_cli(kit: Kit) -> None:
    asked, terminal = run_with_emits(kit, "opencode", [opencode_permission()])
    assert [(e["event"], e["status"]) for e in asked] == [("needs_input", "permission")]
    assert asked[0]["needs_input"]["kind"] == "permission"
    assert (terminal["event"], terminal["status"]) == ("completed", "denied")


def test_opencode_permission_asked_root_session_only_child_cli(kit: Kit) -> None:
    asked, terminal = run_with_emits(kit, "opencode", [opencode_permission(parent_id="ses_pai")])
    assert asked == []
    assert (terminal["event"], terminal["status"]) == ("completed", "ok")


# C65 - AC 56
def test_opencode_question_asked_layer() -> None:
    asked = emit.normalize("opencode", opencode_question())
    assert asked is not None
    assert asked["kind"] == "question"
    assert asked["detail"] == "Qual nome usar?"


def test_opencode_question_asked_cli(kit: Kit) -> None:
    asked, _ = run_with_emits(kit, "opencode", [opencode_question()])
    assert [(e["event"], e["status"], e["exit_reason"]) for e in asked] == [("needs_input", "question", "needs_input")]
    assert asked[0]["needs_input"]["kind"] == "question"


# C66 - AC 57
def test_codex_permission_request_layer() -> None:
    asked = emit.normalize("codex", codex_hook(tool_name="apply_patch"))
    assert asked is not None
    assert asked["kind"] == "permission"
    assert asked["tool_name"] == "apply_patch"
    assert asked["session_id"] == "019a-thread"
    assert emit.normalize("codex", codex_hook(hook_event_name="PostToolUse")) is None


def test_codex_permission_request_cli(kit: Kit) -> None:
    asked, terminal = run_with_emits(kit, "codex", [codex_hook()])
    assert len(asked) == 1
    event = asked[0]
    assert (event["event"], event["status"]) == ("needs_input", "permission")
    assert event["needs_input"]["tool_name"] == "Bash"
    assert event["transcript_path"] == "/srv/codex-home/sessions/rollout.jsonl"
    assert (terminal["event"], terminal["status"]) == ("completed", "denied")


# C70 - AC 58
def test_dedupe_same_id_once_distinct_twice_layer() -> None:
    def key(source: str, data: dict[str, Any]) -> str:
        asked = emit.normalize(source, data)
        assert asked is not None
        return str(asked["discriminator"])

    assert key("claude", claude_hook(tool_use_id="toolu_1")) == "toolu_1"
    assert key("opencode", opencode_permission(request_id="per_9")) == "per_9"
    # sem `tool_use_id` no hook: o mesmo pedido dá a mesma chave, outro pedido dá outra
    assert key("codex", codex_hook()) == key("codex", codex_hook(turn_id="turn-2"))
    assert key("codex", codex_hook()) != key("codex", codex_hook(tool_input={"command": "rm x"}))
    assert key("claude", claude_hook()) != key("claude", claude_hook(tool_name="Write"))
    # um id que não cabe num nome de arquivo vira hash, sem `/`
    assert "/" not in key("claude", claude_hook(tool_use_id="../../etc"))


def test_dedupe_same_id_once_distinct_twice_cli(kit: Kit) -> None:
    same = [claude_hook(tool_use_id="toolu_1")] * 3
    asked, _ = run_with_emits(kit, "claude", same)
    assert len(asked) == 1


def test_dedupe_same_id_once_distinct_twice_distinct_cli(kit: Kit) -> None:
    distinct = [claude_hook(tool_use_id="toolu_1"), claude_hook(tool_use_id="toolu_2")]
    asked, _ = run_with_emits(kit, "claude", distinct)
    assert len(asked) == 2


def test_dedupe_same_id_once_distinct_twice_opencode_cli(kit: Kit) -> None:
    payloads = [opencode_permission(request_id="per_1")] * 3 + [opencode_permission(request_id="per_2")]
    asked, _ = run_with_emits(kit, "opencode", payloads)
    assert len(asked) == 2


AUDIT = """
import json, sys
opened, connected = [], []
def hook(event, args):
    if event == "open" and isinstance(args[0], (str, bytes)):
        opened.append(str(args[0]))
    elif event in ("socket.connect", "urllib.Request"):
        connected.append(event)
sys.addaudithook(hook)
from grokbot_kit.cli import main
code = main(["emit", "--from", sys.argv[1]])
sys.stdout.flush()
with open(sys.argv[2], "w") as f:
    json.dump({"code": code, "opened": opened, "connected": connected}, f)
"""


def audited_emit(kit: Kit, tmp_path: Path, env: dict[str, str]) -> dict[str, Any]:
    report = tmp_path / "audit.json"
    result = subprocess.run(
        [sys.executable, "-c", AUDIT, "claude", str(report)],
        input=json.dumps(claude_hook()),
        capture_output=True,
        text=True,
        env=env,
        cwd=kit.home,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    data: dict[str, Any] = json.loads(report.read_text(encoding="utf-8"))
    data["stdout"] = result.stdout
    return data


def tree(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*")}


def env_without_task(kit: Kit) -> dict[str, str]:
    env = {k: v for k, v in kit.env.items() if not k.startswith("GROKBOT_KIT_")}
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    return env


# C71 - AC 59
def test_no_task_id_is_inert(kit: Kit, tmp_path: Path) -> None:
    before = tree(kit.home)
    result = emit_process(env_without_task(kit), "claude", json.dumps(claude_hook()), kit.home)
    assert result.returncode == 0
    assert tree(kit.home) == before
    assert not kit.sink.exists()


def test_no_task_id_is_inert_no_connection(kit: Kit, tmp_path: Path) -> None:
    before = tree(kit.home)
    data = audited_emit(kit, tmp_path, env_without_task(kit))
    assert data["code"] == 0
    assert data["connected"] == []
    assert tree(kit.home) == before


# C72 - AC 60
def test_always_exit_0_stdout_at_most_braces_delivered(kit: Kit) -> None:
    _, env = finished_task(kit)
    result = emit_process(env, "claude", json.dumps(claude_hook(tool_use_id="toolu_ok")), kit.home)
    assert result.returncode == 0
    assert result.stdout in ("", "{}")
    assert [e["event"] for e in kit.sink_events()].count("needs_input") == 1


def test_always_exit_0_stdout_at_most_braces_delivery_failure(kit: Kit, tmp_path: Path) -> None:
    task_dir, env = finished_task(kit)
    kit.write_config(default_config(tmp_path / "nao-existe" / "sink.jsonl"))
    result = emit_process(env, "claude", json.dumps(claude_hook(tool_use_id="toolu_falha")), kit.home)
    assert result.returncode == 0
    assert result.stdout in ("", "{}")
    assert (task_dir / "undelivered.jsonl").exists()


@pytest.mark.parametrize("stdin", ["isto não é json", "", "[1, 2]", '{"hook_event_name": 3}'])
def test_always_exit_0_stdout_at_most_braces_invalid_stdin(kit: Kit, stdin: str) -> None:
    _, env = finished_task(kit)
    result = emit_process(env, "claude", stdin, kit.home)
    assert result.returncode == 0
    assert result.stdout in ("", "{}")
    assert [e["event"] for e in kit.sink_events()].count("needs_input") == 0


def test_always_exit_0_stdout_at_most_braces_missing_task_dir(kit: Kit, tmp_path: Path) -> None:
    env = {**kit.env, "GROKBOT_KIT_TASK_ID": "nao-existe", "GROKBOT_KIT_TASK_DIR": str(tmp_path / "nao-existe")}
    result = emit_process(env, "claude", json.dumps(claude_hook()), kit.home)
    assert result.returncode == 0
    assert result.stdout in ("", "{}")


# C73 - AC 61
def test_concurrent_same_key_delivers_once(kit: Kit) -> None:
    _, env = finished_task(kit)
    stdin = json.dumps(claude_hook(tool_use_id="toolu_disputa"))
    procs = [
        subprocess.Popen(
            [kit_exe(), "emit", "--from", "claude"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=kit.home,
        )
        for _ in range(8)
    ]
    for p in procs:
        assert p.stdin is not None
        p.stdin.write(stdin)
        p.stdin.close()
    assert [p.wait(timeout=30) for p in procs] == [0] * 8
    assert [e["event"] for e in kit.sink_events()].count("needs_input") == 1


# C74 - AC 62
def test_no_task_id_opens_no_kit_files(kit: Kit, tmp_path: Path) -> None:
    secrets = kit.home / ".secrets" / "grokbot-kit"
    secrets.mkdir(parents=True)
    (secrets / "chave").write_text("crsr_0000", encoding="utf-8")
    (kit.home / ".grokbot-kit" / "tasks" / "t1").mkdir(parents=True)
    data = audited_emit(kit, tmp_path, env_without_task(kit))
    assert data["code"] == 0
    kit_paths = (kit.home / ".config" / "grokbot-kit", kit.home / ".grokbot-kit", secrets)
    touched = [p for p in data["opened"] if any(Path(p).is_relative_to(k) for k in kit_paths)]
    assert touched == []


def imported_modules(env: dict[str, str], *argv: str, stdin: str = "") -> set[str]:
    result = subprocess.run(
        [sys.executable, "-X", "importtime", *argv],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    names = set()
    for line in result.stderr.splitlines():
        if line.startswith("import time:") and "|" in line:
            name = line.rsplit("|", 1)[1].strip()
            if name != "imported package":
                names.add(name)
    return names


def emit_imports(env: dict[str, str]) -> set[str]:
    """Módulos que o `emit` importa: os de `-m grokbot_kit.emit` menos os da partida do interpretador (`site`)."""
    stdin = json.dumps(claude_hook())
    return imported_modules(env, "-m", "grokbot_kit.emit", "--from", "claude", stdin=stdin) - imported_modules(
        env, "-c", "pass"
    )


def foreign(modules: set[str]) -> set[str]:
    return {m for m in modules if m.split(".")[0] not in sys.stdlib_module_names and m.split(".")[0] != "grokbot_kit"}


# C75 - AC 63, door 6
def test_importtime_gate_and_stdlib_only(kit: Kit) -> None:
    modules = emit_imports(env_without_task(kit))
    assert "grokbot_kit" in modules
    assert modules.isdisjoint({"urllib.request", "tomllib", "grokbot_kit.config"})
    assert foreign(modules) == set()


def test_importtime_gate_and_stdlib_only_inside_task(kit: Kit) -> None:
    _, env = finished_task(kit)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    modules = emit_imports(env)
    assert "grokbot_kit.config" in modules
    assert foreign(modules) == set()


def test_importtime_gate_and_stdlib_only_hook_path_before_gate(kit: Kit) -> None:
    # door 6: pelo caminho dos hooks (`grokbot-kit emit`, via cli.py), antes do gate só entram `os`, `sys` e `json`
    code = "import sys; from grokbot_kit.cli import main; sys.exit(main(['emit', '--from', 'claude']))"
    env = env_without_task(kit)
    modules = imported_modules(env, "-c", code) - imported_modules(env, "-c", "import os, sys, json")
    assert modules <= {"grokbot_kit", "grokbot_kit.cli", "grokbot_kit.emit"}
