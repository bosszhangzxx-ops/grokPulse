# Por que cada invariante existe

Não são preferências de organização: cada um saiu de um incidente medido. Reabrir qualquer um
deles custa o mesmo incidente de novo.

## 1. Worktree dedicada — incidente de 14/07/2026

Uma story foi desenvolvida no clone principal e, no meio da sessão, edições **não versionadas de
outro trabalho em andamento** apareceram no mesmo working tree. Foi preciso separar hunks à mão
(`git apply --cached` de um patch filtrado) para não varrer trabalho alheio para dentro do commit
— e ainda assim commits de outra frente entraram na branch da feature.

Worktree dedicada elimina a classe inteira do problema: o clone principal fica limpo e reservado
ao usuário.

## 2. A barra de status não pode mentir — 16/07/2026

Criar a worktree com `git worktree add` **não move a sessão**. A barra continuava mostrando a
branch base enquanto as edições caíam em outro lugar (ou o contrário), e ninguém percebia até o
commit. `cd` dentro de um comando Bash roda em subshell e não conta.

`EnterWorktree` é a única coisa que troca o diretório da sessão. E trabalho **deliberado** no
clone principal tem que ser anunciado, justamente porque é a exceção arriscada.

## 3. Quem cria a worktree decide o que a UI mostra — 16/09/2026

Medido com os dois cards lado a lado:

| rota | card na barra lateral | linha da sessão do agente |
|---|---|---|
| `orca worktree create --agent claude` | sim | **sim** |
| `git worktree add` (entra como *discovered*) | só com `Show in worktree list` ligado | **não** |

Sem a linha da sessão, ninguém sabe que existe um agente trabalhando ali — que é o ponto inteiro
da delegação.

## 4. O `.claude/` corre contra o boot — 17/09/2026

`git worktree add` e `orca worktree create` trazem só o versionado; `.claude/` (skills, commands,
settings locais) e `CLAUDE.local.md` são gitignored. Com `--agent`, o terminal nasce junto com a
worktree, então a cópia corre contra o boot — e o registro de skills do Claude Code **só carrega
no boot**. O primeiro prompt voltou `Error: Unknown skill: bmad-dev-story`.

Copiar depois não conserta a sessão de pé. O que conserta sem reiniciar nada é o prompt de
passagem mandar ler `.claude/skills/<skill>/SKILL.md` na mão.

## 5. Reexecutar o `create` para recuperar o handle — 17/09/2026

O comando é aceito de novo e deixa uma worktree e uma aba duplicadas e órfãs, que alguém tem que
remover à mão. O handle se recupera com `orca terminal list --worktree "path:<path>" --json`,
que é a fonte de verdade inclusive quando o handle devolvido pelo `create` não bate com o que
está de pé.
