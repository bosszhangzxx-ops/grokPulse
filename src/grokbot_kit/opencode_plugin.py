"""`grokbot-kit install opencode` / `uninstall opencode`: o plugin global do opencode (AC 95-97, AD-016, AD-028).

O asset depende do major do opencode (door 5 da needs-input-reply): o 2.x só carrega `export default { id, setup }`
e decide pelo `permission.hook("evaluate")`; o 1.x carrega o export nomeado e só avisa. A primeira linha de cada
asset diz para qual major ele é; o `run` e o `setup cli upgrade` reescrevem o plugin quando ela não casa mais.
"""

import json
import os
import shutil
import sys
from pathlib import Path

from grokbot_kit import launch

ASSETS_DIR = Path(__file__).parent / "assets" / "opencode"
ASSETS = {1: ASSETS_DIR / "grokbot-kit.ts", 2: ASSETS_DIR / "grokbot-kit.v2.ts"}
PLACEHOLDER = '"__GROKBOT_KIT_EXE__"'
MARKER = "// grokbot-kit opencode plugin for opencode "


def plugin_path() -> Path:
    return Path.home() / ".config" / "opencode" / "plugins" / "grokbot-kit.ts"


def asset_major(opencode_major: int | None) -> int:
    """O asset de um opencode com esse major: o v1 só para o 1.x; o v2 para o 2.x em diante e para o desconhecido."""
    return 1 if opencode_major == 1 else 2


def opencode_major() -> int | None:
    """O major do opencode do config (`[cli.opencode] bin`) ou do `PATH`; `None` sem opencode ou sem versão."""
    from grokbot_kit import config

    try:
        configured = config.load(validate=False).get("cli", {}).get("opencode", {}).get("bin")
    except config.ConfigError:
        configured = None
    bin_path = os.path.expanduser(str(configured)) if configured else shutil.which("opencode")
    return launch.cli_major(bin_path) if bin_path else None


def installed_major(path: Path | None = None) -> int | None:
    """Para qual major é o plugin instalado: o da primeira linha, `1` sem marcador (os de antes dele) e `None` sem
    arquivo legível."""
    try:
        with (path or plugin_path()).open(encoding="utf-8") as f:
            first = f.readline().rstrip("\n")
    except OSError:
        return None
    value = first.removeprefix(MARKER)
    return int(value) if first.startswith(MARKER) and value.isdigit() else 1


def write(major: int) -> Path:
    """Grava o asset do `major` com o executável de agora no lugar do marcador; `OSError` se não conseguir."""
    path = plugin_path()
    text = ASSETS[major].read_text(encoding="utf-8").replace(PLACEHOLDER, json.dumps(launch.kit_executable()))
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path


def sync(opencode: int | None) -> str | None:
    """Reescreve o plugin instalado quando ele não é o do major do opencode (AC 25 e 33 da needs-input-reply);
    devolve a linha que diz isso, ou `None` sem plugin ou com o asset certo. `OSError` se a reescrita falha."""
    found = installed_major()
    want = asset_major(opencode)
    if found is None or found == want:
        return None
    write(want)
    return f"opencode plugin rewritten for opencode {want}"


def _fail(action: str, message: str) -> int:
    print(f"grokbot-kit {action} opencode: {message}", file=sys.stderr)
    return 1


def install() -> int:
    try:
        path = write(asset_major(opencode_major()))
    except OSError as e:
        return _fail("install", f"cannot write {plugin_path()}: {e.strerror}")
    print(f"opencode plugin written to {path}")
    return 0


def uninstall() -> int:
    path = plugin_path()
    try:
        path.unlink(missing_ok=True)
    except OSError as e:
        return _fail("uninstall", f"cannot remove {path}: {e.strerror}")
    print(f"opencode plugin removed: {path}")
    return 0
