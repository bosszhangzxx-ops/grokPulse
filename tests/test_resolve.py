"""Provas da resolução de tool, modelo, tier e timeout do `run` (checks C98, C99, C100 e C103; AC 78-80 e 83).

Cada check tem uma prova na fronteira (subprocesso `grokbot-kit run` com as CLIs falsas) e uma na própria camada
(`grokbot_kit.resolve`), uma linha por caso da tabela de decisão.
"""

import json
import tomllib
from typing import Any

import pytest
from conftest import Kit

from grokbot_kit import config, resolve

TOOLS = ("opencode", "claude", "codex")
MODEL_FLAG = {"claude": "--model", "opencode": "-m", "codex": "-m"}
TIERS = {"trivial": ["t-1"], "standard": ["s-1", "s-2"], "complex": ["c-1", "c-2"]}


def make_config(kit: Kit, default_cli: str = "opencode", timeouts: dict[str, str] | None = None) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "setup": {"version": 1, "installed": list(TOOLS), "default_cli": default_cli},
        "cli": {
            tool: {
                "models": ["t-1", "s-1", "s-2", "c-1", "c-2", "m-1"],
                "tiers": {k: list(v) for k, v in TIERS.items()},
            }
            for tool in TOOLS
        },
        "routes": {"bot-a": {"sinks": ["arquivo"]}},
        "sinks": {"arquivo": {"type": "file", "path": str(kit.sink)}},
    }
    cfg["cli"]["codex"]["codex_home"] = "~/.grokbot-kit/codex-home"
    if timeouts is not None:
        cfg["timeouts"] = timeouts
    kit.write_config(config.dump(cfg))
    return cfg


def launched_model(kit: Kit) -> str:
    launched = kit.launched()
    argv: list[str] = launched["argv"]
    flag = MODEL_FLAG[launched["tool"]]
    assert argv.count(flag) == 1, argv
    return argv[argv.index(flag) + 1]


def meta(kit: Kit) -> dict[str, Any]:
    result: dict[str, Any] = json.loads((kit.task_dir() / "meta.json").read_text(encoding="utf-8"))
    return result


def terminal_event(kit: Kit) -> dict[str, Any]:
    events = [e for e in kit.sink_events() if e["event"] != "needs_input"]
    assert len(events) == 1, events
    return events[0]


# C98 - AC 78
@pytest.mark.parametrize("default_cli", TOOLS)
def test_default_cli_when_no_tool(kit: Kit, default_cli: str) -> None:
    make_config(kit, default_cli=default_cli)
    result = kit.run("--target", "bot-a", "--label", "padrao", "--", "oi")
    assert result.returncode == 0, result.stderr
    assert kit.launched()["tool"] == default_cli
    assert terminal_event(kit)["tool"] == default_cli


@pytest.mark.parametrize("default_cli", TOOLS)
def test_default_cli_when_no_tool_resolve_layer(kit: Kit, default_cli: str) -> None:
    cfg = make_config(kit, default_cli=default_cli)
    assert resolve.resolve(cfg, tool=None, model=None, tier=None, timeout=None).tool == default_cli
    other = next(t for t in TOOLS if t != default_cli)
    assert resolve.resolve(cfg, tool=other, model=None, tier=None, timeout=None).tool == other


# C99 - AC 79
@pytest.mark.parametrize("tool", TOOLS)
def test_explicit_model_passthrough(kit: Kit, tool: str) -> None:
    make_config(kit)
    result = kit.run("--tool", tool, "--model", "m-1", "--target", "bot-a", "--label", "modelo", "--", "oi")
    assert result.returncode == 0, result.stderr
    assert launched_model(kit) == "m-1"
    event = terminal_event(kit)
    assert (event["model"], event["model_source"]) == ("m-1", "user")


@pytest.mark.parametrize("tier", [None, "trivial", "complex"])
def test_explicit_model_passthrough_resolve_layer(kit: Kit, tier: str | None) -> None:
    cfg = make_config(kit)
    r = resolve.resolve(cfg, tool="claude", model="m-1", tier=tier, timeout=None)
    assert (r.model, r.model_source) == ("m-1", "user")


# C100 - AC 80
@pytest.mark.parametrize(("tier", "expected"), [(None, ("s-1", "standard")), ("trivial", ("t-1", "trivial"))])
@pytest.mark.parametrize("tool", TOOLS)
def test_first_tier_model_default_standard(kit: Kit, tool: str, tier: str | None, expected: tuple[str, str]) -> None:
    make_config(kit)
    tier_args = ["--tier", tier] if tier else []
    result = kit.run("--tool", tool, *tier_args, "--target", "bot-a", "--label", "tier", "--", "oi")
    assert result.returncode == 0, result.stderr
    assert launched_model(kit) == expected[0]
    event = terminal_event(kit)
    assert (event["model"], event["tier"], event["model_source"]) == (*expected, "tier")


@pytest.mark.parametrize(
    ("tier", "expected"),
    [
        (None, ("s-1", "standard")),
        ("trivial", ("t-1", "trivial")),
        ("standard", ("s-1", "standard")),
        ("complex", ("c-1", "complex")),
    ],
)
def test_first_tier_model_default_standard_resolve_layer(kit: Kit, tier: str | None, expected: tuple[str, str]) -> None:
    cfg = make_config(kit)
    r = resolve.resolve(cfg, tool="opencode", model=None, tier=tier, timeout=None)
    assert (r.model, r.tier, r.model_source) == (*expected, "tier")


def test_first_tier_model_default_standard_empty_tier_refuses(kit: Kit) -> None:
    cfg = make_config(kit)
    cfg["cli"]["opencode"]["tiers"]["trivial"] = []
    with pytest.raises(resolve.ResolveError) as raised:
        resolve.resolve(cfg, tool="opencode", model=None, tier="trivial", timeout=None)
    assert "cli.opencode.tiers.trivial" in str(raised.value)


DEFAULT_SECONDS = {"trivial": 30 * 60, "standard": 2 * 3600, "complex": 4 * 3600}
CONFIG_TIMEOUTS = {"trivial": "10m", "standard": "3h", "complex": "1d"}
CONFIG_SECONDS = {"trivial": 600, "standard": 3 * 3600, "complex": 86400}


# C103 - AC 83
@pytest.mark.parametrize("tier", ["trivial", "standard", "complex"])
@pytest.mark.parametrize("source", ["padrões", "config"])
def test_timeout_per_tier_and_override(kit: Kit, tier: str, source: str) -> None:
    make_config(kit, timeouts=CONFIG_TIMEOUTS if source == "config" else None)
    result = kit.run("--tier", tier, "--target", "bot-a", "--label", "prazo", "--", "oi")
    assert result.returncode == 0, result.stderr
    expected = CONFIG_SECONDS if source == "config" else DEFAULT_SECONDS
    assert meta(kit)["timeout_seconds"] == expected[tier]


@pytest.mark.parametrize("tier", [None, "trivial", "complex"])
def test_timeout_per_tier_and_override_flag_wins(kit: Kit, tier: str | None) -> None:
    make_config(kit, timeouts=CONFIG_TIMEOUTS)
    tier_args = ["--tier", tier] if tier else []
    result = kit.run(*tier_args, "--timeout", "5s", "--target", "bot-a", "--label", "prazo", "--", "oi")
    assert result.returncode == 0, result.stderr
    assert meta(kit)["timeout_seconds"] == 5


def test_timeout_per_tier_and_override_explicit_model_uses_standard(kit: Kit) -> None:
    make_config(kit)
    result = kit.run("--model", "m-1", "--target", "bot-a", "--label", "prazo", "--", "oi")
    assert result.returncode == 0, result.stderr
    assert meta(kit)["timeout_seconds"] == DEFAULT_SECONDS["standard"]


@pytest.mark.parametrize("value", ["2x", "0s", "90", "-5m", "1h30m", "", "5 s"])
def test_timeout_per_tier_and_override_invalid_flag_exit_2(kit: Kit, value: str) -> None:
    make_config(kit)
    result = kit.run("--timeout", value, "--target", "bot-a", "--label", "prazo", "--", "oi")
    assert result.returncode == 2
    assert "--timeout" in result.stderr
    assert not kit.record.exists(), "o agente foi lançado"
    assert kit.tasks() == []


def test_timeout_per_tier_and_override_invalid_config_exit_2(kit: Kit) -> None:
    make_config(kit, timeouts={"trivial": "meia hora"})
    result = kit.run("--tier", "trivial", "--target", "bot-a", "--label", "prazo", "--", "oi")
    assert result.returncode == 2
    assert "timeouts.trivial" in result.stderr
    assert not kit.record.exists(), "o agente foi lançado"


@pytest.mark.parametrize(
    ("tier", "timeouts", "flag", "expected"),
    [
        ("trivial", None, None, 1800),
        ("standard", None, None, 7200),
        ("complex", None, None, 14400),
        (None, None, None, 7200),
        ("trivial", CONFIG_TIMEOUTS, None, 600),
        ("standard", CONFIG_TIMEOUTS, None, 10800),
        ("complex", CONFIG_TIMEOUTS, None, 86400),
        ("standard", {"trivial": "1m"}, None, 7200),
        ("complex", CONFIG_TIMEOUTS, "5s", 5),
        (None, None, "45m", 2700),
    ],
)
def test_timeout_per_tier_and_override_resolve_layer(
    kit: Kit, tier: str | None, timeouts: dict[str, str] | None, flag: str | None, expected: int
) -> None:
    cfg = make_config(kit, timeouts=timeouts)
    assert resolve.resolve(cfg, tool="opencode", model=None, tier=tier, timeout=flag).timeout_seconds == expected


@pytest.mark.parametrize(
    ("text", "seconds"), [("5s", 5), ("30m", 1800), ("2h", 7200), ("4h", 14400), ("30d", 30 * 86400), ("10s", 10)]
)
def test_timeout_per_tier_and_override_duration_grammar(text: str, seconds: int) -> None:
    assert resolve.parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["2x", "0s", "90", "-5m", "1h30m", "", "5 s", "05m", "1.5h", "2H"])
def test_timeout_per_tier_and_override_duration_grammar_rejects(text: str) -> None:
    with pytest.raises(ValueError):
        resolve.parse_duration(text)


def test_timeout_per_tier_and_override_config_shape(kit: Kit) -> None:
    """Os padrões de timeout são os literais da door 3."""
    assert resolve.DEFAULT_TIMEOUTS == {"trivial": "30m", "standard": "2h", "complex": "4h"}
    assert tomllib.loads(config.dump({"timeouts": resolve.DEFAULT_TIMEOUTS})) == {"timeouts": resolve.DEFAULT_TIMEOUTS}
