# kit-update verification

**Verdict**: PASS
**Profile**: standard
**Diff range**: 3b1b42f..80e2ad7
**Round**: 5 - scoped
**Verifier**: independent sub-agent (author != verifier)

O range da feature começa em `3b1b42f` e inclui o squash `d9efceb` na `main` (PR 19, que leva as rodadas 1 a 3 até
`c9e4e65`), seguido dos commits da correção em `fix/update/apply-versao-fixada` (rodada 4, até `3743097`) e dos dois
desta rodada.

Rodada 5, escopo `3743097..80e2ad7` (2 commits). Mudaram:

- `2c4be09`: só `tests/test_update.py`. O C39 (`:618-637`) ficou parametrizado em `same`/`lower` (`:619`, com
  `lower_than` de `:128`, que já existia). Agora afirma a primeira linha inteira do stderr, com o prefixo `uv` e o
  sufixo (`:627-631`), e afirma `later_until` preservado (`:623-624`, `:637`). Entrou também
  `test_apply_success_output_and_state_version_unreadable` (`:489-494`), sob o seletor do C22;
- `80e2ad7`: só `docs/.specs/LESSONS.md` e `docs/.specs/lessons.json`.

`src/`, `skills/`, `plan.md`, `checks.md`, `STATE.md` e `tests/integration/` não mudaram em `3743097..80e2ad7`
(`git diff --stat`). Todas as provas rodaram de novo e por inteiro em `80e2ad7`. Os 40 checks estão verdes e cada um
tem asserção localizada. As duas lacunas da rodada 4 que contavam para o veredito (F11 e F14) estão fechadas: as
duas faults reinjetadas foram mortas. As duas notas da rodada 4 que eram sobre a árvore (sufixo e prefixo da
mensagem, e o fallback do `--version`) agora têm prova e fault morta. Fica uma nota de precisão nova. O texto do C39
(`checks.md:125`) ficou atrás da prova: não nomeia a versão menor, o `later_until` nem o sufixo. Não conta como membro
sem prova, porque as provas do próprio C39 afirmam os três.

## Binding sources

carried from c9e4e65 para AD-009, AD-016/028/033, AD-032 e AD-036: a interface, o `SKILL.md` e o `doctor.py` não
mudaram. A AD-037 foi verified at 80e2ad7, porque a lacuna dela na rodada 4 era do `later_until`.

Não há fonte de design de UI (profile `standard`, sem passo 1). As ADs foram abertas em `docs/.specs/STATE.md`.

| Source | Opened | Contradiction | Uncovered |
| --- | --- | --- | --- |
| AD-009 (zero dependências, `uv tool install --managed-python`) | yes - `docs/.specs/STATE.md:15` (carried from c9e4e65) | none | - |
| AD-016/AD-028/AD-033 (plugin global `~/.config/opencode/plugins/grokbot-kit.ts`) | yes - `docs/.specs/STATE.md:22,34,39` (carried from c9e4e65) | none | - |
| AD-032 (`SKILL.md` na URL `/releases/latest/download/SKILL.md`) | yes - `docs/.specs/STATE.md:38`; C34 (carried from c9e4e65) | none | - |
| AD-036 (a própria feature) | yes - `docs/.specs/STATE.md:42` (carried from c9e4e65) | none | - |
| AD-037 (AC 37, C39, C40, C31 reescrita, `0.3.1`) | yes - `docs/.specs/STATE.md:43`, `plan.md:130`; guarda em `src/grokbot_kit/update.py:288-290`; o `later_until` intacto, que faltava na rodada 4, agora é afirmado pela prova do C39 em `tests/test_update.py:637`, com a precondição não nula em `:623-624` (o texto do C39, `checks.md:125`, ainda não o nomeia: nota de precisão, ver Coverage) | none | - |

## Checks

verified at 80e2ad7. As provas rodaram por inteiro e em lote, em três invocações:

- Prova em lote, uma invocação: `uv run pytest tests/test_update.py tests/test_skill_doc.py tests/test_doctor.py -v -k "<as 39 alternativas não-integration de checks.md, em OR>"` deu 73 passed e 50 deselected. São os 71 da rodada 4 mais `test_apply_installer_left_version[lower]` e `test_apply_success_output_and_state_version_unreadable`. Cada teste aparece listado como PASSED, inclusive `test_apply_installer_left_version[same]` e `[lower]`.
- Integração, uma invocação com o `uv` real: `uv run pytest -m integration tests/integration/test_install.py -k "update_installer_uv or update_apply_uv or update_apply_pinned_uv" -v` deu 3 passed (`test_update_installer_uv`, `test_update_apply_uv`, `test_update_apply_pinned_uv`).
- Gate: `uv run pytest` (ver Gate).

Citações refrescadas em `tests/test_update.py`, o único arquivo tocado. As linhas até `:486` não mudaram. O teste novo
do C22 ocupa `:489-494`. C23 a C29 andaram +8, o C39 está em `:618-637` e o C30 andou +16 (`:647-674`). As
citações de `tests/integration/test_install.py`, `tests/test_skill_doc.py` e `tests/test_doctor.py` não mudaram
(arquivos sem diff) e foram conferidas no ponto em `test_install.py:159-177`.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | estado ausente/vencido -> 1 GET, grava `latest`, `error` null | `-k check_fetches_when_stale` 3 casos PASSED | `tests/test_update.py:90` - `assert gets(receiver) == 1`; `:92-93` - `saved["latest"] == "9.0.0"`, `saved["error"] is None` | PASS |
| C2 | estado fresco -> 0 requisições | `-k check_uses_fresh_state` 2 casos PASSED | `tests/test_update.py:107` - `assert gets(receiver) == 0`; `:108` - `out["latest"] == state["latest"]` | PASS |
| C3 | comparação numérica por componente | `-k compare_versions` 6 casos, `-k check_update_available_boundary` 3 casos PASSED | `tests/test_update.py:125` - `update.newer(a, b) is expected` (inclui `0.2.1-0.2.2-False`); `:145-146` - `out["update_available"] is available`, `out["ask"] is available` | PASS |
| C4 | falhas do GET -> exit 0, `latest` null, `error`, estado gravado | `-k check_failure_exit_zero` 5 casos + `test_check_failure_exit_zero_non_200` PASSED | `tests/test_update.py:68` - `result.returncode == 0`; `:161-164` - `out["latest"] is None`, `update_available is False`, `ask is False`, `out["error"]`; `:167` - `saved["error"] == out["error"]`; `:174-176` - 2xx ≠ 200 | PASS |
| C5 | resposta lenta vira `error`; timeout do `urlopen` é 5 | `-k fetch_timeout` 2 testes PASSED | `tests/test_update.py:190` - `seen["timeout"] == 5`; `:197-198` - `out["error"]`, `update_available is False` | PASS |
| C6 | `{not json` tratado como ausente e regravado | `-k invalid_state_rewritten` PASSED | `tests/test_update.py:208-209` - `gets(receiver) == 1`, `read_state(...)["latest"] == "9.0.0"` | PASS |
| C7 | stdout é um objeto com exatamente as 9 chaves | `-k check_json_shape` PASSED | `tests/test_update.py:218` - `assert set(out) == KEYS` (KEYS em `:24`) | PASS |
| C8 | três linhas de texto do AC 8 | `-k check_text_lines` PASSED | `tests/test_update.py:226,231,238` - igualdade exata de `result.stdout` com as três linhas | PASS |
| C9 | recibo -> `uv` / `pipx` / null | `-k installer_detection` 3 casos PASSED | `tests/test_update.py:248` - `update.installer(tmp_path) == expected` | PASS |
| C10 | `uv tool install` real -> `installer` `uv` | `-m integration -k update_installer_uv` PASSED | `tests/integration/test_install.py:108` - `json.loads(result.stdout)["installer"] == "uv"` | PASS |
| C11 | GET com `User-Agent: grokbot-kit/<v>` | `-k user_agent_header` PASSED | `tests/test_update.py:255-256` - `request.method == "GET"`, `headers["user-agent"] == f"grokbot-kit/{__version__}"` | PASS |
| C12 | `update.json` com 5 chaves, sem temporário | `-k state_file_shape` PASSED | `tests/test_update.py:262-263` - `set(read_state(...)) == STATE_KEYS`, `sorted(...) == ["update.json"]` | PASS |
| C13 | `skip 9.0.0` exit 0, linha, grava `skipped` | `-k skip_records_version` PASSED | `tests/test_update.py:270-272` - `returncode == 0`, `stdout == "skipping grokbot-kit 9.0.0\n"`, `["skipped"] == "9.0.0"` | PASS |
| C14 | versão inválida -> exit 2, estado byte a byte igual | `-k skip_rejects_bad_version` 4 casos PASSED | `tests/test_update.py:281-282` - `returncode == 2`, `read_bytes() == before` | PASS |
| C15 | `skipped` = `latest` -> `ask` false; versão maior -> `ask` true | `-k skip_until_newer` PASSED | `tests/test_update.py:289-290` - `update_available is True`, `ask is False`; `:296-297` - `latest == "9.0.1"`, `ask is True` | PASS |
| C16 | `later` exit 0, linha, `later_until` +24 h (±60 s) | `-k later_records_24h` PASSED | `tests/test_update.py:306` - `stdout == f"asking again after {later_until}\n"`; `:308` - `abs(...) <= 60` | PASS |
| C17 | `later_until` futuro -> `ask` false; passado -> true | `-k later_until_gates_ask` PASSED | `tests/test_update.py:316` - `out["ask"] is False`; `:319` - `check(pkit)["ask"] is True` | PASS |
| C18 | tabela do `ask` (1 true + 4 false) | `-k ask_table` 6 casos PASSED | `tests/test_update.py:340` - `update.ask(available, "9.0.0", skipped, later_until, NOW) is expected` | PASS |
| C19 | `uv` falso `tool upgrade grokbot-kit`; `pipx` falso `upgrade grokbot-kit` | `-k apply_runs_installer` 2 casos PASSED | `tests/test_update.py:428` - `returncode == 0`; `:429-430` - `gets(receiver) == 1`, `venv.upgrader_calls() == [call]` | PASS |
| C20 | timeout do instalador é 300 | `-k installer_timeout_value` PASSED | `tests/test_update.py:460` - `call["timeout"] == 300` | PASS |
| C21 | com plugin, o executável novo recebe `install opencode`; sem, não | `-k apply_rewrites_plugin_with_new_exe` 2 casos PASSED | `tests/test_update.py:470-471` - `returncode == 0`, `new_kit_calls() == ([{"tool": "new-kit", "argv": ["install", "opencode"]}] if plugin else [])` | PASS |
| C22 | imprime `<instalada> -> 9.0.0`, exit 0, limpa `skipped`/`later_until` | `-k apply_success_output_and_state` 2 testes PASSED | `tests/test_update.py:478` - `receiver.respond(pypi("8.0.0"))` (a `<nova>` vem do `--version`); `:483` - `stdout == f"grokbot-kit {__version__} -> 9.0.0\n"`; `:485-486` - `skipped is None`, `later_until is None`; novo, `:492` - `FAKE_NEW_VERSION="broken"` (o `--version` ilegível); `:493-494` - `returncode == 0`, `stdout == f"grokbot-kit {__version__} -> 9.0.0\n"` (fallback para o `latest`, `update.py:287`) | PASS |
| C23 | já na última -> linha, exit 0, sem instalador | `-k apply_already_latest` PASSED | `tests/test_update.py:503-504` - `stdout == f"grokbot-kit {__version__} is the latest\n"`, `upgrader_calls() == []` | PASS |
| C24 | checagem falha -> exit 1, `update check failed:`, sem instalador | `-k apply_check_failed` PASSED | `tests/test_update.py:511-513` - `returncode == 1`, `stderr.startswith("update check failed:")`, `upgrader_calls() == []` | PASS |
| C25 | sem recibo -> exit 2 com a mensagem exata | `-k apply_unknown_installer` PASSED | `tests/test_update.py:520-521` - `returncode == 2`, `UNKNOWN in result.stderr` (texto em `:26`) | PASS |
| C26 | predicado de tarefa rodando | `-k running_task_predicate` PASSED | `tests/test_update.py:548` - `update.task_running(...) is expected` (casos a partir de `:534`); `:550,553` - `is False` para meta ausente e ilegível | PASS |
| C27 | tarefa rodando -> exit 2, `task_id` em stderr, sem instalador | `-k apply_refuses_running_task` PASSED | `tests/test_update.py:568-570` - `returncode == 2`, `task_id in result.stderr`, `upgrader_calls() == []` | PASS |
| C28 | instalador sai 3 -> exit 1, código e últimas 20 linhas, sem `install opencode`; timeout -> 1; fora do `PATH` -> 1 com `cannot run <instalador>` | `-k apply_installer_failed` 3 testes PASSED | `tests/test_update.py:578-582` - `returncode == 1`, `"3" in stderr.splitlines()[0]`, `(f"installer line {i:02d}" in stderr) is (i > 10)`, `new_kit_calls() == []`; `:591` - `update.apply() == 1`; `:604-605` - `update.apply() == 1`, `err.startswith("cannot run uv:")` | PASS |
| C29 | plugin falha -> exit 1 com a mensagem exata | `-k apply_plugin_failed` PASSED | `tests/test_update.py:613,615` - `returncode == 1`, `message in result.stderr` | PASS |
| C30 | lock com pid vivo -> 2; pid morto -> tomado; lock removido | `-k apply_lock` 2 testes PASSED | `tests/test_update.py:654-656` - `returncode == 2`, `upgrader_calls() == []`, `lock.exists()`; `:660-662` - `returncode == 0`, `len(upgrader_calls()) == 1`, `not lock.exists()`; `:672-674` - lock ilegível tomado | PASS |
| C31 | upgrade real `50.0.0` -> `50.0.1` por `--find-links`, exit 0, stdout exato, plugin chama `~/.local/bin/grokbot-kit` | `-m integration -k update_apply_uv` PASSED | `tests/integration/test_install.py:159-160` - `returncode == 0`, `result.stdout == "grokbot-kit 50.0.0 -> 50.0.1\n"`; `:162` - `f"const GROKBOT_KIT = {json.dumps(str(exe))}" in plugin_text` | PASS |
| C32 | `update check --json` em seção antes do Setup e da Tarefa | `-k update_check_before_setup_and_task` PASSED | `tests/test_skill_doc.py:341` - `b.index(s) < b.index("## Setup (primeira vez)") < b.index("## Tarefa")`; `:344-345` | PASS |
| C33 | uma pergunta, três opções, cada uma com o comando | `-k update_three_options` PASSED | `tests/test_skill_doc.py:355-356`; `:366` - `command in item` para os três pares de `:360-363` | PASS |
| C34 | baixar a URL `latest`, redirects, sobrescrever, reler | `-k update_refreshes_skill` PASSED | `tests/test_skill_doc.py:371-379` - `paragraph_with(LATEST_URL)`, `"redirects" in p`, ordem `baixe < sobrescreva < releia` | PASS |
| C35 | `apply` 1/2 -> stderr e seguir; `ask` false/`error` -> silêncio | `-k update_failure_and_silence` PASSED | `tests/test_skill_doc.py:387-388`, `:391-392` | PASS |
| C36 | todo comando citado existe no `--help`; sem `curl` | `-k every_cited_command_exists` 2 testes, `-k install_location_and_allowed_commands` PASSED | `tests/test_skill_doc.py:286` - `result.returncode == 0`; `:399` - os 4 `update`; `:400-401` - sem `curl`; `:305` - `command.split()[0] in ALLOWED` | PASS |
| C37 | `doctor --json` com `kit.update` de 9 chaves, cache, `ok`/`problems`/exit inalterados | `-k doctor_update_field` PASSED | `tests/test_doctor.py:298-305`; `:310` - `gets(receiver) == 1` na segunda chamada | PASS |
| C38 | linha `update:` com 9.0.0; ausente na versão instalada | `-k doctor_update_text_line` PASSED | `tests/test_doctor.py:320` - `UPDATE_LINE in result.stdout.splitlines()`; `:326` - sem linha `update:` | PASS |
| C39 | instalador sai 0 e o executável responde a instalada -> exit 1, `left grokbot-kit at <instalada>; it may be pinned to a version`, últimas 20 de 25 linhas, sem `install opencode`, `skipped` = `9.0.0` | `-k apply_installer_left_version` 2 casos (`same`, `lower`) PASSED | `tests/test_update.py:619` - `left` em `[__version__, lower_than(__version__)]` (`0.3.1` e `0.3.0`); `:623-624` - precondição `skipped="9.0.0"`, `later_until` 5 h no futuro; `:626` - `returncode == 1`; `:627-631` - `result.stderr.splitlines()[0] == "uv left grokbot-kit at {left}; it may be pinned to a version: reinstall the latest grokbot-kit with the tool that installed it"`; `:633` - `(f"installer line {i:02d}" in stderr) is (i > 5)` para 1..25; `:634` - `new_kit_calls() == []`; `:636-637` - `state["skipped"] == "9.0.0"`, `state["later_until"] == later_until` | PASS |
| C40 | `uv` real com instalação do arquivo de wheel não atualiza -> exit 1, `uv left grokbot-kit at <versão do checkout>; it may be pinned to a version` | `-m integration -k update_apply_pinned_uv` PASSED | `tests/integration/test_install.py:176` - `result.returncode == 1`; `:177` - `f"uv left grokbot-kit at {version}; it may be pinned to a version" in result.stderr` | PASS |

## Coverage

verified at 80e2ad7 para as linhas que a correção tocou: o resultado da guarda `newer(new, installed)` (3) e o estado
preservado pelo AC 37 (3), que tinham membro sem prova na rodada 4. Também para a origem da `<nova>` (2), linha nova
porque a correção deu prova ao fallback, e para os exits e caminhos de saída do `apply`, porque as citações de
`tests/test_update.py` andaram. "instalador da door 5" é carried from 3743097: a autoridade não mudou e as provas
seguem verdes. As outras linhas são carried from c9e4e65.

Recalculado a partir do código (`src/grokbot_kit/update.py`, sem diff em `3743097..80e2ad7`) e do plano (AC 37 em
`plan.md:130`), não da tabela do autor.

| Set (size) | Recomputed from | Member -> proof | Unproven |
| --- | --- | --- | --- |
| resultados do GET da door 3 (8) | carried from c9e4e65; `update.py:100-118` | `200` X.Y.Z C1 · sem `info.version` C4 · fora de X.Y.Z C4 · não JSON C4 · não-2xx C4[500] · 2xx ≠ 200 C4 `:172-176` · conexão recusada C4 · timeout C5 | - |
| frescor do estado (5) | carried from c9e4e65; `update.py:138-140` | ausente C1 · ok >24 h C1 · erro >1 h C1 · ok <24 h C2 · erro <1 h C2 | - |
| `update check` exit (1) | carried from c9e4e65 | `0` C4, C7, C8 | - |
| `update check` texto (3) | carried from c9e4e65; `update.py:184-189` | erro C8 · disponível C8 · última C8 | - |
| `update apply` exit (3) | `update.py:252-298` | `0` C22 `:483,494`, C23 `:503`, C31 `test_install.py:159` · `1` C24 `:511`, C28 `:578,591,604`, C29 `:613`, C39 `:626`, C40 `test_install.py:176` · `2` C25 `:520`, C27 `:568`, C30 `:654` | - |
| caminhos de saída do `update apply` (11) | `update.py:252-298` | lock ocupado `:252` C30 `:654-656` · checagem falhou `:264` C24 `:511-513` · já na última `:266-267` C23 `:503-504` · instalador desconhecido `:270` C25 `:520-521` · tarefa rodando `:273` C27 `:568-570` · timeout `:280` C28 `:591` · `cannot run <tool>` `:282` C28 `:604-605` · instalador sai ≠0 `:285` C28 `:578-582` · instalador sai 0 sem atualizar `:290` C39 `:626-637`, C40 `test_install.py:176-177` · plugin falhou `:292` C29 `:613-615` · sucesso `:297-298` C22 `:483-486`, C31 | - |
| resultado da guarda `newer(new, installed)` (3) | AC 37 (`plan.md:130`: "não é maior que a versão instalada") + `update.py:288` | maior: segue, C22 `:483`, C31 `test_install.py:160` · igual: exit 1, C39[same] `:626`, C40 `test_install.py:176` · menor: exit 1, C39[lower] `:619` (`0.3.0`), `:626`, `:631`. A F11 foi morta por `[lower]` | - |
| estado e efeitos preservados pelo AC 37 (3) | AC 37 (`plan.md:130`), AD-037 (`STATE.md:43`) + `update.py:290` | `install opencode` não chamado C39 `:634` · `skipped` intacto C39 `:636` · `later_until` intacto C39 `:637` (precondição não nula em `:623-624`). A F14 foi morta pelos dois casos | - |
| origem da `<nova>` no `apply` (2) | AC 19 (`plan.md:122`, "lida de `--version`") + `update.py:287` | `--version` legível C22 `:478,483` (PyPI `8.0.0`, stdout `9.0.0`) · ilegível -> `latest` da checagem C22 `:492-494`. A F16 foi morta | - |
| `update skip` exit (2) | carried from c9e4e65 | `0` C13 · `2` C14 | - |
| `update later` exit (1) | carried from c9e4e65 | `0` C16 | - |
| `doctor` com `kit.update` (3) | carried from c9e4e65; `doctor.py:159,171-173` | json + exit 0 C37 · linha presente C38 · linha ausente C38 | - |
| instalador da door 5 (3) | carried from 3743097; `update.py:34-35,70-75` | `uv` C9, C10, C19, C31, C40 · `pipx` C9, C19 · null C9, C25 | - |
| tabela do `ask` (5) | carried from c9e4e65 | as 5 linhas C18, mais C15/C17 | - |
| predicado de tarefa rodando (5) | carried from c9e4e65 | C26, C27 | - |
| lock do `apply` (4) | carried from c9e4e65; `update.py:223-242,252` | vivo C30 `:654-656` · morto C30 `:660-662` · ilegível C30 `:672-674` · removido C30 | - |
| opções da skill (3) | carried from c9e4e65 | C33 | - |
| doors do plano (5) | carried from c9e4e65 | 1 C7, C13, C16, C22, C36 · 2 C12 · 3 C1, C5, C11 · 4 C7, C18, C37 · 5 C9, C10, C40 | - |

Notas, que não contam como membros sem prova:

- Precisão do texto do C39 (nova, verified at 80e2ad7). `checks.md:125` ainda descreve só o caso em que o executável
  responde "a versão instalada" e só a mensagem até `pinned to a version`. Também não nomeia `later_until`. A prova do
  próprio C39 é mais forte que o texto: afirma a versão menor (`tests/test_update.py:619`), a linha inteira com prefixo
  `uv` e sufixo (`:627-631`) e o `later_until` (`:637`). O `checks.md` não está no diff desta rodada. O texto do C40
  (`checks.md:122`) e a asserção dele (`tests/integration/test_install.py:177`) continuam sem o sufixo, mas agora o
  sufixo é afirmado no CI pelo C39.
- Comportamento anterior à correção (carried from 3743097, agora com prova). Numa instalação fixada com o `--version`
  ilegível, o `apply` diria `X -> <latest>` com exit `0`, porque o fallback (`update.py:287`) passa pela guarda.
  `tests/test_update.py:489-494` fixa exatamente esse fallback como o comportamento esperado (AC 19), então mudá-lo
  agora seria decisão de spec, não lacuna da verificação.
- As três notas de precisão da rodada 3 seguem abertas, carried from c9e4e65: o texto do C4 (`checks.md:34`) e a
  linha `checks.md:158` (7 membros) sem o 2xx ≠ 200; o texto do C30 (`checks.md:116`) e a linha `checks.md:170` sem o
  lock ilegível; e o `except OSError` genérico do fetch (`update.py:111-112`) sem prova própria.

## Test policy rows

verified at 80e2ad7 para "Decide, alcançado através de uma fronteira", que estava unmet, e para "Ponto de entrada que
não decide", que classifica o `apply` cujas citações andaram. "Integração" é carried from 3743097, re-executada aqui
e verde. "Decide, sem fronteira" e "Instrumentação" são carried from c9e4e65.

Linhas de `docs/.specs/features/agent-run-notify/checks.md` (`## Test policy`), aplicadas sem mudança.

| Row | Files it classifies | Required proof | Expectation met |
| --- | --- | --- | --- |
| Decide, alcançado através de uma fronteira | `update.py`: `newer` (C3), `ask` (C18 + C15/C17), `installer` (C9 + C19/C25), frescor (C1/C2) e a guarda `newer(new, installed)` do `apply` (`:288`) | fronteira e própria camada, um caso por linha | yes - as 3 linhas da guarda têm caso na fronteira (subprocesso `grokbot-kit update apply`). Maior: C22 `tests/test_update.py:483`. Igual: C39[same] `:626`. Menor: C39[lower] `:619,626`. O `newer` tem o caso menor também na própria camada (`:125`). A F11, que sobreviveu na rodada 4, foi morta por `[lower]` |
| Decide, sem fronteira | `update.py`: `task_running` (C26; C27), `_take_lock` (C30: vivo, morto, ilegível) | própria camada, um caso por linha | yes - carried from c9e4e65 |
| Ponto de entrada que não decide | `update.py`: `check`, `skip`, `later`, `apply` pela CLI (`cli.py`) | fronteira: entrada aceita, cada recusada, cada caminho de erro | yes - os 11 caminhos do `apply` têm prova (`tests/test_update.py:483,503,511,520,568,578,591,604,613,626,654`, e o caminho do AC 37 também pelo `uv` real, `tests/integration/test_install.py:176`) |
| Instrumentação, repasse | `doctor.py` (`kit.update` e a linha `update:`) | nenhuma própria; coberto por quem consome | yes - carried from c9e4e65; C37 e C38 verdes em 80e2ad7 |
| Integração com CLI real ou GitHub | `uv tool install`/`uv tool upgrade` reais | `-m integration` executado com o `uv` real | yes - carried from 3743097; C10, C31 e C40 rodaram de novo aqui com o `uv` real em 80e2ad7 (3 passed). O `pipx` real não existe nesta máquina (declarado em checks.md) |

Swept: carried from 3743097. O `## Swept` do checks.md não tem linhas `existing`, e nem o `checks.md` nem o código
mudaram nesta rodada.

## Faults injected

verified at 80e2ad7 para F11, F14, F12r, F15 e F16, as superfícies que a correção criou ou passou a afirmar: o sentido
"menor" da guarda, o `later_until`, o prefixo e o sufixo da mensagem e o fallback do `--version`. F1 a F9 são carried
from c9e4e65 e F10 e F13 são carried from 3743097. O `src/` não mudou e as provas que mataram essas faults seguem
verdes em 80e2ad7.

Rodada 5: worktree scratch em `80e2ad7`
(`/tmp/claude-1000/-home-rodrigo-projetos-pessoal-worktrees-grokbot-kit-kit-update/cfb9c49a-125d-4c99-a510-ee5f78f06b0d/scratchpad/verify-wt5`,
`git worktree add --detach`). O `git status --porcelain` do tree real antes era só ` M
docs/.specs/features/kit-update/verification.md` (o relatório da rodada 4, ainda não commitado). Gravei também o
sha256 desse arquivo. Depois da remoção da scratch (`git worktree remove --force` e `git worktree prune`), o porcelain
era idêntico (`diff` vazio) e o sha256 do `verification.md` batia (`sha256sum -c` OK), antes de este relatório ser
escrito. Não usei `git stash`. Cada fault foi revertida com `git checkout -- src` antes da seguinte. A rodada 5
injetou 5 faults, dentro do teto.

| Mutation | Location | Killed |
| --- | --- | --- |
| F1: `ask` ignora `skipped` | `src/grokbot_kit/update.py:67` | yes - `test_ask_table[True-9.0.0-None-False]` (carried from c9e4e65) |
| F2: frescor usa sempre 24 h | `src/grokbot_kit/update.py:140` | yes - `test_check_fetches_when_stale[error-older-than-1h]` (carried from c9e4e65) |
| F3: `<nova>` vem do `latest` do PyPI em vez de `<exe> --version` | `src/grokbot_kit/update.py:287` | yes - `test_apply_success_output_and_state` (carried from c9e4e65) |
| F4: linha `update:` do doctor condicionada a `latest` | `src/grokbot_kit/doctor.py:172` | yes - `test_doctor_update_text_line` (carried from c9e4e65) |
| F5: "Agora não" mapeada para `update apply` | `skills/grokbot-kit/SKILL.md:42` | yes - `test_update_three_options` (carried from c9e4e65) |
| F6: `cannot run` sai com `2` | `src/grokbot_kit/update.py:282` | yes - `test_apply_installer_failed_not_found` (carried from c9e4e65) |
| F7: `cannot run <tool>:` -> `could not start <tool>:` | `src/grokbot_kit/update.py:282` | yes - `test_apply_installer_failed_not_found` (carried from c9e4e65) |
| F8: `status != 200` -> `status >= 300` | `src/grokbot_kit/update.py:102` | yes - `test_check_failure_exit_zero_non_200` (carried from c9e4e65) |
| F9: lock ilegível tratado como dono vivo | `src/grokbot_kit/update.py:234` | yes - `test_apply_lock_unreadable` (carried from c9e4e65) |
| F10: guarda do AC 37 removida | `src/grokbot_kit/update.py:288` | yes - `test_apply_installer_left_version`, `test_update_apply_pinned_uv` (carried from 3743097) |
| F13: cauda do stderr retirada da mensagem do AC 37 | `src/grokbot_kit/update.py:290` | yes - `test_apply_installer_left_version` em `:633` (carried from 3743097) |
| F11 (reinjetada): `if not newer(new, out["installed"])` -> `if new == out["installed"]` | `src/grokbot_kit/update.py:288` | yes - `-k apply_installer_left_version`: 1 failed, 1 passed. `test_apply_installer_left_version[lower]` falhou com `assert 0 == 1`, stdout `grokbot-kit 0.3.1 -> 0.3.0` (`tests/test_update.py:626`), e `[same]` passou, como esperado |
| F14 (reinjetada): o caminho do AC 37 faz `state.update(later_until=None); save_state(state)` antes de sair com 1 | `src/grokbot_kit/update.py:289` | yes - `-k apply_installer_left_version`: 2 failed. `[same]` e `[lower]` falharam em `:637` com `assert None == '2026-10-22T02:07:31Z'` |
| F12r (reinjetada): prefixo `{argv[0]} ` retirado (`left grokbot-kit at ...`) | `src/grokbot_kit/update.py:290` | yes - `-k apply_installer_left_version`: 2 failed (`[same]`, `[lower]`) em `:631`. Na rodada 4 só a C40, fora do CI, matava esta fault; agora o C39 mata no CI |
| F15: sufixo retirado, `PINNED = "it may be pinned to a version"` | `src/grokbot_kit/update.py:34` | yes - `-k apply_installer_left_version`: 2 failed em `:631` (`'uv left grok... to a version' == 'uv left grok... installed it'`) |
| F16: fallback do `--version` ilegível `or out["latest"]` -> `or out["installed"]` | `src/grokbot_kit/update.py:287` | yes - `-k apply_success_output_and_state`: 1 failed, 1 passed. `test_apply_success_output_and_state_version_unreadable` falhou em `:493` (`assert 1 == 0`, stderr `uv left grokbot-kit at 0.3.1; ...`). `test_apply_success_output_and_state` passou, porque lá o `--version` é legível |

## Gate

verified at 80e2ad7. Rodaram três comandos:

- `uv run pytest`: 619 passed, 0 failed, 19 deselected (`-m integration`). São os 617 da rodada 4 mais
  `test_apply_installer_left_version[lower]` e `test_apply_success_output_and_state_version_unreadable`.
- `uv run pytest -m integration tests/integration/test_install.py -k "update_installer_uv or update_apply_uv or update_apply_pinned_uv" -v`:
  3 passed, 0 failed.
- A prova em lote dos checks não-integration: 73 passed, 50 deselected.

Ranked gaps (nenhum conta para o veredito, são notas):

1. (precisão) O texto do C39 (`docs/.specs/features/kit-update/checks.md:125`) ficou atrás da prova. Não nomeia a
   versão menor, o `later_until` nem o sufixo, que a prova afirma em `tests/test_update.py:619,631,637`. O texto do C40
   (`checks.md:122`) e a asserção dele (`tests/integration/test_install.py:177`) não têm o sufixo. C39, C40.
2. (comportamento, decisão de spec) Numa instalação fixada com o `--version` ilegível, o `apply` reporta sucesso
   `X -> <latest>` com exit `0`, pelo fallback de `src/grokbot_kit/update.py:287`, e
   `tests/test_update.py:489-494` fixa esse fallback como esperado. C22, C39.
3. (notas carried from c9e4e65) Texto do C4 (`checks.md:34`, `:158`), texto do C30 (`checks.md:116`, `:170`) e o
   `except OSError` do fetch (`src/grokbot_kit/update.py:111-112`).
