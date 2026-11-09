"""Fumaça do executável instalado pelo pacote."""

import shutil
import subprocess
import sys

from grokbot_kit import __version__


def test_cli_version() -> None:
    exe = shutil.which("grokbot-kit")
    assert exe is not None, "console script grokbot-kit não instalado"
    result = subprocess.run([exe, "--version"], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == f"grokbot-kit {__version__}"


def test_emit_without_task_id_exits_0() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "grokbot_kit.emit"], capture_output=True, text=True, env={}, check=False
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_emit_through_cli_skips_heavy_imports_without_task_id() -> None:
    # door 6: os hooks chamam `grokbot-kit emit`, que passa pelo cli.py antes de chegar ao emit
    code = "import sys; from grokbot_kit.cli import main; sys.exit(main(['emit', '--from', 'claude']))"
    result = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", code], capture_output=True, text=True, env={}, check=False
    )
    assert result.returncode == 0
    assert result.stdout == ""
    imported = {line.rsplit("|", 1)[-1].strip() for line in result.stderr.splitlines() if "|" in line}
    assert "grokbot_kit.emit" in imported
    for heavy in ("argparse", "importlib.metadata", "urllib.request", "tomllib", "grokbot_kit.config"):
        assert heavy not in imported


# C19 - AC 21: os comandos que a skill cita estão no `--help`
def test_setup_providers_in_help() -> None:
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    setup_help = subprocess.run([exe, "setup", "--help"], capture_output=True, text=True, check=True).stdout
    assert "providers" in setup_help
    refresh_help = subprocess.run(
        [exe, "setup", "models", "refresh", "--help"], capture_output=True, text=True, check=True
    ).stdout
    assert "--json" in refresh_help
    providers_help = subprocess.run(
        [exe, "setup", "providers", "--help"], capture_output=True, text=True, check=True
    ).stdout
    assert "provider" in providers_help
