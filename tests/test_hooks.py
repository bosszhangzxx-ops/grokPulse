"""Provas dos 9 hooks de progresso do Claude Code (patch local): registro por task, formato `[HOOK]`,
associação task_id/session_id/tool_use_id, redação de segredos e imunidade a erros (o hook nunca
pode falhar a task). A fronteira real (`emit --from claude` com o JSON do hook em stdin) também é provada."""

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

import pytest

from grokbot_kit import hooks, launch


def kit_exe() -> str:
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    return exe


def emit_process(
    task_dir: Path, stdin: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "GROKBOT_KIT_TASK_ID": "20261109T000000-hook-t1",
        "GROKBOT_KIT_TASK_DIR": str(task_dir),
        **(extra_env or {}),
    }
    return subprocess.run(
        [kit_exe(), "emit", "--from", "claude"],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )


def event(name: str, **extra: Any) -> dict[str, Any]:
    return {
        "session_id": "6ae1774a",
        "transcript_path": "/home/u/.claude/projects/p/6ae1774a.jsonl",
        "cwd": "/w",
        "hook_event_name": name,
        **extra,
    }


SAMPLES: dict[str, dict[str, Any]] = {
    "SessionStart": event("SessionStart", source="startup", model="mimo-v2.6-pro"),
    "PreToolUse": event("PreToolUse", tool_name="Bash", tool_input={"command": "npm test"}, tool_use_id="toolu_01A"),
    "PostToolUse": event(
        "PostToolUse",
        tool_name="Write",
        tool_input={"file_path": "/w/a.txt", "content": "conteúdo sensível"},
        tool_response={"filePath": "/w/a.txt", "type": "create"},
        tool_use_id="toolu_01B",
        duration_ms=12,
    ),
    "PostToolUseFailure": event(
        "PostToolUseFailure",
        tool_name="Bash",
        tool_input={"command": "npm test"},
        tool_use_id="toolu_01C",
        error="Exit code 1\nError: Cannot find module 'express'",
        is_interrupt=False,
        duration_ms=4187,
    ),
    "PostToolBatch": event(
        "PostToolBatch",
        tool_calls=[
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "/w/a"},
                "tool_use_id": "toolu_01D",
                "tool_response": "1\t...",
            },
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "/w/b"},
                "tool_use_id": "toolu_01E",
                "tool_response": "1\t...",
            },
        ],
    ),
    "TaskCreated": event(
        "TaskCreated", task_id="task-001", task_subject="Implement user authentication", task_description="Add login"
    ),
    "TaskCompleted": event("TaskCompleted", task_id="task-001", task_subject="Implement user authentication"),
    "Notification": event(
        "Notification",
        message="Claude needs your permission",
        title="Permission needed",
        notification_type="permission_prompt",
    ),
    "SessionEnd": event("SessionEnd", reason="other"),
}


# a configuração gerada cobre os 9 eventos + o PermissionRequest de sempre
def test_claude_settings_registers_all_hooks() -> None:
    settings = launch.claude_settings("/opt/gk/grokbot-kit", 60)
    events = settings["hooks"]
    assert set(hooks.EVENTS) <= set(events)
    for name in hooks.EVENTS:
        handlers = events[name][0]["hooks"]
        assert handlers[0]["command"] == "/opt/gk/grokbot-kit emit --from claude"
        assert handlers[0]["type"] == "command"
        if name in launch.NO_MATCHER_EVENTS:
            assert "matcher" not in events[name][0]
        else:
            assert events[name][0]["matcher"] == "*"
    permission = events["PermissionRequest"][0]["hooks"][0]
    assert permission["timeout"] == 120  # ask_wait + 60, inalterado
    session_end = events["SessionEnd"][0]["hooks"][0]
    assert session_end["timeout"] == launch.SESSION_END_TIMEOUT


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_handle_logs_each_event(tmp_path: Path, name: str) -> None:
    task_dir = tmp_path / "task"
    hooks.handle(SAMPLES[name], "20261109T000000-hook-t1", str(task_dir))
    line = (task_dir / "hooks.log").read_text(encoding="utf-8").strip()
    assert line.startswith(f"[HOOK] {name} | task_id=20261109T000000-hook-t1 | session_id=6ae1774a")
    assert "at=" in line
    record = json.loads((task_dir / "hooks-events.jsonl").read_text(encoding="utf-8"))
    assert record["schema"] == "grokbot-kit.hook/v1"
    assert record["event"] == name
    assert record["task_id"] == "20261109T000000-hook-t1"
    assert record["session_id"] == "6ae1774a"


def test_record_correlates_tool_use_id(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    hooks.handle(SAMPLES["PreToolUse"], "t", str(task_dir))
    hooks.handle(SAMPLES["PostToolUseFailure"], "t", str(task_dir))
    records = [json.loads(line) for line in (task_dir / "hooks-events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["tool_use_id"] for r in records] == ["toolu_01A", "toolu_01C"]
    assert [r["status"] for r in records if "status" in r] == ["failed"]
    line = (task_dir / "hooks.log").read_text(encoding="utf-8").splitlines()[1]
    assert "tool_use_id=toolu_01C" in line and "status=failed" in line and "error=" in line


def test_post_tool_batch_lists_calls(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    hooks.handle(SAMPLES["PostToolBatch"], "t", str(task_dir))
    record = json.loads((task_dir / "hooks-events.jsonl").read_text(encoding="utf-8"))
    assert record["count"] == 2
    assert record["tools"] == ["Read"]  # nomes únicos, na ordem da chamada
    assert record["tool_use_ids"] == ["toolu_01D", "toolu_01E"]
    assert "count=2" in (task_dir / "hooks.log").read_text(encoding="utf-8")


def test_task_events_keep_claude_task_id_apart(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    hooks.handle(SAMPLES["TaskCreated"], "gk-task", str(task_dir))
    record = json.loads((task_dir / "hooks-events.jsonl").read_text(encoding="utf-8"))
    assert record["task_id"] == "gk-task"
    assert record["claude_task_id"] == "task-001"
    line = (task_dir / "hooks.log").read_text(encoding="utf-8").strip()
    assert "task_id=gk-task" in line and "claude_task_id=task-001" in line


def test_never_logs_content_or_secrets(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    hooks.handle(SAMPLES["PostToolUse"], "t", str(task_dir))
    hooks.handle(
        event(
            "PreToolUse",
            tool_name="Bash",
            tool_input={"command": "curl -H 'Authorization: Bearer abcdef123456' https://x?api_key=SEGREDO99"},
            tool_use_id="toolu_02",
        ),
        "t",
        str(task_dir),
    )
    log = (task_dir / "hooks.log").read_text(encoding="utf-8")
    all_json = (task_dir / "hooks-events.jsonl").read_text(encoding="utf-8")
    assert "conteúdo sensível" not in log and "conteúdo sensível" not in all_json
    assert "abcdef123456" not in log and "SEGREDO99" not in all_json
    assert "<redacted>" in all_json


def test_handle_tolerates_malformed_input(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    for strange in (
        [],
        "texto",
        None,
        3,
        {"hook_event_name": "PreToolUse"},
        {"hook_event_name": "SessionStart", "source": {"x": 1}},
    ):
        hooks.handle(strange, "t", str(task_dir))  # não deve levantar
    assert (task_dir / "hooks.log").exists()


def test_concurrent_appends_stay_whole(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    threads = [
        threading.Thread(target=hooks.handle, args=(SAMPLES["PreToolUse"], "t", str(task_dir))) for _ in range(20)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    lines = (task_dir / "hooks.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 20
    assert all(line.startswith("[HOOK] PreToolUse | task_id=t | session_id=6ae1774a") for line in lines)
    records = (task_dir / "hooks-events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(records) == 20
    assert all(json.loads(r)["event"] == "PreToolUse" for r in records)


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_emit_dispatches_progress_event(tmp_path: Path, name: str) -> None:
    task_dir = tmp_path / "task"
    result = emit_process(task_dir, json.dumps(SAMPLES[name]))
    assert result.returncode == 0
    assert result.stdout == "{}"
    assert (task_dir / "hooks.log").read_text(encoding="utf-8").startswith(f"[HOOK] {name} ")


def test_emit_progress_event_outside_task_is_noop(tmp_path: Path) -> None:
    env = {**os.environ, "GROKBOT_KIT_TASK_ID": "", "GROKBOT_KIT_TASK_DIR": str(tmp_path / "x")}
    env.pop("GROKBOT_KIT_TASK_ID")
    result = subprocess.run(
        [kit_exe(), "emit", "--from", "claude"],
        input=json.dumps(SAMPLES["PreToolUse"]),
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0
    assert not (tmp_path / "x").exists()


def test_emit_permission_request_still_needs_input(tmp_path: Path) -> None:
    """Regressão: o PermissionRequest continua o único caminho de decisão (needs_input + espera)."""
    home = tmp_path / "home"
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    meta = {
        "task_id": "20261109T000000-hook-t1",
        "task_label": "hook",
        "target": "bot",
        "tool": "claude",
        "model": "m",
        "model_source": "user",
        "tier": "standard",
        "timeout_seconds": 600,
        "ask_wait_seconds": 0,
        "cwd": "/w",
        "started_at": "2026-11-09T00:00:00Z",
    }
    (task_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    config_dir = home / ".config" / "grokbot-kit"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[setup]\nversion = 1\ninstalled = ["claude"]\ndefault_cli = "claude"\n\n'
        '[cli.claude]\nbin = "/bin/claude"\nmodels = ["m"]\n\n[cli.claude.tiers]\nstandard = ["m"]\n\n'
        '[routes.bot]\nsinks = ["file"]\n\n[sinks.file]\ntype = "file"\n'
        f'path = "{tmp_path / "sink.jsonl"}"\n',
        encoding="utf-8",
    )
    stdin = json.dumps(
        {
            "session_id": "s1",
            "hook_event_name": "PermissionRequest",
            "tool_name": "Bash",
            "tool_input": {"command": "true"},
            "tool_use_id": "toolu_03",
        }
    )
    result = emit_process(task_dir, stdin, extra_env={"HOME": str(home)})
    assert result.returncode == 0
    assert "needs_input" in (task_dir / "events.jsonl").read_text(encoding="utf-8")
    assert not (task_dir / "hooks.log").exists()  # PermissionRequest não passa pelo registro de progresso


# ---------------------------------------------------------------------------- tempos e tokens da session


USAGE_A = {
    "input_tokens": 100,
    "output_tokens": 50,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 1000,
    "output_tokens_details": {"thinking_tokens": 42},
}
# o primeiro bloco de stream do mesmo message.id repete o id com o uso parcial (sem output ainda)
USAGE_A_PARTIAL = {"input_tokens": 100, "output_tokens": 0, "cache_read_input_tokens": 1000}
USAGE_B = {
    "input_tokens": 7,
    "output_tokens": 3,
    "cache_creation_input_tokens": 1,
    "cache_read_input_tokens": 2,
    "output_tokens_details": {"thinking_tokens": 2},
}


def assistant(mid: str, usage: dict[str, int]) -> dict[str, Any]:
    return {"type": "assistant", "message": {"id": mid, "usage": usage}}


def write_transcript(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def metrics_of(task_dir: Path) -> dict[str, Any]:
    return json.loads((task_dir / "session-metrics.json").read_text(encoding="utf-8"))


def records_of(task_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (task_dir / "hooks-events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_session_start_marks_started_at(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    hooks.handle(SAMPLES["SessionStart"], "t", str(task_dir))
    record = records_of(task_dir)[0]
    assert record["started_at"] == record["at"]
    metrics = metrics_of(task_dir)
    assert metrics["schema"] == "grokbot-kit.session-metrics/v1"
    assert metrics["sessions"]["6ae1774a"]["started_at"] == record["at"]
    assert f"started_at={record['at']}" in (task_dir / "hooks.log").read_text(encoding="utf-8")


def test_session_end_records_duration_and_tokens(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    transcript = tmp_path / "session.jsonl"
    # 3 linhas de uso para 2 mensagens: a msg_1 se repete por bloco de stream e conta uma vez (a mais cheia)
    write_transcript(
        transcript, [assistant("msg_1", USAGE_A_PARTIAL), assistant("msg_1", USAGE_A), assistant("msg_2", USAGE_B)]
    )
    hooks.handle(SAMPLES["SessionStart"], "t", str(task_dir))
    hooks.handle({**SAMPLES["SessionEnd"], "transcript_path": str(transcript)}, "t", str(task_dir))
    end = records_of(task_dir)[-1]
    assert end["ended_at"] == end["at"]
    assert end["duration_seconds"] >= 0
    assert end["tokens"] == {
        "input_tokens": 107,
        "output_tokens": 53,
        "cache_creation_input_tokens": 1,
        "cache_read_input_tokens": 1002,
        "total_tokens": 1163,
        "api_requests": 2,
        "thinking_tokens": 44,
        "source": "transcript",
    }
    session = metrics_of(task_dir)["sessions"]["6ae1774a"]
    assert session["ended_at"] == end["at"]
    assert session["duration_seconds"] == end["duration_seconds"]
    assert session["end_reason"] == "other"
    assert session["tokens"] == end["tokens"]
    line = (task_dir / "hooks.log").read_text(encoding="utf-8").splitlines()[-1]
    assert f"ended_at={end['at']}" in line
    assert "duration_seconds=" in line
    assert "input_tokens=107" in line and "total_tokens=1163" in line and "api_requests=2" in line


def test_session_end_without_usable_transcript_marks_unavailable(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    hooks.handle({**SAMPLES["SessionEnd"], "transcript_path": str(tmp_path / "sumiu.jsonl")}, "t", str(task_dir))
    hooks.handle({k: v for k, v in SAMPLES["SessionEnd"].items() if k != "transcript_path"}, "t", str(task_dir))
    first, second = records_of(task_dir)
    assert first["tokens"] == {"source": "unavailable", "reason": "transcript not readable"}
    assert second["tokens"] == {"source": "unavailable", "reason": "hook input has no transcript_path"}
    assert "input_tokens" not in first["tokens"] and "input_tokens" not in second["tokens"]
    assert "input_tokens=" not in (task_dir / "hooks.log").read_text(encoding="utf-8")


def test_task_window_tokens_are_the_delta_of_the_transcript(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    transcript = tmp_path / "session.jsonl"
    write_transcript(transcript, [assistant("msg_1", USAGE_A)])
    hooks.handle({**SAMPLES["TaskCreated"], "transcript_path": str(transcript)}, "gk-task", str(task_dir))
    with transcript.open("a", encoding="utf-8") as f:
        f.write(json.dumps(assistant("msg_2", USAGE_B)) + "\n")
    hooks.handle({**SAMPLES["TaskCompleted"], "transcript_path": str(transcript)}, "gk-task", str(task_dir))
    done = records_of(task_dir)[-1]
    assert done["tokens"] == {
        "input_tokens": 7,
        "output_tokens": 3,
        "cache_creation_input_tokens": 1,
        "cache_read_input_tokens": 2,
        "total_tokens": 13,
        "api_requests": 1,
        "thinking_tokens": 2,
        "source": "transcript-window-delta",
    }
    task = metrics_of(task_dir)["tasks"]["task-001"]
    assert task["tokens"] == done["tokens"]
    assert task["subject"] == "Implement user authentication"
    assert task["started_at"] and task["ended_at"] and task["duration_seconds"] >= 0
    assert "_snapshot" not in task
    # os tempos do record espelham os da task: é o record que o sync do Supabase upserta
    created = records_of(task_dir)[-2]
    assert created["started_at"] == task["started_at"]
    assert done["started_at"] == task["started_at"] and done["ended_at"] == task["ended_at"]
    assert done["duration_seconds"] == task["duration_seconds"] >= 0
    line = (task_dir / "hooks.log").read_text(encoding="utf-8").splitlines()[-1]
    assert "claude_task_id=task-001" in line and "total_tokens=13" in line


def test_task_completed_without_snapshot_has_no_tokens(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    transcript = tmp_path / "session.jsonl"
    write_transcript(transcript, [assistant("msg_1", USAGE_A)])
    hooks.handle({**SAMPLES["TaskCompleted"], "transcript_path": str(transcript)}, "t", str(task_dir))
    done = records_of(task_dir)[-1]
    assert "tokens" not in done
    assert "tokens" not in metrics_of(task_dir)["tasks"]["task-001"]


def test_usage_aggregation_skips_garbage_lines(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    transcript = tmp_path / "session.jsonl"
    write_transcript(transcript, [{"type": "user", "message": {"content": "oi"}}, assistant("msg_1", USAGE_B)])
    transcript.write_text("linha quebrada\n" + transcript.read_text(encoding="utf-8") + "{", encoding="utf-8")
    hooks.handle({**SAMPLES["SessionEnd"], "transcript_path": str(transcript)}, "t", str(task_dir))
    tokens = records_of(task_dir)[-1]["tokens"]
    assert tokens["total_tokens"] == 13 and tokens["api_requests"] == 1
    assert (task_dir / "hooks.log").exists()


def test_broken_metrics_file_never_breaks_the_event_record(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "session-metrics.json").write_text("{isso não é json", encoding="utf-8")
    hooks.handle(SAMPLES["SessionStart"], "t", str(task_dir))
    record = records_of(task_dir)[0]
    assert record["started_at"] == record["at"]
    assert metrics_of(task_dir)["schema"] == "grokbot-kit.session-metrics/v1"


def test_session_metrics_resumed_session_keeps_earliest_start(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    hooks.handle(SAMPLES["SessionStart"], "t", str(task_dir))
    first_started = metrics_of(task_dir)["sessions"]["6ae1774a"]["started_at"]
    hooks.handle({**SAMPLES["SessionStart"], "source": "resume"}, "t", str(task_dir))
    assert metrics_of(task_dir)["sessions"]["6ae1774a"]["started_at"] == first_started
