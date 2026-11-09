"""Provas do `setup cli add`, `setup default` e `login` (checks C112-C115; AC 91-94, doors 19 e 20).

Box limpo (`fresh`): nenhuma CLI real no `PATH`, só o `curl` falso, que entrega o instalador falso de cada CLI.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Kit, write_secret

from grokbot_kit import config, setup

INSTALLED_BIN = {
    "claude": Path(".local/bin/claude"),
    "opencode": Path(".opencode/bin/opencode"),
    "codex": Path(".grokbot-kit/bin/codex"),
}


def cli(kit: Kit, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    saved = kit.env
    kit.env = {**saved, **extra}
    try:
        return kit.cli(*args)
    finally:
        kit.env = saved


def calls_of(kit: Kit, tool: str) -> list[dict[str, Any]]:
    return [c for c in kit.calls() if c["tool"] == tool]


def install(kit: Kit, *tools: str) -> None:
    for tool in tools:
        result = cli(kit, "setup", "cli", "add", tool)
        assert result.returncode == 0, result.stderr


# C112 - AC 91, door 19
@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_cli_add_exit_codes_and_bin(fresh: Kit, tool: str) -> None:
    failed = cli(fresh, "setup", "cli", "add", tool, FAKE_INSTALL_FAIL="1")
    assert failed.returncode == 1
    assert calls_of(fresh, f"installer:{tool}")
    assert not (fresh.home / ".config" / "grokbot-kit" / "config.toml").exists()

    result = cli(fresh, "setup", "cli", "add", tool)
    assert result.returncode == 0, result.stderr
    expected = fresh.home / INSTALLED_BIN[tool]
    cfg = fresh.config()
    assert cfg["cli"][tool]["bin"] == str(expected)
    assert os.path.isabs(cfg["cli"][tool]["bin"])
    assert tool in cfg["setup"]["installed"]
    assert "default_cli" not in cfg["setup"]
    assert [c["argv"] for c in calls_of(fresh, tool)] == [["--version"]]

    unknown = cli(fresh, "setup", "cli", "add", "aider")
    assert unknown.returncode == 2


@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_cli_add_exit_codes_and_bin_version_fails(fresh: Kit, tool: str) -> None:
    result = cli(fresh, "setup", "cli", "add", tool, FAKE_VERSION_EXIT="1")
    assert result.returncode == 1
    assert [c["argv"] for c in calls_of(fresh, tool)] == [["--version"]]
    assert not (fresh.home / ".config" / "grokbot-kit" / "config.toml").exists()


def test_cli_add_exit_codes_and_bin_keeps_config(fresh: Kit) -> None:
    install(fresh, "opencode")
    before = fresh.config_text()
    assert cli(fresh, "setup", "cli", "add", "claude", FAKE_INSTALL_FAIL="1").returncode == 1
    assert fresh.config_text() == before
    install(fresh, "claude")
    assert fresh.config()["setup"]["installed"] == ["opencode", "claude"]


def test_cli_add_exit_codes_and_bin_installer_args(fresh: Kit) -> None:
    install(fresh, "opencode", "codex")
    assert calls_of(fresh, "installer:opencode")[0]["argv"] == ["--no-modify-path"]
    codex = calls_of(fresh, "installer:codex")[0]
    kit_bin = fresh.home / ".grokbot-kit" / "bin"
    codex_home = fresh.home / ".grokbot-kit" / "codex-home"
    assert codex["codex_home"] == str(codex_home)
    assert codex["codex_install_dir"] == str(kit_bin)
    assert codex["path"].split(os.pathsep)[0] == str(kit_bin)
    assert (codex_home.stat().st_mode & 0o777) == 0o700
    assert fresh.config()["cli"]["codex"]["codex_home"] == "~/.grokbot-kit/codex-home"
    assert not (fresh.home / ".codex").exists()
    assert not (fresh.home / ".local" / "bin" / "codex").exists()


def test_cli_add_exit_codes_and_bin_layer(tmp_path: Path) -> None:
    codex_home = tmp_path / "ch"
    claude = setup.installer("claude", tmp_path, codex_home)
    assert claude.argv == ["bash", "-c", "curl -fsSL https://claude.ai/install.sh | bash"]
    assert claude.env == {}
    assert claude.bin == tmp_path / ".local" / "bin" / "claude"
    opencode = setup.installer("opencode", tmp_path, codex_home)
    assert opencode.argv == ["bash", "-c", "curl -fsSL https://opencode.ai/install | bash -s -- --no-modify-path"]
    assert opencode.env == {}
    assert opencode.bin == tmp_path / ".opencode" / "bin" / "opencode"
    codex = setup.installer("codex", tmp_path, codex_home)
    assert codex.argv == ["sh", "-c", "curl -fsSL https://chatgpt.com/codex/install.sh | sh"]
    assert codex.env == {"CODEX_HOME": str(codex_home), "CODEX_INSTALL_DIR": str(tmp_path / ".grokbot-kit" / "bin")}
    assert codex.bin == tmp_path / ".grokbot-kit" / "bin" / "codex"


def test_cli_add_exit_codes_and_bin_default(fresh: Kit) -> None:
    assert cli(fresh, "setup", "default", "claude").returncode == 2
    install(fresh, "opencode")
    assert cli(fresh, "setup", "default", "claude").returncode == 2
    assert cli(fresh, "setup", "default", "aider").returncode == 2
    assert cli(fresh, "setup", "default", "opencode").returncode == 0
    assert fresh.config()["setup"]["default_cli"] == "opencode"


# C113 - AC 92, door 20
def test_login_codex_methods_and_home(fresh: Kit) -> None:
    install(fresh, "codex")
    codex_home = fresh.home / ".grokbot-kit" / "codex-home"

    result = cli(fresh, "login", "codex")
    assert result.returncode == 0, result.stderr
    call = calls_of(fresh, "codex")[-1]
    assert call["argv"] == ["login", "--device-auth"]
    assert call["codex_home"] == str(codex_home)
    assert (codex_home / "auth.json").exists()
    assert cli(fresh, "login", "codex", "--method", "subscription", FAKE_LOGIN_EXIT="1").returncode == 1

    key = "sk-test-codex-not-real"
    write_secret(fresh.home, "codex-api-key", key + "\n")
    result = cli(fresh, "login", "codex", "--method", "api-key")
    assert result.returncode == 0, result.stderr
    call = calls_of(fresh, "codex")[-1]
    assert call["argv"] == ["login", "--with-api-key"]
    assert call["stdin"] == key + "\n"
    assert call["codex_home"] == str(codex_home)
    assert key not in result.stdout + result.stderr
    assert key not in fresh.config_text()
    assert cli(fresh, "login", "codex", "--method", "api-key", FAKE_LOGIN_EXIT="1").returncode == 1
    assert not (fresh.home / ".codex").exists()


def test_login_codex_methods_and_home_secret(fresh: Kit) -> None:
    install(fresh, "codex")
    before = len(calls_of(fresh, "codex"))
    assert cli(fresh, "login", "codex", "--method", "api-key").returncode == 1
    write_secret(fresh.home, "codex-api-key", "sk-aberta\n", mode=0o644)
    assert cli(fresh, "login", "codex", "--method", "api-key").returncode == 1
    write_secret(fresh.home, "outra-key", "sk-outra\n")
    assert cli(fresh, "login", "codex", "--method", "api-key", "--secret", "outra-key").returncode == 0
    assert [c["stdin"] for c in calls_of(fresh, "codex")[before:]] == ["sk-outra\n"]


def test_login_codex_methods_and_home_configured(fresh: Kit) -> None:
    install(fresh, "codex")
    other = fresh.home / "outro-codex-home"
    cfg = fresh.config()
    cfg["cli"]["codex"]["codex_home"] = str(other)
    fresh.write_config(config.dump(cfg))
    assert cli(fresh, "login", "codex").returncode == 0
    assert calls_of(fresh, "codex")[-1]["codex_home"] == str(other)
    assert (other / "auth.json").exists()


# C114 - AC 93, door 20
def test_login_claude_methods_and_env_scope(fresh: Kit) -> None:
    install(fresh, "claude", "opencode")
    result = cli(fresh, "login", "claude")
    assert result.returncode == 0, result.stderr
    assert calls_of(fresh, "claude")[-1]["argv"] == ["auth", "login"]
    assert cli(fresh, "login", "claude", FAKE_LOGIN_EXIT="1").returncode == 1

    key = "sk-ant-test-not-real"
    assert cli(fresh, "login", "claude", "--method", "api-key").returncode == 1
    write_secret(fresh.home, "claude-api-key", key + "\n")
    before = len(calls_of(fresh, "claude"))
    result = cli(fresh, "login", "claude", "--method", "api-key")
    assert result.returncode == 0, result.stderr
    assert len(calls_of(fresh, "claude")) == before
    assert fresh.config()["cli"]["claude"]["api_key_secret"] == "claude-api-key"
    assert key not in fresh.config_text() + result.stdout + result.stderr

    cfg = fresh.config()
    cfg["cli"]["claude"]["models"] = ["sonnet"]
    cfg["cli"]["opencode"]["models"] = ["opencode/free"]
    cfg["routes"] = {"bot-a": {"sinks": ["arquivo"]}}
    cfg["sinks"] = {"arquivo": {"type": "file", "path": str(fresh.sink)}}
    fresh.write_config(config.dump(cfg))

    result = fresh.run("--tool", "claude", "--model", "sonnet", "--target", "bot-a", "--label", "chave", "--", "oi")
    assert result.returncode == 0, result.stderr
    assert fresh.launched()["env"]["ANTHROPIC_API_KEY"] == key
    task_dir = fresh.task_dir()
    for path in task_dir.rglob("*"):
        if path.is_file():
            assert key not in path.read_text(encoding="utf-8", errors="replace"), path
    assert key not in result.stdout + result.stderr + fresh.config_text()
    assert key not in fresh.sink.read_text(encoding="utf-8")

    result = fresh.run(
        "--tool", "opencode", "--model", "opencode/free", "--target", "bot-a", "--label", "oc", "--", "oi"
    )
    assert result.returncode == 0, result.stderr
    assert "ANTHROPIC_API_KEY" not in fresh.launched()["env"]

    assert cli(fresh, "login", "claude").returncode == 0
    assert "api_key_secret" not in fresh.config()["cli"]["claude"]


def test_login_claude_methods_and_env_scope_bad_secret(fresh: Kit) -> None:
    install(fresh, "claude")
    write_secret(fresh.home, "claude-api-key", "sk-ant\n")
    assert cli(fresh, "login", "claude", "--method", "api-key").returncode == 0
    cfg = fresh.config()
    cfg["cli"]["claude"]["models"] = ["sonnet"]
    cfg["routes"] = {"bot-a": {"sinks": ["arquivo"]}}
    cfg["sinks"] = {"arquivo": {"type": "file", "path": str(fresh.sink)}}
    fresh.write_config(config.dump(cfg))
    os.chmod(fresh.home / ".secrets" / "grokbot-kit" / "claude-api-key", 0o644)
    result = fresh.run("--tool", "claude", "--model", "sonnet", "--target", "bot-a", "--label", "chave", "--", "oi")
    assert result.returncode == 2
    assert "claude-api-key" in result.stderr
    assert fresh.tasks() == []


# C115 - AC 94 (o `doctor` "OK" inclui o plugin do opencode instalado, door 24)
def test_login_opencode_and_free_without_login(fresh: Kit) -> None:
    install(fresh, "opencode")
    assert cli(fresh, "setup", "default", "opencode").returncode == 0
    assert cli(fresh, "install", "opencode").returncode == 0
    assert not [c for c in calls_of(fresh, "opencode") if c["argv"][:2] == ["auth", "login"]]
    doctor = cli(fresh, "doctor", "--json")
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert json.loads(doctor.stdout)["cli"]["opencode"]["login"]["logged_in"] is False

    for method in ([], ["--method", "subscription"], ["--method", "api-key"]):
        result = cli(fresh, "login", "opencode", *method)
        assert result.returncode == 0, result.stderr
        assert calls_of(fresh, "opencode")[-1]["argv"] == ["auth", "login"]
    assert cli(fresh, "login", "opencode", FAKE_LOGIN_EXIT="1").returncode == 1
