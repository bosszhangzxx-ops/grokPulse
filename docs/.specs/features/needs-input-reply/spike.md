# needs-input-reply - spikes de 05/11/2026

Host de dev, `claude` 2.1.318, `opencode` v2.2.4. Scripts e saídas brutas ficaram no scratchpad da sessão (fora do
repo); abaixo, os comandos e o que voltou.

## Veredito

| Pergunta | Resposta | Prova |
| --- | --- | --- |
| O hook `PermissionRequest` síncrono segura o `claude -p` enquanto espera? | sim | 1a: 30 s de espera, depois `allow`, ferramenta rodou |
| `timeout` acima de 600 no hook é aceito? | sim, na config e na prática | 1a (`timeout: 1200`) e 1d (espera de 660 s com `timeout: 900`) |
| Hook que estoura o `timeout` nega? | sim, sem `onFailure` | 1c: `timeout: 10`, hook de 40 s, negado em ~10 s |
| O plugin global do opencode 2.x decide pelo `permission.hook("evaluate")`? | sim, com `export default { id, setup }` | 2a (`allow` depois de 20 s) e 2b (`deny` com mensagem) |
| O callback assíncrono pode esperar muito? | sim, sem timeout do core em 660 s | 2e |
| O plugin atual do kit carrega no opencode 2.2.4? | **não** | 2d: "Plugin must export a default definition with an id and an effect or setup function" |
| Um arquivo com os dois formatos (v1 nomeado + v2 default) serve? | não no 2.x: o export nomeado é ignorado | 2c |

## Spike 1 - `claude -p` com hook `PermissionRequest` que espera

Isolamento: cwd vazio no scratchpad, `--setting-sources project` (sem as configs do usuário, que têm
`defaultMode: auto` e hooks próprios), `--permission-mode default`, hook só por `--settings`.

Hook (`hook.sh <log> <segundos>`): grava início, lê a entrada, dorme, grava fim e imprime
`{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow"}}}` com exit `0`.

```sh
claude -p --setting-sources project --permission-mode default --settings settings30.json --output-format json \
  "Run exactly this bash command and nothing else: touch <dir>/spike1-ok.txt  . Then reply DONE."
# settings30.json: {"hooks":{"PermissionRequest":[{"matcher":"*","hooks":[{"type":"command",
#                   "command":"hook.sh log30 30","timeout":1200}]}]}}
```

- **1a (espera de 30 s, `timeout: 1200`)**: exit `0`, `result` `DONE`, `permission_denials` `[]`, `num_turns` 2,
  `duration_ms` 33336; o hook começou em `…970.25` e terminou em `…000.26` (30,0 s); `spike1-ok.txt` criado. O
  `timeout: 1200` não deu erro de config.
- **1b (controle, sem hook)**: o `touch` foi negado (`permission_denials` com o `Bash`, `tool_use_id` presente na
  saída mas não na entrada do hook); arquivo não criado.
- **1c (hook de 40 s com `timeout: 10`)**: negado; a tarefa inteira levou 16 s (`duration_ms` 14540), o log do hook
  só tem `start`: o Claude matou o hook no timeout e tratou como sem decisão, sem precisar de `onFailure: block`.
- **1d (espera de 660 s, `timeout: 900`)**: exit `0`, `result` `DONE`, `permission_denials` `[]`, `duration_ms`
  663671; o hook rodou de `…017.96` a `…677.97` (660,0 s) e `spike1-long.txt` foi criado. O limite de 600 s não é
  teto: o `timeout` configurado vale.

A entrada do hook trouxe `session_id`, `transcript_path`, `cwd`, `prompt_id`, `permission_mode`, `effort`,
`hook_event_name`, `tool_name`, `tool_input`, `permission_suggestions`; sem `tool_use_id`, como a research previa.

## Spike 2 - plugin global do opencode 2.x com `permission.hook("evaluate")`

Isolamento: `HOME` temporário no scratchpad com cópia (backup SQLite) do `opencode.db` e do `auth.json`, para ter as
credenciais do `opencode-go` sem tocar o `~/.config/opencode/plugins/` real; `opencode run --standalone` (o mesmo
que o harness do kit usa no 2.x, `launch.py:104`), `OPENCODE_DISABLE_PROJECT_CONFIG=1`,
`OPENCODE_CONFIG_CONTENT='{"permission":{"bash":"ask"}}'`, modelo `opencode-go/glm-5.3-flash`.

Plugin de teste em `$HOME/.config/opencode/plugins/spike.ts`:

```ts
export default {
  id: "grokbot-spike",
  setup: async (ctx: any) => {
    await ctx.permission.hook("evaluate", async (e: any) => {
      if (e.effect !== "ask") return
      await new Promise((r) => setTimeout(r, Number(process.env.SPIKE_WAIT ?? 20000)))
      e.effect = process.env.SPIKE_EFFECT ?? "allow"
      if (e.effect === "deny") e.message = "negado pelo spike"
    })
  },
}
```

- **2-controle (sem plugin)**: `tool_use` com erro "This non-interactive run cannot ask the user for permission, so
  the request was rejected"; stderr `permission requested: shell (touch …); auto-rejecting`. A ação v2 do shell é
  `shell`, não `bash` (a chave da config segue `bash`).
- **2a (espera de 20 s, `allow`)**: o `setup` recebeu `ctx` com `permission` (e `app`, `session`, `event`, …); o
  `evaluate` chegou com `{"sessionID":"ses_…","action":"shell","resources":["touch …/ok.txt"],"effect":"ask",
  "source":{"type":"tool","messageID":"msg_…","id":"chatcmpl-tool-b710cb936a4f8efc"}}`; decidiu `allow` 20,0 s depois;
  `tool_use` `completed`, resposta `DONE`, `ok.txt` criado, 26 s no total.
- **2b (`deny` com `message`)**: `tool_use` com erro `negado pelo spike`; o agente relatou
  `permission.rejected: negado pelo spike`; arquivo não criado.
- **2c (um arquivo com `export const Legacy = async ({ client }) => ({ event })` e `export default { id, setup }`)**:
  só o v2 rodou (`v2 setup`, `v2 evaluate effect=ask`); o `Legacy` não foi chamado.
- **2d (só o export nomeado, e depois o `src/grokbot_kit/assets/opencode/grokbot-kit.ts` real com o executável
  trocado por `/bin/true` e `GROKBOT_KIT_TASK_ID` no ambiente)**, com `--print-logs --log-level debug`:
  `failed to load plugin … PluginModule.LoadError: Plugin must export a default definition with an id and an effect or
  setup function. (cause: SchemaError(Missing key at ["default"]))`. O plugin que o kit instala hoje não carrega no
  opencode 2.2.4.
- **2e (espera de 660 s, `allow`)**: o `evaluate` chegou em `…223.95` e decidiu `allow` em `…883.95` (660,0 s); `tool_use`
  `completed`, resposta `DONE`, `ok.txt` criado, 665 s no total, exit `0`. Nenhum timeout do core nem do `run`.

`source.id` é o id do tool call (único por chamada), bom como `request_id`; não há `parentID` no evento (o plugin
segue perguntando a sessão).

## O que isto muda no plano

- O hook do Claude pode ter `timeout` = espera + 60 s; o timeout do hook já nega sozinho.
- O plugin do opencode 2.x precisa de um asset novo com `export default`; o asset atual não serve no 2.x nem junto
  (door 5 do plano). Isso também conserta o aviso de `needs_input` do opencode 2.x, que hoje não chega.
- Não testado: o opencode 1.x (não há binário 1.x no host de dev); o box estava no 1.19.3 em 22/10 (AD-042).
