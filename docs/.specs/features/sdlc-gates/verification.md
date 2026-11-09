# sdlc-gates verification

**Verdict**: PASS
**Profile**: standard
**Diff range**: 15398f3..72c9a34
**Round**: 11 - scoped
**Verifier**: independent sub-agent (author != verifier)

Resumo: os 57 checks têm evidência localizada e as provas passam em `72c9a34` (ver `## Gate`). O N5 da rodada 10 fecha:
`git push --follow-tags`, `git push --follow-tags origin`, `git push origin +v0.6.0` e `git push origin +refs/tags/v0.6.0`
agora casam um `ask` (`.claude/settings.json:36`, `:42`, `:43`), cada um com um comando concreto em
`test_settings_permissions_ask_covers` (`tests/test_claude_hooks.py:107-111`). Os 5 mutantes desta rodada morrem. A
afirmação da AD-054 no `plan.md:73` ("por qualquer forma de `git push` (`--tags`, `--follow-tags`, `v*`, `refs/tags/`,
`<src>:v*`, `:<tag>`, `+<tag>`, `--mirror`), pede") e a do `AGENTS.md:36` ("push de tag (até por refspec,
`--follow-tags` ou `--mirror`)") batem com o conjunto de regras no emulador do teste, para todas as formas listadas. Sobram
só os limites já aceitos (emulador no lugar do Claude Code real, refs entre aspas, corpo do PR, C25 com push pendente),
nenhum bloqueante.

Escopo da rodada 11: `8869b67` (`plan.md:73`, door 6 `:94` e AC 20 `:147` com as 17 regras; C27 e `Coverage` do
`checks.md`; AD-054 em `STATE.md:60`; lição L-025) e `72c9a34` (`.claude/settings.json` ganha `Bash(git push
--follow-tags *)` em `:36`, `Bash(git push *+v*)` em `:42` e `Bash(git push *+refs/tags/*)` em `:43`;
`tests/test_claude_hooks.py` ganha as 3 regras no `ASK` e 5 comandos no `ask_covers`; `AGENTS.md:35-40`). O intervalo
`5842494..72c9a34` não toca `tools/`, `.pre-commit-config.yaml`, `.claude/hooks/`, `.github/`, `CONTRIBUTING.md`,
`docs/pt-BR/`, `tests/test_sdlc.py`, `tests/test_docs.py`, `tests/test_agents_md.py` nem `tests/test_repo_files.py`.
Verifiquei por inteiro C27 e C29 (settings e teste mudaram), C26 e C41-C43 só com citações atualizadas (as linhas de
`tests/test_claude_hooks.py` desceram 3 até `:130` e 8 a partir de `:133`), e os checks de doc que leem o `AGENTS.md`
(C34-C36, C45, C47, C48). O resto é `carried from 5842494`, com as provas rodadas de novo.

Como as provas rodaram (`verified at 72c9a34`):

- **Lote A**: uma invocação, `uv run pytest -rA -p no:cacheprovider` (a suíte inteira, que contém todas as provas pytest
  do `checks.md`), numa worktree de rascunho (`git worktree add --detach <scratchpad>/mut11 HEAD`), com este relatório
  (PASS) copiado no lugar. Resultado em `## Gate`. Contagem `PASSED` das provas tocadas: `test_settings_registers_hooks`
  1, `test_settings_permissions_ask` 1, `test_settings_permissions_ask_covers` 20, `test_settings_permissions_allow` 1.
- **C25, C30, C32, C45**: comandos que não são pytest. C25: `gh pr checks` é do head do PR, que não mudou (`df8b3a4`);
  reproduzi o job `process` em `72c9a34` (ver `## Gate`). C30 é `carried from eaa574f` (rodada 9, ao vivo); por pedido,
  sem `gh api` nesta rodada, e nada de que ele depende mudou. C32 e C45 são `carried from b852e33`.
- Nenhum `git push`, `git tag`, `gh release`, `gh pr merge` ou `gh api` rodou nesta rodada. O casamento das regras é
  provado pelo emulador do teste (`matches`, `tests/test_claude_hooks.py:57-64`), não pelo Claude Code real (N3).

## Binding sources

`carried from 5842494`. Fora do perfil (`standard`).

| Source | Opened | Contradiction | Uncovered |
| --- | --- | --- | --- |
| doc `memory#agents-md` | não aberta (perfil standard); comportamento conferido pelo `claude` 2.1.312 real (C45) | none | - |
| decisões de 29/10/2026, review do PR #34, AD-053 e AD-054 | via plano (`Landing` door 6 `:94`, `Surface` `:72-73`, AC 20-23 `:147-150`) e `docs/.specs/STATE.md:59-60` | none | - |
| doc `code.claude.com/docs/en/permissions.md` | lida na rodada 9 (carried) | none: forma `Bash(cmd *)`, `ask` vale para qualquer subcomando, ordem deny -> ask -> allow, ` *` no fim aceita o comando sem argumento | - |

## Checks

Proofs `verified at 72c9a34` (lote A). C26, C27, C29 e C41-C43 têm citações atualizadas. Os outros são `carried from
5842494` (citações de `tests/test_sdlc.py`, `tests/test_docs.py`, `tests/test_agents_md.py`, `tests/test_workflows.py` e
`tests/test_repo_files.py` sem mudança, porque esses arquivos não foram tocados), e as provas rodaram de novo.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | `default_install_hook_types` e os 3 hooks criados (carried) | lote A `test_precommit_installs_three_hook_types` PASSED | `tests/test_sdlc.py:206` - `config["default_install_hook_types"] == ["pre-commit", "commit-msg", "pre-push"]`; `:209` - `(repo / ".git" / "hooks" / hook).is_file()` | PASS |
| C2 | hooks `sdlc-*` nas stages certas, mesmo `exclude` (carried) | lote A `test_precommit_hooks`, `test_sdlc_hooks_stages` PASSED | `tests/test_repo_files.py:150` - `hook["stages"] == [stage]`; `:151`; `:152`/`:137` - `hook.get("exclude") == PRECOMMIT_EXCLUDE` | PASS |
| C3 | 11 tipos, com/sem escopo, `!`, 100 caracteres -> `0` sem saída (carried) | lote A `test_commit_msg_accepts[*]` (45) PASSED | `tests/test_sdlc.py:99-100` - `returncode == 0`, `result.stdout == "" and result.stderr == ""`; `:91` - `len(first) == 100` | PASS |
| C4 | 6 rejeições, regex em stderr (carried) | lote A `test_commit_msg_rejects[*]` (6) PASSED | `tests/test_sdlc.py:109-110` - `returncode == 1`, `DOOR_3 in result.stderr` | PASS |
| C5 | `Co-authored-by` em 3 caixas -> `1` e a linha (carried) | lote A `test_commit_msg_coauthor[*]` (3) PASSED | `tests/test_sdlc.py:117-118` - `returncode == 1`, `line in result.stderr` | PASS |
| C6 | 3 aceitas, 6 recusadas com os 3 padrões (carried) | lote A `test_branch_pattern[*]` (9) PASSED | `tests/test_sdlc.py:171` - `returncode == 0`; `:174-176` - `returncode == 1`, `pattern in result.stderr` | PASS |
| C7 | `pre-push` real recusa `feat/sdlc`, aceita `feat/31/sdlc` (carried) | lote A `test_pre_push_hook_blocks` PASSED | `tests/test_sdlc.py:258-259` - `refused.returncode != 0`, `not remote_has("feat/sdlc")`; `:262-263` - `accepted.returncode == 0`, `remote_has("feat/31/sdlc")` | PASS |
| C8 | commit em `main` -> `1` com a mensagem (carried) | lote A `test_pre_commit_on_main` PASSED | `tests/test_sdlc.py:275-276` - `returncode == 1`, `MAIN_MSG in result.stderr` | PASS |
| C9 | clone principal: código listado; 6 caminhos livres; worktree linkada passa (carried) | lote A `test_pre_commit_main_clone` PASSED | `tests/test_sdlc.py:291-292`; `:299` - `allowed.returncode == 0`; `:306` - `linked.returncode == 0` | PASS |
| C10 | escape libera o clone, não `main` (carried) | lote A `test_pre_commit_allow_main_edit` PASSED | `tests/test_sdlc.py:315` - `.returncode == 0`; `:318-319` - `on_main.returncode == 1`, `MAIN_MSG in on_main.stderr` | PASS |
| C11 | sem subcomando / desconhecido -> `2` e uso (carried) | lote A `test_usage_exit_2[*]` (2) PASSED | `tests/test_sdlc.py:326-327` - `returncode == 2`, `"usage:" in result.stderr` | PASS |
| C12 | job `process`, triggers, `fetch-depth: 0`, `--base` = base SHA (carried) | lote A `test_process_job` PASSED | `tests/test_workflows.py:166`, `:168`, `:170`; `:174` - `step["env"][base.group(1)] == "${{ github.event.pull_request.base.sha }}"` | PASS |
| C13 | título/branch/corpo só por `env:` (carried) | lote A `test_process_job_no_expression_in_run` PASSED | `tests/test_workflows.py:183` - `expression not in run`; `:187` - `expression in values` | PASS |
| C14 | título fora da door 3 -> `1` nomeando; bom -> `0` (carried) | lote A `test_pr_title` PASSED | `tests/test_sdlc.py:493` - `ok.returncode == 0`; `:496-497` - `bad.returncode == 1`, `"ajusta coisa" in bad.stderr` | PASS |
| C15 | branch fora da door 2 -> `1` nomeando (carried) | lote A `test_pr_branch` PASSED | `tests/test_sdlc.py:514-515` - `returncode == 1`, `"feat/sdlc" in result.stderr` | PASS |
| C16 | coautor em commit (SHA) e no corpo (carried) | lote A `test_pr_coauthor` PASSED | `tests/test_sdlc.py:523-524` - `returncode == 1`, `sha in in_commit.stderr`; `:529-530` - `"body" in in_body.stderr.lower()` | PASS |
| C17 | `Closes/Fixes/Refs #31` passam; sem, `#32`, `#310` falham; dependabot/release sem link passam (carried) | lote A `test_pr_issue_link[*]` (8) PASSED | `tests/test_sdlc.py:552` - `(result.returncode == 0) is ok`; `:554` - `result.returncode == 1` | PASS |
| C18 | `spec` roda os 3 validadores com `--root docs` só para os presentes (carried) | lote A `test_spec_runs_validators` PASSED | `tests/test_sdlc.py:357` - `ok.returncode == 0`; `:362-363` - `returncode == 1`, `"validate_checks.py" in bad.stderr`; `:369` - `alone.returncode == 0`; `:378-380` - `bad_verification.returncode == 1`, `"validate_verification.py" in ...`, `"validate_checks.py" not in ...` | PASS |
| C19 | dois validadores falhando, os dois nomeados (carried) | lote A `test_spec_reports_every_failure` PASSED | `tests/test_sdlc.py:391-393` - `returncode == 1`, `"validate_plan.py" in result.stderr`, `"validate_checks.py" in ...` | PASS |
| C20 | `pr` roda `spec` só das features tocadas (carried) | lote A `test_pr_specs_of_touched_features` PASSED | `tests/test_sdlc.py:566` - `untouched.returncode == 0`; `:572-573` - `touched.returncode == 1`, `"nova" in touched.stderr and "validate_checks.py" in touched.stderr` | PASS |
| C21 | código sem `verification.md` -> `1` com a mensagem; com, passa; só pyproject/uv.lock/CHANGELOG passa (carried) | lote A `test_pr_requires_verification[*]` (2), `test_pr_requires_verification_not_for_release` PASSED | `tests/test_sdlc.py:583-584` - `missing.returncode == 1`, `NO_VERIFICATION in missing.stderr`; `:588` - `verified.returncode == 0`; `:603` - `result.returncode == 0` | PASS |
| C22 | `plan.md` tocado sem `**Approved**` logo abaixo do título -> `1`; data inválida -> `1`; intocado não reprova (carried) | lote A `test_pr_plan_approved` PASSED | `tests/test_sdlc.py:627` - `ok.returncode == 0`; `:630`, `:634` - `pr.run().returncode == 1`; `:639` - `not below.split("\n", 3)[2].startswith("**Approved**")`; `:641`, `:646` - `== 1`. O `plan.md` desta feature mantém `**Approved**: 2026-10-29` em `:3` (ver N6) | PASS |
| C23 | `## Handoff` 40 -> `0`, 41 -> `1`, e `pr` reprova com 41 (carried) | lote A `test_state_handoff_limit` PASSED | `tests/test_sdlc.py:429` (40) e `:431` - `== 0`; `:433` - `== 1` (41); `:437` - `pr.run().returncode == 1` | PASS |
| C24 | 6 checks com `process`/`15368`, resto da door 11 (carried) | lote A `test_repo_settings_payloads_match_door_11` PASSED | `tests/test_repo_files.py:261` - `json.loads(read(".github/repo-settings/main-protection.json")) == MAIN_PROTECTION`, com `{"context": "process", "app_id": 15368}` em `:233` | PASS |
| C25 | o PR desta feature passa no `process` | `gh pr checks 34` (carried from eaa574f: o head do PR segue `df8b3a4`); reprodução do job em `72c9a34` nesta rodada: exit `0` | `gh pr view 34 --json headRefOid` = `df8b3a48fd0b41cac33507ac7987a4c4c3f6fa8b`, com os 6 `SUCCESS` registrados na rodada 9. **Push pendente**: o PR está 21 commits atrás de `72c9a34`. Reprodução: `uv run python tools/sdlc.py pr --title "feat(sdlc): gates do fluxo de desenvolvimento conferidos por máquina" --branch feat/31/sdlc-gates --body-file <corpo atual do PR 34> --base 15398f38d4fa742178e914debf5e2d231f08eb82` na worktree de rascunho, com este relatório no lugar (ver `## Gate`). O corpo do PR ainda descreve o `gate-humano.sh` (N4) | PASS |
| C26 | sem `PreToolUse` em `Bash`; `gate-worktree.sh` nos 4 nomes de `Edit`; `session-start.sh` em `SessionStart`; `gate-humano.sh` não existe (citação atualizada, +3 linhas) | lote A `test_settings_registers_hooks` PASSED; M3 da rodada 9 (carried; `hooks` intocado) | `tests/test_claude_hooks.py:80` - `assert not commands("PreToolUse", "Bash")`; `:81` - `any("gate-worktree.sh" in c for c in commands("PreToolUse", ...))` com o matcher dos 4 nomes de edição; `:83` - `any("session-start.sh" in c for c in session)`; `:84` - `not (ROOT / ".claude" / "hooks" / "gate-humano.sh").exists()`. Código: `.claude/settings.json:13-23`, matcher em `:15` | PASS |
| C27 | `permissions.ask` é exatamente as 17 regras, e nenhuma casa `git tag`, `git tag -l 'v0.0.0*'`, `git tag --list` (AC 20; verificado por inteiro) | lote A `test_settings_permissions_ask` PASSED, mais `test_settings_permissions_ask_covers[*]` (20), que o `-k settings_permissions_ask` também seleciona; M1-M4 morrem | `tests/test_claude_hooks.py:89` - `assert settings()["permissions"]["ask"] == ASK`, com `ASK` literal em `:31-49`, na mesma ordem e com o mesmo texto das 17 regras da C27, da AC 20 (`plan.md:147`) e da door 6 (`plan.md:94`); `:90-91` - `assert not any(matches(rule, command) for rule in ASK), command` para os 3 comandos `git tag`; `:120` - `any(matches(rule, command) for rule in ASK), command` para 20 comandos, entre eles `git push --follow-tags` (`:107`), `git push --follow-tags origin` (`:108`), `git push origin --follow-tags` (`:109`), `git push origin +v0.6.0` (`:110`), `git push origin +refs/tags/v0.6.0` (`:111`). Código: `.claude/settings.json:30-48` | PASS |
| C28 | `git push origin main` e `HEAD:main` num clone com hooks saem `!= 0`, o remoto não ganha `main`, `branch main` sai `1` (AC 21; carried from 5842494) | lote A `test_pre_push_refuses_main` PASSED; M4 e M5 da rodada 9 (carried; `tools/` e `.pre-commit-config.yaml` intocados) | `tests/test_sdlc.py:226` - `result.returncode != 0, refspec` para `("main", "HEAD:main")` em `:222`; `:230` - `"refs/heads/main" not in heads`; `:231` - `sdlc("branch", "main", cwd=tmp_path).returncode == 1` | PASS |
| C29 | `permissions.allow` é exatamente `Bash(git push *)` e `Bash(gh pr create *)`, e nenhuma casa `gh pr merge 34`, `git tag v1`, `gh release create v1` (AC 22; reverificado com as 3 regras novas) | lote A `test_settings_permissions_allow` PASSED; M5 desta rodada morre | `tests/test_claude_hooks.py:126` - `assert allow == ALLOW` (`ALLOW` em `:50`); `:128` - `not any(matches(rule, command) for rule in allow), command`; `:129-130` - `git push -u origin feat/31/x` casa o `allow` e nenhum `ask` (inclusive as 3 regras novas). Código: `.claude/settings.json:26-29` | PASS |
| C30 | proteção da `main` no GitHub: `enforce_admins`, PR obrigatório, sem force push nem deleção (`carried from eaa574f`) | comando do `checks.md` rodado ao vivo na rodada 9: exit `0`. Não rodado nesta rodada, por pedido; o intervalo não toca a proteção nem o `.github/repo-settings/` | `true true false false` para `enforce_admins.enabled`, `required_pull_request_reviews != null`, `allow_force_pushes.enabled`, `allow_deletions.enabled` (rodada 9) | PASS |
| C31 | `branch_pattern` e `handoff_skill` (carried) | lote A `test_worktree_handoff_config` PASSED | `tests/test_repo_files.py:416-417` | PASS |
| C32 | issues abertos para webhook e sandbox do Codex (`carried from b852e33`) | comando do `checks.md`, exit `0` na rodada 7; o intervalo não toca em issues | #32 e #33 abertos; citados em `tests/test_repo_files.py:432` | PASS |
| C33 | `## Handoff` cita `#32`/`#33`, sem `bwrap` nem `limites do webhook` (carried; o `STATE.md` só mudou a linha da AD-054 em `## Decisions`) | lote A `test_state_handoff_cites_issues` PASSED | `tests/test_repo_files.py:432-434` | PASS |
| C34 | 4 seções; coluna do Rodrigo = plano, merge, tag (reverificado: o `72c9a34` muda só o parágrafo abaixo da tabela, `AGENTS.md:35-40`) | lote A `test_sections_and_autonomy` PASSED | `tests/test_agents_md.py:30` - `section(heading)` para as 4; `:35` - `len(cells) == 3`; `:37` - `len([c for c in cells if word in c.lower()]) == 1` para `plano`, `merge`, `tag` | PASS |
| C35 | `## Skills` e `## Ambiente` com os termos (reverificado; seções intocadas) | lote A `test_skills_and_environment` PASSED | `tests/test_agents_md.py:44` - `needle in skills`; `:46` - `len(no_spec) == 1`; `:48`; `:50-51` | PASS |
| C36 | regras do antigo `CLAUDE.md` no `AGENTS.md` (reverificado) | lote A `test_carries_former_claude_md` PASSED | `tests/test_agents_md.py:65` - `needle in body` (6 termos, incluindo `gate-worktree.sh`) | PASS |
| C37 | `CONTRIBUTING.md` EN/pt-BR com `commit-msg`, `pre-push`, `process`, padrão, `Closes #` (carried from 5842494; par intocado) | lote A `test_contributing_gates` PASSED | `tests/test_docs.py:342` - `needle in text`, com o laço em `:340-341` sobre as duas línguas | PASS |
| C38 | `state` sai `0` contra o repositório (reverificado: o `STATE.md` mudou) | lote A `test_state_handoff_within_limit` PASSED | `tests/test_repo_files.py:442` - `result.returncode == 0` | PASS |
| C39 | nenhum `CLAUDE.md` versionado (carried) | lote A `test_no_claude_md_tracked` PASSED | `tests/test_repo_files.py:454` - `files.stdout == ""` | PASS |
| C40 | `copy` sem `CLAUDE.local.md` (carried) | lote A `test_worktree_handoff_config` PASSED | `tests/test_repo_files.py:418` | PASS |
| C41 | sem `commit-msg` instala e reporta; com, não chama (citação atualizada, +8 linhas) | lote A `test_session_start_installs_hooks` PASSED | `tests/test_claude_hooks.py:173` - `calls.read_text(encoding="utf-8").split() == [str(repo), "run", "pre-commit", "install"]`; `:174` - `"install" in context`; `:180` - `not calls.exists()` | PASS |
| C42 | aviso com `CLAUDE.md` ou `CLAUDE.local.md`; sem, nada (citação atualizada) | lote A `test_session_start_warns_claude_md[*]` (2) PASSED | `tests/test_claude_hooks.py:190` - `CLAUDE_MD_WARNING not in clean`; `:194` - `CLAUDE_MD_WARNING in context.splitlines()` | PASS |
| C43 | install falhando: exit `0` e a linha diz que falhou (citação atualizada) | lote A `test_session_start_install_failure` PASSED | `tests/test_claude_hooks.py:202-204` - `result.returncode == 0`, `calls.exists()`, `"fail" in context.lower()` | PASS |
| C44 | `CONTRIBUTING.md` EN/pt-BR com `AGENTS.md`, `2.1.277`, `CLAUDE.local.md` (carried from 5842494; par intocado) | lote A `test_contributing_agents_md` PASSED | `tests/test_docs.py:349` - `needle in text`, em `:347` sobre `contributing_texts()` | PASS |
| C45 | `claude` real carrega o `AGENTS.md` e responde `150k` (`carried from b852e33`) | manual (host de dev), rodada 7. O `72c9a34` muda o parágrafo dos gates no `AGENTS.md`, mas não `budget: 150k` nem a raiz | `docs/.specs/features/sdlc-gates/evidence/c45.txt:5` - `150k`, `:7` - `grep -q 150k: exit 0` | PASS |
| C46 | `DOOR_10_FILES` com `AGENTS.md`, sem `CLAUDE.md` (carried) | lote A `test_door_10_tree_files[*]` (22) PASSED | `tests/test_repo_files.py:300` - `"AGENTS.md",`; `:312` - `assert tracked(rel)` | PASS |
| C47 | prova C48 da model-setup-docs lê o `AGENTS.md`, mesmas asserções (reverificado: o `AGENTS.md` mudou) | lote A `test_agents_md_doc_rule` PASSED | `tests/test_docs.py:254`; `:256-258` | PASS |
| C48 | `## Documentação` com os termos (reverificado; seção intocada) | lote A `test_documentation_section` PASSED | `tests/test_agents_md.py:80` - `needle in docs` (7 termos); `:82`; `:83`; `:85-88` | PASS |
| C49 | checador acusa `run --timeout` em EN e pt-BR; repositório limpo (carried) | lote A `test_gate_reports_missing_flag`, `test_gate_flags_repo_clean` PASSED | `tests/test_docs.py:283`, `:288`; `:294` - `check_flags(ROOT, options) == []` | PASS |
| C50 | checador acusa `exit_code` em EN e pt-BR; 26 campos limpos (carried) | lote A `test_gate_reports_missing_event_field`, `test_gate_event_fields_repo_clean` PASSED | `tests/test_docs.py:301`, `:306`; `:313` - `len(fields) == 26`; `:314` | PASS |
| C51 | acusa `docs/x.md:3`, ignora `http(s)` e `#`; repositório limpo (carried) | lote A `test_gate_reports_broken_link`, `test_gate_links_repo_clean` PASSED | `tests/test_docs.py:326`; `:330` | PASS |
| C52 | só `README.md` ou só o par -> `1` nomeando os dois; os dois -> passa (carried from 5842494; o intervalo não toca doc com par, e a reprodução do `pr` em `72c9a34` sai `0`) | lote A `test_pr_doc_pair[*]` (6), `test_pr_doc_pair_other_docs` PASSED | `tests/test_sdlc.py:666` - `(result.returncode == 0) is ok`; `:668` - `returncode == 1`; `:670` - `f"{name} changed" in result.stderr or f"pair {name}" in result.stderr`; `:672` - `rel in result.stderr`; `:680-681` | PASS |
| C53 | `feat`/`fix` sem `## [Unreleased]` -> `1`; `refactor`/`chore` passa (carried) | lote A `test_pr_changelog_unreleased[*]` (2), `..._not_for_other_types[*]` (2) PASSED | `tests/test_sdlc.py:689` - `== 0`; `:695-696` - `returncode == 1`, `"CHANGELOG.md" in result.stderr`; `:705` - `== 0` | PASS |
| C54 | `feat`/`fix` sem doc -> `1`; `Docs: n/a - <razão>` passa; razão vazia -> `1` (carried) | lote A `test_pr_docs_or_na[*]` (2) PASSED | `tests/test_sdlc.py:721` - `without.returncode == 1`; `:724` - `with_na.returncode == 0`; `:726` - `pr.run().returncode == 1` | PASS |
| C55 | `spec` exige critério de doc ou `Docs: n/a`; passa contra este plano | lote A `test_spec_plan_doc_criterion` PASSED, com este relatório no lugar | `tests/test_sdlc.py:402` - `missing.returncode == 1`; `:405`, `:411` - `== 0`; `:414` - `this.returncode == 0` (`spec sdlc-gates` com `cwd=ROOT`) | PASS |
| C56 | item de doc do template com `Docs: n/a - <reason>` (carried) | lote A `test_pr_template_doc_item` PASSED | `tests/test_docs.py:267`; `:269` | PASS |
| C59 | `commit-msg` aceita as 6 mensagens de merge do git; recusa `Merge stuff` e merge com coautor; `pr --title "Merge branch 'main'"` -> `1` (carried) | lote A `test_commit_msg_merge_accepts[*]` (6), `test_commit_msg_merge_rejects`, `test_pr_title_merge` PASSED | `tests/test_sdlc.py:137-138`; `:143-144`; `:146-147`; `:505-506`. Código: `tools/sdlc.py:26`, `:80` (intocados) | PASS |

## Coverage

As linhas da door 6 foram recalculadas a partir do `.claude/settings.json` e do texto do `plan.md` e do `AGENTS.md`
(`verified at 72c9a34`). As outras são `carried from 5842494`, porque o intervalo não tocou a autoridade delas.

| Set (size) | Recomputed from | Member -> proof | Unproven |
| --- | --- | --- | --- |
| subcomandos do `tools/sdlc.py` (6) - carried | door 1 | `commit-msg` C3-C5, C59 · `branch` C6, C28 · `pre-commit` C8-C10 · `pr` C14-C23, C52-C54 · `spec` C18-C19, C55 · `state` C23, C38 | - |
| exit codes do `tools/sdlc.py` (3) - carried | door 1 | `0` C3 · `1` C4 · `2` C11 | - |
| hook types instalados (3) - carried | AC 1 | os 3 em C1 | - |
| tipos da door 3 (11) - carried | regex da door 3 | os 11 em C3 | - |
| rejeições da primeira linha (6) - carried | door 3 | os 6 em C4 | - |
| formas da door 2 (3 aceitas + recusa) - carried | `tools/sdlc.py:19-23` | C6, C7; `main` recusada C6, C28 | - |
| regras do `pre-commit` (3) - carried | AC 6-8 | C8 · C9 · C10 | - |
| triggers do job `process` (4) - carried | AC 10 | os 4 em C12 | - |
| regras do `pr` (12) - carried | AC 11-18, 39-41 | título C14 · branch C15 · coautor C16 · link C17 · specs tocadas C20 · `verification.md` C21 · `**Approved**` C22 · `Handoff` C23 · par C52 · `CHANGELOG.md` C53 · doc ou `Docs: n/a` C54 | - |
| palavras do link (3) - carried | door 7 | os 3 em C17 | - |
| validadores do `spec` (4) - carried | AC 15, 42 | `validate_plan` C19 · `validate_checks` C18 · `validate_verification` C18 · critério de doc C55 | - |
| regras `ask` (17) - verified at 72c9a34 | `.claude/settings.json:31-47`, recontado: 17 | as 17 por igualdade de lista em C27 (`tests/test_claude_hooks.py:89`); casamento por comando concreto em `test_settings_permissions_ask_covers` para as 17 (sonda: cada um dos 20 comandos casa ao menos uma regra, e cada regra é casada por ao menos um deles; `--follow-tags` com remoto por `:109`, sem remoto por `:107-108`, `+v*` por `:110`, `+refs/tags/` por `:111`) | - |
| comandos `git tag` locais fora do `ask` (3) - verified at 72c9a34 | AD-054, C27 | `git tag`, `git tag -l 'v0.0.0*'`, `git tag --list` em C27 (`:90-91`) | - |
| formas de publicar tag que o plano diz pedir (8) - verified at 72c9a34 | `plan.md:73` (AD-054: "por qualquer forma de `git push`"), `AGENTS.md:36` | `--tags` C27 (`:99-100`) · `--follow-tags` C27 (`:107-109`) · `v*` C27 (`:101`) · `refs/tags/` C27 (`:102`) · `<src>:refs/tags/` C27 (`:103`) · `<src>:v*` e `:<tag>` C27 (`:104-105`; `git push origin +HEAD:v1` também, na sonda) · `+<tag>` C27 (`:110-111`) · `--mirror` C27 (`:106`) | - |
| regras `allow` (2) - verified at 72c9a34 | `.claude/settings.json:27-28` | as 2 por igualdade em C29 (`:126`); não casam merge, tag, release (`:127-128`) | - |
| registros de hook do Claude Code (2 eventos, 1 matcher de `PreToolUse`) - verified at 72c9a34 | `.claude/settings.json:2-24` | `SessionStart` C26, C41 · `PreToolUse` dos 4 nomes de edição C26 · nenhum `Bash` C26 | - |
| barreiras do push para `main` (3) - carried from 5842494 | AC 21 (`plan.md:148`), door 6 | hook `pre-push` C28 · `tools/sdlc.py branch main` C28 · proteção no GitHub C30 (ao vivo na rodada 9) | - |
| mensagens de merge do git (5 formas, 6 casos) - carried | AC 46, `tools/sdlc.py:26` | as 5 em C59 | - |
| saídas do hook de sessão (4) - carried | AC 9, 32 | instala C41 · já instalado C41 · falha C43 · aviso C42 | - |
| seções do `AGENTS.md` (5) - verified at 72c9a34 | AC 26, 35 | `## Fluxo`, `## Autonomia` C34 · `## Skills`, `## Ambiente` C35 · `## Documentação` C48 | - |
| opções longas do parser (28) - carried | `build_parser()` | C49 | - |
| campos do evento (26) - carried | `event.v1.json` | C50 | - |
| doors (9) - carried from 5842494 | `## Landing` | 1 C2, C11 · 2 C6 · 3 C3, C4, C59 · 4 C12, C24, C25 · 5 C22 · 6 C26-C30 · 7 C17 · 8 C39, C45 · 9 C48, C54, C55 | - |

Consistência do texto (`verified at 72c9a34`):

- `plan.md`: AD-054 em `Surface` (`:73`), door 6 (`:94`) e AC 20 (`:147`) listam as mesmas 17 regras do
  `settings.json:31-47`, do `checks.md` C27 e do `ASK` do teste (`tests/test_claude_hooks.py:32-48`), na mesma ordem.
  A AC 22 (`:149`) diz que nenhum `allow` casa `git tag`, o que segue verdadeiro.
- `checks.md`: C27 com as 17 regras e os 3 comandos `git tag`; `Coverage` com `regras ask (17)` e 17 membros;
  cabeçalho `57 checks em 8 slices` (recontado: 57 linhas `**C<n>**`).
- `STATE.md:60` (AD-054) lista as 6 regras que entram, que são exatamente as 6 do `ask` que não estavam na AD-053.
- `AGENTS.md:35-40` cita AD-054 e "push de tag (até por refspec, `--follow-tags` ou `--mirror`)"; no emulador, toda
  forma listada pede (ver `## Regressões e brechas`). O `CONTRIBUTING.md:74` e o `docs/pt-BR/CONTRIBUTING.md:74` ("a tag
  push" / "push de tag") não mudaram e seguem coerentes.

Swept `existing` (`carried from 5842494`). O `authorization: C27, C28` confere: regras em `.claude/settings.json:30-48`,
e o `main` recusado em `.pre-commit-config.yaml:48` -> `tools/sdlc.py:70-73` (intocados). O `dependency failure`
confere: `tools/sdlc.py` só chama `git`.

## Test policy rows

`verified at 72c9a34` para a linha que classifica `.claude/settings.json`; a outra é `carried from 5842494`.

| Row | Files it classifies | Required proof | Expectation met |
| --- | --- | --- | --- |
| `tools/sdlc.py` decide e é alcançado por hook git e CI: subprocesso contra repositório git de teste, um caso por linha das tabelas - carried | `tools/sdlc.py`, `.pre-commit-config.yaml` | subprocesso em `tmp_path`; hook git real em C1, C7 e C28 (`tests/test_sdlc.py:213-231`) | yes |
| hooks do Claude Code decidem e são alcançados por JSON em stdin: um caso por decisão | `.claude/hooks/session-start.sh`, `.claude/settings.json` | `session-start.sh`: JSON em stdin, um caso por saída (C41-C43, `tests/test_claude_hooks.py:133-204`). `settings.json`: literal (igualdade de lista, C27/C29) e um comando concreto por regra no emulador `matches` (as 17 regras). A fronteira real (o Claude Code pedindo confirmação) segue sem prova automática (N3) | yes |

## Faults injected

`verified at 72c9a34`, numa worktree de rascunho (`git worktree add --detach <scratchpad>/mut11 HEAD`), um mutante por
vez, rodando `uv run pytest -q -p no:cacheprovider tests/test_claude_hooks.py -k settings_permissions` e revertendo com
`git checkout -- .` (porcelain do rascunho vazio depois de cada um). O `git status --porcelain` da árvore real antes:
só ` M docs/.specs/features/sdlc-gates/verification.md` (o relatório da rodada 10); depois: o mesmo arquivo, agora com
este relatório. Os mutantes de `tools/`, `.pre-commit-config.yaml` e `hooks` das rodadas 9 e 10 não foram repetidos: o
intervalo não toca essas superfícies.

| Mutation | Location | Killed |
| --- | --- | --- |
| M1: sai `Bash(git push --follow-tags *)` do `settings.json` e do `ASK` | `.claude/settings.json:36`, `tests/test_claude_hooks.py:37` | yes - `test_settings_permissions_ask_covers[git push --follow-tags]` e `[git push --follow-tags origin]` failed |
| M2: sai `Bash(git push *+v*)` do `settings.json` e do `ASK` | `.claude/settings.json:42` | yes - `test_settings_permissions_ask_covers[git push origin +v0.6.0]` failed |
| M3: sai `Bash(git push *+refs/tags/*)` do `settings.json` e do `ASK` | `.claude/settings.json:43` | yes - `test_settings_permissions_ask_covers[git push origin +refs/tags/v0.6.0]` failed |
| M4: sai `Bash(git push --follow-tags *)` só do `settings.json` | `.claude/settings.json:36` | yes - `test_settings_permissions_ask` failed (igualdade de lista, `:89`) |
| M5: `Bash(git push *+v*)` vira `Bash(git push *-*)` (largo demais) no `settings.json` e no `ASK` | `.claude/settings.json:42` | yes - `test_settings_permissions_allow` failed em `:130` (o `git push -u origin feat/31/x` passa a pedir) e `ask_covers[git push origin +v0.6.0]` failed |

## Regressões e brechas

Sondas no emulador `matches` do teste (`tests/test_claude_hooks.py:57-64`), em `72c9a34`, sem nenhum push real:

- Pedem (casam um `ask`): `git push --follow-tags`, `git push --follow-tags origin`, `git push --follow-tags origin
  feat/31/x`, `git push origin --follow-tags`, `git push -u --follow-tags origin feat/31/x`, `git push origin +v0.6.0`,
  `git push -f origin +v0.6.0`, `git push origin +refs/tags/v0.6.0`, `git push origin +HEAD:refs/tags/v1`,
  `git push origin +HEAD:v1`, `git push origin tag v1`, `git push --delete origin v0.6.0`, `git push --mirror`,
  `git push --tags`, `git push origin :v0.6.0`, `git push origin HEAD:refs/tags/v1`.
- Não pedem (casam só o `allow`): `git push origin 'v0.6.0'` com aspas (limite aceito; depende do Claude Code real, N3).
- Sem falso positivo nas formas do fluxo: `git push`, `git push origin`, `git push -u origin feat/31/x`,
  `git push -u origin HEAD:feat/31/x`, `git push origin feat/31/x --verbose`, `git push -f origin feat/31/x`,
  `git push --force-with-lease origin feat/31/x` e `git push origin +feat/31/x` não casam nenhum `ask`.
- `git tag`, `git tag -l 'v0.0.0*'`, `git tag --list` e `git tag -a v0.7.0 -m x` não casam `ask` nem `allow` (AD-054).
- Nota: `Bash(git push *+v*)` casa qualquer `+v` no comando, então uma branch com `+v` no nome (`feat/31/a+v2`) pediria
  confirmação. É falso positivo, do lado seguro, e nenhuma branch da door 2 do fluxo tem `+`.

## Gate

`verified at 72c9a34`:

- `uv run pytest -rA -p no:cacheprovider` na worktree de rascunho em `72c9a34`, com este relatório copiado no lugar:
  `997 passed, 50 deselected in 206.15s`, exit `0`, nenhum `FAILED`; `test_settings_permissions_ask_covers` com 20
  `PASSED`; `test_spec_plan_doc_criterion` PASSED (o `spec sdlc-gates` aceita este relatório).
- Reprodução do job `process` em `72c9a34` (C25), corpo atual do PR 34, `--base 15398f38d4fa742178e914debf5e2d231f08eb82`,
  com este relatório no lugar: exit `0`.
- C30: `carried from eaa574f` (exit `0`, `true true false false`), sem `gh api` nesta rodada.
- `python3 .claude/skills/tlc-spec-lean/scripts/validate_verification.py sdlc-gates --root docs`: exit `0`
  (`0 error(s), 0 warning(s)`).

## Ranked gaps

Nenhum bloqueante.

1. **N3 (não bloqueia, carried) - as provas da door 6 param no emulador.** C27 e C29 provam o literal e o casamento por
   `matches` (`tests/test_claude_hooks.py:57-64`), não pelo Claude Code real. As formas com aspas dependem disso.
2. **N4 (não bloqueia, carried) - o corpo do PR #34 ainda descreve o `gate-humano.sh` como vivo.** Atualizar no push
   que fecha a C25, já com a AD-054 (o `git tag` local não pede; o push de tag, em toda forma listada, pede).
3. **N6 (não bloqueia, carried) - o `**Approved**: 2026-10-29` do plano é anterior à reescrita da AC 20 e da AC 21 pela
   AD-054 (2026-10-30).** A C22 confere só a presença da linha. Vale o Rodrigo confirmar no chat que a AD-054, agora com
   17 regras, está aprovada.
4. **C25 push pendente (não bloqueia, carried)** - o head do PR é `df8b3a4`, 21 commits atrás de `72c9a34`; a reprodução
   local do `process` passa.

O N5 da rodada 10 fecha: as 4 formas que casavam só o `allow` agora casam um `ask`, cada uma com prova concreta e com
mutante morto (M1-M3).
