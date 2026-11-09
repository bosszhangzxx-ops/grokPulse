# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). While the version is `0.x`, the event schema
`grokbot-kit.event/v1` may change incompatibly, always with a `Changed` or `Removed` entry here.

## [Unreleased]

### Added

- Fork snapshot of [rodrigo-pasini/grokbot-kit](https://github.com/rodrigo-pasini/grokbot-kit) @ `51174f6` (0.7.0) with
  Claude Code Hooks listening for Grok Bot: 9 progress hooks plus `PermissionRequest`.
- The Claude Code hooks now record session timing and token usage: `SessionStart` writes `started_at`, `SessionEnd`
  writes `ended_at` and `duration_seconds`, and both plus the log lines carry real token counters aggregated from the
  session transcript `message.usage` (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`,
  `cache_read_input_tokens`, `total_tokens`, `api_requests`, `thinking_tokens` from `output_tokens_details`). The new
  `session-metrics.json` in the task dir keeps the
  per-session record and, when both `TaskCreated` and `TaskCompleted` snapshots exist, the per-`claude_task_id` window
  delta. With no readable transcript the counters are omitted (`tokens.source = "unavailable"`), never invented.

## [0.7.0] - 2026-11-06

### Added

- `grokbot-kit reply <task_id> <request_id> allow|deny [--message <text>] [--by bot|user]` answers a permission
  request of a running task. With Claude Code and opencode 2.x the agent now waits for the reply, so an `allow` lets it
  use the tool in the same task; with no reply before the deadline the kit denies the request, as before.
- `run --ask-wait <duration>` and `[ask] wait` in the config set how long a request waits (default `10m`; `0` only
  notifies, the old behaviour).
- The `needs_input` object of the event `grokbot-kit.event/v1` has two new fields: `request_id` and `reply_deadline`.
- `grokbot-kit setup cli upgrade <tool>` reruns the official installer to bring a CLI to its latest version, and
  rewrites the opencode plugin for the new opencode version.
- The Grok Bot skill answers low-risk requests by itself (`reply ... --by bot`: reading files, running tests, linters
  or the build, editing inside the task's directory, read-only `git`) and asks the user about everything else.
- `grokbot-kit doctor` reports an opencode plugin made for another opencode version, and warns while opencode is 1.x.

### Changed

- `completed` with `status` `denied` now means a permission request ended without `allow`; a task whose requests were
  all allowed ends `ok`.

### Fixed

- The opencode plugin loads in opencode 2.x again (opencode 2 only loads a default export, so `needs_input` from
  opencode 2.x tasks never arrived). `install opencode` picks the plugin for the installed opencode version, and every
  opencode task rewrites a plugin made for another version before it starts.
- Every opencode 2.x task runs with `--standalone`, not only plugin tasks: the shared opencode service does not see
  the task's environment, so the plugin stayed inert there.

## [0.6.0] - 2026-10-30

### Added

- `docs/event.md` (and `docs/pt-BR/event.md`) describes each of the 26 fields of the event `grokbot-kit.event/v1` and
  the `event`/`status`/`exit_reason` combinations; the README now names every option of every command, including
  `--version`, `run --tool`, `run --timeout`, `run --prompt-file`, `route add --header`, `login --secret` and
  `setup models refresh --add`.

### Changed

- Contributing: `AGENTS.md` is the only instruction file for coding agents (`CLAUDE.md` is gone; Claude Code reads
  `AGENTS.md` from 2.1.277 on), and the development flow is checked by `tools/sdlc.py` in local hooks and in the new
  required CI check `process` (branch and commit names, issue link, specs, changelog and doc pairs). See
  `CONTRIBUTING.md`.

## [0.5.0] - 2026-10-29

### Added

- `grokbot-kit setup models refresh --json` prints `{"models": [{"tool", "id", "provider"}]}`, where `provider` is the
  text before the first `/` of an opencode id and `null` for `claude` and `codex`. Without `--json` the output does not
  change.
- `grokbot-kit setup providers opencode <provider>...` records the opencode providers you use in
  `[cli.opencode] providers`. With the list recorded, `setup tiers opencode` refuses an id from another provider and
  `grokbot-kit doctor` reports a tier that has one; `doctor --json` shows the list in `cli.opencode.providers`.
- Model fallback within a tier: when the model of a `--tier` task fails at the provider before the agent uses any tool
  (opencode: an `error` with no `tool_use`; `claude`: `api_error` in the first turn), the kit launches the next id of
  the tier in the same task, within the same timeout. The earlier attempts stay in the task dir as `out.<n>.jsonl` and
  `stderr.<n>.log`. Codex and `--model` tasks never fall back.
- Event `grokbot-kit.event/v1`: new field `model_fallbacks`, a list of `{"model", "error"}` for each attempt that
  failed and led to another (`[]` without fallback, `null` in the `test` event). `model` is now the last id launched.

### Changed

- The Grok Bot skill asks which opencode providers you use and the ids of each tier, instead of putting the free
  models first on its own; free models come first in `trivial` and `standard` only when the only provider chosen is
  `opencode`.
- When a task fails without a final message from the agent, the event `summary` carries the error message of the CLI
  (opencode: `<name or type>: <message>` of the last `error`; codex: the message of the last `turn.failed` or
  `error`), cut at 2000 characters. It used to be empty.
- `README.md` lists every command, the plugins and the model setup; `CONTRIBUTING.md` is now in English, with the
  Portuguese version in `docs/pt-BR/CONTRIBUTING.md`.

## [0.4.1] - 2026-10-27

### Security

- Plugin tasks with `commands`: an allowed command could write outside the task directory, so `write = "task-dir"`
  did not hold for it. In `opencode`, a command that starts with an allowed prefix could redirect its output with
  `>`; in both `opencode` and `claude`, `git log`, `git diff` and `git show` write a file with `--output`. The harness
  now denies any shell command with `>` in `opencode` and any shell command whose text has `--output` in both CLIs.
  Both rules match the literal text; another spelling, such as quotes, gets around them.
- Plugin tasks with a `repo` input: the `opencode` write tool followed a symbolic link committed in the clone and
  wrote outside the task directory. A clone with a symbolic link that points outside it now ends the task with
  `error` before the agent runs, in every CLI.
- Plugin tasks without a `repo` input: the agent ran in the directory of the caller (or `--cwd`), and the `opencode`
  write tool could write there. The agent of a plugin task now always runs in `<task_dir>/work`, empty when there is
  no `repo` input, and `--cwd` is ignored for such plugins.
- The `tool` cell of `write` now says what it enforces: the agent's file tools and the shell (redirection, chaining,
  pipes, command substitution). An allowed command still writes wherever its other options and the code it runs
  allow, like a test runner does; [docs/plugins.md](docs/plugins.md) says so.

### Fixed

- Plugin tasks: the kit appends a `## Ambiente desta tarefa` block to the plugin prompt, built from the declared
  capabilities (allowed command prefixes, one command per call, read files with the CLI tools, where to write, no
  network, a denied permission does not end the task). Without it, an agent that had one compound shell command
  denied concluded it had no shell, so `code-review` did not post the review and `bug-verify` did not run the test.

## [0.4.0] - 2026-10-22

### Added

- Plugins: ready-made tasks with their own prompt, inputs and declared capabilities (`write`, `network`,
  `commands`). `grokbot-kit plugin list [--json]`, `plugin show <name-or-origin> [--json]`,
  `plugin add <dir-or-git-url> [--ref <ref>] [--replace] [--yes]` and `plugin rm <name>`; installed plugins are
  pinned copies in `~/.grokbot-kit/plugins/`. The plugin format `grokbot-kit.plugin/v0` may change before 1.0; see
  [docs/plugins.md](docs/plugins.md).
- `grokbot-kit run --plugin <name> --input <key>=<value>` clones the PR or branch of a `repo` input into the task
  dir, runs the plugin prompt there and refuses (`2`, before the task dir) a CLI that cannot enforce a capability
  the plugin declares. `claude` and `opencode` enforce `write`, `commands`, the ignored workspace configuration and the
  plugin skills with their own permissions; no CLI enforces `network = "off"`, and `codex` runs no plugin (its sandbox
  needs `bwrap`, which does not start where unprivileged user namespaces are restricted).
- Builtin plugins `code-review` (one `COMMENT` review with inline comments on a GitHub PR) and `bug-verify` (checks
  an error alert against the code).
- `grokbot-kit doctor` lists the plugins (`plugins`) and the capability support of each CLI (`plugin_support`), and
  reports an unreadable installed plugin as a problem. A `gh` that is not logged in shows as `gh.logged_in` `false`
  and a `gh:` line, without changing `problems` or the exit code.
- The skill lists the plugins before delegating, runs a matching plugin instead of writing a prompt, and installs a
  plugin only after showing its capabilities and asking.

### Changed

- `grokbot-kit.event/v1` gains `plugin` and `result` (`null` outside plugin tasks) and the `exit_reason`
  `result_invalid`. A plugin task never ends as `denied`: it ends `ok` only with a valid `result.json`. Its permission
  requests go to `kit.log`, not to the routine as `needs_input`.

### Fixed

- The agent gets `PWD` set to its working directory. It inherited the `PWD` of the process that ran `grokbot-kit run`,
  and opencode, which finds its project from `PWD`, worked on that directory's project instead of `--cwd`.

## [0.3.1] - 2026-10-21

### Fixed

- `grokbot-kit update apply` no longer reports `<old> -> <old>` with exit `0` when the installer leaves the version
  unchanged, which `uv tool upgrade` does for a `grokbot-kit` installed with a pinned version (`grokbot-kit==X.Y.Z`)
  or from a wheel file: it exits `1` saying the install may be pinned, with the tail of the installer's stderr, and
  keeps the opencode plugin and the `skip`/`later` state as they were.

## [0.3.0] - 2026-10-21

### Added

- `grokbot-kit update check [--json]` tells whether PyPI has a newer `grokbot-kit` (cached 24 h in
  `~/.grokbot-kit/update.json`, 1 h after a failed check; a failed check still exits `0`); `update apply` upgrades
  with the tool that installed the kit (`uv tool upgrade` or `pipx upgrade`, from the receipt in the tool
  environment) and rewrites the opencode plugin with the new executable, refusing while a task runs;
  `update skip <version>` and `update later` stop the question for that version or for 24 h.
- `grokbot-kit doctor` reports the same check in `kit.update` (and an `update:` line in text); `problems`, `ok` and
  the exit code do not change.
- The `skills/grokbot-kit/` skill runs `grokbot-kit update check --json` before the Setup and before delegating a
  task, asks once with three options (update now, not now, skip the version) and, after `update apply`, downloads
  the skill of the latest release again. A skill from `0.2.x` does not know this: download
  `https://github.com/rodrigo-pasini/grokbot-kit/releases/latest/download/SKILL.md` once.

## [0.2.2] - 2026-10-21

### Added

- `grokbot-kit doctor` reports the opencode plugin in `cli.opencode.plugin` (`path`, the `exe` it calls, `ok`) and
  lists as a problem, with `grokbot-kit install opencode`, a missing plugin or one that calls another `grokbot-kit`
  executable; before, opencode tasks then ended without `needs_input` events and nothing said why.

## [0.2.1] - 2026-10-21

### Added

- Each GitHub Release carries `SKILL.md` (the `skills/grokbot-kit/` skill of that tag), so
  `https://github.com/rodrigo-pasini/grokbot-kit/releases/latest/download/SKILL.md` always gives the skill of the
  latest release; the README quick start prompt downloads it from there.

### Changed

- The `skills/grokbot-kit/` skill stores secrets with `grokbot-kit secret set` reading the value from standard
  input: the bot reads the routine URL and key with its own tools or asks for each value in a masked secret field;
  a terminal on the box is only the fallback when there is no masked field. The README quick start prompt says the
  same and shows screenshots of a setup and a task.

## [0.2.0] - 2026-10-21

### Added

- `grokbot-kit run`: launches `claude`, `opencode` or `codex` headless with stdin on `/dev/null`, keeps the task in
  `~/.grokbot-kit/tasks/<task_id>/` and sends exactly one terminal event (`completed`/`ok`, `completed`/`denied` or
  `error`/`failed`) to the target's route; exits with the agent's exit code.
- Terminal events carry `repo` (`root`, `branch`, `head` when `cwd` is inside a git repository with a commit),
  `session_id` and `resume_hint` (the command that resumes the agent session), and the `transcript_path` reported by
  the agent hook.
- Config keys `[cli.<tool>] models` (discovered model ids) and arguments after `--` passed verbatim to the agent CLI.
- `grokbot-kit emit --from claude|codex|opencode`: called by the agent hooks inside a task, sends one `needs_input`
  event (`status` `permission` or `question`) per distinct request, recorded in the task dir so the terminal event
  becomes `completed`/`denied`; always exits `0`, prints at most `{}`, and does nothing outside a task.
- The opencode plugin forwards `permission.asked` (root sessions only) and `question.asked` to `grokbot-kit emit`.
  Known limits: `opencode run` denies the question tool, so `question` events do not occur in tasks; `codex exec` never
  asks for approval, so Codex tasks send no `needs_input` and a denied command ends `completed`/`ok`.
- Sinks `grokbot-routine` (POST to the routine webhook with `Authorization: Bearer <key>`, receipt `runUuid` recorded
  in the task dir), `file`, `ntfy` and `slack`. Retries after 1 s and 4 s on `429`, `5xx` and connection failures;
  what is not delivered goes to `undelivered.jsonl` and stderr names `grokbot-kit redeliver <task_id>`.
- `grokbot-kit run` exits `2` before launching when the target has no route or a route secret is missing or not `0600`.
- `grokbot-kit redeliver <task_id>`, `grokbot-kit route add|rm|test <target>` and `grokbot-kit secret set <name>`
  (read from the terminal without echo, or from stdin, and stored in `~/.secrets/grokbot-kit/` with mode `0600`).
- The config is checked when loaded: `setup.default_cli` must be in `setup.installed`, and every id in
  `cli.<tool>.tiers` must be in `cli.<tool>.models`; otherwise commands exit `2` naming the key.
- `grokbot-kit run --timeout <duration>` (`30s`, `30m`, `2h`, `1d`): without it the timeout is `timeouts.<tier>` from
  the config (defaults `trivial = "30m"`, `standard = "2h"`, `complex = "4h"`), recorded in `meta.json` as
  `timeout_seconds`; `--tier` defaults to `standard`, also when `--model` is given.
- `grokbot-kit setup models refresh [<tool>] [--add <id>]...`: records in `[cli.<tool>] models` the ids printed by
  `opencode models`; for Claude the aliases `haiku`, `sonnet` and `opus` plus each added or stored id that a test
  `claude -p --model <id>` accepts; for Codex each added or stored id that a test `codex exec -m <id>` accepts. Exits
  `1` when the CLI list fails or an id is rejected; tiers are never changed.
- `grokbot-kit run` enforces the timeout: the agent runs in its own process group, which gets `SIGINT`, then `SIGTERM`
  10 s later and `SIGKILL` 10 s after that; the event is `timeout`/`timeout` and the run exits `124`. `SIGINT` or
  `SIGTERM` sent to the run is forwarded to that group (followed by the same `SIGTERM`/`SIGKILL` steps if the agent
  keeps running), the event is `error`/`interrupted` and the run exits `130`. A missing agent binary gives
  `error`/`failed` with `exit_reason` `agent_error` and exit `127`. In these three events `exit_code` is the run's own
  exit code.
- `grokbot-kit setup cli add <tool>` installs `claude`, `opencode` or `codex` with the official installer
  (`claude.ai/install.sh`, `opencode.ai/install` with `--no-modify-path`, `chatgpt.com/codex/install.sh` with
  `CODEX_HOME` set to the kit's Codex home and the binary in `~/.grokbot-kit/bin`), checks `<cli> --version` and
  records `cli.<tool>.bin`; `grokbot-kit setup default <tool>` sets `setup.default_cli`.
- `grokbot-kit login <tool> [--method subscription|api-key] [--secret <name>]`: `codex login --device-auth` or
  `codex login --with-api-key` (key from the secret on stdin) in the kit's `CODEX_HOME`, `claude auth login` or an API
  key secret recorded as `[cli.claude] api_key_secret` and passed as `ANTHROPIC_API_KEY` only to the `claude`
  processes the kit starts, and `opencode auth login`.
- `grokbot-kit doctor [--json]`: kit and Python versions and, per installed CLI, version, login state, whether it is
  the default and how many models each tier has, plus routes and secret modes; exits `1` and lists what to fix (with
  the command) when something needs attention. opencode without credentials (free models) is not a problem.
- `grokbot-kit install opencode` writes `~/.config/opencode/plugins/grokbot-kit.ts` with the absolute path of the
  `grokbot-kit` executable (rerunning replaces it); `grokbot-kit uninstall opencode` removes only that file. Outside a
  task the plugin does nothing.
- `grokbot-kit setup tiers <tool> <tier> <id>...` sets the ordered model ids of `cli.<tool>.tiers.<tier>`; exits `2`
  without changing the config when the tool is not installed or an id is not in `cli.<tool>.models`.
- The `skills/grokbot-kit/` skill for any Grok Bot: installs the kit, the chosen CLIs and their login, sets the
  default CLI and the model tiers, guides the routine with a webhook trigger (secrets only through
  `grokbot-kit secret set` in a terminal) and its route, delegates tasks with `grokbot-kit run` choosing the tier by a
  rubric, and handles the events, including `redeliver` when one did not arrive.
- `grokbot-kit gc --older-than <duration> [--dry-run]` removes (or only lists) the task dirs whose task finished more
  than `<duration>` ago (`30d`, `12h`, ...), never a task still running nor one with a non-empty `undelivered.jsonl`;
  an invalid duration exits `2`.

## [0.1.0] - 2026-10-19

### Added

- Repository scaffold: MIT license, Python package `grokbot-kit` built with `uv_build`, `ruff`, `mypy --strict`,
  `pytest`, `pre-commit`, CI and release workflows, Dependabot, issue and pull request templates.
- `grokbot-kit --version`. The commands described in the README are not implemented yet.

[Unreleased]: https://github.com/rodrigo-pasini/grokbot-kit/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/rodrigo-pasini/grokbot-kit/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/rodrigo-pasini/grokbot-kit/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/rodrigo-pasini/grokbot-kit/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/rodrigo-pasini/grokbot-kit/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/rodrigo-pasini/grokbot-kit/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/rodrigo-pasini/grokbot-kit/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/rodrigo-pasini/grokbot-kit/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/rodrigo-pasini/grokbot-kit/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/rodrigo-pasini/grokbot-kit/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/rodrigo-pasini/grokbot-kit/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/rodrigo-pasini/grokbot-kit/releases/tag/v0.1.0
