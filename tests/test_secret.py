"""Provas do `grokbot-kit secret set` (check C88; AC 76, door 3)."""

import os
import pty
import select
import shutil
import stat
import time
from pathlib import Path

from conftest import Kit

VALUE = "crsr_valor_do_tty_9f8e7d"


def secret_path(kit: Kit, name: str) -> Path:
    return kit.home / ".secrets" / "grokbot-kit" / name


def read_until(fd: int, needle: bytes, timeout: float = 10) -> bytes:
    seen = b""
    deadline = time.monotonic() + timeout
    while needle not in seen:
        assert time.monotonic() < deadline, f"sem {needle!r}; saída: {seen!r}"
        ready, _, _ = select.select([fd], [], [], 0.1)
        if ready:
            try:
                chunk = os.read(fd, 1024)
            except OSError:
                break
            if not chunk:
                break
            seen += chunk
    return seen


def read_rest(fd: int) -> bytes:
    seen = b""
    while True:
        ready, _, _ = select.select([fd], [], [], 5)
        if not ready:
            return seen
        try:
            chunk = os.read(fd, 1024)
        except OSError:
            return seen
        if not chunk:
            return seen
        seen += chunk


# C88 - AC 76
def test_tty_noecho_modes_stdin_and_write_failure(kit: Kit) -> None:
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    pid, fd = pty.fork()
    if pid == 0:  # filho: sessão nova com o pty como terminal de controle
        os.execve(exe, [exe, "secret", "set", "rotina-key"], kit.env)
    prompt = read_until(fd, b":")
    os.write(fd, VALUE.encode() + b"\n")
    output = prompt + read_rest(fd)
    _, status = os.waitpid(pid, 0)
    os.close(fd)
    assert os.waitstatus_to_exitcode(status) == 0, output
    assert VALUE.encode() not in output, "o segredo apareceu no terminal (eco ligado)"
    path = secret_path(kit, "rotina-key")
    assert path.read_text(encoding="utf-8").rstrip("\n") == VALUE
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_tty_noecho_modes_stdin_and_write_failure_stdin(kit: Kit) -> None:
    result = kit.cli("secret", "set", "rotina-url", input="https://api2.cursor.sh/automations/webhook/u-1\n")
    assert result.returncode == 0, result.stderr
    assert "u-1" not in result.stdout + result.stderr
    path = secret_path(kit, "rotina-url")
    assert path.read_text(encoding="utf-8").rstrip("\n") == "https://api2.cursor.sh/automations/webhook/u-1"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_tty_noecho_modes_stdin_and_write_failure_overwrite_fixes_mode(kit: Kit) -> None:
    directory = kit.home / ".secrets" / "grokbot-kit"
    directory.mkdir(parents=True, mode=0o755)
    os.chmod(directory, 0o755)
    old = directory / "rotina-key"
    old.write_text("antigo\n", encoding="utf-8")
    os.chmod(old, 0o644)
    result = kit.cli("secret", "set", "rotina-key", input="novo\n")
    assert result.returncode == 0, result.stderr
    assert old.read_text(encoding="utf-8").rstrip("\n") == "novo"
    assert stat.S_IMODE(old.stat().st_mode) == 0o600
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700


def test_tty_noecho_modes_stdin_and_write_failure_cannot_write(kit: Kit) -> None:
    (kit.home / ".secrets").write_text("não é diretório", encoding="utf-8")
    result = kit.cli("secret", "set", "rotina-key", input="valor-que-nao-grava\n")
    assert result.returncode == 1
    assert "valor-que-nao-grava" not in result.stdout + result.stderr


def test_tty_noecho_modes_stdin_and_write_failure_invalid_name(kit: Kit) -> None:
    for name in ("../fora", ".oculto", "a/b", ""):
        result = kit.cli("secret", "set", name, input="valor\n")
        assert result.returncode == 1, name
    assert not (kit.home / ".secrets" / "fora").exists()
