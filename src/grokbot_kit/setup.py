"""`grokbot-kit setup cli add <tool>`, `setup default <tool>`, `setup tiers` (AC 91, doors 3, 7, 19 e 22),
`setup providers` (doors 2 e 3 da model-setup-docs) e `setup cli upgrade <tool>` (door 7 da needs-input-reply)."""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

from grokbot_kit import config
from grokbot_kit.launch import DEFAULT_CODEX_HOME
from grokbot_kit.models import provider

INSTALL_TIMEOUT = 900
VERSION_TIMEOUT = 60


class Installer(NamedTuple):
    argv: list[str]
    env: dict[str, str]
    bin: Path


def installer(tool: str, home: Path, codex_home: Path) -> Installer:
    """O instalador oficial de `tool` e onde ele deixa o binário (door 19)."""
    if tool == "claude":
        return Installer(
            ["bash", "-c", "curl -fsSL https://claude.ai/install.sh | bash"], {}, home / ".local" / "bin" / "claude"
        )
    if tool == "opencode":
        argv = ["bash", "-c", "curl -fsSL https://opencode.ai/install | bash -s -- --no-modify-path"]
        return Installer(argv, {}, home / ".opencode" / "bin" / "opencode")
    if tool == "codex":
        bin_dir = home / ".grokbot-kit" / "bin"
        env = {"CODEX_HOME": str(codex_home), "CODEX_INSTALL_DIR": str(bin_dir)}
        return Installer(["sh", "-c", "curl -fsSL https://chatgpt.com/codex/install.sh | sh"], env, bin_dir / "codex")
    raise ValueError(f"unknown tool: {tool}")


def _err(message: str) -> None:
    print(f"grokbot-kit setup: {message}", file=sys.stderr)


def _load() -> dict[str, Any]:
    return config.load(validate=False) if config.config_path().exists() else {}


def codex_home(cli: dict[str, Any]) -> Path:
    return Path(os.path.expanduser(str(cli.get("codex_home", DEFAULT_CODEX_HOME))))


def _run_installer(tool: str, cli: dict[str, Any]) -> tuple[Installer, str] | None:
    """Roda o instalador oficial de `tool` e lê a versão do binário que ele deixou; `None` (com o motivo em stderr)
    se um dos dois falha. Não grava o config."""
    if tool == "codex":
        codex_home(cli).mkdir(parents=True, exist_ok=True, mode=0o700)
    inst = installer(tool, Path.home(), codex_home(cli))
    env = {**os.environ, **inst.env}
    if tool == "codex":
        # com o diretório no `PATH`, o instalador do Codex não edita o perfil do shell
        env["PATH"] = os.pathsep.join([inst.env["CODEX_INSTALL_DIR"], env.get("PATH", "")])
    try:
        proc = subprocess.run(
            inst.argv, stdin=subprocess.DEVNULL, stdout=sys.stderr, env=env, timeout=INSTALL_TIMEOUT, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        _err(f"{tool} installer failed: {e}")
        return None
    if proc.returncode != 0:
        _err(f"{tool} installer exited {proc.returncode}; config not changed")
        return None
    version = _version(str(inst.bin), inst.env)
    if version is None:
        return None
    return inst, version


def _version(bin_path: str, extra_env: dict[str, str], *, quiet: bool = False) -> str | None:
    """A primeira linha de `<bin> --version`, ou `None` (com o motivo em stderr, salvo `quiet`)."""
    try:
        version = subprocess.run(
            [bin_path, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            # o Codex cria arquivos no `CODEX_HOME` ao iniciar, então nem o `--version` roda com `~/.codex` (AC 98)
            env={**os.environ, **extra_env},
            timeout=VERSION_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        if not quiet:
            _err(f"{bin_path} --version failed: {e}; config not changed")
        return None
    if version.returncode != 0:
        if not quiet:
            _err(f"{bin_path} --version exited {version.returncode}; config not changed")
        return None
    return (version.stdout.strip().splitlines() or [""])[0]


def cli_add(tool: str) -> int:
    try:
        cfg = _load()
    except config.ConfigError as e:
        _err(str(e))
        return 2
    cli = dict(cfg.get("cli", {}).get(tool, {}))
    if tool == "codex":
        cli.setdefault("codex_home", DEFAULT_CODEX_HOME)
    done = _run_installer(tool, cli)
    if done is None:
        return 1
    inst, version = done
    cli["bin"] = str(inst.bin)
    cfg.setdefault("cli", {})[tool] = cli
    setup = cfg.setdefault("setup", {})
    setup.setdefault("version", 1)
    installed = setup.setdefault("installed", [])
    if tool not in installed:
        installed.append(tool)
    config.save(cfg)
    print(f"{tool} {version} installed at {inst.bin}")
    return 0


def _number(version: str | None) -> str:
    """O número de uma linha de `--version` (`opencode v2.2.4` -> `2.2.4`), ou ela inteira sem número."""
    found = re.search(r"\d+\.\d+(?:\.\d+)*", version or "")
    return found.group(0) if found else (version or "unknown")


def cli_upgrade(tool: str) -> int:
    """`setup cli upgrade <tool>` (door 7 da needs-input-reply): o instalador oficial de novo, que traz a última versão,
    e no opencode o plugin reescrito para o major novo (AC 30-33)."""
    try:
        cfg = _load()
    except config.ConfigError as e:
        _err(str(e))
        return 2
    cli = dict(cfg.get("cli", {}).get(tool, {}))
    if "bin" not in cli:
        _err(f"{tool} is not installed by grokbot-kit; run: grokbot-kit setup cli add {tool}")
        return 2
    extra_env = {"CODEX_HOME": str(codex_home(cli))} if tool == "codex" else {}
    before = _version(os.path.expanduser(str(cli["bin"])), extra_env, quiet=True)
    done = _run_installer(tool, cli)
    if done is None:
        return 1
    inst, after = done
    if cli["bin"] != str(inst.bin):
        cli["bin"] = str(inst.bin)
        cfg.setdefault("cli", {})[tool] = cli
        config.save(cfg)
    old, new = _number(before), _number(after)
    print(f"{tool} {new} is already the latest" if old == new else f"{tool} {old} -> {new}")
    if tool != "opencode":
        return 0
    from grokbot_kit import launch, opencode_plugin

    try:
        rewritten = opencode_plugin.sync(launch.cli_major(str(inst.bin)))
    except OSError as e:
        _err(
            f"cannot rewrite the opencode plugin at {opencode_plugin.plugin_path()}: {e.strerror}; "
            "run: grokbot-kit install opencode"
        )
        return 1
    if rewritten:
        print(rewritten)
    return 0


def set_default(tool: str) -> int:
    try:
        cfg = _load()
    except config.ConfigError as e:
        _err(str(e))
        return 2
    setup = cfg.get("setup", {})
    if tool not in setup.get("installed", []):
        _err(f"{tool} is not in setup.installed; run: grokbot-kit setup cli add {tool}")
        return 2
    setup["default_cli"] = tool
    config.save(cfg)
    print(f"default CLI: {tool}")
    return 0


def set_tiers(tool: str, tier: str, ids: list[str]) -> int:
    """Troca `[cli.<tool>.tiers] <tier>` pela lista dada, só com ids descobertos (door 22)."""
    try:
        cfg = _load()
    except config.ConfigError as e:
        _err(str(e))
        return 2
    if tool not in cfg.get("setup", {}).get("installed", []):
        _err(f"{tool} is not in setup.installed; run: grokbot-kit setup cli add {tool}")
        return 2
    cli = cfg.setdefault("cli", {}).setdefault(tool, {})
    discovered = cli.get("models", [])
    unknown = [model for model in ids if model not in discovered]
    if unknown:
        _err(f"not discovered for {tool}: {', '.join(unknown)}; run: grokbot-kit setup models refresh {tool}")
        return 2
    # door 3 da model-setup-docs: provedor só existe no opencode
    allowed = cli.get("providers") if tool == "opencode" else None
    if allowed is not None:
        outside = [model for model in ids if provider(tool, model) not in allowed]
        if outside:
            _err(
                f"provider not in cli.{tool}.providers ({', '.join(allowed)}): {', '.join(outside)}; "
                f"run: grokbot-kit setup providers {tool} <provider>..."
            )
            return 2
    cli.setdefault("tiers", {})[tier] = list(ids)
    config.save(cfg)
    print(f"{tool} {tier}: {', '.join(ids)}")
    return 0


def set_providers(tool: str, providers: list[str]) -> int:
    """Grava `[cli.opencode] providers` na ordem dada (door 2); só avisa dos ids de tier fora da lista (door 3)."""
    if tool != "opencode":
        _err("providers apply only to opencode")
        return 2
    try:
        cfg = _load()
    except config.ConfigError as e:
        _err(str(e))
        return 2
    if tool not in cfg.get("setup", {}).get("installed", []):
        _err(f"{tool} is not in setup.installed; run: grokbot-kit setup cli add {tool}")
        return 2
    cli = cfg.setdefault("cli", {}).setdefault(tool, {})
    known = {provider(tool, model) for model in cli.get("models", [])}
    unknown = [p for p in providers if p not in known]
    if unknown:
        _err(
            f"no discovered {tool} model id has provider {', '.join(unknown)}; "
            f"run: grokbot-kit setup models refresh {tool}"
        )
        return 2
    cli["providers"] = list(providers)
    config.save(cfg)
    for tier, ids in cli.get("tiers", {}).items():
        for model in ids:
            if provider(tool, model) not in providers:
                _err(f"cli.{tool}.tiers.{tier} has {model!r}, whose provider is not in cli.{tool}.providers")
    print(f"{tool} providers: {', '.join(providers)}")
    return 0
