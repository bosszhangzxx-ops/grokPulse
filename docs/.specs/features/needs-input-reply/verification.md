# needs-input-reply verification

**Verdict**: PASS
**Profile**: standard
**Diff range**: 913599d..dc430ed
**Round**: 2 - scoped
**Verifier**: independent sub-agent (author != verifier)

Escopo da rodada 2: o diff do fix `5705e3c..dc430ed` (só `tests/test_emit_wait.py`, `tests/test_reply.py`,
`tests/test_payload.py` e o `checks.md`, que ganhou a C60 e a linha da door 8 no `Coverage`; nenhum arquivo de `src/`
mudou) e os 4 vereditos não PASS da rodada 1 (C24, C54, door 8, precision gap da C5). Todas as provas, C1-C60 e as 3
de integração, rodaram de novo em `dc430ed`. O que não foi re-julgado diz `carried from 5705e3c`.

As 4 lacunas da rodada 1:

1. **C24 / door 1 (mutante sobrevivente) - fechada.** A prova `-k race_single_decision` agora seleciona dois testes:
   `test_race_single_decision` (fronteira, o `reply` sai 40-135 ms antes do prazo; instrumentado numa cópia, 17 das 20
   rodadas terminam com `user`/`allow` e 3 com `timeout`/`deny`, então os dois lados da disputa acontecem) e
   `test_race_single_decision_layer` (12 processos chamam `write_once` no mesmo instante). O mutante de escrita por
   cima (`os.replace` sem exclusão) morre no segundo (`tests/test_reply.py:209`, 3 de 3). Sozinho, o teste de
   fronteira não o mata (ver Observações).
2. **C54 / schema - fechada.** `test_needs_input_schema_new_fields` existe e roda (`tests/test_payload.py:482`):
   valida um `needs_input` com `reply_deadline` string e outro com `null`, e recusa a falta de cada campo e
   `request_id` `null`.
3. **Door 8 - fechada.** Nova C60 (`tests/test_emit_wait.py:281`) roda `codex`, `question.asked` com
   `GROKBOT_KIT_REPLY=1` e opencode sem a variável; a linha `quem espera, door 8 (5)` entrou no `Coverage` do
   `checks.md`. Os três mutantes de `_can_wait` morrem.
4. **C5 precision gap - fechada.** O limite de baixo virou `before + 3 s` (`tests/test_emit_wait.py:111`); o mutante
   `wait - 1` morre na C5 sozinha (3 de 3).

## Binding sources

carried from 5705e3c. O plano não marca nenhuma fonte como binding no sentido de design (perfil `standard`, sem
tela); o fix não tocou a interface. Fontes lidas para contexto: `plan.md`, `checks.md`.

## Checks

verified at dc430ed. Proof run (uma invocação para todas as provas não integration): `uv run pytest -rA
tests/test_launch.py tests/test_run_guards.py tests/test_config.py tests/test_emit_wait.py tests/test_reply.py
tests/test_opencode_plugin.py tests/test_opencode_plugin_v2.py tests/test_doctor.py tests/test_terminal.py
tests/test_setup_upgrade.py tests/test_update.py tests/test_skill_doc.py tests/test_docs.py tests/test_payload.py -k
"<os 60 padrões -k do checks.md, unidos por or>"` - exit 0, 95 passed, cada teste listado por nome em `PASSED`
(inclui `test_only_claude_and_plugin_v2_wait`, `test_race_single_decision`, `test_race_single_decision_layer` e
`test_needs_input_schema_new_fields`). Integration (host de dev, `claude` 2.1.318, `opencode` v2.2.4,
`GROKBOT_KIT_IT_OPENCODE_MODEL=opencode-go/glm-5.3-flash`): `uv run pytest -rA -m integration
tests/integration/test_real_hooks.py tests/integration/test_install.py -k "claude_reply_allow or opencode_reply_allow
or upgrade_opencode_real"` - 3 passed. Citações refrescadas nos 3 arquivos de teste tocados; as demais carried from
5705e3c (arquivos sem mudança).

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | hook `timeout` 660 com espera 600, ausente com 0 | `test_claude_settings_hook_timeout[3]` PASSED | `tests/test_launch.py:182` - `assert hook.get("timeout") == timeout` | PASS |
| C2 | `ask_wait_seconds` 600/120/30/0 pela precedência | `test_ask_wait_meta[...]` x5 PASSED | `tests/test_run_guards.py:295` - `assert _meta(kit)["ask_wait_seconds"] == expected` | PASS |
| C3 | `--ask-wait 10x` sai 2, sem task dir | `test_ask_wait_invalid` PASSED | `tests/test_run_guards.py:303` - `assert kit.tasks() == []` | PASS |
| C4 | `[ask] wait = "abc"` -> `ConfigError` com `ask.wait`; `"0"` carrega | `test_ask_wait_validation` PASSED | `tests/test_config.py:162` - `assert "ask.wait" in str(raised.value)`; `:164` | PASS |
| C5 | `request_id` = discriminador; `reply_deadline` = pedido + 3 s, `Z` | `test_needs_input_fields` PASSED | `tests/test_emit_wait.py:106` - `== request_id(data)`; `:108` - `deadline.endswith("Z")`; `:111` - `before + timedelta(seconds=3) <= parse_ts(deadline) <= after + timedelta(seconds=4)` | PASS |
| C6 | prazo limitado por `started_at + timeout_seconds` | `test_deadline_capped_by_task_timeout` PASSED | `tests/test_emit_wait.py:121` - `assert parse_ts(event["needs_input"]["reply_deadline"]) == expected` | PASS |
| C7 | `allow` -> JSON exato da door 6, exit 0, < 3 s | `test_claude_allow` PASSED | `tests/test_emit_wait.py:132` - `proc.stdout == json.dumps(CLAUDE_ALLOW, separators=(",", ":"))`; `:133` - `elapsed < 3` | PASS |
| C8 | `deny` com `"não"`; `null` -> `denied by the user` | `test_claude_deny_message`, `test_claude_deny_message_null` PASSED | `tests/test_emit_wait.py:142` - `== claude_deny("não")`; `:150` - `== claude_deny("denied by the user")` | PASS |
| C9 | prazo vencido grava `deny`/`timeout` e imprime `no reply before <deadline>` | `test_timeout_denies_and_records` PASSED | `tests/test_emit_wait.py:161` - `(recorded["decision"], recorded["by"]) == ("deny", "timeout")`; `:165` | PASS |
| C10 | espera 0: `reply_deadline` null, `{}`, < 1 s, sem `replies/` | `test_wait_zero_notify_only` PASSED | `tests/test_emit_wait.py:172` - `(proc.returncode, proc.stdout) == (0, "{}")`; `:175`; `:177` | PASS |
| C11 | meta antigo sem `ask_wait_seconds` = C10 | `test_old_meta_is_notify_only` PASSED | `tests/test_emit_wait.py:187` - `(proc.returncode, proc.stdout) == (0, "{}")`; `:190` | PASS |
| C12 | sink em 500 x3 e ainda espera e devolve `allow` | `test_waits_after_failed_delivery` PASSED | `tests/test_emit_wait.py:202` - `len(receiver.requests) == 3`; `:203` - `== CLAUDE_ALLOW` | PASS |
| C13 | segundo `emit` reaproveita a resposta, < 1 s, um só `needs_input` | `test_repeated_request_reuses_reply` PASSED | `tests/test_emit_wait.py:215` - `elapsed < 1`; `:216` - `len(needs_inputs(kit)) == 1` | PASS |
| C14 | dois `emit` simultâneos: um `needs_input`, ambos `allow` | `test_concurrent_same_request` PASSED | `tests/test_emit_wait.py:236` - `== [CLAUDE_ALLOW, CLAUDE_ALLOW]`; `:237` | PASS |
| C15 | resposta ilegível -> `{}`, motivo no `kit.log`, exit 0 | `test_unreadable_reply_no_decision` PASSED | `tests/test_emit_wait.py:249` - `(proc.returncode, proc.stdout) == (0, "{}")`; `:250` | PASS |
| C16 | `claude` real espera até `reply allow`, roda e termina `ok` | `-m integration test_claude_reply_allow` PASSED (rodado nesta rodada) | `tests/integration/test_real_hooks.py:176` - `(work / "criado.txt").exists()`; `:178` - `== ("completed", "ok", "success")` | PASS |
| C58 | 401: 1 tentativa e `undelivered`; 429: 3; segue esperando | `test_needs_input_delivery_statuses` PASSED | `tests/test_emit_wait.py:321` - `len(receiver.requests) == attempts`; `:322`; `:326` - `== CLAUDE_ALLOW` | PASS |
| C60 | espera 10: `codex`, `question` com `GROKBOT_KIT_REPLY=1` e opencode sem a variável não esperam | `test_only_claude_and_plugin_v2_wait` PASSED | `tests/test_emit_wait.py:292` - `(proc.returncode, proc.stdout) == (0, "{}"), source`; `:293` - `elapsed < 1`; `:295` - `reply_deadline"] is None`; `:296` - `not (task_dir / "replies").exists()` | PASS |
| C17 | `reply allow` grava `allow`/`null`/`user`/`at` e imprime a linha | `test_allow_recorded` PASSED | `tests/test_reply.py:70` - `== (0, f"recorded allow for {p.rid} (by user)")`; `:72` | PASS |
| C18 | `deny --message` grava a mensagem | `test_deny_with_message` PASSED | `tests/test_reply.py:83` - `== ("deny", "fora do repo")` | PASS |
| C19 | `allow --message` sai 2 sem `replies/` | `test_message_with_allow_rejected` PASSED | `tests/test_reply.py:91` - `returncode == 2`; `:93` | PASS |
| C20 | tarefa ou pedido desconhecido -> 1 com o motivo | `test_unknown_task_or_request` PASSED | `tests/test_reply.py:102` - `"task not found" in ...`; `:105`; `:106` | PASS |
| C21 | já respondido / vencido -> 1, arquivo intacto | `test_already_answered_or_expired` PASSED | `tests/test_reply.py:117` - `"already answered: allow" in again.stderr`; `:118`; `:127` | PASS |
| C22 | `finished_at` -> 1 `task already finished` | `test_task_finished` PASSED | `tests/test_reply.py:151` - `"task already finished" in result.stderr`; `:152` | PASS |
| C23 | `request_id` inválido -> 2; `sha256:abc` passa | `test_request_id_charset` PASSED | `tests/test_reply.py:161` - `returncode == 2`; `:165-166` | PASS |
| C24 | `reply` x prazo no mesmo instante, 20 rodadas, uma decisão | `test_race_single_decision`, `test_race_single_decision_layer` PASSED | `tests/test_reply.py:184` - `len(files) == 1`; `:186` - `body["decision"] == decision`; `:187` - `(answered == 0) == (body["by"] == "user") == (decision == "allow")`; `:209` - `len(winners) == 1`; `:210` - `recorded(path)["by"] == winners[0]` | PASS |
| C25 | `--by bot` grava, imprime e loga | `test_by_bot_logged` PASSED | `tests/test_reply.py:218` - `(by bot)`; `:219`; `:220` - `f"reply: allow for {p.rid} by bot" in ...` | PASS |
| C26 | `--by robot` -> 2 sem arquivo | `test_by_invalid` PASSED | `tests/test_reply.py:228` - `returncode == 2`; `:229` | PASS |
| C27 | `install` com v2 ou sem opencode grava o asset v2 | `test_install_picks_v2[2]` PASSED | `tests/test_opencode_plugin.py:103` - `text.splitlines()[0] == "// grokbot-kit opencode plugin for opencode 2"`; `:108` | PASS |
| C28 | `install` com v1 grava o asset v1 com marcador | `test_install_picks_v1` PASSED | `tests/test_opencode_plugin.py:119`; `:120` - `assert text == expected` | PASS |
| C29 | plugin v2 chama `emit --from opencode` com o JSON da door 14 | `test_evaluate_calls_emit` PASSED | `tests/test_opencode_plugin_v2.py:145` - `call["argv"] == ["emit", "--from", "opencode"]`; `:149`; `:151-156` | PASS |
| C30 | não bloqueia (>= 10 ticks) e timeout = espera + 60 s | `test_does_not_block` PASSED | `tests/test_opencode_plugin_v2.py:163` - `out["ticks"] >= 10`; `:164` - `== [{"timeout": (5 + 60) * 1000}]` | PASS |
| C31 | aplica `allow`/`deny`; `{}`, vazio, não JSON, exit 1, timeout deixam `ask` | `test_applies_emit_decision[7]` PASSED | `tests/test_opencode_plugin_v2.py:183` - `out["event"]["effect"] == effect`; `:184` | PASS |
| C32 | `effect` da config ou sessão filha não chamam o kit | `test_only_root_ask[3]` PASSED | `tests/test_opencode_plugin_v2.py:193`; `:194` - `harness.calls() == []` | PASS |
| C33 | sem `GROKBOT_KIT_TASK_ID`, inerte | `test_inert_without_task` PASSED | `tests/test_opencode_plugin_v2.py:200` - `out["registered"] == 0`; `:202` | PASS |
| C34 | `emit --from opencode` imprime o JSON exato da door 6 | `test_opencode_effect_output` PASSED | `tests/test_emit_wait.py:265` - `(proc.returncode, proc.stdout) == (0, expected)` | PASS |
| C35 | `doctor` acusa asset fora do major; sem marcador = 1 | `test_plugin_major_mismatch[3]` PASSED | `tests/test_doctor.py:424` - `assert expected in out["problems"]` | PASS |
| C36 | `run` reescreve antes de lançar; certo = mtime igual; ausente = nada | `test_run_rewrites_stale_plugin`, `..._untouched_when_current`, `..._absent` PASSED | `tests/test_run_guards.py:378`; `:380`; `:397` - `st_mtime == 1_000_000_000`; `:408` | PASS |
| C37 | reescrita falha: loga e a tarefa roda | `test_run_plugin_rewrite_failure` PASSED | `tests/test_run_guards.py:426` - `"cannot rewrite the opencode plugin" in log`; `:429` | PASS |
| C59 | `--standalone` com v2.2.4, sem ele com v1.19.3 | `test_opencode_standalone_by_major[2]` PASSED | `tests/test_launch.py:200` - `kit.launched()["argv"] == ["run", "--format", "json", "-m", MODELS["opencode"], *flag, "oi"]` | PASS |
| C38 | `opencode` 2.x real espera até `reply allow` e termina `ok` | `-m integration test_opencode_reply_allow` PASSED (rodado nesta rodada, `opencode-go/glm-5.3-flash`) | `tests/integration/test_real_hooks.py:186`; `:188`; `:190` - `== ("completed", "ok", "success")` | PASS |
| C39 | dois `allow` -> `completed/ok/success` | `test_all_allowed_is_success` PASSED | `tests/test_terminal.py:410` - `classify(...) == ("completed", "ok", "success")` | PASS |
| C40 | sem resposta / deny / timeout / `permission_denials` -> `denied` | `test_any_unallowed_is_denied[3]`, `..._permission_denials`, `..._legacy_record` PASSED | `tests/test_terminal.py:422` - `unanswered(...) == [asked[1]]`; `:424`; `:435` | PASS |
| C41 | `run` com pedido respondido `allow` termina `ok` | `test_run_allowed_request_ends_ok` PASSED | `tests/test_run_guards.py:347` - `== ("completed", "ok", "success")` | PASS |
| C42 | tarefa de plugin não espera nem entrega | `test_plugin_task_no_wait` PASSED | `tests/test_emit_wait.py:306` - `(0, "{}")`; `:307` - `elapsed < 1`; `:308` - `needs_inputs(kit) == []` | PASS |
| C43 | upgrade imprime `old -> new` / `already the latest` | `test_upgrade_prints_versions` PASSED | `tests/test_setup_upgrade.py:27`; `:28`; `:32` | PASS |
| C44 | upgrade de `claude` e `codex` com o argv do `add` | `test_upgrade_each_tool[2]` PASSED | `tests/test_setup_upgrade.py:44` - `calls[1] == {**calls[0], "path": ...}`; `:46` | PASS |
| C45 | sem `bin` -> 2 com a mensagem; `foo` -> 2 | `test_upgrade_not_installed` PASSED | `tests/test_setup_upgrade.py:54`; `:55`; `:56` | PASS |
| C46 | falha do instalador ou do `--version` -> 1, config intacto | `test_upgrade_failure_keeps_config[2]` PASSED | `tests/test_setup_upgrade.py:73` - `fresh.config_text() == before` | PASS |
| C47 | reescreve o plugin; ausente não cria; sem escrita -> 1 | `test_upgrade_rewrites_plugin`, `..._absent`, `..._unwritable` PASSED | `tests/test_setup_upgrade.py:84`; `:92`; `:105` | PASS |
| C48 | aviso do opencode 1.x fora de `problems`, exit igual | `test_opencode_1_warning` PASSED | `tests/test_doctor.py:442` - `["warning"] == warning`; `:449` - `code == code_2` | PASS |
| C49 | `setup cli upgrade opencode` real leva à última versão | `-m integration test_upgrade_opencode_real` PASSED (rodado nesta rodada) | `tests/integration/test_install.py:206` - `latest in version.stdout`; `:207` | PASS |
| C57 | `update apply` + v2.2.4 termina com o plugin v2 | `test_apply_rewrites_plugin_for_major` PASSED | `tests/test_update.py:691` - `call["argv"] == ["install", "opencode"]`; `:703` | PASS |
| C50 | SKILL: `reply_deadline` preenchido -> regra de risco; `null` -> `resume_hint` | `test_needs_input_reply_flow` PASSED | `tests/test_skill_doc.py:519`; `:521` | PASS |
| C51 | lista de baixo risco exata, sem `rm`/`push`/`curl`/`install` | `test_risk_rule_low_list` PASSED | `tests/test_skill_doc.py:533` - `len(items) == 4`; `:541` | PASS |
| C52 | lista de perguntar ao usuário | `test_risk_rule_ask_list` PASSED | `tests/test_skill_doc.py:563` - `assert needle in ask, needle` | PASS |
| C53 | `--by bot`, `--by user`, nunca nega sozinho, upgrade; comandos existem | `test_reply_by_and_upgrade`, `test_every_cited_command_exists` PASSED | `tests/test_skill_doc.py:570`; `:573`; `:576`; `tests/test_skill_doc.py:286` - `result.returncode == 0` | PASS |
| C54 | README/event.md nas duas línguas; schema aceita os campos novos | `gate_*_repo_clean`, `test_needs_input_reply_docs`, `test_needs_input_schema_new_fields` PASSED | `tests/test_docs.py:357`; `:362`; `:363`; `tests/test_payload.py:489` - `VALIDATOR.validate(waiting)` (com `reply_deadline` string, `:486`); `:492` - `VALIDATOR.validate(notify)` (`null`); `:496` - `not VALIDATOR.is_valid(broken), key` | PASS |
| C55 | README diz Claude/opencode 2.x/1.x e o upgrade | `test_opencode_version_note` PASSED | `tests/test_docs.py:372`; `:373` | PASS |
| C56 | CHANGELOG `[Unreleased]` com os 10 termos | `test_changelog_needs_input_reply` PASSED | `tests/test_docs.py:392` - `assert term in unreleased, term` | PASS |

Testes antigos que mudaram de valor (carried from 5705e3c): nenhum afrouxou. No fix, a única asserção antiga alterada é
`tests/test_emit_wait.py:111` (C5), que ficou mais estrita (`seconds=2` -> `seconds=3`); `tests/test_reply.py:186`
(C24) mantém a igualdade antiga e ganha `:187`.

## Coverage

Linhas recomputadas nesta rodada: door 1, door 8, `reply_deadline`, campos novos da door 2 (verified at dc430ed). As
demais: carried from 5705e3c (autoridade em `src/`, que o fix não tocou).

| Set (size) | Recomputed from | Member -> proof | Unproven |
| --- | --- | --- | --- |
| `POST` webhook statuses (4) - carried from 5705e3c | tabela de retry da agent-run-notify (`deliver.py`) | `200` C5 · `401` C58 · `429` C58 · `500` C12, C58 | - |
| `reply` exit codes (3) - carried | `src/grokbot_kit/reply.py` + argparse | `0` C17 · `1` C20-C22 · `2` C19, C23, C26 | - |
| `reply` recusas com `1` (6) - carried | `reply.py:62-81` | task C20 · finished C22 · request C20 · já respondido C21 · prazo vencido C21 · pedido sem espera `test_notify_only_request_refused` (`tests/test_reply.py:233`, sem check) | - |
| `reply` recusas com `2` (3) - carried | `reply.py:57-60`, argparse `--by` | C19 · C23 · C26 | - |
| `setup cli upgrade` exit codes (3) - carried | `setup.py` `cli_upgrade` | `0` C43 · `1` C46, C47 · `2` C45 | - |
| `setup cli upgrade` tools (3) - carried | `launch.TOOLS` | opencode C43 · claude C44 · codex C44 | - |
| precedência da espera (4) - carried | `resolve.ask_wait` | C2 x5 | - |
| espera inválida (2) - carried | `resolve.ask_wait`, `config.check_constraints` | flag C3 · config C4 | - |
| desfechos do `emit` com espera (7) - carried | `emit.py:181-243` | allow C7 · deny msg C8 · deny null C8 · prazo C9 · espera 0 C10 · reaproveitada C13 · ilegível C15 | - |
| saída por fonte, door 6 (5) - carried | `emit._answer` | C7 · C8 · C34 x2 · `{}` C10, C15 | - |
| `by`, door 1 (3) - carried | door 1 | user C17 · bot C25 · timeout C9 | - |
| `reply_deadline` (3) - verified at dc430ed | `emit.py:212-219` (espera arredondada para cima, teto `started_at + timeout`, `None`) | espera C5 (`:111`, limite de baixo `before + 3 s`; mata `wait - 1`) · teto C6 · `null` C10, C60 | - |
| door 1: uma decisão por `request_id`, nunca sobrescrita (2) - verified at dc430ed | plan door 1, `emit.write_once` (`emit.py:105-121`) | exclusão entre escritores simultâneos C24 (`tests/test_reply.py:209-211`) · disputa `reply` x prazo do `emit` C24 (`:184-187`), C21 | - |
| door 8: quem espera (5) - verified at dc430ed | plan door 8, `emit._can_wait` (`emit.py:153-157`) | claude/`permission` C7 · opencode+`GROKBOT_KIT_REPLY=1` C34 · opencode sem a variável C60 · `codex` C60 · `question` C60 | - |
| `--standalone` por major, door 9 (2) - carried | `run.py:361` | `2` C59 · `1` C59 | - |
| asset por major, door 5 (3) - carried | `opencode_plugin.asset_major` | 2 C27 · desconhecido C27 · 1 C28 | - |
| resposta do plugin v2 (6) - carried | `grokbot-kit.v2.ts` | C31 x6 | - |
| eventos ignorados pelo plugin v2 (4) - carried | `grokbot-kit.v2.ts:71-75` | sem task C33 · allow C32 · deny C32 · filha C32 | - |
| lugares que escrevem o plugin (4) - carried | `install`, `cli_upgrade`, `run`, `update apply` | C27/C28 · C47 · C36 · C57 | - |
| `doctor` e a versão (3) - carried | `doctor` | C35 x2 · C48 | - |
| classificação com respostas (5) - carried | `terminal.unanswered`/`classify` | C39, C41 · C40 x4 | - |
| campos novos do evento, door 2 (2) - verified at dc430ed | door 2 + `assets/event.v1.json:183-199` | `request_id` C5, C54 (`tests/test_payload.py:496`, `:499`) · `reply_deadline` string e `null` C54 (`:489`, `:492`), C5 | - |
| regra de risco: baixo (4) / pergunta (7) - carried | AC 36/37 | C51 · C52 | - |
| docs (4) - carried | AGENTS.md, regra de par | C54, C55, C50-C53, C56 | - |
| startup config do hook do Claude (2) - carried | `launch.claude_settings` no `run`; harness de plugin | `run` C1 · plugin C42 | - |

## Test policy rows

| Row | Files it classifies | Required proof | Expectation met |
| --- | --- | --- | --- |
| `emit.py` decide, alcançado pela CLI - verified at dc430ed | `src/grokbot_kit/emit.py` | fronteira (subprocess `emit`) C5-C15, C34, C42, C60 | yes - door 8 com os 5 membros na fronteira (C60 via subprocess `emit`) |
| `reply` ponto de entrada que decide, na fronteira - verified at dc430ed | `src/grokbot_kit/reply.py` | CLI C17-C26 | yes - C24 de fronteira com os dois desfechos da disputa; a exclusão do `write_once` provada por processos concorrentes |
| `terminal.py` decide - carried | `src/grokbot_kit/terminal.py`, `run.py` | camada C39, C40; fronteira C41 | yes |
| plugin v2 decide - carried | `assets/opencode/grokbot-kit.v2.ts` | `node` com `ctx` falso C29-C33; real C38 | yes |
| asset e marcador - carried | `opencode_plugin.py`, `run.py`, `doctor.py` | C27, C28, C35-C37 | yes |
| `setup.py` upgrade, na fronteira - carried | `src/grokbot_kit/setup.py` | CLI C43-C47; real C49 | yes |

## Faults injected

verified at dc430ed, nas superfícies que o fix criou ou tocou (C5, C24, C54, C60). Isolamento: cópia de `HEAD` por
`git archive` no scratchpad, com `.venv` próprio; cada mutação revertida do original antes da seguinte. `git status
--porcelain` da worktree real vazio antes e depois.

| Mutation | Location | Killed |
| --- | --- | --- |
| F1 `os.link(tmp, path)` -> `os.replace(tmp, path)` com o `unlink` do temporário tolerante (grava por cima, sem exclusão, sem quebrar) | `src/grokbot_kit/emit.py:116`, `:120` | yes - C24 por `tests/test_reply.py:209` (`assert 12 == 1`), 3 de 3 |
| F2 espera `wait` -> `wait - 1` | `src/grokbot_kit/emit.py:215` | yes - C5 sozinha, `tests/test_emit_wait.py:111`, 3 de 3 |
| F3 door 8: checagem de `kind` desligada; `codex` incluído; `GROKBOT_KIT_REPLY` ignorado (três variantes, uma por vez) | `src/grokbot_kit/emit.py:155`, `:157` | yes - C60, `tests/test_emit_wait.py:292`, as três |
| F4 schema: `reply_deadline` só `null` | `src/grokbot_kit/assets/event.v1.json:187-190` | yes - C54, `ValidationError` em `tests/test_payload.py:489` |
| F5 arredondamento para cima desligado (`if asked_until.microsecond:` -> `if False:`; o prazo sai truncado, até 1 s antes do pedido) | `src/grokbot_kit/emit.py:216` | yes - C5, `tests/test_emit_wait.py:111`, 13 de 15 rodadas (probabilístico: quando o `emit` cruza a virada de segundo depois do `before`, o prazo truncado ainda cabe) |

## Swept existing

carried from 5705e3c (o fix não tocou `src/`):

- data lifecycle: `replies/` sai com o `gc` - `src/grokbot_kit/gc.py:35` faz `shutil.rmtree(task_dir)`.
- authorization (n/a aprovado): `REQUEST_ID_RE` em `src/grokbot_kit/reply.py:18` e `TASK_ID_RE` impedem caminho fora
  de `replies/`; o `emit` só usa um id sem hash quando ele cabe em `_SAFE_ID` (`emit.py:21`).

## Observations (não mudam o veredito)

- Nova (rodada 2): o teste de fronteira da C24 (`test_race_single_decision`) sozinho não mata F1 - com a escrita por
  cima, a resposta do `reply` e o `deny` do prazo raramente gravam no mesmo instante, e o teste passa (1 de 1 na
  cópia). Quem prova a exclusão é `test_race_single_decision_layer`, que a mesma prova seleciona. Se a prova da C24
  for um dia estreitada para o nome exato do primeiro teste, a door 1 volta a ficar sem asserção.
- Nova (rodada 2): a C5 ainda diz "com tolerância de 1 s" (simétrica), enquanto o teste exige o prazo nunca menor que
  o pedido; F5 (prazo truncado, dentro da letra da check) morre em 13 de 15 rodadas. A asserção é mais forte que a
  check; o texto da check poderia dizer "nunca antes de pedido + 3 s".
- carried from 5705e3c - Major desconhecido (`--version` falha): `run` chama `opencode_plugin.sync(None)`
  (`src/grokbot_kit/run.py:413`), que pede o asset v2 (`src/grokbot_kit/opencode_plugin.py:29`), mas não passa
  `--standalone` (`run.py:361` exige `major is not None`). As doors 5 e 9 divergem no caso desconhecido; o fix não
  tocou nisso.
- carried from 5705e3c - C57 prova o `update apply` em duas metades (`tests/test_update.py:691` e `:703`).
- carried from 5705e3c - C49 cobre o ramo `is already the latest`, não a troca de versão; "`opencode upgrade --help`
  não é usado" não tem asserção.
- carried from 5705e3c - a recusa "pedido sem espera" do `reply` (`exit 1`) tem teste (`tests/test_reply.py:233`)
  mas nenhuma check.

## Gate

`uv run pytest` (suíte do CI) em `dc430ed` - 1092 passed, 0 failed, 53 deselected. Provas nomeadas: 95 passed, 0
failed. `-m integration` (C16, C38, C49): 3 passed, 0 failed.
