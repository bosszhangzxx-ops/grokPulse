"""Provas das recusas do `run` antes de lançar o agente (check C53; AC 47 sobre os AC 64, 65, 81, 82 e 90)."""

import os
import tomllib
from collections.abc import Callable
from typing import Any

import pytest
from conftest import Kit, default_config

from grokbot_kit import config, resolve

ROUTINE_ROUTE = """
[routes.bot-r]
sinks = ["rotina"]

[sinks.rotina]
type = "grokbot-routine"
url_secret = "bot-r-url"
key_secret = "bot-r-key"
"""


def write_secret(kit: Kit, name: str, mode: int) -> None:
    secrets = kit.home / ".secrets" / "grokbot-kit"
    secrets.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = secrets / name
    path.write_text("valor-de-teste\n", encoding="utf-8")
    os.chmod(path, mode)


def arrange(kit: Kit, cause: str) -> list[str]:
    base = ["--target", "bot-a", "--label", "recusa"]
    if cause == "target inexistente (AC 64)":
        return ["--target", "bot-inexistente", "--label", "recusa", "--", "oi"]
    if cause.startswith("segredo"):
        kit.write_config(default_config(kit.sink) + ROUTINE_ROUTE)
        if cause == "segredo com modo 0644 (AC 65)":
            write_secret(kit, "bot-r-url", 0o600)
            write_secret(kit, "bot-r-key", 0o644)
        else:
            write_secret(kit, "bot-r-url", 0o600)
        return ["--target", "bot-r", "--label", "recusa", "--", "oi"]
    if cause == "modelo não descoberto (AC 81)":
        return ["--tool", "opencode", "--model", "inventado-123", *base, "--", "oi"]
    if cause == "tool não instalada (AC 82)":
        kit.write_config(default_config(kit.sink, installed=("opencode",)))
        return ["--tool", "codex", *base, "--", "oi"]
    if cause == "--bare com claude (AC 90)":
        return ["--tool", "claude", *base, "--", "--bare", "oi"]
    raise AssertionError(cause)


# C53 - AC 47
@pytest.mark.parametrize(
    "cause",
    [
        "target inexistente (AC 64)",
        "segredo ausente (AC 65)",
        "segredo com modo 0644 (AC 65)",
        "modelo não descoberto (AC 81)",
        "tool não instalada (AC 82)",
        "--bare com claude (AC 90)",
    ],
)
def test_exit_2_creates_no_task_dir(kit: Kit, cause: str) -> None:
    result = kit.run(*arrange(kit, cause))
    assert result.returncode == 2, result.stderr
    assert kit.tasks() == []
    assert not kit.sink.exists()
    assert not kit.record.exists(), "o agente foi lançado"


def test_exit_2_creates_no_task_dir_control_valid_secrets_launch(kit: Kit) -> None:
    kit.write_config(default_config(kit.sink) + ROUTINE_ROUTE)
    write_secret(kit, "bot-r-url", 0o600)
    write_secret(kit, "bot-r-key", 0o600)
    result = kit.run("--target", "bot-r", "--label", "aceita", "--", "oi")
    assert result.returncode == 0, result.stderr
    assert kit.record.exists()
    assert len(kit.tasks()) == 1


SINK_SECRETS = """
[routes.bot-s]
sinks = ["rotina-s", "avisos", "canal"]

[sinks.rotina-s]
type = "grokbot-routine"
url_secret = "s-url"
key_secret = "s-key"

[sinks.avisos]
type = "ntfy"
topic_url = "https://ntfy.example/topico"
token_secret = "s-ntfy"

[sinks.canal]
type = "slack"
webhook_secret = "s-slack"
"""


# C76 - AC 64
def test_unknown_target_exit_2(kit: Kit) -> None:
    result = kit.run("--target", "bot-inexistente", "--label", "alvo", "--", "oi")
    assert result.returncode == 2
    assert "bot-inexistente" in result.stderr
    assert not kit.record.exists(), "o agente foi lançado"
    assert kit.tasks() == []


def test_unknown_target_exit_2_control_known_target_launches(kit: Kit) -> None:
    result = kit.run("--target", "bot-a", "--label", "alvo", "--", "oi")
    assert result.returncode == 0, result.stderr
    assert kit.record.exists()


# C77 - AC 65: cada segredo referenciado pela rota (url, key, token do ntfy, webhook do slack)
@pytest.mark.parametrize("secret", ["s-url", "s-key", "s-ntfy", "s-slack"])
@pytest.mark.parametrize("problem", ["ausente", "0644", "0640", "0400"])
def test_secret_missing_or_wrong_mode_exit_2(kit: Kit, secret: str, problem: str) -> None:
    kit.write_config(default_config(kit.sink) + SINK_SECRETS)
    for name in ("s-url", "s-key", "s-ntfy", "s-slack"):
        if name != secret:
            write_secret(kit, name, 0o600)
        elif problem != "ausente":
            write_secret(kit, name, int(problem, 8))
    result = kit.run("--target", "bot-s", "--label", "segredo", "--", "oi")
    assert result.returncode == 2
    assert secret in result.stderr
    assert "valor-de-teste" not in result.stderr + result.stdout
    assert not kit.record.exists(), "o agente foi lançado"
    assert kit.tasks() == []


def test_secret_missing_or_wrong_mode_exit_2_control_0600_launches(kit: Kit) -> None:
    kit.write_config(default_config(kit.sink) + SINK_SECRETS)
    for name in ("s-url", "s-key", "s-ntfy", "s-slack"):
        write_secret(kit, name, 0o600)
    result = kit.run("--target", "bot-s", "--label", "segredo", "--", "oi")
    assert kit.record.exists(), result.stderr
    assert len(kit.tasks()) == 1


def config_with(kit: Kit, mutate: Callable[[dict[str, Any]], None]) -> None:
    cfg = tomllib.loads(default_config(kit.sink))
    mutate(cfg)
    kit.write_config(config.dump(cfg))


# C101 - AC 81: o modelo resolvido, venha de `--model` ou do tier, precisa estar na lista descoberta
@pytest.mark.parametrize("origin", ["--model", "tier"])
@pytest.mark.parametrize("tool", ["opencode", "claude", "codex"])
def test_undiscovered_model_exit_2(kit: Kit, tool: str, origin: str) -> None:
    if origin == "tier":
        config_with(kit, lambda c: c["cli"][tool]["tiers"].update(standard=["inventado-123"]))
        args = ["--tool", tool]
    else:
        args = ["--tool", tool, "--model", "inventado-123"]
    result = kit.run(*args, "--target", "bot-a", "--label", "modelo", "--", "oi")
    assert result.returncode == 2
    assert f"grokbot-kit setup models refresh {tool}" in result.stderr
    assert not kit.record.exists(), "o agente foi lançado"
    assert kit.tasks() == []


def test_undiscovered_model_exit_2_resolve_layer(kit: Kit) -> None:
    cfg = tomllib.loads(default_config(kit.sink))
    with pytest.raises(resolve.ResolveError) as raised:
        resolve.resolve(cfg, tool="codex", model="inventado-123", tier=None, timeout=None)
    assert "grokbot-kit setup models refresh codex" in str(raised.value)
    cfg["cli"]["claude"]["tiers"]["standard"] = ["inventado-123"]
    with pytest.raises(resolve.ResolveError) as raised:
        resolve.resolve(cfg, tool="claude", model=None, tier=None, timeout=None)
    assert "grokbot-kit setup models refresh claude" in str(raised.value)


def test_undiscovered_model_exit_2_control_discovered_launches(kit: Kit) -> None:
    result = kit.run("--tool", "codex", "--model", "gpt-test", "--target", "bot-a", "--label", "modelo", "--", "oi")
    assert result.returncode == 0, result.stderr
    assert kit.record.exists()


# C102 - AC 82: pela `--tool` ou pela `default_cli`
@pytest.mark.parametrize("via", ["--tool", "default_cli"])
def test_tool_not_installed_exit_2(kit: Kit, via: str) -> None:
    def mutate(c: dict[str, Any]) -> None:
        c["setup"]["installed"] = ["opencode"]
        if via == "default_cli":
            c["setup"]["default_cli"] = "codex"

    config_with(kit, mutate)
    args = ["--tool", "codex"] if via == "--tool" else []
    result = kit.run(*args, "--target", "bot-a", "--label", "instalada", "--", "oi")
    assert result.returncode == 2
    assert "codex" in result.stderr
    assert not kit.record.exists(), "o agente foi lançado"
    assert kit.tasks() == []


def test_tool_not_installed_exit_2_resolve_layer(kit: Kit) -> None:
    cfg = tomllib.loads(default_config(kit.sink, installed=("opencode",)))
    with pytest.raises(resolve.ResolveError) as raised:
        resolve.resolve(cfg, tool="claude", model=None, tier=None, timeout=None)
    assert "setup.installed" in str(raised.value)
    assert resolve.resolve(cfg, tool="opencode", model=None, tier=None, timeout=None).tool == "opencode"


def test_tool_not_installed_exit_2_control_installed_launches(kit: Kit) -> None:
    config_with(kit, lambda c: c["setup"].update(installed=["opencode", "codex"]))
    result = kit.run("--tool", "codex", "--target", "bot-a", "--label", "instalada", "--", "oi")
    assert result.returncode == 0, result.stderr
    assert kit.launched()["tool"] == "codex"


# C111 - AC 90
@pytest.mark.parametrize("extras", [["--bare", "oi"], ["--allowedTools", "Bash", "--bare", "oi"]])
def test_bare_rejected_for_claude(kit: Kit, extras: list[str]) -> None:
    result = kit.run("--tool", "claude", "--target", "bot-a", "--label", "bare", "--", *extras)
    assert result.returncode == 2
    assert "--bare" in result.stderr
    assert not kit.record.exists(), "o agente foi lançado"
    assert kit.tasks() == []


@pytest.mark.parametrize("tool", ["opencode", "codex"])
def test_bare_rejected_for_claude_control_other_tools_launch(kit: Kit, tool: str) -> None:
    result = kit.run("--tool", tool, "--target", "bot-a", "--label", "bare", "--", "--bare", "oi")
    assert result.returncode == 0, result.stderr
    assert kit.launched()["argv"][-2:] == ["--bare", "oi"]


# C147 - Test policy "Ponto de entrada que não decide": as demais recusas do `run` saem com `2` antes do task dir
def other_refusal(kit: Kit, cause: str) -> list[str]:
    base = ["--target", "bot-a", "--label", "recusa"]
    if cause == "sink da rota fora de [sinks]":
        kit.write_config(default_config(kit.sink).replace('sinks = ["arquivo"]', 'sinks = ["arquivo", "sumido"]'))
        return [*base, "--", "oi"]
    if cause == "--label inválido":
        return ["--target", "bot-a", "--label", "com espaço", "--", "oi"]
    if cause == "--cwd não é diretório":
        return [*base, "--cwd", str(kit.home / "nao-existe"), "--", "oi"]
    if cause == "--prompt-file ilegível":
        return [*base, "--prompt-file", str(kit.home / "nao-existe.txt")]
    raise AssertionError(cause)


@pytest.mark.parametrize(
    ("cause", "named"),
    [
        ("sink da rota fora de [sinks]", "sumido"),
        ("--label inválido", "--label"),
        ("--cwd não é diretório", "--cwd"),
        ("--prompt-file ilegível", "--prompt-file"),
    ],
)
def test_other_refusals_exit_2(kit: Kit, cause: str, named: str) -> None:
    result = kit.run(*other_refusal(kit, cause))
    assert result.returncode == 2, result.stderr
    assert named in result.stderr
    assert kit.tasks() == []
    assert not kit.sink.exists()
    assert not kit.record.exists(), "o agente foi lançado"


# C148 - door 13: `--prompt-file` acrescenta o conteúdo do arquivo como último argumento, depois dos extras
def test_prompt_file_appended_last(kit: Kit) -> None:
    prompt = kit.home / "prompt.txt"
    prompt.write_text("renomeie as variáveis\nde x.py", encoding="utf-8")
    result = kit.run("--target", "bot-a", "--label", "pf", "--prompt-file", str(prompt), "--", "--extra", "valor")
    assert result.returncode == 0, result.stderr
    argv = kit.launched()["argv"]
    assert argv[-3:] == ["--extra", "valor", "renomeie as variáveis\nde x.py"]


def _meta(kit: Kit) -> dict[str, Any]:
    import json

    meta: dict[str, Any] = json.loads((kit.task_dir() / "meta.json").read_text(encoding="utf-8"))
    return meta


# C2 - AC 1 e 6 da needs-input-reply, door 4
@pytest.mark.parametrize(
    ("config_wait", "flag", "expected"),
    [(None, None, 600), ("2m", None, 120), ("2m", "30s", 30), (None, "0", 0), ("0", None, 0)],
)
def test_ask_wait_meta(kit: Kit, config_wait: str | None, flag: str | None, expected: int) -> None:
    if config_wait is not None:
        kit.write_config(kit.config_text() + f'\n[ask]\nwait = "{config_wait}"\n')
    extra = ["--ask-wait", flag] if flag is not None else []
    result = kit.run("--tool", "claude", "--target", "bot-a", "--label", "w", *extra, "--", "oi")
    assert result.returncode == 0, result.stderr
    assert _meta(kit)["ask_wait_seconds"] == expected


# C3 - Surface da needs-input-reply
def test_ask_wait_invalid(kit: Kit) -> None:
    result = kit.run("--tool", "claude", "--target", "bot-a", "--label", "w", "--ask-wait", "10x", "--", "oi")
    assert result.returncode == 2
    assert "invalid duration '10x'" in result.stderr
    assert kit.tasks() == []


# C41 - AC 27 da needs-input-reply, na fronteira
def test_run_allowed_request_ends_ok(kit: Kit) -> None:
    import json
    import threading
    import time

    from test_emit import CLAUDE_OK, claude_hook

    answers: list[int] = []

    def answer() -> None:
        until = time.monotonic() + 30
        while time.monotonic() < until:
            asked = [e for e in kit.sink_events() if e["event"] == "needs_input"]
            if asked:
                event = asked[0]
                result = kit.cli("reply", event["task_id"], event["needs_input"]["request_id"], "allow")
                answers.append(result.returncode)
                return
            time.sleep(0.05)

    thread = threading.Thread(target=answer)
    thread.start()
    result = kit.run(
        "--tool",
        "claude",
        "--target",
        "bot-a",
        "--label",
        "ok",
        "--ask-wait",
        "20s",
        "--",
        "faça",
        FAKE_STDOUT=CLAUDE_OK,
        FAKE_EMIT=json.dumps([claude_hook()]),
    )
    thread.join()
    assert answers == [0]
    assert result.returncode == 0, result.stderr
    [terminal] = [e for e in kit.sink_events() if e["event"] != "needs_input"]
    assert (terminal["event"], terminal["status"], terminal["exit_reason"]) == ("completed", "ok", "success")


def _plugin_path(kit: Kit) -> "os.PathLike[str]":
    return kit.home / ".config" / "opencode" / "plugins" / "grokbot-kit.ts"


def _install_marked(kit: Kit, major: int) -> None:
    from pathlib import Path

    path = Path(_plugin_path(kit))
    env = kit.env
    kit.env = {**env, "FAKE_VERSION": f"opencode v{major}.0.0"}
    try:
        assert kit.cli("install", "opencode").returncode == 0
    finally:
        kit.env = env
    assert path.read_text(encoding="utf-8").startswith(f"// grokbot-kit opencode plugin for opencode {major}\n")


# C36 - AC 25 da needs-input-reply
def test_run_rewrites_stale_plugin(kit: Kit) -> None:
    import json
    from pathlib import Path

    path = Path(_plugin_path(kit))
    _install_marked(kit, 1)
    result = kit.run(
        "--tool", "opencode", "--target", "bot-a", "--label", "p", "--", "oi", FAKE_VERSION="opencode v2.2.4"
    )
    assert result.returncode == 0, result.stderr
    assert path.read_text(encoding="utf-8").startswith("// grokbot-kit opencode plugin for opencode 2\n")
    log = (kit.task_dir() / "kit.log").read_text(encoding="utf-8")
    assert "opencode plugin rewritten for opencode 2" in log
    # já reescrito quando a CLI rodou: o log diz isso antes do `launch`
    assert log.index("opencode plugin rewritten") < log.index("launch opencode")
    assert json.loads((kit.task_dir() / "meta.json").read_text(encoding="utf-8"))["tool"] == "opencode"


def test_run_rewrites_stale_plugin_untouched_when_current(kit: Kit) -> None:
    import os as _os
    from pathlib import Path

    path = Path(_plugin_path(kit))
    _install_marked(kit, 2)
    _os.utime(path, (1_000_000_000, 1_000_000_000))
    result = kit.run(
        "--tool", "opencode", "--target", "bot-a", "--label", "p", "--", "oi", FAKE_VERSION="opencode v2.2.4"
    )
    assert result.returncode == 0, result.stderr
    assert path.stat().st_mtime == 1_000_000_000
    assert "rewritten" not in (kit.task_dir() / "kit.log").read_text(encoding="utf-8")


def test_run_rewrites_stale_plugin_absent(kit: Kit) -> None:
    from pathlib import Path

    result = kit.run(
        "--tool", "opencode", "--target", "bot-a", "--label", "p", "--", "oi", FAKE_VERSION="opencode v2.2.4"
    )
    assert result.returncode == 0, result.stderr
    assert not Path(_plugin_path(kit)).exists()


# C37 - AC 26 da needs-input-reply
def test_run_plugin_rewrite_failure(kit: Kit) -> None:
    from pathlib import Path

    path = Path(_plugin_path(kit))
    _install_marked(kit, 1)
    os.chmod(path.parent, 0o500)
    try:
        result = kit.run(
            "--tool", "opencode", "--target", "bot-a", "--label", "p", "--", "oi", FAKE_VERSION="opencode v2.2.4"
        )
    finally:
        os.chmod(path.parent, 0o700)
    assert result.returncode == 0, result.stderr
    log = (kit.task_dir() / "kit.log").read_text(encoding="utf-8")
    assert "cannot rewrite the opencode plugin" in log
    assert kit.launched()["tool"] == "opencode"
    [terminal] = kit.sink_events()
    assert terminal["event"] == "completed"
