"""`grokbot-kit gc --older-than <dur> [--dry-run]`: apaga task dirs terminados e antigos (AC 101, doors 4 e 17)."""

import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from grokbot_kit import config
from grokbot_kit.resolve import parse_duration


def removable(task_dir: Path, now: datetime, older_than: timedelta) -> bool:
    """Terminada há mais de `older_than` e sem `undelivered.jsonl` não vazio; na dúvida, preserva."""
    try:
        meta = json.loads((task_dir / "meta.json").read_text(encoding="utf-8"))
        old = now - datetime.fromisoformat(meta["finished_at"]) > older_than
    except (OSError, ValueError, KeyError, TypeError):
        return False
    undelivered = task_dir / "undelivered.jsonl"
    return old and not (undelivered.exists() and undelivered.stat().st_size > 0)


def gc(older_than: str, dry_run: bool) -> int:
    try:
        seconds = parse_duration(older_than)
    except ValueError as e:
        print(f"grokbot-kit gc: --older-than: {e}", file=sys.stderr)
        return 2
    root = config.tasks_dir()
    now = datetime.now(UTC)
    for task_dir in sorted(root.iterdir()) if root.is_dir() else []:
        if task_dir.is_dir() and removable(task_dir, now, timedelta(seconds=seconds)):
            if not dry_run:
                shutil.rmtree(task_dir)
            print(task_dir)
    return 0
