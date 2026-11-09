"""Provas de `grokbot-kit setup models refresh` (checks C104, C105 e C106; AC 84-86, doors 12 e 16).

Na fronteira, o subprocesso `grokbot-kit` com as CLIs falsas no `PATH`; na própria camada, `models.discover`.
"""

import json
import os
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
from conftest import FAKES, Kit

from grokbot_kit import models

RFC3339_UTC = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"


def read_config(kit: Kit) -> dict[str, Any]:
    return tomllib.loads(kit.config_text())


def calls(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def refresh(kit: Kit, tmp_path: Path, *args: str, **fake: str) -> Any:
    env = {**kit.env, "FAKE_CALLS": str(tmp_path / "calls.jsonl"), **fake}
    kit.env, saved = env, kit.env
    try:
        return kit.cli("setup", "models", "refresh", *args)
    finally:
        kit.env = saved


# C104 - AC 84
def test_opencode_models_exact(kit: Kit, tmp_path: Path) -> None:
    printed = "opencode/grok-code\nanthropic/claude-x-1\n\n  openai/gpt-5  \nopencode/big-pickle\n"
    result = refresh(kit, tmp_path, "opencode", FAKE_OPENCODE_MODELS=printed)
    assert result.returncode == 0, result.stderr
    cli = read_config(kit)["cli"]["opencode"]
    assert cli["models"] == ["opencode/grok-code", "anthropic/claude-x-1", "openai/gpt-5", "opencode/big-pickle"]
    assert isinstance(cli["models_discovered_at"], str)
    assert re.match(RFC3339_UTC, cli["models_discovered_at"])
    made = calls(tmp_path / "calls.jsonl")
    assert [c["argv"] for c in made] == [["models"]]
    assert made[0]["stdin_target"] == "/dev/null"


def test_opencode_models_exact_keeps_tiers_and_other_tools(kit: Kit, tmp_path: Path) -> None:
    before = read_config(kit)
    result = refresh(kit, tmp_path, "opencode", FAKE_OPENCODE_MODELS="opencode/free-model\nnovo/x\n")
    assert result.returncode == 0, result.stderr
    after = read_config(kit)
    assert after["cli"]["opencode"]["tiers"] == before["cli"]["opencode"]["tiers"]
    assert after["cli"]["claude"] == before["cli"]["claude"]
    assert after["routes"] == before["routes"]


@pytest.mark.parametrize(("printed", "exit_code"), [("a/x\n", "1"), ("", "0"), ("\n  \n", "0")])
def test_opencode_models_exact_failure_exit_1_keeps_config(
    kit: Kit, tmp_path: Path, printed: str, exit_code: str
) -> None:
    before = kit.config_text()
    result = refresh(kit, tmp_path, "opencode", FAKE_OPENCODE_MODELS=printed, FAKE_MODELS_EXIT=exit_code)
    assert result.returncode == 1
    assert kit.config_text() == before


def test_opencode_models_exact_add_exit_2(kit: Kit, tmp_path: Path) -> None:
    before = kit.config_text()
    result = refresh(kit, tmp_path, "opencode", "--add", "a/x", FAKE_OPENCODE_MODELS="a/x\n")
    assert result.returncode == 2
    assert kit.config_text() == before
    assert calls(tmp_path / "calls.jsonl") == []


def test_opencode_models_exact_unknown_tool_exit_2(kit: Kit, tmp_path: Path) -> None:
    result = refresh(kit, tmp_path, "gemini")
    assert result.returncode == 2


def test_opencode_models_exact_discover_layer(kit: Kit, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", f"{FAKES}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_OPENCODE_MODELS", "b/y\na/x\n\n")
    found = models.discover("opencode", {}, [])
    assert (found.ids, found.rejected, found.failed) == (["b/y", "a/x"], [], False)


# C105 - AC 85
def test_claude_aliases_and_accepted_ids(kit: Kit, tmp_path: Path) -> None:
    result = refresh(
        kit,
        tmp_path,
        "claude",
        "--add",
        "claude-x-1",
        "--add",
        "inventado-123",
        "--add",
        "claude-erro-0",
        FAKE_ACCEPT_MODELS=json.dumps(["claude-x-1", "claude-erro-0"]),
        FAKE_ERROR_EXIT0=json.dumps(["claude-erro-0"]),
    )
    assert result.returncode == 1, "um id recusado faz o refresh sair com 1"
    assert "inventado-123" in result.stderr
    assert "claude-erro-0" in result.stderr
    assert "not found" not in result.stderr, "a saída da CLI não vai para o stderr do kit"
    assert read_config(kit)["cli"]["claude"]["models"] == ["haiku", "sonnet", "opus", "claude-x-1"]
    made = calls(tmp_path / "calls.jsonl")
    tested = [c["argv"][c["argv"].index("--model") + 1] for c in made]
    assert sorted(tested) == ["claude-erro-0", "claude-x-1", "inventado-123"], "os aliases não são testados"
    for c in made:
        assert c["argv"][:3] == ["-p", "--output-format", "json"]
        assert c["stdin_target"] == "/dev/null"
        assert c["cwd"] != str(kit.home)


def test_claude_aliases_and_accepted_ids_retests_stored_ids(kit: Kit, tmp_path: Path) -> None:
    kit.write_config(
        kit.config_text().replace('models = ["sonnet"]', 'models = ["sonnet", "claude-velho", "claude-ok"]')
    )
    assert read_config(kit)["cli"]["claude"]["models"] == ["sonnet", "claude-velho", "claude-ok"]
    result = refresh(kit, tmp_path, "claude", FAKE_ACCEPT_MODELS=json.dumps(["claude-ok"]))
    assert result.returncode == 1
    assert read_config(kit)["cli"]["claude"]["models"] == ["haiku", "sonnet", "opus", "claude-ok"]


def test_claude_aliases_and_accepted_ids_all_accepted_exit_0(kit: Kit, tmp_path: Path) -> None:
    result = refresh(kit, tmp_path, "claude", "--add", "claude-x-1", FAKE_ACCEPT_MODELS=json.dumps(["claude-x-1"]))
    assert result.returncode == 0, result.stderr
    assert read_config(kit)["cli"]["claude"]["models"] == ["haiku", "sonnet", "opus", "claude-x-1"]


def test_claude_aliases_and_accepted_ids_discover_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", f"{FAKES}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_ACCEPT_MODELS", json.dumps(["x-1"]))
    found = models.discover("claude", {"models": ["opus", "x-velho"]}, ["x-1", "x-1"])
    assert found.ids == ["haiku", "sonnet", "opus", "x-1"]
    assert [r[0] for r in found.rejected] == ["x-velho"]


# C106 - AC 86
def test_codex_accepted_ids_only(kit: Kit, tmp_path: Path) -> None:
    result = refresh(
        kit,
        tmp_path,
        "codex",
        "--add",
        "gpt-a",
        "--add",
        "gpt-b",
        "--add",
        "gpt-erro-0",
        FAKE_ACCEPT_MODELS=json.dumps(["gpt-a", "gpt-erro-0"]),
        FAKE_ERROR_EXIT0=json.dumps(["gpt-erro-0"]),
    )
    assert result.returncode == 1
    assert "gpt-b" in result.stderr
    assert "gpt-erro-0" in result.stderr
    assert read_config(kit)["cli"]["codex"]["models"] == ["gpt-a"]
    made = calls(tmp_path / "calls.jsonl")
    tested = [c["argv"][c["argv"].index("-m") + 1] for c in made]
    assert sorted(tested) == ["gpt-a", "gpt-b", "gpt-erro-0", "gpt-test"], "o id já gravado também é testado"
    for c in made:
        assert c["argv"][:3] == ["exec", "--json", "--skip-git-repo-check"]
        assert c["codex_home"] == str(kit.home / ".grokbot-kit" / "codex-home")
        assert c["stdin_target"] == "/dev/null"


def test_codex_accepted_ids_only_none_accepted_keeps_config(kit: Kit, tmp_path: Path) -> None:
    before = kit.config_text()
    result = refresh(kit, tmp_path, "codex", "--add", "gpt-b", FAKE_ACCEPT_MODELS="[]")
    assert result.returncode == 1
    assert kit.config_text() == before, "sem nenhum id aceito o config não muda"


def test_codex_accepted_ids_only_discover_layer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", f"{FAKES}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_ACCEPT_MODELS", json.dumps(["gpt-a", "gpt-c"]))
    monkeypatch.setenv("FAKE_CALLS", str(tmp_path / "calls.jsonl"))
    found = models.discover("codex", {"models": ["gpt-c"], "codex_home": str(tmp_path / "ch")}, ["gpt-a", "gpt-b"])
    assert found.ids == ["gpt-c", "gpt-a"]
    assert [r[0] for r in found.rejected] == ["gpt-b"]
    assert {c["codex_home"] for c in calls(tmp_path / "calls.jsonl")} == {str(tmp_path / "ch")}


def test_codex_accepted_ids_only_no_tool_refreshes_installed(kit: Kit, tmp_path: Path) -> None:
    kit.write_config(kit.config_text().replace('installed = ["opencode", "claude", "codex"]', 'installed = ["codex"]'))
    kit.write_config(kit.config_text().replace('default_cli = "opencode"', 'default_cli = "codex"'))
    result = refresh(kit, tmp_path, FAKE_ACCEPT_MODELS=json.dumps(["gpt-test"]))
    assert result.returncode == 0, result.stderr
    assert {c["tool"] for c in calls(tmp_path / "calls.jsonl")} == {"codex"}


# model-setup-docs: `--json` com o `provider` de cada id (door 1)
def opencode_and_claude(kit: Kit) -> None:
    kit.write_config(
        kit.config_text().replace('installed = ["opencode", "claude", "codex"]', 'installed = ["opencode", "claude"]')
    )


def json_items(stdout: str) -> list[dict[str, Any]]:
    out = json.loads(stdout)
    assert list(out) == ["models"]
    items: list[dict[str, Any]] = out["models"]
    return items


# C1 - AC 1, door 1
def test_refresh_json_shape(kit: Kit, tmp_path: Path) -> None:
    opencode_and_claude(kit)
    result = refresh(
        kit,
        tmp_path,
        "--json",
        FAKE_OPENCODE_MODELS="opencode/a-free\nopencode-go/b\n",
        FAKE_ACCEPT_MODELS=json.dumps(["sonnet"]),
    )
    assert result.returncode == 0, result.stderr
    assert not any("\t" in line for line in result.stdout.splitlines())
    items = json_items(result.stdout)
    assert items == [
        {"tool": "opencode", "id": "opencode/a-free", "provider": "opencode"},
        {"tool": "opencode", "id": "opencode-go/b", "provider": "opencode-go"},
        {"tool": "claude", "id": "haiku", "provider": None},
        {"tool": "claude", "id": "sonnet", "provider": None},
        {"tool": "claude", "id": "opus", "provider": None},
    ]
    assert all(list(item) == ["tool", "id", "provider"] for item in items)


# C2 - AC 2
def test_refresh_json_provider(kit: Kit, tmp_path: Path) -> None:
    result = refresh(
        kit,
        tmp_path,
        "--json",
        FAKE_OPENCODE_MODELS="opencode/a-free\nopencode-go/b\nollama/x/y\n",
        FAKE_ACCEPT_MODELS=json.dumps(["gpt-test"]),
    )
    assert result.returncode == 0, result.stderr
    provider = {(i["tool"], i["id"]): i["provider"] for i in json_items(result.stdout)}
    assert provider[("opencode", "opencode/a-free")] == "opencode"
    assert provider[("opencode", "opencode-go/b")] == "opencode-go"
    assert provider[("opencode", "ollama/x/y")] == "ollama"
    assert provider[("claude", "sonnet")] is None
    assert provider[("codex", "gpt-test")] is None


def test_refresh_json_provider_layer() -> None:
    assert models.provider("opencode", "ollama/x/y") == "ollama"
    assert models.provider("opencode", "opencode-go/glm-5.3") == "opencode-go"
    assert models.provider("claude", "sonnet") is None
    assert models.provider("codex", "openai/gpt") is None


# C3 - AC 1, Observable
def test_refresh_json_partial_failure(kit: Kit, tmp_path: Path) -> None:
    opencode_and_claude(kit)
    result = refresh(
        kit,
        tmp_path,
        "--json",
        FAKE_OPENCODE_MODELS="opencode/a-free\n",
        FAKE_MODELS_EXIT="1",
        FAKE_ACCEPT_MODELS=json.dumps(["sonnet"]),
    )
    assert result.returncode == 1
    items = json_items(result.stdout)
    assert [i["tool"] for i in items] == ["claude", "claude", "claude"]
    assert "opencode" in result.stderr
    assert "exited 1" in result.stderr


# C4 - AC 3
def test_refresh_text_unchanged(kit: Kit, tmp_path: Path) -> None:
    result = refresh(kit, tmp_path, "opencode", FAKE_OPENCODE_MODELS="opencode/a-free\nopencode-go/b\n")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["opencode\topencode/a-free", "opencode\topencode-go/b"]
    assert not any(line.startswith("{") for line in result.stdout.splitlines())
