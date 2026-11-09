"""Provas do `grokbot-kit update` (checks C1-C30 da kit-update; AC 1-26, doors 1-5).

O `check` roda pela CLI contra o receptor local (`GROKBOT_KIT_PYPI_URL`). O `apply` roda de um venv falso do kit em
`tmp_path`: `sys.prefix` é o venv, com o recibo da door 5, e os `uv`/`pipx` falsos de `tests/fakes/installers/`
trocam o `bin/grokbot-kit` do venv por um `grokbot-kit 9.0.0`.
"""

import json
import os
import site
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from conftest import FAKES, Kit, Receiver, closed_port_url

from grokbot_kit import __version__, update

KEYS = {"installed", "latest", "update_available", "ask", "skipped", "later_until", "checked_at", "installer", "error"}
STATE_KEYS = {"checked_at", "latest", "error", "skipped", "later_until"}
UNKNOWN = "cannot tell how grokbot-kit was installed; upgrade it with the tool that installed it"


def pypi(version: Any) -> tuple[int, str]:
    return (200, json.dumps({"info": {"version": version}, "releases": {}}))


def stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def ago(**delta: float) -> str:
    return stamp(datetime.now(UTC) - timedelta(**delta))


def state_path(home: Path) -> Path:
    return home / ".grokbot-kit" / "update.json"


def write_state(home: Path, **fields: Any) -> None:
    state = {"checked_at": ago(), "latest": __version__, "error": None, "skipped": None, "later_until": None}
    state.update(fields)
    path = state_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def read_state(home: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(state_path(home).read_text(encoding="utf-8"))
    return result


@pytest.fixture
def pkit(kit: Kit, receiver: Receiver) -> Kit:
    """O `kit` com o PyPI apontando para o receptor, que responde `9.0.0`."""
    kit.env = {**kit.env, "GROKBOT_KIT_PYPI_URL": receiver.url}
    receiver.respond(pypi("9.0.0"))
    return kit


def check(kit: Kit) -> dict[str, Any]:
    result = kit.cli("update", "check", "--json")
    assert result.returncode == 0, result.stderr
    out: dict[str, Any] = json.loads(result.stdout)
    return out


def gets(receiver: Receiver) -> int:
    return sum(1 for r in receiver.requests if r.method == "GET")


# C1 - AC 1, doors 2 e 3
@pytest.mark.parametrize(
    ("age", "state"),
    [(None, {}), ({"hours": 25}, {}), ({"hours": 1, "minutes": 5}, {"latest": None, "error": "boom"})],
    ids=["absent", "ok-older-than-24h", "error-older-than-1h"],
)
def test_check_fetches_when_stale(
    pkit: Kit, receiver: Receiver, age: dict[str, float] | None, state: dict[str, Any]
) -> None:
    if age is not None:
        write_state(pkit.home, checked_at=ago(**age), **state)
    before = datetime.now(UTC).replace(microsecond=0)
    out = check(pkit)
    assert gets(receiver) == 1
    saved = read_state(pkit.home)
    assert saved["latest"] == "9.0.0"
    assert saved["error"] is None
    assert datetime.fromisoformat(saved["checked_at"]) >= before
    assert out["latest"] == "9.0.0"


# C2 - AC 2
@pytest.mark.parametrize(
    ("age", "state"),
    [({"hours": 23}, {"latest": "8.0.0"}), ({"minutes": 59}, {"latest": None, "error": "boom"})],
    ids=["ok-younger-than-24h", "error-younger-than-1h"],
)
def test_check_uses_fresh_state(pkit: Kit, receiver: Receiver, age: dict[str, float], state: dict[str, Any]) -> None:
    write_state(pkit.home, checked_at=ago(**age), **state)
    out = check(pkit)
    assert gets(receiver) == 0
    assert out["latest"] == state["latest"]
    assert out["error"] == state.get("error")


# C3 - AC 3, AC 4
@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("0.3.0", "0.2.2", True),
        ("0.10.0", "0.9.0", True),
        ("1.0.0", "0.99.99", True),
        ("0.2.2", "0.2.2", False),
        ("0.2.1", "0.2.2", False),
        ("0.9.0", "0.10.0", False),
    ],
)
def test_compare_versions(a: str, b: str, expected: bool) -> None:
    assert update.newer(a, b) is expected


def lower_than(version: str) -> str:
    parts = [int(p) for p in version.split(".")]
    for i in (2, 1, 0):
        if parts[i]:
            parts[i] -= 1
            return ".".join(map(str, parts))
    raise AssertionError(version)


# C3 - AC 3, AC 4, na fronteira (`0.10.0` perde para `0.2.2` numa comparação de texto)
@pytest.mark.parametrize(
    ("latest", "available"), [(__version__, False), (lower_than(__version__), False), ("0.10.0", True)]
)
def test_check_update_available_boundary(pkit: Kit, receiver: Receiver, latest: str, available: bool) -> None:
    assert update.newer("0.10.0", __version__), "a versão instalada já passou de 0.10.0; troque o caso"
    receiver.respond(pypi(latest))
    out = check(pkit)
    assert out["update_available"] is available
    assert out["ask"] is available


# C4 - AC 5
@pytest.mark.parametrize(
    "response",
    ["closed", (500, "oops"), (200, "<html>not json</html>"), (200, json.dumps({"info": {}})), pypi("1.0")],
    ids=["refused", "500", "not-json", "no-version", "not-x-y-z"],
)
def test_check_failure_exit_zero(pkit: Kit, receiver: Receiver, response: Any) -> None:
    if response == "closed":
        pkit.env = {**pkit.env, "GROKBOT_KIT_PYPI_URL": closed_port_url()}
    else:
        receiver.respond(response)
    out = check(pkit)
    assert out["latest"] is None
    assert out["update_available"] is False
    assert out["ask"] is False
    assert out["error"]
    saved = read_state(pkit.home)
    assert saved["checked_at"]
    assert saved["error"] == out["error"]


# C4 - AC 5: um 2xx que não é `200` também é falha, mesmo com a versão no corpo
def test_check_failure_exit_zero_non_200(pkit: Kit, receiver: Receiver) -> None:
    receiver.respond((203, pypi("9.0.0")[1]))
    out = check(pkit)
    assert out["latest"] is None
    assert out["update_available"] is False
    assert "203" in out["error"]


# C5 - AC 5, door 3
def test_fetch_timeout_value(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> Any:
        seen["timeout"] = timeout
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(update.FetchError):
        update.fetch("http://127.0.0.1:9/pypi")
    assert seen["timeout"] == 5


# C5 - AC 5, door 3: a resposta que passa dos 5 s vira `error`
def test_fetch_timeout_slow_response(pkit: Kit, receiver: Receiver) -> None:
    receiver.delay = 7
    out = check(pkit)
    assert out["error"]
    assert out["update_available"] is False
    assert out["latest"] is None


# C6 - AC 6
def test_invalid_state_rewritten(pkit: Kit, receiver: Receiver) -> None:
    path = state_path(pkit.home)
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    check(pkit)
    assert gets(receiver) == 1
    assert read_state(pkit.home)["latest"] == "9.0.0"


# C7 - AC 7, door 4
def test_check_json_shape(pkit: Kit) -> None:
    result = pkit.cli("update", "check", "--json")
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert isinstance(out, dict)
    assert set(out) == KEYS
    assert out["installed"] == __version__


# C8 - AC 8
def test_check_text_lines(pkit: Kit, receiver: Receiver) -> None:
    result = pkit.cli("update", "check")
    assert result.returncode == 0
    assert result.stdout == f"grokbot-kit 9.0.0 available (installed {__version__}); run: grokbot-kit update apply\n"

    state_path(pkit.home).unlink()
    receiver.respond(pypi(__version__))
    result = pkit.cli("update", "check")
    assert result.stdout == f"grokbot-kit {__version__} is the latest\n"

    state_path(pkit.home).unlink()
    receiver.respond((500, "oops"))
    result = pkit.cli("update", "check")
    assert result.returncode == 0
    error = read_state(pkit.home)["error"]
    assert result.stdout == f"update check failed: {error}\n"


# C9 - AC 9, door 5
@pytest.mark.parametrize(
    ("receipt", "expected"), [("uv-receipt.toml", "uv"), ("pipx_metadata.json", "pipx"), (None, None)]
)
def test_installer_detection(tmp_path: Path, receipt: str | None, expected: str | None) -> None:
    if receipt:
        (tmp_path / receipt).write_text("", encoding="utf-8")
    assert update.installer(tmp_path) == expected


# C11 - AC 10, door 3
def test_user_agent_header(pkit: Kit, receiver: Receiver) -> None:
    check(pkit)
    (request,) = receiver.requests
    assert request.method == "GET"
    assert request.headers["user-agent"] == f"grokbot-kit/{__version__}"


# C12 - door 2
def test_state_file_shape(pkit: Kit) -> None:
    check(pkit)
    assert set(read_state(pkit.home)) == STATE_KEYS
    assert sorted(p.name for p in (pkit.home / ".grokbot-kit").iterdir()) == ["update.json"]


# C13 - AC 11
def test_skip_records_version(pkit: Kit) -> None:
    check(pkit)
    result = pkit.cli("update", "skip", "9.0.0")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "skipping grokbot-kit 9.0.0\n"
    assert read_state(pkit.home)["skipped"] == "9.0.0"


# C14 - AC 12
@pytest.mark.parametrize("version", ["latest", "1.2", "v1.2.3", "1.2.3.4"])
def test_skip_rejects_bad_version(pkit: Kit, version: str) -> None:
    check(pkit)
    before = state_path(pkit.home).read_bytes()
    result = pkit.cli("update", "skip", version)
    assert result.returncode == 2
    assert state_path(pkit.home).read_bytes() == before


# C15 - AC 13, AC 14
def test_skip_until_newer(pkit: Kit, receiver: Receiver) -> None:
    assert pkit.cli("update", "skip", "9.0.0").returncode == 0
    out = check(pkit)
    assert out["update_available"] is True
    assert out["ask"] is False
    assert out["skipped"] == "9.0.0"

    receiver.respond(pypi("9.0.1"))
    write_state(pkit.home, **{**read_state(pkit.home), "checked_at": ago(hours=25)})
    out = check(pkit)
    assert out["latest"] == "9.0.1"
    assert out["ask"] is True


# C16 - AC 15
def test_later_records_24h(pkit: Kit) -> None:
    check(pkit)
    result = pkit.cli("update", "later")
    assert result.returncode == 0, result.stderr
    later_until = read_state(pkit.home)["later_until"]
    assert result.stdout == f"asking again after {later_until}\n"
    target = datetime.now(UTC) + timedelta(hours=24)
    assert abs((datetime.fromisoformat(later_until) - target).total_seconds()) <= 60


# C17 - AC 16
def test_later_until_gates_ask(pkit: Kit) -> None:
    write_state(pkit.home, latest="9.0.0", later_until=stamp(datetime.now(UTC) + timedelta(hours=2)))
    out = check(pkit)
    assert out["update_available"] is True
    assert out["ask"] is False

    write_state(pkit.home, latest="9.0.0", later_until=ago(minutes=1))
    assert check(pkit)["ask"] is True


NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
FUTURE = "2026-10-21T13:00:00Z"
PAST = "2026-10-21T11:00:00Z"


# C18 - door 4
@pytest.mark.parametrize(
    ("available", "skipped", "later_until", "expected"),
    [
        (True, None, None, True),
        (True, "8.0.0", PAST, True),
        (False, None, None, False),
        (True, "9.0.0", None, False),
        (True, None, FUTURE, False),
        (True, "9.0.0", FUTURE, False),
    ],
)
def test_ask_table(available: bool, skipped: str | None, later_until: str | None, expected: bool) -> None:
    assert update.ask(available, "9.0.0", skipped, later_until, NOW) is expected


# --- apply -----------------------------------------------------------------------------------------------------


@dataclass
class Venv:
    root: Path
    kit: Kit

    @property
    def exe(self) -> Path:
        return self.root / "bin" / "grokbot-kit"

    def apply(self, timeout: float = 60, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.root / "bin" / "python"), str(self.exe), "update", "apply"],
            capture_output=True,
            text=True,
            env={**self.kit.env, **env},
            cwd=self.kit.home,
            check=False,
            timeout=timeout,
        )

    def upgrader_calls(self) -> list[dict[str, Any]]:
        return [c for c in self.kit.calls() if c["tool"].startswith("upgrader:")]

    def new_kit_calls(self) -> list[dict[str, Any]]:
        return [c for c in self.kit.calls() if c["tool"] == "new-kit"]


def make_venv(root: Path, receipt: str | None) -> Path:
    """Venv mínimo cujo `sys.prefix` é `root`, que importa o kit do venv dos testes."""
    real = os.path.realpath(sys.executable)
    (root / "bin").mkdir(parents=True)
    (root / "pyvenv.cfg").write_text(
        f"home = {os.path.dirname(real)}\ninclude-system-site-packages = false\nversion = {sys.version.split()[0]}\n",
        encoding="utf-8",
    )
    (root / "bin" / "python").symlink_to(real)
    packages = root / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    packages.mkdir(parents=True)
    (packages / "_kit.pth").write_text(f"import site; site.addsitedir({site.getsitepackages()[0]!r})\n")
    exe = root / "bin" / "grokbot-kit"
    exe.write_text(
        f"#!{root / 'bin' / 'python'}\nimport sys\nfrom grokbot_kit.cli import main\nsys.exit(main())\n",
        encoding="utf-8",
    )
    exe.chmod(0o755)
    if receipt:
        (root / receipt).write_text("", encoding="utf-8")
    return root


def venv_for(kit: Kit, receiver: Receiver, receipt: str | None = "uv-receipt.toml") -> Venv:
    root = make_venv(kit.home.parent / "venv", receipt)
    kit.env = {
        "HOME": str(kit.home),
        "PATH": os.pathsep.join([str(FAKES / "installers"), "/usr/bin", "/bin"]),
        "LANG": "C.UTF-8",
        "FAKE_CALLS": str(kit.home.parent / "calls.jsonl"),
        "FAKE_KIT_EXE": str(root / "bin" / "grokbot-kit"),
        "GROKBOT_KIT_PYPI_URL": receiver.url,
    }
    receiver.respond(pypi("9.0.0"))
    return Venv(root, kit)


def write_plugin(home: Path) -> None:
    path = home / ".config" / "opencode" / "plugins" / "grokbot-kit.ts"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("// plugin velho\n", encoding="utf-8")


# C19 - AC 17, door 5
@pytest.mark.parametrize(
    ("receipt", "call"),
    [
        ("uv-receipt.toml", {"tool": "upgrader:uv", "argv": ["tool", "upgrade", "grokbot-kit"]}),
        ("pipx_metadata.json", {"tool": "upgrader:pipx", "argv": ["upgrade", "grokbot-kit"]}),
    ],
)
def test_apply_runs_installer(kit: Kit, receiver: Receiver, receipt: str, call: dict[str, Any]) -> None:
    venv = venv_for(kit, receiver, receipt)
    write_state(kit.home, latest=__version__)
    result = venv.apply()
    assert result.returncode == 0, result.stderr
    assert gets(receiver) == 1
    assert venv.upgrader_calls() == [call]


def in_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, receiver: Receiver) -> None:
    """O `update.apply()` no próprio processo: `HOME` e `sys.prefix` em `tmp_path`, recibo `uv`, PyPI no receptor."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    (prefix / "uv-receipt.toml").write_text("", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GROKBOT_KIT_PYPI_URL", receiver.url)
    monkeypatch.setenv("PATH", os.pathsep.join([str(FAKES / "installers"), "/usr/bin", "/bin"]))
    monkeypatch.setattr(sys, "prefix", str(prefix))
    receiver.respond(pypi("9.0.0"))


# C20 - AC 17
def test_installer_timeout_value(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, receiver: Receiver) -> None:
    in_process(monkeypatch, tmp_path, receiver)
    seen: list[dict[str, Any]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.append({"argv": argv, **kwargs})
        return subprocess.CompletedProcess(argv, 1, "", "nope\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert update.apply() == 1
    (call,) = seen
    assert call["argv"][-3:] == ["tool", "upgrade", "grokbot-kit"]
    assert call["timeout"] == 300


# C21 - AC 18
@pytest.mark.parametrize("plugin", [True, False], ids=["plugin", "no-plugin"])
def test_apply_rewrites_plugin_with_new_exe(kit: Kit, receiver: Receiver, plugin: bool) -> None:
    venv = venv_for(kit, receiver)
    if plugin:
        write_plugin(kit.home)
    result = venv.apply()
    assert result.returncode == 0, result.stderr
    assert venv.new_kit_calls() == ([{"tool": "new-kit", "argv": ["install", "opencode"]}] if plugin else [])


# C22 - AC 19
def test_apply_success_output_and_state(kit: Kit, receiver: Receiver) -> None:
    venv = venv_for(kit, receiver)
    # o PyPI diz 8.0.0 e o executável novo responde 9.0.0: a `<nova>` vem do `--version` do executável
    receiver.respond(pypi("8.0.0"))
    write_plugin(kit.home)
    write_state(kit.home, skipped="9.0.0", later_until=stamp(datetime.now(UTC) + timedelta(hours=5)))
    result = venv.apply()
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"grokbot-kit {__version__} -> 9.0.0\n"
    state = read_state(kit.home)
    assert state["skipped"] is None
    assert state["later_until"] is None


# C22 - AC 19: sem `--version` legível no executável novo, a `<nova>` é o `latest` da checagem
def test_apply_success_output_and_state_version_unreadable(kit: Kit, receiver: Receiver) -> None:
    venv = venv_for(kit, receiver)
    result = venv.apply(FAKE_NEW_VERSION="broken")
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"grokbot-kit {__version__} -> 9.0.0\n"


# C23 - AC 20
def test_apply_already_latest(kit: Kit, receiver: Receiver) -> None:
    venv = venv_for(kit, receiver)
    receiver.respond(pypi(__version__))
    result = venv.apply()
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"grokbot-kit {__version__} is the latest\n"
    assert venv.upgrader_calls() == []


# C24 - AC 21
def test_apply_check_failed(kit: Kit, receiver: Receiver) -> None:
    venv = venv_for(kit, receiver)
    result = venv.apply(GROKBOT_KIT_PYPI_URL=closed_port_url())
    assert result.returncode == 1
    assert result.stderr.startswith("update check failed:")
    assert venv.upgrader_calls() == []


# C25 - AC 22
def test_apply_unknown_installer(kit: Kit, receiver: Receiver) -> None:
    venv = venv_for(kit, receiver, receipt=None)
    result = venv.apply()
    assert result.returncode == 2
    assert UNKNOWN in result.stderr
    assert venv.upgrader_calls() == []


def write_meta(task_dir: Path, **meta: Any) -> None:
    task_dir.mkdir(parents=True)
    (task_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


# C26 - AC 23
def test_running_task_predicate(tmp_path: Path) -> None:
    now = NOW
    started = stamp(now - timedelta(minutes=10))
    cases = {
        "running": ({"started_at": started, "timeout_seconds": 1800, "finished_at": None}, True),
        "in-grace": (
            {"started_at": stamp(now - timedelta(seconds=1830)), "timeout_seconds": 1800, "finished_at": None},
            True,
        ),
        "finished": ({"started_at": started, "timeout_seconds": 1800, "finished_at": stamp(now)}, False),
        "expired": (
            {"started_at": stamp(now - timedelta(hours=1)), "timeout_seconds": 1800, "finished_at": None},
            False,
        ),
    }
    for name, (meta, expected) in cases.items():
        write_meta(tmp_path / name, task_id=name, **meta)
        assert update.task_running(tmp_path / name, now) is expected, name
    (tmp_path / "no-meta").mkdir()
    assert update.task_running(tmp_path / "no-meta", now) is False
    (tmp_path / "bad-meta").mkdir()
    (tmp_path / "bad-meta" / "meta.json").write_text("{not json", encoding="utf-8")
    assert update.task_running(tmp_path / "bad-meta", now) is False


# C27 - AC 23
def test_apply_refuses_running_task(kit: Kit, receiver: Receiver) -> None:
    venv = venv_for(kit, receiver)
    task_id = "20261021T120000Z-bot-a-a1b2c3"
    write_meta(
        kit.home / ".grokbot-kit" / "tasks" / task_id,
        task_id=task_id,
        started_at=ago(minutes=5),
        timeout_seconds=1800,
        finished_at=None,
    )
    result = venv.apply()
    assert result.returncode == 2
    assert task_id in result.stderr
    assert venv.upgrader_calls() == []


# C28 - AC 24
def test_apply_installer_failed(kit: Kit, receiver: Receiver) -> None:
    venv = venv_for(kit, receiver)
    write_plugin(kit.home)
    result = venv.apply(FAKE_UPGRADE_EXIT="3", FAKE_UPGRADE_STDERR_LINES="30")
    assert result.returncode == 1
    assert "3" in result.stderr.splitlines()[0]
    for i in range(1, 31):
        assert (f"installer line {i:02d}" in result.stderr) is (i > 10), i
    assert venv.new_kit_calls() == []


# C28 - AC 24: o instalador que passa do timeout
def test_apply_installer_failed_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, receiver: Receiver) -> None:
    in_process(monkeypatch, tmp_path, receiver)
    monkeypatch.setattr(update, "INSTALL_TIMEOUT", 1)
    monkeypatch.setenv("FAKE_UPGRADE_SLEEP", "5")
    monkeypatch.setenv("FAKE_CALLS", str(tmp_path / "calls.jsonl"))
    assert update.apply() == 1
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [c["tool"] for c in calls] == ["upgrader:uv"]


# C28 - AC 24: o instalador do recibo não existe no `PATH`
def test_apply_installer_failed_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, receiver: Receiver, capsys: pytest.CaptureFixture[str]
) -> None:
    in_process(monkeypatch, tmp_path, receiver)
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert update.apply() == 1
    assert capsys.readouterr().err.startswith("cannot run uv:")


# C29 - AC 25
def test_apply_plugin_failed(kit: Kit, receiver: Receiver) -> None:
    venv = venv_for(kit, receiver)
    write_plugin(kit.home)
    result = venv.apply(FAKE_NEW_KIT_EXIT="1")
    assert result.returncode == 1
    message = "upgraded to 9.0.0, but the opencode plugin was not rewritten; run: grokbot-kit install opencode"
    assert message in result.stderr


# C39 - AC 37: o executável novo responde a mesma versão ou uma menor que a instalada
@pytest.mark.parametrize("left", [__version__, lower_than(__version__)], ids=["same", "lower"])
def test_apply_installer_left_version(kit: Kit, receiver: Receiver, left: str) -> None:
    venv = venv_for(kit, receiver)
    write_plugin(kit.home)
    later_until = stamp(datetime.now(UTC) + timedelta(hours=5))
    write_state(kit.home, skipped="9.0.0", later_until=later_until)
    result = venv.apply(FAKE_NEW_VERSION=left, FAKE_UPGRADE_STDERR_LINES="25")
    assert result.returncode == 1
    message = (
        f"uv left grokbot-kit at {left}; it may be pinned to a version: "
        "reinstall the latest grokbot-kit with the tool that installed it"
    )
    assert result.stderr.splitlines()[0] == message
    for i in range(1, 26):
        assert (f"installer line {i:02d}" in result.stderr) is (i > 5), i
    assert venv.new_kit_calls() == []
    state = read_state(kit.home)
    assert state["skipped"] == "9.0.0"
    assert state["later_until"] == later_until


def dead_pid() -> int:
    proc = subprocess.Popen(["/bin/true"])
    proc.wait()
    return proc.pid


# C30 - AC 26
def test_apply_lock(kit: Kit, receiver: Receiver) -> None:
    venv = venv_for(kit, receiver)
    lock = kit.home / ".grokbot-kit" / "update.lock"
    lock.parent.mkdir(parents=True)

    lock.write_text(str(os.getpid()), encoding="utf-8")
    result = venv.apply()
    assert result.returncode == 2
    assert venv.upgrader_calls() == []
    assert lock.exists()

    lock.write_text(str(dead_pid()), encoding="utf-8")
    result = venv.apply()
    assert result.returncode == 0, result.stderr
    assert len(venv.upgrader_calls()) == 1
    assert not lock.exists()


# C30 - AC 26: um lock ilegível não tem dono vivo e é tomado
def test_apply_lock_unreadable(kit: Kit, receiver: Receiver) -> None:
    venv = venv_for(kit, receiver)
    lock = kit.home / ".grokbot-kit" / "update.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("not a pid", encoding="utf-8")
    result = venv.apply()
    assert result.returncode == 0, result.stderr
    assert len(venv.upgrader_calls()) == 1
    assert not lock.exists()


# C57 - AC 19 da needs-input-reply, Impact
def test_apply_rewrites_plugin_for_major(kit: Kit, receiver: Receiver) -> None:
    import shutil

    from conftest import FAKES

    venv = venv_for(kit, receiver)
    write_state(kit.home, latest=__version__)
    path = kit.home / ".config" / "opencode" / "plugins" / "grokbot-kit.ts"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("// grokbot-kit opencode plugin for opencode 1\n// plugin velho\n", encoding="utf-8")
    result = venv.apply()
    assert result.returncode == 0, result.stderr
    [call] = venv.new_kit_calls()
    assert call["argv"] == ["install", "opencode"]
    # o kit novo roda o mesmo `install opencode` que este kit, aqui com um opencode 2.x no PATH
    bin_dir = kit.home.parent / "oc-bin"
    bin_dir.mkdir()
    (bin_dir / "opencode").symlink_to(FAKES / "opencode")
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    kit.env = {**kit.env, "PATH": f"{bin_dir}{os.pathsep}{kit.env['PATH']}", "FAKE_VERSION": "opencode v2.2.4"}
    import subprocess

    rewritten = subprocess.run([exe, *call["argv"]], env=kit.env, capture_output=True, text=True, check=False)
    assert rewritten.returncode == 0, rewritten.stderr
    assert path.read_text(encoding="utf-8").startswith("// grokbot-kit opencode plugin for opencode 2\n")
