# kit-update checks

Profile: standard
Plan: `docs/.specs/features/kit-update/plan.md`

40 checks em 5 slices (C39 e C40 aditivos pela AD-037) · 5 one-way doors · 0 open

Convenções das provas:

- `uv run pytest <arquivo> -k <nome>` roda no CI: `HOME` isolado em `tmp_path`, receptor HTTP local em `127.0.0.1`
  (o `Receiver` do `tests/conftest.py` ganha `do_GET`) apontado por `GROKBOT_KIT_PYPI_URL`.
- O `apply` na fronteira roda de um venv falso do kit em `tmp_path` (`pyvenv.cfg`, `bin/python` ligado ao
  interpretador dos testes, `bin/grokbot-kit` e o arquivo de recibo da door 5 em `sys.prefix`), com `uv` e `pipx`
  falsos em `tests/fakes/installers/` que gravam a chamada em `FAKE_CALLS`, saem com `FAKE_UPGRADE_EXIT` (padrão `0`)
  e trocam o `bin/grokbot-kit` do venv falso por um que responde `--version` com `grokbot-kit 9.0.0` e grava cada
  chamada.
- `uv run pytest -m integration <arquivo> -k <nome>` roda só no box, com o `uv` real; fica fora do CI. O `pipx` não
  existe no box (SPEC), então o ramo `pipx` é provado só na própria camada e pelo `pipx` falso.

## Checks

### S1 - o kit sabe se há versão nova · 6 arquivos · ~55 KB · ~14k

**C1** - Com o estado ausente, com `checked_at` de mais de 24 h e `error` `null`, ou com `checked_at` de mais de 1 h e `error` preenchido, `update check --json` faz exatamente 1 `GET` no receptor e grava `checked_at`, `latest` = `info.version` e `error` `null` (AC 1, doors 2 e 3)
Proof: `uv run pytest tests/test_update.py -k check_fetches_when_stale`

**C2** - Com `checked_at` de menos de 24 h e `error` `null`, ou de menos de 1 h e `error` preenchido, `update check --json` responde do estado com 0 requisições no receptor (AC 2)
Proof: `uv run pytest tests/test_update.py -k check_uses_fresh_state`

**C3** - A comparação de `X.Y.Z` é numérica por componente: `0.3.0` > `0.2.2`, `0.10.0` > `0.9.0`, `1.0.0` > `0.99.99` dão `update_available` `true`; `0.2.2` = `0.2.2` e `0.2.1` < `0.2.2` dão `update_available` `false` e `ask` `false` (AC 3, AC 4)
Proof: `uv run pytest tests/test_update.py -k compare_versions`
Proof: `uv run pytest tests/test_update.py -k check_update_available_boundary`

**C4** - Receptor desligado, status `500`, `200` com corpo que não é JSON, `200` sem `info.version` e `200` com `info.version` = `"1.0"` fazem `update check --json` sair com `0`, com `latest` `null`, `update_available` `false`, `ask` `false`, `error` não vazio, e gravar `checked_at` e `error` no estado (AC 5)
Proof: `uv run pytest tests/test_update.py -k check_failure_exit_zero`

**C5** - Uma resposta que demora mais que o timeout da door 3 vira `error` com `update_available` `false`; o timeout passado ao `urlopen` é `5` (AC 5, door 3)
Proof: `uv run pytest tests/test_update.py -k fetch_timeout`

**C6** - `update.json` com conteúdo `{not json` é tratado como ausente: `update check --json` faz 1 `GET` e regrava o arquivo como JSON válido (AC 6)
Proof: `uv run pytest tests/test_update.py -k invalid_state_rewritten`

**C7** - O stdout de `update check --json` é um único objeto JSON cujas chaves são exatamente `installed`, `latest`, `update_available`, `ask`, `skipped`, `later_until`, `checked_at`, `installer`, `error` (AC 7, door 4)
Proof: `uv run pytest tests/test_update.py -k check_json_shape`

**C8** - Sem `--json`, `update check` imprime exatamente uma das três linhas do AC 8: `grokbot-kit 9.0.0 available (installed <v>); run: grokbot-kit update apply`, `grokbot-kit <v> is the latest`, ou `update check failed: <error>` (AC 8)
Proof: `uv run pytest tests/test_update.py -k check_text_lines`

**C9** - Com `uv-receipt.toml` em `sys.prefix` o `installer` é `uv`; com `pipx_metadata.json` é `pipx`; sem nenhum dos dois é `null` (AC 9, door 5)
Proof: `uv run pytest tests/test_update.py -k installer_detection`

**C10** - Com o kit instalado por `uv tool install --managed-python <wheel deste checkout>` num `HOME` limpo, `update check --json` dá `installer` `uv` (AC 9, door 5)
Proof: `uv run pytest -m integration tests/integration/test_install.py -k update_installer_uv`

**C11** - A requisição recebida pelo receptor é um `GET` com o header `User-Agent: grokbot-kit/<versão instalada>` (AC 10, door 3)
Proof: `uv run pytest tests/test_update.py -k user_agent_header`

**C12** - Depois de `update check`, `~/.grokbot-kit/update.json` tem exatamente as chaves `checked_at`, `latest`, `error`, `skipped`, `later_until`, e nenhum arquivo temporário fica em `~/.grokbot-kit/` (door 2)
Proof: `uv run pytest tests/test_update.py -k state_file_shape`

### S2 - o usuário adia ou pula uma versão · 2 arquivos · ~30 KB · ~8k

**C13** - `update skip 9.0.0` sai com `0`, imprime `skipping grokbot-kit 9.0.0` e grava `skipped` = `"9.0.0"` (AC 11)
Proof: `uv run pytest tests/test_update.py -k skip_records_version`

**C14** - `update skip` com `latest`, `1.2`, `v1.2.3` e `1.2.3.4` sai com `2` e o `update.json` fica byte a byte igual (AC 12)
Proof: `uv run pytest tests/test_update.py -k skip_rejects_bad_version`

**C15** - Com o receptor em `9.0.0` e `skipped` = `9.0.0`, `update check --json` dá `update_available` `true` e `ask` `false`; com o receptor em `9.0.1` e o cache vencido, `ask` `true` (AC 13, AC 14)
Proof: `uv run pytest tests/test_update.py -k skip_until_newer`

**C16** - `update later` sai com `0`, imprime `asking again after <RFC 3339>` e grava `later_until` a 24 h de agora (tolerância de 60 s) (AC 15)
Proof: `uv run pytest tests/test_update.py -k later_records_24h`

**C17** - Com `later_until` no futuro, `ask` `false`; com `later_until` no passado, `ask` `true` (receptor em `9.0.0`) (AC 16)
Proof: `uv run pytest tests/test_update.py -k later_until_gates_ask`

**C18** - A função que decide `ask` dá `true` só na linha `update_available` `true`, `skipped` diferente de `latest`, agora ≥ `later_until`; as outras 4 linhas da tabela (`update_available` `false`; `skipped` = `latest`; `later_until` no futuro; `skipped` = `latest` com `later_until` no futuro) dão `false` (door 4)
Proof: `uv run pytest tests/test_update.py -k ask_table`

### S3 - o kit se atualiza pelo instalador que o instalou · 5 arquivos · ~45 KB · ~11k

**C19** - No venv falso com recibo `uv`, estado dizendo `latest` = versão instalada e receptor em `9.0.0`, `update apply` chama o `uv` falso com exatamente `tool upgrade grokbot-kit`; com recibo `pipx`, chama o `pipx` falso com exatamente `upgrade grokbot-kit` (AC 17, door 5)
Proof: `uv run pytest tests/test_update.py -k apply_runs_installer`

**C20** - O timeout passado ao `subprocess.run` do instalador é `300` (AC 17)
Proof: `uv run pytest tests/test_update.py -k installer_timeout_value`

**C21** - Com o plugin em `~/.config/opencode/plugins/grokbot-kit.ts`, depois do upgrade o `bin/grokbot-kit` trocado pelo instalador falso recebe `install opencode`; sem o plugin, não recebe (AC 18)
Proof: `uv run pytest tests/test_update.py -k apply_rewrites_plugin_with_new_exe`

**C22** - Com upgrade e plugin em `0`, `update apply` imprime `grokbot-kit <instalada> -> 9.0.0`, sai com `0`, e o estado fica com `skipped` e `later_until` `null` (AC 19)
Proof: `uv run pytest tests/test_update.py -k apply_success_output_and_state`

**C23** - Com o receptor na versão instalada, `update apply` imprime `grokbot-kit <v> is the latest`, sai com `0` e o `FAKE_CALLS` não tem chamada ao instalador (AC 20)
Proof: `uv run pytest tests/test_update.py -k apply_already_latest`

**C24** - Com o receptor desligado, `update apply` sai com `1`, stderr começa com `update check failed:`, e nenhum instalador é chamado (AC 21)
Proof: `uv run pytest tests/test_update.py -k apply_check_failed`

**C25** - Sem recibo em `sys.prefix`, `update apply` sai com `2` com `cannot tell how grokbot-kit was installed; upgrade it with the tool that installed it` em stderr (AC 22)
Proof: `uv run pytest tests/test_update.py -k apply_unknown_installer`

**C26** - O predicado de tarefa rodando dá `true` para `finished_at` `null` com `started_at` + `timeout_seconds` + 60 s no futuro, e `false` para `finished_at` preenchido, para `finished_at` `null` com a janela já vencida, e para `meta.json` ausente ou ilegível (AC 23)
Proof: `uv run pytest tests/test_update.py -k running_task_predicate`

**C27** - Com uma tarefa rodando em `~/.grokbot-kit/tasks/`, `update apply` sai com `2`, o `task_id` dela aparece em stderr e nenhum instalador é chamado (AC 23)
Proof: `uv run pytest tests/test_update.py -k apply_refuses_running_task`

**C28** - Com `FAKE_UPGRADE_EXIT=3` e 30 linhas em stderr do instalador falso, `update apply` sai com `1`, stderr tem `3` e exatamente as últimas 20 linhas, e `install opencode` não é chamado; um instalador que passa do timeout também dá `1`, e um instalador que não existe no `PATH` dá `1` com `cannot run <instalador>` em stderr (AC 24; o caso do `PATH` entrou na verificação, rodada 1)
Proof: `uv run pytest tests/test_update.py -k apply_installer_failed`

**C29** - Com upgrade em `0` e o `install opencode` do executável novo saindo com `1`, `update apply` sai com `1` com `upgraded to 9.0.0, but the opencode plugin was not rewritten; run: grokbot-kit install opencode` em stderr (AC 25)
Proof: `uv run pytest tests/test_update.py -k apply_plugin_failed`

**C30** - Com `~/.grokbot-kit/update.lock` contendo o pid de um processo vivo, `update apply` sai com `2`; com o pid de um processo que não existe, o lock é tomado e o `apply` segue; depois do `apply`, o lock não existe (AC 26)
Proof: `uv run pytest tests/test_update.py -k apply_lock`

**C31** - No box, com o kit instalado sem versão fixada por `uv tool install --managed-python --find-links <dir> grokbot-kit` a partir de uma wheel deste checkout marcada `50.0.0`, num `HOME` limpo, com o plugin instalado, uma wheel `50.0.1` acrescentada a `<dir>` e `GROKBOT_KIT_PYPI_URL` num receptor em `99.0.0`, `update apply` roda o `uv tool upgrade grokbot-kit` real, sai com `0`, imprime `grokbot-kit 50.0.0 -> 50.0.1`, e o plugin continua chamando `~/.local/bin/grokbot-kit` (AC 17, AC 18, AC 19, door 5; cenário reescrito pela AD-037: o anterior, instalado do arquivo de wheel, virou a C40)
Proof: `uv run pytest -m integration tests/integration/test_install.py -k update_apply_uv`

**C40** - No box, com o kit instalado por `uv tool install --managed-python <arquivo da wheel deste checkout>` num `HOME` limpo e `GROKBOT_KIT_PYPI_URL` num receptor em `9.0.0`, `update apply` roda o `uv tool upgrade grokbot-kit` real, que não atualiza, e sai com `1` com `uv left grokbot-kit at <versão do checkout>; it may be pinned to a version` em stderr (AC 37, AD-037)
Proof: `uv run pytest -m integration tests/integration/test_install.py -k update_apply_pinned_uv`

**C39** - Com o `bin/grokbot-kit` trocado pelo instalador falso respondendo `--version` com a versão instalada, o plugin presente, `skipped` = `9.0.0` no estado e 25 linhas em stderr do instalador, `update apply` sai com `1`, stderr tem `left grokbot-kit at <instalada>; it may be pinned to a version` e exatamente as últimas 20 linhas do instalador, `install opencode` não é chamado e o estado continua com `skipped` = `9.0.0` (AC 37)
Proof: `uv run pytest tests/test_update.py -k apply_installer_left_version`

### S4 - o bot pergunta e atualiza tudo · 3 arquivos · ~25 KB · ~6k

**C32** - O `SKILL.md` cita `grokbot-kit update check --json` numa seção que vem antes de `## Setup (primeira vez)` e manda rodá-lo antes do Setup e antes de delegar uma Tarefa (AC 27)
Proof: `uv run pytest tests/test_skill_doc.py -k update_check_before_setup_and_task`

**C33** - A seção de atualização manda uma única pergunta de múltipla escolha quando `ask` é `true`, com três opções - atualizar agora, agora não, pular a versão - e cada uma ligada a `grokbot-kit update apply`, `grokbot-kit update later` e `grokbot-kit update skip <latest>` (AC 28, AC 29)
Proof: `uv run pytest tests/test_skill_doc.py -k update_three_options`

**C34** - Depois do `update apply` com `0`, o `SKILL.md` manda baixar `https://github.com/rodrigo-pasini/grokbot-kit/releases/latest/download/SKILL.md` seguindo redirects, sobrescrever o `SKILL.md` do diretório de workflows da skill e reler a skill (AC 30)
Proof: `uv run pytest tests/test_skill_doc.py -k update_refreshes_skill`

**C35** - O `SKILL.md` manda contar a mensagem de stderr e seguir com o pedido quando o `apply` sai com `1` ou `2`, e seguir sem mencionar atualização quando `ask` é `false` ou há `error` (AC 31, AC 32)
Proof: `uv run pytest tests/test_skill_doc.py -k update_failure_and_silence`

**C36** - Todo comando `grokbot-kit` citado no `SKILL.md`, inclusive os quatro `update`, existe no `--help`, e o `SKILL.md` não cita `curl` (AC 33)
Proof: `uv run pytest tests/test_skill_doc.py -k every_cited_command_exists`
Proof: `uv run pytest tests/test_skill_doc.py -k install_location_and_allowed_commands`

### S5 - o doctor mostra a atualização · 2 arquivos · ~20 KB · ~5k

**C37** - `doctor --json` com receptor em `9.0.0` tem `kit.update` com as nove chaves da door 4 e `update_available` `true`; com estado fresco, 0 requisições no receptor; e, com a config sem problemas, sai com `0`, `ok` `true` e `problems` `[]` (AC 34, AC 35)
Proof: `uv run pytest tests/test_doctor.py -k doctor_update_field`

**C38** - `doctor` em texto com receptor em `9.0.0` imprime a linha `update: grokbot-kit 9.0.0 available; run: grokbot-kit update apply`, e não a imprime com o receptor na versão instalada (AC 36)
Proof: `uv run pytest tests/test_doctor.py -k doctor_update_text_line`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET https://pypi.org/pypi/grokbot-kit/json`: resultados (7) | `200` com `X.Y.Z` C1 · `200` sem `info.version` C4 · `200` com versão fora de `X.Y.Z` C4 · `200` não JSON C4 · `500` C4 · conexão recusada C4 · timeout C5 | - |
| frescor do estado (5) | ausente C1 · ok com mais de 24 h C1 · erro com mais de 1 h C1 · ok com menos de 24 h C2 · erro com menos de 1 h C2 | - |
| `update check` exit (1) | `0` C4, C7 | - |
| `update check` texto (3) | disponível C8 · última C8 · falhou C8 | - |
| `update apply` exit (3) | `0` C22, C23 · `1` C24, C28, C29, C39 · `2` C25, C27, C30 | - |
| `update apply` caminhos de saída (11) | instalador saiu com `0` sem atualizar C39, C40 · sucesso C22 · já na última C23 · checagem falhou C24 · instalador desconhecido C25 · tarefa rodando C27 · instalador saiu com erro C28 · instalador passou do timeout C28 · instalador fora do `PATH` C28 · plugin falhou C29 · lock de outro `apply` C30 | - |
| `update skip` exit (2) | `0` C13 · `2` C14 | - |
| `update later` exit (1) | `0` C16 | - |
| `doctor --json` exit com update (1) | `0` C37 | - |
| instalador da door 5 (3) | `uv` C9, C10, C19, C31 · `pipx` C9, C19 · `null` C9, C25 | - |
| tabela de `ask` (5 linhas) | C18, table-driven sobre as 5 | - |
| predicado de tarefa rodando (5) | rodando C26, C27 · terminada C26 · janela vencida C26 · `meta.json` ausente C26 · ilegível C26 | - |
| lock do `apply` (3) | pid vivo C30 · pid morto C30 · removido no fim C30 | - |
| opções da skill (3) | atualizar C33 · agora não C33 · pular C33 | - |
| doors do plano (5) | 1 comandos C7, C13, C16, C22, C36 · 2 estado C12 · 3 fonte C1, C5, C11 · 4 objeto C7, C18, C37 · 5 instalador C9, C10 | - |

- Claims que nomeiam um exit code, header ou formato: C4, C7, C11, C13-C16, C22-C30, C37 - cada um tem prova que
  cruza a fronteira (subprocesso `grokbot-kit` contra o receptor local)
- C3, C9, C18 e C26 provam a tabela na própria camada e têm, além disso, uma prova na fronteira (para C3, o
  `check_update_available_boundary`; para C9, C19 e C25; para C18, C15 e C17; para C26, C27)

## Test policy

As linhas da `## Test policy` de `docs/.specs/features/agent-run-notify/checks.md` valem aqui sem mudança (o repo
não tem guia de testes; essas linhas são o padrão do projeto).

Evidência:

- `update.py`, comparação de versão: 3 componentes, 2 saídas -> decide, alcançado pela CLI (C3)
- `update.py`, frescor do estado: 5 casos -> decide (C1, C2)
- `update.py`, `ask`: 3 condições, 5 linhas -> decide, alcançado pela CLI (C18 + C15/C17)
- `update.py`, instalador: 3 linhas -> decide (C9 + C19/C25)
- `update.py`, tarefa rodando: 5 casos -> decide (C26 + C27); análogo: `gc.removable` (`tests/test_gc.py`), mesma
  forma e já provado na própria camada
- `update.py`, `apply`: 11 caminhos de saída -> ponto de entrada que decide, provado na fronteira (C22-C30, C39)
- `doctor.py`: repassa o objeto -> instrumentação, coberta por C37/C38

Custo: 6 provas na própria camada e 28 na fronteira, em 3 arquivos de teste, mais 2 `-m integration` no box.

## Swept

- validation: C14 (versão do `skip`), C4 (versão do PyPI fora de `X.Y.Z`), C6 (estado ilegível)
- failure modes: C4, C24, C28, C29
- idempotency: C23 (`apply` sem versão nova não roda instalador), C12 (gravação por `os.replace`, sem temporário)
- authorization: n/a - comando local do usuário do box; o PyPI é público e sem auth; rate limit: C2 (no máximo 1 `GET` a cada 24 h, 1 h em falha)
- concurrency: C30 (lock do `apply`), C27 (tarefa rodando), C12 (troca atômica do estado)
- data lifecycle: C22 (o `apply` limpa `skipped` e `later_until`); o `update.json` é um arquivo único, sem expiração além das janelas do C1/C2
- dependency failure: C4, C5, C24 (PyPI), C28 (instalador), C29 (plugin)
- state transitions: C15, C17, C18, C22
- observability: C22 (linha `<antiga> -> <nova>`), C28 (código e cauda do stderr do instalador); sem log próprio - o `kit.log` é por tarefa e o `apply` não é uma tarefa

## Handoff

Arquivos tocados: existentes `cli.py` (7,4 KB), `doctor.py` (8,5 KB), `SKILL.md` (10 KB), `tests/test_doctor.py`
(9,1 KB), `tests/test_skill_doc.py` (11,6 KB), `tests/conftest.py` (9 KB), `tests/fakes/installers/*` (2,7 KB),
`tests/integration/test_install.py` (2,5 KB), `CHANGELOG.md` (8,1 KB) = 69 KB; novos `src/grokbot_kit/update.py`
(~10 KB), `tests/test_update.py` (~20 KB), `uv` e `pipx` falsos (~2 KB) = ~32 KB. Total ~101 KB ÷ 4 ≈ 25k, mais a
leitura fixa de `plan.md` (18 KB) e deste arquivo (~16 KB) ≈ 9k: 34k, abaixo do budget de 150k.

- S1 = 14k; S2 a 22k; S3 a 33k; S4 a 39k; S5 a 44k (com sobreposição de arquivos; o total real é o 34k acima) → um builder
- Mechanism: um builder
- C10, C31 e C40 rodam só no box (`-m integration`); o `pipx` real não existe no box
