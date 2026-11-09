"""Provas do `setup tiers <tool> <tier> <id>...` (door 22; a skill aplica a tabela de tiers do AC 109)."""

import json

import pytest
from conftest import Kit, default_config

OPENCODE_MODELS = ["opencode/a-free", "opencode/b-free", "provider/pago"]


def with_models(kit: Kit, installed: tuple[str, ...] = ("opencode", "claude", "codex")) -> None:
    text = default_config(kit.sink, installed).replace(
        'models = ["opencode/free-model"]', f"models = {json.dumps(OPENCODE_MODELS)}"
    )
    kit.write_config(text.replace('standard = ["opencode/free-model"]', 'standard = ["provider/pago"]'))


def test_setup_tiers_writes_ordered_list(kit: Kit) -> None:
    with_models(kit)
    before = kit.config()
    result = kit.cli("setup", "tiers", "opencode", "trivial", "opencode/b-free", "opencode/a-free")
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.strip().splitlines()) == 1
    after = kit.config()
    assert after["cli"]["opencode"]["tiers"]["trivial"] == ["opencode/b-free", "opencode/a-free"]
    assert after["cli"]["opencode"]["tiers"]["standard"] == ["provider/pago"]
    assert after["cli"]["opencode"]["models"] == OPENCODE_MODELS
    del after["cli"]["opencode"]["tiers"]["trivial"]
    assert after == before


def test_setup_tiers_replaces_existing_tier(kit: Kit) -> None:
    with_models(kit)
    result = kit.cli("setup", "tiers", "opencode", "standard", "opencode/a-free", "provider/pago")
    assert result.returncode == 0, result.stderr
    assert kit.config()["cli"]["opencode"]["tiers"]["standard"] == ["opencode/a-free", "provider/pago"]


def test_setup_tiers_refuses_undiscovered_id(kit: Kit) -> None:
    with_models(kit)
    before = kit.config_text()
    result = kit.cli("setup", "tiers", "opencode", "trivial", "opencode/a-free", "inventado-123")
    assert result.returncode == 2
    assert "inventado-123" in result.stderr
    assert "grokbot-kit setup models refresh opencode" in result.stderr
    assert kit.config_text() == before


def test_setup_tiers_refuses_tool_not_installed(kit: Kit) -> None:
    with_models(kit, installed=("opencode",))
    before = kit.config_text()
    result = kit.cli("setup", "tiers", "claude", "standard", "sonnet")
    assert result.returncode == 2
    assert "grokbot-kit setup cli add claude" in result.stderr
    assert kit.config_text() == before


@pytest.mark.parametrize(
    "args",
    [
        ("aider", "standard", "x"),
        ("opencode", "huge", "opencode/a-free"),
        ("opencode", "trivial"),
    ],
)
def test_setup_tiers_usage_errors(kit: Kit, args: tuple[str, ...]) -> None:
    with_models(kit)
    before = kit.config_text()
    assert kit.cli("setup", "tiers", *args).returncode == 2
    assert kit.config_text() == before


# model-setup-docs: a restrição de provedor (door 3)
PROVIDER_MODELS = ["opencode/a-free", "opencode-go/b"]


def with_providers(kit: Kit, providers: list[str] | None) -> None:
    text = default_config(kit.sink).replace(
        'models = ["opencode/free-model"]', f"models = {json.dumps(PROVIDER_MODELS)}"
    )
    text = text.replace('standard = ["opencode/free-model"]', 'standard = ["opencode-go/b"]')
    if providers is not None:
        text = text.replace("[cli.opencode.tiers]", f"providers = {json.dumps(providers)}\n[cli.opencode.tiers]", 1)
    kit.write_config(text)


# C7 - AC 8, door 3
def test_tiers_provider_outside(kit: Kit) -> None:
    with_providers(kit, ["opencode-go"])
    assert kit.config()["cli"]["opencode"]["providers"] == ["opencode-go"]
    before = kit.config_text()
    result = kit.cli("setup", "tiers", "opencode", "standard", "opencode-go/b", "opencode/a-free")
    assert result.returncode == 2
    assert "opencode/a-free" in result.stderr
    assert "grokbot-kit setup providers opencode" in result.stderr
    assert kit.config_text() == before


# C8 - AC 9
def test_tiers_no_providers(kit: Kit) -> None:
    with_providers(kit, None)
    result = kit.cli("setup", "tiers", "opencode", "standard", "opencode/a-free", "opencode-go/b")
    assert result.returncode == 0, result.stderr
    assert kit.config()["cli"]["opencode"]["tiers"]["standard"] == ["opencode/a-free", "opencode-go/b"]


# review do PR 29: `providers` só vale para o opencode; um campo manual em outra CLI não restringe os tiers dela
def test_tiers_providers_ignored_outside_opencode(kit: Kit) -> None:
    text = default_config(kit.sink).replace('models = ["sonnet"]', 'models = ["sonnet"]\nproviders = ["x"]', 1)
    kit.write_config(text)
    assert kit.config()["cli"]["claude"]["providers"] == ["x"]
    result = kit.cli("setup", "tiers", "claude", "standard", "sonnet")
    assert result.returncode == 0, result.stderr
    assert kit.config()["cli"]["claude"]["tiers"]["standard"] == ["sonnet"]
