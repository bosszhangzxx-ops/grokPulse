"""Provas do `grokbot-kit doctor` (checks C121 e C150; AC 100 e 126, doors 21 e 24)."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Kit, Receiver, closed_port_url, default_config, write_plugin, write_secret

from grokbot_kit import __version__, doctor

STATUS_COMMAND = {"claude": "claude auth status", "codex": "codex login status", "opencode": "opencode auth list"}


def run_doctor(kit: Kit, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    saved = kit.env
    kit.env = {
        **saved,
        "FAKE_CALLS": str(kit.home.parent / "calls.jsonl"),
        "FAKE_OPENCODE_CREDENTIALS": "2",
        # o `doctor` consulta o PyPI (`kit.update`); nos testes, nunca o de verdade
        "GROKBOT_KIT_PYPI_URL": closed_port_url(),
        **extra,
    }
    try:
        return kit.cli("doctor", *args)
    finally:
        kit.env = saved


def kit_python_version() -> str:
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    # o console script fica no `bin/` do venv ao lado do `python`; ler o shebang falha quando o caminho é longo e o
    # launcher vira `#!/bin/sh` com o interpretador na segunda linha
    python = str(Path(exe).parent / "python")
    code = "import platform; print(platform.python_version())"
    return subprocess.run([python, "-c", code], capture_output=True, text=True, check=True).stdout.strip()


def report(kit: Kit, **extra: str) -> tuple[int, dict[str, Any]]:
    result = run_doctor(kit, "--json", **extra)
    return result.returncode, json.loads(result.stdout)


# C121 - AC 100 (o "tudo OK" inclui o plugin do opencode instalado, door 24)
def test_fields_and_exit_codes(kit: Kit) -> None:
    assert kit.cli("install", "opencode").returncode == 0
    write_secret(kit.home, "bot-a-key", "crsr_x\n")
    code, out = report(kit)
    assert code == 0, out
    assert out["ok"] is True
    assert out["problems"] == []
    assert out["kit"]["version"] == __version__
    assert out["python"]["version"] == kit_python_version()
    assert os.path.isabs(out["python"]["executable"])
    assert out["setup"] == {"installed": ["opencode", "claude", "codex"], "default_cli": "opencode"}
    assert set(out["cli"]) == {"opencode", "claude", "codex"}
    for tool, cli in out["cli"].items():
        assert cli["version"] == f"9.9.9 ({tool} fake)"
        assert cli["login"]["command"] == STATUS_COMMAND[tool]
        assert cli["login"]["logged_in"] is True
        assert cli["login"]["method"] == "subscription"
        assert cli["default"] is (tool == "opencode")
        assert cli["tiers"] == {"trivial": 0, "standard": 1, "complex": 0}
    assert out["routes"] == {"bot-a": ["arquivo"]}
    assert out["secrets"] == {"bot-a-key": {"mode": "0600", "ok": True}}

    calls = [json.loads(line) for line in (kit.home.parent / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    codex_status = [c for c in calls if c["tool"] == "codex" and c["argv"] == ["login", "status"]]
    assert codex_status
    assert codex_status[0]["codex_home"] == str(kit.home / ".grokbot-kit" / "codex-home")

    text = run_doctor(kit)
    assert text.returncode == 0
    assert __version__ in text.stdout
    assert "9.9.9 (claude fake)" in text.stdout


def test_fields_and_exit_codes_open_secret(kit: Kit) -> None:
    write_secret(kit.home, "bot-a-key", "crsr_x\n", mode=0o644)
    code, out = report(kit)
    assert code == 1
    assert out["ok"] is False
    assert out["secrets"]["bot-a-key"] == {"mode": "0644", "ok": False}
    assert any("bot-a-key" in p for p in out["problems"])
    assert run_doctor(kit).returncode == 1


@pytest.mark.parametrize("tool", ["claude", "codex"])
def test_fields_and_exit_codes_logged_out(kit: Kit, tool: str) -> None:
    code, out = report(kit, FAKE_LOGGED_OUT=tool)
    assert code == 1
    assert out["cli"][tool]["login"]["logged_in"] is False
    assert any(tool in p and "grokbot-kit login" in p for p in out["problems"])


def test_fields_and_exit_codes_opencode_free(kit: Kit) -> None:
    assert kit.cli("install", "opencode").returncode == 0
    code, out = report(kit, FAKE_OPENCODE_CREDENTIALS="0")
    assert code == 0, out
    assert out["cli"]["opencode"]["login"]["logged_in"] is False


def test_fields_and_exit_codes_empty_box(tmp_path: Path, fresh: Kit) -> None:
    result = fresh.cli("doctor", "--json")
    assert result.returncode == 1
    out = json.loads(result.stdout)
    assert out["setup"] == {"installed": [], "default_cli": None}
    assert out["cli"] == {}
    assert any("grokbot-kit setup cli add" in p for p in out["problems"])


def cli_entry(**over: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "bin": "/x",
        "version": "1.0",
        "default": True,
        "login": {"command": "claude auth status", "method": "subscription", "logged_in": True},
        "tiers": {"trivial": 0, "standard": 1, "complex": 0},
    }
    entry.update(over)
    return entry


def base(**over: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "setup": {"installed": ["claude"], "default_cli": "claude"},
        "cli": {"claude": cli_entry()},
        "secrets": {},
    }
    out.update(over)
    return out


@pytest.mark.parametrize(
    ("out", "facts", "expect"),
    [
        (base(), {}, None),
        (base(setup={"installed": [], "default_cli": None}, cli={}), {}, "setup cli add"),
        (base(setup={"installed": ["claude"], "default_cli": None}), {}, "setup default"),
        (base(), {"config_error": "cli.claude.tiers.standard has 'x'"}, "cli.claude.tiers.standard"),
        (base(cli={"claude": cli_entry(version=None)}), {}, "--version"),
        (
            base(cli={"claude": cli_entry(login={"command": "c", "method": "subscription", "logged_in": False})}),
            {},
            "grokbot-kit login claude",
        ),
        (
            base(
                cli={
                    "opencode": cli_entry(
                        login={"command": "opencode auth list", "method": "subscription", "logged_in": None}
                    )
                },
                setup={"installed": ["opencode"], "default_cli": "opencode"},
            ),
            {},
            "opencode auth list",
        ),
        (
            base(
                cli={
                    "opencode": cli_entry(
                        login={"command": "opencode auth list", "method": "subscription", "logged_in": False}
                    )
                },
                setup={"installed": ["opencode"], "default_cli": "opencode"},
            ),
            {},
            None,
        ),
        (base(), {"secrets_dir_mode": 0o755}, "0700"),
        (base(secrets={"k": {"mode": "0640", "ok": False}}), {}, "k"),
        (base(), {"missing_secrets": ["bot-url"]}, "bot-url"),
    ],
)
def test_fields_and_exit_codes_layer(out: dict[str, Any], facts: dict[str, Any], expect: str | None) -> None:
    found = doctor.problems(out, facts)
    if expect is None:
        assert found == []
    else:
        assert len(found) == 1, found
        assert expect in found[0]


def plugin_file(kit: Kit) -> Path:
    return kit.home / ".config" / "opencode" / "plugins" / "grokbot-kit.ts"


# C150 - AC 126, door 24
def test_opencode_plugin_installed(kit: Kit) -> None:
    assert kit.cli("install", "opencode").returncode == 0
    code, out = report(kit)
    assert code == 0, out
    plugin = out["cli"]["opencode"]["plugin"]
    assert plugin["path"] == str(plugin_file(kit))
    assert plugin["ok"] is True
    assert isinstance(plugin["exe"], str) and os.path.isabs(plugin["exe"])
    assert not any("plugin" in p for p in out["problems"])
    assert "plugin: ok" in run_doctor(kit).stdout


def test_opencode_plugin_missing(kit: Kit) -> None:
    code, out = report(kit)
    assert code == 1
    plugin = out["cli"]["opencode"]["plugin"]
    assert plugin == {"path": str(plugin_file(kit)), "exe": None, "ok": False}
    found = [p for p in out["problems"] if "plugin" in p]
    assert len(found) == 1 and "grokbot-kit install opencode" in found[0]
    assert "plugin: missing" in run_doctor(kit).stdout


def test_opencode_plugin_other_executable(kit: Kit) -> None:
    assert kit.cli("install", "opencode").returncode == 0
    path = plugin_file(kit)
    current = report(kit)[1]["cli"]["opencode"]["plugin"]["exe"]
    text = path.read_text(encoding="utf-8")
    assert text.count(json.dumps(current)) == 1
    path.write_text(text.replace(json.dumps(current), json.dumps("/old/bin/grokbot-kit")), encoding="utf-8")
    code, out = report(kit)
    assert code == 1
    plugin = out["cli"]["opencode"]["plugin"]
    assert plugin["exe"] == "/old/bin/grokbot-kit"
    assert plugin["ok"] is False
    found = [p for p in out["problems"] if "plugin" in p]
    assert len(found) == 1
    assert "/old/bin/grokbot-kit" in found[0] and "grokbot-kit install opencode" in found[0]
    assert "plugin: stale" in run_doctor(kit).stdout


# C151 - AC 126, door 24
@pytest.mark.parametrize("case", ["sem a linha", "valor não string", "valor não JSON", "ilegível"])
def test_plugin_without_exe_line(kit: Kit, case: str) -> None:
    assert kit.cli("install", "opencode").returncode == 0
    path = plugin_file(kit)
    lines = path.read_text(encoding="utf-8").splitlines()
    exe_line = [i for i, line in enumerate(lines) if line.startswith("const GROKBOT_KIT = ")]
    assert len(exe_line) == 1
    if case == "sem a linha":
        del lines[exe_line[0]]
    elif case == "valor não string":
        lines[exe_line[0]] = "const GROKBOT_KIT = 42"
    elif case == "valor não JSON":
        lines[exe_line[0]] = "const GROKBOT_KIT = process.env.GROKBOT_KIT"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if case == "ilegível":
        path.chmod(0)
    code, out = report(kit)
    assert code == 1
    plugin = out["cli"]["opencode"]["plugin"]
    assert plugin["exe"] is None
    assert plugin["ok"] is False
    found = [p for p in out["problems"] if "plugin" in p]
    assert len(found) == 1 and "grokbot-kit install opencode" in found[0]


def test_opencode_plugin_not_installed_tool(kit: Kit) -> None:
    kit.write_config(default_config(kit.sink, installed=("claude",)))
    code, out = report(kit)
    assert code == 0, out
    assert all("plugin" not in cli for cli in out["cli"].values())
    assert not any("plugin" in p for p in out["problems"])


# --- kit-update (checks C37 e C38; AC 34-36) ----------------------------------------------------------------------

UPDATE_KEYS = {
    "installed",
    "latest",
    "update_available",
    "ask",
    "skipped",
    "later_until",
    "checked_at",
    "installer",
    "error",
}


def pypi(version: str) -> tuple[int, str]:
    return (200, json.dumps({"info": {"version": version}}))


def gets(receiver: Receiver) -> int:
    return sum(1 for r in receiver.requests if r.method == "GET")


# C37 - AC 34, AC 35
def test_doctor_update_field(kit: Kit, receiver: Receiver) -> None:
    assert kit.cli("install", "opencode").returncode == 0
    write_secret(kit.home, "bot-a-key", "crsr_x\n")
    receiver.respond(pypi("9.0.0"))
    code, out = report(kit, GROKBOT_KIT_PYPI_URL=receiver.url)
    assert code == 0, out
    assert out["ok"] is True
    assert out["problems"] == []
    update = out["kit"]["update"]
    assert set(update) == UPDATE_KEYS
    assert update["update_available"] is True
    assert update["latest"] == "9.0.0"
    assert gets(receiver) == 1

    code, again = report(kit, GROKBOT_KIT_PYPI_URL=receiver.url)
    assert code == 0
    assert again["kit"]["update"]["latest"] == "9.0.0"
    assert gets(receiver) == 1


UPDATE_LINE = "update: grokbot-kit 9.0.0 available; run: grokbot-kit update apply"


# C38 - AC 36
def test_doctor_update_text_line(kit: Kit, receiver: Receiver) -> None:
    receiver.respond(pypi("9.0.0"))
    result = run_doctor(kit, GROKBOT_KIT_PYPI_URL=receiver.url)
    assert UPDATE_LINE in result.stdout.splitlines()

    (kit.home / ".grokbot-kit" / "update.json").unlink()
    receiver.respond(pypi(__version__))
    result = run_doctor(kit, GROKBOT_KIT_PYPI_URL=receiver.url)
    assert gets(receiver) == 2
    assert not [line for line in result.stdout.splitlines() if line.startswith("update:")]


# C58 - AC 65, AC 66
def test_plugins_listed_and_problems(kit: Kit, tmp_path: Path) -> None:
    assert kit.cli("install", "opencode").returncode == 0
    code, out = report(kit)
    assert (code, out["problems"]) == (0, [])
    assert [(p["name"], p["source"]) for p in out["plugins"]] == [("bug-verify", "builtin"), ("code-review", "builtin")]
    for p in out["plugins"]:
        assert {"name", "version", "source"} <= set(p)

    source = write_plugin(tmp_path / "teste")
    assert kit.cli("plugin", "add", str(source), "--yes").returncode == 0
    _, out = report(kit)
    assert ("teste", "dir") in [(p["name"], p["source"]) for p in out["plugins"]]
    (kit.home / ".grokbot-kit" / "plugins" / "teste" / "grokbot-kit.toml").write_text("name = \n", encoding="utf-8")
    code, out = report(kit)
    assert code == 1
    assert len(out["problems"]) == 1, out["problems"]
    assert "teste" not in [p["name"] for p in out["plugins"]]
    assert [p for p in out["problems"] if "plugin teste" in p and "grokbot-kit.toml" in p], out["problems"]

    shutil.rmtree(kit.home / ".grokbot-kit" / "plugins" / "teste")
    code, out = report(kit)
    assert (code, out["problems"], out["gh"]) == (0, [], {"logged_in": True})
    code, out = report(kit, FAKE_GH_AUTH_EXIT="1")
    assert (code, out["problems"], out["gh"]) == (0, [], {"logged_in": False})
    text = run_doctor(kit, FAKE_GH_AUTH_EXIT="1")
    assert text.returncode == 0
    assert "gh: not logged in; plugins with repo inputs cannot run; run: gh auth login" in text.stdout.splitlines()
    assert "problem:" not in text.stdout
    assert "plugin code-review " in text.stdout


# model-setup-docs: `cli.opencode.providers` e o problema da door 3
def with_providers(kit: Kit, providers: list[str] | None, standard: str) -> None:
    text = default_config(kit.sink).replace(
        'models = ["opencode/free-model"]', 'models = ["opencode/a-free", "opencode-go/b"]'
    )
    text = text.replace('standard = ["opencode/free-model"]', f'standard = ["{standard}"]')
    if providers is not None:
        text = text.replace("[cli.opencode.tiers]", f"providers = {json.dumps(providers)}\n[cli.opencode.tiers]", 1)
    kit.write_config(text)


PROVIDER_PROBLEM = "cli.opencode.tiers.standard has 'opencode/a-free', whose provider is not in cli.opencode.providers"


# C10 - AC 11
def test_opencode_providers_field(kit: Kit) -> None:
    with_providers(kit, ["opencode-go"], "opencode-go/b")
    _, out = report(kit)
    assert out["cli"]["opencode"]["providers"] == ["opencode-go"]
    with_providers(kit, None, "opencode-go/b")
    _, out = report(kit)
    assert out["cli"]["opencode"]["providers"] is None


# C11 - AC 12, door 3
def test_opencode_tier_provider_problem(kit: Kit) -> None:
    with_providers(kit, ["opencode-go"], "opencode/a-free")
    code, out = report(kit)
    assert code == 1
    found = [p for p in out["problems"] if p.startswith(PROVIDER_PROBLEM)]
    assert len(found) == 1, out["problems"]
    assert "grokbot-kit setup tiers opencode standard" in found[0]
    with_providers(kit, ["opencode-go"], "opencode-go/b")
    _, out = report(kit)
    assert not any("whose provider" in p for p in out["problems"])


def write_plugin_for(kit: Kit, major: int | None) -> None:
    assert kit.cli("install", "opencode").returncode == 0
    path = plugin_file(kit)
    lines = path.read_text(encoding="utf-8").splitlines()[1:]
    head = [] if major is None else [f"// grokbot-kit opencode plugin for opencode {major}"]
    path.write_text("\n".join(head + lines) + "\n", encoding="utf-8")


# C35 - AC 24 da needs-input-reply
@pytest.mark.parametrize(
    ("version", "marker", "plugin_major", "opencode_major"),
    [("opencode v2.2.4", 1, 1, 2), ("opencode v1.19.3", 2, 2, 1), ("opencode v2.2.4", None, 1, 2)],
    ids=["v1-no-2", "v2-no-1", "sem-marcador"],
)
def test_plugin_major_mismatch(
    kit: Kit, version: str, marker: int | None, plugin_major: int, opencode_major: int
) -> None:
    write_secret(kit.home, "bot-a-key", "crsr_x\n")
    kit.env = {**kit.env, "FAKE_VERSION": version}
    write_plugin_for(kit, marker)
    code, out = report(kit)
    expected = (
        f"opencode plugin is for opencode {plugin_major}, installed opencode is {opencode_major}; "
        "run: grokbot-kit install opencode"
    )
    assert code == 1
    assert expected in out["problems"]


def test_plugin_major_match_is_ok(kit: Kit) -> None:
    write_secret(kit.home, "bot-a-key", "crsr_x\n")
    kit.env = {**kit.env, "FAKE_VERSION": "opencode v2.2.4"}
    assert kit.cli("install", "opencode").returncode == 0
    _, out = report(kit)
    assert not any("plugin is for opencode" in p for p in out["problems"]), out["problems"]


# C48 - AC 34 da needs-input-reply
def test_opencode_1_warning(kit: Kit) -> None:
    write_secret(kit.home, "bot-a-key", "crsr_x\n")
    kit.env = {**kit.env, "FAKE_VERSION": "opencode v1.19.3"}
    assert kit.cli("install", "opencode").returncode == 0
    warning = "opencode 1.19.3: replies to needs_input need opencode 2; run: grokbot-kit setup cli upgrade opencode"
    code, out = report(kit)
    assert out["cli"]["opencode"]["reply"]["warning"] == warning
    assert not any("replies to needs_input" in p for p in out["problems"])
    assert warning in run_doctor(kit).stdout
    kit.env = {**kit.env, "FAKE_VERSION": "opencode v2.2.4"}
    assert kit.cli("install", "opencode").returncode == 0
    code_2, out_2 = report(kit)
    assert out_2["cli"]["opencode"]["reply"]["warning"] is None
    assert code == code_2
