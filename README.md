# grokbot-kit

> Leia em português: [docs/pt-BR/README.md](docs/pt-BR/README.md)

Grok Bot integration kit: delegate tasks to headless coding agents (opencode, Claude Code, Codex) and wake the right
Grok Bot routine when they finish or need input.

**Status:** `0.x`. The commands below work; the event schema `grokbot-kit.event/v1` may still change, always with a
[CHANGELOG](CHANGELOG.md) entry.

**Fork:** snapshot of [rodrigo-pasini/grokbot-kit](https://github.com/rodrigo-pasini/grokbot-kit) at `51174f6` (0.7.0),
with Claude Code Hooks listening for Grok Bot: 9 progress hooks (`SessionStart`, `PreToolUse`, `PostToolUse`,
`PostToolUseFailure`, `PostToolBatch`, `TaskCreated`, `TaskCompleted`, `Notification`, `SessionEnd`) plus
`PermissionRequest`.

## What it is

A Grok Bot that delegates a long task to a headless coding agent hibernates while the agent runs, and nothing wakes
it up. The exit code alone does not tell whether the task was done, failed, or stopped at a permission prompt.

`grokbot-kit` wraps the agent run (`grokbot-kit run`), listens to each agent's native hooks, and sends exactly one
terminal event (`completed`, `error` or `timeout`) — plus a `needs_input` event when the agent hits a permission — to
the webhook trigger of the routine of the bot that delegated the task. Other bots are not woken up.

## Install

```sh
uv tool install --managed-python grokbot-kit
```

`pipx install grokbot-kit` also works. To try what is on `main` before it is released:

```sh
uv tool install --managed-python git+https://github.com/rodrigo-pasini/grokbot-kit
```

Requires Linux and Python 3.11 or newer (`uv` manages the interpreter). The package has no runtime dependencies.

## Quick start

### With a Grok Bot

Send this message to the bot. It installs the [skill](#grok-bot-skill) and walks you through the setup: the kit, the
CLIs and their login, the default CLI, the model tiers and the routine that the bot's events wake up. Replace
`mybot` with a short name for the bot (letters, digits, `.`, `_` and `-`).

```text
Install the grokbot-kit skill and set up grokbot-kit on this box:
1. Download https://github.com/rodrigo-pasini/grokbot-kit/releases/latest/download/SKILL.md (follow redirects)
   to /home/box/agent-data/workflows/grokbot-kit/SKILL.md (create the directory).
2. Read that skill and follow its "Setup (primeira vez)" section from start to finish, one step at a time,
   skipping what `grokbot-kit doctor --json` shows as already done. Use "mybot" as the name of this bot.
3. Never ask me for a secret (API key, routine URL or key) in the chat: read it yourself from the routine
   or ask me in a masked secret field, and pass it to `grokbot-kit secret set` on standard input.
4. At the end, run `grokbot-kit doctor --json` and summarise the result and any problems.
```

The bot creates the routine, with a webhook trigger and the routine prompt from the skill, or asks you to create it
in the Grok Bot panel. It reads the routine URL and key itself or asks for each one in a masked secret field, never
in the chat or a screenshot. When the setup ends, ask for a small task, such as "rename the variables in x.py": the bot picks the
`trivial` tier and tells you so, and the result arrives through the routine.

<details>
<summary>Screenshots of a setup and a task (Grok Bot, in Portuguese)</summary>

**1. The message and the choice of CLIs**

![1. The message and the choice of CLIs](https://raw.githubusercontent.com/rodrigo-pasini/grokbot-kit/main/docs/images/quickstart/01-pedido-e-clis.png)

**2. opencode installed, free models without login**

![2. opencode installed, free models without login](https://raw.githubusercontent.com/rodrigo-pasini/grokbot-kit/main/docs/images/quickstart/02-login.png)

**3. Model tiers and the routine created by the bot**

![3. Model tiers and the routine created by the bot](https://raw.githubusercontent.com/rodrigo-pasini/grokbot-kit/main/docs/images/quickstart/03-tiers-e-routine.png)

**4. Routine URL and key through the masked secret field**

![4. Routine URL and key through the masked secret field](https://raw.githubusercontent.com/rodrigo-pasini/grokbot-kit/main/docs/images/quickstart/04-segredos.png)

**5. A task delegated to opencode, with the result back through the routine**

![5. A task delegated to opencode, with the result back through the routine](https://raw.githubusercontent.com/rodrigo-pasini/grokbot-kit/main/docs/images/quickstart/05-tarefa.png)

</details>

### By hand

```sh
grokbot-kit setup cli add opencode
grokbot-kit setup default opencode
grokbot-kit secret set mybot-url
grokbot-kit secret set mybot-key
grokbot-kit route add mybot --url-secret mybot-url --key-secret mybot-key
grokbot-kit route test mybot
grokbot-kit run --target mybot --label rename-vars -- "Rename the variables in x.py"
```

## Grok Bot skill

`skills/grokbot-kit/` is a skill for any Grok Bot. Copy the folder into the bot's workflows directory and the bot can
install the kit, install and log in to the CLIs you choose, create the route to its own routine, and delegate tasks
choosing CLI and model.

## Commands

| Command | What it does |
| --- | --- |
| `grokbot-kit run` | runs a task in a headless agent and sends one terminal event to the route of `--target`; the model comes from `--model` or from `--tier` (`trivial`, `standard`, `complex`), and `--plugin` runs a [plugin](#plugins) |
| `grokbot-kit emit` | called by the agents' hooks inside a task; not for direct use |
| `grokbot-kit reply <task_id> <request_id> allow` | answers a permission request of a running task with `allow` or `deny`; `--message` tells the agent why (only with `deny`), `--by bot` records that the bot decided alone (default `user`); see [Permission requests](#permission-requests) |
| `grokbot-kit redeliver <task_id>` | resends the events of a task that were not delivered |
| `grokbot-kit gc --older-than <duration>` | removes the task dirs of tasks that finished long ago; `--dry-run` only lists them |
| `grokbot-kit route add <bot>` | `add` routes a bot to its routine webhook (URL and key from two secrets), `rm` removes the route, `test` sends a `test` event |
| `grokbot-kit setup cli add <tool>` | sets up the CLIs: `cli add` installs one with its official installer, `default` picks the one used when a task names none, `models refresh` discovers the model ids, `providers` picks the opencode providers and `tiers` sets the ids of a tier (see [Models](#models)); `cli upgrade` reruns the official installer to bring a CLI to its latest version, and rewrites the opencode plugin for the new version |
| `grokbot-kit login <tool>` | logs a CLI in with its official command, by subscription or API key (`--method`) |
| `grokbot-kit doctor` | checks versions, CLIs, logins, routes, secrets and plugins, with the command that fixes each problem; `--json` for the bot |
| `grokbot-kit install opencode` | installs the opencode plugin that reports permission requests (inert outside a task) |
| `grokbot-kit uninstall opencode` | removes the opencode plugin |
| `grokbot-kit update check` | tells whether a new release exists; `apply` upgrades, `skip <version>` and `later` stop asking |
| `grokbot-kit plugin list` | lists the plugins; `show` prints a manifest, `add` installs one from a directory or git URL, `rm` removes it |
| `grokbot-kit secret set <name>` | stores a secret in `~/.secrets/grokbot-kit/` with mode `0600`, read without echo or from stdin |

`grokbot-kit <command> --help` shows every option. The ones not named above:

- `grokbot-kit --version` prints the installed version.
- `run --tool <tool>` picks the CLI of the task (default: the one set with `setup default`); `run --timeout <duration>`
  (`30m`, `2h`, `1d`) overrides `timeouts.<tier>` of the config; `run --prompt-file <file>` reads the prompt from a
  file, passed to the agent after the arguments that follow `--`; `run --ask-wait <duration>` sets how long a
  permission request waits for `grokbot-kit reply` (`0` only notifies; default `ask.wait` of the config, `10m`).
- `emit --from <tool>` names the CLI whose hook is calling.
- `route add --header 'Name: value'` adds a header to every request of the route; repeatable.
- `setup models refresh --add <id>` (`claude` and `codex`) also tests and records an id the discovery does not list.
- `login --secret <name>` names the secret that holds the API key (default: `<tool>-api-key`).

## Permission requests

When the agent of a task asks for a permission, the kit sends a `needs_input` event with `needs_input.request_id` and
`needs_input.reply_deadline`, and the agent waits. `grokbot-kit reply <task_id> <request_id> allow` (or `deny`) answers
it: with `allow` the agent uses the tool in the same task, and the task can still end `ok`. With no reply before
`reply_deadline` (10 minutes by default, `ask.wait` in the config or `run --ask-wait`), the kit denies the request, as
it did before this feature. The Grok Bot skill answers low-risk requests by itself (reading files, running tests,
editing inside the task's directory) with `--by bot`, and asks the user about everything else.

Replies work with Claude Code and with opencode 2.x. opencode 1.x only notifies the request (`reply_deadline` is
`null`); `grokbot-kit setup cli upgrade opencode` brings opencode to its latest version and rewrites the plugin, and
`grokbot-kit doctor` warns while opencode is 1.x. Codex never asks: `codex exec` denies every approval by itself.

## Plugins

A plugin is a ready-made task: a prompt, the inputs it asks for and what the agent may do while it runs (`write`,
`network`, `commands`). The kit ships `code-review` (reviews a GitHub pull request) and `bug-verify`;
`grokbot-kit plugin list` shows them and the installed ones. The bot runs a plugin with a few inputs, without writing a
prompt, and the event brings the plugin's structured result:

```sh
grokbot-kit run --plugin code-review --input pr=https://github.com/<owner>/<repo>/pull/<n> --target <bot> --label review
```

The format, the capabilities each CLI enforces and how to write a plugin are in [docs/plugins.md](docs/plugins.md).

## Models

`grokbot-kit setup models refresh --json` lists the model ids of each CLI. In opencode, each id carries its provider,
the text before the first `/` (`opencode-go` in `opencode-go/<model>`). The bot asks which opencode providers you use
and records them; a paid provider needs `grokbot-kit login opencode` first:

```sh
grokbot-kit setup providers opencode opencode-go
```

Then it asks for the ids of each tier, in order. With providers recorded, `setup tiers` refuses an opencode id from
another provider, and `grokbot-kit doctor` reports a tier that has one:

```sh
grokbot-kit setup tiers opencode standard <id> <id>
```

`grokbot-kit run --tier <tier>` launches the first id of the tier. When the provider fails before the agent uses any
tool (opencode: an `error` with no `tool_use`; Claude Code: an `api_error` in the first turn), the kit launches the
next id in the same task, within the same timeout. The event names the model that ran last in `model` and lists the
ones that failed, with the reason, in `model_fallbacks`. A model given with `--model` is never replaced, and Codex
never falls back. When a task fails without a final message from the agent, `summary` carries the error of the CLI.

## Event

Each event the routine receives is a `grokbot-kit.event/v1` JSON object: `event` and `status` say how the task ended,
`summary` carries the agent's final message, and `resume_hint` the command that resumes its session. Every field is
described in [docs/event.md](docs/event.md).

## Configuration

The configuration lives in `~/.config/grokbot-kit/config.toml`: installed CLIs and the default one, model tiers
(`trivial`, `standard`, `complex`) per CLI, timeouts per tier, how long a permission request waits for a reply
(`[ask] wait`, default `10m`), and one route per target bot. Each task keeps its
output, logs and events in `~/.grokbot-kit/tasks/<task_id>/` until `grokbot-kit gc` removes it.

## Security

- Secrets (routine URL and key, API keys) are written with `grokbot-kit secret set` to `~/.secrets/grokbot-kit/`
  with mode `0600`, never to the config file and never pasted into a chat.
- `grokbot-kit` never writes a secret to logs, stdout, stderr or events.
- `~/.claude/settings.json` and `~/.codex/` are never modified; Codex runs in its own `CODEX_HOME`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). Third-party material in this repository is listed in [NOTICE](NOTICE).
