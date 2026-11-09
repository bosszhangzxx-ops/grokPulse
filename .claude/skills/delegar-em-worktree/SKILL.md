---
name: delegar-em-worktree
description: |
  Cria a git worktree dedicada de uma tarefa e PASSA a execução para um agente que nasce
  dentro dela — no Orca, com card e painel próprios; fora do Orca, movendo a sessão atual
  com EnterWorktree. Agnóstica de projeto: descobre base branch, padrão de nome de branch e
  arquivos gitignored a copiar, ou lê `.claude/worktree-handoff.json`.
  Use quando o usuário disser "vou começar a story/task X", "cria a worktree", "delega essa
  tarefa pra um agente", "abre um painel pro US-243", "passa isso pra outra sessão",
  "handoff", "manda pro Orca", "spawna um claude nessa worktree" — e sempre que um workflow
  (BMAD dev-story, guardião de dev flow, squad) exigir worktree dedicada antes da primeira
  edição de código.
  NÃO use para trabalho deliberadamente no clone principal, nem para operações do Orca que
  não envolvem worktree de tarefa (isso é a skill `orca-cli`).
---

# Delegar em worktree

Transforma "vou mexer nessa tarefa" em **um checkout isolado com um agente trabalhando dentro
dele**, sem que o clone principal seja tocado e sem que a barra de status minta sobre onde as
edições caem.

## Os 3 invariantes

1. **Toda tarefa edita numa worktree dedicada.** O clone principal é território compartilhado:
   edições não versionadas de outra frente aparecem no mesmo working tree e entram no commit
   errado (incidente medido — ver `references/por-que.md`).
2. **A barra de status nunca mente.** O diretório da sessão tem que refletir onde as edições
   caem. `cd` dentro de um comando Bash roda em subshell e **não** move a sessão.
3. **Quem cria a worktree decide o que a UI mostra.** Dentro do Orca, quem cria é o Orca —
   worktree criada por fora entra como *discovered* e o card **não** lista a sessão do agente.

## Passo 0 — Contexto (sempre, antes de qualquer coisa)

```bash
~/.claude/skills/delegar-em-worktree/scripts/detectar-contexto.sh
```

Ele imprime: repo e seu pai, se a sessão está dentro do Orca, a base de worktrees, candidatos
a base branch, o regex de branch do hook `pre-push` (quando existe), os arquivos gitignored do
topo do repo (candidatos a cópia) e o `.claude/worktree-handoff.json` do projeto, se houver.

**Nunca assumir** base branch nem padrão de nome. Se a detecção for ambígua, perguntar ao
usuário em uma linha e seguir. Schema do arquivo de config e regras de detecção:
`references/config-projeto.md`.

Parâmetros da execução (preencha antes de decidir a rota):

| parâmetro | de onde vem | exemplo |
|---|---|---|
| `ID` | o pedido do usuário / o workflow que chamou | `US-243`, `CSEVO-2263`, `ISSUE-77` |
| `SLUG` | resumo em kebab-case do que será feito | `fatura-classificada-errada` |
| `BASE` | config ou detecção — **nunca** assumir | `staging`, `main`, `master` |
| `BRANCH` | padrão do projeto, tipicamente `tipo/<ID>/<SLUG>` | `bugfix/US-243/fatura-...` |
| `NOME_WT` | nome do diretório, **sem barras** | `US-243-fatura-...` |
| `TAREFA` | o que o agente filho vai executar | `skill bmad-dev-story com docs/.../US-243.md` |

## Rota

| situação | rota |
|---|---|
| `TERM_PROGRAM=Orca` **e** `ORCA_WORKTREE_ID` presentes, sessão ainda no clone principal | **A — Orca** (delega) |
| Os dois presentes e a sessão **já está** na worktree da tarefa | gate cumprido: seguir a tarefa aqui, sem nova passagem |
| Qualquer outro terminal, **ou** qualquer falha do Orca | **B — fallback** (a sessão atual entra) |

---

## Rota A — dentro do Orca (delegação)

Detalhes, flags e saídas em `references/orca.md`. **Resolva o executável do Orca** conforme a
skill `orca-cli` antes do primeiro comando — em Linux, fora de um terminal do Orca, `orca` nu
é o leitor de tela do GNOME e começa a falar na máquina do usuário.

1. **Pré-requisito, uma vez por projeto:** a base de worktrees do Orca tem que ser o diretório
   `worktrees` irmão do repo (`orca project setups --json` → `worktreeBasePath`; ajustar com
   `orca project setup-update`). ⚠️ O Orca **sempre** aninha o nome do repo sob a base, então o
   caminho final é `<base>/<nome-do-repo>/<NOME_WT>` — e é assim mesmo: `git worktree move`
   para o caminho plano **órfã** o registro (o id do Orca é `<repoId>::<path>`).
2. **Criar a worktree já com o agente** (~2s), guardando `result.worktree.path` e
   `result.agentTerminalHandle`:
   ```
   orca worktree create --name "<NOME_WT>" --repo "path:<repo>" --base-branch <BASE> \
     --no-parent --setup skip --comment "<contexto curto>" --agent claude --activate --json
   ```
   É o `--agent` que faz nascer **uma** aba com a sessão adotada nativamente — o que faz o card
   exibir a linha da sessão.
   ⚠️ **Handle perdido NUNCA se recupera reexecutando o `create`** — o comando é aceito de novo
   e deixa uma worktree/aba duplicada e órfã para alguém remover à mão. A fonte de verdade é
   `orca terminal list --worktree "path:<path>" --json`.
3. **Corrigir a branch**, que o Orca nomeia igual ao `--name`:
   `git -C <path> branch -m <NOME_WT> <BRANCH>`. O Orca acompanha (com um instante de atraso —
   reconsultar antes de tratar como erro) e o rótulo do card não muda (é o `displayName`).
4. **Setup da worktree, imediatamente** (ver seção abaixo). A criação só traz o versionado.
5. **Entregar a tarefa** na sessão que já está de pé:
   ```
   orca terminal send --terminal <handle> --text "<prompt de passagem>" --enter --wait-submit 30 --json
   ```
   Texto **sem aspas de nenhum tipo**. Modelo do prompt em `references/orca.md` — ele precisa
   dizer o que já foi feito (branch, worktree, setup, gates) para o filho **não refazer**, e
   carregar o fallback de skill do item 6.
6. ⚠️ **A cópia do `.claude/` corre contra o boot do agente.** O registro de skills do Claude
   Code só carrega no boot, então copiar depois não conserta a sessão de pé (medido: o primeiro
   prompt volta `Error: Unknown skill: <nome>`). Não tente ganhar a corrida: **mande o fallback
   dentro do próprio prompt** — "se a skill X não for encontrada, leia e siga
   `.claude/skills/X/SKILL.md` na mão, é o mesmo workflow".
7. **Confirmar** com `orca terminal read --terminal <handle> --json`: tem que aparecer o
   cabeçalho do agente com o **caminho da worktree** e a resposta ao prompt. ⚠️ Não usar o
   `satisfied` de `orca terminal wait --for tui-idle` como prova — volta `None` com a sessão de
   pé; o `wait` serve só para dar tempo ao boot.
8. **Anunciar e PARAR.** Diga ao usuário o card, a aba e que a tarefa seguiu por lá. Esta sessão
   **não edita mais nada** da tarefa — duas sessões no mesmo checkout recriam o problema que a
   worktree existe para eliminar.

⚠️ **Nunca** passe o nome nu de um agente (`claude`, `codex`) em `orca terminal create --command`
e **nunca** use `--focus`: as duas formas estouram em ~10s com `ok: false` sem criar terminal
nenhum (determinístico). Aba extra numa worktree existente vai embrulhada em shell + `orca
terminal switch` — receita em `references/orca.md`.

**Falha em qualquer passo do Orca** (CLI ausente, `ok: false`, handle que não volta) ⇒ não
insistir, não repetir a chamada: cair na Rota B e avisar o usuário que a sessão ficou no card do
clone principal.

---

## Rota B — fora do Orca, ou fallback

```bash
git worktree add <base>/<NOME_WT> -b <BRANCH> <BASE>
```

Depois, **a única coisa que move a sessão**: chamar a ferramenta `EnterWorktree` com `path`
apontando para a worktree recém-criada (relativo ao clone principal ou absoluto; ela já está no
`git worktree list`, requisito da ferramenta). Confirmar que a barra/CWD passaram a mostrar a
branch da tarefa **antes da primeira edição**. Rodar o setup. Ao encerrar,
`ExitWorktree(action="keep")`.

Aqui **não há delegação**: quem executa a tarefa é a própria sessão. Detalhes em
`references/fora-do-orca.md`.

---

## Setup da worktree (as duas rotas)

`git worktree add` / `orca worktree create` trazem **só o versionado**. Sem os arquivos
gitignored, containers e testes não sobem e a sessão filha não acha as skills:

```bash
~/.claude/skills/delegar-em-worktree/scripts/setup-worktree.sh <repo> <worktree>
```

Copia o que a config/detecção indicar (tipicamente `.env`, `.claude/`, `CLAUDE.local.md`,
credenciais) e cria os diretórios exigidos por volume mount (tipicamente `logs/`). É
idempotente e imprime o que fez. Na Rota A, rode **logo após o create** — antes do `terminal
send`, mesmo sabendo que pode perder a corrida com o boot (item 6).

## Trabalho excepcional no clone principal

Só estar no clone principal quando o trabalho for **deliberadamente** nele (ex.: artefatos de
processo versionados direto na branch base). Nesse caso torne isso **visível**: se veio de uma
worktree, `ExitWorktree(action="keep")` e **avise o usuário** que agora está no clone principal —
território compartilhado, onde a colisão com outra frente é o cenário normal, não o excepcional.

## Armadilhas medidas

| sintoma | causa | o que fazer |
|---|---|---|
| Card no Orca sem linha de sessão | worktree criada por `git worktree add` (vira *discovered*) | criar com `orca worktree create --agent` |
| `Timed out waiting for terminal handle after creation` (~10s) | nome nu de agente em `--command`, ou `--focus` | embrulhar em `zsh -lc` + `orca terminal switch` |
| Worktree/aba duplicada e órfã | reexecutar `worktree create` para recuperar handle | `orca terminal list --worktree "path:<path>" --json` |
| `Error: Unknown skill: X` no filho | `.claude/` copiado depois do boot | fallback "leia `.claude/skills/X/SKILL.md`" no prompt |
| Card aponta para caminho velho, worktree nova some | `git worktree move` sobre worktree do Orca | não mover; aceitar `<base>/<repo>/<nome>` |
| Barra de status na branch base enquanto edita a worktree | `cd` em comando Bash | `EnterWorktree` |
| Falar na máquina do usuário | `orca` nu em Linux fora do Orca (GNOME Orca) | resolver o executável pela skill `orca-cli` |

## Referências

- `references/orca.md` — comandos, flags, prompt de passagem, recuperação de handle, aba extra
- `references/fora-do-orca.md` — rota B e o contrato de `EnterWorktree`/`ExitWorktree`
- `references/config-projeto.md` — `.claude/worktree-handoff.json` e as regras de detecção
- `references/por-que.md` — os incidentes que produziram cada invariante
