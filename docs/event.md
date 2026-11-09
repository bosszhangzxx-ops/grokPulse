# Event `grokbot-kit.event/v1`

> Leia em português: [pt-BR/event.md](pt-BR/event.md)

Every event `grokbot-kit` sends to the route of a target is one JSON object with the 26 fields below, always present
(a field with no value is `null`). The JSON Schema is
[`src/grokbot_kit/assets/event.v1.json`](../src/grokbot_kit/assets/event.v1.json). While the version is `0.x` the
schema may change, always with an entry in the [CHANGELOG](../CHANGELOG.md).

## Events and status

A task sends exactly one terminal event (`completed`, `error` or `timeout`), plus one `needs_input` event each time the
agent stops at a permission prompt or a question. A permission request waits for `grokbot-kit reply` until
`needs_input.reply_deadline` (see the README, Permission requests). `grokbot-kit route test` sends a `test` event, whose task fields are
`null`.

| `event` | `status` | `exit_reason` |
| --- | --- | --- |
| `completed` | `ok`: the agent finished | `success` |
| `completed` | `denied`: the agent finished, but a permission request ended without `allow` (denied, or no reply before `reply_deadline`) | `permission_denied` |
| `error` | `failed` | `agent_error` (the CLI reported an error), `nonzero_exit`, or `result_invalid` (a plugin task whose result does not match the plugin's schema) |
| `error` | `interrupted`: the task got `SIGINT` or `SIGTERM` | `interrupted` |
| `timeout` | `timeout`: the task ran past `--timeout` | `timeout` |
| `needs_input` | `permission` or `question` | `needs_input` |
| `test` | `test` | `null` |

## Fields

| Field | Type | What it holds |
| --- | --- | --- |
| `schema` | string | always `grokbot-kit.event/v1` |
| `event` | string | `completed`, `error`, `timeout`, `needs_input` or `test` (table above) |
| `status` | string | the outcome within the event (table above) |
| `task_id` | string | the id of the task, also the name of its task dir `~/.grokbot-kit/tasks/<task_id>/`; `null` in `test` |
| `task_label` | string | the `--label` given to `grokbot-kit run`; `null` in `test` |
| `target` | string | the bot whose route received the event (`--target`) |
| `tool` | string | `opencode`, `claude` or `codex`; `null` in `test` |
| `model` | string | the model id that ran last; `null` in `test` |
| `model_source` | string | where the model came from: `user` (`--model`), `tier` (`--tier`) or `default`; `null` in `test` |
| `model_fallbacks` | list | one `{"model", "error"}` per attempt of a tier that failed at the provider and led to the next id; `[]` without fallback, `null` in `test` |
| `tier` | string | `trivial`, `standard` or `complex`; `null` in `test` |
| `session_id` | string | the agent's session id, when the CLI reported one |
| `cwd` | string | the directory the agent worked in |
| `repo` | object | `{"root", "branch", "head"}` of the git repository that holds `cwd`; `null` outside a repository and in `test` |
| `exit_code` | integer | the exit code of `grokbot-kit run` (the agent's, or the kit's own in `timeout`, `interrupted` and a missing binary); `null` in `needs_input` and `test` |
| `exit_reason` | string | why the task ended (table above) |
| `summary` | string | the agent's final message, or the CLI's error when the task failed without one; in a plugin task, the `summary` of the result |
| `needs_input` | object | in a `needs_input` event, `{"kind", "tool_name", "detail", "request_id", "reply_deadline"}`: what the agent asked for; `null` otherwise. `needs_input.request_id` is the id `grokbot-kit reply` answers; `needs_input.reply_deadline` (ISO 8601) is when the kit denies an unanswered request, `null` when nobody waits for a reply (`--ask-wait 0`, opencode 1.x, a question) |
| `resume_hint` | string | the command that resumes the agent's session (`claude -p --resume <id>`, `opencode run -s <id>`, `codex exec resume <id>`); `null` without `session_id` |
| `output_file` | string | the agent's raw output, `<task dir>/out.jsonl`; `null` in `test` |
| `transcript_path` | string | the agent's own transcript, when its hook reported one |
| `log_file` | string | the agent's stderr, `<task dir>/stderr.log`; `null` in `test` |
| `started_at` | string | when the task started (ISO 8601); `null` in `test` |
| `plugin` | object | in a plugin task, `{"name", "version", "source", "commit"}` of the plugin that ran; `null` otherwise |
| `result` | object | in a plugin task, the structured result the plugin asks for (see [plugins.md](plugins.md)); `null` otherwise |
| `timestamp` | string | when the event was built (ISO 8601) |
