"""Config do kit e segredos (door 3)."""

import json
import os
import re
import stat
import tomllib
from pathlib import Path
from typing import Any

from grokbot_kit.launch import DEFAULT_CODEX_HOME


class ConfigError(Exception):
    pass


def config_path() -> Path:
    return Path.home() / ".config" / "grokbot-kit" / "config.toml"


def secrets_dir() -> Path:
    return Path.home() / ".secrets" / "grokbot-kit"


def check_secret(name: str) -> Path:
    """O caminho do segredo `name`, que precisa existir com modo `0600` (AC 65); nunca lê o conteúdo."""
    path = secrets_dir() / name
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        raise ConfigError(f"secret {name!r} not found; run: grokbot-kit secret set {name}") from None
    if mode != 0o600:
        raise ConfigError(f"secret {name!r} has mode {mode:04o}, expected 0600: {path}")
    return path


def read_secret(name: str) -> str:
    """O conteúdo do segredo `name` sem a quebra de linha final (AC 66)."""
    path = check_secret(name)
    try:
        return path.read_text(encoding="utf-8").rstrip("\r\n")
    except OSError as e:
        raise ConfigError(f"cannot read secret {name!r}: {e.strerror}") from None


def tasks_dir() -> Path:
    return Path.home() / ".grokbot-kit" / "tasks"


def check_constraints(cfg: dict[str, Any]) -> None:
    """As constraints one-way de Relations: `default_cli` instalada e ids de tier descobertos (door 3)."""
    setup = cfg.get("setup", {})
    if "default_cli" in setup and setup["default_cli"] not in setup.get("installed", []):
        raise ConfigError(
            f"setup.default_cli is {setup['default_cli']!r}, which is not in setup.installed {setup.get('installed', [])}"
        )
    if "wait" in cfg.get("ask", {}):
        from grokbot_kit.resolve import ResolveError, ask_wait

        try:
            ask_wait(cfg, None)
        except ResolveError as e:
            raise ConfigError(str(e)) from None
    for tool, cli in cfg.get("cli", {}).items():
        discovered = cli.get("models", [])
        for tier, ids in cli.get("tiers", {}).items():
            for model in ids:
                if model not in discovered:
                    raise ConfigError(
                        f"cli.{tool}.tiers.{tier} has {model!r}, which is not in cli.{tool}.models (the ids discovered "
                        f"for {tool}); run: grokbot-kit setup models refresh {tool}"
                    )


def load(*, validate: bool = True) -> dict[str, Any]:
    path = config_path()
    try:
        with path.open("rb") as f:
            cfg = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"config not found: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"invalid config {path}: {e}") from None
    if validate:
        check_constraints(cfg)
    return cfg


_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def _key(name: str) -> str:
    return name if _BARE_KEY.match(name) else json.dumps(name, ensure_ascii=False)


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, str):
        # uma string JSON é uma basic string TOML válida
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(_value(v) for v in value) + "]"
    raise TypeError(f"cannot write {type(value).__name__} to the config")


def _table(lines: list[str], path: list[str], table: dict[str, Any]) -> None:
    scalars = [(k, v) for k, v in table.items() if not isinstance(v, dict)]
    tables = [(k, v) for k, v in table.items() if isinstance(v, dict)]
    if path and (scalars or not tables):
        lines += ["", "[" + ".".join(_key(p) for p in path) + "]"]
    lines += [f"{_key(k)} = {_value(v)}" for k, v in scalars]
    for k, v in tables:
        _table(lines, [*path, k], v)


def dump(cfg: dict[str, Any]) -> str:
    lines: list[str] = []
    _table(lines, [], cfg)
    return "\n".join(lines).lstrip("\n") + "\n"


def save(cfg: dict[str, Any]) -> None:
    """Grava o config inteiro de uma vez (arquivo temporário e `os.replace`)."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(dump(cfg), encoding="utf-8")
    os.replace(tmp, path)


def cli_env(tool: str, cli: dict[str, Any]) -> dict[str, str]:
    """O env que só os processos da CLI `tool` recebem: `CODEX_HOME` do kit (door 7) e, no Claude com login por API
    key, `ANTHROPIC_API_KEY` lido do segredo de `api_key_secret` (door 20)."""
    if tool == "codex":
        return {"CODEX_HOME": os.path.expanduser(str(cli.get("codex_home", DEFAULT_CODEX_HOME)))}
    if tool == "claude" and "api_key_secret" in cli:
        return {"ANTHROPIC_API_KEY": read_secret(str(cli["api_key_secret"]))}
    return {}
