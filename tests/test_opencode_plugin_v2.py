"""Provas do plugin v2 do opencode (needs-input-reply, C29-C33; AC 21-23, doors 5, 6 e 8).

O asset é importado no `node` com um `ctx` falso (o `permission.hook` guarda o callback; o `session.get` diz se a
sessão é filha) e com o executável trocado por um `grokbot-kit` falso, que grava argv, stdin e env e responde o que
o teste mandar. Um preload embrulha o `spawn` para gravar as opções que o plugin passa.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ASSET = Path(__file__).resolve().parents[1] / "src" / "grokbot_kit" / "assets" / "opencode" / "grokbot-kit.v2.ts"

FAKE_KIT = """#!{python}
import json, os, sys, time
data = sys.stdin.read()
with open(os.environ["FAKE_KIT_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "stdin": data, "reply": os.environ.get("GROKBOT_KIT_REPLY")}}) + "\\n")
time.sleep(float(os.environ.get("FAKE_KIT_SLEEP", "0")))
sys.stdout.write(os.environ.get("FAKE_KIT_OUT", ""))
sys.exit(int(os.environ.get("FAKE_KIT_EXIT", "0")))
"""

PRELOAD = """
import cp from "node:child_process"
import { syncBuiltinESMExports } from "node:module"
import { appendFileSync } from "node:fs"
const original = cp.spawn
cp.spawn = (cmd, args, options) => {
  appendFileSync(process.env.SPAWN_LOG, JSON.stringify({ timeout: options?.timeout ?? null }) + "\\n")
  if (process.env.TEST_SPAWN_TIMEOUT) options = { ...options, timeout: Number(process.env.TEST_SPAWN_TIMEOUT) }
  return original(cmd, args, options)
}
syncBuiltinESMExports()
"""

HARNESS = """
const plugin = (await import(process.argv[2])).default
const hooks = {}
let registered = 0
const ctx = {
  permission: { hook: async (name, cb) => { registered++; hooks[name] = cb; return { dispose: async () => {} } } },
  session: { get: async ({ sessionID }) => ({ id: sessionID, parentID: sessionID === "child" ? "root" : undefined }) },
}
await plugin.setup(ctx)
const event = JSON.parse(process.argv[3])
let ticks = 0
const timer = setInterval(() => ticks++, 100)
if (hooks.evaluate) await hooks.evaluate(event)
clearInterval(timer)
console.log(JSON.stringify({ id: plugin.id, registered, event, ticks }))
"""


def ask_event(**extra: Any) -> dict[str, Any]:
    return {
        "sessionID": "s1",
        "action": "shell",
        "resources": ["touch x"],
        "effect": "ask",
        "source": {"type": "tool", "messageID": "m1", "id": "call-1"},
        **extra,
    }


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        node = shutil.which("node")
        assert node is not None, "o node é necessário para provar o plugin v2"
        self.node = node
        self.tmp = tmp_path
        self.fake = tmp_path / "grokbot-kit"
        self.fake.write_text(FAKE_KIT.format(python=sys.executable), encoding="utf-8")
        self.fake.chmod(0o755)
        self.plugin = tmp_path / "plugin.mjs"
        text = ASSET.read_text(encoding="utf-8").replace('"__GROKBOT_KIT_EXE__"', json.dumps(str(self.fake)))
        self.plugin.write_text(text, encoding="utf-8")
        (tmp_path / "preload.mjs").write_text(PRELOAD, encoding="utf-8")
        (tmp_path / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        self.task_dir = tmp_path / "task"
        self.task_dir.mkdir()
        self.set_wait(600)
        self.log = tmp_path / "kit.jsonl"
        self.spawn_log = tmp_path / "spawn.jsonl"

    def set_wait(self, seconds: int) -> None:
        (self.task_dir / "meta.json").write_text(json.dumps({"ask_wait_seconds": seconds}), encoding="utf-8")

    def run(self, event: dict[str, Any], *, task: bool = True, **env: str) -> dict[str, Any]:
        full = {
            **os.environ,
            "FAKE_KIT_LOG": str(self.log),
            "SPAWN_LOG": str(self.spawn_log),
            "GROKBOT_KIT_TASK_DIR": str(self.task_dir),
            **env,
        }
        full.pop("GROKBOT_KIT_TASK_ID", None)
        if task:
            full["GROKBOT_KIT_TASK_ID"] = "t-1"
        proc = subprocess.run(
            [
                self.node,
                "--import",
                str(self.tmp / "preload.mjs"),
                str(self.tmp / "harness.mjs"),
                str(self.plugin),
                json.dumps(event),
            ],
            capture_output=True,
            text=True,
            env=full,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        result: dict[str, Any] = json.loads(proc.stdout.strip().splitlines()[-1])
        return result

    def calls(self) -> list[dict[str, Any]]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def spawns(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.spawn_log.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


# C29 - AC 21
def test_evaluate_calls_emit(harness: Harness) -> None:
    out = harness.run(ask_event(), FAKE_KIT_OUT="{}")
    assert out["id"] == "grokbot-kit"
    assert out["registered"] == 1
    [call] = harness.calls()
    assert call["argv"] == ["emit", "--from", "opencode"]
    assert call["reply"] == "1"
    sent = json.loads(call["stdin"])
    assert sent["type"] == "permission.asked"
    assert sent["parentID"] is None
    props = sent["properties"]
    assert (props["permission"], props["patterns"], props["id"], props["sessionID"]) == (
        "shell",
        ["touch x"],
        "call-1",
        "s1",
    )


# C30 - AC 21
def test_does_not_block(harness: Harness) -> None:
    harness.set_wait(5)
    out = harness.run(ask_event(), FAKE_KIT_SLEEP="2", FAKE_KIT_OUT="{}")
    assert out["ticks"] >= 10
    assert harness.spawns() == [{"timeout": (5 + 60) * 1000}]


# C31 - AC 22
@pytest.mark.parametrize(
    ("env", "effect", "message"),
    [
        ({"FAKE_KIT_OUT": '{"effect":"allow","message":null}'}, "allow", None),
        ({"FAKE_KIT_OUT": '{"effect":"deny","message":"m"}'}, "deny", "m"),
        ({"FAKE_KIT_OUT": "{}"}, "ask", None),
        ({"FAKE_KIT_OUT": ""}, "ask", None),
        ({"FAKE_KIT_OUT": "não é json"}, "ask", None),
        ({"FAKE_KIT_OUT": '{"effect":"allow"}', "FAKE_KIT_EXIT": "1"}, "ask", None),
        ({"FAKE_KIT_OUT": '{"effect":"allow"}', "FAKE_KIT_SLEEP": "5", "TEST_SPAWN_TIMEOUT": "500"}, "ask", None),
    ],
    ids=["allow", "deny", "vazio-objeto", "vazio", "nao-json", "exit-1", "timeout"],
)
def test_applies_emit_decision(harness: Harness, env: dict[str, str], effect: str, message: str | None) -> None:
    out = harness.run(ask_event(), **env)
    assert out["event"]["effect"] == effect
    assert out["event"].get("message") == message


# C32 - AC 21
@pytest.mark.parametrize(
    "event", [ask_event(effect="allow"), ask_event(effect="deny"), ask_event(sessionID="child")], ids=str
)
def test_only_root_ask(harness: Harness, event: dict[str, Any]) -> None:
    out = harness.run(event, FAKE_KIT_OUT='{"effect":"allow","message":null}')
    assert out["event"]["effect"] == event["effect"]
    assert harness.calls() == []


# C33 - AC 23
def test_inert_without_task(harness: Harness) -> None:
    out = harness.run(ask_event(), task=False, FAKE_KIT_OUT='{"effect":"allow","message":null}')
    assert out["registered"] == 0
    assert out["event"]["effect"] == "ask"
    assert harness.calls() == []
