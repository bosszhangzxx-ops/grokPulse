"""`grokbot-kit setup models refresh`: a lista de modelos descobertos de cada CLI (AC 84-86, doors 12 e 16).

Com `--json`, um objeto com o `provider` de cada id (door 1 da model-setup-docs)."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

from grokbot_kit import config, terminal
from grokbot_kit.payload import rfc3339

CLAUDE_ALIASES = ("haiku", "sonnet", "opus")
PROBE_PROMPT = "Reply with exactly the word ok. Do not use any tool."
PROBE_TIMEOUT = 300


class Discovery(NamedTuple):
    ids: list[str]
    rejected: list[tuple[str, str]]
    failed: bool
    error: str = ""


def provider(tool: str, model: str) -> str | None:
    """O provedor de um id: o texto antes do primeiro `/` no opencode; `None` nas outras CLIs."""
    return model.split("/", 1)[0] if tool == "opencode" and "/" in model else None


def _bin(tool: str, cli: dict[str, Any]) -> str:
    return os.path.expanduser(str(cli.get("bin", tool)))


def _opencode(cli: dict[str, Any]) -> Discovery:
    try:
        proc = subprocess.run(
            [_bin("opencode", cli), "models"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
            check=False,
        )
    except FileNotFoundError:
        return Discovery([], [], True, f"{_bin('opencode', cli)} not found")
    except subprocess.TimeoutExpired:
        return Discovery([], [], True, f"opencode models timed out after {PROBE_TIMEOUT} s")
    if proc.returncode != 0:
        return Discovery([], [], True, f"opencode models exited {proc.returncode}")
    ids = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return Discovery(ids, [], not ids, "" if ids else "opencode models printed no model id")


def _probe(tool: str, cli: dict[str, Any], model: str) -> str | None:
    """`None` quando a CLI aceita `model` numa chamada de teste; senão o motivo, sem a saída da CLI."""
    try:
        env = {**os.environ, **config.cli_env(tool, cli)}
    except config.ConfigError as e:
        return str(e)
    if tool == "claude":
        argv = [_bin(tool, cli), "-p", "--output-format", "json", "--model", model, PROBE_PROMPT]
    else:
        argv = [_bin(tool, cli), "exec", "--json", "--skip-git-repo-check", "-m", model, PROBE_PROMPT]
    with tempfile.TemporaryDirectory(prefix="grokbot-kit-models-") as tmp:
        try:
            proc = subprocess.run(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=tmp,
                env=env,
                timeout=PROBE_TIMEOUT,
                check=False,
            )
        except FileNotFoundError:
            return f"{argv[0]} not found"
        except subprocess.TimeoutExpired:
            return f"timed out after {PROBE_TIMEOUT} s"
        # a mesma leitura de erro do evento terminal (AC 45)
        Path(tmp, "out.jsonl").write_bytes(proc.stdout)
        output = terminal.read_output(tool, Path(tmp))
    if proc.returncode != 0:
        return f"exit {proc.returncode}"
    if output.error:
        return "error in the JSON output"
    return None


def discover(tool: str, cli: dict[str, Any], add: list[str]) -> Discovery:
    if tool == "opencode":
        return _opencode(cli)
    known = list(CLAUDE_ALIASES) if tool == "claude" else []
    candidates = list(dict.fromkeys(m for m in [*cli.get("models", []), *add] if m not in known))
    ids, rejected = known, []
    for model in candidates:
        reason = _probe(tool, cli, model)
        if reason is None:
            ids.append(model)
        else:
            rejected.append((model, reason))
    return Discovery(ids, rejected, not ids, "" if ids else f"no model id accepted by {tool}")


def _err(message: str) -> None:
    print(f"grokbot-kit setup: {message}", file=sys.stderr)


def refresh(tool: str | None, add: list[str], as_json: bool = False) -> int:
    try:
        cfg = config.load(validate=False) if config.config_path().exists() else {}
    except config.ConfigError as e:
        _err(str(e))
        return 2
    tools = [tool] if tool else list(cfg.get("setup", {}).get("installed", []))
    if not tools:
        _err("no CLI in setup.installed; run: grokbot-kit setup cli add <tool>")
        return 2
    if add and tool is None:
        _err("--add needs the tool: grokbot-kit setup models refresh <tool> --add <id>")
        return 2
    if add and tool == "opencode":
        _err("--add does not apply to opencode: its model ids come from opencode models")
        return 2
    status, changed = 0, False
    items: list[dict[str, str | None]] = []
    for t in tools:
        cli = cfg.get("cli", {}).get(t, {})
        found = discover(t, cli, add)
        for model, reason in found.rejected:
            _err(f"{t} rejected model {model!r} ({reason}); it was not recorded")
            status = 1
        if found.failed:
            _err(f"{t}: {found.error}; cli.{t}.models not changed")
            status = 1
            continue
        cli["models"] = found.ids
        cli["models_discovered_at"] = rfc3339(datetime.now(UTC))
        cfg.setdefault("cli", {})[t] = cli
        changed = True
        for model in found.ids:
            if as_json:
                items.append({"tool": t, "id": model, "provider": provider(t, model)})
            else:
                print(f"{t}\t{model}")
        for tier, ids in cli.get("tiers", {}).items():
            for model in ids:
                if model not in found.ids:
                    _err(f"cli.{t}.tiers.{tier} has {model!r}, which was not discovered; remove it from that tier")
    if changed:
        config.save(cfg)
    if as_json:
        print(json.dumps({"models": items}, ensure_ascii=False))
    return status
