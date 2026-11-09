"""Provas dos hooks com as CLIs reais no box (checks C67-C69, C118; AC 54-57, 97). Rodam só com `-m integration`.

Mesmo `HOME` temporário de `test_real_cli.py`, que no opencode já instala o plugin `grokbot-kit.ts` com o caminho
absoluto do `grokbot-kit` do ambiente de teste, como `grokbot-kit install opencode` o deixaria.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from integration.test_real_cli import REAL_HOME, link, model_for, prepare_home, real_bin

pytestmark = pytest.mark.integration

QUESTION_PROMPT = (
    "Before doing anything else, use your question tool to ask me which file name to use, "
    "offering the options a.txt and b.txt. Do not use any other tool."
)


def kit_exe() -> str:
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    return exe


def run_task(tmp_path: Path, home: Path, work: Path, tool: str, *cli_args: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        [kit_exe(), "run", "--tool", tool, "--target", "it", "--label", "hook", "--cwd", str(work), "--", *cli_args],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home)},
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=600,
    )
    sink = tmp_path / "sink.jsonl"
    events = [json.loads(line) for line in sink.read_text(encoding="utf-8").splitlines()] if sink.exists() else []
    assert events, result.stderr
    assert events[-1]["event"] in ("completed", "error", "timeout"), (events, result.stderr)
    return events


def asked_before_terminal(events: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    asked = [e for e in events[:-1] if e["event"] == "needs_input" and e["status"] == status]
    assert asked, events
    return asked


# C67 - AC 54
def test_claude_hook_fires(tmp_path: Path) -> None:
    home, work, prompt = prepare_home(tmp_path, "claude", "denied")
    events = run_task(tmp_path, home, work, "claude", prompt)
    asked = asked_before_terminal(events, "permission")
    assert asked[0]["needs_input"]["tool_name"] == "Bash"
    assert (events[-1]["event"], events[-1]["status"]) == ("completed", "denied")


# C68 - AC 55
def test_opencode_plugin_fires_permission(tmp_path: Path) -> None:
    home, work, prompt = prepare_home(tmp_path, "opencode", "denied")
    events = run_task(tmp_path, home, work, "opencode", prompt)
    asked_before_terminal(events, "permission")


# C68 - AD-026: o `opencode run` não interativo nega a ferramenta `question`, então o pedido não vira pergunta nem trava
def test_opencode_plugin_fires_no_question_in_run(tmp_path: Path) -> None:
    home, work, _ = prepare_home(tmp_path, "opencode", "ok")
    events = run_task(tmp_path, home, work, "opencode", QUESTION_PROMPT)
    assert events[-1]["event"] != "timeout", events
    assert not [e for e in events if e["event"] == "needs_input" and e["status"] == "question"], events


# C69 - AC 57, AD-027: o `codex exec` força `approval_policy = never` e não chama o hook `PermissionRequest`
def test_codex_hook_silent_in_exec(tmp_path: Path) -> None:
    home, work, prompt = prepare_home(tmp_path, "codex", "denied")
    events = run_task(tmp_path, home, work, "codex", "-s", "read-only", prompt)
    assert not [e for e in events if e["event"] == "needs_input"], events
    assert [(e["event"], e["status"]) for e in events] == [("completed", "ok")], events


# C118 - AC 97
def test_opencode_plugin_inert_without_task(tmp_path: Path) -> None:
    home = tmp_path / "home"
    work = tmp_path / "work"
    work.mkdir()
    link(
        REAL_HOME / ".local" / "share" / "opencode" / "auth.json", home / ".local" / "share" / "opencode" / "auth.json"
    )
    calls = tmp_path / "shim-calls.log"
    shim = tmp_path / "shim" / "grokbot-kit"
    shim.parent.mkdir()
    # cópia do console script que registra cada chamada: o `install` grava o caminho do shim no plugin
    shebang, *body = Path(kit_exe()).read_text(encoding="utf-8").splitlines()
    record = f"import sys; open({str(calls)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')"
    shim.write_text("\n".join([shebang, record, *body]) + "\n", encoding="utf-8")
    shim.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GROKBOT_KIT_")}
    env["HOME"] = str(home)

    installed = subprocess.run([str(shim), "install", "opencode"], capture_output=True, text=True, env=env, check=False)
    assert installed.returncode == 0, installed.stderr
    plugin = home / ".config" / "opencode" / "plugins" / "grokbot-kit.ts"
    assert f"const GROKBOT_KIT = {json.dumps(str(shim))}" in plugin.read_text(encoding="utf-8")
    calls.unlink()

    def opencode_run() -> int:
        argv = [real_bin("opencode"), "run", "--format", "json", "-m", model_for("opencode")]
        argv.append("Reply with exactly the word pong. Do not use any tool.")
        proc = subprocess.run(
            argv, cwd=work, env=env, stdin=subprocess.DEVNULL, capture_output=True, check=False, timeout=600
        )
        return proc.returncode

    with_plugin = opencode_run()
    assert not calls.exists(), calls.read_text(encoding="utf-8")
    plugin.unlink()
    without_plugin = opencode_run()
    assert with_plugin == without_plugin == 0


def run_and_reply(tmp_path: Path, home: Path, work: Path, tool: str, prompt: str) -> tuple[list[dict[str, Any]], int]:
    """Roda a task com espera de 120 s e responde `allow` ao primeiro `needs_input` com `grokbot-kit reply`."""
    import threading
    import time

    sink = tmp_path / "sink.jsonl"
    codes: list[int] = []

    def answer() -> None:
        until = time.monotonic() + 300
        while time.monotonic() < until:
            lines = sink.read_text(encoding="utf-8").splitlines() if sink.exists() else []
            asked = [json.loads(line) for line in lines if json.loads(line)["event"] == "needs_input"]
            if asked:
                event = asked[0]
                reply = subprocess.run(
                    [kit_exe(), "reply", event["task_id"], event["needs_input"]["request_id"], "allow"],
                    capture_output=True,
                    text=True,
                    env={**os.environ, "HOME": str(home)},
                    check=False,
                )
                codes.append(reply.returncode)
                return
            time.sleep(0.2)

    thread = threading.Thread(target=answer)
    thread.start()
    argv = [kit_exe(), "run", "--tool", tool, "--target", "it", "--label", "reply", "--cwd", str(work)]
    result = subprocess.run(
        [*argv, "--ask-wait", "120s", "--", prompt],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home)},
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=600,
    )
    thread.join()
    events = [json.loads(line) for line in sink.read_text(encoding="utf-8").splitlines()] if sink.exists() else []
    assert events, result.stderr
    return events, codes[0] if codes else -1


# C16 - S1 da needs-input-reply
def test_claude_reply_allow(tmp_path: Path) -> None:
    home, work, prompt = prepare_home(tmp_path, "claude", "denied")
    events, code = run_and_reply(tmp_path, home, work, "claude", prompt)
    assert code == 0, events
    assert (work / "criado.txt").exists()
    terminal = events[-1]
    assert (terminal["event"], terminal["status"], terminal["exit_reason"]) == ("completed", "ok", "success")


# C38 - S3 da needs-input-reply
def test_opencode_reply_allow(tmp_path: Path) -> None:
    home, work, prompt = prepare_home(tmp_path, "opencode", "denied")
    events, code = run_and_reply(tmp_path, home, work, "opencode", prompt)
    assert code == 0, events
    assert (work / "criado.txt").exists()
    plugin = home / ".config" / "opencode" / "plugins" / "grokbot-kit.ts"
    assert plugin.read_text(encoding="utf-8").startswith("// grokbot-kit opencode plugin for opencode 2\n")
    terminal = events[-1]
    assert (terminal["event"], terminal["status"], terminal["exit_reason"]) == ("completed", "ok", "success")
