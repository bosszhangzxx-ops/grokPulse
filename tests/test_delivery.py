"""Prova do dedupe por arquivo do roteador (check C97; door 5)."""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from grokbot_kit import deliver


def file_route(sink: Path) -> dict[str, Any]:
    return {"routes": {"bot-a": {"sinks": ["arquivo"]}}, "sinks": {"arquivo": {"type": "file", "path": str(sink)}}}


def event(task_id: str) -> dict[str, Any]:
    return {"schema": "grokbot-kit.event/v1", "event": "needs_input", "status": "permission", "task_id": task_id}


# C97 - door 5
def test_dedupe_key_format_and_excl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    sink = tmp_path / "sink.jsonl"
    opened: list[tuple[str, int]] = []
    real_open = os.open

    def spy(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        opened.append((str(path), flags))
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(deliver.os, "open", spy)
    cfg = file_route(sink)
    deliver.deliver(task_dir, cfg, "bot-a", event("20261020T120000-tarefa-a1b2c3"), "perm-1")
    deliver.deliver(task_dir, cfg, "bot-a", event("20261020T120000-tarefa-a1b2c3"), "perm-1")

    key = "20261020T120000-tarefa-a1b2c3:needs_input:perm-1"
    assert sorted(p.name for p in (task_dir / "sent").iterdir()) == [key]
    assert len(sink.read_text(encoding="utf-8").splitlines()) == 1, "a segunda criação entregou de novo"
    events = [json.loads(line) for line in (task_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["dedupe_key"] for e in events] == [key]
    receipts = [flags for path, flags in opened if path == str(task_dir / "sent" / key)]
    assert len(receipts) == 2
    assert all(flags & os.O_CREAT and flags & os.O_EXCL for flags in receipts)


def test_dedupe_key_format_and_excl_existing_receipt_blocks_delivery(tmp_path: Path) -> None:
    """`sent/<chave>` criado por outro processo antes: a entrega não acontece."""
    task_dir = tmp_path / "task"
    (task_dir / "sent").mkdir(parents=True)
    (task_dir / "sent" / "t-1:completed:terminal").write_text("{}", encoding="utf-8")
    sink = tmp_path / "sink.jsonl"
    deliver.deliver(task_dir, file_route(sink), "bot-a", {**event("t-1"), "event": "completed"}, "terminal")
    assert not sink.exists()
    assert not (task_dir / "events.jsonl").exists()


def test_dedupe_key_format_and_excl_distinct_keys_deliver_each(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    sink = tmp_path / "sink.jsonl"
    cfg = file_route(sink)
    deliver.deliver(task_dir, cfg, "bot-a", event("t-1"), "perm-1")
    deliver.deliver(task_dir, cfg, "bot-a", event("t-1"), "perm-2")
    deliver.deliver(task_dir, cfg, "bot-a", {**event("t-1"), "event": "completed"}, "terminal")
    assert sorted(p.name for p in (task_dir / "sent").iterdir()) == [
        "t-1:completed:terminal",
        "t-1:needs_input:perm-1",
        "t-1:needs_input:perm-2",
    ]
    assert len(sink.read_text(encoding="utf-8").splitlines()) == 3
