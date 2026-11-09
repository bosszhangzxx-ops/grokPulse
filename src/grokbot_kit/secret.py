"""`grokbot-kit secret set <name>` (AC 76, door 3): o segredo vem do TTY sem eco, ou do stdin, e nunca é impresso."""

import getpass
import os
import re
import sys

from grokbot_kit import config

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _fail(message: str) -> int:
    print(f"grokbot-kit secret: {message}", file=sys.stderr)
    return 1


def set_secret(name: str) -> int:
    if not NAME_RE.match(name):
        return _fail("name must use only letters, digits, '.', '_' and '-', and not start with '.'")
    if sys.stdin.isatty():
        value = getpass.getpass(f"secret {name}: ")
    else:
        value = sys.stdin.read()
    value = value.rstrip("\r\n")
    if not value:
        return _fail("empty secret, nothing written")
    directory = config.secrets_dir()
    tmp = directory / f".{name}.{os.getpid()}.tmp"
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(value + "\n")
        os.replace(tmp, directory / name)
    except OSError as e:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return _fail(f"cannot write {directory / name}: {e.strerror}")
    print(f"secret {name} written to {directory / name} (mode 0600)")
    return 0
