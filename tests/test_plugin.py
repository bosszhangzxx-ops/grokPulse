"""Provas do ciclo de vida de um plugin: `grokbot-kit plugin list|show|add|rm` (checks C9-C26; AC 9-25, doors 1-4).

Tudo roda na fronteira (subprocesso `grokbot-kit` com `HOME` isolado), menos o predicado de tarefa rodando (C25), que
também é provado na própria camada.
"""

import json
import os
import pty
import re
import select
import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from conftest import Kit, plugin_manifest, write_plugin
from test_plugin_manifest import INVALID

from grokbot_kit import plugin

DOOR_4_KEYS = {"name", "version", "description", "source", "origin", "commit", "inputs", "capabilities", "support"}
CAPABILITIES = {"write", "network", "commands", "workspace_config", "skills"}
CLIS = {"claude", "opencode", "codex"}
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def plugins_root(kit: Kit) -> Path:
    return kit.home / ".grokbot-kit" / "plugins"


def entries(kit: Kit) -> list[str]:
    root = plugins_root(kit)
    return sorted(os.listdir(root)) if root.exists() else []


def listed(kit: Kit) -> list[dict[str, Any]]:
    result = kit.cli("plugin", "list", "--json")
    assert result.returncode == 0, result.stderr
    plugins: list[dict[str, Any]] = json.loads(result.stdout)["plugins"]
    return plugins


def install(kit: Kit, source: Path | str, *flags: str) -> subprocess.CompletedProcess[str]:
    return kit.cli("plugin", "add", str(source), "--yes", *flags)


def read_until(fd: int, marker: bytes, timeout: float = 10) -> bytes:
    seen = b""
    while marker not in seen:
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            break
        try:
            chunk = os.read(fd, 1024)
        except OSError:
            break
        if not chunk:
            break
        seen += chunk
    return seen


def add_on_tty(kit: Kit, source: Path, answer: bytes) -> tuple[int, bytes]:
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    pid, fd = pty.fork()
    if pid == 0:  # filho: o pty é o terminal de controle e o stdin
        os.execve(exe, [exe, "plugin", "add", str(source)], kit.env)
    output = read_until(fd, b"[y/N] ")
    os.write(fd, answer + b"\n")
    output += read_until(fd, b"\x00", timeout=5)
    _, status = os.waitpid(pid, 0)
    os.close(fd)
    return os.waitstatus_to_exitcode(status), output


def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def plugin_repo(tmp_path: Path) -> Path:
    """Repositório git com o plugin `teste` em `main`: a tag `v1` em 1.2.3 e um commit depois com a versão 2.0.0."""
    repo = write_plugin(tmp_path / "repo")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "v1")
    git(repo, "tag", "v1")
    manifest = plugin_manifest()
    manifest["version"] = "2.0.0"
    write_plugin(repo, manifest)
    git(repo, "commit", "-q", "-am", "v2")
    return repo


def running_meta(task_dir: Path, **meta: Any) -> None:
    task_dir.mkdir(parents=True)
    (task_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def now_rfc3339(delta: timedelta = timedelta()) -> str:
    return (datetime.now(UTC) + delta).strftime("%Y-%m-%dT%H:%M:%SZ")


# C9 - AC 9, door 4
def test_list_json_shape(kit: Kit, tmp_path: Path) -> None:
    assert install(kit, write_plugin(tmp_path / "teste")).returncode == 0
    plugins = listed(kit)
    assert [(p["name"], p["source"]) for p in plugins] == [
        ("bug-verify", "builtin"),
        ("code-review", "builtin"),
        ("teste", "dir"),
    ]
    for p in plugins:
        assert set(p) == DOOR_4_KEYS
    teste = plugins[2]
    assert teste["origin"] == str(tmp_path / "teste")
    assert teste["commit"] is None
    assert teste["inputs"] == {"pr": {"kind": "repo", "required": True}}
    assert teste["capabilities"] == {"write": "task-dir", "network": "on", "commands": ["git", "gh pr view"]}


# C10 - AC 10
def test_list_text_lines(kit: Kit, tmp_path: Path) -> None:
    assert install(kit, write_plugin(tmp_path / "teste")).returncode == 0
    result = kit.cli("plugin", "list")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 3
    assert lines[2] == "teste 1.2.3 dir - plugin de teste"
    for line, p in zip(lines, listed(kit), strict=True):
        assert line == f"{p['name']} {p['version']} {p['source']} - {p['description']}"


# C11 - AC 11
def test_show_by_name(kit: Kit) -> None:
    result = kit.cli("plugin", "show", "code-review", "--json")
    assert result.returncode == 0, result.stderr
    shown = json.loads(result.stdout)
    assert set(shown) == DOOR_4_KEYS
    assert shown["name"] == "code-review"
    assert shown["source"] == "builtin"
    assert set(shown["support"]) == CLIS
    for cells in shown["support"].values():
        assert set(cells) == CAPABILITIES
        assert set(cells.values()) <= {"os", "tool", "unsupported"}
    text = kit.cli("plugin", "show", "code-review")
    assert text.returncode == 0
    assert "inputs: pr (repo, required)" in text.stdout
    assert all(f"  {cli}: write=" in text.stdout for cli in CLIS)


# C12 - AC 12
def test_show_origin_without_writing(kit: Kit, tmp_path: Path) -> None:
    source = write_plugin(tmp_path / "teste")
    shown = kit.cli("plugin", "show", str(source), "--json")
    assert shown.returncode == 0, shown.stderr
    assert entries(kit) == []
    assert install(kit, source).returncode == 0
    assert json.loads(shown.stdout) == listed(kit)[2]

    bad = write_plugin(tmp_path / "ruim")
    (bad / "hooks").mkdir()
    show_bad = kit.cli("plugin", "show", str(bad))
    add_bad = install(kit, bad)
    assert show_bad.returncode == add_bad.returncode == 2
    message = show_bad.stderr.removeprefix("grokbot-kit plugin show: ")
    assert message == add_bad.stderr.removeprefix("grokbot-kit plugin add: ")
    assert "hooks" in message


# C13 - AC 13
def test_show_unknown_name(kit: Kit) -> None:
    result = kit.cli("plugin", "show", "nao-existe")
    assert result.returncode == 2
    assert "no plugin named nao-existe; run: grokbot-kit plugin list" in result.stderr


# C14 - AC 14, door 3
def test_add_dir_confirms_on_tty(kit: Kit, tmp_path: Path) -> None:
    source = write_plugin(tmp_path / "teste")
    code, output = add_on_tty(kit, source, b"n")
    assert code == 2, output
    assert b"capabilities: write=task-dir network=on" in output
    assert entries(kit) == []  # nada gravado, nem temporário

    code, output = add_on_tty(kit, source, b"y")
    assert code == 0, output
    assert b"capabilities: write=task-dir network=on" in output
    assert entries(kit) == ["teste"]
    installed = plugins_root(kit) / "teste"
    assert (installed / "grokbot-kit.toml").read_text() == (source / "grokbot-kit.toml").read_text()
    origin = json.loads((installed / "origin.json").read_text(encoding="utf-8"))
    assert set(origin) == {"source", "origin", "ref", "commit", "installed_at"}
    assert origin["source"] == "dir"
    assert origin["origin"] == str(source)
    assert Path(origin["origin"]).is_absolute()
    assert origin["ref"] is None
    assert origin["commit"] is None
    assert RFC3339.match(origin["installed_at"])


# C15 - AC 15
def test_add_yes_skips_prompt(kit: Kit, tmp_path: Path) -> None:
    result = install(kit, write_plugin(tmp_path / "teste"))
    assert result.returncode == 0, result.stderr
    assert "capabilities: write=task-dir network=on" in result.stdout
    assert "[y/N]" not in result.stdout + result.stderr
    assert result.stdout.splitlines()[-1] == f"installed teste 1.2.3 ({tmp_path / 'teste'})"
    assert entries(kit) == ["teste"]


# C16 - AC 16
def test_add_without_tty_refuses(kit: Kit, tmp_path: Path) -> None:
    result = kit.cli("plugin", "add", str(write_plugin(tmp_path / "teste")), input="y\n")
    assert result.returncode == 2
    assert "--yes" in result.stderr
    assert entries(kit) == []


# C17 - AC 17, door 3
def test_add_git_pins_commit(kit: Kit, tmp_path: Path) -> None:
    repo = plugin_repo(tmp_path)
    url = f"file://{repo}"
    tag_commit = git(repo, "rev-parse", "v1^{commit}")
    head_commit = git(repo, "rev-parse", "main")

    result = install(kit, url, "--ref", "v1")
    assert result.returncode == 0, result.stderr
    origin = json.loads((plugins_root(kit) / "teste" / "origin.json").read_text(encoding="utf-8"))
    assert origin["source"] == "git"
    assert origin["origin"] == url
    assert origin["ref"] == "v1"
    assert origin["commit"] == tag_commit
    assert len(origin["commit"]) == 40
    assert not (plugins_root(kit) / "teste" / ".git").exists()
    assert listed(kit)[2]["version"] == "1.2.3"

    result = kit.cli("plugin", "add", url, "--yes", "--replace")
    assert result.returncode == 0, result.stderr
    origin = json.loads((plugins_root(kit) / "teste" / "origin.json").read_text(encoding="utf-8"))
    assert origin["ref"] is None
    assert origin["commit"] == head_commit
    assert listed(kit)[2]["version"] == "2.0.0"


# C18 - AC 18, door 1
@pytest.mark.parametrize("part", ["hooks/", "commands/", "agents/", ".mcp.json", ".lsp.json"])
def test_add_refuses_executable_parts(kit: Kit, tmp_path: Path, part: str) -> None:
    source = write_plugin(tmp_path / "teste")
    if part.endswith("/"):
        (source / part).mkdir()
    else:
        (source / part).write_text("{}", encoding="utf-8")
    result = install(kit, source)
    assert result.returncode == 2
    assert part.rstrip("/") in result.stderr
    assert entries(kit) == []


# C19 - AC 19, door 2
@pytest.mark.parametrize(("case", "build", "message"), INVALID, ids=[c[0] for c in INVALID])
def test_add_refuses_invalid_manifest(
    kit: Kit, tmp_path: Path, case: str, build: Callable[[Path], None], message: str
) -> None:
    build(tmp_path / "p")
    result = install(kit, tmp_path / "p")
    assert result.returncode == 2, result.stderr
    assert message in result.stderr
    assert entries(kit) == []


# door 4: `--ref` fixa um commit de um git; com um diretório não há o que fixar
def test_add_refuses_ref_for_directory(kit: Kit, tmp_path: Path) -> None:
    result = install(kit, write_plugin(tmp_path / "p"), "--ref", "main")
    assert result.returncode == 2, result.stderr
    assert "--ref only applies to a git URL" in result.stderr
    assert entries(kit) == []


# C20 - AC 20
def test_add_refuses_builtin_name(kit: Kit, tmp_path: Path) -> None:
    result = install(kit, write_plugin(tmp_path / "cr", plugin_manifest("code-review")))
    assert result.returncode == 2
    assert "builtin" in result.stderr
    assert entries(kit) == []


# C21 - AC 21
def test_add_existing_needs_replace(kit: Kit, tmp_path: Path) -> None:
    assert install(kit, write_plugin(tmp_path / "teste")).returncode == 0
    manifest = plugin_manifest()
    manifest["version"] = "9.0.0"
    newer = write_plugin(tmp_path / "novo", manifest)

    result = install(kit, newer)
    assert result.returncode == 2
    assert "--replace" in result.stderr
    assert listed(kit)[2]["version"] == "1.2.3"

    result = install(kit, newer, "--replace")
    assert result.returncode == 0, result.stderr
    assert listed(kit)[2]["version"] == "9.0.0"
    assert listed(kit)[2]["origin"] == str(newer)
    assert entries(kit) == ["teste"]


# C22 - AC 22, door 3
def test_add_io_failure_leaves_nothing(kit: Kit, tmp_path: Path) -> None:
    locked = write_plugin(tmp_path / "trancado")
    os.chmod(locked, 0o000)
    try:
        result = install(kit, locked)
    finally:
        os.chmod(locked, 0o755)
    assert result.returncode == 1, result.stderr
    assert entries(kit) == []

    result = kit.cli("plugin", "add", f"file://{tmp_path / 'nao-existe'}", "--yes")
    assert result.returncode == 1, result.stderr
    assert "git clone" in result.stderr
    assert entries(kit) == []


# C23 - AC 23
def test_rm_installed(kit: Kit, tmp_path: Path) -> None:
    assert install(kit, write_plugin(tmp_path / "teste")).returncode == 0
    result = kit.cli("plugin", "rm", "teste")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "removed teste\n"
    assert entries(kit) == []
    assert [p["name"] for p in listed(kit)] == ["bug-verify", "code-review"]


# C24 - AC 24
@pytest.mark.parametrize("name", ["code-review", "nao-existe"])
def test_rm_refuses_builtin_and_unknown(kit: Kit, name: str) -> None:
    result = kit.cli("plugin", "rm", name)
    assert result.returncode == 2
    assert name in result.stderr


# C25 - AC 25
def test_running_task_predicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    tasks = tmp_path / ".grokbot-kit" / "tasks"
    now = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
    base = {"plugin": {"name": "teste"}, "finished_at": None, "timeout_seconds": 3600}
    running_meta(tasks / "a-rodando", **base, started_at="2026-10-21T11:30:00Z")
    running_meta(
        tasks / "b-terminada", **{**base, "finished_at": "2026-10-21T11:40:00Z"}, started_at="2026-10-21T11:30:00Z"
    )
    # janela: 10:58:59 + 3600 s + 60 s = 11:59:59, antes de `now`
    running_meta(tasks / "c-janela-vencida", **base, started_at="2026-10-21T10:58:59Z")
    running_meta(tasks / "d-outro-plugin", **{**base, "plugin": {"name": "outro"}}, started_at="2026-10-21T11:30:00Z")
    running_meta(tasks / "e-sem-plugin", finished_at=None, timeout_seconds=3600, started_at="2026-10-21T11:30:00Z")
    (tasks / "f-sem-meta").mkdir(parents=True)
    (tasks / "g-ilegivel").mkdir(parents=True)
    (tasks / "g-ilegivel" / "meta.json").write_text("{nao json", encoding="utf-8")
    assert plugin.running_tasks("teste", now) == ["a-rodando"]

    # na borda da janela: started_at + timeout + 60 s exatamente em `now` já não roda; 1 s antes, roda
    running_meta(tasks / "h-borda", **base, started_at="2026-10-21T10:59:00Z")
    running_meta(tasks / "i-dentro", **base, started_at="2026-10-21T10:59:01Z")
    assert plugin.running_tasks("teste", now) == ["a-rodando", "i-dentro"]


# C26 - AC 25
def test_rm_and_replace_refuse_running_task(kit: Kit, tmp_path: Path) -> None:
    assert install(kit, write_plugin(tmp_path / "teste")).returncode == 0
    task = "20261021T120000-rev-abc123"
    running_meta(
        kit.home / ".grokbot-kit" / "tasks" / task,
        plugin={"name": "teste"},
        finished_at=None,
        timeout_seconds=3600,
        started_at=now_rfc3339(),
    )
    result = kit.cli("plugin", "rm", "teste")
    assert result.returncode == 2
    assert task in result.stderr
    assert entries(kit) == ["teste"]

    manifest = plugin_manifest()
    manifest["version"] = "9.0.0"
    result = install(kit, write_plugin(tmp_path / "novo", manifest), "--replace")
    assert result.returncode == 2
    assert task in result.stderr
    assert listed(kit)[2]["version"] == "1.2.3"
