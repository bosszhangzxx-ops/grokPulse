"""Prova do formato do `task_id` e do layout do task dir (check C124; door 4)."""

import json
import re

import pytest
from conftest import Kit

LAYOUT = {"meta.json", "out.jsonl", "stderr.log", "events.jsonl", "kit.log", "sent"}


# C124 - door 4
@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_task_id_format_and_layout(kit: Kit, tool: str) -> None:
    label = f"layout-{tool}.v1"
    result = kit.run("--tool", tool, "--target", "bot-a", "--label", label, "--", "oi")
    assert result.returncode == 0, result.stderr
    task_dir = kit.task_dir()
    assert task_dir.parent == kit.home / ".grokbot-kit" / "tasks"
    assert re.fullmatch(rf"\d{{8}}T\d{{6}}-{re.escape(label)}-[0-9a-f]{{6}}", task_dir.name), task_dir.name

    names = {p.name for p in task_dir.iterdir()}
    assert names >= LAYOUT, names
    assert ("claude-settings.json" in names) is (tool == "claude")
    assert (task_dir / "sent").is_dir()
    assert all((task_dir / n).is_file() for n in LAYOUT - {"sent"})
    meta = json.loads((task_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["task_id"] == task_dir.name
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", meta["finished_at"])
