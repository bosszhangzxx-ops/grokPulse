"""Entrega de um evento a um sink: `grokbot-routine`, `file`, `ntfy` e `slack` (AC 66-72, 120-124, AD-021).

Todo texto que sai daqui (`message`) passa por `_redact`: o valor de cada segredo usado na entrega vira
`<secret:<nome>>`, e uma exceção que não vem do HTTP nunca leva a URL junto (AC 70).
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, NamedTuple

from grokbot_kit import config

RETRY_WAITS = (1, 4)
ATTEMPT_TIMEOUT = 10
MESSAGE_LIMIT = 500


# `NamedTuple` e não `dataclass`: `dataclasses` importa `copy`, que tenta `org.python.core` no caminho do `emit` (door 6).
class Result(NamedTuple):
    delivered: bool
    http_status: int | None = None
    run_uuid: str | None = None
    message: str = ""


class _Response(NamedTuple):
    status: int | None
    text: str
    error: str = ""


def _redact(text: str, secrets: dict[str, str]) -> str:
    for name, value in secrets.items():
        if value:
            text = text.replace(value, f"<secret:{name}>")
    return text[:MESSAGE_LIMIT]


def _post(url: str, headers: dict[str, str], data: bytes) -> _Response:
    from grokbot_kit import __version__

    if not url.startswith(("https://", "http://")):
        return _Response(None, "", "invalid URL")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("User-Agent", f"grokbot-kit/{__version__}")
    for name, value in headers.items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=ATTEMPT_TIMEOUT) as response:
            return _Response(response.status, response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        return _Response(e.code, e.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, OSError) as e:
        reason = e.reason if isinstance(e, urllib.error.URLError) else e
        return _Response(None, "", f"connection failed: {reason}")
    except ValueError:
        return _Response(None, "", "invalid URL")


def _retryable(response: _Response) -> bool:
    return response.status is None or response.status == 429 or 500 <= response.status <= 599


def _post_with_retry(url: str, headers: dict[str, str], data: bytes) -> _Response:
    response = _post(url, headers, data)
    for wait in RETRY_WAITS:
        if not _retryable(response) or response.error == "invalid URL":
            break
        time.sleep(wait)
        response = _post(url, headers, data)
    return response


def _message(response: _Response) -> str:
    if response.error:
        return response.error
    try:
        parsed = json.loads(response.text)
    except ValueError:
        return response.text.strip()
    if isinstance(parsed, dict) and isinstance(parsed.get("message"), str):
        return str(parsed["message"])
    return response.text.strip()


def _routine(sink: dict[str, Any], body: bytes, secrets: dict[str, str]) -> Result:
    url = secrets[sink["url_secret"]] = config.read_secret(sink["url_secret"])
    key = secrets[sink["key_secret"]] = config.read_secret(sink["key_secret"])
    headers = {**sink.get("headers", {}), "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    response = _post_with_retry(url, headers, body)
    if response.status is not None and 200 <= response.status <= 299:
        try:
            receipt = json.loads(response.text)
        except ValueError:
            receipt = None
        run_uuid = receipt.get("runUuid") if isinstance(receipt, dict) else None
        if isinstance(receipt, dict) and receipt.get("success") is True and isinstance(run_uuid, str) and run_uuid:
            return Result(True, response.status, run_uuid)
        return Result(False, response.status, message=f"response without success/runUuid: {_message(response)}")
    return Result(False, response.status, message=_message(response))


def _http_result(response: _Response, delivered: bool) -> Result:
    if delivered:
        return Result(True, response.status)
    return Result(False, response.status, message=_message(response))


def _ntfy(sink: dict[str, Any], event: dict[str, Any], secrets: dict[str, str]) -> Result:
    label = event.get("task_label") or "test"
    headers = {"Title": f"grokbot-kit {event['event']} {event['status']} {label}"}
    if sink.get("token_secret"):
        token = secrets[sink["token_secret"]] = config.read_secret(sink["token_secret"])
        headers["Authorization"] = f"Bearer {token}"
    text = event.get("summary") or f"{event['event']} {event['status']}"
    response = _post_with_retry(sink["topic_url"], headers, text.encode("utf-8"))
    return _http_result(response, response.status is not None and 200 <= response.status <= 299)


def _slack(sink: dict[str, Any], event: dict[str, Any], secrets: dict[str, str]) -> Result:
    url = secrets[sink["webhook_secret"]] = config.read_secret(sink["webhook_secret"])
    label = event.get("task_label") or "test"
    text = f"[grokbot-kit] {event['event']}/{event['status']} {label} ({event['target']})\n{event.get('summary') or ''}"
    data = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    response = _post_with_retry(url, {"Content-Type": "application/json"}, data)
    return _http_result(response, response.status == 200 and response.text == "ok")


def append_line(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "ab") as f:
        f.write(data + b"\n")


def send(name: str, sink: dict[str, Any], event: dict[str, Any], body: bytes) -> Result:
    """Entrega `event` (serializado em `body`, AC 67) ao sink `name`; nunca levanta exceção."""
    secrets: dict[str, str] = {}
    kind = sink.get("type")
    try:
        if kind == "grokbot-routine":
            result = _routine(sink, body, secrets)
        elif kind == "file":
            try:
                append_line(Path(os.path.expanduser(sink["path"])), body)
                result = Result(True)
            except OSError as e:
                result = Result(False, message=str(e))
        elif kind == "ntfy":
            result = _ntfy(sink, event, secrets)
        elif kind == "slack":
            result = _slack(sink, event, secrets)
        else:
            result = Result(False, message=f"unknown sink type {kind!r}")
    except config.ConfigError as e:
        result = Result(False, message=str(e))
    except KeyError as e:
        result = Result(False, message=f"sink {name!r} is missing key {e}")
    return Result(result.delivered, result.http_status, result.run_uuid, _redact(result.message, secrets))
