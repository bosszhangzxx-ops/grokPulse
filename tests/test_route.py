"""Provas do `grokbot-kit route` (checks C87 e C89; AC 75 e 77, doors 2 e 3)."""

import json
import os
import tomllib
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from conftest import KEY, Kit, Receiver, write_secret

from grokbot_kit import config

SCHEMA = json.loads((Path(config.__file__).parent / "assets" / "event.v1.json").read_text(encoding="utf-8"))
DOOR_2_TEST_NULLS = ("task_id", "task_label", "tool", "model", "model_source", "output_file", "log_file", "started_at")
RECEIPT = json.dumps({"success": True, "runUuid": "u-test-1"})


def route_test_config(kit: Kit, receiver: Receiver, receiver_b: Receiver) -> Path:
    file_sink = kit.home / "teste.jsonl"
    write_secret(kit.home, "t-url", receiver.url + "\n")
    write_secret(kit.home, "t-key", KEY + "\n")
    write_secret(kit.home, "t2-url", receiver_b.url + "\n")
    write_secret(kit.home, "t2-key", KEY + "\n")
    kit.write_config(
        kit.config_text()
        + "\n".join(
            [
                "",
                "[routes.bot-t]",
                'sinks = ["rotina-t", "rotina-t2", "arquivo-t"]',
                "",
                "[sinks.rotina-t]",
                'type = "grokbot-routine"',
                'url_secret = "t-url"',
                'key_secret = "t-key"',
                "",
                "[sinks.rotina-t2]",
                'type = "grokbot-routine"',
                'url_secret = "t2-url"',
                'key_secret = "t2-key"',
                "",
                "[sinks.arquivo-t]",
                'type = "file"',
                f"path = {json.dumps(str(file_sink))}",
                "",
            ]
        )
    )
    receiver_b.respond((200, json.dumps({"success": True, "runUuid": "u-test-2"})))
    return file_sink


# C87 - AC 75
def test_route_test_event_and_exit_codes(kit: Kit, receiver: Receiver, receiver_b: Receiver) -> None:
    file_sink = route_test_config(kit, receiver, receiver_b)
    receiver.respond((200, RECEIPT))
    result = kit.cli("route", "test", "bot-t")
    assert result.returncode == 0, result.stderr
    assert "u-test-1" in result.stdout and "u-test-2" in result.stdout
    events: list[dict[str, Any]] = [*receiver.bodies(), *receiver_b.bodies()]
    events.append(json.loads(file_sink.read_text(encoding="utf-8")))
    assert len(events) == 3
    for event in events:
        jsonschema.validate(event, SCHEMA)
        assert event["event"] == "test"
        assert event["status"] == "test"
        assert event["target"] == "bot-t"
        for field in DOOR_2_TEST_NULLS:
            assert event[field] is None, field
    assert KEY not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "response",
    [
        (400, json.dumps({"message": "não"})),
        (200, json.dumps({"success": True})),
        (200, json.dumps({"success": False})),
    ],
)
def test_route_test_event_and_exit_codes_one_failed(
    kit: Kit, receiver: Receiver, receiver_b: Receiver, response: tuple[int, str]
) -> None:
    file_sink = route_test_config(kit, receiver, receiver_b)
    receiver.respond(response)
    result = kit.cli("route", "test", "bot-t")
    assert result.returncode == 1
    assert len(receiver_b.requests) == 1 and file_sink.exists(), "os outros sinks também recebem"
    assert "rotina-t" in result.stderr


def test_route_test_event_and_exit_codes_unknown_target(kit: Kit) -> None:
    result = kit.cli("route", "test", "bot-inexistente")
    assert result.returncode == 2


@pytest.mark.parametrize("problem", ["ausente", "0644"])
def test_route_test_event_and_exit_codes_secret(
    kit: Kit, receiver: Receiver, receiver_b: Receiver, problem: str
) -> None:
    route_test_config(kit, receiver, receiver_b)
    secret = kit.home / ".secrets" / "grokbot-kit" / "t2-key"
    if problem == "ausente":
        secret.unlink()
    else:
        os.chmod(secret, 0o644)
    result = kit.cli("route", "test", "bot-t")
    assert result.returncode == 2
    assert "t2-key" in result.stderr
    assert receiver.requests == [] and receiver_b.requests == []


# C89 - AC 77
URL = "https://api2.cursor.sh/automations/webhook/7d1e-routine-uuid"


def add(kit: Kit, url: str, key: str, *extra: str) -> Any:
    write_secret(kit.home, "n-url", url + "\n")
    write_secret(kit.home, "n-key", key + "\n")
    return kit.cli("route", "add", "bot-n", "--url-secret", "n-url", "--key-secret", "n-key", *extra)


def loaded(kit: Kit) -> dict[str, Any]:
    return tomllib.loads(kit.config_text())


@pytest.mark.parametrize(
    "url, key",
    [
        (URL, f"Bearer {KEY}"),
        (URL, "bearer crsr_abc"),
        (URL, "sk-ant-abcdef"),
        (URL, ""),
        ("http://api2.cursor.sh/automations/webhook/7d1e-routine-uuid", KEY),
        ("api2.cursor.sh/automations/webhook/7d1e-routine-uuid", KEY),
    ],
)
def test_route_add_secret_validation(kit: Kit, url: str, key: str) -> None:
    before = kit.config_text()
    result = add(kit, url, key)
    assert result.returncode == 2
    output = result.stdout + result.stderr
    assert "7d1e-routine-uuid" not in output
    assert KEY not in output and "crsr_abc" not in output and "sk-ant-abcdef" not in output
    assert kit.config_text() == before


def test_route_add_secret_validation_valid(kit: Kit) -> None:
    before = loaded(kit)
    result = add(kit, URL, KEY, "--header", "X-Grokbot-Bot: bot-n")
    assert result.returncode == 0, result.stderr
    assert "7d1e-routine-uuid" not in result.stdout + result.stderr and KEY not in result.stdout + result.stderr
    text = kit.config_text()
    assert KEY not in text and URL not in text
    cfg = loaded(kit)
    (sink_name,) = cfg["routes"]["bot-n"]["sinks"]
    assert cfg["sinks"][sink_name] == {
        "type": "grokbot-routine",
        "url_secret": "n-url",
        "key_secret": "n-key",
        "headers": {"X-Grokbot-Bot": "bot-n"},
    }
    assert cfg["routes"]["bot-a"] == before["routes"]["bot-a"]
    assert cfg["setup"] == before["setup"] and cfg["cli"] == before["cli"]


def test_route_add_secret_validation_missing_secret(kit: Kit) -> None:
    write_secret(kit.home, "n-url", URL + "\n")
    result = kit.cli("route", "add", "bot-n", "--url-secret", "n-url", "--key-secret", "nao-existe")
    assert result.returncode == 2
    assert "nao-existe" in result.stderr


def test_route_add_secret_validation_then_rm(kit: Kit) -> None:
    assert add(kit, URL, KEY).returncode == 0
    result = kit.cli("route", "rm", "bot-n")
    assert result.returncode == 0, result.stderr
    cfg = loaded(kit)
    assert "bot-n" not in cfg["routes"]
    assert "bot-a" in cfg["routes"] and "arquivo" in cfg["sinks"]
    assert kit.cli("route", "rm", "bot-n").returncode == 2
