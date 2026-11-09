# Plugins do grokbot-kit

> Plan from this document. Each slice below carries its own shape - copy it, do not re-derive it.
> Status: confirmed by Rodrigo, 2026-10-21

## Situation

- Project: in active construction - `0.3.0`, UAT com um Grok Bot real feito, sem divulgação e sem usuários além do Rodrigo.
- Decision: committed by Rodrigo, 2026-10-21, nesta discovery (veredito de construir confirmado).
- In flight: copia a injeção por task que o `run` já faz (settings do Claude no task dir, `-c` no `CODEX_HOME` do kit, plugin do opencode inerte fora de task) e a regra de evoluir `grokbot-kit.event/v1` antes da 1.0 (AD-006). Fica fora a worktree `kit-update`, que só mexe na atualização do kit.
- At stake: o formato do plugin vira contrato para terceiros desde o primeiro release (instável até a 1.0, como o webhook), e as capacidades decidem o que um agente pode fazer no box compartilhado, inclusive com o `gh` autenticado.

## Problem

O Grok Bot já revisa os PRs de um repositório que ele observa, mas revisa com a própria capacidade: pelo menos 10 reviews por dia, que comem boa parte do limite de tokens do bot (relato do Rodrigo; não há medição). O kit existe justamente para delegar trabalho longo às CLIs do box, mas hoje só aceita um prompt solto: o bot teria que escrever o prompt do review a cada vez, o agente roda com o `gh` autenticado e permissão de escrita (pode dar push no PR que revisa), e o resultado volta como texto livre que o bot precisa reler.

O que esta peça torna possível: capacidades prontas e reaproveitáveis - review de PR, verificação de um alerta de erro contra o código - que o bot dispara com poucos parâmetros, que rodam independentes do harness do repositório alvo, com o que o agente pode fazer declarado e imposto, e que outras pessoas conseguem escrever seguindo um guia.

## Success

- Worked if: duas semanas depois do release, todos os reviews do repositório observado rodam por `--plugin code-review`, e o custo no limite do bot cai a disparar a tarefa e ler o resultado.
- Going wrong: o bot relê o diff ou o PR para entender o resultado (o `result` não basta), ou algum review escreve fora do task dir.
- Review: 2 semanas depois do release - Rodrigo.

## Boundary

In: formato do plugin; capacidades declaradas e a tradução de cada uma para as três CLIs; `grokbot-kit plugin list|show|add|rm`; `run --plugin` com entradas e workspace clonado; resultado estruturado no evento; plugins próprios `code-review` e `bug-verify`; guia de como escrever plugins com o `code-review` como exemplo; skill do bot listando plugins e capacidades.

Out: o kit escutar GitHub ou observabilidade - o bot é quem dispara (AD-005, sem servidor de longa duração). Fluxos de várias etapas orquestrados pelo kit - o fluxo vive na skill do plugin. Gates em forma de script e hooks de plugin - capacidades declaradas cobrem os dois casos e mantêm o plugin sem código executável. Comandos, agentes e MCP de plugin - nenhum dos dois casos precisa. Marketplace ou registro de plugins. Atualização automática de plugins de terceiros. Estabilidade do formato antes da 1.0.

Unchanged: `run` sem `--plugin` continua igual; `emit` e `needs_input`; rotas, sinks e segredos; o plugin global do opencode do kit (AD-028/AD-033) continua só repassando ao `emit`; `~/.claude` e `~/.codex` do usuário seguem intocados (AD-010).

## Prior art

- Plugin do Claude Code (`.claude-plugin/plugin.json`, `skills/`) e o padrão `SKILL.md`, que opencode e Codex também leem - adotamos o layout em vez de inventar um.
- Bots de review (Codex Review, Greptile) leem o `AGENTS.md`/`CLAUDE.md` do repo como diretrizes de review - adotamos como contexto (Key decision 3).
- A falha conhecida de agentes revisando conteúdo de terceiros é prompt injection vinda do próprio PR - Key decisions 2 e 3 existem para que um texto do PR não amplie permissão nem rode configuração.

## Shape

Um plugin é um diretório no layout de plugin do Claude Code mais um manifesto do kit, `grokbot-kit.toml`, que declara entradas, capacidades, prompt e o resultado prometido. `grokbot-kit run --plugin <nome> --input k=v` clona o PR ou a branch no task dir, monta o harness da CLI escolhida a partir do plugin, recusa se a CLI não consegue impor as capacidades, e devolve o resultado validado no evento. A porta é o formato do plugin com o vocabulário fechado de capacidades: aberto a terceiros desde já, instável até a 1.0.

A forma mais pesada - compatibilidade total com plugins do Claude Code (hooks, comandos, agentes, MCP) traduzida para as três CLIs, com sandbox próprio do kit - só se paga se terceiros chegarem trazendo plugins do Claude Code prontos, e hoje o kit não tem usuários.

## Key decisions

1. **O formato é o layout de plugin do Claude Code restrito a manifesto e `skills/`, mais o `grokbot-kit.toml`; qualquer outra coisa recusa a instalação.** Um plugin com `hooks/`, `commands/`, `agents/`, `.mcp.json` ou `.lsp.json` não instala, para que plugin seja só texto e declaração, nunca código que roda no box. O mesmo diretório carrega no Claude Code sem o kit. Formato instável até a 1.0, com aviso no `CHANGELOG.md`, como a AD-006.
2. **Nenhuma tarefa roda com permissão mais aberta do que o plugin declara.** Se a CLI escolhida não consegue impor uma capacidade, o `run` sai com `2` antes de existir task dir, nomeando a capacidade e a CLI. `plugin show` e `doctor` dizem, por CLI, se cada capacidade é imposta por sandbox do sistema (`os`) ou por permissão de ferramenta (`tool`), para quem instala saber a força real da garantia.
3. **Nada do workspace clonado executa como configuração do harness; só o texto de instruções do repo entra, como contexto.** `CLAUDE.md`/`AGENTS.md` do repo são lidos; settings, hooks, plugins e MCP do repo (`.claude/settings*.json`, `.opencode/`, `.codex/`) não carregam. Regras e capacidades do plugin prevalecem, e quem as garante é a CLI, não o texto. Não copiar o `run` atual neste ponto: hoje o `claude -p` carrega os settings do projeto no `cwd`, e num clone de PR isso deixaria o autor do PR rodar hooks no box.
4. **O workspace é um clone novo, feito pelo kit antes do lançamento, dentro do task dir; o agente só escreve no task dir.** A entrada de tipo `repo` aceita URL de PR ou de branch do GitHub; o kit clona com o `gh` do box e o `cwd` do agente é o clone, para que as CLIs leiam as instruções do repo sozinhas. Clonar antes, e não deixar o agente clonar, é o que faz a Key decision 3 valer.
5. **Sucesso de tarefa de plugin exige o resultado prometido, válido.** O agente grava o resultado no task dir; o kit confere os campos que o manifesto declara obrigatórios e leva o objeto no evento como `result`, com `plugin` (nome, versão, origem). Resultado ausente ou inválido vira `error`/`failed` com `exit_reason` `result_invalid`, estendendo a AD-008. Os campos novos são aditivos a `grokbot-kit.event/v1`.
6. **Plugin instalado é uma cópia fixada, nunca atualizada sozinha.** `plugin add` copia o diretório ou o commit do git para o diretório de plugins do kit, grava origem e commit, mostra as capacidades e exige confirmação; `--yes` só depois que o bot perguntou ao usuário. Os plugins próprios vêm dentro do pacote e mudam com a versão do kit.
7. **O kit não dispara nem encadeia tarefas.** Quem dispara é o Grok Bot (evento do PR, alerta, pedido no chat); o fluxo do plugin vive na sua skill, e efeitos externos (comentário no PR) são feitos pelo agente com as capacidades declaradas.

## Work

| Slice | Delivers | Status |
|---|---|---|
| [`plugin`](#plugin) | formato, diretório de plugins, `plugin list/show/add/rm` e plugins próprios listados | open — 2 defaults taken |
| [Capabilities](#capabilities) | vocabulário de capacidades e sua tradução para claude, opencode e codex | spike |
| [`run --plugin`](#run---plugin) | entradas, workspace clonado e harness montado por task | clear |
| [`result`](#result) | resultado validado e campos `plugin`/`result` no evento | clear |
| [`code-review`](#code-review) | plugin próprio de review de PR, exemplo de referência | open — 2 defaults taken |
| [`bug-verify`](#bug-verify) | plugin próprio de verificação de alerta contra o código | open — 1 default taken |
| [Skill e guia](#skill-e-guia) | skill do bot com plugins e capacidades; guia de autoria | clear |

Order: Capabilities (spike) → `plugin` → `run --plugin` → `result` → `code-review` → `bug-verify` → Skill e guia.

Already handled by existing code: tarefa que estoura o tempo ou é interrompida → `timeout`/`interrupted` do `run`; entrega que falha → retry e `redeliver`; task dir antigo, clone incluído → `gc`.

Derivable from the repository, left to the plan: mensagens de erro, códigos de saída `1`/`2`, saída `--json` e o registro no `doctor` - todos como `setup` e `update` já fazem; nomes de diretórios sob `~/.grokbot-kit/`.

### `plugin`

**Delivers** o formato e o ciclo de vida de um plugin instalado. **Status: open.** É a porta da Key decision 1.

| State | What should happen | Caller sees |
|---|---|---|
| `plugin list` | plugins próprios e instalados, com versão, origem (`builtin`, diretório ou git+commit) e capacidades | lista; `--json` para a skill |
| `plugin show <nome>` | manifesto, entradas, capacidades e, por CLI, `os`/`tool`/`unsupported` | texto ou `--json` |
| `plugin add` de terceiro | mostra capacidades e pede confirmação; grava cópia fixada (Key decision 6) | prompt; `0` |
| `plugin add` com `hooks/`, `commands/`, `agents/`, MCP ou LSP | recusa, nada gravado (Key decision 1) | `2`, nomeando o que foi encontrado |
| manifesto inválido ou capacidade fora do vocabulário | recusa, nada gravado | `2` |
| nome igual a um plugin próprio | recusa | `2` |
| `plugin add` de um nome já instalado | recusa sem `--replace` | `2` |
| `plugin rm` com tarefa do plugin rodando | recusa | `2` |
| `doctor` | lista plugins e acusa manifesto ilegível ou CLI que não impõe uma capacidade | entrada em `problems` |

`grokbot-kit plugin list [--json]` · `plugin show <nome> [--json]` · `plugin add <dir|git-url> [--ref <commit>] [--replace] [--yes]` · `plugin rm <nome>`

Manifesto `grokbot-kit.toml`:

| Campo | Tipo | Obrigatório | Nota |
|---|---|---|---|
| `schema` | string | sim | `grokbot-kit.plugin/v0` |
| `name`, `version`, `description` | string | sim | `name` igual ao de `.claude-plugin/plugin.json` |
| `prompt` | string | sim | arquivo do plugin com o prompt da tarefa; `{input}` substitui entradas |
| `inputs.<nome>.kind` | enum | sim | `repo`, `text`, `file` |
| `inputs.<nome>.required` | bool | não | padrão `true` |
| `capabilities` | tabela | sim | vocabulário do slice Capabilities |
| `result.required` | lista de string | sim | campos obrigatórios do resultado |
| `result.max_bytes` | int | não | padrão 16384 |

Alternatives considered: plugins em git sem cópia local - ganha se plugins mudassem várias vezes por dia, o que não é o caso.

1. Fixar plugin de git exige `--ref` com commit completo? - default: aceita branch ou tag, resolve para o commit e grava o commit.
2. Entrada `repo` limitada ao GitHub? - default: sim no v0 (o box tem o `gh`); outro forge é mudança aditiva.

### Capabilities

**Delivers** o vocabulário fechado de capacidades e como cada CLI o impõe. **Status: spike.** Concretiza a Key decision 2.

Vocabulário v0: `write` = `task-dir` | `none`; `commands` = lista de prefixos de comando permitidos (por exemplo `gh pr view`, `gh pr review`, `git`, `pytest`), o resto negado; `network` = `on` | `off`.

| Capacidade | claude | opencode | codex |
|---|---|---|---|
| `write: task-dir` | regras de permissão de edição por caminho + `--add-dir` (`tool`); sandbox do Claude (`os`) se o box permitir | `permission.edit` + `external_directory` negado fora do task dir (`tool`) | `--sandbox workspace-write` com `cwd` no task dir (`os`) |
| `commands` | `--allowedTools`/regras `Bash(<prefixo> *)` (`tool`) | `permission.bash` por padrão (`tool`) | regras de execução do Codex - a verificar |
| `network: off` | sandbox do Claude - a verificar | sem mecanismo conhecido → `unsupported` | `network_access = false` (`os`) |
| ignorar settings do repo (Key decision 3) | `--setting-sources user` + `--settings` do kit | config por task em `OPENCODE_CONFIG` (AD-028) - falta saber se impede `.opencode/` do projeto | `CODEX_HOME` do kit; config de projeto do Codex - a verificar |
| skills do plugin | `--plugin-dir` (nativo) | diretório de skills - a verificar | skills no `CODEX_HOME` - a verificar sem perder o login |

| State | What should happen | Caller sees |
|---|---|---|
| CLI impõe tudo o que o plugin declara | roda | — |
| alguma capacidade `unsupported` na CLI escolhida | recusa antes do task dir (Key decision 2) | `2`, capacidade e CLI |
| Codex no box atual: sandbox `bwrap` não sobe (STATE, erro aberto do S3) | `write: task-dir` é `unsupported` no Codex até o sandbox funcionar | `2`; `doctor` acusa |

- Spike: no box (claude 2.1.30x, opencode 1.19.3, codex 0.163.0), para cada célula "a verificar" e para `write: task-dir` com bash liberado, provar com um agente tentando escrever fora do task dir, rodar comando fora da lista e carregar settings/hooks de um repo clonado - cada célula vira `os`, `tool` ou `unsupported`; uma célula `unsupported` em `write` ou em "ignorar settings do repo" tira a CLI dos plugins no v0. Para quando as 15 células tiverem valor provado.

### `run --plugin`

**Delivers** `grokbot-kit run --plugin <nome> --input k=v ...` com workspace e harness por task. **Status: clear.** Concretiza as Key decisions 3 e 4.

| State | What should happen | Caller sees |
|---|---|---|
| entrada obrigatória ausente ou de tipo errado | recusa antes do task dir | `2` |
| `--input` que o manifesto não declara | recusa | `2` |
| plugin inexistente | recusa | `2`, com `plugin list` na mensagem |
| `--plugin` com `--prompt-file` ou prompt em `extras` | recusa: o prompt é do plugin | `2` |
| `--cwd` com `--plugin` que tem entrada `repo` | recusa: o workspace é o clone | `2` |
| PR ou branch inexistente, ou `gh` sem login | task dir criado, agente não lançado | evento `error`/`failed`, motivo no `summary` |
| clone pronto | `cwd` do agente é o clone; prompt montado com as entradas; harness do plugin montado no task dir | — |
| agente tenta escrever fora do task dir ou rodar comando fora da lista | negado pela CLI; a tarefa segue | nada (não vira `needs_input`) |
| `meta.json` da tarefa | grava plugin, versão, origem e capacidades em vigor | — |

Alternatives considered: o agente clonar o repo sozinho - ganha se o workspace não precisasse ser o `cwd`, mas aí as instruções do repo não carregariam e a Key decision 3 dependeria do agente.

### `result`

**Delivers** o resultado estruturado no evento. **Status: clear.** Concretiza a Key decision 5.

| State | What should happen | Caller sees |
|---|---|---|
| resultado válido | `event` `completed`, `status` `ok`; `result` no evento; `summary` = campo `summary` do resultado, se houver | routine recebe `result` |
| resultado ausente, não é objeto JSON, sem campo obrigatório ou acima de `max_bytes` | `error`/`failed`, `exit_reason` `result_invalid` | motivo no `summary` |
| tarefa sem plugin | `plugin` e `result` são `null` | igual a hoje |

Schema `grokbot-kit.event/v1`, mudança aditiva: `plugin` (`object|null`: `name`, `version`, `source`); `result` (`object|null`); `exit_reason` ganha `result_invalid`.

### `code-review`

**Delivers** o plugin próprio de review de PR, escrito para ser o exemplo do guia. **Status: open.**

Entradas: `pr` (`repo`, URL do PR). Capacidades: `write: task-dir`, `network: on`, `commands` com leitura do PR, `gh pr review`/comentário, `git` só de leitura (`log`, `diff`, `show`, `blame`; AD-039) e os executores de teste. Resultado obrigatório: `summary`, `verdict` (`approve` | `comment` | `request_changes`), `findings` (lista com severidade, arquivo, linha, mensagem), `review_url`.

| State | What should happen | Caller sees |
|---|---|---|
| primeiro review do PR | review completo postado no PR pelo `gh` do box | `result` com `review_url` |
| re-review depois de push novo | lê os próprios reviews anteriores no PR e foca nos commits novos; sem estado no kit | `result` só com achados novos ou ainda abertos |
| PR sem mudança de código (só docs, lockfile) | review curto, sem achado inventado | `verdict` `comment` |
| PR fechado ou mergeado | não posta | `error`/`failed`, motivo no `summary` |
| instrução do PR mandando aprovar, dar push ou ignorar regras | ignorada; o plugin trata o conteúdo do PR como dado | — |

1. O review posta como `approve`/`request_changes` ou sempre `comment`? - default: sempre `comment` no GitHub; o `verdict` vai só ao bot, para o review não destravar merge sozinho.
2. Comentários inline ou um único review consolidado? - default: um review consolidado com comentários inline, como a skill `revisar-pr` do repo faz.

### `bug-verify`

**Delivers** o plugin próprio que verifica um alerta de erro contra o código. **Status: open.**

Entradas: `repo` (`repo`, URL de branch), `alert` (`text` ou `file`, o alerta como o bot recebeu). Capacidades: `write: task-dir`, `network: off` se o spike permitir, `commands` com `git` só de leitura e executores de teste. Resultado obrigatório: `summary`, `reproduced` (`yes` | `no` | `unknown`), `suspects` (arquivo, linha, motivo), `next_step`.

| State | What should happen | Caller sees |
|---|---|---|
| alerta reproduzido por teste | grava o teste no clone e cita o comando | `reproduced` `yes` |
| causa localizada sem reproduzir | aponta suspeitos com evidência | `reproduced` `unknown` |
| alerta sem stack trace nem mensagem utilizável | não chuta | `reproduced` `unknown`, `next_step` pedindo o dado que falta |

1. O plugin abre issue ou PR com a correção? - default: não; só verifica e devolve ao bot, que decide.

### Skill e guia

**Delivers** a skill do bot sabendo usar plugins e o guia de autoria. **Status: clear.**

| State | What should happen | Caller sees |
|---|---|---|
| usuário pergunta o que o kit sabe fazer | a skill roda `plugin list --json` e mostra plugins e capacidades | lista no chat |
| tarefa que casa com um plugin | a skill usa `run --plugin` com as entradas, sem escrever prompt | — |
| usuário pede para instalar um plugin | a skill roda `plugin show` da origem, mostra as capacidades, pergunta e só então `plugin add --yes` | pergunta de confirmação |
| quem escreve plugin | guia em `docs/` com manifesto, vocabulário, tabela de força por CLI, resultado, e o `code-review` comentado como exemplo; aviso de instabilidade até a 1.0 | — |

## Sources

- `docs/.specs/STATE.md` - AD-005, AD-006, AD-008, AD-009, AD-010, AD-028, AD-033 e o erro aberto do sandbox do Codex no box.
- Claude Code 2.1.307 `--help` - `--plugin-dir`, `--setting-sources`, `--allowedTools`, `--restricted`, `--add-dir`.
- codex-cli 0.163.0 `exec --help` e `codex-rs/config` (`sandbox_workspace_write.writable_roots`, `network_access`).
- opencode docs: permissions (`edit`, `bash`, `external_directory`) e skills (locais de descoberta) - https://opencode.ai/docs/permissions, https://opencode.ai/docs/skills
