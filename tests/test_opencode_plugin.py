"""Provas do `install opencode` e `uninstall opencode` (checks C116, C117; AC 95, 96)."""

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest
from conftest import Kit


def plugins(kit: Kit) -> Path:
    return kit.home / ".config" / "opencode" / "plugins"


def kit_exe() -> str:
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    return exe


def tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir"
        for p in sorted(root.rglob("*"))
    }


# C116 - AC 95
@pytest.mark.parametrize("previous", [None, "// plugin antigo apontando para /opt/velho/grokbot-kit\n"])
def test_install_idempotent_abs_path(fresh: Kit, previous: str | None) -> None:
    if previous is not None:
        plugins(fresh).mkdir(parents=True)
        (plugins(fresh) / "grokbot-kit.ts").write_text(previous, encoding="utf-8")
    for _ in range(2):
        result = fresh.cli("install", "opencode")
        assert result.returncode == 0, result.stderr
        assert [p.name for p in plugins(fresh).iterdir()] == ["grokbot-kit.ts"]
    text = (plugins(fresh) / "grokbot-kit.ts").read_text(encoding="utf-8")
    assert '"__GROKBOT_KIT_EXE__"' not in text
    assert "/opt/velho" not in text
    declared = [line for line in text.splitlines() if line.startswith("const GROKBOT_KIT = ")]
    assert len(declared) == 1
    path = declared[0].removeprefix("const GROKBOT_KIT = ").strip().strip('"')
    assert os.path.isabs(path)
    assert Path(path).samefile(kit_exe())
    assert "process.env.GROKBOT_KIT_TASK_ID" in text


def test_install_idempotent_abs_path_unwritable(fresh: Kit) -> None:
    plugins(fresh).mkdir(parents=True)
    os.chmod(plugins(fresh), 0o500)
    try:
        result = fresh.cli("install", "opencode")
    finally:
        os.chmod(plugins(fresh), 0o700)
    assert result.returncode == 1
    assert list(plugins(fresh).iterdir()) == []


# C117 - AC 96
def test_uninstall_removes_only_plugin(fresh: Kit) -> None:
    config_dir = fresh.home / ".config" / "opencode"
    plugins(fresh).mkdir(parents=True)
    (config_dir / "opencode.json").write_text('{"permission": {"bash": "ask"}}', encoding="utf-8")
    (plugins(fresh) / "outro.ts").write_text("export const Outro = async () => ({})\n", encoding="utf-8")
    (config_dir / "agent").mkdir()
    (config_dir / "agent" / "revisor.md").write_text("# revisor\n", encoding="utf-8")
    others = tree(config_dir)

    assert fresh.cli("install", "opencode").returncode == 0
    result = fresh.cli("uninstall", "opencode")
    assert result.returncode == 0, result.stderr
    assert not (plugins(fresh) / "grokbot-kit.ts").exists()
    assert tree(config_dir) == others

    again = fresh.cli("uninstall", "opencode")
    assert again.returncode == 0, again.stderr
    assert tree(config_dir) == others


def with_opencode(kit: Kit, version: str) -> None:
    """Um `opencode` falso no `PATH` do `fresh`, que responde `version` ao `--version`."""
    from conftest import FAKES

    bin_dir = kit.home.parent / "oc-bin"
    bin_dir.mkdir(exist_ok=True)
    link = bin_dir / "opencode"
    if not link.exists():
        link.symlink_to(FAKES / "opencode")
    kit.env = {**kit.env, "PATH": f"{bin_dir}{os.pathsep}{kit.env['PATH']}", "FAKE_VERSION": version}


# C27 - AC 19 da needs-input-reply, door 5
@pytest.mark.parametrize("version", ["opencode v2.2.4", None], ids=["v2", "sem-opencode"])
def test_install_picks_v2(fresh: Kit, version: str | None) -> None:
    if version is not None:
        with_opencode(fresh, version)
    result = fresh.cli("install", "opencode")
    assert result.returncode == 0, result.stderr
    text = (plugins(fresh) / "grokbot-kit.ts").read_text(encoding="utf-8")
    assert text.splitlines()[0] == "// grokbot-kit opencode plugin for opencode 2"
    assert "export default {" in text
    assert 'id: "grokbot-kit"' in text
    assert '"__GROKBOT_KIT_EXE__"' not in text
    declared = [line for line in text.splitlines() if line.startswith("const GROKBOT_KIT = ")]
    assert Path(json.loads(declared[0].removeprefix("const GROKBOT_KIT = "))).samefile(kit_exe())


# C28 - AC 20 da needs-input-reply
def test_install_picks_v1(fresh: Kit) -> None:
    with_opencode(fresh, "opencode v1.19.3")
    result = fresh.cli("install", "opencode")
    assert result.returncode == 0, result.stderr
    text = (plugins(fresh) / "grokbot-kit.ts").read_text(encoding="utf-8")
    asset = Path(__file__).resolve().parents[1] / "src" / "grokbot_kit" / "assets" / "opencode" / "grokbot-kit.ts"
    expected = asset.read_text(encoding="utf-8").replace('"__GROKBOT_KIT_EXE__"', json.dumps(kit_exe()))
    assert text.splitlines()[0] == "// grokbot-kit opencode plugin for opencode 1"
    assert text == expected
    assert "export const GrokbotKit" in text
