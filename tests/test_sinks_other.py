"""Provas dos sinks `file`, `ntfy` e `slack` (checks C90-C94; AC 120-124, door 3).

Na fronteira, `grokbot-kit run` entrega o evento terminal; na própria camada, `sinks.send` é chamado direto.
"""

import hashlib
import json
import os
import stat
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from conftest import Kit, Receiver, closed_port_url, write_secret

from grokbot_kit import sinks

CLAUDE_OK = json.dumps({"type": "result", "is_error": False, "result": "pronto: ação é", "permission_denials": []})
CLAUDE_EMPTY = json.dumps({"type": "result", "is_error": False, "result": "", "permission_denials": []})


def task_event(**extra: Any) -> dict[str, Any]:
    return {
        "schema": "grokbot-kit.event/v1",
        "event": "completed",
        "status": "ok",
        "task_label": "notif",
        "target": "bot-x",
        "summary": "pronto",
        **extra,
    }


def body_of(event: dict[str, Any]) -> bytes:
    return json.dumps(event, ensure_ascii=False).encode("utf-8")


def run_task(kit: Kit, target: str, stdout: str = CLAUDE_OK, exit_code: int = 0) -> tuple[Any, Path]:
    result = kit.run(
        "--tool",
        "claude",
        "--target",
        target,
        "--label",
        "notif",
        "--",
        "faça",
        FAKE_STDOUT=stdout,
        FAKE_EXIT=str(exit_code),
    )
    return result, kit.task_dir()


def undelivered(task_dir: Path) -> list[dict[str, Any]]:
    path = task_dir / "undelivered.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def add_route(kit: Kit, target: str, sink: str, lines: list[str]) -> None:
    text = "\n".join(["", f"[routes.{target}]", f'sinks = ["{sink}"]', "", f"[sinks.{sink}]", *lines, ""])
    kit.write_config(kit.config_text() + text)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def observed(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    seen: dict[str, list[Any]] = {"sleeps": [], "timeouts": []}
    real_urlopen = urllib.request.urlopen

    def urlopen(*args: Any, **kwargs: Any) -> Any:
        seen["timeouts"].append(kwargs.get("timeout"))
        return real_urlopen(*args, **kwargs)

    monkeypatch.setattr("time.sleep", lambda s: seen["sleeps"].append(s))
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return seen


# C90 - AC 120
def test_file_sink_appends_line_0600(kit: Kit) -> None:
    result, task_dir = run_task(kit, "bot-a")
    assert result.returncode == 0, result.stderr
    raw = kit.sink.read_bytes()
    assert raw.endswith(b"\n") and raw.count(b"\n") == 1
    assert "pronto: ação é".encode() in raw and b"\\u00e9" not in raw
    assert stat.S_IMODE(kit.sink.stat().st_mode) == 0o600
    (record,) = [json.loads(line) for line in (task_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert record["body_digest"] == "sha256:" + hashlib.sha256(raw[:-1]).hexdigest()


def test_file_sink_appends_line_0600_existing_file_kept(kit: Kit) -> None:
    kit.sink.write_text("linha antiga\n", encoding="utf-8")
    os.chmod(kit.sink, 0o640)
    result, _ = run_task(kit, "bot-a")
    assert result.returncode == 0, result.stderr
    lines = kit.sink.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "linha antiga"
    assert json.loads(lines[1])["event"] == "completed"
    assert len(lines) == 2


def test_file_sink_appends_line_0600_flags_layer(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = home / "eventos.jsonl"
    opened: list[tuple[str, int, int]] = []
    real_open = os.open

    def spy(file: Any, flags: int, mode: int = 0o777, *args: Any, **kwargs: Any) -> int:
        opened.append((os.fspath(file), flags, mode))
        return real_open(file, flags, mode, *args, **kwargs)

    monkeypatch.setattr(os, "open", spy)
    event = task_event()
    result = sinks.send("arquivo", {"type": "file", "path": str(path)}, event, body_of(event))
    assert result.delivered
    ((_, flags, mode),) = [o for o in opened if o[0] == str(path)]
    assert flags & os.O_APPEND and flags & os.O_CREAT
    assert mode == 0o600
    assert path.read_bytes() == body_of(event) + b"\n"


# C91 - AC 121
@pytest.mark.parametrize("status", [200, 201, 299])
def test_ntfy_request_and_success(home: Path, receiver: Receiver, status: int) -> None:
    write_secret(home, "n-token", "tk_ntfy_123\n")
    receiver.respond((status, "{}"))
    event = task_event()
    result = sinks.send("avisos", {"type": "ntfy", "topic_url": receiver.url, "token_secret": "n-token"}, event, b"")
    assert result.delivered
    (request,) = receiver.requests
    assert request.method == "POST"
    assert request.body == b"pronto"
    assert request.headers["title"] == "grokbot-kit completed ok notif"
    assert request.headers["authorization"] == "Bearer tk_ntfy_123"


def test_ntfy_request_and_success_empty_summary_null_label_no_token(home: Path, receiver: Receiver) -> None:
    receiver.respond((200, "{}"))
    event = task_event(event="test", status="test", task_label=None, summary="")
    result = sinks.send("avisos", {"type": "ntfy", "topic_url": receiver.url}, event, b"")
    assert result.delivered
    (request,) = receiver.requests
    assert request.body == b"test test"
    assert request.headers["title"] == "grokbot-kit test test test"
    assert "authorization" not in request.headers


def test_ntfy_request_and_success_cli(kit: Kit, receiver: Receiver) -> None:
    receiver.respond((200, "{}"))
    add_route(kit, "bot-n", "avisos", ['type = "ntfy"', f'topic_url = "{receiver.url}"'])
    result, task_dir = run_task(kit, "bot-n", stdout=CLAUDE_EMPTY)
    assert result.returncode == 0, result.stderr
    (request,) = receiver.requests
    assert request.body == b"completed ok"
    assert request.headers["title"] == "grokbot-kit completed ok notif"
    assert undelivered(task_dir) == []


# C92 - AC 122
def test_slack_request_and_ok_body(home: Path, receiver: Receiver) -> None:
    write_secret(home, "k-hook", receiver.url + "\n")
    receiver.respond((200, "ok"))
    event = task_event()
    result = sinks.send("canal", {"type": "slack", "webhook_secret": "k-hook"}, event, b"")
    assert result.delivered
    (request,) = receiver.requests
    assert request.headers["content-type"] == "application/json"
    assert json.loads(request.body) == {"text": "[grokbot-kit] completed/ok notif (bot-x)\npronto"}


@pytest.mark.parametrize("status, text", [(200, "no_text"), (200, ""), (201, "ok")])
def test_slack_request_and_ok_body_other_body_fails(home: Path, receiver: Receiver, status: int, text: str) -> None:
    write_secret(home, "k-hook", receiver.url + "\n")
    receiver.respond((status, text))
    event = task_event()
    result = sinks.send("canal", {"type": "slack", "webhook_secret": "k-hook"}, event, b"")
    assert not result.delivered
    assert len(receiver.requests) == 1


def test_slack_request_and_ok_body_cli(kit: Kit, receiver: Receiver) -> None:
    write_secret(kit.home, "k-hook", receiver.url + "\n")
    add_route(kit, "bot-k", "canal", ['type = "slack"', 'webhook_secret = "k-hook"'])
    receiver.respond((200, "invalid_payload"))
    result, task_dir = run_task(kit, "bot-k")
    assert result.returncode == 0, result.stderr
    (request,) = receiver.requests
    assert json.loads(request.body) == {"text": "[grokbot-kit] completed/ok notif (bot-k)\npronto: ação é"}
    (line,) = undelivered(task_dir)
    assert line["sink"] == "canal"
    assert line["http_status"] == 200


# C93 - AC 123
def other_sink(kind: str, home: Path, url: str) -> dict[str, Any]:
    if kind == "ntfy":
        return {"type": "ntfy", "topic_url": url}
    write_secret(home, "k-hook", url + "\n")
    return {"type": "slack", "webhook_secret": "k-hook"}


@pytest.mark.parametrize("kind", ["ntfy", "slack"])
@pytest.mark.parametrize("status", [429, 500])
def test_ntfy_slack_retry_table(home: Path, receiver: Receiver, observed: Any, kind: str, status: int) -> None:
    receiver.respond((status, "depois"))
    event = task_event()
    result = sinks.send(kind, other_sink(kind, home, receiver.url), event, body_of(event))
    assert not result.delivered
    assert result.http_status == status
    assert len(receiver.requests) == 3
    assert observed["sleeps"] == [1, 4]
    assert observed["timeouts"] == [10, 10, 10]


@pytest.mark.parametrize("kind", ["ntfy", "slack"])
def test_ntfy_slack_retry_table_connection_refused(home: Path, observed: Any, kind: str) -> None:
    event = task_event()
    result = sinks.send(kind, other_sink(kind, home, closed_port_url()), event, body_of(event))
    assert not result.delivered
    assert len(observed["timeouts"]) == 3
    assert observed["sleeps"] == [1, 4]


@pytest.mark.parametrize("kind", ["ntfy", "slack"])
@pytest.mark.parametrize("status", [400, 403, 404])
def test_ntfy_slack_retry_table_4xx_no_retry(
    home: Path, receiver: Receiver, observed: Any, kind: str, status: int
) -> None:
    receiver.respond((status, "não"))
    event = task_event()
    result = sinks.send(kind, other_sink(kind, home, receiver.url), event, body_of(event))
    assert not result.delivered
    assert result.http_status == status
    assert len(receiver.requests) == 1
    assert observed["sleeps"] == []


@pytest.mark.parametrize("kind", ["ntfy", "slack"])
def test_ntfy_slack_retry_table_cli_4xx_to_undelivered(kit: Kit, receiver: Receiver, kind: str) -> None:
    receiver.respond((404, "sem tópico"))
    if kind == "ntfy":
        add_route(kit, "bot-o", "outro", ['type = "ntfy"', f'topic_url = "{receiver.url}"'])
    else:
        write_secret(kit.home, "k-hook", receiver.url + "\n")
        add_route(kit, "bot-o", "outro", ['type = "slack"', 'webhook_secret = "k-hook"'])
    result, task_dir = run_task(kit, "bot-o", exit_code=3)
    assert result.returncode == 3
    assert len(receiver.requests) == 1
    (line,) = undelivered(task_dir)
    assert line["http_status"] == 404
    assert line["message"] == "sem tópico"
    assert f"grokbot-kit redeliver {task_dir.name}" in result.stderr


# C94 - AC 124
@pytest.mark.parametrize("exit_code", [0, 3])
def test_file_sink_write_failure(kit: Kit, tmp_path: Path, exit_code: int) -> None:
    locked = tmp_path / "trancado"
    locked.mkdir(mode=0o500)
    add_route(kit, "bot-f", "trancado", ['type = "file"', f"path = {json.dumps(str(locked / 'eventos.jsonl'))}"])
    try:
        result, task_dir = run_task(kit, "bot-f", exit_code=exit_code)
    finally:
        locked.chmod(0o700)
    assert result.returncode == exit_code
    (line,) = undelivered(task_dir)
    assert line["sink"] == "trancado"
    assert line["http_status"] is None
    assert "Permission denied" in line["message"]
    assert line["event"]["event"] in ("completed", "error")
    assert not (locked / "eventos.jsonl").exists()


def test_file_sink_write_failure_no_retry_layer(home: Path, observed: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    locked = home / "trancado"
    locked.mkdir(mode=0o500)
    path = locked / "eventos.jsonl"
    attempts: list[str] = []
    real_open = os.open

    def spy(file: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if os.fspath(file) == str(path):
            attempts.append(os.fspath(file))
        return real_open(file, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", spy)
    event = task_event()
    try:
        result = sinks.send("trancado", {"type": "file", "path": str(path)}, event, body_of(event))
    finally:
        locked.chmod(0o700)
    assert not result.delivered
    assert result.http_status is None
    assert "Permission denied" in result.message
    assert attempts == [str(path)]
    assert observed["sleeps"] == []
