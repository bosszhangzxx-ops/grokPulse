"""Roteador: entrega um evento aos sinks da rota do `target`, uma vez por chave de dedupe (door 5).

Os registros no task dir seguem a door 15: `events.jsonl` com o `body_digest` e o recibo de cada sink,
`sent/<chave>` com os mesmos recibos, e uma linha de `undelivered.jsonl` por sink que falhou.
"""

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from grokbot_kit import sinks


def _append(path: Path, line: str) -> None:
    sinks.append_line(path, line.encode("utf-8"))


def serialize(event: dict[str, Any]) -> tuple[bytes, str]:
    """O corpo de cada entrega (um objeto JSON em UTF-8, AC 67) e o seu `body_digest`."""
    body = json.dumps(event, ensure_ascii=False).encode("utf-8")
    return body, "sha256:" + hashlib.sha256(body).hexdigest()


def receipt(name: str, sink: dict[str, Any], result: sinks.Result) -> dict[str, Any]:
    return {
        "sink": name,
        "type": sink.get("type"),
        "delivered": result.delivered,
        "http_status": result.http_status,
        "run_uuid": result.run_uuid,
    }


def record_undelivered(
    task_dir: Path, key: str, name: str, sink: dict[str, Any], result: sinks.Result, event: dict[str, Any]
) -> None:
    line = {
        "dedupe_key": key,
        "sink": name,
        "type": sink.get("type"),
        "http_status": result.http_status,
        "message": result.message,
        "event": event,
    }
    _append(task_dir / "undelivered.jsonl", json.dumps(line, ensure_ascii=False))


def warn_undelivered(event: dict[str, Any], name: str, sink: dict[str, Any], result: sinks.Result) -> None:
    status = f"HTTP {result.http_status}" if result.http_status is not None else "no HTTP response"
    hint = f"; retry with: grokbot-kit redeliver {event['task_id']}"
    if result.http_status == 401 and sink.get("key_secret"):
        hint += f"; if the key is wrong: grokbot-kit secret set {sink['key_secret']}"
    print(
        f"grokbot-kit: {event['event']} event not delivered to sink {name} ({status}: {result.message}){hint}",
        file=sys.stderr,
    )


def deliver(task_dir: Path, config: dict[str, Any], target: str, event: dict[str, Any], discriminator: str) -> None:
    key = f"{event['task_id']}:{event['event']}:{discriminator}"
    sent = task_dir / "sent"
    sent.mkdir(exist_ok=True)
    try:
        receipt_fd = os.open(sent / key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    body, digest = serialize(event)
    deliveries = []
    for name in config["routes"][target]["sinks"]:
        sink = config["sinks"][name]
        result = sinks.send(name, sink, event, body)
        deliveries.append(receipt(name, sink, result))
        if not result.delivered:
            record_undelivered(task_dir, key, name, sink, result, event)
            warn_undelivered(event, name, sink, result)
    with os.fdopen(receipt_fd, "w", encoding="utf-8") as f:
        json.dump({"body_digest": digest, "deliveries": deliveries}, f)
    record = {"dedupe_key": key, "body_digest": digest, "event": event, "deliveries": deliveries}
    _append(task_dir / "events.jsonl", json.dumps(record, ensure_ascii=False))
