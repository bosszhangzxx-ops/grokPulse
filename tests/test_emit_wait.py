"""Provas da espera do `grokbot-kit emit` pela resposta do bot (needs-input-reply, C5-C15, C34, C42, C58).

Cada teste parte de uma task real (`run` com a CLI falsa) e reabre o `meta.json` como se ela ainda rodasse, com a
espera curta do teste. A resposta é o arquivo da door 1, gravado por uma thread no meio da espera.
"""

import json
import os
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from conftest import Kit, Receiver, add_routine
from test_emit import claude_hook, finished_task, kit_exe, opencode_permission

from grokbot_kit import emit

CLAUDE_ALLOW = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}


def claude_deny(message: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "deny", "message": message},
        }
    }


def running_task(kit: Kit, wait: int, *, timeout_seconds: int = 7200, **meta_extra: Any) -> tuple[Path, dict[str, str]]:
    """Uma task lançada por `run` e reaberta: sem `finished_at`, com `ask_wait_seconds` = `wait` e `started_at` agora."""
    task_dir, env = finished_task(kit)
    meta = json.loads((task_dir / "meta.json").read_text(encoding="utf-8"))
    meta.update(
        finished_at=None,
        exit_code=None,
        ask_wait_seconds=wait,
        timeout_seconds=timeout_seconds,
        started_at=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        **meta_extra,
    )
    (task_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return task_dir, env


def request_id(data: dict[str, Any]) -> str:
    asked = emit.normalize("claude", data)
    assert asked is not None
    return str(asked["discriminator"])


def write_reply(task_dir: Path, rid: str, decision: str, message: str | None = None, by: str = "user") -> None:
    replies = task_dir / "replies"
    replies.mkdir(exist_ok=True)
    body = {"decision": decision, "message": message, "by": by, "at": datetime.now(UTC).isoformat()}
    tmp = replies / f".{rid}.tmp"
    tmp.write_text(json.dumps(body), encoding="utf-8")
    os.link(tmp, replies / f"{rid}.json")
    tmp.unlink()


def reply_later(task_dir: Path, rid: str, after: float, decision: str = "allow", message: str | None = None) -> None:
    def go() -> None:
        time.sleep(after)
        write_reply(task_dir, rid, decision, message)

    threading.Thread(target=go, daemon=True).start()


def run_emit(env: dict[str, str], source: str, data: dict[str, Any], cwd: Path, **extra_env: str) -> tuple[Any, float]:
    started = time.monotonic()
    proc = subprocess.run(
        [kit_exe(), "emit", "--from", source],
        input=json.dumps(data),
        capture_output=True,
        text=True,
        env={**env, **extra_env},
        cwd=cwd,
        check=False,
        timeout=60,
    )
    return proc, time.monotonic() - started


def needs_inputs(kit: Kit) -> list[dict[str, Any]]:
    return [e for e in kit.sink_events() if e["event"] == "needs_input"]


def parse_ts(text: str) -> datetime:
    return datetime.fromisoformat(text)


# C5 - AC 2
def test_needs_input_fields(kit: Kit) -> None:
    task_dir, env = running_task(kit, 3)
    data = claude_hook()
    reply_later(task_dir, request_id(data), 0.5)
    before = datetime.now(UTC)
    proc, _ = run_emit(env, "claude", data, kit.home)
    after = datetime.now(UTC)
    assert proc.returncode == 0
    [event] = needs_inputs(kit)
    assert event["needs_input"]["request_id"] == request_id(data)
    deadline = event["needs_input"]["reply_deadline"]
    assert deadline.endswith("Z")
    # o pedido chega ao `emit` entre `before` e `after`; o prazo é ele + 3 s arredondado para cima (nunca menor que a
    # espera pedida), com 1 s de tolerância só para cima
    assert before + timedelta(seconds=3) <= parse_ts(deadline) <= after + timedelta(seconds=4)


# C6 - AC 2
def test_deadline_capped_by_task_timeout(kit: Kit) -> None:
    task_dir, env = running_task(kit, 600, timeout_seconds=2)
    meta = json.loads((task_dir / "meta.json").read_text(encoding="utf-8"))
    run_emit(env, "claude", claude_hook(), kit.home)
    [event] = needs_inputs(kit)
    expected = parse_ts(meta["started_at"]) + timedelta(seconds=2)
    assert parse_ts(event["needs_input"]["reply_deadline"]) == expected


# C7 - AC 3, door 6
def test_claude_allow(kit: Kit) -> None:
    task_dir, env = running_task(kit, 10)
    data = claude_hook()
    reply_later(task_dir, request_id(data), 1)
    proc, elapsed = run_emit(env, "claude", data, kit.home)
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == CLAUDE_ALLOW
    assert proc.stdout == json.dumps(CLAUDE_ALLOW, separators=(",", ":"))
    assert elapsed < 3


# C8 - AC 4, door 6
def test_claude_deny_message(kit: Kit) -> None:
    task_dir, env = running_task(kit, 10)
    data = claude_hook()
    reply_later(task_dir, request_id(data), 0.5, "deny", "não")
    proc, _ = run_emit(env, "claude", data, kit.home)
    assert json.loads(proc.stdout) == claude_deny("não")


def test_claude_deny_message_null(kit: Kit) -> None:
    task_dir, env = running_task(kit, 10)
    data = claude_hook(tool_name="Write")
    reply_later(task_dir, request_id(data), 0.5, "deny", None)
    proc, _ = run_emit(env, "claude", data, kit.home)
    assert json.loads(proc.stdout) == claude_deny("denied by the user")


# C9 - AC 5
def test_timeout_denies_and_records(kit: Kit) -> None:
    task_dir, env = running_task(kit, 1)
    data = claude_hook()
    proc, elapsed = run_emit(env, "claude", data, kit.home)
    assert proc.returncode == 0
    assert 1 <= elapsed < 3
    recorded = json.loads((task_dir / "replies" / f"{request_id(data)}.json").read_text(encoding="utf-8"))
    assert (recorded["decision"], recorded["by"]) == ("deny", "timeout")
    assert recorded["at"]
    [event] = needs_inputs(kit)
    deadline = event["needs_input"]["reply_deadline"]
    assert json.loads(proc.stdout) == claude_deny(f"no reply before {deadline}")


# C10 - AC 6
def test_wait_zero_notify_only(kit: Kit) -> None:
    task_dir, env = running_task(kit, 0)
    proc, elapsed = run_emit(env, "claude", claude_hook(), kit.home)
    assert (proc.returncode, proc.stdout) == (0, "{}")
    assert elapsed < 1
    [event] = needs_inputs(kit)
    assert event["needs_input"]["reply_deadline"] is None
    assert event["needs_input"]["request_id"]
    assert not (task_dir / "replies").exists()


# C11 - Impact, stored data
def test_old_meta_is_notify_only(kit: Kit) -> None:
    task_dir, env = running_task(kit, 600)
    meta = json.loads((task_dir / "meta.json").read_text(encoding="utf-8"))
    del meta["ask_wait_seconds"]
    (task_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    proc, elapsed = run_emit(env, "claude", claude_hook(), kit.home)
    assert (proc.returncode, proc.stdout) == (0, "{}")
    assert elapsed < 1
    [event] = needs_inputs(kit)
    assert event["needs_input"]["reply_deadline"] is None
    assert not (task_dir / "replies").exists()


# C12 - AC 7
def test_waits_after_failed_delivery(kit: Kit, receiver: Receiver) -> None:
    add_routine(kit, receiver)
    receiver.respond((500, "{}"))
    task_dir, env = running_task(kit, 30, target="bot-r")
    data = claude_hook()
    reply_later(task_dir, request_id(data), 1)
    proc, _ = run_emit(env, "claude", data, kit.home)
    assert len(receiver.requests) == 3
    assert json.loads(proc.stdout) == CLAUDE_ALLOW


# C13 - AC 8
def test_repeated_request_reuses_reply(kit: Kit) -> None:
    task_dir, env = running_task(kit, 10)
    data = claude_hook()
    reply_later(task_dir, request_id(data), 0.5)
    first, _ = run_emit(env, "claude", data, kit.home)
    assert json.loads(first.stdout) == CLAUDE_ALLOW
    second, elapsed = run_emit(env, "claude", data, kit.home)
    assert json.loads(second.stdout) == CLAUDE_ALLOW
    assert elapsed < 1
    assert len(needs_inputs(kit)) == 1


# C14 - AC 8, AC 61 da agent-run-notify
def test_concurrent_same_request(kit: Kit) -> None:
    task_dir, env = running_task(kit, 3)
    data = claude_hook()
    reply_later(task_dir, request_id(data), 1)
    procs = [
        subprocess.Popen(
            [kit_exe(), "emit", "--from", "claude"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=env,
            cwd=kit.home,
        )
        for _ in range(2)
    ]
    outs = [p.communicate(json.dumps(data), timeout=30)[0] for p in procs]
    assert [json.loads(o) for o in outs] == [CLAUDE_ALLOW, CLAUDE_ALLOW]
    assert len(needs_inputs(kit)) == 1


# C15 - AC 60 da agent-run-notify
def test_unreadable_reply_no_decision(kit: Kit) -> None:
    for body in ("{", json.dumps({"decision": "maybe", "message": None, "by": "user", "at": "x"})):
        task_dir, env = running_task(kit, 10)
        data = claude_hook(tool_input={"command": body})
        rid = request_id(data)
        (task_dir / "replies").mkdir(exist_ok=True)
        (task_dir / "replies" / f"{rid}.json").write_text(body, encoding="utf-8")
        proc, _ = run_emit(env, "claude", data, kit.home)
        assert (proc.returncode, proc.stdout) == (0, "{}")
        assert rid in (task_dir / "kit.log").read_text(encoding="utf-8")
        for path in kit.tasks():
            subprocess.run(["rm", "-rf", str(path)], check=True)


# C34 - door 6
def test_opencode_effect_output(kit: Kit) -> None:
    for decision, message, expected in (
        ("allow", None, '{"effect":"allow","message":null}'),
        ("deny", "m", '{"effect":"deny","message":"m"}'),
    ):
        task_dir, env = running_task(kit, 10)
        data = opencode_permission(request_id=f"call-{decision}")
        reply_later(task_dir, f"call-{decision}", 0.5, decision, message)
        proc, _ = run_emit(env, "opencode", data, kit.home, GROKBOT_KIT_REPLY="1")
        assert (proc.returncode, proc.stdout) == (0, expected)
        for path in kit.tasks():
            subprocess.run(["rm", "-rf", str(path)], check=True)


def test_opencode_without_reply_flag_is_notify_only(kit: Kit) -> None:
    # door 8: o plugin v1 (opencode 1.x) chama o `emit` sem `GROKBOT_KIT_REPLY`
    _task_dir, env = running_task(kit, 10)
    proc, elapsed = run_emit(env, "opencode", opencode_permission(), kit.home)
    assert (proc.returncode, proc.stdout) == (0, "{}")
    assert elapsed < 1
    [event] = needs_inputs(kit)
    assert event["needs_input"]["reply_deadline"] is None


# C60 - door 8
def test_only_claude_and_plugin_v2_wait(kit: Kit) -> None:
    from test_emit import codex_hook, opencode_question

    cases = [
        ("codex", codex_hook(), {}),
        ("opencode", opencode_question(), {"GROKBOT_KIT_REPLY": "1"}),
        ("opencode", opencode_permission(), {}),
    ]
    for source, data, extra in cases:
        task_dir, env = running_task(kit, 10)
        proc, elapsed = run_emit(env, source, data, kit.home, **extra)
        assert (proc.returncode, proc.stdout) == (0, "{}"), source
        assert elapsed < 1, source
        [event] = needs_inputs(kit)
        assert event["needs_input"]["reply_deadline"] is None, source
        assert not (task_dir / "replies").exists(), source
        for path in kit.tasks():
            subprocess.run(["rm", "-rf", str(path)], check=True)
        kit.sink.unlink()


# C42 - AC 29
def test_plugin_task_no_wait(kit: Kit) -> None:
    _task_dir, env = running_task(kit, 600, plugin={"name": "teste", "version": "1.2.3"})
    proc, elapsed = run_emit(env, "claude", claude_hook(), kit.home)
    assert (proc.returncode, proc.stdout) == (0, "{}")
    assert elapsed < 1
    assert needs_inputs(kit) == []


# C58 - Surface
def test_needs_input_delivery_statuses(kit: Kit, receiver: Receiver) -> None:
    add_routine(kit, receiver)
    for status, attempts, undelivered in ((401, 1, True), (429, 3, False)):
        receiver.requests.clear()
        receiver.respond((status, "{}"))
        task_dir, env = running_task(kit, 30, target="bot-r")
        data = claude_hook()
        reply_later(task_dir, request_id(data), 0.5)
        proc, _ = run_emit(env, "claude", data, kit.home)
        assert len(receiver.requests) == attempts
        assert (task_dir / "undelivered.jsonl").exists() is True
        if undelivered:
            line = json.loads((task_dir / "undelivered.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            assert line["event"]["event"] == "needs_input"
        assert json.loads(proc.stdout) == CLAUDE_ALLOW
        for path in kit.tasks():
            subprocess.run(["rm", "-rf", str(path)], check=True)
