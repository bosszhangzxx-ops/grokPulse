#!/usr/bin/env python3
"""Regras do fluxo de desenvolvimento do grokbot-kit, conferidas por máquina (feature sdlc-gates, door 1).

Chamado pelos hooks git (`.pre-commit-config.yaml`) e pelo job `process` do CI. Exit `0` ok, `1` violação (o motivo
em stderr), `2` uso. Só stdlib; lê o repositório do diretório atual.
"""

import argparse
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

COMMIT_TYPES = "feat|fix|refactor|perf|test|docs|chore|build|ci|style|revert"
DOOR_3 = rf"^({COMMIT_TYPES})(\([a-z0-9._-]+\))?!?: \S.*$"
MAX_FIRST_LINE = 100
DOOR_2 = (
    r"^(feat|fix|refactor|perf|test|docs|chore|build|ci)/[0-9]+/[a-z0-9][a-z0-9-]*$",
    r"^chore/release/[0-9]+\.[0-9]+\.[0-9]+$",
    r"^dependabot/",
)
COAUTHOR = re.compile(r"^\s*co-authored-by:", re.IGNORECASE)
# Primeira linha que o próprio git escreve num `git merge` ou `git pull` (o hook `commit-msg` roda nos dois).
GIT_MERGE = re.compile(r"^Merge (branch|branches|remote-tracking branch|tag|commit) '")
MAIN_CLONE_ALLOWED = ("docs/", ".specs/", ".claude/", ".agents/")
MAIN_CLONE_FILES = ("CLAUDE.md", "AGENTS.md")
APPROVED = re.compile(r"^\*\*Approved\*\*: (\d{4}-\d{2}-\d{2})$")
DOCS_NA = re.compile(r"^Docs: n/a - \S", re.MULTILINE)
FEATURES = "docs/.specs/features/"
STATE = "docs/.specs/STATE.md"
HANDOFF_MAX = 40
VALIDATORS = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "tlc-spec-lean" / "scripts"
SPEC_FILES = (
    ("plan.md", "validate_plan.py"),
    ("checks.md", "validate_checks.py"),
    ("verification.md", "validate_verification.py"),
)


def fail(lines: list[str]) -> int:
    for line in lines:
        print(line, file=sys.stderr)
    return 1 if lines else 0


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def git_ok(*args: str) -> str | None:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


# ---------------------------------------------------------------------------- mensagens e branches


def first_line_problems(line: str, what: str) -> list[str]:
    if re.match(DOOR_3, line) and len(line) <= MAX_FIRST_LINE:
        return []
    return [f"{what} {line!r} does not match {DOOR_3} (at most {MAX_FIRST_LINE} characters)"]


def coauthor_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if COAUTHOR.match(line)]


def branch_problems(name: str) -> list[str]:
    if any(re.match(pattern, name) for pattern in DOOR_2):
        return []
    return [f"branch {name!r} matches none of:", *(f"  {pattern}" for pattern in DOOR_2)]


def cmd_commit_msg(path: str) -> int:
    text = Path(path).read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    first = next((line for line in lines if line.strip()), "")
    problems = [] if GIT_MERGE.match(first) else first_line_problems(first, "commit message")
    problems += [f"commit message has a co-author line: {line}" for line in coauthor_lines("\n".join(lines))]
    return fail(problems)


def cmd_branch(name: str) -> int:
    return fail(branch_problems(name))


# ---------------------------------------------------------------------------- pre-commit


def cmd_pre_commit() -> int:
    if git_ok("symbolic-ref", "--short", "HEAD") == "main":
        return fail(["commit on main: create a <type>/<issue>/<slug> branch"])
    if os.environ.get("GROKBOT_KIT_ALLOW_MAIN_EDIT") == "1":
        return 0
    git_dir = Path(git("rev-parse", "--absolute-git-dir").strip())
    common = Path(git("rev-parse", "--git-common-dir").strip())
    if not common.is_absolute():
        common = Path.cwd() / common
    if git_dir.resolve() != common.resolve():
        return 0
    staged = git("diff", "--cached", "--name-only").splitlines()
    outside = [f for f in staged if not f.startswith(MAIN_CLONE_ALLOWED) and f not in MAIN_CLONE_FILES]
    if not outside:
        return 0
    return fail(
        [
            "commit in the main clone with code staged (work in a worktree, or GROKBOT_KIT_ALLOW_MAIN_EDIT=1):",
            *(f"  {f}" for f in outside),
        ]
    )


# ---------------------------------------------------------------------------- spec e state


def section(text: str, heading: str) -> str | None:
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def plan_doc_problems(plan: Path) -> list[str]:
    text = plan.read_text(encoding="utf-8")
    criteria = section(text, "## Criteria") or ""
    if "README.md" in criteria or re.search(r"docs/(?!\.specs)", criteria) or DOCS_NA.search(text):
        return []
    return [f"{plan}: no criterion cites README.md or docs/, and no 'Docs: n/a - <reason>' line"]


def spec_problems(feature: str) -> list[str]:
    folder = Path(FEATURES) / feature
    problems = []
    for name, script in SPEC_FILES:
        if not (folder / name).is_file():
            continue
        cmd = [sys.executable, str(VALIDATORS / script), feature, "--root", "docs"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            output = (result.stdout + result.stderr).strip()
            problems.append(f"{feature}: {script} exited {result.returncode}")
            problems += [f"  {line}" for line in output.splitlines()]
    if (folder / "plan.md").is_file():
        problems += plan_doc_problems(folder / "plan.md")
    return problems


def cmd_spec(feature: str) -> int:
    if not (Path(FEATURES) / feature).is_dir():
        print(f"no feature at {FEATURES}{feature}", file=sys.stderr)
        return 2
    return fail(spec_problems(feature))


def state_problems() -> list[str]:
    path = Path(STATE)
    if not path.is_file():
        return []
    handoff = section(path.read_text(encoding="utf-8"), "## Handoff")
    if handoff is None:
        return []
    count = len(handoff.splitlines())
    if count <= HANDOFF_MAX:
        return []
    return [f"{STATE}: ## Handoff has {count} lines (at most {HANDOFF_MAX}); keep only the current state"]


def cmd_state() -> int:
    return fail(state_problems())


# ---------------------------------------------------------------------------- pr


def changelog_unreleased(text: str) -> str:
    return section(text, "## [Unreleased]") or ""


def paired(path: str) -> str | None:
    """O par de um doc pareado (`README.md`, `CONTRIBUTING.md`, `docs/<x>.md` e os de `docs/pt-BR/`)."""
    if path in ("README.md", "CONTRIBUTING.md"):
        return f"docs/pt-BR/{path}"
    match = re.fullmatch(r"docs/pt-BR/([^/]+\.md)", path)
    if match:
        name = match.group(1)
        return name if name in ("README.md", "CONTRIBUTING.md") else f"docs/{name}"
    if re.fullmatch(r"docs/[^/]+\.md", path):
        return f"docs/pt-BR/{path.removeprefix('docs/')}"
    return None


def plan_approved(path: Path) -> bool:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines()]
    if not lines or not lines[0].startswith("# "):
        return False
    rest = [line for line in lines[1:] if line.strip()]
    match = APPROVED.match(rest[0]) if rest else None
    if not match:
        return False
    try:
        datetime.date.fromisoformat(match.group(1))
    except ValueError:
        return False
    return True


def pr_problems(title: str, branch: str, body: str, base: str) -> list[str]:
    # o `base.sha` do evento é a ponta da `main`; o PR começa no merge-base com ela
    base = git_ok("merge-base", base, "HEAD") or base
    problems = first_line_problems(title, "PR title")
    problems += branch_problems(branch)
    log = git("log", "--no-merges", "--format=%H%x00%B%x1e", f"{base}..HEAD")
    for entry in filter(str.strip, log.split("\x1e")):
        sha, message = entry.strip().split("\x00", 1)
        problems += [f"commit {sha} has a co-author line: {line}" for line in coauthor_lines(message)]
    problems += [f"PR body has a co-author line: {line}" for line in coauthor_lines(body)]

    issue = re.match(r"^[a-z]+/([0-9]+)/", branch)
    if issue and not re.search(rf"\b(Closes|Fixes|Refs) #{issue.group(1)}(?!\d)", body, re.IGNORECASE):
        problems.append(f"PR body links no issue: add 'Closes #{issue.group(1)}' (or Fixes/Refs)")

    changed = git("diff", "--name-only", base, "HEAD").splitlines()
    present = [p for p in changed if Path(p).is_file()]
    features = sorted({m.group(1) for p in changed if (m := re.match(rf"{FEATURES}([^/]+)/", p))})
    for feature in features:
        if (Path(FEATURES) / feature).is_dir():
            problems += spec_problems(feature)

    code = [p for p in changed if p.startswith(("src/", "skills/"))]
    verified = any(re.fullmatch(rf"{FEATURES}[^/]+/verification\.md", p) for p in present)
    if code and not verified:
        problems.append("src/ or skills/ changed without a verification.md")

    for path in present:
        if re.fullmatch(rf"{FEATURES}[^/]+/plan\.md", path) and not plan_approved(Path(path)):
            problems.append(f"{path}: no '**Approved**: YYYY-MM-DD' line right below the title")

    problems += state_problems()

    reported = set()
    for path in changed:
        pair = paired(path)
        if pair and pair not in changed and (path, pair) not in reported:
            reported.add((path, pair))
            problems.append(f"{path} changed without its pair {pair}: update both in the same PR")

    kind = re.match(r"^([a-z]+)", title)
    if kind and kind.group(1) in ("feat", "fix") and code:
        before = git_ok("show", f"{base}:CHANGELOG.md") or ""
        after = Path("CHANGELOG.md").read_text(encoding="utf-8") if Path("CHANGELOG.md").is_file() else ""
        if changelog_unreleased(before) == changelog_unreleased(after):
            problems.append(
                "CHANGELOG.md: a feat/fix PR that changes src/ or skills/ needs an entry in ## [Unreleased]"
            )
        docs = [p for p in changed if p == "README.md" or re.fullmatch(r"docs/([^/]+|pt-BR/[^/]+)\.md", p)]
        if not docs and not DOCS_NA.search(body):
            problems.append(
                "a feat/fix PR that changes src/ or skills/ changes no README.md or docs/*.md;"
                " update the docs or add 'Docs: n/a - <reason>' to the PR body"
            )
    return problems


def cmd_pr(title: str, branch: str, body_file: str, base: str) -> int:
    body = Path(body_file).read_text(encoding="utf-8")
    return fail(pr_problems(title, branch, body, base))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/sdlc.py", description="Development flow rules of grokbot-kit.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("commit-msg", help="check a commit message file").add_argument("file")
    sub.add_parser("branch", help="check a branch name").add_argument("name")
    sub.add_parser("pre-commit", help="refuse commits on main and code commits in the main clone")
    pr = sub.add_parser("pr", help="check a pull request (the CI job process)")
    pr.add_argument("--title", required=True)
    pr.add_argument("--branch", required=True)
    pr.add_argument("--body-file", required=True)
    pr.add_argument("--base", required=True, help="SHA of the PR base")
    sub.add_parser("spec", help="run the tlc-spec-lean validators of a feature").add_argument("feature")
    sub.add_parser("state", help="check the size of the ## Handoff of docs/.specs/STATE.md")
    args = parser.parse_args(argv)
    if args.command == "pr":
        args.body_file = os.path.abspath(args.body_file)
    if args.command in ("pr", "spec", "state"):
        top = git_ok("rev-parse", "--show-toplevel")
        if top:
            os.chdir(top)

    if args.command == "commit-msg":
        return cmd_commit_msg(args.file)
    if args.command == "branch":
        return cmd_branch(args.name)
    if args.command == "pre-commit":
        return cmd_pre_commit()
    if args.command == "pr":
        return cmd_pr(args.title, args.branch, args.body_file, args.base)
    if args.command == "spec":
        return cmd_spec(args.feature)
    return cmd_state()


if __name__ == "__main__":
    sys.exit(main())
