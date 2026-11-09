"""Resolução de tool, modelo, tier e timeout de uma task (AC 78-83, doors 3 e 17)."""

import re
from typing import Any, NamedTuple

from grokbot_kit.launch import TOOLS

DEFAULT_TIER = "standard"
DEFAULT_TIMEOUTS = {"trivial": "30m", "standard": "2h", "complex": "4h"}
DEFAULT_ASK_WAIT = "10m"

_DURATION = re.compile(r"([1-9][0-9]*)([smhd])")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class ResolveError(Exception):
    pass


class Resolved(NamedTuple):
    tool: str
    model: str
    model_source: str
    tier: str
    timeout_seconds: int


def parse_duration(text: str) -> int:
    """Segundos de uma duração `<n>s|m|h|d` (door 17); `ValueError` em qualquer outro formato."""
    match = _DURATION.fullmatch(text)
    if match is None:
        raise ValueError(f"invalid duration {text!r}: use a positive integer followed by s, m, h or d (e.g. 30m)")
    return int(match.group(1)) * _UNIT_SECONDS[match.group(2)]


def parse_wait(text: str) -> int:
    """Segundos da espera por resposta (`[ask] wait`, `run --ask-wait`, door 4 da needs-input-reply): uma duração ou
    `0`, que desliga a espera."""
    return 0 if text == "0" else parse_duration(text)


def ask_wait(cfg: dict[str, Any], flag: str | None) -> int:
    """A espera da task: `--ask-wait`, senão `[ask] wait`, senão 10 min; `ResolveError` com a origem do valor."""
    source, value = ("--ask-wait", flag) if flag is not None else ("ask.wait", cfg.get("ask", {}).get("wait"))
    if value is None:
        source, value = "ask.wait", DEFAULT_ASK_WAIT
    try:
        return parse_wait(value if isinstance(value, str) else repr(value))
    except ValueError as e:
        raise ResolveError(f"{source}: {e}") from None


def resolve(
    cfg: dict[str, Any], *, tool: str | None, model: str | None, tier: str | None, timeout: str | None
) -> Resolved:
    setup = cfg.get("setup", {})
    tool = tool or setup.get("default_cli")
    if tool not in TOOLS:
        raise ResolveError(f"no tool given and setup.default_cli is not one of {', '.join(TOOLS)}")
    if tool not in setup.get("installed", []):
        raise ResolveError(f"{tool} is not in setup.installed; run: grokbot-kit setup cli add {tool}")
    cli = cfg.get("cli", {}).get(tool, {})
    tier = tier or DEFAULT_TIER
    if model:
        model_source = "user"
    else:
        candidates = cli.get("tiers", {}).get(tier, [])
        if not candidates:
            raise ResolveError(f"no model in cli.{tool}.tiers.{tier}; run: grokbot-kit setup models refresh {tool}")
        model, model_source = candidates[0], "tier"
    if model not in cli.get("models", []):
        raise ResolveError(
            f"model {model!r} was not discovered for {tool}; run: grokbot-kit setup models refresh {tool}"
        )
    if timeout is not None:
        try:
            seconds = parse_duration(timeout)
        except ValueError as e:
            raise ResolveError(f"--timeout: {e}") from None
    else:
        value = cfg.get("timeouts", {}).get(tier, DEFAULT_TIMEOUTS.get(tier))
        try:
            seconds = parse_duration(value if isinstance(value, str) else repr(value))
        except ValueError as e:
            raise ResolveError(f"timeouts.{tier}: {e}") from None
    return Resolved(tool, model, model_source, tier, seconds)
