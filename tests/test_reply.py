"""Provas do `grokbot-kit reply` (needs-input-reply, C17-C26; AC 9-18, doors 1 e 3).

Cada pedido é real: um `emit --from claude` com espera roda em segundo plano e entrega o `needs_input` ao sink;
o `reply` responde enquanto ele espera.
"""

import json
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from conftest import Kit
from test_emit import claude_hook, kit_exe
from test_emit_wait import parse_ts, request_id, running_task, write_reply


class Pending:
    def __init__(self, kit: Kit, wait: int = 10, **hook: Any) -> None:
        self.task_dir, env = running_task(kit, wait)
        self.task_id = self.task_dir.name
        data = claude_hook(**hook)
        self.rid = request_id(data)
        self.proc = subprocess.Popen(
            [kit_exe(), "emit", "--from", "claude"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=env,
            cwd=kit.home,
        )
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(data))
        self.proc.stdin.close()
        until = time.monotonic() + 10
        while not [e for e in kit.sink_events() if e["event"] == "needs_input"]:
            assert time.monotonic() < until, "o needs_input não chegou ao sink"
            time.sleep(0.05)
        [event] = [e for e in kit.sink_events() if e["event"] == "needs_input"]
        self.deadline: str = event["needs_input"]["reply_deadline"]

    def emitted(self) -> dict[str, Any]:
        assert self.proc.stdout is not None
        out = self.proc.stdout.read()
        assert self.proc.wait(timeout=30) == 0
        result: dict[str, Any] = json.loads(out)
        return result

    def reply_file(self) -> Path:
        return self.task_dir / "replies" / f"{self.rid}.json"


def reset(kit: Kit) -> None:
    """Apaga as tasks e o sink, para a próxima `Pending` ser a única task e o único `needs_input`."""
    for path in kit.tasks():
        subprocess.run(["rm", "-rf", str(path)], check=True)
    kit.sink.unlink(missing_ok=True)


def recorded(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


# C17 - AC 9
def test_allow_recorded(kit: Kit) -> None:
    p = Pending(kit)
    result = kit.cli("reply", p.task_id, p.rid, "allow")
    assert (result.returncode, result.stdout.strip()) == (0, f"recorded allow for {p.rid} (by user)")
    body = recorded(p.reply_file())
    assert (body["decision"], body["message"], body["by"]) == ("allow", None, "user")
    assert parse_ts(body["at"]).tzinfo is not None
    assert p.emitted()["hookSpecificOutput"]["decision"] == {"behavior": "allow"}


# C18 - AC 10
def test_deny_with_message(kit: Kit) -> None:
    p = Pending(kit)
    result = kit.cli("reply", p.task_id, p.rid, "deny", "--message", "fora do repo")
    assert result.returncode == 0, result.stderr
    body = recorded(p.reply_file())
    assert (body["decision"], body["message"]) == ("deny", "fora do repo")
    assert p.emitted()["hookSpecificOutput"]["decision"] == {"behavior": "deny", "message": "fora do repo"}


# C19 - AC 11
def test_message_with_allow_rejected(kit: Kit) -> None:
    p = Pending(kit, wait=2)
    result = kit.cli("reply", p.task_id, p.rid, "allow", "--message", "x")
    assert result.returncode == 2
    assert not p.reply_file().exists()
    assert not (p.task_dir / "replies").exists()
    p.emitted()


# C20 - AC 12
def test_unknown_task_or_request(kit: Kit) -> None:
    p = Pending(kit, wait=2)
    missing_task = kit.cli("reply", "20990101T000000-nada-000000", p.rid, "allow")
    assert missing_task.returncode == 1
    assert "task not found" in missing_task.stderr
    missing_request = kit.cli("reply", p.task_id, "sha256:outro", "allow")
    assert missing_request.returncode == 1
    assert "no needs_input with request_id sha256:outro" in missing_request.stderr
    assert not (p.task_dir / "replies").exists()
    p.emitted()


# C21 - AC 13
def test_already_answered_or_expired(kit: Kit) -> None:
    p = Pending(kit)
    assert kit.cli("reply", p.task_id, p.rid, "allow").returncode == 0
    before = p.reply_file().read_bytes()
    again = kit.cli("reply", p.task_id, p.rid, "deny")
    assert again.returncode == 1
    assert "already answered: allow" in again.stderr
    assert p.reply_file().read_bytes() == before
    p.emitted()

    reset(kit)
    expired = Pending(kit, wait=1, tool_name="Write")
    expired.emitted()
    assert recorded(expired.reply_file())["by"] == "timeout"
    late = kit.cli("reply", expired.task_id, expired.rid, "allow")
    assert late.returncode == 1
    assert f"no reply before {expired.deadline}; the request was denied" in late.stderr


def test_expired_before_emit_records_it(kit: Kit) -> None:
    # o prazo passou e o arquivo do prazo ainda não existe (o `emit` morreu): o `reply` recusa do mesmo jeito
    p = Pending(kit, wait=1)
    p.proc.kill()
    p.proc.wait()
    while datetime.now(UTC) <= parse_ts(p.deadline):
        time.sleep(0.1)
    late = kit.cli("reply", p.task_id, p.rid, "allow")
    assert late.returncode == 1
    assert f"no reply before {p.deadline}; the request was denied" in late.stderr
    assert not p.reply_file().exists()


# C22 - AC 14
def test_task_finished(kit: Kit) -> None:
    p = Pending(kit, wait=2)
    meta = json.loads((p.task_dir / "meta.json").read_text(encoding="utf-8"))
    meta["finished_at"] = "2026-11-05T12:00:00Z"
    (p.task_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    result = kit.cli("reply", p.task_id, p.rid, "allow")
    assert result.returncode == 1
    assert "task already finished" in result.stderr
    assert not p.reply_file().exists()
    p.emitted()


# C23 - AC 15
def test_request_id_charset(kit: Kit) -> None:
    p = Pending(kit, wait=2)
    for bad in ("../x", "a/b", "a b"):
        result = kit.cli("reply", p.task_id, bad, "allow")
        assert result.returncode == 2, bad
    assert not (p.task_dir / "replies").exists()
    for good in ("sha256:abc", "chatcmpl-tool-1.x_y"):
        result = kit.cli("reply", p.task_id, good, "allow")
        assert result.returncode == 1, good
        assert "no needs_input with request_id" in result.stderr
    p.emitted()


# C24 - AC 16
def test_race_single_decision(kit: Kit) -> None:
    for round_ in range(20):
        reset(kit)
        p = Pending(kit, wait=1, tool_input={"command": f"touch r{round_}"})
        # o `reply` sai um pouco antes do prazo: passa da checagem de prazo e chega ao `write_once` junto com o do
        # `emit`; vale um só, e os dois lados contam a mesma história
        deadline = parse_ts(p.deadline) - timedelta(milliseconds=40 + 5 * round_)
        while datetime.now(UTC) < deadline:
            time.sleep(0.002)
        answered = kit.cli("reply", p.task_id, p.rid, "allow").returncode
        decision = p.emitted()["hookSpecificOutput"]["decision"]["behavior"]
        files = [f for f in (p.task_dir / "replies").iterdir() if f.suffix == ".json"]
        assert len(files) == 1
        body = recorded(files[0])
        assert body["decision"] == decision
        assert (answered == 0) == (body["by"] == "user") == (decision == "allow")


def test_race_single_decision_layer(tmp_path: Path) -> None:
    # 12 processos gravam a mesma resposta ao mesmo tempo: só um consegue, e o arquivo é o dele
    path = tmp_path / "replies" / "r.json"
    start = time.time() + 1.0
    code = (
        "import sys, time, json\n"
        "from grokbot_kit.emit import write_once\n"
        "start, who, path = float(sys.argv[1]), sys.argv[2], sys.argv[3]\n"
        "while time.time() < start: pass\n"
        "print(json.dumps(write_once(path, {'decision': 'allow', 'message': None, 'by': who, 'at': 'x'})))\n"
    )
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(start), f"p{i}", str(path)], stdout=subprocess.PIPE, text=True
        )
        for i in range(12)
    ]
    results = {f"p{i}": json.loads(p.communicate(timeout=30)[0]) for i, p in enumerate(procs)}
    winners = [who for who, won in results.items() if won]
    assert len(winners) == 1, results
    assert recorded(path)["by"] == winners[0]
    assert [f.name for f in path.parent.iterdir()] == ["r.json"]


# C25 - AC 17
def test_by_bot_logged(kit: Kit) -> None:
    p = Pending(kit)
    result = kit.cli("reply", p.task_id, p.rid, "allow", "--by", "bot")
    assert (result.returncode, result.stdout.strip()) == (0, f"recorded allow for {p.rid} (by bot)")
    assert recorded(p.reply_file())["by"] == "bot"
    assert f"reply: allow for {p.rid} by bot" in (p.task_dir / "kit.log").read_text(encoding="utf-8")
    p.emitted()


# C26 - AC 18
def test_by_invalid(kit: Kit) -> None:
    p = Pending(kit, wait=2)
    result = kit.cli("reply", p.task_id, p.rid, "allow", "--by", "robot")
    assert result.returncode == 2
    assert not (p.task_dir / "replies").exists()
    p.emitted()


def test_notify_only_request_refused(kit: Kit) -> None:
    # um pedido entregue sem espera (`reply_deadline` `null`) não tem ninguém esperando a resposta
    task_dir, env = running_task(kit, 0)
    data = claude_hook()
    subprocess.run(
        [kit_exe(), "emit", "--from", "claude"], input=json.dumps(data), text=True, env=env, cwd=kit.home, check=True
    )
    result = kit.cli("reply", task_dir.name, request_id(data), "allow")
    assert result.returncode == 1
    assert "does not wait for a reply" in result.stderr
    assert not (task_dir / "replies").exists()


def test_write_reply_helper_matches_door_1(kit: Kit) -> None:
    # o formato que os testes do `emit` gravam é o mesmo que o `reply` grava
    p = Pending(kit, wait=2)
    write_reply(p.task_dir, "x", "allow")
    assert set(recorded(p.task_dir / "replies" / "x.json")) == {"decision", "message", "by", "at"}
    kit.cli("reply", p.task_id, p.rid, "allow")
    assert set(recorded(p.reply_file())) == {"decision", "message", "by", "at"}
    p.emitted()
