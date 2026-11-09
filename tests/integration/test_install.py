"""Prova da instalação isolada com `uv tool` (check C123; door 6). Roda só com `-m integration`.

O wheel é construído deste checkout e instalado num `HOME` limpo. O cache e os Pythons gerenciados do `uv` do
usuário são reaproveitados (`UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`) para não baixar de novo um Python que já está
no box; o ambiente da ferramenta e o executável ficam no `HOME` limpo.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

TYPE_CHECKING = False
if TYPE_CHECKING:
    from conftest import Receiver

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


def uv() -> str:
    found = shutil.which("uv")
    if found is None:
        pytest.fail("uv não está instalado no box")
    return found


def uv_dir(*args: str) -> str:
    return subprocess.run([uv(), *args], capture_output=True, text=True, check=True).stdout.strip()


# C123 - door 6
def test_uv_tool_install_isolated(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    subprocess.run([uv(), "build", "--wheel", "-o", str(dist)], cwd=ROOT, capture_output=True, check=True)
    (wheel,) = dist.glob("grokbot_kit-*.whl")

    home = tmp_path / "home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("UV_", "XDG_", "VIRTUAL_ENV", "PYTHON"))}
    bin_dir = home / ".local" / "bin"
    env.update(
        HOME=str(home),
        PATH=os.pathsep.join([str(bin_dir), os.path.dirname(uv()), "/usr/bin", "/bin"]),
        UV_CACHE_DIR=uv_dir("cache", "dir"),
        UV_PYTHON_INSTALL_DIR=uv_dir("python", "dir"),
    )
    installed = subprocess.run(
        [uv(), "tool", "install", "--managed-python", str(wheel)], capture_output=True, text=True, env=env, check=False
    )
    assert installed.returncode == 0, installed.stderr

    exe = bin_dir / "grokbot-kit"
    assert exe.exists()
    version = subprocess.run([str(exe), "--version"], capture_output=True, text=True, env=env, check=False)
    assert version.returncode == 0, version.stderr
    assert version.stdout.startswith("grokbot-kit ")

    tool_python = home / ".local" / "share" / "uv" / "tools" / "grokbot-kit" / "bin" / "python"
    assert tool_python.exists()
    real_python = Path(os.path.realpath(tool_python))
    assert real_python.is_relative_to(Path(env["UV_PYTHON_INSTALL_DIR"])), real_python

    system = subprocess.run(
        ["/usr/bin/python3", "-I", "-c", "import grokbot_kit"], capture_output=True, text=True, env=env, check=False
    )
    assert system.returncode != 0
    assert "ModuleNotFoundError" in system.stderr


def install_kit(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    """O kit instalado por `uv tool install --managed-python <wheel deste checkout>` num `HOME` limpo."""
    dist = tmp_path / "dist"
    subprocess.run([uv(), "build", "--wheel", "-o", str(dist)], cwd=ROOT, capture_output=True, check=True)
    (wheel,) = dist.glob("grokbot_kit-*.whl")
    home = tmp_path / "home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("UV_", "XDG_", "VIRTUAL_ENV", "PYTHON"))}
    bin_dir = home / ".local" / "bin"
    env.update(
        HOME=str(home),
        PATH=os.pathsep.join([str(bin_dir), os.path.dirname(uv()), "/usr/bin", "/bin"]),
        UV_CACHE_DIR=uv_dir("cache", "dir"),
        UV_PYTHON_INSTALL_DIR=uv_dir("python", "dir"),
    )
    installed = subprocess.run(
        [uv(), "tool", "install", "--managed-python", str(wheel)], capture_output=True, text=True, env=env, check=False
    )
    assert installed.returncode == 0, installed.stderr
    return home, env, bin_dir / "grokbot-kit"


# C10 - kit-update AC 9, door 5
def test_update_installer_uv(tmp_path: Path) -> None:
    from conftest import closed_port_url

    _, env, exe = install_kit(tmp_path)
    env["GROKBOT_KIT_PYPI_URL"] = closed_port_url()
    result = subprocess.run(
        [str(exe), "update", "check", "--json"], capture_output=True, text=True, env=env, check=False
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["installer"] == "uv"


def clean_env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("UV_", "XDG_", "VIRTUAL_ENV", "PYTHON"))}
    env.update(
        HOME=str(home),
        PATH=os.pathsep.join([str(home / ".local" / "bin"), os.path.dirname(uv()), "/usr/bin", "/bin"]),
        UV_CACHE_DIR=uv_dir("cache", "dir"),
        UV_PYTHON_INSTALL_DIR=uv_dir("python", "dir"),
    )
    return env


def build_wheel_as(tmp_path: Path, version: str, out: Path) -> None:
    """Uma wheel deste checkout com a versão trocada, para um upgrade real sem passar pelo PyPI."""
    src = tmp_path / f"src-{version}"
    shutil.copytree(ROOT / "src", src / "src", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("README.md", "LICENSE"):
        shutil.copy(ROOT / name, src / name)
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    (src / "pyproject.toml").write_text(
        re.sub(r'(?m)^version = ".*"$', f'version = "{version}"', text), encoding="utf-8"
    )
    subprocess.run([uv(), "build", "--wheel", "-o", str(out)], cwd=src, capture_output=True, check=True)


# C31 - kit-update AC 17, AC 18, AC 19, door 5 (AD-037)
def test_update_apply_uv(tmp_path: Path, receiver: "Receiver") -> None:
    links = tmp_path / "links"
    build_wheel_as(tmp_path, "50.0.0", links)
    home = tmp_path / "home"
    home.mkdir()
    env = clean_env(home)
    installed = subprocess.run(
        [uv(), "tool", "install", "--managed-python", "--find-links", str(links), "grokbot-kit"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    exe = home / ".local" / "bin" / "grokbot-kit"
    plugin = subprocess.run([str(exe), "install", "opencode"], env=env, capture_output=True, check=False)
    assert plugin.returncode == 0, plugin.stderr
    build_wheel_as(tmp_path, "50.0.1", links)
    receiver.respond((200, json.dumps({"info": {"version": "99.0.0"}})))
    env["GROKBOT_KIT_PYPI_URL"] = receiver.url
    result = subprocess.run(
        [str(exe), "update", "apply"], capture_output=True, text=True, env=env, timeout=600, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "grokbot-kit 50.0.0 -> 50.0.1\n"
    plugin_text = (home / ".config" / "opencode" / "plugins" / "grokbot-kit.ts").read_text(encoding="utf-8")
    assert f"const GROKBOT_KIT = {json.dumps(str(exe))}" in plugin_text


# C40 - kit-update AC 37 (AD-037)
def test_update_apply_pinned_uv(tmp_path: Path, receiver: "Receiver") -> None:
    _, env, exe = install_kit(tmp_path)
    version = subprocess.run(
        [str(exe), "--version"], capture_output=True, text=True, env=env, check=True
    ).stdout.split()[-1]
    receiver.respond((200, json.dumps({"info": {"version": "9.0.0"}})))
    env["GROKBOT_KIT_PYPI_URL"] = receiver.url
    result = subprocess.run(
        [str(exe), "update", "apply"], capture_output=True, text=True, env=env, timeout=600, check=False
    )
    assert result.returncode == 1
    assert f"uv left grokbot-kit at {version}; it may be pinned to a version" in result.stderr


# C49 - needs-input-reply, Assumptions: o instalador oficial atualiza uma CLI já instalada
def test_upgrade_opencode_real(tmp_path: Path) -> None:
    import urllib.request

    home = tmp_path / "home"
    home.mkdir()
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    env = {"HOME": str(home), "PATH": os.pathsep.join([os.path.dirname(exe), "/usr/bin", "/bin"]), "LANG": "C.UTF-8"}
    added = subprocess.run(
        [exe, "setup", "cli", "add", "opencode"], env=env, capture_output=True, text=True, check=False
    )
    assert added.returncode == 0, added.stderr
    upgraded = subprocess.run(
        [exe, "setup", "cli", "upgrade", "opencode"], env=env, capture_output=True, text=True, check=False
    )
    assert upgraded.returncode == 0, upgraded.stderr
    with urllib.request.urlopen("https://api.github.com/repos/sst/opencode/releases/latest", timeout=30) as r:
        latest = json.load(r)["tag_name"].lstrip("v")
    version = subprocess.run(
        [str(home / ".opencode" / "bin" / "opencode"), "--version"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert latest in version.stdout, (latest, version.stdout)
    assert f"opencode {latest}" in upgraded.stdout
