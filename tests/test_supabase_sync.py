"""Provas do sync best-effort para o Supabase: payload das linhas, upsert no PostgREST, silêncio
sem configuração e imunidade a falhas (o hook nunca pode falhar a task nem perder o log local)."""

import json
import urllib.error
from pathlib import Path
from typing import Any, Self

import pytest

from grokbot_kit import hooks, supabase_sync


class FakeResponse:
    def __init__(self, status: int = 201) -> None:
        self.status = status
        self.headers: dict[str, str] = {}

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeUrwlopen:
    """Captura os `Request` do PostgREST; pode falhar sob demanda."""

    def __init__(self, error: Exception | None = None) -> None:
        self.requests: list[Any] = []
        self.error = error

    def __call__(self, request: Any, timeout: float | None = None) -> FakeResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return FakeResponse()


def configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROKBOT_SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("GROKBOT_SUPABASE_ANON_KEY", "sb_publishable_fake_key_for_tests")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)


def sample(name: str, **extra: Any) -> dict[str, Any]:
    return {
        "session_id": "6ae1774a",
        "transcript_path": "/home/u/.claude/projects/p/6ae1774a.jsonl",
        "cwd": "/w",
        "hook_event_name": name,
        **extra,
    }


def body_of(request: Any) -> dict[str, Any]:
    return json.loads(request.data.decode("utf-8"))


def test_config_prefers_grokbot_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    assert supabase_sync._config() == ("https://proj.supabase.co", "sb_publishable_fake_key_for_tests")
    monkeypatch.setenv("SUPABASE_URL", "https://fallback.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "fallback_key")
    assert supabase_sync._config() == ("https://proj.supabase.co", "sb_publishable_fake_key_for_tests")
    monkeypatch.delenv("GROKBOT_SUPABASE_URL")
    monkeypatch.delenv("GROKBOT_SUPABASE_ANON_KEY")
    assert supabase_sync._config() == ("https://fallback.supabase.co", "fallback_key")


def test_config_is_none_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROKBOT_SUPABASE_URL", raising=False)
    monkeypatch.delenv("GROKBOT_SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    assert supabase_sync._config() is None


def test_session_end_row_maps_tokens_and_times() -> None:
    record = {
        "event": "SessionEnd",
        "at": "2026-11-09T07:03:08Z",
        "task_id": "t1",
        "session_id": "6ae1774a",
        "ended_at": "2026-11-09T07:03:08Z",
        "duration_seconds": 11.0,
        "reason": "other",
        "tokens": {
            "input_tokens": 11,
            "output_tokens": 5,
            "cache_creation_input_tokens": 2,
            "cache_read_input_tokens": 100,
            "total_tokens": 118,
            "api_requests": 1,
            "thinking_tokens": 3,
            "source": "transcript",
        },
    }
    row = supabase_sync._session_row(record, {"cwd": "/w", "model": "mimo-v2.6-pro"})
    assert row == {
        "session_id": "6ae1774a",
        "kit_task_id": "t1",
        "status": "ended",
        "updated_at": "2026-11-09T07:03:08Z",
        "ended_at": "2026-11-09T07:03:08Z",
        "duration_seconds": 11.0,
        "model": "mimo-v2.6-pro",
        "cwd": "/w",
        "input_tokens": 11,
        "output_tokens": 5,
        "cache_read_tokens": 100,
        "cache_creation_tokens": 2,
        "total_tokens": 118,
        "summary": {"api_requests": 1, "thinking_tokens": 3, "tokens_source": "transcript", "end_reason": "other"},
    }


def test_session_start_row_is_running_without_tokens() -> None:
    record = {
        "event": "SessionStart",
        "at": "2026-11-09T07:02:57Z",
        "task_id": "t1",
        "session_id": "6ae1774a",
        "started_at": "2026-11-09T07:02:57Z",
        "model": "mimo-v2.6-pro",
    }
    row = supabase_sync._session_row(record, {"cwd": "/w"})
    assert row["status"] == "running"
    assert row["started_at"] == "2026-11-09T07:02:57Z"
    assert "input_tokens" not in row and "summary" not in row
    assert supabase_sync._session_row({"event": "SessionStart", "at": "x"}, {}) == {}


def test_task_rows_map_window_delta_and_title() -> None:
    created = {
        "event": "TaskCreated",
        "at": "2026-11-09T07:03:00Z",
        "task_id": "t1",
        "session_id": "6ae1774a",
        "claude_task_id": "task-001",
        "subject": "Implement user authentication",
        "started_at": "2026-11-09T07:03:00Z",
    }
    row = supabase_sync._task_row(created, {"cwd": "/w"})
    assert row == {
        "session_id": "6ae1774a",
        "claude_task_id": "task-001",
        "kit_task_id": "t1",
        "status": "running",
        "updated_at": "2026-11-09T07:03:00Z",
        "started_at": "2026-11-09T07:03:00Z",
        "title": "Implement user authentication",
        "meta": {"cwd": "/w"},
    }
    completed = {
        **created,
        "event": "TaskCompleted",
        "at": "2026-11-09T07:03:09Z",
        "ended_at": "2026-11-09T07:03:09Z",
        "duration_seconds": 9.0,
        "tokens": {
            "input_tokens": 3,
            "output_tokens": 2,
            "cache_creation_input_tokens": 1,
            "cache_read_input_tokens": 4,
            "total_tokens": 10,
            "api_requests": 1,
            "thinking_tokens": 1,
            "source": "transcript-window-delta",
        },
    }
    row = supabase_sync._task_row(completed, {})
    assert row["status"] == "completed"
    assert row["ended_at"] == "2026-11-09T07:03:09Z"
    assert row["duration_seconds"] == 9.0
    assert row["input_tokens"] == 3 and row["output_tokens"] == 2 and row["total_tokens"] == 10
    assert row["meta"] == {
        "cache_read_tokens": 4,
        "cache_creation_tokens": 1,
        "api_requests": 1,
        "thinking_tokens": 1,
        "tokens_source": "transcript-window-delta",
    }
    assert supabase_sync._task_row({"event": "TaskCompleted", "at": "x"}, {}) == {}


def test_sync_posts_session_and_task_upserts(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    fake = FakeUrwlopen()
    monkeypatch.setattr("urllib.request.urlopen", fake)
    task_dir = "/tmp/nao-usado"
    supabase_sync.sync(
        {"event": "SessionStart", "at": "2026-11-09T07:02:57Z", "task_id": "t1", "session_id": "s1"}, {}, task_dir
    )
    supabase_sync.sync(
        {
            "event": "TaskCreated",
            "at": "2026-11-09T07:03:00Z",
            "task_id": "t1",
            "session_id": "s1",
            "claude_task_id": "task-001",
            "subject": "auth",
        },
        {},
        task_dir,
    )
    assert len(fake.requests) == 2
    session_request, task_request = fake.requests
    assert session_request.full_url == "https://proj.supabase.co/rest/v1/claude_sessions?on_conflict=session_id"
    assert (
        task_request.full_url == "https://proj.supabase.co/rest/v1/claude_tasks?on_conflict=session_id,claude_task_id"
    )
    for request in fake.requests:
        assert request.get_header("Apikey") == "sb_publishable_fake_key_for_tests"
        assert request.get_header("Authorization") == "Bearer sb_publishable_fake_key_for_tests"
        assert request.get_header("Prefer") == "resolution=merge-duplicates,return=minimal"
    assert body_of(session_request)["status"] == "running"
    assert body_of(task_request)["claude_task_id"] == "task-001"


def test_sync_ignores_tool_events_and_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    fake = FakeUrwlopen()
    monkeypatch.setattr("urllib.request.urlopen", fake)
    supabase_sync.sync({"event": "PreToolUse", "at": "x", "task_id": "t1", "session_id": "s1"}, {}, "/tmp/nao-usado")
    assert fake.requests == []
    monkeypatch.delenv("GROKBOT_SUPABASE_URL")
    monkeypatch.delenv("GROKBOT_SUPABASE_ANON_KEY")
    supabase_sync.sync({"event": "SessionStart", "at": "x", "task_id": "t1", "session_id": "s1"}, {}, "/tmp/nao-usado")
    assert fake.requests == []


def test_sync_failure_is_logged_and_never_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure(monkeypatch)
    fake = FakeUrwlopen(urllib.error.URLError("connection refused"))
    monkeypatch.setattr("urllib.request.urlopen", fake)
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    supabase_sync.sync({"event": "SessionEnd", "at": "x", "task_id": "t1", "session_id": "s1"}, {}, str(task_dir))
    log = (task_dir / "kit.log").read_text(encoding="utf-8")
    assert "supabase_sync: cannot upsert 'SessionEnd'" in log
    assert "URLError" in log


def test_handle_syncs_lifecycle_without_losing_local_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure(monkeypatch)
    fake = FakeUrwlopen(
        urllib.error.HTTPError("https://proj.supabase.co/rest/v1/claude_sessions", 401, "no", None, None)
    )
    monkeypatch.setattr("urllib.request.urlopen", fake)
    task_dir = tmp_path / "task"
    hooks.handle(sample("SessionStart", source="startup", model="mimo-v2.6-pro"), "t1", str(task_dir))
    hooks.handle(sample("SessionEnd", reason="other"), "t1", str(task_dir))
    events = [json.loads(line) for line in (task_dir / "hooks-events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["event"] for e in events] == ["SessionStart", "SessionEnd"]
    assert len(fake.requests) == 2  # a falha HTTP não desliga o próximo upsert
    log = (task_dir / "kit.log").read_text(encoding="utf-8")
    assert "supabase_sync: cannot upsert" in log
