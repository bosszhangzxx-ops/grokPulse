"""Provas do `grokbot-kit gc --older-than <dur> [--dry-run]` (check C122; AC 101, door 17)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import Kit

from grokbot_kit import gc


def stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_task(home: Path, name: str, finished_days_ago: float | None, undelivered: str | None = None) -> Path:
    task_dir = home / ".grokbot-kit" / "tasks" / name
    task_dir.mkdir(parents=True)
    now = datetime.now(UTC)
    finished = None if finished_days_ago is None else stamp(now - timedelta(days=finished_days_ago))
    started = stamp(now - timedelta(days=(finished_days_ago or 0) + 1))
    meta = {"task_id": name, "started_at": started, "finished_at": finished, "exit_code": None}
    (task_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (task_dir / "out.jsonl").write_text("{}\n", encoding="utf-8")
    if undelivered is not None:
        (task_dir / "undelivered.jsonl").write_text(undelivered, encoding="utf-8")
    return task_dir


# C122 - AC 101, door 17
def test_predicate_dry_run_and_invalid_duration(fresh: Kit) -> None:
    old = make_task(fresh.home, "20260919T100000-velha-aaaaaa", 31)
    recent = make_task(fresh.home, "20260921T100000-recente-bbbbbb", 29)
    running = make_task(fresh.home, "20260901T100000-rodando-cccccc", None)
    pending = make_task(fresh.home, "20260918T100000-pendente-dddddd", 31, undelivered='{"dedupe_key": "x"}\n')
    kept = [recent, running, pending]

    dry = fresh.cli("gc", "--older-than", "30d", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert dry.stdout.split() == [str(old)]
    assert all(p.exists() for p in [old, *kept])

    result = fresh.cli("gc", "--older-than", "30d")
    assert result.returncode == 0, result.stderr
    assert str(old) in result.stdout
    assert not old.exists()
    assert all(p.exists() for p in kept)

    invalid = fresh.cli("gc", "--older-than", "xyz")
    assert invalid.returncode == 2
    assert "--older-than" in invalid.stderr
    assert all(p.exists() for p in kept)


def test_predicate_dry_run_and_invalid_duration_formats(fresh: Kit) -> None:
    for bad in ("30", "0d", "1h30m", "PT2H", "-1d"):
        result = fresh.cli("gc", "--older-than", bad)
        assert result.returncode == 2, bad
    assert fresh.cli("gc", "--older-than", "1s").returncode == 0


def test_predicate_dry_run_and_invalid_duration_empty_undelivered(fresh: Kit) -> None:
    emptied = make_task(fresh.home, "20260918T100000-entregue-eeeeee", 31, undelivered="")
    assert fresh.cli("gc", "--older-than", "30d").returncode == 0
    assert not emptied.exists()


NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("meta", "undelivered", "removable"),
    [
        ({"finished_at": "2026-09-19T11:59:59Z"}, None, True),
        ({"finished_at": "2026-09-21T12:00:00Z"}, None, False),
        ({"finished_at": None}, None, False),
        ({"finished_at": "2026-09-01T12:00:00Z"}, '{"dedupe_key": "k"}\n', False),
    ],
)
def test_predicate_dry_run_and_invalid_duration_layer(
    tmp_path: Path, meta: dict[str, object], undelivered: str | None, removable: bool
) -> None:
    (tmp_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if undelivered is not None:
        (tmp_path / "undelivered.jsonl").write_text(undelivered, encoding="utf-8")
    assert gc.removable(tmp_path, NOW, timedelta(days=30)) is removable


def test_predicate_dry_run_and_invalid_duration_layer_unreadable(tmp_path: Path) -> None:
    assert gc.removable(tmp_path, NOW, timedelta(days=30)) is False
    (tmp_path / "meta.json").write_text("{nao é json", encoding="utf-8")
    assert gc.removable(tmp_path, NOW, timedelta(days=30)) is False
