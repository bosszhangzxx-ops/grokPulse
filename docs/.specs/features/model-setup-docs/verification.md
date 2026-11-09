# model-setup-docs verification

**Verdict**: PASS
**Profile**: standard
**Diff range**: main..HEAD (b3eed06..544dc80)
**Round**: 3 - scoped
**Verifier**: independent sub-agent (author != verifier)

The only item round 2 left open, C36, now has a proof run: `test_opencode_fallback_real` PASSED on the box at
`1a71566`, recorded in `docs/.specs/features/model-setup-docs/box/c36.md`. That run was made by the user's bot on the
box, not by this verifier (the box has no ssh from here, and this dev host's opencode 2.1.3 fails the test for an
environmental reason, a managed-service port bind). `1a71566..544dc80` adds only that record, so the test and the code
it ran against are byte for byte the ones at `HEAD`. The box runs opencode 1.19.5, not the 1.19.3 that C36 and the plan
assumption name; that is recorded below as a precision gap in the check text, not a failed proof. Every check (50 of 50)
now PASSES with located evidence; the default suite is green at `544dc80` (836 passed, 0 failed) and C37 re-ran green.

Scope of this round (verify.md, "Re-verifying after a fix"): the diff `0f6fc1e..544dc80` is 3 files:
`tests/integration/test_real_cli.py` (+16: `copy_opencode_db`, a sqlite backup of the real `opencode.db` into the
test's temporary `HOME`, opencode only), `skills/grokbot-kit/SKILL.md` (the paid-provider login paragraph, the C15
surface, `:144-146`) and the new box record. Proofs re-ran in full at `544dc80`; C36, C15, C37 (its file moved),
the `real CLIs with fallback` coverage row and the `Integração com CLI real` Test policy row were re-judged; one fault
was injected on the C15 surface. Everything else is carried from 69c84b7 (or from 9e9e5b9 where round 2 carried it)
and says so.

## Binding sources

Carried from 9e9e5b9 (via 69c84b7). Neither round-2 nor round-3 fixes touched the interface (round 3: an integration-test helper, one
SKILL.md paragraph whose instruction stays inside AC 16, and a box record), so step 1 was not re-run.

Step 1 is a `ui` step. Under `standard` this is a narrow contradiction pass over the sources the plan names.

| Source | Opened | Contradiction | Uncovered |
| --- | --- | --- | --- |
| `docs/.specs/features/agent-run-notify/plan.md` AC 109 (`:372`) | yes | none - the plan supersedes it in part (free-first only when the only provider chosen is `opencode`); AD-048 in `docs/.specs/STATE.md` records this, and C17 asserts the conditioned rule | - |
| agent-run-notify door 3, config (`:154`) | yes | none - `[cli.opencode] providers` is additive and optional; `config.load()` does not validate it (C12) | - |
| agent-run-notify door 16, `setup models refresh` (`:167`) | yes | none - `--json` only changes how stdout is formatted; recording, the order and `--add` are unchanged (`src/grokbot_kit/models.py:145-157`) | - |
| agent-run-notify door 21, `doctor --json` (`:173`) | yes | none - `cli.opencode.providers` is additive; the new problem keeps "exit `1` exactly when `problems` is not empty" (C11) | - |
| agent-run-notify door 22, `setup tiers` (`:174`) | yes | none - the new refusal adds an exit-`2` cause with the config unchanged, matching door 22's own refusals (C7) | - |
| `CLAUDE.md` doc-language rule (AD-041) | yes | none - `CONTRIBUTING.md` is in English with the pt-BR pair at `docs/pt-BR/CONTRIBUTING.md`, the two link each other at line 3, and the "Pendente" line is gone (C41, C47) | - |

## Checks

Verified at 544dc80 (proofs). All non-integration proofs ran in one invocation, `uv run pytest -v -rA -p no:cacheprovider`,
at `544dc80`: 836 passed, 0 failed, 50 deselected, exit 0 (190.9 s). Each named test was matched individually as a
`PASSED tests/...::test_<name>` line in that output (all 57 name patterns, every parametrized case: e.g.
`fallback_eligible` x10, `error_summary_codex` x8, `providers_refused` x3, `providers_written_keeps_order`,
`refresh_json_provider_layer`, `non_retryable_4xx_to_undelivered_layer` x5, `retry_table_429_5xx_connection*` x6; no
`FAILED`/`ERROR` line). C37 ran in a second invocation (`-m integration ... -k claude_fallback_real`) at `544dc80`. C36
was run on the box by the bot, not by this verifier (record cited in its row).

Citations: round 3 touched `tests/integration/test_real_cli.py` (every line after `:16` moved; C36 and C37 citations
refreshed) and `skills/grokbot-kit/SKILL.md` (the C15 paragraph, now `:144-146`; its test `tests/test_skill_doc.py` is
unchanged, `:481`). No other cited file changed, so every other row's evidence is carried from 69c84b7 with the proof
re-run at 544dc80.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | `refresh --json`: only `{"models": [...]}`, items in order, no tab line, exit 0 | `test_refresh_json_shape` PASSED | `tests/test_models.py:224` - `assert result.returncode == 0`; `:225` - `assert not any("\t" in line ...)`; `:227` - `assert items == [{"tool": "opencode", "id": "opencode/a-free", "provider": "opencode"}, ...]`; `:209` - `assert list(out) == ["models"]` | PASS |
| C2 | `provider` = prefix before the first `/`; `null` for claude/codex | `test_refresh_json_provider` (+`_layer`) PASSED | `tests/test_models.py:250` - `assert provider[("opencode", "ollama/x/y")] == "ollama"`; `:251-252` - `... is None` for claude/codex | PASS |
| C3 | opencode exits 1: exit 1, no opencode item, error on stderr | `test_refresh_json_partial_failure` PASSED | `tests/test_models.py:273` - `assert result.returncode == 1`; `:275` - `assert [i["tool"] for i in items] == ["claude", "claude", "claude"]`; `:277` - `assert "exited 1" in result.stderr` | PASS |
| C4 | text output unchanged | `test_refresh_text_unchanged` PASSED | `tests/test_models.py:284` - `assert result.stdout.splitlines() == ["opencode\topencode/a-free", "opencode\topencode-go/b"]`; `:285` | PASS |
| C5 | `setup providers` writes the list in order, nothing else changes | `test_providers_written`, `_keeps_order` PASSED | `tests/test_setup_providers.py:26` - `assert result.stdout == "opencode providers: opencode-go\n"`; `:30` - `assert after == before`; `:38` - `== ["opencode-go", "opencode"]` | PASS |
| C6 | the 3 refusals: exit 2, config byte for byte unchanged | `test_providers_refused` x3 PASSED | `tests/test_setup_providers.py:54` - `assert result.returncode == 2`; `:56` - `assert text in result.stderr`; `:57` - `assert kit.config_text() == before`; cases `:45-47` | PASS |
| C7 | `setup tiers` refuses an id from a provider outside the list | `test_tiers_provider_outside` PASSED | `tests/test_setup_tiers.py:93-96` - `returncode == 2`, `"opencode/a-free" in result.stderr`, `"grokbot-kit setup providers opencode" in result.stderr`, `kit.config_text() == before` | PASS |
| C8 | without `providers`, any discovered id is accepted | `test_tiers_no_providers` PASSED | `tests/test_setup_tiers.py:104` - `assert ...["standard"] == ["opencode/a-free", "opencode-go/b"]` | PASS |
| C9 | writes even with a tier outside the list, and warns once | `test_providers_warns_tier_outside` PASSED | `tests/test_setup_providers.py:65` - `providers == ["opencode-go"]`; `:67-68` - `len(warning) == 1`, `"opencode/a-free" in warning[0]` | PASS |
| C10 | `doctor --json` shows `cli.opencode.providers` or `null` | `test_opencode_providers_field` PASSED | `tests/test_doctor.py:379` - `== ["opencode-go"]`; `:382` - `is None` | PASS |
| C11 | doctor problem for a tier id outside the list, exit 1 | `test_opencode_tier_provider_problem` PASSED | `tests/test_doctor.py:389` - `assert code == 1`; `:391` - `len(found) == 1` (prefix `:372`); `:392` - `"grokbot-kit setup tiers opencode standard" in found[0]`; `:395` - the line is absent when the tier is inside | PASS |
| C12 | `load()` does not refuse; `run` launches the id that is outside | `test_load_ignores_providers`, `test_run_tier_outside_providers` PASSED | `tests/test_config.py:152` - `assert config.load() == cfg`; `tests/test_run_fallback.py:29` - `assert argv[argv.index("-m") + 1] == "opencode/a-free"` | PASS |
| C13 | `refresh --json` comes before `setup providers` and `setup tiers` | `test_models_refresh_json_first` PASSED | `tests/test_skill_doc.py:463-464` - `assert first < s.index("grokbot-kit setup providers")`, `... setup tiers` | PASS |
| C14 | one multiple-choice provider question, with the count per provider | `test_providers_question` PASSED | `tests/test_skill_doc.py:470-474` - `"única pergunta de múltipla escolha" in p`, `"quantos ids" in p`, `"grokbot-kit setup providers opencode <provider>" in ...` | PASS |
| C15 | a paid provider needs `grokbot-kit login opencode` | `test_paid_provider_login` PASSED at 544dc80 (re-judged: the paragraph was reworded in 1a71566) | `tests/test_skill_doc.py:481` - `assert "grokbot-kit login opencode" in p`, over the paragraph with "provedor pago" (`:479`), which is now `skills/grokbot-kit/SKILL.md:144-146`: "pergunte se o usuário já fez esse login no box; se não, peça que ele rode `grokbot-kit login opencode` num terminal do box". AC 16 (login needed before use, citing the command) still holds; the new sentence "Não decida pelo `login` do `grokbot-kit doctor --json`" is beyond AC 16 and has no proof of its own (not required). The fault on this surface is killed (see Faults) | PASS |
| C16 | one question per tier, up to 4 ids, recommended first | `test_tier_question_per_tier` PASSED | `tests/test_skill_doc.py:487-493` - each tier, `"até 4 ids"`, `"recomendado primeiro"`, `"só ids dos provedores escolhidos"`, `"grokbot-kit setup tiers <tool> <tier> <id>"` | PASS |
| C17 | free-first only with `opencode` as the sole provider; otherwise the paid provider first | `test_free_first_only_without_paid` PASSED | `tests/test_skill_doc.py:499` - `"só o provedor \`opencode\`" in free`; `:503` - `"todos os tiers" in paid` | PASS |
| C18 | changing models redoes only providers and tiers | `test_change_models_redo_steps` PASSED | `tests/test_skill_doc.py:511-512` - `for absent in ("setup cli add", "login", "route add"): assert absent not in p` | PASS |
| C19 | new commands are in `--help`; the existing skill proofs stay green | `test_no_literal_model_ids` x5, `test_every_cited_command_exists`, `test_install_location_and_allowed_commands`, `test_setup_providers_in_help` PASSED | `tests/test_cli.py:44` - `"providers" in setup_help`; `:48` - `"--json" in refresh_help`; `tests/test_skill_doc.py:286-288` - each flag of each cited command `in result.stdout`; `:323` - `assert not re.search(pattern, text(), ...)` | PASS |
| C20 | opencode error `summary`: 1.19, 2.x, name only, last of two | `test_error_summary_opencode` x4 PASSED | `tests/test_terminal.py:312` - `assert summary_of(...) == expected` over the cases at `:304-307` | PASS |
| C21 | codex error `summary`: `turn.failed`, `error`, last of both | `test_error_summary_codex` x8 PASSED | `tests/test_terminal.py:330` - `== expected` over `:321-324` x `last_message in [None, ""]` | PASS |
| C22 | the agent's final text wins over the error | `test_error_summary_text_wins` PASSED | `tests/test_terminal.py:336` and `:339` - `== "feito"` | PASS |
| C23 | the error `summary` is cut at 2000 characters | `test_error_summary_limit` x2 PASSED | `tests/test_terminal.py:350` - `assert len(summary_of(tmp_path, tool, out)) == 2000` | PASS |
| C24 | at the boundary, the event carries the error `summary` | `test_event_summary_from_error` PASSED | `tests/test_run_fallback.py:87-88` - `outcome(event) == ("error", "failed", "agent_error")`, `event["summary"] == ERROR_SUMMARY` | PASS |
| C25 | door 4 eligibility table (10 rows: the 9, with `stopped` split into timeout and interrupted) | `test_fallback_eligible` x10 PASSED | `tests/test_terminal.py:380` - `assert terminal.fallback_eligible(tool, tmp_path, stopped) is expected` over `:362-371` | PASS |
| C26 | next id ok: event, calls, renamed files, `kit.log` | `test_fallback_next_model` PASSED | `tests/test_run_fallback.py:98-110` - `outcome == ("completed","ok","success")`, `model == M2`, `model_fallbacks == [{"model": M1, "error": ERROR_SUMMARY}]`, the same cwd and prompt, the contents of `out.1.jsonl`, `stderr.1.log` and `out.jsonl`, and the `kit.log` line | PASS |
| C27 | `model_fallbacks == []` on ok, nonzero_exit and timeout | `test_no_fallback_empty_list` PASSED | `tests/test_run_fallback.py:147-148` - `outcome(event) == expected`, `event["model_fallbacks"] == []` over `:139-141` | PASS |
| C28 | `--model` never falls back | `test_explicit_model_no_fallback` PASSED | `tests/test_run_fallback.py:155-157` - `len(calls(tmp_path)) == 1`, `agent_error`, `[]` | PASS |
| C29 | no fallback after a tool (opencode and claude) | `test_failure_after_tool_no_fallback` (+`_claude`) PASSED | `tests/test_run_fallback.py:164` and `:175` - `assert len(calls(tmp_path)) == 1` | PASS |
| C30 | every attempt fails: last summary, all but the last in `model_fallbacks` | `test_all_models_fail` PASSED | `tests/test_run_fallback.py:185-194` - `model == M3`, `summary == "UnknownError: erro 3"`, the list of m1 and m2, `out.1`/`out.2`/`out.jsonl` | PASS |
| C31 | one deadline counted from `started_at`; a timeout ends the task in under 6 s of wall time (amended 28/10/2026) | `test_shared_deadline` (+`_first_times_out`) PASSED (4.14 s and 1.14 s in the scratch baseline) | `tests/test_run_fallback.py:203` - `assert time.monotonic() - began < 6, "as tentativas dividem um prazo só, não um por tentativa"`; `:204` - `outcome(event) == ("timeout", "timeout", "timeout")`; `:205` - `event["model"] == M2`; `:206` - `len(calls(tmp_path)) == 2`; `:212-213` - `timeout`, 1 call. The bound now matches the amended check text (`checks.md:124`, "menos de 6 s de parede"), and both deadline mutants are killed (see Faults) | PASS |
| C32 | codex never falls back | `test_codex_never_falls_back` PASSED | `tests/test_run_fallback.py:222` - `len([...exec calls]) == 1`; `:224` - `model_fallbacks == []` | PASS |
| C33 | plugin: fallback reuses the clone | `test_plugin_fallback_clone_once` PASSED | `tests/test_run_plugin.py:625-627` - `completed/ok`, `model == m2`, `.count(["repo", "clone"]) == 1`; `:630` - `== [work, work]` | PASS |
| C34 | `meta.json` records `model` and `model_fallbacks` | `test_meta_records_fallback` PASSED | `tests/test_run_fallback.py:118-119` - `meta["model"] == M2`, `meta["model_fallbacks"] == event["model_fallbacks"]` | PASS |
| C35 | the body delivered to the routine has `model_fallbacks`, delivered 200 | `test_delivered_body_has_fallbacks` PASSED | `tests/test_run_fallback.py:130` - `bodies[0]["model_fallbacks"] == [...]`; `:132` - `== [200]` | PASS |
| C36 | opencode on the box: real fallback plus a real `tool_use` | Run on the box by the user's bot, not by this verifier: `uv run pytest -m integration tests/integration/test_real_cli.py -k opencode_fallback_real` with `GROKBOT_KIT_IT_OPENCODE_GO_MODEL=opencode-go/claude-haiku-5-5`, at `1a71566`, opencode 1.19.5 - `PASSED tests/integration/test_real_cli.py::test_opencode_fallback_real`, `1 passed, 10 deselected in 26.29s`, `PYTEST_EXIT=0` (`docs/.specs/features/model-setup-docs/box/c36.md:20-30`). `git diff --stat 1a71566..544dc80` is that record only, so the run covers the `HEAD` test and code. Not runnable here (no ssh to the box; this host's opencode 2.1.3 fails on a port bind, also without the change) | `tests/integration/test_real_cli.py:283` - `(event["event"], event["status"]) == ("completed", "ok")`; `:284` - `event["model"] == second`; `:287` - `[f["model"] for f in fallbacks] == [MISSING["opencode"]]`; `:292` - `assert "tool_use" in kinds` (one test, so the PASS covers both halves). Corroboration from the two earlier failing box runs (`box/c36.md:6-16`): the kit already fell back as door 5 says, with the C26 `kit.log` line and a 1.19-format `summary` (`UnknownError: Unexpected server error...`); they failed only because the second id had no login in the temporary `HOME`, which `1a71566` fixes (`test_real_cli.py:69-79`, `:101-102`). Precision gap: the check names 1.19.3, the proof ran on 1.19.5 (see Test policy rows) | PASS |
| C37 | the real claude: fallback from an id that does not exist to `haiku` | `uv run pytest -m integration tests/integration/test_real_cli.py -k claude_fallback_real -v -rA -p no:cacheprovider` - `PASSED tests/integration/test_real_cli.py::test_claude_fallback_real` (1 passed, 10 deselected, 4.96 s) at 544dc80 | `tests/integration/test_real_cli.py:298` - `event["model"] == "haiku"`; `:300` - `[f["model"] for f in fallbacks] == [MISSING["claude"]]`. `copy_opencode_db` runs only for `tool == "opencode"` (`:101`), so this test's setup is unchanged | PASS |
| C50 | delivery status table unchanged with the new field | `test_non_retryable_4xx_to_undelivered` (+`_layer`) x10, `test_retry_table_429_5xx_connection*` x6 PASSED | `tests/test_sink_routine.py:270-272` - `len(receiver.requests) == 1`, `line["http_status"] == status` (401/400/403/404/422); `:217-218` - `result.http_status == status`, `len(receiver.requests) == 3` (429/500/503) | PASS |
| C38 | `## Commands`/`## Comandos` lists the 13 parser subcommands, in order | `test_readme_commands_section` PASSED | `tests/test_docs.py:87` - `assert len(expected) == 13`; `:91` - `assert named == expected` | PASS |
| C39 | `## Plugins` with the command and the link | `test_readme_plugins_section` PASSED | `tests/test_docs.py:98-99` - `"grokbot-kit run --plugin code-review --input pr=" in s`, `link in s`; the full form is at `README.md:129` and `docs/pt-BR/README.md:129` | PASS |
| C40 | READMEs cite `setup providers`, `setup tiers`, `model_fallbacks` | `test_readme_models_and_fallback` PASSED | `tests/test_docs.py:107` - `assert needle in text` | PASS |
| C41 | CONTRIBUTING in English plus the pt-BR pair, same heading count | `test_contributing_pair`, `test_contributing_and_changelog`, `test_contributing_pypi_pending_publisher` PASSED | `tests/test_docs.py:114-117` - the two titles, then equal `## `/`### ` counts; `tests/test_repo_files.py:185`, `:308-309`. `diff <(git show main:CONTRIBUTING.md) docs/pt-BR/CONTRIBUTING.md` shows only the language link and the new doc rule added | PASS |
| C42 | `docs/SPEC.md` absent, CLAUDE.md does not cite it | `test ! -e docs/SPEC.md && ! grep -q "SPEC.md" CLAUDE.md` exit 0 (re-run at 69c84b7) | `CLAUDE.md:4` - "Specs e decisões em `docs/.specs/`." (the `SPEC.md` sentence was removed in the diff). The file is gitignored (`.gitignore:18`), so a fresh worktree cannot tell "deleted" from "never generated" | PASS |
| C43 | CHANGELOG `[Unreleased]` names the four items | `test_changelog_unreleased_model_setup` PASSED | `tests/test_repo_files.py:393-394` - `for needle in ("setup providers", "--json", "model_fallbacks", "summary"): assert needle in unreleased` | PASS |
| C44 | the checker reports a missing command per file; the list comes from the parser | `test_gate_reports_missing_command` PASSED | `tests/test_docs.py:127-129` - `== ["docs/pt-BR/README.md: no \`grokbot-kit redeliver\` ..."]`; `:134` - `{...foo...} == set(READMES)` | PASS |
| C45 | the checker reports a missing pair | `test_gate_reports_missing_pair` PASSED | `tests/test_docs.py:143-144` - `f.startswith("docs/plugins.md: no pt-BR pair")`, `"docs/novo.md: no pt-BR pair"` | PASS |
| C46 | the checker reports a missing link, in either direction | `test_gate_reports_missing_link` PASSED | `tests/test_docs.py:157-158` - `"README.md: no link to docs/pt-BR/README.md"`, `"docs/pt-BR/plugins.md: no link to docs/plugins.md"` | PASS |
| C47 | the real repo is clean | `test_gate_repo_clean` PASSED | `tests/test_docs.py:163` - `assert check(ROOT, commands()) == []` | PASS |
| C48 | CLAUDE.md doc rule | `test_claude_md_doc_rule` PASSED | `tests/test_docs.py:170-172` - `` "`README.md`" in rule ``, `"inglês" in rule and "pt-BR" in rule`, `"critério de doc" in rule` | PASS |
| C49 | PR template item | `test_pr_template_doc_item` PASSED | `tests/test_docs.py:180` - `any("README.md" in i and "docs" in i and "pt-BR" in i for i in items)` | PASS |

## Coverage

Carried from 69c84b7, except the `real CLIs with fallback` row, re-judged at 544dc80 (C36 now has its box run). Round 3
added no branch and no member.

| Set (size) | Recomputed from | Member -> proof | Unproven |
| --- | --- | --- | --- |
| routine delivery status (4 classes) | plan Surface / agent-run-notify door 3 | `200` C35 (`test_run_fallback.py:132`) · `401` C50 · other `4xx` (400/403/404/422) C50 · `429`/`5xx` C50 | - |
| `refresh --json` exit (3) | code `src/grokbot_kit/models.py:113-158` | `0` C1 · `1` C3 (`found.failed`, `:137-140`) · `2` the early returns at `:118,122,125,128` come before any JSON output, so `--json` cannot change them; existing `tests/test_models.py:84` (`returncode == 2`) | - |
| `provider` per CLI (3) | code `models.py:29-31` | opencode, claude, codex all asserted in C2 (`test_models.py:248-252`, layer `:256-259`) | - |
| `setup providers` exit (2) | code `src/grokbot_kit/setup.py:154-182` | `0` C5, C9 · `2` C6 | - |
| `setup providers` refusals (3 in the plan; 4 in the code) | plan door 2 + code | not opencode C6 · not installed C6 · unknown provider C6. The code's 4th exit-2 path, `ConfigError` at `setup.py:158-161`, is the shared `_load()` pattern the plan does not enumerate (observation, not counted) | - |
| `setup tiers opencode` with/without `providers` (2) | code `setup.py:138-146` | with C7 · without C8 | - |
| `doctor --json` exit (2) | code `doctor.py:96-108,147` | `0`/field C10 · `1` C11 | - |
| door 4 eligibility (9 rows from the plan; 10 cases in the code, since `stopped` has 2 values) | plan door 4 + code `terminal.py:91-112` | C25, table-driven over all 10 (`test_terminal.py:362-371`) | - |
| fallback outcomes in `run` (6) | plan AC 26-35 + code `run.py:410-441` | next ok C26 · all fail C30 · `--model` C28 · after a tool C29 · timeout C31 (green; both deadline mutants killed at 69c84b7) · codex C32 | - |
| error `summary` formats (5, plus text precedence) | plan door 6 + code `terminal.py:38-55` | opencode 1.19 / 2.x / name only C20 · codex `turn.failed` / `error` C21 · text wins C22 · 2000 cut C23 | - |
| terminal events carrying `model_fallbacks` | plan door 5 ("every terminal event") + code: a single construction at `payload.py:104` | `completed/ok` C26, C27 · `error/agent_error` C30 · `error/nonzero_exit` C27 · `timeout` C27. `completed/denied` and `error/interrupted` go through the same `task_event` path, and the schema requires the field (`event.v1.json` `required`; `tests/test_payload.py` validates every event against it) | - |
| real CLIs with fallback (2) | plan Assumptions | claude C37 (ran here at 544dc80, PASS) · opencode on the box C36 (run by the bot at 1a71566 on opencode 1.19.5, PASS; the plan names 1.19.3, precision gap below) | - |
| paired docs (3 English docs today, plus a new one) | `paired_docs()` over the tree: `README.md`, `CONTRIBUTING.md`, `docs/plugins.md` | README C38, C46 · CONTRIBUTING C41, C47 · plugins.md C45, C46 · new `docs/*.md` C45 | - |
| doc checker failure kinds (3) | code `tests/test_docs.py:39-59` | command C44 · pair C45 · link C46 (both directions) | - |
| top-level subcommands (13) | parser `build_parser()` | C38 asserts `len == 13` and the per-README order; C47 runs on the real repo | - |
| plan doors (7) | plan Landing | 1 C1, C2 · 2 C5, C6 · 3 C7, C9, C11, C12 · 4 C25 · 5 C26, C30, C34, C35 · 6 C20, C21, C24 · 7 C44-C47 | - |
| `providers` -> `tiers` relation (1) | plan Relations | `setup tiers` refuses C7 · `doctor` C11 · `load` does not C12 | - |

Sweep for sets with no row: the `setup providers` stdout line (`opencode providers: <p>, <p>`) is asserted in C5. The
door 5 `kit.log` line is asserted in C26. Every Observable surface in the plan maps to a row above. No unrowed set found.

## Test policy rows

Re-judged at 544dc80: the round-2 unmet row (real CLI integration), which also classifies the touched
`tests/integration/test_real_cli.py`. The other rows are carried from 69c84b7.

These are the rows of `docs/.specs/features/agent-run-notify/checks.md:554-564`, applied unchanged.

| Row | Files it classifies | Required proof | Expectation met |
| --- | --- | --- | --- |
| Decide, alcançado através de uma fronteira | `models.py` `provider`; `terminal.py` eligibility and error `summary` | boundary + own layer | yes - `provider`: C1 (CLI) + `test_refresh_json_provider_layer`; eligibility: C25 layer (all 10 rows) + C26/C29 boundary; `summary`: C20-C23 layer + C24 boundary |
| Decide, alcançado através de uma fronteira (decision in an entry point) | `setup.py` `set_providers` and the `set_tiers` provider check; `doctor.py` `_provider_problems`; the `run.py` attempt loop | every decision row asserted (the repo precedent accepts the subprocess boundary, as in the plugins verification for `run.py`) | yes - each refusal, the warning and the success at the boundary (C5-C9); doctor on and off (C11); every loop outcome at the boundary (C26-C33). The C31 timing assertion that was non-discriminating in round 1 now kills both deadline mutants (re-judged at 69c84b7) |
| Ponto de entrada que não decide | `cli.py` (the `providers` subparser and `--json` flag) | boundary: accepted input | yes - C19 `test_setup_providers_in_help`, C1 |
| Instrumentação, repasse | `payload.py:104` (`model_fallbacks`), `meta.json` | none of its own | yes - covered by C34, C35 |
| Integração com CLI real | `tests/integration/test_real_cli.py` C36 (opencode, box) and C37 (claude, dev host) | `-m integration`, once per CLI | yes - claude: C37 re-ran green here at 544dc80; opencode: C36 PASSED on the box at 1a71566 (identical test and code to `HEAD`), run by the bot, record `box/c36.md` |

`Swept` rows that resolve to existing, read against the code:

- data lifecycle: `gc` removes the whole task dir, `src/grokbot_kit/gc.py:35` `shutil.rmtree(task_dir)`, so
  `out.<n>.jsonl` and `stderr.<n>.log` go with it. Present.
- concurrency: `config.save` writes through a temp file and `os.replace`, `src/grokbot_kit/config.py:119-125`, and
  `set_providers` saves once at `setup.py:174`, before the warnings. Present.

Precision gap (a finding about the checks, not a failed proof): C36 (`checks.md:139`) and the plan assumption
(`plan.md:212`, "o opencode 1.19.3 do box grava `tool_use` como o 2.1.3", Confirmed `n`) pin opencode 1.19.3, but the
box now runs 1.19.5 and that is where the proof ran. Judged sufficient because the check's object is the box's real
opencode, 1.19.3 is no longer installed there to test, and the 1.19.5 runs show the same 1.19 error shape the code
parses (`UnknownError: ...`, door 6) and a real `tool_use`. No proof exists for 1.19.3 itself. Suggested amendment:
name the version the proof ran on (1.19.5) in C36 and the assumption row, and mark the assumption confirmed for it.

## Faults injected

Verified at 544dc80 for the C15 row (the only touched surface whose check proof can run here: C36's test can
only run on the box, so no fault was injected on `test_real_cli.py`). All other rows are carried from 69c84b7 (the two
shared-deadline rows) or from 9e9e5b9 (the first four), whose surfaces round 3 did not touch.

Round-3 isolation: `git worktree add --detach <scratchpad>/mut3 HEAD` at `544dc80`; baseline `test_paid_provider_login`
PASSED in the scratch; the mutant reverted with `git checkout`, the scratch removed with `git worktree remove --force`
plus `git worktree prune`. The real tree's `git status --porcelain` was empty before and identical after (compared with
`diff`). No `git stash` was used.

Round-2 isolation (carried): a scratch worktree at `69c84b7`, removed after; see the round-2 report in git history
(`0f6fc1e`).

| Mutation | Location | Killed |
| --- | --- | --- |
| `split("/", 1)[0]` -> `rsplit("/", 1)[0]` (provider of `ollama/x/y` becomes `ollama/x`) | `src/grokbot_kit/models.py:31` | yes - C2 `test_refresh_json_provider` and `_layer` failed |
| `set_tiers` provider check disabled (`... not in allowed and False`) | `src/grokbot_kit/setup.py:140` | yes - C7 `test_tiers_provider_outside` failed |
| opencode error name drops the `error.type` fallback | `src/grokbot_kit/terminal.py:45` | yes - C20 2.x case failed |
| eligibility ignores `tool_use` (`return "error" in kinds`) | `src/grokbot_kit/terminal.py:99` | yes - C25 `[opencode-objects1-None-False]` failed |
| a per-attempt deadline instead of the shared one: `deadline` -> `time.monotonic() + r["timeout_seconds"]` passed to `_supervise` (the alternative door 5 rejects) | `src/grokbot_kit/run.py:426` | yes - C31 `test_shared_deadline` FAILED at `tests/test_run_fallback.py:203`, `assert (…408 - …210) < 6` (7.20 s) |
| a looser deadline: `time.monotonic() < deadline` -> `time.monotonic() < deadline + timeout_seconds` in the `_supervise` wait loop | `src/grokbot_kit/run.py:220` | yes - C31 `test_shared_deadline` FAILED at `tests/test_run_fallback.py:203` (8.14 s) |
| C15 paragraph drops the command: "peça que ele rode `grokbot-kit login opencode`" -> "peça que ele faça o login do opencode" | `skills/grokbot-kit/SKILL.md:145` | yes - C15 `test_paid_provider_login` FAILED at `tests/test_skill_doc.py:481`, `assert 'grokbot-kit login opencode' in ...` |

Note, not a finding: the amended bound accepts any end below 6 s, so a grace of about 1 s past `--timeout` would still
pass (the correct code ends at ~4.1 s). That slack is the tolerance the user approved in the C31 amendment, not a
plausible wrong implementation of a shared deadline, so it was not injected.

## Gate

Verified at 544dc80.

`uv run pytest -v -rA -p no:cacheprovider`: 836 passed, 0 failed, 50 deselected (190.9 s), exit 0.
`uv run pytest -m integration tests/integration/test_real_cli.py -k claude_fallback_real -v -rA -p no:cacheprovider`:
1 passed, 10 deselected (4.96 s).
`test ! -e docs/SPEC.md && ! grep -q "SPEC.md" CLAUDE.md`: exit 0 (C42; `docs/SPEC.md` is gitignored, so in a worktree
the shell proof cannot tell "deleted" from "never generated").
Run on the box by the bot, not here: `test_opencode_fallback_real` (C36) at `1a71566`, 1 passed, 10 deselected, exit 0
(`docs/.specs/features/model-setup-docs/box/c36.md`).

Observations outside the checks (not findings against this feature):

- `doctor` still decides the opencode login from `opencode auth list`'s `<n> credentials` line
  (`src/grokbot_kit/doctor.py:42-48`). On the box's 1.19.5 the paid login lives in `opencode.db` and `auth list` prints
  `0 credentials` (`box/c36.md:13`), so `doctor` will report `opencode is not logged in` (`doctor.py:128`) and exit 1 for
  a logged-in box. The C15 rewording works around it in the skill; `doctor` itself (agent-run-notify door 21) is
  unchanged and may deserve a follow-up.
- The module docstring of `tests/integration/test_real_cli.py:3-5` still says only the credential files enter the
  temporary `HOME` by symlink; it does not mention the `opencode.db` copy added in `1a71566`.
- Carried from 9e9e5b9: when opencode fails before writing any JSON (error only on stderr, exit 1) the event arrives
  with `summary` `""` and no fallback; that matches doors 4 and 6 as written and may deserve a follow-up decision.
