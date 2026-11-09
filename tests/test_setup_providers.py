"""Provas do `setup providers opencode <provider>...` (checks C5, C6 e C9; AC 4-7 e 10, doors 2 e 3)."""

import json

import pytest
from conftest import Kit, default_config

OPENCODE_MODELS = ["opencode/a-free", "opencode-go/b"]


def with_models(
    kit: Kit, installed: tuple[str, ...] = ("opencode", "claude", "codex"), standard: str = "opencode-go/b"
) -> None:
    text = default_config(kit.sink, installed).replace(
        'models = ["opencode/free-model"]', f"models = {json.dumps(OPENCODE_MODELS)}"
    )
    kit.write_config(text.replace('standard = ["opencode/free-model"]', f'standard = ["{standard}"]'))


# C5 - AC 4, door 2
def test_providers_written(kit: Kit) -> None:
    with_models(kit)
    before = kit.config()
    result = kit.cli("setup", "providers", "opencode", "opencode-go")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "opencode providers: opencode-go\n"
    after = kit.config()
    assert after["cli"]["opencode"]["providers"] == ["opencode-go"]
    del after["cli"]["opencode"]["providers"]
    assert after == before, "models, tiers, bin e o resto não mudam"


def test_providers_written_keeps_order(kit: Kit) -> None:
    with_models(kit)
    result = kit.cli("setup", "providers", "opencode", "opencode-go", "opencode")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "opencode providers: opencode-go, opencode\n"
    assert kit.config()["cli"]["opencode"]["providers"] == ["opencode-go", "opencode"]


# C6 - AC 5, AC 6, AC 7
@pytest.mark.parametrize(
    ("installed", "args", "expected"),
    [
        (("opencode", "claude", "codex"), ("claude", "x"), ["providers apply only to opencode"]),
        (("claude",), ("opencode", "opencode-go"), ["grokbot-kit setup cli add opencode"]),
        (("opencode", "claude", "codex"), ("opencode", "nada"), ["nada", "grokbot-kit setup models refresh opencode"]),
    ],
)
def test_providers_refused(kit: Kit, installed: tuple[str, ...], args: tuple[str, ...], expected: list[str]) -> None:
    with_models(kit, installed)
    before = kit.config_text()
    result = kit.cli("setup", "providers", *args)
    assert result.returncode == 2
    for text in expected:
        assert text in result.stderr
    assert kit.config_text() == before


# C9 - AC 10, door 3
def test_providers_warns_tier_outside(kit: Kit) -> None:
    with_models(kit, standard="opencode/a-free")
    result = kit.cli("setup", "providers", "opencode", "opencode-go")
    assert result.returncode == 0, result.stderr
    assert kit.config()["cli"]["opencode"]["providers"] == ["opencode-go"]
    warning = [line for line in result.stderr.splitlines() if "cli.opencode.tiers.standard" in line]
    assert len(warning) == 1
    assert "opencode/a-free" in warning[0]
