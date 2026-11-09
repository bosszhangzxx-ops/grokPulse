"""`grokbot-kit route add/rm/test` (AC 75 e 77, door 3): a rota de cada `target` e o seu sink `grokbot-routine`."""

import re
import sys
from typing import Any

from grokbot_kit import config, deliver, payload, sinks

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SECRET_KEYS = ("url_secret", "key_secret", "token_secret", "webhook_secret")


class RouteError(Exception):
    pass


def _err(message: str) -> int:
    print(f"grokbot-kit route: {message}", file=sys.stderr)
    return 2


def _load_or_empty() -> dict[str, Any]:
    if not config.config_path().exists():
        return {}
    return config.load()


def _headers(raw: list[str]) -> dict[str, str]:
    headers = {}
    for item in raw:
        name, sep, value = item.partition(":")
        if not sep or not re.match(r"^[A-Za-z0-9-]+$", name.strip()):
            raise RouteError(f"--header must look like 'Name: value', got a header named {name.strip()!r}")
        headers[name.strip()] = value.strip()
    return headers


def add(target: str, url_secret: str, key_secret: str, raw_headers: list[str]) -> int:
    try:
        if not NAME_RE.match(target):
            raise RouteError("target must use only letters, digits, '.', '_' and '-'")
        headers = _headers(raw_headers)
        # a mensagem de erro nunca cita o conteúdo dos segredos (AC 77)
        if not config.read_secret(key_secret).startswith("crsr_"):
            raise RouteError(
                f"secret {key_secret!r} must hold only the routine key (crsr_...), without 'Bearer '; "
                f"run: grokbot-kit secret set {key_secret}"
            )
        if not config.read_secret(url_secret).startswith("https://"):
            raise RouteError(
                f"secret {url_secret!r} must hold the routine webhook URL (https://...); "
                f"run: grokbot-kit secret set {url_secret}"
            )
        cfg = _load_or_empty()
    except (RouteError, config.ConfigError) as e:
        return _err(str(e))
    sink: dict[str, Any] = {"type": "grokbot-routine", "url_secret": url_secret, "key_secret": key_secret}
    if headers:
        sink["headers"] = headers
    cfg.setdefault("sinks", {})[target] = sink
    route = cfg.setdefault("routes", {}).setdefault(target, {"sinks": []})
    if target not in route.setdefault("sinks", []):
        route["sinks"].append(target)
    config.save(cfg)
    print(f"route {target}: sinks {', '.join(route['sinks'])}")
    return 0


def rm(target: str) -> int:
    try:
        cfg = _load_or_empty()
    except config.ConfigError as e:
        return _err(str(e))
    routes = cfg.get("routes", {})
    if target not in routes:
        return _err(f"target {target!r} has no route")
    removed = routes.pop(target)
    still_used = {name for r in routes.values() for name in r.get("sinks", [])}
    for name in removed.get("sinks", []):
        if name not in still_used:
            cfg.get("sinks", {}).pop(name, None)
    config.save(cfg)
    print(f"route {target} removed")
    return 0


def test(target: str) -> int:
    try:
        cfg = config.load()
        route = cfg.get("routes", {}).get(target)
        if route is None:
            raise RouteError(f"target {target!r} has no route; run: grokbot-kit route add {target}")
        named = []
        for name in route.get("sinks", []):
            sink = cfg.get("sinks", {}).get(name)
            if sink is None:
                raise RouteError(f"route {target!r} uses sink {name!r}, which is not in [sinks]")
            for key in SECRET_KEYS:
                if key in sink:
                    config.check_secret(sink[key])
            named.append((name, sink))
    except (RouteError, config.ConfigError) as e:
        return _err(str(e))
    event = payload.route_test_event(target)
    body, _ = deliver.serialize(event)
    failed = 0
    for name, sink in named:
        result = sinks.send(name, sink, event, body)
        if result.delivered:
            run_uuid = f" runUuid {result.run_uuid}" if result.run_uuid else ""
            print(f"{name}: delivered{run_uuid}")
        else:
            failed += 1
            status = f"HTTP {result.http_status}" if result.http_status is not None else "no HTTP response"
            print(f"grokbot-kit route: {name}: not delivered ({status}: {result.message})", file=sys.stderr)
    return 1 if failed else 0
