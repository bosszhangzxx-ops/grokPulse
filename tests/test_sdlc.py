"""Provas do `tools/sdlc.py` (sdlc-gates: checks C1, C3-C11, C14-C23, C52-C55; AC 1-8, 11-18, 39-42).

O script roda como subprocesso, como no hook git e no job `process`, contra um repositório git montado em `tmp_path`.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SDLC = ROOT / "tools" / "sdlc.py"
FIXTURES = ROOT / ".claude" / "skills" / "tlc-spec-lean" / "scripts" / "fixtures"

COMMIT_TYPES = ["feat", "fix", "refactor", "perf", "test", "docs", "chore", "build", "ci", "style", "revert"]
DOOR_3 = r"^(feat|fix|refactor|perf|test|docs|chore|build|ci|style|revert)(\([a-z0-9._-]+\))?!?: \S.*$"
DOOR_2 = [
    r"^(feat|fix|refactor|perf|test|docs|chore|build|ci)/[0-9]+/[a-z0-9][a-z0-9-]*$",
    r"^chore/release/[0-9]+\.[0-9]+\.[0-9]+$",
    r"^dependabot/",
]
MAIN_MSG = "commit on main: create a <type>/<issue>/<slug> branch"
NO_VERIFICATION = "src/ or skills/ changed without a verification.md"


def sdlc(
    *args: str, cwd: Path, env: dict[str, str] | None = None, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    full_env = {k: v for k, v in os.environ.items() if k != "GROKBOT_KIT_ALLOW_MAIN_EDIT"}
    full_env.update(env or {})
    return subprocess.run(
        [sys.executable, str(SDLC), *args],
        cwd=cwd,
        env=full_env,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "Teste")
    git(path, "config", "user.email", "teste@example.com")
    git(path, "config", "commit.gpgsign", "false")
    (path / "README.md").write_text("# repo\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "chore: init")
    return path


def write(repo: Path, rel: str, text: str) -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def commit(repo: Path, files: dict[str, str], message: str = "feat(x): muda coisa") -> str:
    for rel, text in files.items():
        write(repo, rel, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


# ---------------------------------------------------------------------------- commit-msg


def commit_msg(tmp_path: Path, message: str) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(message, encoding="utf-8")
    return sdlc("commit-msg", str(path), cwd=tmp_path)


def accepted_messages() -> list[str]:
    messages = []
    for kind in COMMIT_TYPES:
        messages += [f"{kind}: descreve", f"{kind}(run): descreve", f"{kind}(run.x_y-z)!: descreve", f"{kind}!: x"]
    first = "feat(run): " + "x" * 89
    assert len(first) == 100
    return messages + [first + "\n\ncorpo do commit\n"]


# C3 - AC 4, door 3
@pytest.mark.parametrize("message", accepted_messages())
def test_commit_msg_accepts(tmp_path: Path, message: str) -> None:
    result = commit_msg(tmp_path, message)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "" and result.stderr == ""


# C4 - AC 2, door 3
@pytest.mark.parametrize(
    "message", ["ajusta coisa", "Feat: x", "feat(Run): x", "feat:x", "feat: ", "feat(run): " + "x" * 90]
)
def test_commit_msg_rejects(tmp_path: Path, message: str) -> None:
    result = commit_msg(tmp_path, message + "\n")
    assert result.returncode == 1
    assert DOOR_3 in result.stderr


# C5 - AC 3
@pytest.mark.parametrize("line", ["Co-Authored-By: X <x@y>", "co-authored-by: X", "CO-AUTHORED-BY: X"])
def test_commit_msg_coauthor(tmp_path: Path, line: str) -> None:
    result = commit_msg(tmp_path, f"feat(run): descreve\n\ncorpo\n\n{line}\n")
    assert result.returncode == 1
    assert line in result.stderr


# C59 - AC 46, door 3
@pytest.mark.parametrize(
    "message",
    [
        "Merge branch 'main' into feat/31/x",
        "Merge branch 'main' of github.com:o/r into feat/31/x",
        "Merge branches 'a' and 'b'",
        "Merge remote-tracking branch 'origin/main' into feat/31/x",
        "Merge tag 'v0.6.0'",
        "Merge commit 'abc123'",
    ],
)
def test_commit_msg_merge_accepts(tmp_path: Path, message: str) -> None:
    result = commit_msg(
        tmp_path, message + "\n\n# Please enter a commit message to explain why this merge is necessary\n"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "" and result.stderr == ""


def test_commit_msg_merge_rejects(tmp_path: Path) -> None:
    loose = commit_msg(tmp_path, "Merge stuff\n")
    assert loose.returncode == 1
    assert DOOR_3 in loose.stderr
    coauthor = commit_msg(tmp_path, "Merge branch 'main' into feat/31/x\n\nCo-authored-by: X <x@y>\n")
    assert coauthor.returncode == 1
    assert "Co-authored-by: X <x@y>" in coauthor.stderr


# ---------------------------------------------------------------------------- branch


# C6 - AC 5, door 2
@pytest.mark.parametrize(
    ("name", "ok"),
    [
        ("feat/31/sdlc-gates", True),
        ("chore/release/0.6.0", True),
        ("dependabot/uv/ruff-0.17.3", True),
        ("feat/sdlc-gates", False),
        ("feat/S3/x", False),
        ("feature/31/x", False),
        ("feat/31/Sdlc", False),
        ("chore/release/0.6", False),
        ("main", False),
    ],
)
def test_branch_pattern(tmp_path: Path, name: str, ok: bool) -> None:
    result = sdlc("branch", name, cwd=tmp_path)
    if ok:
        assert result.returncode == 0, result.stderr
        assert result.stderr == ""
    else:
        assert result.returncode == 1
        for pattern in DOOR_2:
            assert pattern in result.stderr


# ---------------------------------------------------------------------------- hooks instalados


def clone_with_hooks(tmp_path: Path) -> Path:
    """Um clone de teste com o `.pre-commit-config.yaml` e o `tools/sdlc.py` do repositório, hooks instalados."""
    repo = tmp_path / "clone"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Teste")
    git(repo, "config", "user.email", "teste@example.com")
    shutil.copyfile(ROOT / ".pre-commit-config.yaml", repo / ".pre-commit-config.yaml")
    (repo / "tools").mkdir()
    shutil.copyfile(SDLC, repo / "tools" / "sdlc.py")
    result = subprocess.run(
        ["uv", "run", "--project", str(ROOT), "pre-commit", "install"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return repo


# C1 - AC 1
def test_precommit_installs_three_hook_types(tmp_path: Path) -> None:
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    assert config["default_install_hook_types"] == ["pre-commit", "commit-msg", "pre-push"]
    repo = clone_with_hooks(tmp_path)
    for hook in ("pre-commit", "commit-msg", "pre-push"):
        assert (repo / ".git" / "hooks" / hook).is_file(), hook


# C28 - AC 21, door 6
def test_pre_push_refuses_main(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    repo = clone_with_hooks(tmp_path)
    git(repo, "remote", "add", "origin", str(remote))
    env = {**os.environ, "GROKBOT_KIT_ALLOW_MAIN_EDIT": "1"}
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    subprocess.run(["git", "commit", "-q", "--no-verify", "-m", "feat(x): a"], cwd=repo, check=True, env=env)
    for refspec in ("main", "HEAD:main"):
        result = subprocess.run(
            ["git", "push", "-q", "origin", refspec], cwd=repo, capture_output=True, text=True, check=False, env=env
        )
        assert result.returncode != 0, refspec
    heads = subprocess.run(
        ["git", "ls-remote", "--heads", str(remote)], capture_output=True, text=True, check=True
    ).stdout
    assert "refs/heads/main" not in heads
    assert sdlc("branch", "main", cwd=tmp_path).returncode == 1


# C7 - AC 5
def test_pre_push_hook_blocks(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    repo = clone_with_hooks(tmp_path)
    git(repo, "remote", "add", "origin", str(remote))
    env = {**os.environ, "GROKBOT_KIT_ALLOW_MAIN_EDIT": "1"}
    git(repo, "checkout", "-q", "-b", "feat/sdlc")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    subprocess.run(["git", "commit", "-q", "--no-verify", "-m", "feat(x): a"], cwd=repo, check=True, env=env)

    def push(branch: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "push", "-q", "origin", branch], cwd=repo, capture_output=True, text=True, check=False, env=env
        )

    def remote_has(branch: str) -> bool:
        out = subprocess.run(
            ["git", "--git-dir", str(remote), "branch", "--list", branch], capture_output=True, text=True, check=True
        )
        return out.stdout.strip() != ""

    refused = push("feat/sdlc")
    assert refused.returncode != 0
    assert not remote_has("feat/sdlc")
    git(repo, "branch", "-q", "feat/31/sdlc")
    accepted = push("feat/31/sdlc")
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert remote_has("feat/31/sdlc")


# ---------------------------------------------------------------------------- pre-commit


# C8 - AC 6
def test_pre_commit_on_main(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "r")
    write(repo, "docs/a.md", "a\n")
    git(repo, "add", "-A")
    result = sdlc("pre-commit", cwd=repo)
    assert result.returncode == 1
    assert MAIN_MSG in result.stderr


def stage(repo: Path, *rels: str) -> None:
    for rel in rels:
        write(repo, rel, "x\n")
    git(repo, "add", "-A")


# C9 - AC 7
def test_pre_commit_main_clone(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "r")
    git(repo, "checkout", "-q", "-b", "feat/31/x")
    stage(repo, "src/x.py", "tests/t.py")
    blocked = sdlc("pre-commit", cwd=repo)
    assert blocked.returncode == 1
    assert "src/x.py" in blocked.stderr and "tests/t.py" in blocked.stderr

    git(repo, "reset", "-q")
    for rel in ("src/x.py", "tests/t.py"):
        (repo / rel).unlink()
    stage(repo, "docs/a.md", ".claude/b", ".agents/c", ".specs/d", "CLAUDE.md", "AGENTS.md")
    allowed = sdlc("pre-commit", cwd=repo)
    assert allowed.returncode == 0, allowed.stderr

    git(repo, "commit", "-q", "--no-verify", "-m", "docs: x")
    worktree = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "feat/31/y", str(worktree))
    stage(worktree, "src/x.py")
    linked = sdlc("pre-commit", cwd=worktree)
    assert linked.returncode == 0, linked.stderr


# C10 - AC 8
def test_pre_commit_allow_main_edit(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "r")
    git(repo, "checkout", "-q", "-b", "feat/31/x")
    stage(repo, "src/x.py")
    escape = {"GROKBOT_KIT_ALLOW_MAIN_EDIT": "1"}
    assert sdlc("pre-commit", cwd=repo, env=escape).returncode == 0
    git(repo, "checkout", "-q", "main")
    on_main = sdlc("pre-commit", cwd=repo, env=escape)
    assert on_main.returncode == 1
    assert MAIN_MSG in on_main.stderr


# C11 - door 1
@pytest.mark.parametrize("args", [[], ["nao-existe"]])
def test_usage_exit_2(tmp_path: Path, args: list[str]) -> None:
    result = sdlc(*args, cwd=tmp_path)
    assert result.returncode == 2
    assert "usage:" in result.stderr


# ---------------------------------------------------------------------------- spec


def approved_plan(extra: str = "\nDocs: n/a - fixture\n") -> str:
    lines = (FIXTURES / "plan.md").read_text(encoding="utf-8").splitlines(keepends=True)
    return lines[0] + "\n**Approved**: 2026-10-29\n" + "".join(lines[1:]) + extra


def feature_files(name: str, plan: str | None = None) -> dict[str, str]:
    base = f"docs/.specs/features/{name}"
    return {
        f"{base}/plan.md": plan if plan is not None else approved_plan(),
        f"{base}/checks.md": (FIXTURES / "checks.md").read_text(encoding="utf-8"),
        f"{base}/verification.md": (FIXTURES / "verification.md").read_text(encoding="utf-8"),
    }


def without_profile(text: str) -> str:
    return "".join(line for line in text.splitlines(keepends=True) if not line.startswith("Profile:"))


# C18 - AC 15
def test_spec_runs_validators(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "r")
    for rel, text in feature_files("demo").items():
        write(repo, rel, text)
    ok = sdlc("spec", "demo", cwd=repo)
    assert ok.returncode == 0, ok.stderr

    checks = repo / "docs/.specs/features/demo/checks.md"
    checks.write_text(without_profile(checks.read_text(encoding="utf-8")), encoding="utf-8")
    bad = sdlc("spec", "demo", cwd=repo)
    assert bad.returncode == 1
    assert "validate_checks.py" in bad.stderr

    # só os presentes: sem checks.md nem verification.md, só o validate_plan roda
    only_plan = init_repo(tmp_path / "p")
    write(only_plan, "docs/.specs/features/demo/plan.md", approved_plan())
    alone = sdlc("spec", "demo", cwd=only_plan)
    assert alone.returncode == 0, alone.stderr

    # o verification.md também é validado (rodada 1 do Verifier: F1 sobreviveu)
    for rel, text in feature_files("demo").items():
        write(repo, rel, text)
    verification = repo / "docs/.specs/features/demo/verification.md"
    failed = verification.read_text(encoding="utf-8").replace("**Verdict**: PASS", "**Verdict**: FAIL", 1)
    verification.write_text(failed, encoding="utf-8")
    bad_verification = sdlc("spec", "demo", cwd=repo)
    assert bad_verification.returncode == 1
    assert "validate_verification.py" in bad_verification.stderr
    assert "validate_checks.py" not in bad_verification.stderr


# C19 - AC 15
def test_spec_reports_every_failure(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "r")
    files = feature_files("demo", plan="# demo\n\n**Approved**: 2026-10-29\n\nDocs: n/a - fixture\n")
    files["docs/.specs/features/demo/checks.md"] = without_profile(files["docs/.specs/features/demo/checks.md"])
    for rel, text in files.items():
        write(repo, rel, text)
    result = sdlc("spec", "demo", cwd=repo)
    assert result.returncode == 1
    assert "validate_plan.py" in result.stderr
    assert "validate_checks.py" in result.stderr


# C55 - AC 42, door 9
def test_spec_plan_doc_criterion(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "r")
    plan = repo / "docs/.specs/features/demo/plan.md"
    write(repo, "docs/.specs/features/demo/plan.md", approved_plan(extra=""))
    missing = sdlc("spec", "demo", cwd=repo)
    assert missing.returncode == 1, "plano sem critério de doc nem Docs: n/a passou"

    plan.write_text(approved_plan(extra="\nDocs: n/a - só mexe no faturamento interno\n"), encoding="utf-8")
    assert sdlc("spec", "demo", cwd=repo).returncode == 0

    text = approved_plan(extra="")
    marker = "**Acceptance Criteria**\n"
    with_doc = text.replace(marker, marker + "\n0. The `README.md` SHALL document the dunning flow\n", 1)
    plan.write_text(with_doc, encoding="utf-8")
    assert sdlc("spec", "demo", cwd=repo).returncode == 0

    this = sdlc("spec", "sdlc-gates", cwd=ROOT)
    assert this.returncode == 0, this.stderr


# ---------------------------------------------------------------------------- state


def handoff(lines: int) -> str:
    body = [f"- linha {i}" for i in range(lines - 1)]
    return "# State\n\n## Decisions\n\nnada\n\n## Handoff\n" + "\n".join(body) + "\n"


# C23 - AC 18
def test_state_handoff_limit(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "r")
    write(repo, "docs/.specs/STATE.md", handoff(40))
    assert sdlc("state", cwd=repo).returncode == 0
    write(repo, "docs/.specs/STATE.md", handoff(40) + "\n## Depois\n\n" + "x\n" * 30)
    assert sdlc("state", cwd=repo).returncode == 0
    write(repo, "docs/.specs/STATE.md", handoff(41))
    assert sdlc("state", cwd=repo).returncode == 1

    pr = PR(tmp_path / "pr")
    pr.change({"docs/.specs/STATE.md": handoff(41)})
    assert pr.run().returncode == 1


# ---------------------------------------------------------------------------- pr


class PR:
    """Um PR de teste: a base em `main`, a branch com as mudanças, e o corpo num arquivo."""

    def __init__(self, path: Path, branch: str = "feat/31/x") -> None:
        self.repo = init_repo(path)
        commit(
            self.repo,
            {"CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n\n- a\n"},
            "chore: base",
        )
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.branch = branch
        git(self.repo, "checkout", "-q", "-b", "work")
        self.title = "feat(ci): job process"
        self.body = "## What\n\nCloses #31\n"

    def change(self, files: dict[str, str], message: str = "feat(ci): muda coisa") -> str:
        return commit(self.repo, files, message)

    def run(self) -> subprocess.CompletedProcess[str]:
        body = self.repo.parent / f"{self.repo.name}-body.md"
        body.write_text(self.body, encoding="utf-8")
        args = ["--title", self.title, "--branch", self.branch, "--body-file", str(body), "--base", self.base]
        return sdlc("pr", *args, cwd=self.repo)


def neutral_pr(tmp_path: Path, **kwargs: str) -> PR:
    pr = PR(tmp_path / "pr", **kwargs)
    pr.change({"pyproject.toml": "[project]\nname = 'x'\n"}, "build: muda pyproject")
    return pr


def code_pr(tmp_path: Path) -> PR:
    """Um PR `feat` em dia que muda `src/`: verificação, CHANGELOG e doc."""
    pr = PR(tmp_path / "pr")
    files = {
        "src/a.py": "x = 1\n",
        "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n- a nova\n\n## [0.1.0] - 2026-01-01\n\n- a\n",
        "README.md": "# repo\n\nmais\n",
        "docs/pt-BR/README.md": "# repo\n\nmais\n",
        **feature_files("demo"),
    }
    pr.change(files)
    return pr


# C14 - AC 11
def test_pr_title(tmp_path: Path) -> None:
    pr = neutral_pr(tmp_path)
    ok = pr.run()
    assert ok.returncode == 0, ok.stderr
    pr.title = "ajusta coisa"
    bad = pr.run()
    assert bad.returncode == 1
    assert "ajusta coisa" in bad.stderr


# C59 - AC 46: o título do PR segue a door 3 sem a exceção do merge
def test_pr_title_merge(tmp_path: Path) -> None:
    pr = neutral_pr(tmp_path)
    pr.title = "Merge branch 'main'"
    result = pr.run()
    assert result.returncode == 1
    assert "Merge branch 'main'" in result.stderr


# C15 - AC 12
def test_pr_branch(tmp_path: Path) -> None:
    pr = neutral_pr(tmp_path, branch="feat/sdlc")
    pr.body = "## What\n\nsem issue\n"
    result = pr.run()
    assert result.returncode == 1
    assert "feat/sdlc" in result.stderr


# C16 - AC 13
def test_pr_coauthor(tmp_path: Path) -> None:
    pr = neutral_pr(tmp_path)
    sha = pr.change({"b.txt": "b\n"}, "build: outra\n\nCo-authored-by: X <x@y>")
    in_commit = pr.run()
    assert in_commit.returncode == 1
    assert sha in in_commit.stderr

    clean = neutral_pr(tmp_path / "2")
    clean.body = "Closes #31\n\nco-authored-by: X <x@y>\n"
    in_body = clean.run()
    assert in_body.returncode == 1
    assert "body" in in_body.stderr.lower()


# C17 - AC 14, door 7
@pytest.mark.parametrize(
    ("branch", "body", "ok"),
    [
        ("feat/31/x", "Closes #31", True),
        ("feat/31/x", "Fixes #31", True),
        ("feat/31/x", "Refs #31", True),
        ("feat/31/x", "sem link", False),
        ("feat/31/x", "Closes #32", False),
        ("feat/31/x", "Closes #310", False),
        ("dependabot/uv/x", "Bumps x", True),
        ("chore/release/0.6.0", "release", True),
    ],
)
def test_pr_issue_link(tmp_path: Path, branch: str, body: str, ok: bool) -> None:
    pr = neutral_pr(tmp_path, branch=branch)
    pr.title = "build: muda pyproject"
    pr.body = f"## What\n\n{body}\n"
    result = pr.run()
    assert (result.returncode == 0) is ok, result.stderr
    if not ok:
        assert result.returncode == 1


# C20 - AC 15
def test_pr_specs_of_touched_features(tmp_path: Path) -> None:
    pr = PR(tmp_path / "pr")
    broken = feature_files("velha")
    broken["docs/.specs/features/velha/checks.md"] = without_profile(broken["docs/.specs/features/velha/checks.md"])
    commit(pr.repo, broken, "docs: feature velha quebrada")
    pr.base = git(pr.repo, "rev-parse", "HEAD")
    pr.change(feature_files("nova"), "docs(specs): feature nova")
    untouched = pr.run()
    assert untouched.returncode == 0, untouched.stderr

    bad = feature_files("nova")
    bad["docs/.specs/features/nova/checks.md"] = without_profile(bad["docs/.specs/features/nova/checks.md"])
    pr.change(bad, "docs(specs): quebra a nova")
    touched = pr.run()
    assert touched.returncode == 1
    assert "nova" in touched.stderr and "validate_checks.py" in touched.stderr


# C21 - AC 16
@pytest.mark.parametrize("path", ["src/a.py", "skills/b.md"])
def test_pr_requires_verification(tmp_path: Path, path: str) -> None:
    pr = PR(tmp_path / "pr")
    pr.title = "refactor: muda codigo"
    pr.change({path: "x\n"})
    missing = pr.run()
    assert missing.returncode == 1
    assert NO_VERIFICATION in missing.stderr

    pr.change(feature_files("demo"), "docs(specs): verifica")
    verified = pr.run()
    assert verified.returncode == 0, verified.stderr


def test_pr_requires_verification_not_for_release(tmp_path: Path) -> None:
    pr = PR(tmp_path / "pr", branch="chore/release/0.6.0")
    pr.title = "chore(release): 0.6.0"
    pr.body = "release\n"
    pr.change(
        {
            "pyproject.toml": "[project]\nversion = '0.6.0'\n",
            "uv.lock": "lock\n",
            "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n## [0.6.0] - 2026-11-01\n",
        }
    )
    result = pr.run()
    assert result.returncode == 0, result.stderr


def test_pr_base_ahead_of_branch(tmp_path: Path) -> None:
    """O `--base` do CI é a ponta da `main`, que pode ter andado depois da branch: o PR é o que veio do merge-base."""
    pr = PR(tmp_path / "pr")
    pr.title = "build: muda pyproject"
    pr.change({"pyproject.toml": "[project]\nname = 'x'\n"}, "build: muda pyproject")
    git(pr.repo, "checkout", "-q", "main")
    pr.base = commit(pr.repo, {"src/outro.py": "y = 2\n"}, "feat(x): outro PR, já em main")
    git(pr.repo, "checkout", "-q", "work")
    result = pr.run()
    assert result.returncode == 0, result.stderr


# C22 - AC 17, door 5
def test_pr_plan_approved(tmp_path: Path) -> None:
    pr = PR(tmp_path / "pr")
    pr.title = "docs(specs): plano"
    unapproved = approved_plan().replace("\n**Approved**: 2026-10-29\n", "", 1)
    commit(pr.repo, {"docs/.specs/features/velha/plan.md": unapproved}, "docs: plano velho sem marcador")
    pr.base = git(pr.repo, "rev-parse", "HEAD")
    pr.change({"docs/.specs/features/nova/plan.md": approved_plan()}, "docs(specs): plano novo")
    ok = pr.run()
    assert ok.returncode == 0, ok.stderr

    pr.change({"docs/.specs/features/nova/plan.md": unapproved}, "docs(specs): tira o marcador")
    assert pr.run().returncode == 1

    tomorrow = approved_plan().replace("**Approved**: 2026-10-29", "**Approved**: amanhã", 1)
    pr.change({"docs/.specs/features/nova/plan.md": tomorrow}, "docs(specs): data errada")
    assert pr.run().returncode == 1

    # door 5: a linha vale só logo abaixo do título (rodada 1 do Verifier: F3 sobreviveu)
    lines = unapproved.splitlines(keepends=True)
    below = "".join(lines[:3]) + "\n**Approved**: 2026-10-29\n\n" + "".join(lines[3:])
    assert not below.split("\n", 3)[2].startswith("**Approved**")
    pr.change({"docs/.specs/features/nova/plan.md": below}, "docs(specs): marcador fora do lugar")
    assert pr.run().returncode == 1

    edited = pr.change({"docs/.specs/features/velha/plan.md": unapproved + "\nmais\n"}, "docs(specs): mexe no velho")
    assert edited
    pr.change({"docs/.specs/features/nova/plan.md": approved_plan()}, "docs(specs): volta o novo")
    assert pr.run().returncode == 1, "plan.md alterado sem marcador passou"


# C52 - AC 39
@pytest.mark.parametrize(
    ("changed", "ok"),
    [
        (["README.md"], False),
        (["docs/pt-BR/README.md"], False),
        (["README.md", "docs/pt-BR/README.md"], True),
        (["CONTRIBUTING.md"], False),
        (["docs/pt-BR/CONTRIBUTING.md"], False),
        (["CONTRIBUTING.md", "docs/pt-BR/CONTRIBUTING.md"], True),
    ],
)
def test_pr_doc_pair(tmp_path: Path, changed: list[str], ok: bool) -> None:
    pr = PR(tmp_path / "pr")
    pr.title = "docs: muda o doc"
    pr.change({rel: "# mudou\n" for rel in changed}, "docs: muda o doc")
    result = pr.run()
    assert (result.returncode == 0) is ok, result.stderr
    if not ok:
        assert result.returncode == 1
        name = Path(changed[0]).name
        assert f"{name} changed" in result.stderr or f"pair {name}" in result.stderr
        for rel in (name, f"docs/pt-BR/{name}"):
            assert rel in result.stderr, rel


def test_pr_doc_pair_other_docs(tmp_path: Path) -> None:
    pr = PR(tmp_path / "pr")
    pr.title = "docs: muda plugins"
    pr.change({"docs/plugins.md": "# p\n"}, "docs: muda plugins")
    result = pr.run()
    assert result.returncode == 1
    assert "docs/plugins.md" in result.stderr and "docs/pt-BR/plugins.md" in result.stderr


# C53 - AC 40
@pytest.mark.parametrize("kind", ["feat", "fix"])
def test_pr_changelog_unreleased(tmp_path: Path, kind: str) -> None:
    pr = code_pr(tmp_path)
    pr.title = f"{kind}(run): muda"
    assert pr.run().returncode == 0
    pr.change(
        {"CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n\n- a\n- b antiga\n"},
        "docs: mexe só na seção velha",
    )
    result = pr.run()
    assert result.returncode == 1
    assert "CHANGELOG.md" in result.stderr


@pytest.mark.parametrize("kind", ["refactor", "chore"])
def test_pr_changelog_unreleased_not_for_other_types(tmp_path: Path, kind: str) -> None:
    pr = PR(tmp_path / "pr")
    pr.title = f"{kind}(run): muda"
    pr.change({"src/a.py": "x = 1\n", **feature_files("demo")})
    result = pr.run()
    assert result.returncode == 0, result.stderr


# C54 - AC 41, door 9
@pytest.mark.parametrize("kind", ["feat", "fix"])
def test_pr_docs_or_na(tmp_path: Path, kind: str) -> None:
    pr = PR(tmp_path / "pr")
    pr.title = f"{kind}(run): muda"
    pr.change(
        {
            "src/a.py": "x = 1\n",
            "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n- a nova\n\n## [0.1.0] - 2026-01-01\n\n- a\n",
            **feature_files("demo"),
        }
    )
    without = pr.run()
    assert without.returncode == 1
    pr.body = "Closes #31\n\nDocs: n/a - só refatora o parser\n"
    with_na = pr.run()
    assert with_na.returncode == 0, with_na.stderr
    pr.body = "Closes #31\n\nDocs: n/a - \n"
    assert pr.run().returncode == 1
