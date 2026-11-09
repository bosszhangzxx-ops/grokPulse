# sdlc-gates

**Approved**: 2026-10-29

## Problem

As regras do fluxo de desenvolvimento do repositório existem só como texto (`CLAUDE.md`, `CONTRIBUTING.md`, skills), e
quem as cumpre é o agente que lembra delas. Hoje:

- o `pre-commit` não está instalado no clone (`.git/hooks` sem hook nenhum, e as worktrees usam o mesmo diretório),
  então ruff e mypy só rodam no CI;
- nada confere Conventional Commits, título do PR (que vira a mensagem do squash), padrão de branch, nem a ausência de
  `Co-Authored-By` — o próprio harness do Claude Code injeta a linha a cada sessão e só o `CLAUDE.md` a barra;
- nenhum validador do `tlc-spec-lean` roda no CI: um PR que muda `src/` entra sem plano, checks ou `verification.md`;
- as aprovações humanas (push, PR, merge, tag) não têm mecanismo: o agente pede ok a cada push e, ao mesmo tempo, nada
  o impede de fazer merge ou tag com o `gh` do Rodrigo;
- o `<id>` da branch não tem origem (`S3`, `update`, `plugins`, `model-setup`), as pendências moram no `Next step` do
  `STATE.md`, e o `## Handoff` virou um diário de 37 KB que fica velho a cada PR (corrigido à mão no PR 28);
- qual skill usar para qual trabalho, a raiz dos specs (`docs`, passada à mão como `--root docs`) e fatos do ambiente
  ("box só pelo bot", "opencode-go no box") estão espalhados ou só na memória local de um agente;
- as instruções do projeto estão em dois arquivos: o `CLAUDE.md` tem as regras e o `AGENTS.md` só aponta para ele, então
  Codex e opencode recebem um ponteiro em vez das regras;
- a regra de doc cobre só os subcomandos de topo e a existência dos pares: das 28 flags do `grokbot-kit`, 8 não aparecem
  nos docs nas duas línguas (`--version`, `emit --from`, `login --secret`, `route add --header`, `run --prompt-file`,
  `run --timeout`, `run --tool`, `setup models refresh --add`), e dos 26 campos do evento `grokbot-kit.event/v1`, 16 não
  aparecem (`event`, `status`, `task_id`, `exit_code`, `resume_hint`, `output_file` e outros); nada cobra o
  `CHANGELOG.md`, o par alterado no mesmo PR, nem o critério de doc no plano.

Quem paga é o Rodrigo: cada passo pede a presença dele para lembrar a regra ou dar o ok, e o que escapa (commit fora do
padrão, PR sem verificação) só aparece depois do merge. Evidência: 30 PRs, só 2 com review; Verifier com 3, 5 e 8
rodadas nas últimas features; o `worktree-handoff.json` aponta `handoff_skill: tlc-implement` enquanto o fluxo real é
`tlc-spec-lean`.

Depois desta feature, um agente segue o fluxo sozinho do issue ao PR aberto: as regras falham cedo e por máquina (hook
local e job `process` no CI), e só três passos esperam o Rodrigo — aprovar o plano, fazer o merge e criar a tag.

## Flow

Reusa os validadores do `tlc-spec-lean` (`.claude/skills/tlc-spec-lean/scripts/`), o `pre-commit` já declarado em
`pyproject.toml` e o padrão de hook do `gate-worktree.sh`; nada disso é reescrito.

1. commit local -> `pre-commit` (exists) roda os hooks de hoje e os hooks locais novos, que chamam `tools/sdlc.py`
   (door 1): `pre-commit` (main e clone principal), `commit-msg` (door 3) e, no push, `branch` (door 2)
2. sessão do Claude Code começa -> `.claude/settings.json` (exists) ganha um hook de início de sessão, que instala os hooks git se faltarem
3. comando Bash do agente -> regras de permissão do `.claude/settings.json` (door 6, AD-053): o Claude Code pede confirmação para merge, tag, release e proteção; o push para `main` é recusado pelo hook `pre-push` e pela proteção da `main` no GitHub
4. PR para `main` -> `.github/workflows/ci.yml` (exists) ganha o job `process` (door 4), que roda `tools/sdlc.py pr`:
   título, branch, commits, link do issue (door 7), validadores das features tocadas e o marcador de aprovação (door 5)
5. out: o check `process` entra no `main-protection.json` (exists) como o 6º obrigatório; o Rodrigo aplica o payload no
   GitHub
6. regras para o leitor -> `AGENTS.md` (exists) passa a ser o único arquivo de instruções do projeto (door 8), lido pelo
   Claude Code (2.1.277 ou mais novo) e pelas outras CLIs; o `CLAUDE.md` sai; `CONTRIBUTING.md` e o par em
   `docs/pt-BR/` descrevem os gates
7. doc -> `tests/test_docs.py` (exists) passa a cobrar flags, campos do evento e links; `tools/sdlc.py pr` cobra par no
   mesmo PR, `CHANGELOG.md` e doc (ou `Docs: n/a`, door 9) em PR `feat`/`fix`; `tools/sdlc.py spec` cobra o critério de
   doc no plano

## Impact

| Front | What changes |
| --- | --- |
| domain | termo novo: `process` — o job de CI e o check obrigatório que valida o processo de um PR |
| domain | termo existente: `<id>` da branch era livre, passa a ser o número do issue (door 2) — usam o padrão hoje `CLAUDE.md`, `CONTRIBUTING.md` (EN e pt-BR), `.claude/worktree-handoff.json` e a skill `delegar-em-worktree` (lê o `branch_pattern` do json) |
| domain | termo existente: `## Handoff` do `STATE.md` era o histórico das features, passa a ser só o estado atual (até 40 linhas); o histórico fica no git, nos PRs e nos `verification.md` |
| tests | `test_repo_settings_payloads_match_door_11` (C21 da agent-run-notify) compara o `main-protection.json` literal: ganha `process`, por decisão nova que supera a forma da door 11 |
| tests | `test_precommit_hooks` exige o mesmo `exclude` em todo hook: os hooks locais novos levam o mesmo `exclude` |
| tests | `test_ci_jobs_and_triggers` (C13 da agent-run-notify) lista os jobs do `ci.yml`: ganha `process`, pela door 4 (achado no build) |
| tests | `test_mypy_strict_config` (C11 da agent-run-notify) compara `[tool.mypy] files`: passa a `["src", "tools"]`, pela linha de tooling abaixo (achado no build) |
| instruções | o `CLAUDE.md` some: o conteúdo vai para o `AGENTS.md`. Leem o `CLAUDE.md` hoje: o Claude Code (passa a ler o `AGENTS.md` quando não há `CLAUDE.md` nem `CLAUDE.local.md`), `test_claude_md_doc_rule` (C48 da model-setup-docs), `DOOR_10_FILES` em `test_repo_files.py` (door 10 da agent-run-notify), `CONTRIBUTING.md` (EN e pt-BR) e o `copy` do `worktree-handoff.json` (`CLAUDE.local.md`); `detectar-contexto.sh` e o `gate-worktree.sh` já aceitam os dois nomes |
| instruções | um `CLAUDE.local.md` local (gitignored) faz o Claude Code parar de ler o `AGENTS.md` para quem o tiver |
| docs | flags e campos do evento hoje sem doc passam a ser documentados nesta feature (AC 36-37) |
| hooks | o `commit-msg` do git roda também em `git merge` e `git pull` (githooks(5)): a mensagem automática de merge fica fora da door 3 (AC 46, achado no review do PR #34); o `pr` do CI já ignora merge commits (`--no-merges`) |
| hooks | AD-053: o `gate-humano.sh` (um parser de shell em bash, 8 rodadas do Verifier sem convergir e pedidos de confirmação em texto que o bash não executa) sai; a door 6 passa a ser regras de permissão do Claude Code, e o push para `main` fica com o hook `pre-push` e a proteção da `main` no GitHub. As AC 20-23 são reescritas e as AC 44-45 e 47-59 saem |
| hooks | AD-054: `git tag` local (listar, criar) não pede confirmação; publicar a tag, por qualquer forma de `git push` (`--tags`, `--follow-tags`, `v*`, `refs/tags/`, `<src>:v*`, `:<tag>`, `+<tag>`, `--mirror`), pede. A AC 20 muda a lista |
| tooling | `[tool.mypy] files` ganha `tools`, então `tools/sdlc.py` roda em `mypy --strict` no job `typecheck` |
| stored data | nada a migrar; os planos já existentes não ganham `**Approved**` retroativo (a regra vale para `plan.md` adicionado ou alterado no PR) |

## Relations

None - no stored-data shape change

## Surface

None - nothing consumed outside the repository except the check name `process`, which branch protection binds to (door 4)

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. um ponto de entrada para as regras | `tools/sdlc.py` (stdlib, Python 3.11) com `commit-msg <arquivo>`, `branch <nome>`, `pre-commit`, `pr --title <t> --branch <b> --body-file <f> --base <sha>`, `spec <feature>` e `state`; exit `0` ok, `1` violação (mensagem em stderr), `2` uso | um shell por hook: três cópias das regex e nenhuma prova na própria camada; subcomando `grokbot-kit dev`: entregaria regra de processo do repositório a quem instala o kit pelo PyPI |
| 2. padrão de branch | `^(feat\|fix\|refactor\|perf\|test\|docs\|chore\|build\|ci)/[0-9]+/[a-z0-9][a-z0-9-]*$`, mais `^chore/release/[0-9]+\.[0-9]+\.[0-9]+$` e `^dependabot/` | `<id>` livre (o de hoje): não liga a branch a nada que o CI confira |
| 3. primeira linha do commit e título do PR | `^(feat\|fix\|refactor\|perf\|test\|docs\|chore\|build\|ci\|style\|revert)(\([a-z0-9._-]+\))?!?: \S.*$` com até 100 caracteres; nenhuma linha `Co-authored-by:` (sem diferenciar maiúsculas) | commitlint: dependência Node num repositório Python sem Node |
| 4. check obrigatório | job `process` em `ci.yml`, nome de status `process`, sexto item de `required_status_checks.checks` com `app_id` `15368` | checar no workflow de release: o erro apareceria depois do merge |
| 5. marcador de aprovação do plano | linha `**Approved**: AAAA-MM-DD` logo abaixo do título do `plan.md`, escrita só depois do ok do Rodrigo no chat | label no PR: o plano é aprovado antes de existir PR |
| 6. gates humanos do Claude Code | `permissions` no `.claude/settings.json`: `ask` para `Bash(gh pr merge *)`, `Bash(gh release *)`, `Bash(git push --tags *)`, `Bash(git push * --tags *)`, `Bash(git push * --follow-tags *)`, `Bash(git push --follow-tags *)`, `Bash(git push * v*)`, `Bash(git push * refs/tags/*)`, `Bash(git push *:refs/tags/*)`, `Bash(git push *:v*)`, `Bash(git push *--mirror*)`, `Bash(git push *+v*)`, `Bash(git push *+refs/tags/*)`, `Bash(gh api *protection*)`, `Bash(gh api *environments*)`, `Bash(gh api *merge*)`, `Bash(gh api *releases*)`; `allow` para `Bash(git push *)` e `Bash(gh pr create *)`; nenhum hook `PreToolUse` em `Bash`. O push para `main` é recusado pelo hook git `pre-push` (a door 2 não aceita `main`) e pela proteção da `main` no GitHub (`enforce_admins`, PR obrigatório). Reescrita pela AD-053; a AD-054 troca `Bash(git tag *)` pelas formas de refspec (`<src>:`, `:<tag>`, `+`), `--follow-tags` sem remoto e `--mirror` | `PreToolUse` em `Bash` com um parser de shell próprio (`gate-humano.sh`, a forma aprovada antes da AD-053): 8 rodadas do Verifier sem convergir e confirmação pedida em mensagem de commit; só permissões sem o `pre-push`: o `allow` de `git push *` também cobriria `main` |
| 7. ligação PR ↔ issue | corpo do PR com `Closes #N`, `Fixes #N` ou `Refs #N`, `N` igual ao `<id>` da branch | issue no título: o título é a mensagem do squash e fica em Conventional Commits |

| 8. um arquivo de instruções | só `AGENTS.md` na raiz; nenhum `CLAUDE.md`, `.claude/CLAUDE.md` ou `CLAUDE.local.md` versionado; o `~/.claude/CLAUDE.md` de cada pessoa continua valendo | `CLAUDE.md` com `@AGENTS.md`: dois arquivos, o que o Rodrigo pediu para acabar; symlink: quebra em checkout sem suporte a symlink e o Claude Code já lê o `AGENTS.md` sem ele |
| 9. escape de doc | linha `Docs: n/a - <razão>` no corpo do PR ou no `plan.md`, com razão não vazia | label `no-docs`: some do texto que o revisor lê e não carrega a razão |

- Nothing else in this change is hard to reverse

## Criteria

### S1: as regras de commit e branch falham no clone, antes do push (P1)

Um commit ou push fora do padrão é recusado localmente, com a regra impressa.

**Acceptance Criteria**

1. WHEN `uv run pre-commit install` roda THEN o repositório SHALL instalar os hooks `pre-commit`, `commit-msg` e `pre-push`, por `default_install_hook_types` no `.pre-commit-config.yaml`
2. IF a primeira linha da mensagem de commit não casa a regex da door 3 ou passa de 100 caracteres THEN `tools/sdlc.py commit-msg <arquivo>` SHALL sair com `1` e imprimir a regex em stderr
3. IF a mensagem de commit tem uma linha `Co-authored-by:` em qualquer caixa THEN `tools/sdlc.py commit-msg <arquivo>` SHALL sair com `1` e imprimir essa linha em stderr
4. WHEN a mensagem casa a door 3 e não tem `Co-authored-by:` THEN `tools/sdlc.py commit-msg <arquivo>` SHALL sair com `0` sem saída
5. IF o nome da branch não casa a door 2 THEN `tools/sdlc.py branch <nome>` SHALL sair com `1` e imprimir os padrões aceitos, e o hook `pre-push` SHALL recusar o push
6. IF um commit é feito com a branch atual `main` THEN `tools/sdlc.py pre-commit` SHALL sair com `1` com a mensagem `commit on main: create a <type>/<issue>/<slug> branch`
7. IF um commit é feito no clone principal (git-dir igual ao git-common-dir) com arquivo staged fora de `docs/`, `.specs/`, `.claude/`, `.agents/`, `CLAUDE.md` e `AGENTS.md` THEN `tools/sdlc.py pre-commit` SHALL sair com `1` e listar esses arquivos
8. WHERE `GROKBOT_KIT_ALLOW_MAIN_EDIT=1` está no ambiente the `tools/sdlc.py pre-commit` SHALL não aplicar a regra da AC 7
9. WHEN uma sessão do Claude Code começa e `.git/hooks/commit-msg` do repositório não existe THEN o hook `SessionStart` SHALL rodar `uv run pre-commit install` e devolver ao contexto uma linha com o resultado

**Independent test:** num clone de teste, `git commit -m "ajusta coisa"` é recusado e `git commit -m "fix(run): ajusta coisa"` passa.

### S2: o CI recusa um PR fora do processo (P1)

O job `process` reprova o PR que pulou uma regra, com o motivo no log.

**Acceptance Criteria**

10. WHEN um PR para `main` abre, muda de título ou corpo, ou recebe commit THEN o workflow `CI` SHALL rodar o job `process`
11. IF o título do PR não casa a door 3 THEN `tools/sdlc.py pr` SHALL sair com `1`
12. IF a branch do PR não casa a door 2 THEN `tools/sdlc.py pr` SHALL sair com `1`
13. IF algum commit entre `--base` e `HEAD`, ou o corpo do PR, tem linha `Co-authored-by:` THEN `tools/sdlc.py pr` SHALL sair com `1` e nomear o commit ou o corpo
14. IF o `<id>` da branch é o número `N` e o corpo do PR não tem `Closes #N`, `Fixes #N` nem `Refs #N` THEN `tools/sdlc.py pr` SHALL sair com `1`
15. WHEN o PR muda arquivo em `docs/.specs/features/<f>/` THEN `tools/sdlc.py pr` SHALL rodar `tools/sdlc.py spec <f>`, que roda com `--root docs` o `validate_plan.py` (se há `plan.md`), o `validate_checks.py` (se há `checks.md`) e o `validate_verification.py` (se há `verification.md`), e sair com `1` se algum sair diferente de `0`
16. IF o PR muda arquivo em `src/` ou `skills/` e não muda nenhum `docs/.specs/features/<f>/verification.md` THEN `tools/sdlc.py pr` SHALL sair com `1` com a mensagem `src/ or skills/ changed without a verification.md`
17. IF o PR adiciona ou altera um `plan.md` sem a linha `**Approved**: AAAA-MM-DD` da door 5 THEN `tools/sdlc.py pr` SHALL sair com `1`
18. IF o `## Handoff` do `docs/.specs/STATE.md` passa de 40 linhas THEN `tools/sdlc.py state` SHALL sair com `1`, e `tools/sdlc.py pr` SHALL rodá-lo
19. The `.github/repo-settings/main-protection.json` SHALL listar `process` com `app_id` `15368` entre os 6 checks obrigatórios

**Independent test:** `tools/sdlc.py pr` contra um repositório de teste com um commit `Co-authored-by:` sai com `1`; com o PR corrigido, `0`.

### S3: o agente faz push e abre PR sozinho, e para no merge e na tag (P1)

O Claude Code segue sem pedir ok até o PR aberto e pede confirmação nos passos que são do Rodrigo.

**Acceptance Criteria**

20. The `.claude/settings.json` SHALL ter em `permissions.ask` as regras `Bash(gh pr merge *)`, `Bash(gh release *)`, `Bash(git push --tags *)`, `Bash(git push * --tags *)`, `Bash(git push * --follow-tags *)`, `Bash(git push --follow-tags *)`, `Bash(git push * v*)`, `Bash(git push * refs/tags/*)`, `Bash(git push *:refs/tags/*)`, `Bash(git push *:v*)`, `Bash(git push *--mirror*)`, `Bash(git push *+v*)`, `Bash(git push *+refs/tags/*)`, `Bash(gh api *protection*)`, `Bash(gh api *environments*)`, `Bash(gh api *merge*)`, `Bash(gh api *releases*)`: o Claude Code pede confirmação quando qualquer trecho de um comando composto casa uma delas (AD-053)
21. IF um `git push` tem `main` como destino da primeira ref com commits THEN o hook git `pre-push` SHALL recusá-lo (o `pre-commit` só passa essa ref ao hook), e, para qualquer ref `main` do push, a proteção da `main` no GitHub (`enforce_admins`, PR obrigatório, sem force push nem deleção) SHALL rejeitá-lo
22. The `.claude/settings.json` SHALL ter em `permissions.allow` as regras `Bash(git push *)` e `Bash(gh pr create *)`, e nenhuma regra de `allow` SHALL casar `gh pr merge`, `git tag` ou `gh release`
23. The repositório SHALL não ter hook `PreToolUse` em `Bash` nem o `.claude/hooks/gate-humano.sh` (AD-053)

**Independent test:** `cd x && gh pr merge 34` pede confirmação no Claude Code; `git push origin main` num clone com os hooks é recusado pelo `pre-push`.

### S4: o backlog vive em GitHub Issues (P2)

Toda tarefa nasce de um issue e o fecha pelo PR.

**Acceptance Criteria**

24. The `.claude/worktree-handoff.json` SHALL ter `branch_pattern` `<tipo>/<issue>/<slug>` e `handoff_skill` `tlc-spec-lean`
25. WHEN esta feature entra em `main` THEN cada pendência do `Next step` do `STATE.md` (limites do webhook; sandbox do Codex no box) SHALL existir como issue aberto, e o `STATE.md` SHALL citá-la só pelo número

**Independent test:** `gh issue list` mostra as duas pendências, e o `STATE.md` não as descreve mais.

### S5: as regras do fluxo estão num lugar só (P2)

Um agente novo, de qualquer CLI, acha o fluxo inteiro lendo o `AGENTS.md`.

**Acceptance Criteria**

26. The `AGENTS.md` SHALL ter as seções `## Fluxo`, `## Autonomia`, `## Skills` e `## Ambiente`: o fluxo do issue ao merge, a tabela do que o agente faz sozinho e do que espera o Rodrigo (aprovar o plano, merge, tag), qual skill para qual trabalho (feature → `tlc-spec-lean`; ideia sem forma → `tlc-discover`; mudança de até 3 arquivos sem door → `checks.md` só com `## Intent`; deps, docs e release → sem spec), a raiz dos specs `docs` com `tools/sdlc.py spec <f>`, e os fatos do box (só pelo bot; modelos opencode-go)
27. The `AGENTS.md` SHALL ter as regras que hoje estão no `CLAUDE.md` (gate da worktree, skills do projeto, git), sem a tabela de autonomia repetida em outro arquivo
28. The `CONTRIBUTING.md` e o `docs/pt-BR/CONTRIBUTING.md` SHALL descrever os hooks locais, o job `process`, o padrão de branch com o número do issue e o `Closes #N`
29. The `## Handoff` do `STATE.md` SHALL ter até 40 linhas quando esta feature entra em `main`

**Independent test:** `tools/sdlc.py state` sai com `0`; o `test_docs.py` passa com o `CONTRIBUTING.md` novo.

### S6: um só arquivo de instruções, o padrão de mercado (P1)

Claude Code, Codex e opencode leem as mesmas regras, de um arquivo.

**Acceptance Criteria**

30. The repositório SHALL não ter `CLAUDE.md` nem `.claude/CLAUDE.md` versionados (door 8)
31. The `.claude/worktree-handoff.json` SHALL não listar `CLAUDE.local.md` em `copy`
32. WHEN uma sessão do Claude Code começa e existe `CLAUDE.md` ou `CLAUDE.local.md` na raiz do repositório THEN o hook de início de sessão da AC 9 SHALL devolver ao contexto a linha `CLAUDE.md or CLAUDE.local.md found: AGENTS.md is not loaded; move its content to AGENTS.md`
33. The `CONTRIBUTING.md` e o `docs/pt-BR/CONTRIBUTING.md` SHALL dizer que as instruções do projeto estão no `AGENTS.md`, que o Claude Code o lê a partir da 2.1.277 e que um `CLAUDE.local.md` desliga essa leitura
34. The prova da regra de doc (C48 da model-setup-docs) e a lista da door 10 da agent-run-notify SHALL ler `AGENTS.md` no lugar de `CLAUDE.md`

**Independent test:** numa sessão nova do Claude Code na raiz, aparece `no CLAUDE.md found; AGENTS.md loaded: .../AGENTS.md`.

### S7: a doc é cobrada por máquina, não por memória (P1)

Um PR que muda comportamento sem doc, sem par ou sem `CHANGELOG.md` falha, e a regra está escrita onde o agente lê.

**Acceptance Criteria**

35. The `AGENTS.md` SHALL ter a seção `## Documentação` com: inglês primeiro e par em `docs/pt-BR/` com o mesmo nome e os links nas 5 primeiras linhas; as duas versões no mesmo commit; o que fica fora da regra; a tabela do que cada mudança atualiza (subcomando ou flag → `README.md` e doc do tema; campo do evento → doc do evento; plugin → `docs/plugins.md`; comportamento visível → `CHANGELOG.md` em `## [Unreleased]`); e o escape da door 9
36. IF uma opção longa (`--<nome>`, menos `--help`) de qualquer subcomando do parser de `grokbot-kit` não aparece em `README.md` ou `docs/*.md`, ou não aparece em `docs/pt-BR/*.md` THEN `tests/test_docs.py` SHALL falhar nomeando o subcomando e a opção
37. IF um campo de `properties` do `src/grokbot_kit/assets/event.v1.json` não aparece entre crases em `README.md` ou `docs/*.md`, ou em `docs/pt-BR/*.md` THEN `tests/test_docs.py` SHALL falhar nomeando o campo
38. IF um link Markdown relativo em `README.md`, `CONTRIBUTING.md`, `docs/*.md` ou `docs/pt-BR/*.md` aponta para arquivo que não existe THEN `tests/test_docs.py` SHALL falhar com `<arquivo>:<linha>`
39. IF o PR muda um doc pareado (`README.md`, `CONTRIBUTING.md`, `docs/<x>.md`) e não muda o par, ou muda o par e não o original THEN `tools/sdlc.py pr` SHALL sair com `1` nomeando os dois arquivos
40. IF o tipo do título do PR é `feat` ou `fix`, o PR muda `src/` ou `skills/` e não muda a seção `## [Unreleased]` do `CHANGELOG.md` THEN `tools/sdlc.py pr` SHALL sair com `1`
41. IF o tipo do título do PR é `feat` ou `fix`, o PR muda `src/` ou `skills/`, não muda `README.md` nem `docs/*.md`, e o corpo não tem a linha `Docs: n/a - <razão>` com razão não vazia THEN `tools/sdlc.py pr` SHALL sair com `1`
42. IF um `plan.md` não tem critério que cite `README.md` ou `docs/` e não tem a linha `Docs: n/a - <razão>` THEN `tools/sdlc.py spec <f>` SHALL sair com `1`
43. The `.github/pull_request_template.md` SHALL ter, no item de doc, a alternativa `Docs: n/a - <reason>` nesta descrição

**Independent test:** apagar `--timeout` do `README.md` faz o `uv run pytest tests/test_docs.py` falhar nomeando `run --timeout`.

### S8: o `commit-msg` não trava um merge local (P1, achado no review do PR #34)

O `commit-msg` deixa passar a mensagem que o próprio git escreve num merge.

**Acceptance Criteria**

46. WHEN a primeira linha da mensagem é a que o git escreve num merge (`Merge branch '<b>'`, `Merge branches`, `Merge remote-tracking branch '<b>'`, `Merge tag '<t>'`, `Merge commit '<c>'`) THEN `tools/sdlc.py commit-msg <arquivo>` SHALL não aplicar a door 3 a ela, e ainda SHALL aplicar a AC 3; o título do PR segue a door 3 sem exceção

**Independent test:** `git pull` numa branch divergida faz o merge sem `--no-verify`.

## Out of scope

- Barrar no GitHub o merge, a tag e o release feitos pelo agente: ele usa as credenciais do `gh` do Rodrigo, e para o GitHub é o Rodrigo; o gate é o `ask` local da AC 20 (AD-053)

Product capabilities only. Process and harness rules live in AGENTS.md or as Observable `n/a`.

| Excluded | Why |
| --- | --- |
| provas do box disparadas pelo agente | o box só é alcançado pelo bot, sem API que o agente chame; segue o comando escrito para o Rodrigo repassar |
| review com aprovação obrigatória na proteção | o autor e o revisor são a mesma conta; o `revisar-pr` continua como passo do agente, conferido pelo Rodrigo no merge |
| merge automático e release automatizado | merge e tag ficam com o Rodrigo (decisão de 29/10/2026) |
| gate para Codex e opencode trabalhando no repositório | os hooks git das AC 1-7 valem para qualquer CLI; só os gates do Claude Code (S3) são exclusivos dele |
| remover as skills `tlc-*` que não estão no roteamento | apagar exige rever o `NOTICE` e o lock; o roteamento da AC 26 já resolve a ambiguidade |
| consolidar `DECISOES.md` no `STATE.md` | não bloqueia o fluxo; fica como issue |
| cobrar chaves de config e campos do manifesto de plugin na doc | sem schema único de onde tirar a lista; fica como issue |
| regra de doc para o `SKILL.md` do bot | já tem prova própria (`tests/test_skill_doc.py`) e segue a língua do bot |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| língua de commits e PRs | segue pt-BR na descrição, tipos e escopos em inglês | é o histórico inteiro do repositório; a regra é de formato, não de língua | n |
| exceção à AC 16 | nenhuma: todo PR que muda `src/` ou `skills/` traz um `verification.md` | sem exceção o agente não tem como pular o Verifier; release e deps não tocam `src/` (PR 30 e Dependabot) | n |
| instalação dos hooks pela sessão | o `SessionStart` instala sozinho em vez de só avisar | instalar é local e reversível, e avisar depende de alguém ler | n |
| doc dos campos do evento | um doc novo `docs/event.md` com par em pt-BR, linkado do `README.md` | 26 campos não cabem no README sem soterrar o quick start | n |
| aplicar o `main-protection.json` no GitHub | o Rodrigo aplica (`gh api` cai no `ask` da AC 20) depois do merge | mudar a proteção é um passo humano pela decisão de 29/10/2026 | y |

**Open questions:** none - all resolved or logged above.

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| comando `tools/sdlc.py` | output format and verbosity | AC 2-5 (silêncio no `0`, motivo em stderr no `1`) |
| comando `tools/sdlc.py` | every flag and its default | door 1 |
| comando `tools/sdlc.py` | exit codes | door 1 (`0`, `1`, `2`) |
| comando `tools/sdlc.py` | what it prints when it fails halfway | AC 15 (cada validador que falhou é nomeado; os outros ainda rodam) |
| job `process` no CI | output format | AC 11-18 (o stderr do `tools/sdlc.py` no log do job) |
| regras de permissão do Claude Code | output format | AC 20, 22 (o pedido de confirmação nativo) |
| hook `SessionStart` | output and failure | AC 9 |
| doc `AGENTS.md` | structure, tone, depth, what the reader does next | AC 26 |
| doc `CONTRIBUTING.md` (EN e pt-BR) | structure and what the reader does next | AC 28, AC 33 |
| doc `AGENTS.md`, seção `## Documentação` | structure and what the reader does next | AC 35 |
| doc do evento (EN e pt-BR) | structure, depth | AC 37 (todo campo de `properties`) |
| `tests/test_docs.py` | output when it fails | AC 36-38 (nomeia subcomando e opção, campo, `<arquivo>:<linha>`) |
| backlog (issues) | grouping, naming, duplicates | AC 25; labels de hoje (`area:*`, `cli:*`, `bug`, `enhancement`); duplicata pelo label `duplicate` existente |

## Sources

- <https://code.claude.com/docs/en/memory#agents-md> — o Claude Code lê o `AGENTS.md` sem `CLAUDE.md` nem `CLAUDE.local.md` na árvore, a partir da 2.1.277 (aqui: 2.1.312)
- Diagnóstico do fluxo, conversa de 29/10/2026, e as decisões do Rodrigo: aprovações dele ficam em plano, merge e tag; backlog em GitHub Issues
- `CLAUDE.md`, `CONTRIBUTING.md` e `.claude/hooks/gate-worktree.sh` — as regras de hoje que esta feature transforma em gates
