# Kit de integração Grok Bot - v1 - checks

Profile: standard
Plan: `docs/.specs/features/agent-run-notify/plan.md`

151 checks em 9 slices (C146-C148 acrescentados na verificação, C149 pela AD-032, C150 pela AD-033, C151 pela AD-035) · 11 one-way doors · 3 open, das quais 1 bloqueia (pergunta 2 → C66, C69)

Convenções das provas:

- `uv run pytest <arquivo> -k <nome>` roda no CI (unitário, CLIs falsas em `tests/fakes/` no `PATH`, `HOME` isolado em `tmp_path`, receptor HTTP local em `127.0.0.1`).
- `uv run pytest -m integration <arquivo> -k <nome>` roda **só no box**, com as CLIs reais instaladas e logadas; fica fora do CI (`addopts = "-m 'not integration'"`) e o Verifier roda os dois níveis.
- Provas do S0 contra o GitHub são comandos `gh`/`git` cujo exit decide; `jq -e` sai com `1` quando a expressão é falsa.
- `pyyaml` e `jsonschema` entram só em `[dependency-groups] dev` (ler workflows e validar eventos); `dependencies = []` continua.

## Checks

### S0 - repositório `grokbot-kit` criado e constituído · ~22 arquivos · ~45 KB · ~11k

**C1** - `rodrigo-pasini/grokbot-kit` existe, é público, sob `rodrigo-pasini`, com branch padrão `main` (AC 1)
Proof: `gh repo view rodrigo-pasini/grokbot-kit --json name,visibility,owner,defaultBranchRef | jq -e '.name=="grokbot-kit" and .visibility=="PUBLIC" and .owner.login=="rodrigo-pasini" and .defaultBranchRef.name=="main"'`

**C2** - A aprovação explícita do Rodrigo para criar o repositório público está registrada no `STATE.md` antes da criação (AC 1)
Proof: `grep -nE '^\| AD-[0-9]+ \| Aprovação para criar o repositório público' docs/.specs/STATE.md`

**C3** - `LICENSE` contém o texto MIT e `Copyright (c) 2026 Rodrigo Pasini`, e o `pyproject.toml` declara `license = "MIT"` (AC 2, door 9)
Proof: `uv run pytest tests/test_repo_files.py -k license_mit`

**C4** - `NOTICE` credita as skills `tlc-*` de `.claude/skills/` a tech-leads-club/agent-skills sob CC-BY-4.0 (AC 2)
Proof: `uv run pytest tests/test_repo_files.py -k notice_credits_tlc_skills`

**C5** - `README.md` tem as 8 seções `What it is`, `Install`, `Quick start`, `Grok Bot skill`, `Configuration`, `Security`, `Contributing`, `License` e link para `docs/pt-BR/README.md` (AC 3)
Proof: `uv run pytest tests/test_repo_files.py -k readme_sections`

**C6** - `pyproject.toml` declara `name = "grokbot-kit"`, `requires-python = ">=3.11"`, `dependencies = []`, o script `grokbot-kit = "grokbot_kit.cli:main"` e build backend `uv_build`, com o código em `src/grokbot_kit/` (AC 4, door 6)
Proof: `uv run pytest tests/test_repo_files.py -k pyproject_fields`

**C7** - `.python-version` contém `3.11`, `uv.lock` está versionado e `uv sync --locked` num clone limpo sai com `0` (AC 5)
Proof: `uv run pytest tests/test_repo_files.py -k python_version_and_lock`
Proof: `tmp=$(mktemp -d) && git clone -q . "$tmp" && uv sync --locked --directory "$tmp"`

**C8** - O ruff está configurado com `target-version = "py311"`, `extend-exclude = [".claude", ".agents"]` e `force-exclude = true` (AC 6)
Proof: `uv run pytest tests/test_repo_files.py -k ruff_config`

**C9** - `uv run ruff check` e `uv run ruff format --check` saem com `0` (AC 6)
Proof: `uv run ruff check && uv run ruff format --check`

**C10** - Num clone limpo, `uv run pytest` coleta pelo menos um teste e sai com `0`, não `5` (AC 7)
Proof: `tmp=$(mktemp -d) && git clone -q . "$tmp" && cd "$tmp" && uv sync --locked && uv run pytest`

**C11** - O mypy está configurado com `strict = true` sobre `src/`, e `uv run mypy` sai com `0` (AC 8)
Proof: `uv run pytest tests/test_repo_files.py -k mypy_strict_config`
Proof: `uv run mypy`

**C12** - `.pre-commit-config.yaml` tem os 6 hooks `ruff check --fix`, `ruff format`, `check-toml`, `check-yaml`, `end-of-file-fixer`, `trailing-whitespace` e um hook local `uv run mypy`, todos com `exclude: ^(\.claude|\.agents)/` (AC 9)
Proof: `uv run pytest tests/test_repo_files.py -k precommit_hooks`

**C13** - `ci.yml` dispara em `push` e `pull_request` para `main`, roda em `ubuntu-latest` com `uv sync --locked` e tem os 5 jobs de nomes exatos `lint`, `typecheck`, `test (3.11)`, `test (3.12)`, `test (3.13)` (AC 10)
Proof: `uv run pytest tests/test_workflows.py -k ci_jobs_and_triggers`

**C14** - `release.yml` dispara em tag `v*`, tem `build` sem `id-token` e `publish` com `environment: pypi`, `permissions` `id-token: write` e `contents: write`, `pypa/gh-action-pypi-publish@release/v1` e anexa `dist/*` a um GitHub Release (AC 11)
Proof: `uv run pytest tests/test_workflows.py -k release_jobs_and_permissions`

**C15** - Com a tag `v0.2.0` e `version = "0.1.0"` no `pyproject.toml`, o passo de checagem de versão do release sai com código diferente de `0` antes do publish; com versões iguais, sai com `0` (AC 12)
Proof: `uv run pytest tests/test_workflows.py -k release_version_mismatch_fails`

**C16** - `.gitignore` ignora os 10 padrões `.venv/`, `__pycache__/`, `dist/`, `build/`, `*.egg-info/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `.coverage`, `.env` e não ignora `.claude/` nem `.agents/` (AC 13)
Proof: `uv run pytest tests/test_repo_files.py -k gitignore_entries`

**C17** - `CONTRIBUTING.md` documenta `uv sync`, `pre-commit install`, lint, tipos, testes, fluxo de PR e o gate de worktree com `GROKBOT_KIT_ALLOW_MAIN_EDIT=1`; `CHANGELOG.md` segue Keep a Changelog com `## [Unreleased]` (AC 14)
Proof: `uv run pytest tests/test_repo_files.py -k contributing_and_changelog`

**C18** - Existem `bug_report.yml`, `feature_request.yml` e `pull_request_template.md`, e o template de bug pede versão do `grokbot-kit` e da CLI e avisa para não colar segredos (AC 15)
Proof: `uv run pytest tests/test_repo_files.py -k issue_and_pr_templates`

**C19** - `dependabot.yml` declara atualizações `weekly` para os ecossistemas `uv` e `github-actions` (AC 17)
Proof: `uv run pytest tests/test_workflows.py -k dependabot_ecosystems`

**C20** - Os 3 originais de `docs/.specs/` e os 2 payloads de `.github/repo-settings/` estão versionados, e `docs/SPEC.md` é ignorado (AC 18)
Proof: `git ls-files --error-unmatch docs/.specs/STATE.md docs/.specs/DECISOES.md docs/.specs/features/agent-run-notify/plan.md .github/repo-settings/main-protection.json .github/repo-settings/pypi-environment.json && git check-ignore -q docs/SPEC.md`

**C21** - Os 2 payloads de `.github/repo-settings/` são idênticos, como JSON, aos literais da door 11 (AC 18, door 11)
Proof: `uv run pytest tests/test_repo_files.py -k repo_settings_payloads_match_door_11`

**C22** - `skills/grokbot-kit/SKILL.md`, `src/grokbot_kit/assets/opencode/grokbot-kit.ts` e `src/grokbot_kit/assets/event.v1.json` existem e os dois assets entram no wheel de `uv build` (AC 19)
Proof: `uv run pytest tests/test_repo_files.py -k assets_in_wheel`

**C23** - Toda a árvore literal da door 10 existe no repositório (door 10)
Proof: `uv run pytest tests/test_repo_files.py -k door_10_tree`

**C24** - Antes de criar, `gh auth status` ativo em `github.com` mostra `login` `rodrigo-pasini`, `state` `success` e `repo` nos `scopes` quando há scopes (AC 20)
Proof: `gh auth status --active --hostname github.com --json hosts --jq '.hosts["github.com"][] | select(.active) | {login, state, scopes}' | jq -e '.login=="rodrigo-pasini" and .state=="success" and ((.scopes // "") == "" or (.scopes | test("(^|, )repo(,|$)")))'`

**C25** - Antes de criar, `gh repo view rodrigo-pasini/grokbot-kit` e `git remote get-url origin` saem ambos com código diferente de `0` (AC 21)
Proof: `grep -nE '^\| AD-024 \|.*precondições C24/C25 verdes' docs/.specs/STATE.md`
Prova histórica, renegociada na verificação de 20/10/2026 (a precondição só vale antes da criação e não se repete); a original, rodada no build do S0 e registrada na AD-024, era `! gh repo view rodrigo-pasini/grokbot-kit --json name >/dev/null 2>&1 && ! git remote get-url origin >/dev/null 2>&1`.

**C26** - `79f430f2af45c0d3ca32b72df7f00162225dfe5d` e `0c3e4a28b6e1595bc1f2fe83ee57221a51b0e17d` são ancestrais de `main`, e os 5 comandos de qualidade saem com `0` no commit enviado (AC 22)
Proof: `git merge-base --is-ancestor 0c3e4a28b6e1595bc1f2fe83ee57221a51b0e17d main && uv sync --locked && uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest`

**C27** - Nenhum commit de `main` casa com o regex de segredos do AC 23 e `git ls-files` não lista `.env` (AC 23, AC 35)
Proof: `! git grep -nE 'crsr_[0-9a-f]{8}|gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}|sk-ant-[A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|pypi-AgEI[A-Za-z0-9_-]{20,}' $(git rev-list main) && ! git ls-files | grep -qE '(^|/)\.env$'`

**C28** - O commit raiz do remoto é `79f430f2af45c0d3ca32b72df7f00162225dfe5d`, ou seja, o GitHub não criou commit próprio (sem `--add-readme`/`--license`/`--gitignore`) (AC 24)
Proof: `test "$(git rev-list --max-parents=0 origin/main)" = 79f430f2af45c0d3ca32b72df7f00162225dfe5d`

**C29** - As configurações do repositório batem com a door 11: `PUBLIC`, issues `true`, wiki/projects/discussions `false`, só squash, `deleteBranchOnMerge` `true`, os 10 topics, licença MIT, `main`, auto-merge e update branch `true`, secret scanning e push protection `enabled` (AC 25, AC 33)
Proof: `uv run pytest -m integration tests/integration/test_github_repo.py -k repo_settings_match_door_11`

**C30** - O `main` local e o remoto apontam para o mesmo commit depois do primeiro push (AC 26)
Proof: `test "$(git rev-parse main)" = "$(git ls-remote origin refs/heads/main | cut -f1)"`

**C31** - A execução mais recente do `ci.yml` em `main` terminou com `success` (AC 27)
Proof: `test "$(gh run list -R rodrigo-pasini/grokbot-kit --branch main --workflow ci.yml --limit 1 --json conclusion --jq '.[0].conclusion')" = success`

**C32** - O agente tem `ADMIN` no repositório (AC 28)
Proof: `test "$(gh repo view rodrigo-pasini/grokbot-kit --json viewerPermission --jq .viewerPermission)" = ADMIN`

**C33** - A proteção de `main` mostra os 5 checks, `strict` `true`, `approvals` `0`, `admins` `true`, `force` `false`, `deletions` `false`, `linear` `true` (AC 16, AC 28, AC 29)
Proof: `gh api repos/rodrigo-pasini/grokbot-kit/branches/main/protection --jq '{checks: [.required_status_checks.checks[].context] | sort, strict: .required_status_checks.strict, approvals: .required_pull_request_reviews.required_approving_review_count, admins: .enforce_admins.enabled, force: .allow_force_pushes.enabled, deletions: .allow_deletions.enabled, linear: .required_linear_history.enabled}' | jq -e '. == {checks: ["lint","test (3.11)","test (3.12)","test (3.13)","typecheck"], strict: true, approvals: 0, admins: true, force: false, deletions: false, linear: true}'`

**C34** - Alertas de vulnerabilidade respondem `204` e `automated-security-fixes` mostra `enabled` `true` (AC 30)
Proof: `gh api repos/rodrigo-pasini/grokbot-kit/vulnerability-alerts && gh api repos/rodrigo-pasini/grokbot-kit/automated-security-fixes --jq .enabled | grep -qx true`

**C35** - O environment `pypi` existe com as regras `required_reviewers` e `branch_policy`, e a única política de deploy é a tag `v*` (AC 31)
Proof: `gh api repos/rodrigo-pasini/grokbot-kit/environments/pypi --jq '{name, rules: [.protection_rules[].type] | sort}' | jq -e '. == {name: "pypi", rules: ["branch_policy","required_reviewers"]}' && gh api repos/rodrigo-pasini/grokbot-kit/environments/pypi/deployment-branch-policies --jq '[.branch_policies[] | {name, type}]' | jq -e '. == [{name: "v*", type: "tag"}]'`

**C36** - Os 9 labels da door 11 existem no repositório (AC 32, AC 33)
Proof: `gh label list -R rodrigo-pasini/grokbot-kit --limit 100 --json name --jq '[.[].name]' | jq -e '["area:cli","area:hooks","area:skill","area:webhook","cli:opencode","cli:claude","cli:codex","security","needs-triage"] - . == []'`

**C37** - Nenhum arquivo versionado chama `gh auth token` ou `gh auth status --show-token`, nem grava `GH_TOKEN`/`GITHUB_TOKEN` (AC 34)
Proof: `! git grep -nE 'gh auth token|--show-token|(GH_TOKEN|GITHUB_TOKEN)=' -- . ':!docs/.specs'`

**C38** - `release.yml` não referencia nenhum `secrets.*` (AC 35)
Proof: `uv run pytest tests/test_workflows.py -k release_reads_no_secret`

**C39** - `CONTRIBUTING.md` documenta o pending publisher com projeto `grokbot-kit`, owner `rodrigo-pasini`, repositório `grokbot-kit`, workflow `release.yml`, environment `pypi` e a URL `https://pypi.org/manage/account/publishing/` (AC 36)
Proof: `uv run pytest tests/test_repo_files.py -k contributing_pypi_pending_publisher`

**C40** - Enquanto o `STATE.md` não registra a confirmação do pending publisher, o remoto não tem nenhuma tag `v*` (AC 37)
Proof: `grep -qE '^\| AD-[0-9]+ \| Pending publisher do PyPI criado' docs/.specs/STATE.md || test -z "$(git ls-remote --tags origin 'v*')"`

**C41** - O relatório do S0 em `docs/.specs/features/agent-run-notify/s0-report.md` traz a saída dos comandos dos AC 29, 30, 31 e 33 e nenhum token (AC 38)
Proof: `uv run pytest tests/test_repo_files.py -k s0_report_has_outputs_and_no_token`

### S1 - o bot que delegou é acordado quando a tarefa termina · ~8 arquivos · ~60 KB · ~15k

**C42** - O processo filho lançado por `run` tem o stdin ligado a `/dev/null` (AC 39)
Proof: `uv run pytest tests/test_launch.py -k child_stdin_is_devnull`

**C43** - Com `--tool claude`, o argv contém `-p`, `--output-format json`, `--model <id>` e `--settings <task dir>/claude-settings.json`, e esse arquivo registra os hooks `PermissionRequest` chamando o caminho absoluto de `grokbot-kit emit --from claude` (AC 40)
Proof: `uv run pytest tests/test_launch.py -k claude_argv_and_settings`

**C44** - Com `--tool opencode`, o argv contém `run --format json -m <provider/model>` (AC 41)
Proof: `uv run pytest tests/test_launch.py -k opencode_argv`

**C45** - Com `--tool codex`, o env tem `CODEX_HOME` igual a `cli.codex.codex_home` e o argv contém `exec --json -m <id> -o <task dir>/last-message.txt --dangerously-bypass-hook-trust` e o `-c 'hooks.PermissionRequest=[...]'` literal da door 7 (AC 42, door 7)
Proof: `uv run pytest tests/test_launch.py -k codex_argv_env_and_inline_hooks`

**C46** - Exit `0`, saída JSON sem erro e nenhum `needs_input` no task dir geram `event: "completed"`, `status: "ok"`, `exit_reason: "success"` (AC 43)
Proof: `uv run pytest tests/test_terminal.py -k ok_on_clean_exit`

**C47** - Exit `0` com um `needs_input` registrado gera `completed`, `status: "denied"`, `exit_reason: "permission_denied"` (AC 44)
Proof: `uv run pytest tests/test_terminal.py -k denied_on_recorded_needs_input`

**C48** - Exit `0` do `claude` com `permission_denials` não vazio gera `completed`, `status: "denied"`, `exit_reason: "permission_denied"` (AC 44)
Proof: `uv run pytest tests/test_terminal.py -k denied_on_claude_permission_denials`

**C49** - Cada uma das 5 condições de erro gera `event: "error"`, `status: "failed"` com o `exit_reason` da tabela: exit ≠ `0` sem erro na saída → `nonzero_exit`; `is_error: true` (claude), `turn.failed` (codex), `error` (codex), evento `error` (opencode) → `agent_error` (AC 45)
Proof: `uv run pytest tests/test_terminal.py -k error_table_all_5_conditions`

**C50** - Erro na saída com `needs_input` registrado gera `error`/`failed`, não `denied` (AC 45 sobre AC 44)
Proof: `uv run pytest tests/test_terminal.py -k error_wins_over_needs_input`

**C51** - `summary` vem de `result` (claude), de `last-message.txt` (codex) ou do último evento `text` (opencode), e é cortado em 2000 caracteres: entradas de 1999, 2000 e 2001 caracteres resultam em 1999, 2000 e 2000 (AC 46)
Proof: `uv run pytest tests/test_terminal.py -k summary_source_per_tool_and_2000_bound`

**C52** - Uma task gera exatamente um evento terminal em `events.jsonl` e nos sinks, mesmo com o `emit` chamado com `completed`/`error`/`timeout`, que ele recusa (AC 47, door 5)
Proof: `uv run pytest tests/test_terminal.py -k exactly_one_terminal_per_task`

**C53** - As saídas com `2` dos AC 64, 65, 81, 82 e 90 não criam diretório em `~/.grokbot-kit/tasks/` nem enviam evento (AC 47)
Proof: `uv run pytest tests/test_run_guards.py -k exit_2_creates_no_task_dir`

**C54** - Quando a CLI falsa sai sozinha com `0`, `1` ou `3`, o `run` sai com o mesmo código (AC 48)
Proof: `uv run pytest tests/test_terminal.py -k run_exit_mirrors_agent`

**C55** - No box, uma tarefa curta em cada uma das 3 CLIs reais gera uma linha `completed`/`ok` no sink `file`, e um `touch` sem permissão gera `completed`/`denied` no `claude` e no `opencode` e `completed`/`ok` sem `needs_input` no `codex`, que não pede permissão em `codex exec` (AC 40, 41, 42, 43, 44, 57; AD-027)
Proof: `uv run pytest -m integration tests/integration/test_real_cli.py -k completed_ok_and_denied_per_tool`

### S2 - payload que deixa a routine agir sem perguntar · ~4 arquivos · ~30 KB · ~8k

**C56** - Todo evento de task tem os 13 campos do AC 49 não nulos e valida contra `src/grokbot_kit/assets/event.v1.json` (AC 49)
Proof: `uv run pytest tests/test_payload.py -k task_event_required_fields_and_schema`

**C57** - As propriedades de `event.v1.json` são exatamente os campos literais da door 2, com `schema` const `grokbot-kit.event/v1`, os enums de `event` (5), `status` (8) e `model_source` (3), e os campos de task anuláveis só para `event: "test"` (door 2)
Proof: `uv run pytest tests/test_payload.py -k schema_matches_door_2`

**C58** - Com `cwd` dentro de um repo git, `repo.root`, `repo.branch` e `repo.head` vêm de `git`; fora de um repo, `repo` é `null` (AC 50)
Proof: `uv run pytest tests/test_payload.py -k repo_fields_inside_and_outside_git`

**C59** - Com um id de sessão, `session_id` é preenchido e `resume_hint` é o comando literal de cada tool (`claude -p --resume <id>`, `opencode run -s <id>`, `CODEX_HOME=<codex_home> codex exec resume <id>`); sem id, ambos são `null` (AC 51)
Proof: `uv run pytest tests/test_payload.py -k resume_hint_per_tool`

**C60** - O `transcript_path` informado pelo hook aparece no evento; sem hook que o informe, é `null` (AC 52)
Proof: `uv run pytest tests/test_payload.py -k transcript_path_from_hook`

**C61** - `exit_reason` só assume os 7 valores do AC 53, e todo `event: "needs_input"` traz `exit_reason: "needs_input"` (AC 53)
Proof: `uv run pytest tests/test_payload.py -k exit_reason_enum_and_needs_input_mapping`

**C62** - `started_at` e `timestamp` são RFC 3339 em UTC com sufixo `Z` ou `+00:00` (door 2)
Proof: `uv run pytest tests/test_payload.py -k timestamps_rfc3339_utc`

### S3 - acordar o bot quando o agente esbarra numa permissão · ~6 arquivos · ~50 KB · ~13k

**C63** - O JSON de hook `PermissionRequest` do Claude, com `GROKBOT_KIT_TASK_ID` no env, gera `needs_input`, `status: "permission"` e `needs_input.tool_name` igual ao `tool_name` do hook (AC 54)
Proof: `uv run pytest tests/test_emit.py -k claude_permission_request`

**C64** - `permission.asked` do opencode sem `parentID` gera `needs_input`/`permission`; com `parentID`, não gera nada (AC 55)
Proof: `uv run pytest tests/test_emit.py -k opencode_permission_asked_root_session_only`

**C65** - `question.asked` do opencode gera `needs_input`, `status: "question"` (AC 56)
Proof: `uv run pytest tests/test_emit.py -k opencode_question_asked`

**C66** - O JSON de hook `PermissionRequest` do Codex gera `needs_input`, `status: "permission"` e `needs_input.tool_name` igual ao `tool_name` do hook (AC 57, segunda cláusula)
Proof: `uv run pytest tests/test_emit.py -k codex_permission_request`

**C67** - No box, `claude -p` real lançado por `run` sem `--allowedTools` e com um prompt que escreve arquivo gera um `needs_input` antes do terminal (AC 54)
Proof: `uv run pytest -m integration tests/integration/test_real_hooks.py -k claude_hook_fires`

**C68** - No box, `opencode run` real com `"permission": {"bash": "ask"}` gera `needs_input`/`permission`, e um prompt que pede uma pergunta termina com evento terminal diferente de `timeout` e sem nenhum `needs_input`/`question`, porque o `opencode run` 1.18.32 não interativo nega a ferramenta `question` (AC 55; AC 56 fica provada só pelo C65, AD-026)
Proof: `uv run pytest -m integration tests/integration/test_real_hooks.py -k opencode_plugin_fires`

**C69** - No box, `codex exec` real com `-s read-only` e um prompt que escreve arquivo não gera nenhum `needs_input` e termina com um único evento terminal `completed`/`ok`, porque o `codex exec` 0.163.0 força `approval_policy = never` e não chama o hook `PermissionRequest` (AC 57, primeira cláusula; AD-027)
Proof: `uv run pytest -m integration tests/integration/test_real_hooks.py -k codex_hook_silent_in_exec`

**C70** - O mesmo `tool_use_id` enviado 3 vezes gera 1 entrega; 2 ids distintos geram 2 (AC 58)
Proof: `uv run pytest tests/test_emit.py -k dedupe_same_id_once_distinct_twice`

**C71** - Sem `GROKBOT_KIT_TASK_ID`, o `emit` sai com `0`, não cria nenhum arquivo e não abre conexão (AC 59)
Proof: `uv run pytest tests/test_emit.py -k no_task_id_is_inert`

**C72** - Em entrega OK, em falha de entrega e em JSON de stdin inválido, o `emit` sai com `0` e o stdout é vazio ou exatamente `{}` (AC 60)
Proof: `uv run pytest tests/test_emit.py -k always_exit_0_stdout_at_most_braces`

**C73** - 8 processos `emit` simultâneos com a mesma chave de dedupe geram 1 entrega no receptor (AC 61)
Proof: `uv run pytest tests/test_emit.py -k concurrent_same_key_delivers_once`

**C74** - Sem `GROKBOT_KIT_TASK_ID`, um audit hook de `open` registra zero aberturas do config, de `~/.grokbot-kit/tasks/` e de `~/.secrets/grokbot-kit/` (AC 62)
Proof: `uv run pytest tests/test_emit.py -k no_task_id_opens_no_kit_files`

**C75** - Sem `GROKBOT_KIT_TASK_ID`, a saída de `python -X importtime -m grokbot_kit.emit` não lista `urllib.request`, `tomllib` nem `grokbot_kit.config`, e todo módulo importado pelo `emit` é da stdlib ou de `grokbot_kit` (AC 63, door 6)
Proof: `uv run pytest tests/test_emit.py -k importtime_gate_and_stdlib_only`

### S4 - rota por bot, autenticação, sinks e reentrega · ~10 arquivos · ~100 KB · ~25k

**C76** - `run --target inexistente` sai com `2` sem lançar a CLI falsa (AC 64)
Proof: `uv run pytest tests/test_run_guards.py -k unknown_target_exit_2`

**C77** - Segredo ausente ou com modo `0644` faz o `run` sair com `2` sem lançar; com `0600`, lança (AC 65)
Proof: `uv run pytest tests/test_run_guards.py -k secret_missing_or_wrong_mode_exit_2`

**C78** - O sink `grokbot-routine` faz `POST` na URL de `url_secret` com `Authorization: Bearer <key sem \n final>`, `Content-Type: application/json`, `User-Agent: grokbot-kit/<versão>` e os headers extras do sink (AC 66)
Proof: `uv run pytest tests/test_sink_routine.py -k request_headers_literal`

**C79** - O corpo é um único objeto JSON UTF-8 com `é` literal (sem `é`), e o `body_digest` em `events.jsonl` é `sha256:` do corpo recebido (AC 67)
Proof: `uv run pytest tests/test_sink_routine.py -k body_utf8_and_digest`

**C80** - `200` com `{"success": true, "runUuid": "u-1"}` e `202` com o mesmo corpo gravam `run_uuid` e `http_status` em `sent/<chave>` e em `events.jsonl` (AC 68)
Proof: `uv run pytest tests/test_sink_routine.py -k receipt_on_2xx_success`

**C81** - `200` com `{"success": false}` e `200` sem `runUuid` geram 1 requisição só e uma linha em `undelivered.jsonl` (AC 69)
Proof: `uv run pytest tests/test_sink_routine.py -k 2xx_without_receipt_fails_without_retry`

**C82** - Depois de um `run` completo com entrega `401`, nenhum arquivo do task dir, nem stdout, stderr, config ou evento contém o valor da key nem o da URL secreta (AC 70)
Proof: `uv run pytest tests/test_sink_routine.py -k secret_never_written`

**C83** - `429`, `500`, `503` e conexão recusada geram 3 tentativas com esperas de 1 s e 4 s e timeout de 10 s por tentativa; sucesso na 2ª tentativa para o retry (AC 71)
Proof: `uv run pytest tests/test_sink_routine.py -k retry_table_429_5xx_connection`

**C84** - `401`, `400`, `403`, `404` e `422` geram 1 tentativa, uma linha em `undelivered.jsonl` com status e `message`, stderr citando `grokbot-kit redeliver <task_id>` (e `grokbot-kit secret set <key_secret>` no `401`), e o exit do `run` igual ao do agente (AC 72)
Proof: `uv run pytest tests/test_sink_routine.py -k non_retryable_4xx_to_undelivered`

**C85** - `redeliver` sai com `0` quando reenvia tudo e esvazia o arquivo, `1` quando um evento falha e só ele fica, e `2` com task inexistente (AC 73)
Proof: `uv run pytest tests/test_redeliver.py -k exit_codes_0_1_2`

**C86** - Dois `redeliver` simultâneos na mesma task entregam cada evento uma vez, e o segundo encontra `redeliver.lock` criado com `O_CREAT + O_EXCL` (AC 74)
Proof: `uv run pytest tests/test_redeliver.py -k concurrent_redeliver_lock`

**C87** - `route test` envia `event: "test"`, `status: "test"`, `target` e os campos de task `null` a todos os sinks, imprime o `runUuid` de cada routine e sai com `0` só se todas as entregas tiveram sucesso, `1` se alguma falhou e `2` com target ou segredo inexistente (AC 75)
Proof: `uv run pytest tests/test_route.py -k route_test_event_and_exit_codes`

**C88** - `secret set` num pty desliga o eco, grava em `~/.secrets/grokbot-kit/<name>` com modo `0600` e diretório `0700`, aceita stdin sem TTY e sai com `1` quando a escrita falha (AC 76)
Proof: `uv run pytest tests/test_secret.py -k tty_noecho_modes_stdin_and_write_failure`

**C89** - `route add` sai com `2` quando a key não começa com `crsr_`, inclusive quando começa com `Bearer `, ou a URL não começa com `https://`, e a saída não contém nenhum dos dois valores; com valores válidos sai com `0` (AC 77)
Proof: `uv run pytest tests/test_route.py -k route_add_secret_validation`

**C90** - O sink `file` acrescenta uma linha com o corpo do AC 67 e `\n`, com `O_APPEND`, e cria o arquivo com modo `0600` (AC 120)
Proof: `uv run pytest tests/test_sinks_other.py -k file_sink_appends_line_0600`

**C91** - O sink `ntfy` faz `POST` em `topic_url` com o `summary` como corpo (ou `<event> <status>` quando vazio), `Title: grokbot-kit <event> <status> <task_label>` (`test` para label nulo), `Authorization: Bearer` só com `token_secret`, e trata `200`-`299` como entregue (AC 121)
Proof: `uv run pytest tests/test_sinks_other.py -k ntfy_request_and_success`

**C92** - O sink `slack` faz `POST` na URL de `webhook_secret` com `{"text": "[grokbot-kit] <event>/<status> <task_label> (<target>)\n<summary>"}` e trata como entregue só `200` com corpo `ok`; `200` com outro corpo vai para `undelivered.jsonl` (AC 122)
Proof: `uv run pytest tests/test_sinks_other.py -k slack_request_and_ok_body`

**C93** - `ntfy` e `slack` fazem retry em `429`, `500` e conexão recusada, e mandam `400`, `403` e `404` direto para `undelivered.jsonl` (AC 123)
Proof: `uv run pytest tests/test_sinks_other.py -k ntfy_slack_retry_table`

**C94** - Escrita do sink `file` em diretório sem permissão grava em `undelivered.jsonl` o erro do sistema, sem retry, e o exit do `run` não muda (AC 124)
Proof: `uv run pytest tests/test_sinks_other.py -k file_sink_write_failure`

**C95** - O serializador do config faz round-trip `tomllib.loads(dump(cfg)) == cfg` para um config com todas as chaves literais da door 3 e os 4 tipos de sink (door 3)
Proof: `uv run pytest tests/test_config.py -k roundtrip_door_3_all_keys`

**C96** - Carregar um config com `default_cli` fora de `installed`, ou com um id de tier fora dos descobertos, falha com mensagem que nomeia a chave; um config válido carrega (door 3, Relations)
Proof: `uv run pytest tests/test_config.py -k constraints_default_cli_and_discovered_ids`

**C97** - A chave de dedupe é `<task_id>:<event>:<discriminator>`, e uma segunda criação de `sent/<chave>` com `O_CREAT + O_EXCL` falha sem nova entrega (door 5)
Proof: `uv run pytest tests/test_delivery.py -k dedupe_key_format_and_excl`

### S5 - CLI, modelo e timeout da tarefa · ~5 arquivos · ~40 KB · ~10k

**C98** - `run` sem `--tool` lança a CLI de `setup.default_cli` (AC 78)
Proof: `uv run pytest tests/test_resolve.py -k default_cli_when_no_tool`

**C99** - `run --model m-1` passa exatamente `m-1` à CLI e o evento traz `model_source: "user"` (AC 79)
Proof: `uv run pytest tests/test_resolve.py -k explicit_model_passthrough`

**C100** - `run` sem `--model` usa o primeiro id de `cli.<tool>.tiers.<tier>`, com tier `standard` quando falta `--tier`, e `model_source: "tier"` (AC 80)
Proof: `uv run pytest tests/test_resolve.py -k first_tier_model_default_standard`

**C101** - Um modelo resolvido fora da lista descoberta, vindo de `--model` ou do tier, faz o `run` sair com `2` sem lançar e com `grokbot-kit setup models refresh <tool>` no stderr (AC 81)
Proof: `uv run pytest tests/test_run_guards.py -k undiscovered_model_exit_2`

**C102** - Uma tool fora de `setup.installed` faz o `run` sair com `2` sem lançar (AC 82)
Proof: `uv run pytest tests/test_run_guards.py -k tool_not_installed_exit_2`

**C103** - Sem `--timeout`, o timeout é `30m`, `2h` e `4h` para `trivial`, `standard` e `complex` (padrões e valores do config), e `--timeout 5s` prevalece (AC 83)
Proof: `uv run pytest tests/test_resolve.py -k timeout_per_tier_and_override`

**C104** - `setup models refresh opencode` grava como descobertos exatamente as linhas impressas pela `opencode models` falsa (AC 84)
Proof: `uv run pytest tests/test_models.py -k opencode_models_exact`

**C105** - `setup models refresh claude` grava `haiku`, `sonnet`, `opus` e só os ids adicionados que a `claude -p --model <id>` falsa aceitou (AC 85)
Proof: `uv run pytest tests/test_models.py -k claude_aliases_and_accepted_ids`

**C106** - `setup models refresh codex` grava só os ids que a `codex exec -m <id>` falsa aceitou sem erro de modelo (AC 86)
Proof: `uv run pytest tests/test_models.py -k codex_accepted_ids_only`

**C107** - No box, `setup models refresh` nas 3 CLIs reais grava pelo menos um id por CLI, e um `run --tier trivial` com o primeiro id lança sem erro de modelo (AC 84, 85, 86)
Proof: `uv run pytest -m integration tests/integration/test_real_cli.py -k models_refresh_real`

### S6 - timeout e interrupção · ~3 arquivos · ~25 KB · ~6k

**C108** - No timeout, o grupo do agente recebe `SIGINT`, `SIGTERM` 10 s depois e `SIGKILL` 10 s depois disso (CLI falsa que ignora os dois primeiros), o evento é `timeout`/`timeout`/`timeout`, o `run` sai com `124` e nenhum processo do grupo sobra (AC 87)
Proof: `uv run pytest tests/test_signals.py -k timeout_ladder_and_exit_124`

**C109** - `SIGINT` e `SIGTERM` no `run` são repassados ao grupo do agente, e geram `event: "error"`, `status: "interrupted"`, `exit_reason: "interrupted"` e exit `130` (AC 88)
Proof: `uv run pytest tests/test_signals.py -k sigint_sigterm_forwarded_exit_130`

**C110** - Com `cli.<tool>.bin` apontando para um caminho inexistente, o `run` gera `error`/`failed`/`agent_error` e sai com `127` (AC 89)
Proof: `uv run pytest tests/test_signals.py -k missing_binary_exit_127`

**C111** - `run --tool claude -- --bare` sai com `2`; `--bare` com `--tool opencode` não é recusado por essa regra (AC 90)
Proof: `uv run pytest tests/test_run_guards.py -k bare_rejected_for_claude`

### S7 - instalação, login, isolamento e manutenção · ~8 arquivos · ~70 KB · ~18k

**C112** - `setup cli add <tool>` roda o instalador oficial (falso), confirma com `<cli> --version`, grava `cli.<tool>.bin` e sai com `0`; com instalador falhando sai com `1`; com tool desconhecida sai com `2` (AC 91)
Proof: `uv run pytest tests/test_setup.py -k cli_add_exit_codes_and_bin`

**C113** - `login codex` roda `codex login --device-auth` (assinatura) ou `codex login --with-api-key` com a key do `secret_file` no stdin (api-key), sempre com `CODEX_HOME` do kit, e sai com `0`, ou `1` quando o comando falha (AC 92)
Proof: `uv run pytest tests/test_setup.py -k login_codex_methods_and_home`

**C114** - `login claude` roda `claude auth login` (assinatura) ou registra o `secret_file`, e o `run` passa `ANTHROPIC_API_KEY` só no env do processo do agente (AC 93)
Proof: `uv run pytest tests/test_setup.py -k login_claude_methods_and_env_scope`

**C115** - `login opencode` roda `opencode auth login`, e um setup só com opencode e sem login termina com `0` (AC 94)
Proof: `uv run pytest tests/test_setup.py -k login_opencode_and_free_without_login`

**C116** - `install opencode` roda 2 vezes, com e sem arquivo prévio, e deixa exatamente um `~/.config/opencode/plugins/grokbot-kit.ts` com o caminho absoluto do executável; sai com `1` em diretório sem escrita (AC 95)
Proof: `uv run pytest tests/test_opencode_plugin.py -k install_idempotent_abs_path`

**C117** - `uninstall opencode` remove o plugin e deixa intactos os outros arquivos de `~/.config/opencode/` (AC 96)
Proof: `uv run pytest tests/test_opencode_plugin.py -k uninstall_removes_only_plugin`

**C118** - No box, com o plugin instalado e sem `GROKBOT_KIT_TASK_ID`, um `opencode run` real não invoca o `grokbot-kit` (um shim no caminho absoluto registra zero chamadas) e sai como sem o plugin (AC 97)
Proof: `uv run pytest -m integration tests/integration/test_real_hooks.py -k opencode_plugin_inert_without_task`

**C119** - Depois de rodar `setup`, `login`, `install`, `run` nas 3 tools, `doctor` e `gc` num `HOME` isolado, `~/.claude/settings.json` e todo `~/.codex/` têm os mesmos hashes de antes (AC 98)
Proof: `uv run pytest tests/test_isolation.py -k user_claude_and_codex_untouched`

**C120** - Depois de `setup`, `login` e `run` com `codex`, o `config.toml` de `cli.codex.codex_home` não tem nenhuma chave `projects.*.trust_level` (AC 99)
Proof: `uv run pytest tests/test_isolation.py -k codex_home_never_trusts_projects`

**C121** - `doctor --json` lista a versão do kit e do Python e, por CLI, versão, login (`claude auth status`, `codex login status`, `opencode auth list`), se é a padrão e a contagem por tier; sai com `0` quando tudo está OK e `1` com um segredo `0644` ou uma CLI deslogada (AC 100)
Proof: `uv run pytest tests/test_doctor.py -k fields_and_exit_codes`

**C122** - `gc --older-than 30d` apaga a task terminada há 31 dias, preserva a terminada há 29 dias, a sem `finished_at` (em andamento) e a com `undelivered.jsonl` não vazio; `--dry-run` só lista; `--older-than xyz` sai com `2` (AC 101)
Proof: `uv run pytest tests/test_gc.py -k predicate_dry_run_and_invalid_duration`

**C123** - No box, `uv tool install --managed-python <wheel>` num `HOME` limpo cria `~/.local/bin/grokbot-kit` e `grokbot-kit --version` sai com `0`, sem pacote no Python do sistema (door 6)
Proof: `uv run pytest -m integration tests/integration/test_install.py -k uv_tool_install_isolated`

**C124** - O `task_id` casa com `^\d{8}T\d{6}-<label>-[0-9a-f]{6}$` e o task dir de uma task terminada tem `meta.json` com `finished_at`, `out.jsonl`, `stderr.log`, `events.jsonl`, `kit.log` e `sent/`, mais `claude-settings.json` quando a tool é `claude` (door 4)
Proof: `uv run pytest tests/test_taskdir.py -k task_id_format_and_layout`

**C125** - O agente lançado recebe no env `GROKBOT_KIT_TASK_ID`, `GROKBOT_KIT_TARGET`, `GROKBOT_KIT_LABEL` e `GROKBOT_KIT_TASK_DIR` com os valores da task, e `grokbot-kit --help` lista os 11 comandos do `Surface` (door 1)
Proof: `uv run pytest tests/test_launch.py -k env_contract_and_commands`

### S8 - skill `grokbot-kit` para qualquer Grok Bot · 2 arquivos · ~30 KB · ~8k

As provas do S8 são do nível do documento: afirmam o que o `SKILL.md` instrui, não o que um bot faz com ele. O comportamento de ponta a ponta é o teste independente do S8 (UAT manual com um Grok Bot) e não tem prova automatizada.

**C126** - O frontmatter tem `name: grokbot-kit` e uma `description` com os 3 gatilhos "configurar grokbot-kit", "delegar para opencode/claude/codex" e "rodar tarefa headless" (AC 102, door 8)
Proof: `uv run pytest tests/test_skill_doc.py -k frontmatter_name_and_triggers`

**C127** - O `SKILL.md` instrui instalar com `uv tool install --managed-python grokbot-kit`, ou `pipx install grokbot-kit` sem `uv`, como primeiro passo quando `grokbot-kit` não está no `PATH` (AC 103)
Proof: `uv run pytest tests/test_skill_doc.py -k install_first_step`

**C128** - O `SKILL.md` instrui, com `setup.installed` vazio no `doctor --json`, uma única pergunta de múltipla escolha entre `opencode`, `claude` e `codex` (AC 104)
Proof: `uv run pytest tests/test_skill_doc.py -k single_multichoice_cli_question`

**C129** - O `SKILL.md` instrui `grokbot-kit setup cli add` e, por CLI, perguntar assinatura ou API key e rodar `grokbot-kit login` (AC 105)
Proof: `uv run pytest tests/test_skill_doc.py -k cli_add_and_login_per_cli`

**C130** - O `SKILL.md` proíbe pedir key, sender key ou URL secreta no chat e instrui `grokbot-kit secret set <name>` com o valor na entrada padrão, vindo das ferramentas do bot ou de um campo mascarado de segredos, nunca como argumento, e o terminal do box só sem campo mascarado (AC 106; revisada pela AD-031)
Proof: `uv run pytest tests/test_skill_doc.py -k never_ask_secret_in_chat`

**C131** - O `SKILL.md` instrui, diante de segredo colado ou print com a key, avisar para regenerar no painel e gravar de novo com `grokbot-kit secret set`, sem gravar nem repetir o valor (AC 107)
Proof: `uv run pytest tests/test_skill_doc.py -k leaked_secret_handling`

**C132** - O `SKILL.md` instrui perguntar a CLI padrão e gravar com `grokbot-kit setup default <tool>` (AC 108)
Proof: `uv run pytest tests/test_skill_doc.py -k default_cli_step`

**C133** - O `SKILL.md` instrui `grokbot-kit setup models refresh` e propor tiers só com ids descobertos, com os gratuitos do opencode primeiro em `trivial` e `standard` (AC 109)
Proof: `uv run pytest tests/test_skill_doc.py -k models_refresh_and_free_first`

**C134** - O `SKILL.md` instrui criar a routine com webhook trigger, `grokbot-kit secret set <bot>-url` e `grokbot-kit secret set <bot>-key` pela entrada padrão, preferindo ler os valores da routine, depois um campo mascarado de segredos e só então o terminal do box, e `grokbot-kit route add` e `grokbot-kit route test`, nessa ordem (AC 110; revisada pela AD-031)
Proof: `uv run pytest tests/test_skill_doc.py -k routine_setup_order`

**C135** - No `SKILL.md`, o aviso de que a key não pode aparecer em print, colagem ou mensagem vem antes do passo de abrir o painel da routine (AC 111)
Proof: `uv run pytest tests/test_skill_doc.py -k print_warning_before_panel`

**C136** - O prompt de routine proposto no `SKILL.md` faz parse de `body` como JSON, confere `schema: "grokbot-kit.event/v1"` e ignora `target` diferente do bot (AC 112)
Proof: `uv run pytest tests/test_skill_doc.py -k routine_prompt_parse_schema_target`

**C137** - O `SKILL.md` instrui `grokbot-kit run --tool <cli> --model <id> --target <este bot>` quando o usuário pede CLI e modelo (AC 113)
Proof: `uv run pytest tests/test_skill_doc.py -k run_with_tool_and_model`

**C138** - O `SKILL.md` instrui omitir `--tool` quando o usuário não pede CLI (AC 114)
Proof: `uv run pytest tests/test_skill_doc.py -k omit_tool_for_default`

**C139** - O `SKILL.md` instrui classificar em `trivial`, `standard` ou `complex`, passar `--tier <tier>` e citar a classe em uma linha quando não há modelo (AC 115)
Proof: `uv run pytest tests/test_skill_doc.py -k tier_classification_one_line`

**C140** - A rubrica do `SKILL.md` classifica como `complex` as 4 classes revisão de segurança, decisões de arquitetura, checagem de fatos e o que toca produção, credenciais ou dados sensíveis, e proíbe mandá-las a modelos gratuitos (AC 116)
Proof: `uv run pytest tests/test_skill_doc.py -k rubric_complex_classes_never_free`

**C141** - O `SKILL.md` instrui fazer parse de `body`, ler `event`, `status`, `summary` e `output_file`, e diante de `needs_input` ou `denied` mostrar o pedido e oferecer `resume_hint` (AC 117)
Proof: `uv run pytest tests/test_skill_doc.py -k event_handling`

**C142** - O `SKILL.md` instrui checar `undelivered.jsonl` no task dir e oferecer `grokbot-kit redeliver <task_id>` quando um evento não chegou (AC 118)
Proof: `uv run pytest tests/test_skill_doc.py -k undelivered_and_redeliver`

**C143** - Todo comando `grokbot-kit <subcomando>` citado no `SKILL.md` existe (`grokbot-kit <subcomando> --help` sai com `0`), e o `SKILL.md` proíbe inventar id de modelo, comando ou flag (AC 119)
Proof: `uv run pytest tests/test_skill_doc.py -k every_cited_command_exists`

**C144** - O `SKILL.md` instala copiando a pasta para o diretório de workflows do Grok Bot (`/home/box/agent-data/workflows/grokbot-kit/` no box) e só chama comandos `grokbot-kit`, `uv`/`pipx` e as CLIs oficiais (door 8)
Proof: `uv run pytest tests/test_skill_doc.py -k install_location_and_allowed_commands`

**C145** - A rubrica e os exemplos do `SKILL.md` não citam nenhum id de modelo literal; ids só vêm de `setup models refresh` (AC 109, AC 119, AD-011)
Proof: `uv run pytest tests/test_skill_doc.py -k no_literal_model_ids`

### Acréscimos da verificação (rodada 1, 20/10/2026, aprovados pelo Rodrigo)

O Verifier achou a door 22 sem check e recusas do `run` e a door 13 sem prova; estes checks são aditivos e não mudam nenhum aprovado.

**C146** - `grokbot-kit setup tiers <tool> <tier> <id>...` grava `[cli.<tool>.tiers] <tier>` com os ids na ordem dada, sem mexer no resto do config, e sai com `0`; sai com `2`, sem mudar o config, com tool fora de `setup.installed` (citando `grokbot-kit setup cli add <tool>`), id fora de `[cli.<tool>] models` (citando o id e `grokbot-kit setup models refresh <tool>`), tool ou tier desconhecido ou nenhum id (door 22)
Proof: `uv run pytest tests/test_setup_tiers.py -k setup_tiers`

**C147** - O `run` sai com `2` antes de criar task dir, lançar o agente ou enviar evento, citando a causa em stderr, quando a rota usa um sink fora de `[sinks]`, o `--label` foge de `^[A-Za-z0-9][A-Za-z0-9._-]*$`, o `--cwd` não é diretório ou o `--prompt-file` não pode ser lido (AC 47, Test policy "Ponto de entrada que não decide")
Proof: `uv run pytest tests/test_run_guards.py -k other_refusals_exit_2`

**C148** - `--prompt-file <f>` acrescenta o conteúdo de `<f>` como último argumento da CLI, depois dos extras de `--` (door 13)
Proof: `uv run pytest tests/test_run_guards.py -k prompt_file_appended_last`

### Acréscimos depois do UAT do S8 (21/10/2026, aprovados pelo Rodrigo)

A AD-032 abre a door 23; este check é aditivo e não muda nenhum aprovado.

**C149** - O job `publish` do `release.yml` faz checkout de `skills/grokbot-kit/SKILL.md` e o `gh release create` anexa esse arquivo junto com `dist/*`, sem que ele entre no artefato `dist` enviado ao PyPI; os dois READMEs baixam a skill de `https://github.com/rodrigo-pasini/grokbot-kit/releases/latest/download/SKILL.md` e de nenhuma URL com tag (AC 125, door 23)
Proof: `uv run pytest tests/test_workflows.py -k release_attaches_skill`

A AD-033 abre a door 24; o C115 e o C121 continuam iguais, e os seus cenários de `doctor` com exit `0` passam a ter o plugin instalado (`grokbot-kit install opencode`, como no setup da skill), porque sem ele a door 24 aponta um problema real.

**C150** - Com `opencode` em `setup.installed`, `doctor --json` sai com `0` e `cli.opencode.plugin.ok` `true` depois de `grokbot-kit install opencode`; sai com `1`, `exe` `null` e um problema citando `grokbot-kit install opencode` sem o arquivo do plugin; e sai com `1`, `ok` `false`, `exe` igual ao caminho gravado e um problema citando esse caminho e `grokbot-kit install opencode` quando o plugin chama outro executável; sem `opencode` instalado não há `plugin` nem problema de plugin (AC 126, door 24)
Proof: `uv run pytest tests/test_doctor.py -k opencode_plugin`

A rodada 3 do Verifier achou o membro "arquivo sem a linha" da door 24 sem prova (AD-035); este check é aditivo.

**C151** - Com `opencode` em `setup.installed` e o arquivo do plugin presente sem a linha `const GROKBOT_KIT = "<caminho>"`, com essa linha trazendo um valor que não é string JSON, ou ilegível, `doctor --json` sai com `1`, `cli.opencode.plugin.exe` `null`, `ok` `false` e um problema citando `grokbot-kit install opencode` (AC 126, door 24)
Proof: `uv run pytest tests/test_doctor.py -k plugin_without_exe_line`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `POST https://api2.cursor.sh/automations/webhook/<routine-uuid>`: classes de resposta (7) | `2xx` com recibo C80 · `2xx` sem recibo C81 · `401` C84 · `429` C83 · `500`-`599` C83 · `400`/`403`/`404`/outros `4xx` C84 · falha de conexão C83 | - |
| `grokbot-kit run`: exit codes (5) | espelho do agente C54 · `124` C108 · `130` C109 · `2` C76 · `127` C110 | - |
| `grokbot-kit run`: causas de exit `2` (5) | target C76 · segredo C77 · modelo C101 · tool C102 · `--bare` C111 | - |
| `grokbot-kit emit`: exit (1) | sempre `0` C72 | - |
| `grokbot-kit redeliver`: exit codes (3) | `0` C85 · `1` C85 · `2` C85 | - |
| `grokbot-kit gc`: exit codes (2) | `0` C122 · `2` C122 | - |
| `grokbot-kit setup`: exit codes (3) | `0` C112 · `1` C112 · `2` C112 | - |
| `grokbot-kit login`: exit codes (2) | `0` C113 · `1` C113 | - |
| `grokbot-kit secret set`: exit codes (2) | `0` C88 · `1` C88 | - |
| `grokbot-kit route`: exit codes (3) | `0` C87 · `1` C87 · `2` C87, C89 | - |
| `grokbot-kit doctor`: exit codes (2) | `0` C121 · `1` C121 | - |
| `grokbot-kit install/uninstall opencode`: exit codes (2) | `0` C116 · `1` C116 | - |
| `event` (5) | `completed` C46 · `error` C49 · `timeout` C108 · `needs_input` C63 · `test` C87 | - |
| `status` (8) | `ok` C46 · `denied` C47 · `failed` C49 · `interrupted` C109 · `timeout` C108 · `permission` C63 · `question` C65 · `test` C87 | - |
| `exit_reason` (7) | `success` C46 · `permission_denied` C47 · `agent_error` C49 · `nonzero_exit` C49 · `timeout` C108 · `interrupted` C109 · `needs_input` C61 | - |
| condições de erro do AC 45 (5) | C49, table-driven over all 5 | - |
| tools: argv de lançamento (3) | `claude` C43 · `opencode` C44 · `codex` C45 | - |
| tools: lançamento real no box (3) | C55, table-driven over all 3 | - |
| tools: fonte do `summary` (3) | C51, table-driven over all 3 | - |
| tools: `resume_hint` (3) | C59, table-driven over all 3 | - |
| `summary`: borda de 2000 (3 edges) | 1999 C51 · 2000 C51 · 2001 C51 | - |
| fontes de `needs_input` (4) | Claude `PermissionRequest` C63, C67 · opencode `permission.asked` C64, C68 · opencode `question.asked` C65 (no box o `opencode run` não publica o evento: C68, AD-026) · Codex `PermissionRequest` C66 (no box o `codex exec` não chama o hook: C69, AD-027) | - |
| tipos de sink (4) | `grokbot-routine` C78 · `file` C90 · `ntfy` C91 · `slack` C92 | - |
| tiers: timeout (3) | `trivial` C103 · `standard` C103 · `complex` C103 | - |
| descoberta de modelos por CLI (3) | `opencode` C104 · `claude` C105 · `codex` C106 | - |
| login por CLI (3) | `codex` C113 · `claude` C114 · `opencode` C115 | - |
| predicado do `gc` (4) | terminada e antiga C122 · terminada e recente C122 · em andamento C122 · `undelivered.jsonl` não vazio C122 | - |
| doors (24) | 1 C125 · 2 C57 · 3 C95 · 4 C124 · 5 C97 · 6 C123 · 7 C45 · 8 C144 · 9 C3 · 10 C23 · 11 C21, C29, C33, C35, C36 · 12 C104 · 13 C111, C148 · 14 C63-C70 · 15 C80, C84 · 16 C104-C106 · 17 C103, C122 · 18 C108-C110 · 19 C112 · 20 C113, C114 · 21 C121 · 22 C146 · 23 C149 · 24 C150, C151 | - |
| Relations: constraints one-way (5) | um terminal por task C52 · chave de dedupe única C97 · `target` existe antes de lançar C76 · `default_cli` em `installed` C96 · ids de tier descobertos C96, C101 | - |
| Relations: entidades (10) | `Config` C95 · `CliProfile` C112 · `ModelTier` C100 · `TierTimeout` C103 · `Route` C76 · `Sink` C78 · `Task` C124 · `Event` C56 · `TerminalEvent` C52 · `Delivery` C80 | - |
| startup config: hook do kit registrado (3 lugares) | `--settings` do Claude C43 · `-c` inline do Codex C45 · plugin global do opencode C116 | - |
| CI: jobs obrigatórios (5) | C13, table-driven over all 5 | - |
| labels da door 11 (9) | C36, table-driven over all 9 | - |
| `README.md`: seções (8) | C5, table-driven over all 8 | - |
| `.gitignore`: padrões (10) | C16, table-driven over all 10 | - |
| rubrica `complex` (4 classes) | C140, table-driven over all 4 | - |
| `grokbot-kit setup tiers`: exit codes (2) | `0` C146 · `2` C146 | - |
| `grokbot-kit run`: demais recusas com `2` (4) | sink fora de `[sinks]` C147 · `--label` inválido C147 · `--cwd` não diretório C147 · `--prompt-file` ilegível C147 | - |
| door 13: repasse à CLI (2) | extras depois de `--` C148 · conteúdo do `--prompt-file` por último C148 | - |
| door 23: onde a skill aparece (2) | arquivo `SKILL.md` no GitHub Release C149 · URL `latest` nos dois READMEs C149 | - |
| door 24: estado do plugin do opencode (5) | instalado e atual C150 · ausente C150 · presente sem a linha do executável C151 · outro executável C150 · `opencode` fora de `setup.installed` C150 | - |

- Claims que nomeiam status HTTP, exit code ou forma de resposta: C54, C72, C76-C94, C101-C122 - cada um tem prova que cruza a fronteira (receptor HTTP local ou subprocesso do executável)
- Nenhum outro check afirma mais do que o caso único que a sua prova exercita

## Test policy

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

## Swept

- validation: C76, C77, C89, C101, C102, C111, C122 (duração inválida), C96
- failure modes: C84, C94, C110, C72, C81
- idempotency: C70, C97, C116, C85
- authorization: C78, C82, C88, C89 - `Authorization: Bearer` lido de segredo `0600`; rate limit da routine: C83 (`429` com retry)
- concurrency: C73, C86, C52
- data lifecycle: C122, C124 - task dirs guardados até o `gc` manual; nada expira sozinho (Out of scope)
- dependency failure: C83, C93, C112, C110
- state transitions: C46-C50 (tabela de status terminal e precedência), C52 (um terminal por task), C61
- observability: C79 (`body_digest` em `events.jsonl`), C80 (recibo `run_uuid`), C121 (`doctor`), C124 (`kit.log`, `stderr.log`); meta de serviço do `emit` sem task (mediana ≤ 50 ms em 20 execuções no box) é medida no build com `hyperfine` e registrada no relatório, sem check

## Handoff

Os arquivos ainda não existem, então o tamanho é projetado: KB estimados por slice ÷ 4, mais a leitura fixa de `plan.md` (65 921 bytes ≈ 16k) e deste `checks.md` (≈ 45 KB ≈ 11k).

- S0 = 11k; S1 entra no núcleo do kit e chega a 26k; S2 a 34k; S3 a 47k; S4 a 72k; S5 a 82k; S6 a 88k; S7 a 106k; S8 a 114k; com a leitura fixa (27k), 141k, abaixo do budget de 150k → um builder
- Mechanism: um builder (estimativa cabe no budget; margem de 9k)
- As etapas do S0 que mexem no GitHub (C24-C36, C40: `gh repo create`, `gh repo edit`, `git push`, proteção, environment, labels) são outward-facing e esperam o "pode" explícito do Rodrigo para essa ação, mesmo com a spec aprovada
- C66 e C69 dependiam da pergunta 2: o spike de 19/10/2026 mostrou que o hook não dispara em `codex exec`; voltou ao plano, e a AC 57, o C55 e o C69 foram reescritos pela AD-027 com o ok do Rodrigo
- Lote C95-C107 (20/10/2026, resto do S4 e o S5): arquivos tocados ≈ 40 KB existentes (`config.py`, `run.py`, `cli.py`, `deliver.py`, `launch.py`, `conftest.py`, `test_run_guards.py`, a CLI falsa e `test_real_cli.py`) mais ≈ 25 KB novos (módulo de descoberta de modelos e 4 arquivos de teste) = 65 KB ≈ 16k, mais a leitura fixa de `plan.md` (69 KB) e deste arquivo (48 KB) ≈ 29k: 45k, abaixo do budget de 150k
- Mechanism (lote C95-C107): um builder
- Lote S6 (C108-C111, 20/10/2026): coberto pela estimativa original (S6 a 88k acumulados); arquivos tocados no fim do build ≈ 52 KB (`run.py`, `terminal.py`, a CLI falsa, `test_run_guards.py`, `test_signals.py`, `CHANGELOG.md`) ≈ 13k, mais a leitura fixa de `plan.md` e deste arquivo ≈ 29k: 42k, abaixo do budget de 150k
- Mechanism (lote S6): um builder
- Lote S7 (C112-C125, 20/10/2026): arquivos existentes tocados ≈ 62 KB (`cli.py`, `run.py`, `models.py`, `launch.py`, `config.py`, a CLI falsa, `conftest.py`, `test_launch.py`, `test_real_hooks.py`, `test_real_cli.py`, `CHANGELOG.md`) mais ≈ 58 KB novos (módulos de setup, login, plugin, doctor e gc; o instalador falso; 6 arquivos de teste e `tests/integration/test_install.py`) = 120 KB ≈ 30k, mais a leitura fixa de `plan.md` (72 KB) e deste arquivo (49 KB) ≈ 30k: 60k, abaixo do budget de 150k
- Mechanism (lote S7): um builder
- Lote S8 (C126-C145, 20/10/2026): arquivos tocados ≈ 49 KB (`SKILL.md`, `tests/test_skill_doc.py`, e pela door 22 `setup.py`, `cli.py`, `tests/test_setup_tiers.py` e `CHANGELOG.md`) ≈ 12k, mais a leitura fixa de `plan.md` (78 KB) e deste arquivo (50 KB) ≈ 32k: 44k, abaixo do budget de 150k
- Mechanism (lote S8): um builder
- Revisão AD-031 (21/10/2026, depois do UAT do S8): C130 e C134 reescritas com o ok do Rodrigo; arquivos tocados ≈ 30 KB (`SKILL.md`, `tests/test_skill_doc.py`, os dois READMEs, `CHANGELOG.md`) ≈ 8k, mais a leitura fixa ≈ 32k: 40k, abaixo do budget de 150k
- Mechanism (revisão AD-031): um builder
- Door 23 (AD-032, 21/10/2026): arquivos tocados ≈ 12 KB (`release.yml`, `tests/test_workflows.py`, os dois READMEs) ≈ 3k, mais a leitura fixa ≈ 32k: 35k, abaixo do budget de 150k; um builder
- Door 24 (AD-033, 21/10/2026): arquivos tocados ≈ 25 KB (`doctor.py`, `tests/test_doctor.py`, `CHANGELOG.md`) ≈ 6k, mais a leitura fixa ≈ 33k: 39k, abaixo do budget de 150k; um builder
- Rodada 3 do Verifier (AD-035, 21/10/2026): arquivos tocados ≈ 20 KB (`tests/test_doctor.py`, `tests/test_workflows.py`) ≈ 5k, mais a leitura fixa ≈ 33k: 38k, abaixo do budget de 150k; um builder
