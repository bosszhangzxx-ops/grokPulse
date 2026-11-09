"""Provas do config do kit (checks C95 e C96; door 3 e as constraints de Relations)."""

import tomllib
from typing import Any

import pytest
from conftest import Kit, default_config

from grokbot_kit import config


def door_3_config() -> dict[str, Any]:
    """Um config com todas as chaves literais da door 3 (mais `models`, door 12) e os 4 tipos de sink."""

    def tiers() -> dict[str, list[str]]:
        return {"trivial": ["t-1"], "standard": ["s-1", "s-2"], "complex": ["c-1"]}

    discovered = ["t-1", "s-1", "s-2", "c-1"]
    return {
        "setup": {"version": 1, "installed": ["opencode", "claude", "codex"], "default_cli": "opencode"},
        "timeouts": {"trivial": "30m", "standard": "2h", "complex": "4h"},
        "cli": {
            "opencode": {
                "bin": "/home/box/.opencode/bin/opencode",
                "models_discovered_at": "2026-10-20T12:00:00Z",
                "models": ["opencode/grok-code", *discovered],
                "tiers": tiers(),
            },
            "claude": {
                "bin": "/home/box/.local/bin/claude",
                "models_discovered_at": "2026-10-20T12:00:01Z",
                "models": ["haiku", "sonnet", "opus", *discovered],
                "tiers": tiers(),
            },
            "codex": {
                "bin": "/home/box/.local/bin/codex",
                "models_discovered_at": "2026-10-20T12:00:02Z",
                "models": discovered,
                "codex_home": "~/.grokbot-kit/codex-home",
                "tiers": tiers(),
            },
        },
        "routes": {
            "bot-a": {"sinks": ["rotina-a", "arquivo", "avisos", "canal"]},
            "bot.ponto": {"sinks": ["rotina-a"]},
        },
        "sinks": {
            "rotina-a": {
                "type": "grokbot-routine",
                "url_secret": "bot-a-url",
                "key_secret": "bot-a-key",
                "headers": {"X-Origem": 'box "compartilhado" \\ ção'},
            },
            "arquivo": {"type": "file", "path": "/home/box/eventos ção.jsonl"},
            "avisos": {"type": "ntfy", "topic_url": "https://ntfy.example/topico", "token_secret": "ntfy-token"},
            "canal": {"type": "slack", "webhook_secret": "slack-url"},
        },
    }


# C95 - door 3
def test_roundtrip_door_3_all_keys() -> None:
    cfg = door_3_config()
    assert tomllib.loads(config.dump(cfg)) == cfg


def test_roundtrip_door_3_all_keys_through_save_and_load(kit: Kit, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(kit.home))
    cfg = door_3_config()
    config.save(cfg)
    assert config.load() == cfg


INVALID = {
    "default_cli fora de installed": (
        lambda c: c["setup"].update(installed=["claude", "codex"]),
        "setup.default_cli",
    ),
    "default_cli sem installed": (
        lambda c: c["setup"].pop("installed"),
        "setup.default_cli",
    ),
    "id de tier fora dos descobertos": (
        lambda c: c["cli"]["claude"]["tiers"].update(complex=["inventado-123"]),
        "cli.claude.tiers.complex",
    ),
    "tier sem lista descoberta": (
        lambda c: c["cli"]["codex"].pop("models"),
        "cli.codex.tiers.",
    ),
}


def write(kit: Kit, cfg: dict[str, Any]) -> None:
    kit.write_config(config.dump(cfg))


# C96 - door 3, Relations
@pytest.mark.parametrize("case", list(INVALID))
def test_constraints_default_cli_and_discovered_ids(kit: Kit, case: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(kit.home))
    cfg = door_3_config()
    mutate, key = INVALID[case]
    mutate(cfg)
    write(kit, cfg)
    with pytest.raises(config.ConfigError) as raised:
        config.load()
    assert key in str(raised.value)


def test_constraints_default_cli_and_discovered_ids_valid_loads(kit: Kit, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(kit.home))
    cfg = door_3_config()
    write(kit, cfg)
    assert config.load() == cfg


def test_constraints_default_cli_and_discovered_ids_routes_only_loads(
    kit: Kit, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um config que só tem rotas (o `route add` antes do setup) não fere nenhuma constraint."""
    monkeypatch.setenv("HOME", str(kit.home))
    cfg = {k: v for k, v in door_3_config().items() if k in ("routes", "sinks")}
    write(kit, cfg)
    assert config.load() == cfg


@pytest.mark.parametrize("case", list(INVALID))
def test_constraints_default_cli_and_discovered_ids_run_exit_2(kit: Kit, case: str) -> None:
    """Na fronteira: o `run` recusa com `2`, sem lançar, e a mensagem nomeia a chave."""
    cfg = tomllib.loads(default_config(kit.sink))
    cfg["cli"]["claude"]["tiers"]["complex"] = ["sonnet"]
    cfg["setup"]["default_cli"] = "opencode"
    mutate, key = INVALID[case]
    mutate(cfg)
    write(kit, cfg)
    result = kit.run("--target", "bot-a", "--label", "config", "--", "oi")
    assert result.returncode == 2
    assert key in result.stderr
    assert not kit.record.exists(), "o agente foi lançado"
    assert kit.tasks() == []


# C12 - AC 13: `providers` não entra nas constraints do `load()`
def test_load_ignores_providers(kit: Kit, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(kit.home))
    cfg = door_3_config()
    cfg["cli"]["opencode"]["models"] = ["opencode/a-free", "opencode-go/b"]
    cfg["cli"]["opencode"]["providers"] = ["opencode-go"]
    cfg["cli"]["opencode"]["tiers"] = {"standard": ["opencode/a-free"]}
    write(kit, cfg)
    assert config.load() == cfg


# C4 - Surface da needs-input-reply
def test_ask_wait_validation(kit: Kit, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(kit.home))
    base = kit.config_text()
    kit.write_config(base + '\n[ask]\nwait = "abc"\n')
    with pytest.raises(config.ConfigError) as raised:
        config.load()
    assert "ask.wait" in str(raised.value)
    kit.write_config(base + '\n[ask]\nwait = "0"\n')
    assert config.load()["ask"]["wait"] == "0"
