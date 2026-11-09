# Rota A — mecânica do Orca

Tudo aqui foi medido com o app 1.4.201 / CLI 1.4.204 (16–17/09/2026). Onde houver divergência,
`--help` do executável resolvido manda.

## 0. Resolver o executável

Siga a skill `orca-cli`. Resumo do que não pode dar errado:

- `ORCA_CLI_COMMAND` setado ⇒ use o valor dele.
- Checkout de dev com `ORCA_DEV_REPO_ROOT` ⇒ `orca-dev`.
- **Linux, fora de um terminal do Orca ⇒ `orca-ide`.** Nunca `orca` nu: resolve para
  `/usr/bin/orca`, o leitor de tela do GNOME, e começa a falar na máquina do usuário.
- Caso contrário ⇒ `orca`.

Abaixo, `ORCA` é o executável já resolvido — substitua no texto, não crie variável de shell.
Prefira `--json` em tudo. Se algum comando disser que o Orca não está rodando: `ORCA open --json`
e repetir.

## 1. Detecção de ambiente

```bash
echo "$TERM_PROGRAM $ORCA_WORKTREE_ID"
```

Os **dois** presentes (`Orca` e um id) = sessão dentro do Orca. O trecho depois de `::` no
`ORCA_WORKTREE_ID` é o caminho da worktree da sessão: se já for a worktree da tarefa (e
`git branch --show-current` der a branch da tarefa), **o gate já está cumprido** — é a sessão que
recebeu a passagem. Seguir a tarefa, sem criar nada.

## 2. Pré-requisito por projeto — base de worktrees

```bash
ORCA project setups --json          # ler worktreeBasePath do setup do repo
ORCA project setup-update --setup <id> --worktree-base-path <pai-do-repo>/worktrees --json
```

⚠️ O caminho final **sempre** ganha o nível do repo: `<base>/<nome-do-repo>/<NOME_WT>`. Um nível
a mais que worktrees criadas à mão, e é assim mesmo — o id do Orca é `<repoId>::<path>`, então
`git worktree move` para o caminho plano deixa o card apontando para o caminho velho e a worktree
nova simplesmente some da UI.

## 3. Criar worktree + agente (uma chamada)

```bash
ORCA worktree create \
  --name "<NOME_WT>" \
  --repo "path:<caminho-do-repo>" \
  --base-branch <BASE> \
  --no-parent \
  --setup skip \
  --comment "<contexto curto: o que é a tarefa>" \
  --agent claude \
  --activate \
  --json
```

Guarde do resultado:

- `result.worktree.path` — onde a worktree nasceu
- `result.agentTerminalHandle` — o handle para falar com a sessão

Por que `--agent` e não `terminal create` depois: só assim a sessão é **adotada nativamente** e o
card passa a exibir a linha da sessão, como o card do clone principal.

⚠️ **Handle perdido não se recupera reexecutando este comando.** Ele é aceito de novo e deixa uma
worktree e uma aba duplicadas e órfãs (aconteceu, 17/09/2026). Fonte de verdade:

```bash
ORCA terminal list --worktree "path:<path>" --json
```

— inclusive quando o handle devolvido pelo `create` não bate com o que está de pé.

## 4. Renomear a branch

O Orca nomeia a branch igual ao `--name`; o padrão do repo quase sempre é outro:

```bash
git -C <path> branch -m <NOME_WT> <BRANCH>
```

O Orca acompanha (o `worktree show` passa a reportar a branch nova) e o rótulo do card **não**
muda — é o `displayName`, fixo no `--name`. O registro pode levar um instante para refletir o
rename: reconsultar antes de tratar como erro. Se o projeto tiver validador de nome de branch
(hook, script), rode-o aqui.

## 5. Prompt de passagem

```bash
ORCA terminal send --terminal <handle> \
  --text "<prompt>" \
  --enter --wait-submit 30 --json
```

⚠️ O texto vai **sem aspas de nenhum tipo** — nem simples, nem duplas, nem crase.

Molde (adapte; o que está entre `<>` sai do que **de fato** aconteceu nesta sessão, nunca desta
página):

> Execute `<a tarefa: skill X com o arquivo Y, relativo à worktree>`. Passagem de worktree:
> `<gates já cumpridos e por quem>`, branch `<BRANCH>` e worktree `<path>` já criadas, com
> `<arquivos copiados>` já no lugar. NÃO refaça os gates nem crie outra worktree/branch — você já
> está nela. Se a skill `X` não for encontrada, leia e siga `.claude/skills/X/SKILL.md` na mão: é
> o mesmo workflow.

Três coisas que o prompt precisa carregar, sempre:

1. **O caminho da tarefa relativo à worktree** (não ao clone principal).
2. **O que já foi feito**, para o filho não refazer gate nem criar worktree dentro de worktree.
3. **O fallback de skill** — o registro de skills só carrega no boot, e a cópia do `.claude/`
   pode ter chegado tarde.

## 6. Confirmar

```bash
ORCA terminal read --terminal <handle> --json
```

Tem que aparecer o cabeçalho do agente **com o caminho da worktree** e a resposta ao prompt.

⚠️ `ORCA terminal wait --for tui-idle` devolve `satisfied: None` mesmo com a sessão de pé — serve
só para dar tempo ao boot, **nunca** como prova de que a passagem funcionou.

## 7. Aba extra numa worktree que já existe (caminho de exceção)

⚠️ `ORCA terminal create --command claude` (nome nu de agente) **ou** qualquer uso de `--focus`
estoura em ~10s com `ok: false` / `Timed out waiting for terminal handle after creation`, sem
criar terminal nenhum. Determinístico. Embrulhe em shell:

```bash
ORCA terminal create --worktree "path:<path>" \
  --command 'zsh -lc "exec claude \"<prompt>\""' --json
ORCA terminal switch --terminal <handle> --json    # substituto do --focus quebrado
```

Cria em ~0,2s e o painel é reconhecido como Claude (`terminal show` → `agentIdentity: claude`),
mas ⚠️ a sessão criada assim **não** vira linha de sessão no card — por isso é exceção, e o
`--agent` do passo 3 é a regra.

Qualquer shell serve no embrulho: o ambiente vem do PTY que o Orca injeta, não dos rc files — e
⚠️ nem `zsh -lc` lê `~/.zshrc` (login não-interativo lê só `.zshenv`/`.zprofile`), então não conte
com export feito lá.

## 8. Encerrar a sessão-pai

Anuncie card, aba e que a tarefa seguiu por lá; **pare**. Esta sessão não edita mais nada da
tarefa. O usuário fecha a aba do clone principal quando quiser.

Por que sessão **nova** e não `claude --resume`: o histórico é guardado por diretório, então
retomar a partir da worktree não é confiável — e o arquivo/descrição da tarefa já carrega o
contexto que importa.
