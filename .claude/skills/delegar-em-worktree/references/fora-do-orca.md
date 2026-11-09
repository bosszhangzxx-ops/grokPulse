# Rota B — fora do Orca (e fallback de qualquer falha do Orca)

Aqui **não há delegação**: a própria sessão entra na worktree e executa a tarefa. Use quando
`TERM_PROGRAM`/`ORCA_WORKTREE_ID` não indicarem Orca, ou quando qualquer passo da Rota A falhar
(CLI ausente, `ok: false`, handle que não volta) — nesse caso, **não insista e não repita a
chamada do Orca**: caia aqui e avise o usuário que a sessão ficou no card do clone principal.

## 1. Criar worktree e branch de uma vez

```bash
git worktree add <pai-do-repo>/worktrees/<NOME_WT> -b <BRANCH> <BASE>
```

- `<NOME_WT>` = nome do diretório, **sem barras** (`US-243-slug`).
- `<BRANCH>` = padrão do projeto, tipicamente com barras (`bugfix/US-243/slug`).
- `<BASE>` = detectada ou perguntada. **Nunca assumir**: varia por repo *e* por tipo de trabalho
  (feature de um repo sai de `staging`, bugfix de produção sai de `main`, outro repo é `master`).
- A base de worktrees é **irmã do repo**, per-repo — nunca um diretório global único.

## 2. Mover a sessão de verdade

Chame a ferramenta **`EnterWorktree`** com `path` apontando para a worktree recém-criada
(relativo ao clone principal ou absoluto; ela já aparece no `git worktree list`, que é requisito
da ferramenta):

```
EnterWorktree(path="../worktrees/US-243-slug")
```

⚠️ **Só isso troca o diretório de trabalho da sessão** e faz a barra de status mostrar a branch da
worktree. Não basta `cd` dentro de um comando Bash — roda em subshell, a sessão não se move, a
barra continua na branch base e as edições caem onde ninguém está olhando.

Confirme que a barra/CWD refletem a worktree **antes da primeira edição**. Daí em diante todo
caminho de arquivo, docker e git é relativo a ela.

## 3. Setup

```bash
~/.claude/skills/delegar-em-worktree/scripts/setup-worktree.sh <repo> <worktree>
```

## 4. Encerrar

```
ExitWorktree(action="keep")
```

Preserva o trabalho e devolve o CWD/barra para o clone principal. Anuncie ao usuário que a sessão
voltou para o clone principal — a partir daí ele é território compartilhado de novo.

## Delegar sem Orca?

É possível abrir um agente na worktree com `Agent(...)` (subagente, mesma sessão) ou um terminal
externo, mas **nenhum dos dois dá card, aba própria nem sessão visível** — a rastreabilidade que
justifica a Rota A. Fora do Orca, o padrão é a própria sessão entrar e trabalhar.
