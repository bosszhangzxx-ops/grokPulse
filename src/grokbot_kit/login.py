"""`grokbot-kit login <tool>` pelo comando oficial de cada CLI (AC 92-94, doors 3, 7 e 20)."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from grokbot_kit import config


def _err(message: str) -> int:
    print(f"grokbot-kit login: {message}", file=sys.stderr)
    return 1


def login_argv(tool: str, method: str) -> list[str]:
    """Os argumentos do comando oficial de login; vazio quando não há comando a rodar (API key do Claude)."""
    if tool == "codex":
        return ["login", "--with-api-key"] if method == "api-key" else ["login", "--device-auth"]
    if tool == "claude":
        return [] if method == "api-key" else ["auth", "login"]
    return ["auth", "login"]


def login(tool: str, method: str, secret: str | None) -> int:
    try:
        cfg = config.load(validate=False) if config.config_path().exists() else {}
    except config.ConfigError as e:
        return _err(str(e))
    cli: dict[str, Any] = cfg.get("cli", {}).get(tool, {})
    secret = secret or f"{tool}-api-key"
    argv = login_argv(tool, method)
    key = None
    if method == "api-key" and tool in ("codex", "claude"):
        try:
            key = config.read_secret(secret)
        except config.ConfigError as e:
            return _err(str(e))

    if tool == "claude":
        if method == "api-key":
            cli["api_key_secret"] = secret
        else:
            cli.pop("api_key_secret", None)
    if argv:
        env = {**os.environ, **config.cli_env(tool, {k: v for k, v in cli.items() if k != "api_key_secret"})}
        if tool == "codex":
            Path(env["CODEX_HOME"]).mkdir(parents=True, exist_ok=True, mode=0o700)
        bin_path = os.path.expanduser(str(cli.get("bin", tool)))
        stdin = None if key is None else (key + "\n")
        try:
            proc = subprocess.run([bin_path, *argv], input=stdin, text=True, env=env, check=False)
        except OSError as e:
            return _err(f"cannot run {bin_path}: {e.strerror}")
        if proc.returncode != 0:
            return _err(f"{tool} {' '.join(argv)} exited {proc.returncode}")
    if tool == "claude":
        cfg.setdefault("cli", {})["claude"] = cli
        config.save(cfg)
    print(f"{tool}: logged in ({method})")
    return 0
