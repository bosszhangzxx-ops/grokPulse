"""Provas do evento terminal do `run` (checks C46-C52, C54; AC 43-48, door 5).

Cada linha da tabela de status é provada na própria camada (`terminal.classify`, `terminal.read_output`) e na
fronteira (subprocesso `grokbot-kit run` com a CLI falsa).
"""

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import Kit

from grokbot_kit import terminal
from grokbot_kit.terminal import AgentOutput

TERMINAL_EVENTS = {"completed", "error", "timeout"}

CLAUDE_OK = json.dumps(
    {"type": "result", "subtype": "success", "is_error": False, "result": "feito", "permission_denials": []}
)
OPENCODE_OK = json.dumps({"type": "text", "sessionID": "ses_1", "part": {"type": "text", "text": "feito"}}) + "\n"
CODEX_OK = json.dumps({"type": "thread.started", "thread_id": "t1"}) + "\n" + json.dumps({"type": "turn.completed"})

CLEAN = AgentOutput(error=False, permission_denied=False, summary="")


def opencode_text(*texts: str) -> str:
    return "".join(json.dumps({"type": "text", "part": {"type": "text", "text": t}}) + "\n" for t in texts)


def run_task_with(kit: Kit, tool: str, fake: dict[str, str]) -> tuple[int, dict[str, Any]]:
    result = kit.run("--tool", tool, "--target", "bot-a", "--label", "t", "--", "faça", **fake)
    events = kit.sink_events()
    assert len(events) == 1, (events, result.stderr)
    return result.returncode, events[0]


def outcome(event: dict[str, Any]) -> tuple[str, str, str]:
    return event["event"], event["status"], event["exit_reason"]


# C46 - AC 43
def test_ok_on_clean_exit_layer() -> None:
    assert terminal.classify(0, CLEAN, needs_input=False) == ("completed", "ok", "success")


@pytest.mark.parametrize(("tool", "stdout"), [("claude", CLAUDE_OK), ("opencode", OPENCODE_OK), ("codex", CODEX_OK)])
def test_ok_on_clean_exit_cli(kit: Kit, tool: str, stdout: str) -> None:
    code, event = run_task_with(kit, tool, {"FAKE_STDOUT": stdout, "FAKE_LAST_MESSAGE": "feito"})
    assert outcome(event) == ("completed", "ok", "success")
    assert code == 0
    assert event["task_id"] == kit.task_dir().name
    assert event["target"] == "bot-a"
    assert event["tool"] == tool


# C47 - AC 44
def test_denied_on_recorded_needs_input_layer() -> None:
    assert terminal.classify(0, CLEAN, needs_input=True) == ("completed", "denied", "permission_denied")


@pytest.mark.parametrize(("tool", "stdout"), [("claude", CLAUDE_OK), ("opencode", OPENCODE_OK), ("codex", CODEX_OK)])
def test_denied_on_recorded_needs_input_cli(kit: Kit, tool: str, stdout: str) -> None:
    code, event = run_task_with(kit, tool, {"FAKE_STDOUT": stdout, "FAKE_NEEDS_INPUT": "1"})
    assert outcome(event) == ("completed", "denied", "permission_denied")
    assert code == 0


# C48 - AC 44
def test_denied_on_claude_permission_denials_layer(tmp_path: Path) -> None:
    out = {"type": "result", "is_error": False, "result": "não deu", "permission_denials": [{"tool_name": "Bash"}]}
    (tmp_path / "out.jsonl").write_text(json.dumps(out), encoding="utf-8")
    output = terminal.read_output("claude", tmp_path)
    assert output.permission_denied is True
    assert output.error is False
    assert terminal.classify(0, output, needs_input=False) == ("completed", "denied", "permission_denied")


def test_denied_on_claude_permission_denials_cli(kit: Kit) -> None:
    stdout = json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "não deu",
            "permission_denials": [{"tool_name": "Bash", "tool_use_id": "tu_1", "tool_input": {"command": "touch x"}}],
        }
    )
    code, event = run_task_with(kit, "claude", {"FAKE_STDOUT": stdout})
    assert outcome(event) == ("completed", "denied", "permission_denied")
    assert code == 0


# C49 - AC 45: exit != 0 sem erro na saída, mais as 4 formas de erro na saída
ERROR_OUTPUTS = {
    "claude is_error": ("claude", json.dumps({"type": "result", "is_error": True, "result": "falhou"})),
    "codex turn.failed": ("codex", json.dumps({"type": "turn.failed", "error": {"message": "boom"}})),
    "codex error": ("codex", json.dumps({"type": "error", "message": "boom"})),
    "opencode error": ("opencode", json.dumps({"type": "error", "error": {"name": "UnknownError"}})),
}


@pytest.mark.parametrize("case", sorted(ERROR_OUTPUTS))
def test_error_table_all_5_conditions_output_layer(tmp_path: Path, case: str) -> None:
    tool, stdout = ERROR_OUTPUTS[case]
    (tmp_path / "out.jsonl").write_text(stdout + "\n", encoding="utf-8")
    output = terminal.read_output(tool, tmp_path)
    assert output.error is True
    assert terminal.classify(0, output, needs_input=False) == ("error", "failed", "agent_error")
    assert terminal.classify(1, output, needs_input=False) == ("error", "failed", "agent_error")


def test_error_table_all_5_conditions_nonzero_layer() -> None:
    assert terminal.classify(1, CLEAN, needs_input=False) == ("error", "failed", "nonzero_exit")
    assert terminal.classify(3, CLEAN, needs_input=True) == ("error", "failed", "nonzero_exit")


@pytest.mark.parametrize("case", sorted(ERROR_OUTPUTS))
def test_error_table_all_5_conditions_output_cli(kit: Kit, case: str) -> None:
    tool, stdout = ERROR_OUTPUTS[case]
    code, event = run_task_with(kit, tool, {"FAKE_STDOUT": stdout})
    assert outcome(event) == ("error", "failed", "agent_error")
    assert code == 0


def test_error_table_all_5_conditions_nonzero_cli(kit: Kit) -> None:
    code, event = run_task_with(kit, "opencode", {"FAKE_STDOUT": OPENCODE_OK, "FAKE_EXIT": "1"})
    assert outcome(event) == ("error", "failed", "nonzero_exit")
    assert event["exit_code"] == 1
    assert code == 1


# C50 - AC 45 sobre AC 44
def test_error_wins_over_needs_input_layer() -> None:
    err = AgentOutput(error=True, permission_denied=True, summary="")
    assert terminal.classify(0, err, needs_input=True) == ("error", "failed", "agent_error")


def test_error_wins_over_needs_input_cli(kit: Kit) -> None:
    stdout = json.dumps({"type": "error", "error": {"name": "UnknownError"}})
    code, event = run_task_with(kit, "opencode", {"FAKE_STDOUT": stdout, "FAKE_NEEDS_INPUT": "1"})
    assert outcome(event) == ("error", "failed", "agent_error")
    assert code == 0


# C51 - AC 46
def write_summary_source(task_dir: Path, tool: str, text: str) -> None:
    if tool == "claude":
        out = json.dumps({"type": "result", "is_error": False, "result": text, "permission_denials": []})
    elif tool == "opencode":
        out = opencode_text("rascunho", text)
    else:
        out = CODEX_OK
        (task_dir / "last-message.txt").write_text(text, encoding="utf-8")
    (task_dir / "out.jsonl").write_text(out, encoding="utf-8")


@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
@pytest.mark.parametrize(("size", "expected"), [(1999, 1999), (2000, 2000), (2001, 2000)])
def test_summary_source_per_tool_and_2000_bound_layer(tmp_path: Path, tool: str, size: int, expected: int) -> None:
    text = "é" * (size - 1) + "z"
    write_summary_source(tmp_path, tool, text)
    assert terminal.read_output(tool, tmp_path).summary == text[:expected]


@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_summary_source_per_tool_and_2000_bound_cli(kit: Kit, tool: str) -> None:
    text = "r" * 2001
    if tool == "claude":
        fake = {"FAKE_STDOUT": json.dumps({"type": "result", "is_error": False, "result": text})}
    elif tool == "opencode":
        fake = {"FAKE_STDOUT": opencode_text("rascunho", text)}
    else:
        fake = {"FAKE_STDOUT": CODEX_OK, "FAKE_LAST_MESSAGE": text}
    _, event = run_task_with(kit, tool, fake)
    assert event["summary"] == "r" * 2000


# C52 - AC 47, door 5
EMIT_TERMINAL_ATTEMPTS = [
    {"event": "completed"},
    {"event": "error"},
    {"event": "timeout"},
    {"hook_event_name": "Stop"},
    {"hook_event_name": "SessionEnd"},
    {"type": "session.idle"},
]


@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_exactly_one_terminal_per_task(kit: Kit, tool: str) -> None:
    result = kit.run(
        "--tool",
        tool,
        "--target",
        "bot-a",
        "--label",
        "um",
        "--ask-wait",
        "0",
        "--",
        "faça",
        FAKE_EMIT=json.dumps(EMIT_TERMINAL_ATTEMPTS),
    )
    assert result.returncode == 0, result.stderr
    task_dir = kit.task_dir()
    sunk = [e for e in kit.sink_events() if e["event"] in TERMINAL_EVENTS]
    assert len(sunk) == 1
    assert sunk[0]["task_id"] == task_dir.name
    records = [json.loads(line) for line in (task_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["event"]["event"] for r in records if r["event"]["event"] in TERMINAL_EVENTS] == [sunk[0]["event"]]


# C54 - AC 48
@pytest.mark.parametrize("code", [0, 1, 3])
def test_run_exit_mirrors_agent(kit: Kit, code: int) -> None:
    result = kit.run(
        "--tool",
        "opencode",
        "--target",
        "bot-a",
        "--label",
        "x",
        "--",
        "faça",
        FAKE_STDOUT=OPENCODE_OK,
        FAKE_EXIT=str(code),
    )
    assert result.returncode == code, result.stderr
    assert kit.sink_events()[0]["exit_code"] == code


# C43 - AC 44
def test_plugin_task_never_denied() -> None:
    denied = AgentOutput(error=False, permission_denied=True, summary="")
    for needs_input in (False, True):
        assert terminal.classify(0, denied, needs_input=needs_input, plugin=True, result_valid=True) == (
            "completed",
            "ok",
            "success",
        )
        assert terminal.classify(0, denied, needs_input=needs_input, plugin=True, result_valid=False) == (
            "error",
            "failed",
            "result_invalid",
        )
    assert terminal.classify(0, denied, needs_input=False) == ("completed", "denied", "permission_denied")


# C44 - AC 45: a mesma precedência de hoje antes do resultado, que só decide quando o agente saiu limpo
PLUGIN_PRECEDENCE = [
    ("timeout", 124, CLEAN, "timeout", True, ("timeout", "timeout", "timeout")),
    ("interrompida", 130, CLEAN, "interrupted", True, ("error", "interrupted", "interrupted")),
    (
        "binario_ausente",
        127,
        AgentOutput(error=True, permission_denied=False, summary=""),
        None,
        True,
        ("error", "failed", "agent_error"),
    ),
    (
        "erro_do_agente",
        0,
        AgentOutput(error=True, permission_denied=False, summary=""),
        None,
        True,
        ("error", "failed", "agent_error"),
    ),
    ("exit_diferente_de_0", 3, CLEAN, None, True, ("error", "failed", "nonzero_exit")),
    ("resultado_invalido", 0, CLEAN, None, False, ("error", "failed", "result_invalid")),
    (
        "negacao_com_resultado_valido",
        0,
        AgentOutput(error=False, permission_denied=True, summary=""),
        None,
        True,
        ("completed", "ok", "success"),
    ),
]


@pytest.mark.parametrize(
    ("case", "code", "output", "stopped", "valid", "expected"), PLUGIN_PRECEDENCE, ids=[r[0] for r in PLUGIN_PRECEDENCE]
)
def test_plugin_precedence_table(
    case: str, code: int, output: AgentOutput, stopped: str | None, valid: bool, expected: tuple[str, str, str]
) -> None:
    got = terminal.classify(code, output, needs_input=True, stopped=stopped, plugin=True, result_valid=valid)
    assert got == expected


# model-setup-docs: o `summary` vem da mensagem de erro da CLI quando o agente não deixou texto (door 6)
ERROR_119 = {"type": "error", "error": {"name": "UnknownError", "data": {"message": "Unexpected server error"}}}
ERROR_2X = {"type": "error", "error": {"type": "provider.no-route", "message": "Model unavailable: opencode/x"}}


def jsonl(*objects: dict[str, Any]) -> str:
    return "".join(json.dumps(o) + "\n" for o in objects)


def summary_of(tmp_path: Path, tool: str, out: str, last_message: str | None = None) -> str:
    (tmp_path / "out.jsonl").write_text(out, encoding="utf-8")
    if last_message is not None:
        (tmp_path / "last-message.txt").write_text(last_message, encoding="utf-8")
    return terminal.read_output(tool, tmp_path).summary


# C20 - AC 22, door 6
@pytest.mark.parametrize(
    ("objects", "expected"),
    [
        ([ERROR_119], "UnknownError: Unexpected server error"),
        ([ERROR_2X], "provider.no-route: Model unavailable: opencode/x"),
        ([{"type": "error", "error": {"name": "UnknownError"}}], "UnknownError"),
        ([ERROR_2X, ERROR_119], "UnknownError: Unexpected server error"),
    ],
)
def test_error_summary_opencode(tmp_path: Path, objects: list[dict[str, Any]], expected: str) -> None:
    output_text = jsonl({"type": "step_start", "sessionID": "ses_1"}, *objects)
    assert summary_of(tmp_path, "opencode", output_text) == expected
    assert terminal.read_output("opencode", tmp_path).error is True


# C21 - AC 23, door 6
@pytest.mark.parametrize("last_message", [None, ""])
@pytest.mark.parametrize(
    ("objects", "expected"),
    [
        ([{"type": "turn.failed", "error": {"message": "boom"}}], "boom"),
        ([{"type": "error", "message": "boom"}], "boom"),
        ([{"type": "error", "message": "primeiro"}, {"type": "turn.failed", "error": {"message": "último"}}], "último"),
        ([{"type": "turn.failed", "error": {"message": "primeiro"}}, {"type": "error", "message": "último"}], "último"),
    ],
)
def test_error_summary_codex(
    tmp_path: Path, objects: list[dict[str, Any]], expected: str, last_message: str | None
) -> None:
    assert summary_of(tmp_path, "codex", jsonl(*objects), last_message) == expected


# C22 - AC 24
def test_error_summary_text_wins(tmp_path: Path) -> None:
    out = jsonl(ERROR_119, {"type": "text", "part": {"type": "text", "text": "feito"}})
    assert summary_of(tmp_path, "opencode", out) == "feito"
    codex = tmp_path / "codex"
    codex.mkdir()
    assert summary_of(codex, "codex", jsonl({"type": "turn.failed", "error": {"message": "boom"}}), "feito") == "feito"


# C23 - AC 25
@pytest.mark.parametrize("tool", ["opencode", "codex"])
def test_error_summary_limit(tmp_path: Path, tool: str) -> None:
    message = "x" * 5000
    if tool == "opencode":
        out = jsonl({"type": "error", "error": {"type": "e", "message": message}})
    else:
        out = jsonl({"type": "error", "message": message})
    assert len(summary_of(tmp_path, tool, out)) == 2000


# C25 - AC 26, AC 31, AC 34, door 4: a tentativa caiu no provedor antes de qualquer ferramenta
TOOL_USE = {"type": "tool_use", "part": {"type": "tool", "tool": "read"}}


def claude_result(**fields: Any) -> dict[str, Any]:
    return {"type": "result", "is_error": True, "terminal_reason": "api_error", "num_turns": 1, "result": "x", **fields}


ELIGIBILITY = [
    ("opencode", [ERROR_119], None, True),
    ("opencode", [TOOL_USE, ERROR_119], None, False),
    ("opencode", [{"type": "text", "part": {"type": "text", "text": "ok"}}], None, False),
    ("claude", [claude_result()], None, True),
    ("claude", [claude_result(num_turns=2)], None, False),
    ("claude", [claude_result(terminal_reason="max_turns")], None, False),
    ("claude", [claude_result(is_error=False)], None, False),
    ("codex", [{"type": "turn.failed", "error": {"message": "boom"}}], None, False),
    ("opencode", [ERROR_119], "timeout", False),
    ("claude", [claude_result()], "interrupted", False),
]


@pytest.mark.parametrize(("tool", "objects", "stopped", "expected"), ELIGIBILITY)
def test_fallback_eligible(
    tmp_path: Path, tool: str, objects: list[dict[str, Any]], stopped: str | None, expected: bool
) -> None:
    (tmp_path / "out.jsonl").write_text(jsonl(*objects), encoding="utf-8")
    assert terminal.fallback_eligible(tool, tmp_path, stopped) is expected


def _asked(request_id: str) -> dict[str, Any]:
    return {"event": "needs_input", "status": "permission", "needs_input": {"request_id": request_id}}


def _reply(task_dir: Path, request_id: str, decision: str, by: str = "user") -> None:
    (task_dir / "replies").mkdir(exist_ok=True)
    body = {"decision": decision, "message": None, "by": by, "at": "2026-11-05T12:00:00Z"}
    (task_dir / "replies" / f"{request_id}.json").write_text(json.dumps(body), encoding="utf-8")


# C39 - AC 27 da needs-input-reply
def test_all_allowed_is_success(tmp_path: Path) -> None:
    asked = [_asked("a"), _asked("b")]
    _reply(tmp_path, "a", "allow")
    _reply(tmp_path, "b", "allow", by="bot")
    assert terminal.unanswered(tmp_path, asked) == []
    pending = bool(terminal.unanswered(tmp_path, asked))
    assert terminal.classify(0, CLEAN, needs_input=pending) == ("completed", "ok", "success")


# C40 - AC 28 da needs-input-reply
@pytest.mark.parametrize("case", ["sem resposta", "deny do usuário", "deny do prazo"])
def test_any_unallowed_is_denied(tmp_path: Path, case: str) -> None:
    asked = [_asked("a"), _asked("b")]
    _reply(tmp_path, "a", "allow")
    if case == "deny do usuário":
        _reply(tmp_path, "b", "deny")
    elif case == "deny do prazo":
        _reply(tmp_path, "b", "deny", by="timeout")
    assert terminal.unanswered(tmp_path, asked) == [asked[1]]
    pending = bool(terminal.unanswered(tmp_path, asked))
    assert terminal.classify(0, CLEAN, needs_input=pending) == ("completed", "denied", "permission_denied")


def test_any_unallowed_is_denied_permission_denials(tmp_path: Path) -> None:
    asked = [_asked("a"), _asked("b")]
    _reply(tmp_path, "a", "allow")
    _reply(tmp_path, "b", "allow")
    out = tmp_path / "out.jsonl"
    out.write_text(json.dumps({"type": "result", "is_error": False, "result": "x", "permission_denials": [{}]}))
    output = terminal.read_output("claude", tmp_path)
    pending = bool(terminal.unanswered(tmp_path, asked))
    assert terminal.classify(0, output, needs_input=pending) == ("completed", "denied", "permission_denied")


def test_any_unallowed_is_denied_legacy_record(tmp_path: Path) -> None:
    # um `needs_input` sem `request_id` (registro de antes desta feature) nunca foi respondido
    legacy = {"event": "needs_input", "status": "permission"}
    assert terminal.unanswered(tmp_path, [legacy]) == [legacy]
