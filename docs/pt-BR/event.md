# Evento `grokbot-kit.event/v1`

> Read in English: [event.md](../event.md)

Cada evento que o `grokbot-kit` envia à rota de um target é um objeto JSON com os 26 campos abaixo, sempre presentes
(campo sem valor vem `null`). O JSON Schema é
[`src/grokbot_kit/assets/event.v1.json`](../../src/grokbot_kit/assets/event.v1.json). Enquanto a versão é `0.x`, o
schema pode mudar, sempre com entrada no [CHANGELOG](../../CHANGELOG.md).

## Eventos e status

Uma tarefa envia exatamente um evento terminal (`completed`, `error` ou `timeout`), mais um evento `needs_input` a cada
vez que o agente para num pedido de permissão ou numa pergunta. Um pedido de permissão espera o `grokbot-kit reply`
até `needs_input.reply_deadline` (veja o README, Pedidos de permissão). O `grokbot-kit route test` envia um evento `test`,
com os campos de tarefa `null`.

| `event` | `status` | `exit_reason` |
| --- | --- | --- |
| `completed` | `ok`: o agente terminou | `success` |
| `completed` | `denied`: o agente terminou, mas um pedido de permissão terminou sem `allow` (negado, ou sem resposta até o `reply_deadline`) | `permission_denied` |
| `error` | `failed` | `agent_error` (a CLI informou um erro), `nonzero_exit`, ou `result_invalid` (tarefa de plugin cujo resultado não casa o schema do plugin) |
| `error` | `interrupted`: a tarefa recebeu `SIGINT` ou `SIGTERM` | `interrupted` |
| `timeout` | `timeout`: a tarefa passou do `--timeout` | `timeout` |
| `needs_input` | `permission` ou `question` | `needs_input` |
| `test` | `test` | `null` |

## Campos

| Campo | Tipo | O que traz |
| --- | --- | --- |
| `schema` | string | sempre `grokbot-kit.event/v1` |
| `event` | string | `completed`, `error`, `timeout`, `needs_input` ou `test` (tabela acima) |
| `status` | string | o desfecho dentro do evento (tabela acima) |
| `task_id` | string | o id da tarefa, também o nome do task dir `~/.grokbot-kit/tasks/<task_id>/`; `null` no `test` |
| `task_label` | string | o `--label` passado ao `grokbot-kit run`; `null` no `test` |
| `target` | string | o bot cuja rota recebeu o evento (`--target`) |
| `tool` | string | `opencode`, `claude` ou `codex`; `null` no `test` |
| `model` | string | o id do modelo que rodou por último; `null` no `test` |
| `model_source` | string | de onde veio o modelo: `user` (`--model`), `tier` (`--tier`) ou `default`; `null` no `test` |
| `model_fallbacks` | lista | um `{"model", "error"}` por tentativa de um tier que falhou no provedor e levou ao próximo id; `[]` sem fallback, `null` no `test` |
| `tier` | string | `trivial`, `standard` ou `complex`; `null` no `test` |
| `session_id` | string | o id da sessão do agente, quando a CLI informou um |
| `cwd` | string | o diretório em que o agente trabalhou |
| `repo` | objeto | `{"root", "branch", "head"}` do repositório git que contém o `cwd`; `null` fora de um repositório e no `test` |
| `exit_code` | inteiro | o exit do `grokbot-kit run` (o do agente, ou o do próprio kit em `timeout`, `interrupted` e binário ausente); `null` no `needs_input` e no `test` |
| `exit_reason` | string | por que a tarefa terminou (tabela acima) |
| `summary` | string | a mensagem final do agente, ou o erro da CLI quando a tarefa falhou sem ela; em tarefa de plugin, o `summary` do resultado |
| `needs_input` | objeto | num evento `needs_input`, `{"kind", "tool_name", "detail", "request_id", "reply_deadline"}`: o que o agente pediu; `null` nos outros. `needs_input.request_id` é o id que o `grokbot-kit reply` responde; `needs_input.reply_deadline` (ISO 8601) é quando o kit nega um pedido sem resposta, `null` quando ninguém espera resposta (`--ask-wait 0`, opencode 1.x, uma pergunta) |
| `resume_hint` | string | o comando que retoma a sessão do agente (`claude -p --resume <id>`, `opencode run -s <id>`, `codex exec resume <id>`); `null` sem `session_id` |
| `output_file` | string | a saída bruta do agente, `<task dir>/out.jsonl`; `null` no `test` |
| `transcript_path` | string | o transcript do próprio agente, quando o hook dele informou um |
| `log_file` | string | o stderr do agente, `<task dir>/stderr.log`; `null` no `test` |
| `started_at` | string | quando a tarefa começou (ISO 8601); `null` no `test` |
| `plugin` | objeto | em tarefa de plugin, `{"name", "version", "source", "commit"}` do plugin que rodou; `null` nas outras |
| `result` | objeto | em tarefa de plugin, o resultado estruturado que o plugin pede (veja [plugins.md](plugins.md)); `null` nas outras |
| `timestamp` | string | quando o evento foi montado (ISO 8601) |
