"""Provas do payload do evento (checks C56-C62; AC 49-53, door 2).

Cada regra é provada na própria camada (`grokbot_kit.payload`, `grokbot_kit.terminal`) e na fronteira (subprocesso
`grokbot-kit run` com a CLI falsa e o sink `file`).
"""

import itertools
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from conftest import MODELS, Kit

from grokbot_kit import payload, terminal
from grokbot_kit.terminal import AgentOutput

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "grokbot_kit" / "assets" / "event.v1.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)

# AC 49: os 13 campos não nulos de todo evento de task
REQUIRED_NON_NULL = (
    "schema",
    "event",
    "status",
    "task_id",
    "task_label",
    "target",
    "tool",
    "model",
    "model_source",
    "cwd",
    "output_file",
    "log_file",
    "timestamp",
)

# door 2, literal
DOOR_2_FIELDS = {
    "schema",
    "event",
    "status",
    "task_id",
    "task_label",
    "target",
    "tool",
    "model",
    "model_source",
    "tier",
    "session_id",
    "cwd",
    "repo",
    "exit_code",
    "exit_reason",
    "summary",
    "needs_input",
    "resume_hint",
    "output_file",
    "transcript_path",
    "log_file",
    "started_at",
    "timestamp",
}
# door 5 da feature plugins: aditivos a `grokbot-kit.event/v1`, `null` fora de tarefa de plugin
DOOR_5_FIELDS = {"plugin", "result"}
# door 5 da model-setup-docs: aditivo, `[]` sem fallback e `null` só no evento `test`
MODEL_SETUP_FIELDS = {"model_fallbacks"}
EVENT_FIELDS = DOOR_2_FIELDS | DOOR_5_FIELDS | MODEL_SETUP_FIELDS

DOOR_2_TEST_NULLS = (
    "task_id",
    "task_label",
    "tool",
    "model",
    "model_source",
    "output_file",
    "log_file",
    "started_at",
)

# AC 53
EXIT_REASONS = {
    "success",
    "permission_denied",
    "agent_error",
    "nonzero_exit",
    "timeout",
    "interrupted",
    "needs_input",
    "result_invalid",  # door 5 da feature plugins
}

RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)$")

CLAUDE_OK = json.dumps({"type": "result", "is_error": False, "result": "feito", "permission_denials": []})
OPENCODE_OK = json.dumps({"type": "text", "part": {"type": "text", "text": "feito"}}) + "\n"
CODEX_OK = json.dumps({"type": "turn.completed"})
OK_OUTPUT = {"claude": CLAUDE_OK, "opencode": OPENCODE_OK, "codex": CODEX_OK}

CLAUDE_SESSION = "6ae1774a-3c98-4d8d-bb1f-57f86d863508"
OPENCODE_SESSION = "ses_eaaff8739ffe2xV7p6qXJ06WAN"
CODEX_SESSION = "01a15500-7471-7222-a88d-27c99f1af68a"
WITH_SESSION = {
    "claude": json.dumps(
        {"type": "result", "is_error": False, "result": "feito", "permission_denials": [], "session_id": CLAUDE_SESSION}
    ),
    "opencode": "\n".join(
        json.dumps(e)
        for e in (
            {"type": "step_start", "sessionID": OPENCODE_SESSION, "part": {"type": "step-start"}},
            {"type": "text", "sessionID": OPENCODE_SESSION, "part": {"type": "text", "text": "feito"}},
        )
    )
    + "\n",
    "codex": "\n".join(
        json.dumps(e)
        for e in (
            {"type": "thread.started", "thread_id": CODEX_SESSION},
            {"type": "turn.started"},
            {"type": "turn.completed"},
        )
    ),
}


def run_task(kit: Kit, tool: str, *args: str, **fake: str) -> dict[str, Any]:
    result = kit.run("--tool", tool, "--target", "bot-a", "--label", "p", *args, "--", "faça", **fake)
    events = kit.sink_events()
    assert len(events) == 1, (events, result.stderr)
    return events[0]


def task_meta(task_dir: Path, tool: str = "claude") -> dict[str, Any]:
    meta: dict[str, Any] = {
        "task_id": task_dir.name,
        "task_label": "p",
        "target": "bot-a",
        "tool": tool,
        "model": "sonnet",
        "model_source": "tier",
        "tier": "standard",
        "cwd": str(task_dir),
        "started_at": "2026-10-19T12:00:00Z",
    }
    if tool == "codex":
        meta["codex_home"] = "/srv/codex-home"
    return meta


def git(cwd: Path, *args: str) -> str:
    cmd = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(cwd), *args]
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()


def make_repo(path: Path) -> str:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    (path / "a.txt").write_text("a\n", encoding="utf-8")
    git(path, "add", "a.txt")
    git(path, "commit", "-q", "-m", "a")
    return git(path, "rev-parse", "HEAD")


# C56 - AC 49
OUTCOMES = {
    "ok": {},
    "denied": {"FAKE_NEEDS_INPUT": "1"},
    "nonzero": {"FAKE_EXIT": "3"},
}


@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
@pytest.mark.parametrize("case", sorted(OUTCOMES))
@pytest.mark.parametrize("model_args", [(), ("--model", "{model}")])
def test_task_event_required_fields_and_schema_cli(kit: Kit, tool: str, case: str, model_args: tuple[str, ...]) -> None:
    args = tuple(a.format(model=MODELS[tool]) for a in model_args)
    event = run_task(kit, tool, *args, FAKE_STDOUT=OK_OUTPUT[tool], **OUTCOMES[case])
    assert event["event"] != "test"
    for field in REQUIRED_NON_NULL:
        assert event[field] is not None, field
    VALIDATOR.validate(event)


def test_task_event_required_fields_and_schema_layer(tmp_path: Path) -> None:
    meta = task_meta(tmp_path)
    terminal_event = payload.task_event(
        meta, tmp_path, event="completed", status="ok", exit_reason="success", exit_code=0, summary="feito"
    )
    asked = payload.needs_input_event(
        meta, tmp_path, kind="permission", tool_name="Bash", detail="touch x", request_id="r-1"
    )
    for event in (terminal_event, asked):
        for field in REQUIRED_NON_NULL:
            assert event[field] is not None, field
        VALIDATOR.validate(event)


@pytest.mark.parametrize("field", REQUIRED_NON_NULL)
def test_task_event_required_fields_and_schema_rejects_null(tmp_path: Path, field: str) -> None:
    event = payload.task_event(
        task_meta(tmp_path), tmp_path, event="completed", status="ok", exit_reason="success", exit_code=0, summary=""
    )
    event[field] = None
    assert not VALIDATOR.is_valid(event)


# C57 - door 2
def test_schema_matches_door_2() -> None:
    props = SCHEMA["properties"]
    assert set(props) == EVENT_FIELDS
    assert set(SCHEMA["required"]) == EVENT_FIELDS
    assert SCHEMA["additionalProperties"] is False
    assert props["schema"] == {"const": "grokbot-kit.event/v1"}
    assert set(props["event"]["enum"]) == {"completed", "error", "timeout", "needs_input", "test"}
    assert len(props["event"]["enum"]) == 5
    assert set(props["status"]["enum"]) == {
        "ok",
        "denied",
        "failed",
        "interrupted",
        "timeout",
        "permission",
        "question",
        "test",
    }
    assert len(props["status"]["enum"]) == 8
    assert [v for v in props["model_source"]["enum"] if v is not None] == ["user", "tier", "default"]
    repo = next(s for s in props["repo"]["oneOf"] if s.get("type") == "object")
    assert set(repo["properties"]) == {"root", "branch", "head"}
    needs_input = next(s for s in props["needs_input"]["oneOf"] if s.get("type") == "object")
    assert set(needs_input["properties"]) == {"kind", "tool_name", "detail", "request_id", "reply_deadline"}


def test_schema_matches_door_2_nullable_only_for_test(tmp_path: Path) -> None:
    probe = {
        "schema": "grokbot-kit.event/v1",
        "event": "test",
        "status": "test",
        "target": "bot-a",
        "tier": None,
        "session_id": None,
        "cwd": "/",
        "repo": None,
        "exit_code": None,
        "exit_reason": None,
        "summary": "",
        "needs_input": None,
        "resume_hint": None,
        "transcript_path": None,
        "timestamp": "2026-10-19T12:00:00Z",
        **dict.fromkeys(DOOR_2_TEST_NULLS),
        **dict.fromkeys(DOOR_5_FIELDS),
        **dict.fromkeys(MODEL_SETUP_FIELDS),
    }
    VALIDATOR.validate(probe)
    task = payload.task_event(
        task_meta(tmp_path), tmp_path, event="completed", status="ok", exit_reason="success", exit_code=0, summary=""
    )
    VALIDATOR.validate(task)
    for field in DOOR_2_TEST_NULLS:
        assert not VALIDATOR.is_valid({**task, field: None}), field


# C58 - AC 50
def test_repo_fields_inside_and_outside_git_cli(kit: Kit, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    head = make_repo(repo)
    (repo / "sub").mkdir()
    event = run_task(kit, "claude", "--cwd", str(repo / "sub"), FAKE_STDOUT=CLAUDE_OK)
    assert event["repo"] == {"root": str(repo.resolve()), "branch": "main", "head": head}


def test_repo_fields_inside_and_outside_git_cli_outside(kit: Kit, tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    event = run_task(kit, "claude", "--cwd", str(plain), FAKE_STDOUT=CLAUDE_OK)
    assert event["repo"] is None


def test_repo_fields_inside_and_outside_git_layer(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    head = make_repo(repo)
    assert payload.repo_info(repo) == {"root": str(repo.resolve()), "branch": "main", "head": head}
    git(repo, "checkout", "-q", "--detach")
    assert payload.repo_info(repo) == {"root": str(repo.resolve()), "branch": None, "head": head}
    plain = tmp_path / "plain"
    plain.mkdir()
    assert payload.repo_info(plain) is None


# C59 - AC 51
def expected_hint(kit: Kit, tool: str) -> str:
    if tool == "claude":
        return f"claude -p --resume {CLAUDE_SESSION}"
    if tool == "opencode":
        return f"opencode run -s {OPENCODE_SESSION}"
    return f"CODEX_HOME={kit.home / '.grokbot-kit' / 'codex-home'} codex exec resume {CODEX_SESSION}"


SESSION_IDS = {"claude": CLAUDE_SESSION, "opencode": OPENCODE_SESSION, "codex": CODEX_SESSION}


@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_resume_hint_per_tool_cli(kit: Kit, tool: str) -> None:
    event = run_task(kit, tool, FAKE_STDOUT=WITH_SESSION[tool])
    assert event["session_id"] == SESSION_IDS[tool]
    assert event["resume_hint"] == expected_hint(kit, tool)


@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_resume_hint_per_tool_cli_without_session(kit: Kit, tool: str) -> None:
    event = run_task(kit, tool, FAKE_STDOUT=OK_OUTPUT[tool])
    assert event["session_id"] is None
    assert event["resume_hint"] is None


@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_resume_hint_per_tool_layer(tmp_path: Path, tool: str) -> None:
    (tmp_path / "out.jsonl").write_text(WITH_SESSION[tool], encoding="utf-8")
    assert terminal.read_output(tool, tmp_path).session_id == SESSION_IDS[tool]
    assert payload.resume_hint("claude", "abc", None) == "claude -p --resume abc"
    assert payload.resume_hint("opencode", "ses_1", None) == "opencode run -s ses_1"
    assert payload.resume_hint("codex", "t1", "/srv/codex-home") == "CODEX_HOME=/srv/codex-home codex exec resume t1"
    assert payload.resume_hint(tool, None, "/srv/codex-home") is None


# C60 - AC 52
def test_transcript_path_from_hook_cli(kit: Kit) -> None:
    transcript = "/home/u/.claude/projects/p/6ae1774a.jsonl"
    event = run_task(kit, "claude", FAKE_STDOUT=CLAUDE_OK, FAKE_NEEDS_INPUT=json.dumps({"transcript_path": transcript}))
    assert event["transcript_path"] == transcript


def test_transcript_path_from_hook_cli_through_emit(kit: Kit) -> None:
    # de ponta a ponta: o hook entrega o `transcript_path` ao `grokbot-kit emit`, que o grava no `needs_input`
    transcript = "/home/u/.claude/projects/p/6ae1774a.jsonl"
    hook = {"hook_event_name": "PermissionRequest", "tool_name": "Bash", "tool_input": {"command": "touch x"}}
    result = kit.run(
        "--tool", "claude", "--target", "bot-a", "--label", "p", "--ask-wait", "0", "--", "faça",
        FAKE_STDOUT=CLAUDE_OK, FAKE_EMIT=json.dumps([{**hook, "session_id": "s1", "transcript_path": transcript}]),
    )  # fmt: skip
    terminal_events = [e for e in kit.sink_events() if e["event"] != "needs_input"]
    assert len(terminal_events) == 1, result.stderr
    assert terminal_events[0]["transcript_path"] == transcript


def test_transcript_path_from_hook_cli_without_hook(kit: Kit) -> None:
    event = run_task(kit, "claude", FAKE_STDOUT=CLAUDE_OK)
    assert event["transcript_path"] is None


def test_transcript_path_from_hook_layer(tmp_path: Path) -> None:
    meta = task_meta(tmp_path)
    asked = payload.needs_input_event(
        meta, tmp_path, kind="permission", tool_name="Bash", detail=None, transcript_path="/t.jsonl", request_id="r-1"
    )
    assert asked["transcript_path"] == "/t.jsonl"
    plain = payload.task_event(
        meta, tmp_path, event="completed", status="ok", exit_reason="success", exit_code=0, summary=""
    )
    assert plain["transcript_path"] is None


# C61 - AC 53
def test_exit_reason_enum_and_needs_input_mapping_layer(tmp_path: Path) -> None:
    assert set(payload.EXIT_REASONS) == EXIT_REASONS
    assert {v for v in SCHEMA["properties"]["exit_reason"]["enum"] if v is not None} == EXIT_REASONS
    seen = set()
    for code, error, denied, needs_input in itertools.product((0, 1, 3, 127), (False, True), (False, True), (0, 1)):
        output = AgentOutput(error=error, permission_denied=denied, summary="")
        seen.add(terminal.classify(code, output, needs_input=bool(needs_input))[2])
    assert seen <= EXIT_REASONS
    meta = task_meta(tmp_path)
    for kind in ("permission", "question"):
        asked = payload.needs_input_event(meta, tmp_path, kind=kind, tool_name=None, detail=None, request_id="r-1")
        assert asked["event"] == "needs_input"
        assert asked["status"] == kind
        assert asked["exit_reason"] == "needs_input"
        VALIDATOR.validate(asked)
    with pytest.raises(ValueError):
        payload.task_event(meta, tmp_path, event="completed", status="ok", exit_reason="done", exit_code=0, summary="")
    with pytest.raises(ValueError):
        payload.task_event(
            meta, tmp_path, event="needs_input", status="permission", exit_reason="success", exit_code=None, summary=""
        )


@pytest.mark.parametrize("case", sorted(OUTCOMES))
def test_exit_reason_enum_and_needs_input_mapping_cli(kit: Kit, case: str) -> None:
    event = run_task(kit, "opencode", FAKE_STDOUT=OPENCODE_OK, **OUTCOMES[case])
    assert event["exit_reason"] in EXIT_REASONS


# C62 - door 2
@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_timestamps_rfc3339_utc_cli(kit: Kit, tool: str) -> None:
    event = run_task(kit, tool, FAKE_STDOUT=OK_OUTPUT[tool])
    for field in ("started_at", "timestamp"):
        value = event[field]
        assert RFC3339_UTC.match(value), (field, value)
        assert datetime.fromisoformat(value).utcoffset() == timedelta(0)


def test_timestamps_rfc3339_utc_layer(tmp_path: Path) -> None:
    brt = timezone(timedelta(hours=-3))
    assert payload.rfc3339(datetime(2026, 10, 19, 9, 0, 5, tzinfo=brt)) == "2026-10-19T12:00:05Z"
    assert payload.rfc3339(datetime(2026, 10, 19, 12, 0, 5, tzinfo=UTC)) == "2026-10-19T12:00:05Z"
    asked = payload.needs_input_event(
        task_meta(tmp_path), tmp_path, kind="question", tool_name=None, detail=None, request_id="r-1"
    )
    assert RFC3339_UTC.match(asked["timestamp"])


# C45 - AC 46
def test_no_plugin_fields_null(kit: Kit, tmp_path: Path) -> None:
    event = payload.task_event(
        task_meta(tmp_path), tmp_path, event="completed", status="ok", exit_reason="success", exit_code=0, summary=""
    )
    assert event["plugin"] is None
    assert event["result"] is None
    assert payload.route_test_event("bot-a")["plugin"] is None
    assert payload.route_test_event("bot-a")["result"] is None
    for tool in ("claude", "opencode", "codex"):
        shutil.rmtree(kit.home / ".grokbot-kit", ignore_errors=True)
        kit.sink.unlink(missing_ok=True)
        cli_event = run_task(kit, tool, FAKE_STDOUT=OK_OUTPUT[tool])
        assert cli_event["plugin"] is None
        assert cli_event["result"] is None
        VALIDATOR.validate(cli_event)


PLUGIN_META = {
    "name": "nota",
    "version": "1.2.3",
    "source": "git",
    "commit": "a" * 40,
    "capabilities": {},
    "support": {},
}


# C46 - AC 47, door 5
def test_schema_accepts_plugin_fields(tmp_path: Path) -> None:
    props = SCHEMA["properties"]
    assert "result_invalid" in props["exit_reason"]["enum"]
    meta = {**task_meta(tmp_path), "plugin": PLUGIN_META}
    ok = payload.task_event(
        meta,
        tmp_path,
        event="completed",
        status="ok",
        exit_reason="success",
        exit_code=0,
        summary="s",
        result={"summary": "s", "findings": []},
    )
    assert ok["plugin"] == {"name": "nota", "version": "1.2.3", "source": "git", "commit": "a" * 40}
    VALIDATOR.validate(ok)
    invalid = payload.task_event(
        meta, tmp_path, event="error", status="failed", exit_reason="result_invalid", exit_code=0, summary="r"
    )
    assert invalid["result"] is None
    VALIDATOR.validate(invalid)
    for field, value in (
        ("plugin", {"name": "nota", "version": "1.2.3", "source": "git"}),
        ("plugin", {**ok["plugin"], "source": "outro"}),
        ("plugin", {**ok["plugin"], "extra": 1}),
        ("result", ["não", "objeto"]),
        ("result", "texto"),
    ):
        assert not VALIDATOR.is_valid({**ok, field: value}), (field, value)
    assert not VALIDATOR.is_valid({**ok, "exit_reason": "result_missing"})


# C54 - door 2 da needs-input-reply
def test_needs_input_schema_new_fields(tmp_path: Path) -> None:
    meta = task_meta(tmp_path)
    waiting = payload.needs_input_event(
        meta, tmp_path, kind="permission", tool_name="Bash", detail="x", request_id="r-1",
        reply_deadline="2026-11-05T12:10:00Z",
    )  # fmt: skip
    assert waiting["needs_input"]["reply_deadline"] == "2026-11-05T12:10:00Z"
    VALIDATOR.validate(waiting)
    notify = payload.needs_input_event(meta, tmp_path, kind="question", tool_name=None, detail=None, request_id="q-1")
    assert notify["needs_input"]["reply_deadline"] is None
    VALIDATOR.validate(notify)
    for key in ("request_id", "reply_deadline"):
        broken = json.loads(json.dumps(waiting))
        del broken["needs_input"][key]
        assert not VALIDATOR.is_valid(broken), key
    wrong = json.loads(json.dumps(waiting))
    wrong["needs_input"]["request_id"] = None
    assert not VALIDATOR.is_valid(wrong)
