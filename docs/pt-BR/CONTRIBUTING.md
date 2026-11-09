# Contribuindo com o grokbot-kit

> Read in English: [CONTRIBUTING.md](../../CONTRIBUTING.md)

## Setup

Requer [`uv`](https://docs.astral.sh/uv/). O `uv` instala o Python fixado em `.python-version` (`3.11`).

```sh
uv sync
uv run pre-commit install
```

`uv sync` cria `.venv/` com as dependências de desenvolvimento do `uv.lock`; `pre-commit install` instala os hooks
`pre-commit`, `commit-msg` e `pre-push` de `.pre-commit-config.yaml` (ruff, checagens de TOML/YAML, espaços, `mypy` e
as regras do fluxo do `tools/sdlc.py`, veja [Gates do fluxo](#gates-do-fluxo)).

## Lint, tipos e testes

```sh
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
```

São os mesmos comandos dos jobs `lint`, `typecheck` e `test (3.11)`, `test (3.12)`, `test (3.13)` do CI. Testes
marcados com `integration` usam as CLIs reais ou o GitHub e só rodam no box: `uv run pytest -m integration`.

## Fluxo de PR

- Tudo sai de `main` e volta por pull request; `main` é protegida e só aceita squash merge.
- Toda tarefa nasce de um issue no GitHub. Branch no padrão `<tipo>/<issue>/<slug>`, com o número do issue
  (`feat/31/sdlc-gates`), e o corpo do pull request liga o issue com `Closes #<issue>` (ou `Fixes #`, `Refs #`).
- Commits e título do pull request em [Conventional Commits](https://www.conventionalcommits.org/), até 100
  caracteres na primeira linha, sem `Co-Authored-By`.
- O pull request só entra com os 6 checks do CI verdes; o título vira a mensagem do squash.
- Mudança de comportamento ganha entrada em `## [Unreleased]` no `CHANGELOG.md`.
- Mudança de comportamento visível (comando, flag, config, evento, plugin) atualiza no mesmo PR o `README.md` e o doc
  do tema, em inglês e na tradução em `docs/pt-BR/`; o `tests/test_docs.py` quebra quando um subcomando não aparece
  nos READMEs ou um doc fica sem par.
- Nunca cole tokens, keys ou URLs secretas em commit, issue ou pull request.

## Gates do fluxo

As regras do fluxo falham cedo, por máquina, pelo `tools/sdlc.py` (só a biblioteca padrão do Python):

- hook `commit-msg`: a primeira linha segue Conventional Commits e nenhuma linha é `Co-authored-by:`; a primeira
  linha que o git escreve num `git merge` ou `git pull` (`Merge branch '...'`) fica fora do Conventional Commits, não
  da regra de coautoria.
- hook `pre-commit`: nenhum commit em `main`, e nenhum commit de código no clone principal (ali, só `docs/`, `.specs/`,
  `.claude/`, `.agents/` e `AGENTS.md`); `GROKBOT_KIT_ALLOW_MAIN_EDIT=1` desliga a segunda regra.
- hook `pre-push`: a branch casa `<tipo>/<issue>/<slug>`, `chore/release/<versão>` ou `dependabot/`.
- job `process` do CI, check obrigatório: o `tools/sdlc.py pr` confere título, branch, commits e `Closes #<issue>` do
  pull request, roda os validadores do `tlc-spec-lean` de cada feature que o PR toca, recusa mudança em `src/` ou
  `skills/` sem `verification.md`, `plan.md` sem a linha `**Approved**: AAAA-MM-DD` e `## Handoff` do
  `docs/.specs/STATE.md` com mais de 40 linhas, e confere a doc: doc pareado alterado sem o par, e `feat` ou `fix`
  que muda `src/` ou `skills/` sem entrada em `## [Unreleased]` ou sem doc (ou uma linha `Docs: n/a - <razão>` no
  corpo).

Qualquer regra roda à mão: `python3 tools/sdlc.py --help`.

## Instruções dos agentes e Claude Code

As instruções para agentes de código (fluxo, autonomia, skills, ambiente, regra de doc) estão no `AGENTS.md`, o único
arquivo de instruções do projeto. O Claude Code o lê a partir da versão 2.1.277, desde que não exista `CLAUDE.md` nem
`CLAUDE.local.md` na raiz: um `CLAUDE.local.md` local desliga essa leitura. O hook de início de sessão
`.claude/hooks/session-start.sh` avisa disso e instala os hooks git quando faltam.

Quem trabalha com o Claude Code neste repositório faz cada tarefa de código numa worktree dedicada em
`../worktrees/`. O hook `.claude/hooks/gate-worktree.sh` (PreToolUse em Edit/Write) nega edição de código no clone
principal. Para trabalhar de propósito no clone principal, rode a sessão com `GROKBOT_KIT_ALLOW_MAIN_EDIT=1`. As regras de
permissão do `.claude/settings.json` deixam o agente fazer push de branch e abrir pull request, e pedem
confirmação antes de merge, push de tag, release ou mudança na proteção da branch, em qualquer trecho de um comando
composto. Push para `main` é recusado pelo hook `pre-push` e pela proteção da `main` no GitHub.

## Release e PyPI

O workflow `release.yml` publica no PyPI por trusted publishing quando uma tag `v<semver>` igual à versão do
`pyproject.toml` é enviada; nenhum token fica guardado no repositório. Antes da primeira tag, um passo humano: em
<https://pypi.org/manage/account/publishing/>, adicionar um pending publisher do GitHub com

- PyPI Project Name: `grokbot-kit`
- Owner: `rodrigo-pasini`
- Repository name: `grokbot-kit`
- Workflow name: `release.yml`
- Environment name: `pypi`

O pending publisher não reserva o nome até a primeira publicação. Nenhuma tag `v*` é criada antes de ele existir.

## Test policy

> Copiada de `docs/.specs/features/agent-run-notify/checks.md` e aprovada como diretriz do repositório.

O repositório não tem guia de testes: nada diz que nível prova que código nem quanto do espaço de entrada uma prova precisa afirmar. Estas linhas são o padrão deste build.

| Code | Required proofs | Coverage expectation |
| --- | --- | --- |
| Decide, alcançado através de uma fronteira (CLI ou HTTP) | uma na fronteira (subprocesso `grokbot-kit` ou receptor HTTP local) **e** uma na própria camada | o contrato na fronteira; um caso afirmado por linha da tabela de decisão na própria camada |
| Decide, sem fronteira | uma na própria camada | um caso afirmado por linha da tabela de decisão |
| Ponto de entrada que não decide | uma na fronteira | entrada aceita, cada entrada recusada, cada caminho de erro |
| Instrumentação, repasse | nenhuma própria | coberto pela prova de quem a consome |
| Integração com CLI real ou GitHub | `-m integration` no box (ou comando `gh`) | o hook ou a configuração dispara de verdade, uma vez por CLI |

Evidência (ainda não há código; tabelas de decisão contadas no plano):

- derivação do status terminal (AC 43-45): 8 linhas (ok, 2 de denied, 5 de error) e 1 regra de precedência → decide, alcançado pela CLI
- classificação da resposta HTTP (AC 68-72, 123): 7 classes por sink → decide, alcançado por HTTP
- resolução de tool/modelo/tier/timeout (AC 78-83): 6 pontos de decisão → decide
- normalização dos hooks no `emit` (AC 54-58): 4 fontes e 1 regra de dedupe → decide, alcançado pela CLI
- predicado do `gc` (AC 101): 4 casos → decide
- montagem do argv por tool (AC 40-42): 3 linhas → decide (mapping com mais de uma linha)
- análogo no repositório: nenhum ainda (projeto novo); o mais próximo por forma é `.claude/skills/revisar-pr/scripts/conferir-achados.py` com `test-conferir-achados.py`, provado na própria camada

Custo: cerca de 45 provas na própria camada em 12 arquivos de teste, mais 9 provas `-m integration` no box. Sem estas linhas, 6 tabelas de decisão seriam provadas só pelo caminho que um teste de ponta a ponta atravessa.
