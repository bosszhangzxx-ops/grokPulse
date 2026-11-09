"""Provas do `setup cli upgrade <tool>` (needs-input-reply, C43-C47; AC 30-33, door 7).

Box limpo (`fresh`) com o `curl` e os instaladores falsos de `tests/fakes/installers/`; o instalador grava a versão
que a CLI instalada passa a responder (`FAKE_INSTALLED_VERSION`).
"""

import os
from pathlib import Path

import pytest
from conftest import Kit
from test_setup import calls_of, cli

PLUGIN = Path(".config/opencode/plugins/grokbot-kit.ts")


def installed(kit: Kit, tool: str, version: str) -> None:
    result = cli(kit, "setup", "cli", "add", tool, FAKE_INSTALLED_VERSION=version)
    assert result.returncode == 0, result.stderr


# C43 - AC 30, door 7
def test_upgrade_prints_versions(fresh: Kit) -> None:
    installed(fresh, "opencode", "opencode v1.19.3")
    result = cli(fresh, "setup", "cli", "upgrade", "opencode", FAKE_INSTALLED_VERSION="opencode v2.2.4")
    assert result.returncode == 0, result.stderr
    assert "opencode 1.19.3 -> 2.2.4" in result.stdout.splitlines()
    assert [c["argv"] for c in calls_of(fresh, "installer:opencode")] == [["--no-modify-path"]] * 2

    same = cli(fresh, "setup", "cli", "upgrade", "opencode", FAKE_INSTALLED_VERSION="opencode v2.2.4")
    assert same.returncode == 0, same.stderr
    assert "opencode 2.2.4 is already the latest" in same.stdout.splitlines()


# C44 - AC 30
@pytest.mark.parametrize("tool", ["claude", "codex"])
def test_upgrade_each_tool(fresh: Kit, tool: str) -> None:
    installed(fresh, tool, "1.0.0 (fake)")
    result = cli(fresh, "setup", "cli", "upgrade", tool, FAKE_INSTALLED_VERSION="1.1.0 (fake)")
    assert result.returncode == 0, result.stderr
    assert f"{tool} 1.0.0 -> 1.1.0" in result.stdout.splitlines()
    calls = calls_of(fresh, f"installer:{tool}")
    assert len(calls) == 2
    assert calls[1] == {**calls[0], "path": calls[1]["path"]}
    if tool == "codex":
        assert calls[1]["codex_home"] == str(fresh.home / ".grokbot-kit" / "codex-home")


# C45 - AC 31
def test_upgrade_not_installed(fresh: Kit) -> None:
    installed(fresh, "opencode", "opencode v2.2.4")
    result = cli(fresh, "setup", "cli", "upgrade", "claude")
    assert result.returncode == 2
    assert "claude is not installed by grokbot-kit; run: grokbot-kit setup cli add claude" in result.stderr
    assert calls_of(fresh, "installer:claude") == []
    assert cli(fresh, "setup", "cli", "upgrade", "foo").returncode == 2


def test_upgrade_not_installed_without_config(fresh: Kit) -> None:
    result = cli(fresh, "setup", "cli", "upgrade", "opencode")
    assert result.returncode == 2
    assert "opencode is not installed by grokbot-kit" in result.stderr


# C46 - AC 32
@pytest.mark.parametrize("failure", ["FAKE_INSTALL_FAIL", "FAKE_VERSION_EXIT"])
def test_upgrade_failure_keeps_config(fresh: Kit, failure: str) -> None:
    installed(fresh, "opencode", "opencode v1.19.3")
    before = fresh.config_text()
    result = cli(fresh, "setup", "cli", "upgrade", "opencode", **{failure: "1"})
    assert result.returncode == 1
    assert result.stderr.strip()
    assert fresh.config_text() == before


# C47 - AC 33
def test_upgrade_rewrites_plugin(fresh: Kit) -> None:
    installed(fresh, "opencode", "opencode v1.19.3")
    assert fresh.cli("install", "opencode").returncode == 0
    plugin = fresh.home / PLUGIN
    assert plugin.read_text(encoding="utf-8").startswith("// grokbot-kit opencode plugin for opencode 1\n")
    result = cli(fresh, "setup", "cli", "upgrade", "opencode", FAKE_INSTALLED_VERSION="opencode v2.2.4")
    assert result.returncode == 0, result.stderr
    assert "opencode plugin rewritten for opencode 2" in result.stdout.splitlines()
    assert plugin.read_text(encoding="utf-8").startswith("// grokbot-kit opencode plugin for opencode 2\n")


def test_upgrade_rewrites_plugin_absent(fresh: Kit) -> None:
    installed(fresh, "opencode", "opencode v1.19.3")
    result = cli(fresh, "setup", "cli", "upgrade", "opencode", FAKE_INSTALLED_VERSION="opencode v2.2.4")
    assert result.returncode == 0, result.stderr
    assert not (fresh.home / PLUGIN).exists()


def test_upgrade_rewrites_plugin_unwritable(fresh: Kit) -> None:
    installed(fresh, "opencode", "opencode v1.19.3")
    assert fresh.cli("install", "opencode").returncode == 0
    plugins = (fresh.home / PLUGIN).parent
    os.chmod(plugins, 0o500)
    try:
        result = cli(fresh, "setup", "cli", "upgrade", "opencode", FAKE_INSTALLED_VERSION="opencode v2.2.4")
    finally:
        os.chmod(plugins, 0o700)
    assert result.returncode == 1
    assert "run: grokbot-kit install opencode" in result.stderr
