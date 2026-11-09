"""Provas do sink `grokbot-routine` (checks C78-C84; AC 66-72, AD-021).

Na fronteira, `grokbot-kit run` entrega o evento terminal a um receptor HTTP local em `127.0.0.1`; na própria
camada, `sinks.send` é chamado direto, com `time.sleep` e `urllib.request.urlopen` observados para medir as esperas
e o timeout de cada tentativa sem esperar de verdade.
"""

import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from conftest import KEY, Kit, Receiver, add_routine, closed_port_url, write_secret

from grokbot_kit import __version__, sinks

CLAUDE_OK = json.dumps({"type": "result", "is_error": False, "result": "pronto: ação é", "permission_denials": []})
UNAUTHORIZED = json.dumps(
    {"code": "error", "message": "Missing Authorization header. Use Authorization: Bearer <key>."}
)
RECEIPT = json.dumps({"success": True, "runUuid": "u-1"})


def run_task(kit: Kit, exit_code: int = 0) -> tuple[Any, Path]:
    result = kit.run(
        "--tool",
        "claude",
        "--target",
        "bot-r",
        "--label",
        "rotina",
        "--",
        "faça",
        FAKE_STDOUT=CLAUDE_OK,
        FAKE_EXIT=str(exit_code),
    )
    return result, kit.task_dir()


def records(task_dir: Path, name: str) -> list[dict[str, Any]]:
    path = task_dir / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def sent_receipts(task_dir: Path) -> dict[str, dict[str, Any]]:
    return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in (task_dir / "sent").iterdir()}


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def observed(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[float]]:
    """Esperas pedidas a `time.sleep` e o `timeout` de cada chamada a `urllib.request.urlopen`."""
    seen: dict[str, list[float]] = {"sleeps": [], "timeouts": []}
    real_urlopen = urllib.request.urlopen

    def urlopen(*args: Any, **kwargs: Any) -> Any:
        seen["timeouts"].append(kwargs.get("timeout", args[2] if len(args) > 2 else None))
        return real_urlopen(*args, **kwargs)

    monkeypatch.setattr("time.sleep", lambda s: seen["sleeps"].append(s))
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return seen


def routine_sink(home: Path, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    write_secret(home, "r-url", url + "\n")
    write_secret(home, "r-key", KEY + "\n")
    sink: dict[str, Any] = {"type": "grokbot-routine", "url_secret": "r-url", "key_secret": "r-key"}
    if headers:
        sink["headers"] = headers
    return sink


EVENT = {"schema": "grokbot-kit.event/v1", "event": "test", "status": "test", "target": "bot-r", "summary": "é"}
BODY = json.dumps(EVENT, ensure_ascii=False).encode("utf-8")


# C78 - AC 66
def test_request_headers_literal(kit: Kit, receiver: Receiver) -> None:
    add_routine(kit, receiver, headers={"X-Grokbot-Bot": "bot-r", "X-Extra": "1"})
    result, _ = run_task(kit)
    assert result.returncode == 0, result.stderr
    assert len(receiver.requests) == 1
    request = receiver.requests[0]
    assert request.method == "POST"
    assert request.path == "/automations/webhook/0f3c-routine-uuid"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.headers["content-type"] == "application/json"
    assert request.headers["user-agent"] == f"grokbot-kit/{__version__}"
    assert request.headers["x-grokbot-bot"] == "bot-r"
    assert request.headers["x-extra"] == "1"


def test_request_headers_literal_layer(home: Path, receiver: Receiver) -> None:
    result = sinks.send("rotina", routine_sink(home, receiver.url, {"X-Extra": "2"}), EVENT, BODY)
    assert result.delivered
    request = receiver.requests[0]
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.headers["content-type"] == "application/json"
    assert request.headers["user-agent"] == f"grokbot-kit/{__version__}"
    assert request.headers["x-extra"] == "2"
    assert request.body == BODY


# C79 - AC 67
def test_body_utf8_and_digest(kit: Kit, receiver: Receiver) -> None:
    add_routine(kit, receiver)
    result, task_dir = run_task(kit)
    assert result.returncode == 0, result.stderr
    body = receiver.requests[0].body
    assert "pronto: ação é".encode() in body
    assert b"\\u00e7" not in body and b"\\u00e9" not in body
    event = json.loads(body.decode("utf-8"))
    assert isinstance(event, dict) and event["schema"] == "grokbot-kit.event/v1"
    (record,) = records(task_dir, "events.jsonl")
    assert record["body_digest"] == "sha256:" + hashlib.sha256(body).hexdigest()


# C80 - AC 68
@pytest.mark.parametrize("status", [200, 202])
def test_receipt_on_2xx_success(kit: Kit, receiver: Receiver, status: int) -> None:
    add_routine(kit, receiver)
    receiver.respond((status, RECEIPT))
    result, task_dir = run_task(kit)
    assert result.returncode == 0, result.stderr
    receipts = sent_receipts(task_dir)
    assert list(receipts) == [f"{task_dir.name}:completed:terminal"]
    (delivery,) = receipts[f"{task_dir.name}:completed:terminal"]["deliveries"]
    assert delivery["run_uuid"] == "u-1"
    assert delivery["http_status"] == status
    assert delivery["delivered"] is True
    (record,) = records(task_dir, "events.jsonl")
    assert record["deliveries"][0]["run_uuid"] == "u-1"
    assert record["deliveries"][0]["http_status"] == status
    assert records(task_dir, "undelivered.jsonl") == []


# C81 - AC 69
@pytest.mark.parametrize(
    "body",
    [
        json.dumps({"success": False}),
        json.dumps({"success": True}),
        json.dumps({"runUuid": "u-1"}),
        json.dumps({"success": "true", "runUuid": "u-1"}),
        "ok",
    ],
)
def test_2xx_without_receipt_fails_without_retry(kit: Kit, receiver: Receiver, body: str) -> None:
    add_routine(kit, receiver)
    receiver.respond((200, body))
    result, task_dir = run_task(kit)
    assert result.returncode == 0, result.stderr
    assert len(receiver.requests) == 1
    (line,) = records(task_dir, "undelivered.jsonl")
    assert line["http_status"] == 200
    assert line["sink"] == "rotina-bot-r"
    assert line["event"]["event"] == "completed"


def test_2xx_without_receipt_fails_without_retry_layer(home: Path, receiver: Receiver, observed: Any) -> None:
    receiver.respond((200, json.dumps({"success": False})))
    result = sinks.send("rotina", routine_sink(home, receiver.url), EVENT, BODY)
    assert not result.delivered
    assert result.http_status == 200
    assert len(receiver.requests) == 1
    assert observed["sleeps"] == []


# C82 - AC 70
def test_secret_never_written(kit: Kit, receiver: Receiver) -> None:
    add_routine(kit, receiver)
    receiver.respond((401, UNAUTHORIZED))
    result, task_dir = run_task(kit)
    secret_values = [KEY, receiver.url, "0f3c-routine-uuid"]
    places = {"stdout": result.stdout, "stderr": result.stderr, "config": kit.config_text()}
    for path in task_dir.rglob("*"):
        if path.is_file():
            places[str(path.relative_to(task_dir))] = path.read_text(encoding="utf-8", errors="replace")
    places["eventos recebidos"] = b"".join(r.body for r in receiver.requests).decode("utf-8")
    assert "undelivered.jsonl" in places
    for where, text in places.items():
        for value in secret_values:
            assert value not in text, f"{value!r} em {where}"


def test_secret_never_written_echoed_by_server(home: Path, receiver: Receiver) -> None:
    receiver.respond((400, json.dumps({"message": f"bad key {KEY} for {receiver.url}"})))
    result = sinks.send("rotina", routine_sink(home, receiver.url), EVENT, BODY)
    assert not result.delivered
    assert KEY not in result.message and receiver.url not in result.message


def test_secret_never_written_invalid_url(home: Path) -> None:
    result = sinks.send("rotina", routine_sink(home, "ftp://segredo.example/xyz-123"), EVENT, BODY)
    assert not result.delivered
    assert "segredo.example" not in result.message and "xyz-123" not in result.message


# C83 - AC 71
@pytest.mark.parametrize("status", [429, 500, 503])
def test_retry_table_429_5xx_connection(home: Path, receiver: Receiver, observed: Any, status: int) -> None:
    receiver.respond((status, json.dumps({"message": "tente depois"})))
    result = sinks.send("rotina", routine_sink(home, receiver.url), EVENT, BODY)
    assert not result.delivered
    assert result.http_status == status
    assert len(receiver.requests) == 3
    assert observed["sleeps"] == [1, 4]
    assert observed["timeouts"] == [10, 10, 10]


def test_retry_table_429_5xx_connection_refused(home: Path, observed: Any) -> None:
    result = sinks.send("rotina", routine_sink(home, closed_port_url()), EVENT, BODY)
    assert not result.delivered
    assert result.http_status is None
    assert len(observed["timeouts"]) == 3
    assert observed["sleeps"] == [1, 4]


def test_retry_table_429_5xx_connection_success_on_second(home: Path, receiver: Receiver, observed: Any) -> None:
    receiver.respond((500, "erro"), (200, RECEIPT))
    result = sinks.send("rotina", routine_sink(home, receiver.url), EVENT, BODY)
    assert result.delivered
    assert result.run_uuid == "u-1"
    assert len(receiver.requests) == 2
    assert observed["sleeps"] == [1]


def test_retry_table_429_5xx_connection_cli_real_waits(kit: Kit, receiver: Receiver) -> None:
    add_routine(kit, receiver)
    receiver.respond((503, json.dumps({"message": "indisponível"})))
    result, task_dir = run_task(kit)
    assert result.returncode == 0, result.stderr
    times = [r.at for r in receiver.requests]
    assert len(times) == 3
    assert 1 <= times[1] - times[0] < 2.5
    assert 4 <= times[2] - times[1] < 5.5
    (line,) = records(task_dir, "undelivered.jsonl")
    assert line["http_status"] == 503
    assert line["message"] == "indisponível"


# C84 - AC 72
NON_RETRYABLE = {
    401: UNAUTHORIZED,
    400: json.dumps({"message": "corpo inválido"}),
    403: json.dumps({"message": "proibido"}),
    404: json.dumps({"message": "routine não existe"}),
    422: json.dumps({"message": "não processável"}),
}


@pytest.mark.parametrize("status", sorted(NON_RETRYABLE))
def test_non_retryable_4xx_to_undelivered(kit: Kit, receiver: Receiver, status: int) -> None:
    add_routine(kit, receiver)
    receiver.respond((status, NON_RETRYABLE[status]))
    result, task_dir = run_task(kit, exit_code=3)
    assert result.returncode == 3
    assert len(receiver.requests) == 1
    (line,) = records(task_dir, "undelivered.jsonl")
    assert line["http_status"] == status
    assert line["message"] == json.loads(NON_RETRYABLE[status])["message"]
    assert line["event"]["task_id"] == task_dir.name
    assert f"grokbot-kit redeliver {task_dir.name}" in result.stderr
    if status == 401:
        assert "grokbot-kit secret set bot-r-key" in result.stderr
    else:
        assert "secret set" not in result.stderr


@pytest.mark.parametrize("status", sorted(NON_RETRYABLE))
def test_non_retryable_4xx_to_undelivered_layer(home: Path, receiver: Receiver, observed: Any, status: int) -> None:
    receiver.respond((status, NON_RETRYABLE[status]))
    result = sinks.send("rotina", routine_sink(home, receiver.url), EVENT, BODY)
    assert not result.delivered
    assert result.http_status == status
    assert result.message == json.loads(NON_RETRYABLE[status])["message"]
    assert len(receiver.requests) == 1
    assert observed["sleeps"] == []
