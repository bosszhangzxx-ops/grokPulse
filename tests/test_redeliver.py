"""Provas do `grokbot-kit redeliver` (checks C85 e C86; AC 73 e 74, door 15).

Uma task real é lançada por `grokbot-kit run` com a routine respondendo `4xx`, o que deixa o evento terminal em
`undelivered.jsonl`; depois o receptor passa a aceitar e o `redeliver` roda como subprocesso.
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from conftest import KEY, Kit, Receiver, add_routine, write_secret

CLAUDE_OK = json.dumps({"type": "result", "is_error": False, "result": "pronto", "permission_denials": []})
RECEIPT = json.dumps({"success": True, "runUuid": "u-redeliver"})
REJECT = json.dumps({"message": "rejeitado"})


def lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def failed_task(kit: Kit, target: str = "bot-r") -> Path:
    result = kit.run("--tool", "claude", "--target", target, "--label", "reenvio", "--", "faça", FAKE_STDOUT=CLAUDE_OK)
    assert result.returncode == 0, result.stderr
    task_dir = kit.task_dir()
    assert lines(task_dir / "undelivered.jsonl"), "a entrega deveria ter falhado"
    return task_dir


def redeliver_process(kit: Kit, task_id: str) -> subprocess.Popen[str]:
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    return subprocess.Popen(
        [exe, "redeliver", task_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=kit.env,
        cwd=kit.home,
    )


def two_routines(kit: Kit, a: Receiver, b: Receiver) -> None:
    for name, receiver in (("a", a), ("b", b)):
        write_secret(kit.home, f"{name}-url", receiver.url + "\n")
        write_secret(kit.home, f"{name}-key", KEY + "\n")
    route = ["", "[routes.bot-2]", 'sinks = ["rotina-a", "rotina-b"]', ""]
    for name in ("a", "b"):
        route += [
            f"[sinks.rotina-{name}]",
            'type = "grokbot-routine"',
            f'url_secret = "{name}-url"',
            f'key_secret = "{name}-key"',
            "",
        ]
    kit.write_config(kit.config_text() + "\n".join(route))


# C85 - AC 73
def test_exit_codes_0_1_2_all_delivered(kit: Kit, receiver: Receiver) -> None:
    add_routine(kit, receiver)
    receiver.respond((400, REJECT))
    task_dir = failed_task(kit)
    receiver.respond((200, RECEIPT))
    result = kit.cli("redeliver", task_dir.name)
    assert result.returncode == 0, result.stderr
    assert (task_dir / "undelivered.jsonl").read_text(encoding="utf-8") == ""
    first, second = receiver.requests
    assert json.loads(second.body) == json.loads(first.body)
    assert "u-redeliver" in result.stdout
    redelivered = [r for r in lines(task_dir / "events.jsonl") if r["deliveries"][0]["delivered"]]
    assert redelivered[-1]["deliveries"][0]["run_uuid"] == "u-redeliver"


def test_exit_codes_0_1_2_same_retry_policy(kit: Kit, receiver: Receiver) -> None:
    add_routine(kit, receiver)
    receiver.respond((400, REJECT))
    task_dir = failed_task(kit)
    receiver.respond((400, REJECT), (503, "fora"), (200, RECEIPT))
    result = kit.cli("redeliver", task_dir.name)
    assert result.returncode == 0, result.stderr
    assert len(receiver.requests) == 3
    assert 1 <= receiver.requests[2].at - receiver.requests[1].at < 2.5
    assert lines(task_dir / "undelivered.jsonl") == []


def test_exit_codes_0_1_2_one_failed_stays(kit: Kit, receiver: Receiver, receiver_b: Receiver) -> None:
    two_routines(kit, receiver, receiver_b)
    receiver.respond((400, REJECT))
    receiver_b.respond((400, REJECT))
    task_dir = failed_task(kit, "bot-2")
    assert [line["sink"] for line in lines(task_dir / "undelivered.jsonl")] == ["rotina-a", "rotina-b"]
    receiver.respond((200, RECEIPT))
    receiver_b.respond((404, json.dumps({"message": "routine apagada"})))
    result = kit.cli("redeliver", task_dir.name)
    assert result.returncode == 1
    (left,) = lines(task_dir / "undelivered.jsonl")
    assert left["sink"] == "rotina-b"
    assert left["http_status"] == 404
    assert left["message"] == "routine apagada"
    assert len(receiver.requests) == 2 and len(receiver_b.requests) == 2


def test_exit_codes_0_1_2_unknown_task(kit: Kit) -> None:
    for task_id in ("20261019T000000-nada-abcdef", "../tasks", ""):
        result = kit.cli("redeliver", task_id)
        assert result.returncode == 2, task_id


# C86 - AC 74
def wait_for(path: Path, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        assert time.monotonic() < deadline, f"{path} não apareceu"
        time.sleep(0.02)


def test_concurrent_redeliver_lock(kit: Kit, receiver: Receiver) -> None:
    add_routine(kit, receiver)
    receiver.respond((400, REJECT))
    task_dir = failed_task(kit)
    receiver.respond((400, REJECT), (200, RECEIPT))
    receiver.delay = 1.5
    lock = task_dir / "redeliver.lock"
    first = redeliver_process(kit, task_dir.name)
    wait_for(lock)
    assert lock.read_text(encoding="utf-8").strip() == str(first.pid)
    second = redeliver_process(kit, task_dir.name)
    assert first.wait(timeout=60) == 0, first.stderr.read() if first.stderr else ""
    assert second.wait(timeout=60) == 0, second.stderr.read() if second.stderr else ""
    assert len(receiver.requests) == 2, "o evento foi reentregue mais de uma vez"
    assert lines(task_dir / "undelivered.jsonl") == []
    assert not lock.exists()


def test_concurrent_redeliver_lock_held_blocks_delivery(kit: Kit, receiver: Receiver) -> None:
    add_routine(kit, receiver)
    receiver.respond((400, REJECT))
    task_dir = failed_task(kit)
    receiver.respond((400, REJECT), (200, RECEIPT))
    lock = task_dir / "redeliver.lock"
    lock.write_text(f"{os.getpid()}\n", encoding="utf-8")
    process = redeliver_process(kit, task_dir.name)
    time.sleep(1.5)
    assert process.poll() is None, "o redeliver não esperou o lock"
    assert len(receiver.requests) == 1
    lock.unlink()
    assert process.wait(timeout=60) == 0
    assert len(receiver.requests) == 2
    assert not lock.exists()


def test_concurrent_redeliver_lock_stale_is_taken(kit: Kit, receiver: Receiver) -> None:
    add_routine(kit, receiver)
    receiver.respond((400, REJECT))
    task_dir = failed_task(kit)
    receiver.respond((400, REJECT), (200, RECEIPT))
    dead = subprocess.Popen(["true"])
    dead.wait()
    (task_dir / "redeliver.lock").write_text(f"{dead.pid}\n", encoding="utf-8")
    result = kit.cli("redeliver", task_dir.name, timeout=30)
    assert result.returncode == 0, result.stderr
    assert len(receiver.requests) == 2
