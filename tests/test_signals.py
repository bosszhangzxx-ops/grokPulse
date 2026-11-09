"""Provas do timeout e da interrupção do `run` (checks C108-C110; AC 87-89, door 18).

Na fronteira, `grokbot-kit run` lança a CLI falsa com a armadilha de sinais (`FAKE_TRAP`) e um filho no mesmo grupo
(`FAKE_CHILD`); na própria camada, `terminal.classify` e a escada `run.stop_group` com uma folga curta.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from conftest import Kit

from grokbot_kit import run, terminal
from grokbot_kit.terminal import AgentOutput

CLEAN = AgentOutput(error=False, permission_denied=False, summary="")
FAILED = AgentOutput(error=True, permission_denied=True, summary="")


def start_run(kit: Kit, trap: Path, *args: str, **fake: str) -> subprocess.Popen[str]:
    exe = shutil.which("grokbot-kit")
    assert exe is not None, "console script grokbot-kit não instalado"
    env = {**kit.env, "FAKE_RECORD": str(kit.record), "FAKE_TRAP": str(trap), "FAKE_CHILD": "1", **fake}
    return subprocess.Popen(
        [exe, "run", "--tool", "opencode", "--target", "bot-a", "--label", "sinal", *args, "--", "durma"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=kit.home,
    )


def trap_lines(trap: Path) -> list[dict[str, Any]]:
    if not trap.exists():
        return []
    return [json.loads(line) for line in trap.read_text(encoding="utf-8").splitlines()]


def wait_ready(trap: Path, count: int = 2, timeout: float = 20) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready = [line for line in trap_lines(trap) if line.get("ready")]
        if len(ready) >= count:
            return ready
        time.sleep(0.05)
    raise AssertionError(f"agente e filho não ficaram prontos: {trap_lines(trap)}")


def kill_leftovers(trap: Path) -> None:
    """Limpeza quando uma prova falha no meio: nenhum agente falso fica rodando depois do teste."""
    for pgid in {line["pgid"] for line in trap_lines(trap) if line.get("ready")} - {os.getpgid(0)}:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def is_gone(pid: int) -> bool:
    """Morto ou zumbi à espera do init: nada mais roda com esse pid."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except FileNotFoundError:
        return True
    return stat.rsplit(")", 1)[1].split()[0] == "Z"


def assert_nothing_left(pids: list[int], timeout: float = 3) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not all(is_gone(pid) for pid in pids):
        time.sleep(0.05)
    assert all(is_gone(pid) for pid in pids), [pid for pid in pids if not is_gone(pid)]


def received(trap: Path, pid: int) -> list[tuple[str, float]]:
    return [(line["signal"], line["at"]) for line in trap_lines(trap) if line.get("pid") == pid and "signal" in line]


def outcome(event: dict[str, Any]) -> tuple[str, str, str]:
    return event["event"], event["status"], event["exit_reason"]


# C108 - AC 87
def test_timeout_ladder_and_exit_124_layer() -> None:
    assert terminal.classify(0, CLEAN, needs_input=True, stopped="timeout") == ("timeout", "timeout", "timeout")
    assert terminal.classify(1, FAILED, needs_input=False, stopped="timeout") == ("timeout", "timeout", "timeout")


def test_timeout_ladder_and_exit_124_stop_group_layer(tmp_path: Path) -> None:
    trap = tmp_path / "trap.jsonl"
    fake = Path(__file__).resolve().parent / "fakes" / "fake_agent.py"
    env = {**os.environ, "FAKE_ROLE": "child", "FAKE_TRAP": str(trap), "FAKE_IGNORE": "SIGINT,SIGTERM"}
    env["FAKE_SLEEP"] = "60"
    proc = subprocess.Popen([sys.executable, str(fake)], env=env, process_group=0)
    try:
        wait_ready(trap, count=1)
        sent = time.monotonic()
        os.killpg(proc.pid, signal.SIGINT)
        run.stop_group(proc, sent, grace=0.5)
        ended = time.monotonic()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        kill_leftovers(trap)
    signals = received(trap, proc.pid)
    assert [name for name, _ in signals] == ["SIGINT", "SIGTERM"]
    assert 0.4 <= signals[1][1] - signals[0][1] <= 1.0
    assert 0.9 <= ended - sent <= 2.0
    assert proc.returncode == -signal.SIGKILL
    assert_nothing_left([proc.pid])


def test_timeout_ladder_and_exit_124(kit: Kit, tmp_path: Path) -> None:
    trap = tmp_path / "trap.jsonl"
    launched = time.monotonic()
    proc = start_run(kit, trap, "--timeout", "1s", FAKE_SLEEP="120", FAKE_IGNORE="SIGINT,SIGTERM")
    try:
        ready = wait_ready(trap)
        _, stderr = proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
        kill_leftovers(trap)
    ended = time.monotonic()
    assert proc.returncode == 124, stderr
    pids = [line["pid"] for line in ready]
    assert len({line["pgid"] for line in ready}) == 1, "agente e filho no mesmo grupo"
    for pid in pids:
        signals = received(trap, pid)
        assert [name for name, _ in signals] == ["SIGINT", "SIGTERM"], (pid, signals)
        (_, sigint_at), (_, sigterm_at) = signals
        assert 0.5 <= sigint_at - launched <= 4, "SIGINT ao passar do timeout de 1 s"
        assert 9.5 <= sigterm_at - sigint_at <= 11, "SIGTERM 10 s depois do SIGINT"
        assert 9.5 <= ended - sigterm_at <= 13, "SIGKILL 10 s depois do SIGTERM"
    assert_nothing_left(pids)
    events = kit.sink_events()
    assert len(events) == 1, events
    assert outcome(events[0]) == ("timeout", "timeout", "timeout")
    assert events[0]["exit_code"] == 124


# C109 - AC 88
def test_sigint_sigterm_forwarded_exit_130_layer() -> None:
    expected = ("error", "interrupted", "interrupted")
    assert terminal.classify(0, CLEAN, needs_input=False, stopped="interrupted") == expected
    assert terminal.classify(1, FAILED, needs_input=True, stopped="interrupted") == expected


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM], ids=lambda s: s.name)
def test_sigint_sigterm_forwarded_exit_130(kit: Kit, tmp_path: Path, sig: signal.Signals) -> None:
    trap = tmp_path / "trap.jsonl"
    proc = start_run(kit, trap, FAKE_SLEEP="120")
    try:
        ready = wait_ready(trap)
        sent = time.monotonic()
        proc.send_signal(sig)
        _, stderr = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
        kill_leftovers(trap)
    assert proc.returncode == 130, stderr
    assert time.monotonic() - sent < 9, "o agente saiu com o sinal repassado; nada de esperar a escada"
    pids = [line["pid"] for line in ready]
    for pid in pids:
        assert [name for name, _ in received(trap, pid)] == [sig.name], pid
    assert_nothing_left(pids)
    events = kit.sink_events()
    assert len(events) == 1, events
    assert outcome(events[0]) == ("error", "interrupted", "interrupted")
    assert events[0]["exit_code"] == 130


def test_sigint_sigterm_forwarded_exit_130_agent_ignores_sigint(kit: Kit, tmp_path: Path) -> None:
    """Um agente que ignora o sinal repassado não segura o `run`: a escada do AC 87 continua com `SIGTERM`."""
    trap = tmp_path / "trap.jsonl"
    proc = start_run(kit, trap, FAKE_SLEEP="120", FAKE_IGNORE="SIGINT")
    try:
        ready = wait_ready(trap)
        proc.send_signal(signal.SIGINT)
        _, stderr = proc.communicate(timeout=40)
    finally:
        if proc.poll() is None:
            proc.kill()
        kill_leftovers(trap)
    assert proc.returncode == 130, stderr
    pids = [line["pid"] for line in ready]
    for pid in pids:
        assert [name for name, _ in received(trap, pid)] == ["SIGINT", "SIGTERM"], pid
    assert_nothing_left(pids)
    assert outcome(kit.sink_events()[0]) == ("error", "interrupted", "interrupted")


# C110 - AC 89
@pytest.mark.parametrize("tool", ["opencode", "claude", "codex"])
def test_missing_binary_exit_127(kit: Kit, tool: str) -> None:
    missing = kit.home / "nao-existe" / tool
    text = kit.config_text()
    section = f"[cli.{tool}]\n"
    assert section in text
    kit.write_config(text.replace(section, f"{section}bin = {json.dumps(str(missing))}\n", 1))
    result = kit.run("--tool", tool, "--target", "bot-a", "--label", "sem-bin", "--", "oi")
    assert result.returncode == 127, result.stderr
    assert len(kit.tasks()) == 1, "o task dir é criado antes de lançar"
    events = kit.sink_events()
    assert len(events) == 1, events
    assert outcome(events[0]) == ("error", "failed", "agent_error")
    assert events[0]["exit_code"] == 127
    assert events[0]["task_id"] == kit.task_dir().name
