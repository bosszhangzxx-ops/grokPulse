"""Provas do `run` com a escolha de provedores, o `summary` de erro e o fallback de modelo do tier (model-setup-docs:
checks C12, C24, C26-C35; doors 3-6).

Na fronteira: o subprocesso `grokbot-kit run` com as CLIs falsas; `FAKE_STDOUT_BY_MODEL` dá uma saída por id.
"""

import json
import time
from pathlib import Path
from typing import Any

from conftest import Kit, Receiver, add_routine, default_config


def opencode_config(kit: Kit, models: list[str], standard: list[str], providers: list[str] | None = None) -> None:
    text = default_config(kit.sink).replace('models = ["opencode/free-model"]', f"models = {json.dumps(models)}")
    text = text.replace('standard = ["opencode/free-model"]', f"standard = {json.dumps(standard)}", 1)
    if providers is not None:
        text = text.replace("[cli.opencode.tiers]", f"providers = {json.dumps(providers)}\n[cli.opencode.tiers]", 1)
    kit.write_config(text)


# C12 - AC 13: o `run` não recusa id de tier fora de `providers`
def test_run_tier_outside_providers(kit: Kit) -> None:
    opencode_config(kit, ["opencode/a-free", "opencode-go/b"], ["opencode/a-free"], ["opencode-go"])
    result = kit.run("--target", "bot-a", "--label", "l", "--", "x")
    assert result.returncode == 0, result.stderr
    argv = kit.launched()["argv"]
    assert argv[argv.index("-m") + 1] == "opencode/a-free"


M1, M2, M3 = "opencode/m1", "opencode/m2", "opencode/m3"
ERROR_119 = {"type": "error", "error": {"name": "UnknownError", "data": {"message": "Unexpected server error"}}}
ERROR_SUMMARY = "UnknownError: Unexpected server error"
TOOL_USE = {"type": "tool_use", "part": {"type": "tool", "tool": "read"}}


def jsonl(*objects: dict[str, Any]) -> str:
    return "".join(json.dumps(o) + "\n" for o in objects)


def text(value: str) -> str:
    return jsonl({"type": "text", "part": {"type": "text", "text": value}})


def error(message: str) -> str:
    return jsonl({"type": "error", "error": {"name": "UnknownError", "data": {"message": message}}})


def by_model(**fake: dict[str, str]) -> dict[str, str]:
    """`FAKE_STDOUT_BY_MODEL` e afins a partir de `{"STDOUT": {"<id>": "<valor>"}, ...}`."""
    return {f"FAKE_{name}_BY_MODEL": json.dumps(table) for name, table in fake.items()}


def run_task(kit: Kit, tmp_path: Path, *args: str, target: str = "bot-a", **fake: str) -> dict[str, Any]:
    result = kit.run(
        "--target",
        target,
        "--label",
        "fb",
        *args,
        "--",
        "revise isto",
        FAKE_CALLS=str(tmp_path / "calls.jsonl"),
        **fake,
    )
    events = [e for e in kit.sink_events() if e["event"] != "needs_input"] if target == "bot-a" else []
    if target == "bot-a":
        assert len(events) == 1, (events, result.stderr)
        return events[0]
    return {"returncode": result.returncode, "stderr": result.stderr}


def calls(tmp_path: Path) -> list[dict[str, Any]]:
    """As tentativas gravadas pela CLI falsa, sem o `opencode --version` que o `run` faz antes de lançar (door 9 da
    needs-input-reply)."""
    path = tmp_path / "calls.jsonl"
    found = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    return [c for c in found if c["argv"] != ["--version"]]


def outcome(event: dict[str, Any]) -> tuple[str, str, str]:
    return event["event"], event["status"], event["exit_reason"]


# C24 - AC 22: o `summary` de erro chega à rota
def test_event_summary_from_error(kit: Kit, tmp_path: Path) -> None:
    opencode_config(kit, [M1], [M1])
    event = run_task(kit, tmp_path, FAKE_STDOUT=jsonl(ERROR_119), FAKE_EXIT="1")
    assert outcome(event) == ("error", "failed", "agent_error")
    assert event["summary"] == ERROR_SUMMARY


FALLBACK_OK = by_model(STDOUT={M1: jsonl(ERROR_119), M2: text("ok")}, EXIT={M1: "1"})


# C26 - AC 26, AC 27, AC 28, door 5
def test_fallback_next_model(kit: Kit, tmp_path: Path) -> None:
    opencode_config(kit, [M1, M2], [M1, M2])
    event = run_task(kit, tmp_path, "--tier", "standard", **FALLBACK_OK)
    assert outcome(event) == ("completed", "ok", "success")
    assert event["model"] == M2
    assert event["model_fallbacks"] == [{"model": M1, "error": ERROR_SUMMARY}]
    made = calls(tmp_path)
    assert [c["argv"][c["argv"].index("-m") + 1] for c in made] == [M1, M2]
    assert made[0]["cwd"] == made[1]["cwd"]
    assert made[0]["argv"][-1] == made[1]["argv"][-1] == "revise isto"
    task_dir = kit.task_dir()
    assert (task_dir / "out.1.jsonl").read_text(encoding="utf-8") == jsonl(ERROR_119)
    assert (task_dir / "stderr.1.log").exists()
    assert (task_dir / "out.jsonl").read_text(encoding="utf-8") == text("ok")
    line = f"model {M1} failed at the provider before any tool call ({ERROR_SUMMARY}); trying {M2}"
    assert line in (task_dir / "kit.log").read_text(encoding="utf-8")


# C34 - door 5
def test_meta_records_fallback(kit: Kit, tmp_path: Path) -> None:
    opencode_config(kit, [M1, M2], [M1, M2])
    event = run_task(kit, tmp_path, "--tier", "standard", **FALLBACK_OK)
    meta = json.loads((kit.task_dir() / "meta.json").read_text(encoding="utf-8"))
    assert meta["model"] == M2
    assert meta["model_fallbacks"] == event["model_fallbacks"]


# C35 - Surface, door 5
def test_delivered_body_has_fallbacks(kit: Kit, tmp_path: Path, receiver: Receiver) -> None:
    opencode_config(kit, [M1, M2], [M1, M2])
    add_routine(kit, receiver)
    result = run_task(kit, tmp_path, "--tier", "standard", target="bot-r", **FALLBACK_OK)
    assert result["returncode"] == 0, result["stderr"]
    bodies = receiver.bodies()
    assert len(bodies) == 1
    assert bodies[0]["model_fallbacks"] == [{"model": M1, "error": ERROR_SUMMARY}]
    records = [json.loads(line) for line in (kit.task_dir() / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [d["http_status"] for d in records[-1]["deliveries"]] == [200]
    assert records[-1]["deliveries"][0]["delivered"] is True


# C27 - AC 29, door 5
def test_no_fallback_empty_list(kit: Kit, tmp_path: Path) -> None:
    cases = [
        ({"FAKE_STDOUT": text("ok")}, (), ("completed", "ok", "success")),
        ({"FAKE_STDOUT": "", "FAKE_EXIT": "3"}, (), ("error", "failed", "nonzero_exit")),
        ({"FAKE_SLEEP": "10"}, ("--timeout", "1s"), ("timeout", "timeout", "timeout")),
    ]
    opencode_config(kit, [M1, M2], [M1, M2])
    for fake, args, expected in cases:
        kit.sink.unlink(missing_ok=True)
        event = run_task(kit, tmp_path, *args, **fake)
        assert outcome(event) == expected
        assert event["model_fallbacks"] == []


# C28 - AC 30
def test_explicit_model_no_fallback(kit: Kit, tmp_path: Path) -> None:
    opencode_config(kit, [M1, M2], [M1, M2])
    event = run_task(kit, tmp_path, "--model", M1, **FALLBACK_OK)
    assert len(calls(tmp_path)) == 1
    assert outcome(event) == ("error", "failed", "agent_error")
    assert event["model_fallbacks"] == []


# C29 - AC 31
def test_failure_after_tool_no_fallback(kit: Kit, tmp_path: Path) -> None:
    opencode_config(kit, [M1, M2], [M1, M2])
    event = run_task(kit, tmp_path, **by_model(STDOUT={M1: jsonl(TOOL_USE, ERROR_119), M2: text("ok")}))
    assert len(calls(tmp_path)) == 1
    assert outcome(event) == ("error", "failed", "agent_error")
    assert event["model_fallbacks"] == []


def test_failure_after_tool_no_fallback_claude(kit: Kit, tmp_path: Path) -> None:
    text_config = kit.config_text().replace('models = ["sonnet"]', 'models = ["c-1", "c-2"]')
    kit.write_config(text_config.replace('standard = ["sonnet"]', 'standard = ["c-1", "c-2"]'))
    failed = {"type": "result", "is_error": True, "terminal_reason": "api_error", "num_turns": 3, "result": "erro"}
    ok = {"type": "result", "is_error": False, "result": "ok", "permission_denials": []}
    event = run_task(kit, tmp_path, "--tool", "claude", **by_model(STDOUT={"c-1": jsonl(failed), "c-2": jsonl(ok)}))
    assert len(calls(tmp_path)) == 1
    assert outcome(event) == ("error", "failed", "agent_error")


# C30 - AC 32
def test_all_models_fail(kit: Kit, tmp_path: Path) -> None:
    opencode_config(kit, [M1, M2, M3], [M1, M2, M3])
    stdout = {M1: error("erro 1"), M2: error("erro 2"), M3: error("erro 3")}
    event = run_task(kit, tmp_path, **by_model(STDOUT=stdout))
    assert outcome(event) == ("error", "failed", "agent_error")
    assert event["model"] == M3
    assert event["summary"] == "UnknownError: erro 3"
    assert event["model_fallbacks"] == [
        {"model": M1, "error": "UnknownError: erro 1"},
        {"model": M2, "error": "UnknownError: erro 2"},
    ]
    task_dir = kit.task_dir()
    assert (task_dir / "out.1.jsonl").read_text(encoding="utf-8") == stdout[M1]
    assert (task_dir / "out.2.jsonl").read_text(encoding="utf-8") == stdout[M2]
    assert (task_dir / "out.jsonl").read_text(encoding="utf-8") == stdout[M3]


# C31 - AC 33
def test_shared_deadline(kit: Kit, tmp_path: Path) -> None:
    opencode_config(kit, [M1, M2, M3], [M1, M2, M3])
    fake = by_model(STDOUT={M1: jsonl(ERROR_119), M2: jsonl(ERROR_119)}, SLEEP={M1: "3", M2: "10"})
    began = time.monotonic()
    event = run_task(kit, tmp_path, "--timeout", "4s", **fake)
    assert time.monotonic() - began < 6, "as tentativas dividem um prazo só, não um por tentativa"
    assert outcome(event) == ("timeout", "timeout", "timeout")
    assert event["model"] == M2
    assert len(calls(tmp_path)) == 2


def test_shared_deadline_first_times_out(kit: Kit, tmp_path: Path) -> None:
    opencode_config(kit, [M1, M2], [M1, M2])
    event = run_task(kit, tmp_path, "--timeout", "1s", **by_model(STDOUT={M1: jsonl(ERROR_119)}, SLEEP={M1: "10"}))
    assert outcome(event) == ("timeout", "timeout", "timeout")
    assert len(calls(tmp_path)) == 1


# C32 - AC 34
def test_codex_never_falls_back(kit: Kit, tmp_path: Path) -> None:
    text_config = kit.config_text().replace('models = ["gpt-test"]', 'models = ["g-1", "g-2"]')
    kit.write_config(text_config.replace('standard = ["gpt-test"]', 'standard = ["g-1", "g-2"]'))
    failed = jsonl({"type": "turn.failed", "error": {"message": "boom"}})
    event = run_task(kit, tmp_path, "--tool", "codex", "--tier", "standard", FAKE_STDOUT=failed)
    assert len([c for c in calls(tmp_path) if c["tool"] == "codex" and c["argv"][:1] == ["exec"]]) == 1
    assert outcome(event) == ("error", "failed", "agent_error")
    assert event["model_fallbacks"] == []


# review do PR 29: um tier vazio nunca chega ao laço de tentativas; o `run` recusa antes do task dir
def test_empty_tier_refused_before_task_dir(kit: Kit, tmp_path: Path) -> None:
    opencode_config(kit, [M1], [])
    result = kit.run("--tier", "standard", "--target", "bot-a", "--label", "vazio", "--", "x")
    assert result.returncode == 2
    assert "no model in cli.opencode.tiers.standard" in result.stderr
    assert kit.tasks() == []
