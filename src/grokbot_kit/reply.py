"""`grokbot-kit reply <task_id> <request_id> allow|deny`: responde a um pedido do agente (needs-input-reply, door 3).

Grava `<task_dir>/replies/<request_id>.json` (door 1) de uma vez, só se ninguém gravou antes: nem outro `reply`, nem o
prazo do `emit`, que é quem espera o arquivo e passa a decisão à CLI. Sai com `0` gravada, `1` quando a tarefa ou o
pedido não aceita a resposta e `2` com uso inválido.
"""

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from grokbot_kit import config
from grokbot_kit.emit import read_reply, write_once

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _fail(code: int, message: str) -> int:
    print(f"grokbot-kit reply: {message}", file=sys.stderr)
    return code


def _request(task_dir: Path, request_id: str) -> dict[str, Any] | None:
    """O `needs_input` entregue com esse `request_id` em `events.jsonl`, ou `None`."""
    try:
        lines = (task_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    for line in lines:
        try:
            event = json.loads(line).get("event")
        except (ValueError, AttributeError):
            continue
        asked = event.get("needs_input") if isinstance(event, dict) and event.get("event") == "needs_input" else None
        if isinstance(asked, dict) and asked.get("request_id") == request_id:
            return asked
    return None


def _log(task_dir: Path, message: str) -> None:
    stamp = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    with (task_dir / "kit.log").open("a", encoding="utf-8") as f:
        f.write(f"{stamp} reply: {message}\n")


def _refusal(existing: dict[str, Any] | None, deadline: str) -> str:
    if existing is not None and existing.get("by") != "timeout":
        return f"already answered: {existing['decision']}"
    return f"no reply before {deadline}; the request was denied"


def reply(task_id: str, request_id: str, decision: str, message: str | None, by: str) -> int:
    if not REQUEST_ID_RE.match(request_id):
        return _fail(2, f"invalid request_id {request_id!r}: use only letters, digits, '.', '_', ':' and '-'")
    if message is not None and decision != "deny":
        return _fail(2, "--message goes only with deny")
    task_dir = config.tasks_dir() / task_id
    if not TASK_ID_RE.match(task_id) or not (task_dir / "meta.json").is_file():
        return _fail(1, f"task not found: {task_id}")
    meta = json.loads((task_dir / "meta.json").read_text(encoding="utf-8"))
    if meta.get("finished_at"):
        return _fail(1, f"task already finished: {task_id}")
    asked = _request(task_dir, request_id)
    if asked is None:
        return _fail(1, f"no needs_input with request_id {request_id} in task {task_id}")
    deadline = asked.get("reply_deadline")
    if not isinstance(deadline, str):
        return _fail(1, f"request {request_id} does not wait for a reply (the task runs with --ask-wait 0)")
    path = task_dir / "replies" / f"{request_id}.json"
    if path.exists():
        return _fail(1, _refusal(read_reply(path), deadline))
    if datetime.now(UTC) >= datetime.fromisoformat(deadline):
        return _fail(1, _refusal(None, deadline))
    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    body: dict[str, object] = {"decision": decision, "message": message, "by": by, "at": now}
    if not write_once(path, body):
        return _fail(1, _refusal(read_reply(path), deadline))
    _log(task_dir, f"{decision} for {request_id} by {by}")
    print(f"recorded {decision} for {request_id} (by {by})")
    return 0
