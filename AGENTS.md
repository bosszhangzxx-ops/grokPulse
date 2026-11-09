# grokbot-kit

Kit de integração Grok Bot: delegar tarefas a agentes headless (opencode, Claude Code, Codex) e acordar a routine do
bot certo. Este é o único arquivo de instruções do projeto, lido pelo Claude Code (2.1.277 ou mais novo), pelo Codex e
pelo opencode. Specs e decisões em `docs/.specs/`.

## Fluxo

Do issue ao merge, cada passo com o gate que o confere:

1. **Issue.** Toda tarefa tem um issue no GitHub (AD-051); pendências vivem nos issues, não no `STATE.md`.
2. **Worktree.** Invoque a skill `delegar-em-worktree`: worktree em `../worktrees/`, base `main`, branch
   `<tipo>/<issue>/<slug>` com o número do issue (`feat/31/sdlc-gates`). O hook `pre-push` recusa outro nome.
3. **Plano.** Feature com spec: a skill do trabalho (veja `## Skills`) escreve o `plan.md`; o Rodrigo aprova no chat
   e só então entra a linha `**Approved**: AAAA-MM-DD` logo abaixo do título.
4. **Checks e build.** `checks.md` com provas, testes escritos a partir dos checks, commits em
   [Conventional Commits](https://www.conventionalcommits.org/) (o hook `commit-msg` confere), validadores sempre com
   `--root docs` ou por `python3 tools/sdlc.py spec <feature>`.
5. **Verifier.** Depois do último commit, um Verifier independente escreve o `verification.md`; o
   `validate_verification.py` tem de sair com `0`. PR que muda `src/` ou `skills/` sem `verification.md` não passa.
6. **PR.** Push da branch e `gh pr create` com `Closes #<issue>` no corpo; o título vira a mensagem do squash e segue a
   mesma regra dos commits. O job `process` do CI roda `tools/sdlc.py pr` (título, branch, commits, link do issue,
   specs das features tocadas, `**Approved**`, `## Handoff`, par de doc, `CHANGELOG.md`). Depois, `revisar-pr` e a
   resposta a cada conversa do review.
7. **Merge e release.** O Rodrigo faz o merge (squash) e cria a tag `v<versão>`.

## Autonomia

| O agente faz sozinho | Espera o Rodrigo |
| --- | --- |
| abrir o issue, criar a worktree, escrever o plano e os checks | aprovar o plano |
| testes, implementação, commits, Verifier | fazer o merge do PR em `main` |
| push da branch de feature, abrir o PR, `revisar-pr`, responder e resolver o review | criar a tag de release |

Os gates do Claude Code são regras de permissão do `.claude/settings.json` (AD-050, AD-053, AD-054): `allow` para `git
push` e `gh pr create`, e `ask` para `gh pr merge`, push de tag (até por refspec, `--follow-tags` ou `--mirror`), `gh
release` e `gh api` de proteção, environment, merge ou release, em qualquer trecho de um comando composto. Aplicar um
payload de `.github/repo-settings/` no GitHub cai no mesmo `ask`. O push para `main` é recusado pelo hook `pre-push` e
pela proteção da `main` no GitHub (`enforce_admins`, PR obrigatório). O hook `commit-msg` aceita a mensagem que o git
escreve num merge (`Merge branch '...'`).

## Skills

| Trabalho | Skill |
| --- | --- |
| feature (comportamento novo ou mudado) | `tlc-spec-lean`: `plan.md` → `checks.md` → build → Verifier |
| ideia sem forma, sem decisão de o que construir | `tlc-discover`, e depois `tlc-spec-lean` |
| mudança de até 3 arquivos sem one-way door | `tlc-spec-lean` com só o `checks.md`, aberto por um `## Intent` |
| dependências, docs, release | sem spec: PR direto, com as regras de commit, branch e doc |
| revisar um PR | `revisar-pr` |

A raiz dos specs é `docs` (`docs/.specs/`): os validadores do `tlc-spec-lean` rodam com `--root docs`, ou todos de uma
vez com `python3 tools/sdlc.py spec <feature>`, que é o que o job `process` roda.

## Ambiente

- O box (onde o Grok Bot roda o kit) não tem ssh daqui: é alcançado só pelo bot. Uma prova que precisa do box vira um
  comando escrito para o Rodrigo repassar ao bot, e a saída volta para `docs/.specs/features/<feature>/`.
- No box, os tiers do opencode usam modelos `opencode-go/<modelo>` (assinatura), não os `-free`.
- O Claude Code lê este arquivo a partir da 2.1.277, desde que não exista `CLAUDE.md` nem `CLAUDE.local.md` na raiz;
  o hook de início de sessão (`.claude/hooks/session-start.sh`) avisa quando existe e instala os hooks git que faltam.

## Gate de implementação (obrigatório)

**Antes de iniciar qualquer implementação, invoque a skill `delegar-em-worktree`.** Toda tarefa de código roda numa
worktree dedicada; o clone principal não recebe edição de código.

- O hook `.claude/hooks/gate-worktree.sh` (PreToolUse em Edit/Write) nega edições de código no clone principal, e o
  hook git `pre-commit` (`tools/sdlc.py pre-commit`) recusa o commit de código ali e qualquer commit em `main`. No
  clone principal só são editáveis `docs/`, `.specs/`, `.claude/`, `.agents/` e `AGENTS.md`.
- Escrever arquivos via Bash não contorna o gate: é a mesma regra.
- Trabalho deliberado no clone principal: só com pedido explícito do usuário, rodando a sessão com
  `GROKBOT_KIT_ALLOW_MAIN_EDIT=1`.
- Config da skill: `.claude/worktree-handoff.json`.

## Skills do projeto

- `tlc-*` (tech-leads-club/agent-skills, spec-driven): instaladas por cópia; atualizar com
  `npx @tech-leads-club/agent-skills update` (lock em `.agents/.skill-lock.json`).
- `delegar-em-worktree`, `revisar-pr` (rodrigo-pasini/skills, commit `508cc3e`): cópia do repo.

## Documentação

- Todo doc para quem usa ou contribui com o projeto é escrito primeiro em inglês e tem a tradução em pt-BR em
  `docs/pt-BR/`, com o mesmo nome: `README.md` → `docs/pt-BR/README.md`, `docs/<doc>.md` → `docs/pt-BR/<doc>.md`.
  Nas 5 primeiras linhas, cada versão aponta para a outra (`Leia em português: ...` / `Read in English: ...`).
- Uma mudança num doc atualiza as duas versões no mesmo commit.
- Fora da regra: `docs/.specs/` (specs e decisões, em pt-BR), `AGENTS.md`, o `CHANGELOG.md` (só em inglês) e o que o
  kit entrega ao bot (`skills/grokbot-kit/SKILL.md` e os prompts e skills dos plugins próprios), que seguem a língua do
  bot.
- Mudança de comportamento visível (comando, flag, config, evento, plugin) atualiza o `README.md` e o doc do tema, em
  inglês e em pt-BR, no mesmo PR; o plano de cada feature tem critério de doc.

| Mudança | Atualiza |
| --- | --- |
| subcomando ou flag | `README.md` (seção `## Commands`) e o doc do tema |
| campo do evento `grokbot-kit.event/v1` | `docs/event.md` |
| plugin, manifesto ou capacidade | `docs/plugins.md` |
| qualquer comportamento visível | `CHANGELOG.md`, em `## [Unreleased]` |

Cada linha vale nas duas línguas. Quem confere: `tests/test_docs.py` (subcomandos, flags e campos do evento nas duas
línguas, pares e links) e o `tools/sdlc.py` (`pr`: par alterado no mesmo PR, `## [Unreleased]` e doc em PR `feat` ou
`fix` que muda `src/` ou `skills/`; `spec`: critério de doc no plano). Quando a mudança não pede doc, o corpo do PR ou
o `plan.md` leva a linha `Docs: n/a - <razão>`, com a razão escrita.

## Git

- Branch padrão `main`, protegida: só entra por PR, com squash e os 6 checks do CI verdes (`process` incluído).
- Branch `<tipo>/<issue>/<slug>`; `chore/release/<versão>` para release; `dependabot/` é do Dependabot.
- Commits e título do PR em Conventional Commits, até 100 caracteres na primeira linha; tipos e escopos em inglês, a
  descrição em pt-BR.
- Nunca adicionar `Co-Authored-By` nos commits nem no corpo do PR: o hook `commit-msg` e o job `process` recusam.
- Hooks git: `uv run pre-commit install` instala `pre-commit`, `commit-msg` e `pre-push` (o hook de início de sessão
  do Claude Code roda isso quando faltam).

## tlc-spec-lean

profile: standard
budget: 150k
