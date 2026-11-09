# needs-input-reply - pesquisa de 04-05/11/2026

Insumo do `plan.md` (issue #41). Fatos levantados na sessão do clone principal; cada um com a fonte.

## Hoje

- O kit roda as três CLIs em headless de tiro único (`launch.agent_argv`): `claude -p --output-format json`,
  `opencode run --format json`, `codex exec --json`.
- O `needs_input` só avisa: o `emit` (`emit.py`) normaliza o hook, entrega o evento e responde `{}` na hora; a CLI
  nega a ferramenta e o agente segue. O terminal sai `completed`/`denied` (`terminal.py:137`, AC 44 da
  agent-run-notify). O bot só pode retomar depois, com `resume_hint`.
- O plugin do opencode (`assets/opencode/grokbot-kit.ts`) escuta `permission.asked`/`question.asked` pelo hook
  `event` e chama `grokbot-kit emit --from opencode` com `spawnSync` (timeout 30 s); não decide nada.

## Claude Code (`-p`) - fonte: https://code.claude.com/docs/en/hooks.md (#permissionrequest-decision-control), .../headless.md

- Em `-p` (Manual mode, 2.1.302+), uma chamada que pede aprovação é negada a menos que algo aprove, "such as a
  `PermissionRequest` hook or a `--permission-prompt-tool`".
- Decisão do hook de comando, saindo com `0`:
  `{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow"}}}` ou
  `{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"deny","message":"..."}}}`
  (`interrupt: true` no deny encerra o Claude). `allow` não passa por cima de regra `deny` configurada.
- Exit `2` não é honrado neste evento; outro exit != 0 é falha mesmo com JSON de allow.
- `timeout` do hook em segundos, padrão 600 para `command`; máximo não documentado. `"onFailure": "block"` (2.1.295+)
  faz timeout/crash/JSON inválido negarem.
- A entrada do hook não traz `tool_use_id` (o `_discriminator` já cai no hash de `tool_name` + `tool_input`).
- **Não confirmado na doc:** que o hook síncrono segura o agente durante a espera (esperado, pelo padrão de 600 s)
  e se `timeout` > 600 é aceito -> spike.

## opencode 2.x - fonte: sst/opencode HEAD `e23d54ca` (2.2.5; instalado 2.2.4)

- Não há `permission.ask` no v2. O equivalente é `ctx.permission.hook("evaluate", cb)`
  (`packages/plugin/src/promise/permission.ts`): o evento tem `sessionID`, `action`, `resources[]`, `metadata?`,
  `source?` e os campos mutáveis `effect: "allow"|"deny"|"ask"` e `message?`. Exemplo interno:
  `packages/core/src/config/plugin/policy.ts:98`.
- Regra `deny` do config corta antes do hook (`core/src/permission.ts:184-187`).
- O callback pode ser assíncrono e o core espera (`core/src/plugin/hooks.ts:88-95`); nenhum timeout achado.
- Sem decisão (`ask`), o cliente do `opencode run` responde sozinho `reject` ("auto-rejecting",
  `cli/src/run/noninteractive.ts:189-214`); `--auto` responde `once` a tudo que está em `ask`.
- **Não confirmado:** se um plugin de arquivo global (`~/.config/opencode/plugins/grokbot-kit.ts`, formato
  `({ client }) => ({ event })`) alcança `permission.hook("evaluate")` -> spike.
- `question` segue fora: o `opencode run` cria a sessão com `question: deny` (AD-026).

## Codex - fora desta feature

- `codex exec` força `approval_policy = Never` (`codex-rs/exec/src/lib.rs:594-597`) e rejeita pedidos de aprovação
  ("approval is not supported in exec mode"); o hook `PermissionRequest` não é chamado (AD-027, spike de 19/10).
- `--approve-for-me` liga `on-request` + `auto_review`, mas força `sandbox_mode = "workspace-write"`, que não sobe
  no box (#33).
- O caminho é o `codex app-server` (JSON-RPC, experimental): `item/commandExecution/requestApproval`,
  `item/fileChange/requestApproval`, `item/tool/requestUserInput`, `turn/steer`, `turn/interrupt`. Feature própria.

## Decisões do Rodrigo (05/11/2026, recomendações aceitas)

- Espera padrão de 10 min, configurável em `[ask] wait` e por `run --ask-wait <dur>`; `0` desliga.
- Ligado por padrão em Claude e opencode.
- Prazo vencido = negar (o comportamento de hoje).
- Tarefas de plugin não perguntam (como hoje, AC 44 da plugins).

## Desenho proposto (a confirmar no plano)

- O `emit` registra e entrega o `needs_input` e espera `<task_dir>/replies/<discriminator>.json` até o prazo.
- Novo `grokbot-kit reply <task_id> <id> allow|deny [--message <texto>]` grava a resposta.
- O evento `needs_input` ganha o id da resposta e o prazo (`docs/event.md`, aditivo em `0.x`, AD-006).
- Permissão aprovada não leva o terminal a `denied` (muda o AC 44 da agent-run-notify).
- A skill do bot (`skills/grokbot-kit/SKILL.md`, seção do `needs_input`) passa a perguntar ao usuário e chamar o
  `reply`.
