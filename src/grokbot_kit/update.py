"""`grokbot-kit update check|apply|skip|later`: a release nova no PyPI e o upgrade pelo instalador (kit-update).

A versão vem do PyPI (door 3) e fica em `~/.grokbot-kit/update.json` (door 2); a checagem vira o objeto da door 4,
que a skill e o `doctor` leem. O `apply` usa o instalador do recibo em `sys.prefix` (door 5) e regrava o plugin do
opencode com o executável novo.
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from grokbot_kit import config, launch, opencode_plugin
from grokbot_kit.payload import rfc3339

PYPI_URL = "https://pypi.org/pypi/grokbot-kit/json"
FETCH_TIMEOUT = 5
INSTALL_TIMEOUT = 300
PLUGIN_TIMEOUT = 60
FRESH_OK = timedelta(hours=24)
FRESH_ERROR = timedelta(hours=1)
LATER = timedelta(hours=24)
TASK_GRACE = timedelta(seconds=60)
STDERR_TAIL = 20
VERSION = re.compile(r"\d+\.\d+\.\d+")
UPGRADE_ARGV = {"uv": ["uv", "tool", "upgrade", "grokbot-kit"], "pipx": ["pipx", "upgrade", "grokbot-kit"]}
RECEIPTS = (("uv-receipt.toml", "uv"), ("pipx_metadata.json", "pipx"))
PINNED = "it may be pinned to a version: reinstall the latest grokbot-kit with the tool that installed it"
UNKNOWN_INSTALLER = "cannot tell how grokbot-kit was installed; upgrade it with the tool that installed it"


class FetchError(Exception):
    pass


def state_path() -> Path:
    return Path.home() / ".grokbot-kit" / "update.json"


def lock_path() -> Path:
    return Path.home() / ".grokbot-kit" / "update.lock"


def _parse(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def newer(a: str, b: str) -> bool:
    """`a` > `b`, comparando os três números de `X.Y.Z`."""
    return tuple(map(int, a.split("."))) > tuple(map(int, b.split(".")))


def ask(
    update_available: bool, latest: str | None, skipped: str | None, later_until: str | None, now: datetime
) -> bool:
    """Perguntar ao usuário: há versão nova, ela não foi pulada e o adiamento venceu (door 4)."""
    until = _parse(later_until)
    return update_available and latest != skipped and (until is None or now >= until)


def installer(prefix: Path) -> str | None:
    """O instalador do kit pelo recibo em `sys.prefix` (door 5)."""
    for receipt, name in RECEIPTS:
        if (prefix / receipt).exists():
            return name
    return None


def task_running(task_dir: Path, now: datetime) -> bool:
    """Sem `finished_at` e ainda dentro de `started_at` + `timeout_seconds` + 60 s; na dúvida, parada."""
    try:
        meta = json.loads((task_dir / "meta.json").read_text(encoding="utf-8"))
        if meta["finished_at"] is not None:
            return False
        deadline = datetime.fromisoformat(meta["started_at"]) + timedelta(seconds=meta["timeout_seconds"])
        return bool(deadline + TASK_GRACE > now)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def running_tasks(now: datetime) -> list[str]:
    root = config.tasks_dir()
    return [d.name for d in sorted(root.iterdir()) if d.is_dir() and task_running(d, now)] if root.is_dir() else []


def fetch(url: str) -> str:
    """O `info.version` do PyPI (door 3); qualquer falha vira `FetchError` com o motivo."""
    from grokbot_kit import __version__

    request = urllib.request.Request(url, headers={"User-Agent": f"grokbot-kit/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
            if response.status != 200:
                raise FetchError(f"HTTP {response.status} from {url}")
            data = json.loads(response.read())
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP {e.code} from {url}") from None
    except urllib.error.URLError as e:
        raise FetchError(f"cannot reach {url}: {e.reason}") from None
    except TimeoutError:
        raise FetchError(f"{url} did not answer in {FETCH_TIMEOUT}s") from None
    except OSError as e:
        raise FetchError(f"cannot reach {url}: {e}") from None
    except ValueError:
        raise FetchError(f"{url} did not return JSON") from None
    version = data.get("info", {}).get("version") if isinstance(data, dict) else None
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise FetchError(f"{url} has no X.Y.Z info.version")
    return version


def load_state() -> dict[str, Any] | None:
    try:
        state = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return state if isinstance(state, dict) else None


def save_state(state: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = ("checked_at", "latest", "error", "skipped", "later_until")
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({k: state.get(k) for k in keys}), encoding="utf-8")
    os.replace(tmp, path)


def _fresh(state: dict[str, Any], now: datetime) -> bool:
    checked = _parse(state.get("checked_at"))
    return checked is not None and now - checked < (FRESH_ERROR if state.get("error") is not None else FRESH_OK)


def refresh(now: datetime, *, force: bool = False) -> dict[str, Any]:
    """O estado da door 2, consultando o PyPI quando venceu (AC 1, 2 e 6) ou com `force`."""
    state = load_state() or {}
    if force or not _fresh(state, now):
        try:
            latest, error = fetch(os.environ.get("GROKBOT_KIT_PYPI_URL") or PYPI_URL), None
        except FetchError as e:
            latest, error = None, str(e)
        state.update(checked_at=rfc3339(now), latest=latest, error=error)
        save_state(state)
    return state


def status_of(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    """O objeto da door 4."""
    from grokbot_kit import __version__

    latest = state.get("latest")
    available = isinstance(latest, str) and bool(VERSION.fullmatch(latest)) and newer(latest, __version__)
    return {
        "installed": __version__,
        "latest": latest,
        "update_available": available,
        "ask": ask(available, latest, state.get("skipped"), state.get("later_until"), now),
        "skipped": state.get("skipped"),
        "later_until": state.get("later_until"),
        "checked_at": state.get("checked_at"),
        "installer": installer(Path(sys.prefix)),
        "error": state.get("error"),
    }


def status() -> dict[str, Any]:
    now = datetime.now(UTC)
    return status_of(refresh(now), now)


def check(as_json: bool) -> int:
    out = status()
    if as_json:
        print(json.dumps(out, ensure_ascii=False))
    elif out["error"] is not None:
        print(f"update check failed: {out['error']}")
    elif out["update_available"]:
        print(f"grokbot-kit {out['latest']} available (installed {out['installed']}); run: grokbot-kit update apply")
    else:
        print(f"grokbot-kit {out['installed']} is the latest")
    return 0


def skip(version: str) -> int:
    if not VERSION.fullmatch(version):
        print(f"grokbot-kit update skip: {version!r} is not a X.Y.Z version", file=sys.stderr)
        return 2
    state = refresh(datetime.now(UTC))
    state["skipped"] = version
    save_state(state)
    print(f"skipping grokbot-kit {version}")
    return 0


def later() -> int:
    now = datetime.now(UTC)
    state = refresh(now)
    state["later_until"] = rfc3339(now + LATER)
    save_state(state)
    print(f"asking again after {state['later_until']}")
    return 0


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _take_lock() -> bool:
    """O lock do `apply` (AC 26); um lock cujo pid não existe é tomado."""
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                pid = int(path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                pid = 0
            if pid > 0 and _pid_alive(pid):
                return False
            path.unlink(missing_ok=True)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return True
    return False


def _fail(code: int, message: str) -> int:
    print(message, file=sys.stderr)
    return code


def apply() -> int:
    if not _take_lock():
        return _fail(2, f"another grokbot-kit update apply is running ({lock_path()})")
    try:
        return _apply()
    finally:
        lock_path().unlink(missing_ok=True)


def _apply() -> int:
    now = datetime.now(UTC)
    state = refresh(now, force=True)
    out = status_of(state, now)
    if out["error"] is not None:
        return _fail(1, f"update check failed: {out['error']}")
    if not out["update_available"]:
        print(f"grokbot-kit {out['installed']} is the latest")
        return 0
    tool = out["installer"]
    if tool is None:
        return _fail(2, UNKNOWN_INSTALLER)
    running = running_tasks(now)
    if running:
        return _fail(2, "tasks still running, try again when they end: " + ", ".join(running))
    argv = UPGRADE_ARGV[tool]
    try:
        upgrade = subprocess.run(
            argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=INSTALL_TIMEOUT, check=False
        )
    except subprocess.TimeoutExpired:
        return _fail(1, f"{' '.join(argv)} did not finish in {INSTALL_TIMEOUT}s")
    except OSError as e:
        return _fail(1, f"cannot run {argv[0]}: {e.strerror}")
    tail = "\n".join(upgrade.stderr.splitlines()[-STDERR_TAIL:])
    if upgrade.returncode != 0:
        return _fail(1, f"{' '.join(argv)} exited with {upgrade.returncode}\n{tail}".rstrip())
    exe = launch.kit_executable()
    new = _version_of(exe) or out["latest"]
    if not newer(new, out["installed"]):
        # instalação fixada numa versão: o `uv tool upgrade` não atualiza e ainda sai com 0 (AC 37)
        return _fail(1, f"{argv[0]} left grokbot-kit at {new}; {PINNED}\n{tail}".rstrip())
    if opencode_plugin.plugin_path().exists() and _call([exe, "install", "opencode"]) != 0:
        return _fail(
            1, f"upgraded to {new}, but the opencode plugin was not rewritten; run: grokbot-kit install opencode"
        )
    state.update(skipped=None, later_until=None)
    save_state(state)
    print(f"grokbot-kit {out['installed']} -> {new}")
    return 0


def _call(argv: list[str]) -> int | None:
    try:
        return subprocess.run(
            argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=PLUGIN_TIMEOUT, check=False
        ).returncode
    except (OSError, subprocess.TimeoutExpired):
        return None


def _version_of(exe: str) -> str | None:
    """A versão do executável novo (`grokbot-kit X.Y.Z`); o código já carregado ainda é o antigo."""
    try:
        proc = subprocess.run(
            [exe, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=PLUGIN_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    words = proc.stdout.split()
    return words[-1] if proc.returncode == 0 and words and VERSION.fullmatch(words[-1]) else None
