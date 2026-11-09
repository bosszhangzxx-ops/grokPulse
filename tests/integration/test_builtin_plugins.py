"""Provas dos plugins próprios com agentes reais (checks C49, C50, C53; AC 49-51, 54, 56, 57). Rodam só com
`-m integration`.

C49 só precisa do `claude`. C50 e C53 rodam no box, com o `gh` logado e repositórios de teste no GitHub:

- `GROKBOT_KIT_IT_REVIEW_PR`: URL de um PR aberto num repositório de teste em que o usuário do `gh` pode dar push na
  branch do PR. A prova posta reviews `COMMENT` nele e empurra um commit novo para a branch.
- `GROKBOT_KIT_IT_BUG_REPO`: URL de branch (`https://github.com/<owner>/<repo>/tree/<branch>`) de um repositório de
  teste com um `ZeroDivisionError` conhecido; `GROKBOT_KIT_IT_BUG_ALERT`, o alerta como o bot o recebe (mensagem e
  stack trace); `GROKBOT_KIT_IT_BUG_FILE`, o caminho do arquivo do bug no repositório.

O kit roda num `HOME` temporário (o de `test_real_cli.py`), com a matriz e o harness do pacote.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from grokbot_kit import plugin
from integration.test_real_cli import TERMINAL_EVENTS, prepare_home, real_bin

pytestmark = pytest.mark.integration


def builtin(name: str) -> Path:
    found = next((p for p in plugin.builtins() if p.name == name), None)
    assert found is not None, name
    return found.path


def env_or_fail(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.fail(f"defina {name} (veja o docstring de {Path(__file__).name})")
    return value


def run_builtin(tmp_path: Path, tool: str, name: str, *inputs: str) -> dict[str, Any]:
    """`run --plugin <name>` com o `gh` real do box; devolve o evento terminal."""
    home, _, _ = prepare_home(tmp_path, tool, "ok")
    gh_config = Path.home() / ".config" / "gh"
    if gh_config.exists():
        (home / ".config").mkdir(parents=True, exist_ok=True)
        (home / ".config" / "gh").symlink_to(gh_config)
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    args = [arg for value in inputs for arg in ("--input", value)]
    result = subprocess.run(
        [exe, "run", "--plugin", name, "--tool", tool, "--target", "it", "--label", name, *args],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home)},
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=3600,
    )
    sink = tmp_path / "sink.jsonl"
    lines = sink.read_text(encoding="utf-8").splitlines() if sink.exists() else []
    terminal = [e for e in map(json.loads, lines) if e["event"] in TERMINAL_EVENTS]
    assert len(terminal) == 1, (result.returncode, result.stderr)
    event: dict[str, Any] = terminal[0]
    return event


def gh_json(*args: str) -> Any:
    return json.loads(subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout)


# C49 - AC 54
@pytest.mark.parametrize("name", ["code-review", "bug-verify"])
def test_code_review_loads_in_claude(tmp_path: Path, name: str) -> None:
    claude = real_bin("claude")
    validated = subprocess.run(
        [claude, "plugin", "validate", str(builtin(name))], capture_output=True, text=True, check=False, cwd=tmp_path
    )
    assert validated.returncode == 0, validated.stdout + validated.stderr
    assert "Validation passed" in validated.stdout
    loaded = subprocess.run(
        [claude, "-p", "Reply with exactly: pong", "--model", "haiku", "--output-format", "json"]
        + ["--plugin-dir", str(builtin(name))],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        check=False,
        cwd=tmp_path,
        timeout=300,
    )
    assert loaded.returncode == 0, loaded.stderr
    assert json.loads(loaded.stdout)["is_error"] is False, loaded.stdout
    assert "plugin" not in loaded.stderr.lower(), loaded.stderr


# C50 - AC 49-51
def test_code_review_posts_comment_review(tmp_path: Path) -> None:
    pr = env_or_fail("GROKBOT_KIT_IT_REVIEW_PR")
    match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", pr)
    assert match, pr
    repo, number = match.groups()

    event = run_builtin(tmp_path / "um", "claude", "code-review", f"pr={pr}")
    assert (event["event"], event["status"]) == ("completed", "ok"), event
    review_url = event["result"]["review_url"]
    assert review_url and review_url.startswith(pr), event["result"]
    review_id = review_url.rsplit("pullrequestreview-", 1)[-1]
    review = gh_json("api", f"repos/{repo}/pulls/{number}/reviews/{review_id}")
    assert review["state"] == "COMMENTED", review

    # um commit novo na branch do PR, com um bug óbvio num arquivo que só ele toca
    head = gh_json("pr", "view", pr, "--json", "headRefName")["headRefName"]
    clone = tmp_path / "push"
    subprocess.run(["gh", "repo", "clone", repo, str(clone), "--", "--branch", head], check=True)
    novo = f"c50_{os.getpid()}.py"
    (clone / novo).write_text("def media(xs):\n    return sum(xs) / 0\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(clone), "add", novo], check=True)
    # identidade própria: o box não tem `user.name` nem `user.email` no git
    ident = ["-c", "user.name=grokbot-kit-it", "-c", "user.email=it@grokbot-kit.invalid"]
    subprocess.run(["git", "-C", str(clone), *ident, "commit", "-q", "-m", "test: commit novo do C50"], check=True)
    subprocess.run(["git", "-C", str(clone), "push", "-q", "origin", head], check=True)

    second = run_builtin(tmp_path / "dois", "claude", "code-review", f"pr={pr}")
    assert (second["event"], second["status"]) == ("completed", "ok"), second
    # AC 51: só achados novos ou ainda abertos; um achado novo fora do commit novo reprova
    first_files = {f["file"] for f in event["result"]["findings"]}
    second_files = {f["file"] for f in second["result"]["findings"]}
    assert novo in second_files, second["result"]
    assert second_files <= {novo} | first_files, (first_files, second["result"])


# C53 - AC 56, AC 57
def test_bug_verify_reproduces(tmp_path: Path) -> None:
    repo = env_or_fail("GROKBOT_KIT_IT_BUG_REPO")
    alert = env_or_fail("GROKBOT_KIT_IT_BUG_ALERT")
    bug_file = env_or_fail("GROKBOT_KIT_IT_BUG_FILE")
    tool = os.environ.get("GROKBOT_KIT_IT_BUG_TOOL", "claude")
    event = run_builtin(tmp_path, tool, "bug-verify", f"repo={repo}", f"alert={alert}")
    assert (event["event"], event["status"]) == ("completed", "ok"), event
    assert event["result"]["reproduced"] == "yes", event["result"]
    assert bug_file in [s["file"] for s in event["result"]["suspects"]], event["result"]
