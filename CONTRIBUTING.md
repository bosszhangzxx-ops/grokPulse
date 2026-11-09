# Contributing to grokbot-kit

> Leia em português: [docs/pt-BR/CONTRIBUTING.md](docs/pt-BR/CONTRIBUTING.md)

## Setup

Requires [`uv`](https://docs.astral.sh/uv/). `uv` installs the Python pinned in `.python-version` (`3.11`).

```sh
uv sync
uv run pre-commit install
```

`uv sync` creates `.venv/` with the development dependencies from `uv.lock`; `pre-commit install` installs the
`pre-commit`, `commit-msg` and `pre-push` hooks of `.pre-commit-config.yaml` (ruff, TOML/YAML checks, whitespace,
`mypy` and the flow rules of `tools/sdlc.py`, see [Flow gates](#flow-gates)).

## Lint, types and tests

```sh
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
```

These are the commands of the CI jobs `lint`, `typecheck` and `test (3.11)`, `test (3.12)`, `test (3.13)`. Tests
marked `integration` use the real CLIs or GitHub and run only on the box: `uv run pytest -m integration`.

## Pull request flow

- Everything branches from `main` and comes back through a pull request; `main` is protected and only takes squash
  merges.
- Every task starts from a GitHub issue. Branch names follow `<type>/<issue>/<slug>`, with the issue number
  (`feat/31/sdlc-gates`), and the pull request body links it with `Closes #<issue>` (or `Fixes #`, `Refs #`).
- Commits and the pull request title follow [Conventional Commits](https://www.conventionalcommits.org/), at most 100
  characters in the first line, without `Co-Authored-By`.
- A pull request only goes in with the 6 CI checks green; its title becomes the squash commit message.
- A behaviour change gets an entry under `## [Unreleased]` in `CHANGELOG.md`.
- A visible behaviour change (command, flag, config, event, plugin) updates `README.md` and the doc of the topic in the
  same PR, in English and in the translation under `docs/pt-BR/`; `tests/test_docs.py` fails when a subcommand is
  missing from the READMEs or a doc has no pair.
- Never paste tokens, keys or secret URLs into a commit, issue or pull request.

## Flow gates

The flow rules fail early, by machine, through `tools/sdlc.py` (Python standard library only):

- `commit-msg` hook: the first line follows Conventional Commits and no line is `Co-authored-by:`; the first line git
  writes for a `git merge` or `git pull` (`Merge branch '...'`) is exempt from Conventional Commits, not from the
  co-author rule.
- `pre-commit` hook: no commit on `main`, and no code commit in the main clone (only `docs/`, `.specs/`, `.claude/`,
  `.agents/` and `AGENTS.md` there); `GROKBOT_KIT_ALLOW_MAIN_EDIT=1` lifts the second rule.
- `pre-push` hook: the branch matches `<type>/<issue>/<slug>`, `chore/release/<version>` or `dependabot/`.
- CI job `process`, a required check: `tools/sdlc.py pr` checks the pull request title, branch, commits and
  `Closes #<issue>`, runs the `tlc-spec-lean` validators of every feature the PR touches, refuses `src/` or `skills/`
  changes without a `verification.md`, a `plan.md` without its `**Approved**: YYYY-MM-DD` line and a `## Handoff` of
  `docs/.specs/STATE.md` over 40 lines, and checks the docs: a paired doc changed without its pair, and a `feat` or
  `fix` that changes `src/` or `skills/` without an entry in `## [Unreleased]` or without docs (or a
  `Docs: n/a - <reason>` line in the body).

Run any rule by hand: `python3 tools/sdlc.py --help`.

## Agent instructions and Claude Code

The instructions for coding agents (flow, autonomy, skills, environment, docs rule) are in `AGENTS.md`, the only
instructions file of the project. Claude Code reads it from version 2.1.277 on, as long as there is no `CLAUDE.md` or
`CLAUDE.local.md` at the root: a local `CLAUDE.local.md` turns that reading off. The session start hook
`.claude/hooks/session-start.sh` warns about it and installs the git hooks when they are missing.

Whoever works on this repository with Claude Code does each code task in a dedicated worktree under `../worktrees/`.
The hook `.claude/hooks/gate-worktree.sh` (PreToolUse on Edit/Write) denies code edits in the main clone. To work in
the main clone on purpose, run the session with `GROKBOT_KIT_ALLOW_MAIN_EDIT=1`. The permission rules
of `.claude/settings.json` let the agent push a branch and open a pull request, and ask before a merge, a tag push,
a release or a change to branch protection, in any part of a compound command. A push to `main` is refused by
the `pre-push` hook and by the branch protection of `main` on GitHub.

## Release and PyPI

The `release.yml` workflow publishes to PyPI through trusted publishing when a `v<semver>` tag equal to the version
in `pyproject.toml` is pushed; no token is stored in the repository. Before the first tag, one human step: at
<https://pypi.org/manage/account/publishing/>, add a GitHub pending publisher with

- PyPI Project Name: `grokbot-kit`
- Owner: `rodrigo-pasini`
- Repository name: `grokbot-kit`
- Workflow name: `release.yml`
- Environment name: `pypi`

The pending publisher does not reserve the name until the first upload. No `v*` tag is created before it exists.

## Test policy

> Copied from `docs/.specs/features/agent-run-notify/checks.md` and approved as a guideline of the repository.

The repository has no testing guide: nothing says which level proves which code, nor how much of the input space a
proof has to assert. These rows are the default of this build.

| Code | Required proofs | Coverage expectation |
| --- | --- | --- |
| Decides, reached through a boundary (CLI or HTTP) | one at the boundary (a `grokbot-kit` subprocess or a local HTTP receiver) **and** one at its own layer | the contract at the boundary; one asserted case per row of the decision table at its own layer |
| Decides, with no boundary | one at its own layer | one asserted case per row of the decision table |
| Entry point that does not decide | one at the boundary | accepted input, each refused input, each error path |
| Instrumentation, pass-through | none of its own | covered by the proof of whoever consumes it |
| Integration with a real CLI or GitHub | `-m integration` on the box (or a `gh` command) | the hook or the setting really fires, once per CLI |

Evidence (there was no code yet; decision tables counted in the plan):

- terminal status derivation (AC 43-45): 8 rows (ok, 2 of denied, 5 of error) and 1 precedence rule → decides, reached
  through the CLI
- HTTP response classification (AC 68-72, 123): 7 classes per sink → decides, reached through HTTP
- tool/model/tier/timeout resolution (AC 78-83): 6 decision points → decides
- hook normalisation in `emit` (AC 54-58): 4 sources and 1 dedupe rule → decides, reached through the CLI
- `gc` predicate (AC 101): 4 cases → decides
- argv assembly per tool (AC 40-42): 3 rows → decides (a mapping with more than one row)
- analogue in the repository: none yet (new project); the closest in shape is
  `.claude/skills/revisar-pr/scripts/conferir-achados.py` with `test-conferir-achados.py`, proved at its own layer

Cost: about 45 proofs at their own layer in 12 test files, plus 9 `-m integration` proofs on the box. Without these
rows, 6 decision tables would be proved only by the path an end-to-end test goes through.
