#!/usr/bin/env python3
"""Instalador oficial falso (door 19): põe a CLI falsa de `tests/fakes/` onde o instalador real poria o binário.

`claude` em `~/.local/bin/claude`; `opencode` em `~/.opencode/bin/opencode`; `codex` em
`${CODEX_HOME:-~/.codex}/packages/standalone/current/bin/codex`, com o link `${CODEX_INSTALL_DIR:-~/.local/bin}/codex`,
como o `install.sh` do Codex. `FAKE_INSTALL_FAIL=1` faz o instalador sair com `1` sem instalar nada.
`FAKE_INSTALLED_VERSION` grava em `~/.fake-version-<tool>` a versão que a CLI instalada passa a responder. `FAKE_CALLS`
acumula uma linha JSON por chamada (`tool` = `installer:<tool>`, argv, `CODEX_HOME`, `CODEX_INSTALL_DIR` e `PATH`).
"""

import json
import os
import sys
from pathlib import Path

FAKE_AGENT = Path(__file__).resolve().parent.parent / "fake_agent.py"

tool, args = sys.argv[1], sys.argv[2:]
calls = os.environ.get("FAKE_CALLS")
if calls:
    with open(calls, "a", encoding="utf-8") as f:
        call = {
            "tool": f"installer:{tool}",
            "argv": args,
            "codex_home": os.environ.get("CODEX_HOME"),
            "codex_install_dir": os.environ.get("CODEX_INSTALL_DIR"),
            "path": os.environ.get("PATH", ""),
        }
        f.write(json.dumps(call) + "\n")
if os.environ.get("FAKE_INSTALL_FAIL") == "1":
    print(f"fake {tool} installer: download failed", file=sys.stderr)
    sys.exit(1)

home = Path.home()


def link(path: Path, target: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    path.symlink_to(target)


if tool == "claude":
    link(home / ".local" / "bin" / "claude", FAKE_AGENT)
elif tool == "opencode":
    link(home / ".opencode" / "bin" / "opencode", FAKE_AGENT)
else:
    codex_home = Path(os.environ.get("CODEX_HOME") or home / ".codex")
    binary = codex_home / "packages" / "standalone" / "current" / "bin" / "codex"
    link(binary, FAKE_AGENT)
    link(Path(os.environ.get("CODEX_INSTALL_DIR") or home / ".local" / "bin") / "codex", binary)
if "FAKE_INSTALLED_VERSION" in os.environ:
    (home / f".fake-version-{tool}").write_text(os.environ["FAKE_INSTALLED_VERSION"], encoding="utf-8")
print(f"fake {tool} installed")
