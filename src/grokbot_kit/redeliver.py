"""`grokbot-kit redeliver <task_id>`: reenvia o que ficou em `undelivered.jsonl` (AC 73 e 74, door 15).

Um único `redeliver` por task de cada vez: o dono cria `redeliver.lock` com `O_CREAT + O_EXCL` e grava o pid; os
outros esperam o lock sumir, e um lock cujo pid não existe mais é tomado.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from grokbot_kit import config, deliver, sinks

LOCK_WAIT = 120
LOCK_POLL = 0.1


def _alive(pid_text: str) -> bool:
    try:
        pid = int(pid_text)
    except ValueError:
        return True  # o dono ainda não gravou o pid
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _acquire(lock: Path) -> bool:
    deadline = time.monotonic() + LOCK_WAIT
    while True:
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            try:
                owner = lock.read_text(encoding="utf-8").strip()
            except FileNotFoundError:
                continue
            if owner and not _alive(owner):
                lock.unlink(missing_ok=True)
                continue
            if time.monotonic() >= deadline:
                return False
            time.sleep(LOCK_POLL)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()}\n")
        return True


def _redeliver(task_dir: Path, cfg: dict[str, Any]) -> int:
    path = task_dir / "undelivered.jsonl"
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        data = b""
    remaining: list[str] = []
    failed = 0
    for raw in data.decode("utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            line = json.loads(raw)
            name, event, key = line["sink"], line["event"], line["dedupe_key"]
        except (ValueError, KeyError, TypeError):
            print(f"grokbot-kit redeliver: skipping unreadable line in {path}", file=sys.stderr)
            remaining.append(raw)
            failed += 1
            continue
        sink = cfg.get("sinks", {}).get(name)
        if sink is None:
            result = sinks.Result(False, message=f"sink {name!r} is no longer in [sinks]")
            sink = {"type": line.get("type")}
        else:
            body, digest = deliver.serialize(event)
            result = sinks.send(name, sink, event, body)
            record = {
                "dedupe_key": key,
                "body_digest": digest,
                "event": event,
                "deliveries": [deliver.receipt(name, sink, result)],
                "redelivered": True,
            }
            sinks.append_line(task_dir / "events.jsonl", json.dumps(record, ensure_ascii=False).encode("utf-8"))
        if result.delivered:
            run_uuid = f" runUuid {result.run_uuid}" if result.run_uuid else ""
            print(f"{event['event']} -> {name}: delivered{run_uuid}")
            continue
        failed += 1
        remaining.append(json.dumps({**line, "http_status": result.http_status, "message": result.message}))
        status = f"HTTP {result.http_status}" if result.http_status is not None else "no HTTP response"
        print(
            f"grokbot-kit redeliver: {event['event']} -> {name}: not delivered ({status}: {result.message})",
            file=sys.stderr,
        )
    # um `emit` da task ainda em andamento pode ter acrescentado linhas enquanto reenviávamos
    try:
        appended = path.read_bytes()[len(data) :].decode("utf-8")
    except FileNotFoundError:
        appended = ""
    tmp = task_dir / "undelivered.jsonl.tmp"
    tmp.write_text("".join(line + "\n" for line in remaining) + appended, encoding="utf-8")
    os.replace(tmp, path)
    return 1 if failed else 0


def redeliver(task_id: str) -> int:
    task_dir = config.tasks_dir() / task_id
    if not task_id or "/" in task_id or task_id.startswith(".") or not task_dir.is_dir():
        print(f"grokbot-kit redeliver: task {task_id!r} not found in {config.tasks_dir()}", file=sys.stderr)
        return 2
    try:
        cfg = config.load()
    except config.ConfigError as e:
        print(f"grokbot-kit redeliver: {e}", file=sys.stderr)
        return 1
    lock = task_dir / "redeliver.lock"
    if not _acquire(lock):
        print(f"grokbot-kit redeliver: another redeliver still holds {lock}", file=sys.stderr)
        return 1
    try:
        return _redeliver(task_dir, cfg)
    finally:
        lock.unlink(missing_ok=True)
