# model-setup-docs checks

Profile: standard
Plan: `docs/.specs/features/model-setup-docs/plan.md`

50 checks em 6 slices · 7 one-way doors · 0 open

Convenções das provas:

- `uv run pytest <arquivo> -k <nome>` roda no CI, com o `HOME` isolado em `tmp_path` e as CLIs falsas de
  `tests/fakes/` (`fake_agent.py`). A CLI falsa ganha `FAKE_STDOUT_BY_MODEL` (objeto JSON `{"<id>": "<stdout>"}`,
  escolhido pelo `-m`/`--model` do argv; sem o id, vale `FAKE_STDOUT`), para uma tarefa ver saídas diferentes por
  tentativa.
- `uv run pytest -m integration <arquivo> -k <nome>` fica fora do CI. O do opencode roda no box pelo bot (o box não tem
  ssh daqui), e o do `claude` roda no host de dev.
- Prova de shell: o comando inteiro, que sai com `0` exatamente quando o check vale.
- Seguem verdes, sem mudança de asserção, as provas da agent-run-notify que tocam a mesma superfície:
  `tests/test_skill_doc.py` (inteiro, inclusive `test_models_refresh_and_free_first`, `test_no_literal_model_ids` e
  `test_every_cited_command_exists`), `tests/test_repo_files.py -k "contributing or readme"` e
  `tests/test_setup_tiers.py`.

## Checks

### S1 - o kit mostra e grava os provedores do opencode · 9 arquivos · ~60 KB · ~15k

**C1** - `setup models refresh --json` com o opencode falso listando `opencode/a-free`, `opencode-go/b` e com o claude aceitando `sonnet` imprime em stdout só um objeto JSON `{"models": [...]}` com um item `{"tool", "id", "provider"}` por id, na ordem da descoberta, nenhuma linha `<tool>\t<id>`, e sai com `0` (AC 1, door 1)
Proof: `uv run pytest tests/test_models.py -k refresh_json_shape`

**C2** - No objeto do C1, `opencode/a-free` tem `provider` `opencode`, `opencode-go/b` tem `opencode-go`, um id com dois `/` (`ollama/x/y`) tem `ollama`, e os ids do `claude` e do `codex` têm `provider` `null` (AC 2)
Proof: `uv run pytest tests/test_models.py -k refresh_json_provider`

**C3** - Com o opencode falso saindo com `1` em `opencode models` e o claude aceitando `sonnet`, `setup models refresh --json` sai com `1`, o objeto não tem item `opencode` e tem os do `claude`, e o erro do opencode vai a stderr (AC 1, Observable)
Proof: `uv run pytest tests/test_models.py -k refresh_json_partial_failure`

**C4** - `setup models refresh` sem `--json` imprime as linhas `opencode\t<id>` de hoje e nenhuma linha começa com `{` (AC 3)
Proof: `uv run pytest tests/test_models.py -k refresh_text_unchanged`

**C5** - `setup providers opencode opencode-go` com `opencode` instalado e `opencode-go/b` em `models` grava `[cli.opencode] providers = ["opencode-go"]`, não muda `models`, `tiers` nem `bin`, imprime `opencode providers: opencode-go` e sai com `0`; com `opencode-go opencode` grava a lista nessa ordem (AC 4, door 2)
Proof: `uv run pytest tests/test_setup_providers.py -k providers_written`

**C6** - Saem com `2`, com o config byte a byte igual, as três recusas: `setup providers claude x` (stderr com `providers apply only to opencode`), `opencode` fora de `setup.installed` (stderr com `grokbot-kit setup cli add opencode`) e provedor `nada` sem id em `models` (stderr com `nada` e `grokbot-kit setup models refresh opencode`) (AC 5, AC 6, AC 7)
Proof: `uv run pytest tests/test_setup_providers.py -k providers_refused`

**C7** - Com `providers = ["opencode-go"]`, `setup tiers opencode standard opencode-go/b opencode/a-free` sai com `2`, stderr cita `opencode/a-free` e `grokbot-kit setup providers opencode`, e o config fica byte a byte igual (AC 8, door 3)
Proof: `uv run pytest tests/test_setup_tiers.py -k tiers_provider_outside`

**C8** - Sem `providers`, `setup tiers opencode standard opencode/a-free opencode-go/b` grava os dois e sai com `0` (AC 9)
Proof: `uv run pytest tests/test_setup_tiers.py -k tiers_no_providers`

**C9** - Com `tiers.standard = ["opencode/a-free"]`, `setup providers opencode opencode-go` grava a lista, sai com `0` e avisa em stderr `cli.opencode.tiers.standard` com `opencode/a-free` (AC 10, door 3)
Proof: `uv run pytest tests/test_setup_providers.py -k providers_warns_tier_outside`

**C10** - `doctor --json` traz `cli.opencode.providers` = `["opencode-go"]` com o campo gravado e `null` sem ele (AC 11)
Proof: `uv run pytest tests/test_doctor.py -k opencode_providers_field`

**C11** - Com `providers = ["opencode-go"]` e `tiers.standard = ["opencode/a-free"]`, `doctor --json` sai com `1` e `problems` tem a linha que começa com `cli.opencode.tiers.standard has 'opencode/a-free', whose provider is not in cli.opencode.providers` e cita `grokbot-kit setup tiers opencode standard`; com o tier dentro da lista, essa linha não aparece (AC 12, door 3)
Proof: `uv run pytest tests/test_doctor.py -k opencode_tier_provider_problem`

**C12** - Com `providers = ["opencode-go"]` e `tiers.standard = ["opencode/a-free"]`, `config.load()` não levanta erro e `grokbot-kit run --target t --label l -- "x"` lança o opencode falso com `-m opencode/a-free` (AC 13)
Proof: `uv run pytest tests/test_config.py -k load_ignores_providers`
Proof: `uv run pytest tests/test_run_fallback.py -k run_tier_outside_providers`

### S2 - o bot pergunta provedores e modelos · 2 arquivos · ~30 KB · ~8k

**C13** - A seção `Modelos e tiers` do `SKILL.md` cita `grokbot-kit setup models refresh --json` antes de qualquer `grokbot-kit setup providers` e `grokbot-kit setup tiers` (AC 14)
Proof: `uv run pytest tests/test_skill_doc.py -k models_refresh_json_first`

**C14** - A seção manda, com o `opencode` instalado, uma única pergunta de múltipla escolha com os provedores do campo `provider`, cita a contagem de ids por provedor e grava com `grokbot-kit setup providers opencode <provider>` (AC 15)
Proof: `uv run pytest tests/test_skill_doc.py -k providers_question`

**C15** - A seção diz que provedor pago precisa de login no opencode e cita `grokbot-kit login opencode` (AC 16)
Proof: `uv run pytest tests/test_skill_doc.py -k paid_provider_login`

**C16** - A seção manda uma pergunta por tier, nomeando `trivial`, `standard` e `complex`, com até 4 ids da lista descoberta, o recomendado primeiro, só dos provedores escolhidos no opencode, e grava com `grokbot-kit setup tiers <tool> <tier> <id>` (AC 17)
Proof: `uv run pytest tests/test_skill_doc.py -k tier_question_per_tier`

**C17** - A regra dos gratuitos primeiro em `trivial` e `standard` aparece condicionada a os provedores escolhidos serem só `opencode`, e a seção manda recomendar primeiro os ids de um provedor escolhido que não é `opencode` (AC 18, AC 19)
Proof: `uv run pytest tests/test_skill_doc.py -k free_first_only_without_paid`

**C18** - O `SKILL.md` manda refazer só os passos de provedores e tiers quando o usuário pede para trocar os modelos, sem `setup cli add`, `login` nem `route add` nesse trecho (AC 20)
Proof: `uv run pytest tests/test_skill_doc.py -k change_models_redo_steps`

**C19** - `setup providers` e o `--json` do `refresh` estão no `--help` do `grokbot-kit`, e as provas de hoje da skill (`test_no_literal_model_ids`, `test_every_cited_command_exists`, `test_install_location_and_allowed_commands`) seguem verdes com a seção nova (AC 21)
Proof: `uv run pytest tests/test_skill_doc.py -k "no_literal_model_ids or every_cited_command_exists or install_location_and_allowed_commands"`
Proof: `uv run pytest tests/test_cli.py -k setup_providers_in_help`

### S3 - o erro do agente chega com o motivo · 3 arquivos · ~35 KB · ~9k

**C20** - `read_output("opencode")` sem parte `text` dá `summary` `UnknownError: Unexpected server error` para `{"type":"error","error":{"name":"UnknownError","data":{"message":"Unexpected server error"}}}` (1.19), `provider.no-route: Model unavailable: opencode/x` para `{"type":"error","error":{"type":"provider.no-route","message":"Model unavailable: opencode/x"}}` (2.x), `UnknownError` só com `name`, e a mensagem do último de dois objetos `error` (AC 22, door 6)
Proof: `uv run pytest tests/test_terminal.py -k error_summary_opencode`

**C21** - `read_output("codex")` com `last-message.txt` ausente ou vazio dá `summary` `boom` para `{"type":"turn.failed","error":{"message":"boom"}}` e para `{"type":"error","message":"boom"}`, e a mensagem do último quando há os dois (AC 23, door 6)
Proof: `uv run pytest tests/test_terminal.py -k error_summary_codex`

**C22** - Com erro na saída e parte `text` `feito` (opencode) ou `last-message.txt` `feito` (codex), o `summary` é `feito` (AC 24)
Proof: `uv run pytest tests/test_terminal.py -k error_summary_text_wins`

**C23** - Uma mensagem de erro de 5000 caracteres dá `summary` de exatamente 2000 (AC 25)
Proof: `uv run pytest tests/test_terminal.py -k error_summary_limit`

**C24** - Na fronteira: `run` com o opencode falso imprimindo o erro 1.19 do C20 e saindo com `1`, com um único id no tier, entrega à rota um evento `error`/`failed`/`agent_error` com `summary` `UnknownError: Unexpected server error` (AC 22)
Proof: `uv run pytest tests/test_run_fallback.py -k event_summary_from_error`

### S4 - o kit tenta o próximo modelo do tier · 5 arquivos · ~80 KB · ~20k

**C25** - A elegibilidade da door 4 é, table-driven sobre 9 linhas: opencode com `error` e sem `tool_use` sim; opencode com `error` e `tool_use` não; opencode sem `error` não; claude `is_error` + `api_error` + `num_turns` 1 sim; claude `num_turns` 2 não; claude `terminal_reason` diferente de `api_error` não; claude `is_error` `false` não; codex com `turn.failed` não; qualquer CLI com `stopped` `timeout` ou `interrupted` não (AC 26, AC 31, AC 34, door 4)
Proof: `uv run pytest tests/test_terminal.py -k fallback_eligible`

**C26** - `run --tier standard` com `standard = ["opencode/m1", "opencode/m2"]`, o opencode falso dando erro 1.19 sem `tool_use` em `m1` e texto `ok` em `m2`: o evento é `completed`/`ok` com `model` `opencode/m2`, `model_fallbacks` `[{"model": "opencode/m1", "error": "UnknownError: Unexpected server error"}]`; as duas chamadas do falso têm o mesmo cwd e o mesmo prompt; o task dir tem `out.1.jsonl` (a saída de `m1`), `stderr.1.log` e `out.jsonl` (a de `m2`); o `kit.log` tem `model opencode/m1 failed at the provider before any tool call (UnknownError: Unexpected server error); trying opencode/m2` (AC 26, AC 27, AC 28, door 5)
Proof: `uv run pytest tests/test_run_fallback.py -k fallback_next_model`

**C27** - Sem fallback, os eventos `completed`/`ok`, `error`/`failed`/`nonzero_exit` e `timeout` trazem `model_fallbacks` `[]` (AC 29, door 5)
Proof: `uv run pytest tests/test_run_fallback.py -k no_fallback_empty_list`

**C28** - `run --model opencode/m1` com `m1` dando erro sem `tool_use` faz 1 chamada ao falso e termina `error`/`agent_error` com `model_fallbacks` `[]` (AC 30)
Proof: `uv run pytest tests/test_run_fallback.py -k explicit_model_no_fallback`

**C29** - Com `m1` imprimindo um `tool_use` e depois o erro, o `run` faz 1 chamada e termina `error`/`agent_error`; com o claude falso dando `is_error`, `api_error` e `num_turns` 3 no primeiro id, também 1 chamada (AC 31)
Proof: `uv run pytest tests/test_run_fallback.py -k failure_after_tool_no_fallback`

**C30** - Com `standard = ["opencode/m1", "opencode/m2", "opencode/m3"]` e os três dando erro sem `tool_use`, o evento é `error`/`failed`/`agent_error` com `model` `opencode/m3`, o `summary` do erro de `m3`, `model_fallbacks` com `m1` e `m2` nessa ordem, e o task dir com `out.1.jsonl`, `out.2.jsonl` e `out.jsonl` (AC 32)
Proof: `uv run pytest tests/test_run_fallback.py -k all_models_fail`

**C31** - Com `--timeout 4s`, `m1` dormindo 3 s e saindo com erro sem `tool_use`, e `m2` dormindo 10 s: o evento é `timeout` em menos de 6 s de parede (emenda de 28/10/2026, decisão do Rodrigo: com 30 s, um prazo novo por tentativa passava), com `model` `opencode/m2`, e não há terceira chamada; com `m1` dormindo além do prazo, o evento é `timeout` com 1 chamada (AC 33)
Proof: `uv run pytest tests/test_run_fallback.py -k shared_deadline`

**C32** - `run --tool codex --tier standard` com dois ids e o codex falso dando `turn.failed` faz 1 chamada (AC 34)
Proof: `uv run pytest tests/test_run_fallback.py -k codex_never_falls_back`

**C33** - Numa task de plugin com entrada `repo`, `m1` dando erro sem `tool_use` e `m2` gravando um `result.json` válido: o evento é `completed`/`ok`, o `gh` falso registra 1 clone, e as duas chamadas têm cwd `<task_dir>/work` (AC 35)
Proof: `uv run pytest tests/test_run_plugin.py -k plugin_fallback_clone_once`

**C34** - O `meta.json` final da task do C26 tem `model` `opencode/m2` e `model_fallbacks` igual ao do evento (door 5)
Proof: `uv run pytest tests/test_run_fallback.py -k meta_records_fallback`

**C35** - O corpo recebido pelo receptor local da rota `grokbot-routine` da task do C26 tem `model_fallbacks` com o item de `m1`, e a entrega é registrada como `200` (Surface, door 5)
Proof: `uv run pytest tests/test_run_fallback.py -k delivered_body_has_fallbacks`

**C36** - No box, com o `opencode` 1.19.3 real e `standard = ["opencode/nao-existe-grokbot-kit", <um id do opencode-go descoberto>]`, `run` termina `completed`/`ok` com `model` = o segundo id e `model_fallbacks` com o primeiro; uma task do mesmo opencode que lê um arquivo grava `type` `tool_use` no `out.jsonl` (AC 26, AC 31, suposições do 1.19.3)
Proof: `uv run pytest -m integration tests/integration/test_real_cli.py -k opencode_fallback_real`

**C37** - No host de dev, com o `claude` real e `standard = ["claude-nao-existe-grokbot-kit", "haiku"]` (o primeiro via `--add` recusado não entra, então o teste grava o config direto), `run` termina com `model` `haiku` e `model_fallbacks` com o primeiro (suposição do `claude`)
Proof: `uv run pytest -m integration tests/integration/test_real_cli.py -k claude_fallback_real`

**C50** - A entrega do evento com o campo novo segue a tabela de status de hoje: `401` e demais `4xx` vão a `undelivered.jsonl` sem retry, e `429`/`5xx` entram no retry (Surface; as provas da agent-run-notify, sem mudança de asserção)
Proof: `uv run pytest tests/test_sink_routine.py -k "non_retryable_4xx_to_undelivered or retry_table_429_5xx_connection"`

### S5 - a doc mostra o kit inteiro · 8 arquivos · ~55 KB · ~14k

**C38** - O `README.md` e o `docs/pt-BR/README.md` têm uma seção `## Commands` (`## Comandos` na pt-BR) com uma linha por subcomando de topo do parser, cada um como `grokbot-kit <subcomando>`, 13 hoje (AC 36)
Proof: `uv run pytest tests/test_docs.py -k readme_commands_section`

**C39** - Os dois READMEs têm uma seção `## Plugins` com `grokbot-kit run --plugin code-review --input pr=` e o link `docs/plugins.md` (no pt-BR, `plugins.md` relativo a `docs/pt-BR/`) (AC 37)
Proof: `uv run pytest tests/test_docs.py -k readme_plugins_section`

**C40** - Os dois READMEs citam `grokbot-kit setup providers`, `grokbot-kit setup tiers` e `model_fallbacks` (AC 38)
Proof: `uv run pytest tests/test_docs.py -k readme_models_and_fallback`

**C41** - `CONTRIBUTING.md` está em inglês (o título é `# Contributing to grokbot-kit`) e `docs/pt-BR/CONTRIBUTING.md` existe com o título `# Contribuindo com o grokbot-kit`; os dois têm o mesmo número de títulos `## ` e `### `, e as provas de hoje do `CONTRIBUTING.md` seguem verdes (AC 39)
Proof: `uv run pytest tests/test_docs.py -k contributing_pair`
Proof: `uv run pytest tests/test_repo_files.py -k "contributing_and_changelog or contributing_pypi_pending_publisher"`

**C42** - `docs/SPEC.md` não existe e o `CLAUDE.md` não cita `SPEC.md` (AC 40)
Proof: `test ! -e docs/SPEC.md && ! grep -q "SPEC.md" CLAUDE.md`

**C43** - O `CHANGELOG.md`, entre `## [0.5.0]` e o próximo `## [`, cita `setup providers`, `--json`, `model_fallbacks` e `summary` (AC 41)

> Emendado na release 0.5.0 (29/10/2026, ok do Rodrigo): era `## [Unreleased]`; ao fechar a versão as entradas passam
> para `## [0.5.0]`.
Proof: `uv run pytest tests/test_repo_files.py -k changelog_unreleased_model_setup`

### S6 - o CI quebra quando a doc fica para trás · 4 arquivos · ~20 KB · ~5k

**C44** - O checador de `tests/test_docs.py`, rodado sobre uma cópia em `tmp_path` com a linha `grokbot-kit redeliver` removida do `docs/pt-BR/README.md`, devolve uma falha que cita `redeliver` e `docs/pt-BR/README.md`; a lista de subcomandos vem do parser de `cli.py`, e um subcomando novo `foo` registrado no parser num teste falha citando `foo` (AC 42, door 7)
Proof: `uv run pytest tests/test_docs.py -k gate_reports_missing_command`

**C45** - Na cópia, apagar `docs/pt-BR/plugins.md` faz o checador citar `docs/plugins.md`, e um `docs/novo.md` sem par também (AC 43, door 7)
Proof: `uv run pytest tests/test_docs.py -k gate_reports_missing_pair`

**C46** - Na cópia, tirar o link `docs/pt-BR/README.md` das 5 primeiras linhas do `README.md` faz o checador citar `README.md`, e tirar o de volta do `docs/pt-BR/plugins.md` faz citar esse (AC 44, door 7)
Proof: `uv run pytest tests/test_docs.py -k gate_reports_missing_link`

**C47** - O checador sobre o repositório de verdade não acha falha (AC 42-44)
Proof: `uv run pytest tests/test_docs.py -k gate_repo_clean`

**C48** - O `CLAUDE.md` tem a regra da doc com `README.md`, as duas línguas, "mesmo PR" e o critério de doc no plano de cada feature (AC 45)
Proof: `uv run pytest tests/test_docs.py -k claude_md_doc_rule`

**C49** - O `.github/pull_request_template.md` tem um item de checklist com `README.md`, `docs` e `pt-BR` (AC 46)
Proof: `uv run pytest tests/test_docs.py -k pr_template_doc_item`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `POST <webhook da routine>` status (4) | `200` C35 · `401` C50 · demais `4xx` C50 · `429`/`5xx` C50 | - |
| `setup models refresh --json` exit (3) | `0` C1 · `1` C3 · `2` existing - `tests/test_models.py -k unknown_tool_exit_2` (o `--json` não muda a recusa; C1 roda a mesma CLI) | - |
| `provider` por CLI (3) | opencode C2 · claude C2 · codex C2 | - |
| `setup providers` exit (2) | `0` C5, C9 · `2` C6 | - |
| `setup providers` recusas (3) | tool não opencode C6 · opencode não instalado C6 · provedor sem id C6 | - |
| `setup tiers opencode` com/sem `providers` (2) | com C7 · sem C8 | - |
| `doctor --json` exit (2) | `0` C10 · `1` C11 | - |
| elegibilidade da door 4 (9 linhas) | C25, table-driven sobre as 9 | - |
| desfechos do fallback no `run` (6) | próximo id ok C26 · todos falham C30 · `--model` C28 · falha depois de ferramenta C29 · timeout C31 · codex C32 | - |
| formatos de erro do `summary` (5) | opencode 1.19 C20 · opencode 2.x C20 · só `name` C20 · codex `turn.failed` C21 · codex `error` C21 | - |
| eventos terminais com `model_fallbacks` (4) | `completed`/`ok` C26, C27 · `error`/`agent_error` C30 · `error`/`nonzero_exit` C27 · `timeout` C27 | - |
| CLIs reais com fallback (2) | opencode 1.19.3 C36 · claude C37 | - |
| arquivos de doc pareados (4 hoje) | `README.md` C38, C46 · `CONTRIBUTING.md` C41 · `docs/plugins.md` C45, C46 · novo `docs/*.md` C45 | - |
| falhas do checador de doc (3) | comando faltando C44 · par faltando C45 · link faltando C46 | - |
| doors do plano (7) | 1 saída `--json` C1, C2 · 2 `setup providers` C5, C6 · 3 restrição C7, C9, C11, C12 · 4 elegibilidade C25 · 5 tentativas C26, C30, C34, C35 · 6 `summary` C20, C21 · 7 prova da doc C44-C47 | - |
| relação `providers` -> `tiers` (1) | restringe `setup tiers` C7; `doctor` C11; `load` não C12 | - |

- Claims que nomeiam exit code, campo ou formato: C1, C3, C5-C7, C9-C11, C24, C26-C35 - cada um tem prova que
  cruza a fronteira (subprocesso `grokbot-kit` com as CLIs falsas e o receptor local)
- C2, C20-C23 e C25 provam a tabela na própria camada; a fronteira delas é C1 (C2), C24 (C20) e C26/C29 (C25)

## Test policy

As linhas da `## Test policy` de `docs/.specs/features/agent-run-notify/checks.md` valem aqui sem mudança (o repo
não tem guia de testes; essas linhas são o padrão do projeto, aplicadas também na kit-update).

Evidência:

- `models.py`, `provider`: 3 CLIs, 1 regra de prefixo -> decide, alcançado pela CLI (C2 + C1)
- `setup.py`, `setup providers`: 3 recusas e 1 aviso -> ponto de entrada que decide, na fronteira (C5, C6, C9)
- `setup.py`, `setup tiers` com `providers`: 2 casos -> decide (C7, C8)
- `doctor.py`, problema de provedor: 2 casos -> decide (C11)
- `terminal.py`, elegibilidade: 3 CLIs, 9 linhas -> decide, alcançado pelo `run` (C25 + C26, C29)
- `terminal.py`, `summary` de erro: 5 formatos e a precedência do texto -> decide (C20-C23 + C24); análogo: a leitura
  de erro de hoje em `tests/test_terminal.py`, já provada na própria camada
- `run.py`, laço de tentativas: 6 desfechos -> decide, na fronteira (C26-C33)
- `tests/test_docs.py`, checador: 3 falhas -> decide; provado com cópias mutadas (C44-C46) e no repo (C47)

Custo: 12 provas na própria camada e 24 na fronteira, em 9 arquivos de teste, mais 2 `-m integration`.

## Swept

- validation: C6 (provedor e tool do `setup providers`), C7 (id de provedor fora), C23 (limite de 2000)
- failure modes: C3 (uma CLI falha no `refresh --json`), C24, C30 (todas as tentativas falham)
- idempotency: C29 (sem nova tentativa depois de ferramenta, para não repetir efeito), C33 (o clone não se repete)
- authorization: n/a - comandos locais do usuário do box; a rota e os segredos não mudam; rate limit: C31 (as tentativas dividem um único prazo, sem laço sem fim)
- concurrency: n/a - as tentativas são sequenciais dentro de uma task, e o config é gravado por `config.save` (existe) como nos outros `setup`
- data lifecycle: C26 (`out.<n>.jsonl` e `stderr.<n>.log` ficam no task dir e saem com ele no `gc`, existe)
- dependency failure: C26, C30, C36 (provedor do modelo falha), C3 (`opencode models` falha)
- state transitions: C25 (tentativa elegível -> próxima), C31 (timeout encerra sem nova tentativa)
- observability: C26 (linha do `kit.log` por tentativa), C34, C35 (`model_fallbacks` no `meta.json` e no evento), C11 (problema no `doctor`)

## Handoff

Arquivos tocados: existentes `models.py` (5,3 KB), `setup.py` (5 KB), `cli.py` (10,3 KB), `doctor.py` (10 KB),
`terminal.py` (3,4 KB), `run.py` (19,6 KB), `payload.py` (5,6 KB), `SKILL.md` (13,2 KB), `README.md` (5,6 KB),
`docs/pt-BR/README.md` (5,6 KB), `CONTRIBUTING.md` (4,5 KB), `CHANGELOG.md` (14,2 KB), `CLAUDE.md` (~2 KB),
`.github/pull_request_template.md` (~0,5 KB), `tests/fakes/fake_agent.py` (~7 KB), `tests/test_models.py` (8,6 KB),
`tests/test_setup_tiers.py` (2,8 KB), `tests/test_doctor.py` (14 KB), `tests/test_terminal.py` (11,3 KB),
`tests/test_skill_doc.py` (16,5 KB), `tests/test_repo_files.py` (~15 KB), `tests/test_run_plugin.py` (26,5 KB),
`tests/test_config.py` (~6 KB), `tests/test_cli.py` (~6 KB), `tests/integration/test_real_cli.py` (~8 KB) = ~226 KB;
novos `tests/test_setup_providers.py` (~5 KB), `tests/test_run_fallback.py` (~15 KB), `tests/test_docs.py` (~6 KB),
`docs/pt-BR/CONTRIBUTING.md` (~4,5 KB) = ~31 KB. Total ~257 KB ÷ 4 ≈ 64k, mais a leitura fixa de `plan.md` (~27 KB)
e deste arquivo (~22 KB) ≈ 12k: 76k, abaixo do budget de 150k.

- S1 = 15k; S2 a 23k; S3 a 32k; S4 a 52k; S5 a 66k; S6 a 71k (com sobreposição de arquivos; o total real é o 76k
  acima) → um builder
- Mechanism: um builder
- C36 roda só no box, pelo bot; C37 roda no host de dev com o `claude` real
