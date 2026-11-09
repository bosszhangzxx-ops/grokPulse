# needs-input-reply checks

Profile: standard
Plan: `docs/.specs/features/needs-input-reply/plan.md`

60 checks em 6 slices · 7 one-way doors · 0 open

Convenções das provas:

- `uv run pytest <arquivo> -k <nome>` roda no CI, com o `HOME` isolado em `tmp_path` e as CLIs falsas de
  `tests/fakes/` (`fake_agent.py`), como nas features anteriores. A espera do `emit` nos testes usa prazos curtos
  (`ask_wait_seconds` de 1 a 3 s no `meta.json`) e um `reply` disparado em outra thread ou processo.
- O plugin v2 do opencode é escrito sem sintaxe só de TypeScript (sem anotação de tipo), para que
  `tests/test_opencode_plugin_v2.py` o copie para um `.mjs` e o importe com `node` (o do CI) com um `ctx` falso e um
  `grokbot-kit` falso; o asset continua `.ts` para o opencode.
- `uv run pytest -m integration <arquivo> -k <nome>` fica fora do CI e roda no host de dev, com o `claude` e o
  `opencode` 2.x reais em `HOME` temporário, como os spikes (`spike.md`).
- Seguem verdes, sem mudança de asserção, as provas da agent-run-notify que tocam a mesma superfície, menos a da AC 44
  da agent-run-notify, que a AC 28 desta feature muda: `tests/test_emit.py` (inteiro), `tests/test_opencode_plugin.py`,
  `tests/test_skill_doc.py -k "every_cited_command_exists or no_literal_model_ids"`, `tests/test_docs.py` e
  `tests/test_repo_files.py`. Em `tests/test_terminal.py`, o teste da AC 44 da agent-run-notify passa a ter
  `needs_input` sem resposta (é o que a C40 desta feature cobra); a asserção de `denied` não muda.
  Em `tests/test_payload.py`, `test_schema_matches_door_2` passa a exigir o conjunto exato de 5 chaves do
  `needs_input` (door 2 desta feature), no lugar das 3 da agent-run-notify.
- Provas antigas que fixam um valor que este plano muda passam a fixar o valor novo, sem afrouxar a asserção:
  `tests/test_launch.py::test_env_contract_and_commands` e `tests/test_docs.py::test_readme_commands_section`
  (14 subcomandos, com `reply`),
  `tests/test_run_plugin.py::test_run_without_plugin_unchanged` (o hook do Claude com `"timeout": 660`, AC 1, e o
  `--standalone` da door 9, já que o opencode falso responde `9.9.9`) e as
  chamadas de `payload.needs_input_event` em `tests/test_payload.py` (com `request_id`). As provas que rodam o `emit`
  dentro de uma tarefa para cobrar o aviso (`run_with_emits` em `tests/test_emit.py`,
  `test_transcript_path_from_hook_cli_through_emit`, `test_exactly_one_terminal_per_task`) passam `--ask-wait 0`, o
  modo só-aviso da AC 6, e o config das provas `-m integration` de `tests/integration/test_real_cli.py` ganha
  `[ask] wait = "0"` pelo mesmo motivo (C16 e C38 passam `--ask-wait` na linha de comando). O `emit` não espera numa tarefa com `finished_at` (nenhuma CLI espera a decisão), o que
  mantém as provas da agent-run-notify que chamam o `emit` depois do `run`. Em `tests/test_run_fallback.py`, a lista
  de tentativas deixa de fora a chamada `opencode --version` que o `run` passa a fazer antes de lançar (door 9).

## Checks

### S1 - o Claude espera a resposta do bot · 8 arquivos · ~85 KB · ~21k

**C1** - Com `ask_wait_seconds` `600`, o `claude-settings.json` que o `run` grava tem o hook `PermissionRequest` com `"timeout": 660`; com `0`, o hook não tem `timeout` (AC 1)
Proof: `uv run pytest tests/test_launch.py -k claude_settings_hook_timeout`

**C2** - `run` sem `--ask-wait` e sem `[ask]` no config grava `ask_wait_seconds` `600` no `meta.json`; com `[ask] wait = "2m"`, `120`; com `--ask-wait 30s` e `[ask] wait = "2m"`, `30`; com `--ask-wait 0`, `0` (AC 1, 6, door 4)
Proof: `uv run pytest tests/test_run_guards.py -k ask_wait_meta`

**C3** - `run --ask-wait 10x` sai com `2` e a mensagem do `parse_duration` (`invalid duration '10x'`), sem criar task dir (Surface)
Proof: `uv run pytest tests/test_run_guards.py -k ask_wait_invalid`

**C4** - `config.load()` com `[ask] wait = "abc"` levanta `ConfigError` citando `ask.wait`; com `[ask] wait = "0"` carrega (Surface)
Proof: `uv run pytest tests/test_config.py -k ask_wait_validation`

**C5** - O `emit --from claude` com espera `3` entrega um `needs_input` com `needs_input.request_id` igual ao discriminador da agent-run-notify (hash de `tool_name` + `tool_input` sem `tool_use_id`) e `needs_input.reply_deadline` = momento do pedido + 3 s em ISO 8601 UTC (`Z`), com tolerância de 1 s (AC 2)
Proof: `uv run pytest tests/test_emit_wait.py -k needs_input_fields`

**C6** - Com `started_at` + `timeout_seconds` 2 s depois do pedido e espera `600`, o `reply_deadline` é `started_at` + `timeout_seconds` (AC 2)
Proof: `uv run pytest tests/test_emit_wait.py -k deadline_capped_by_task_timeout`

**C7** - Com `replies/<request_id>.json` `{"decision": "allow", ...}` criado 1 s depois do pedido, o `emit --from claude` imprime exatamente `{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow"}}}`, sai com `0` e leva menos de 3 s (AC 3, door 6)
Proof: `uv run pytest tests/test_emit_wait.py -k claude_allow`

**C8** - Com `deny` e `message` `"não"`, o `emit --from claude` imprime `decision` `{"behavior": "deny", "message": "não"}`; com `message` `null`, `"message": "denied by the user"` (AC 4, door 6)
Proof: `uv run pytest tests/test_emit_wait.py -k claude_deny_message`

**C9** - Sem resposta e espera `1`, o `emit` sai com `0` entre 1 e 3 s, cria `replies/<request_id>.json` com `decision` `deny`, `by` `timeout` e `at` preenchido, e imprime o JSON de `deny` com `message` `no reply before <reply_deadline>` (AC 5)
Proof: `uv run pytest tests/test_emit_wait.py -k timeout_denies_and_records`

**C10** - Com espera `0`, o `emit --from claude` entrega o `needs_input` com `reply_deadline` `null` e `request_id` preenchido, imprime `{}`, sai com `0` em menos de 1 s e não cria `replies/` (AC 6)
Proof: `uv run pytest tests/test_emit_wait.py -k wait_zero_notify_only`

**C11** - Num task dir sem `ask_wait_seconds` no `meta.json` (tarefa antiga), o `emit` se comporta como no C10 (Impact, stored data)
Proof: `uv run pytest tests/test_emit_wait.py -k old_meta_is_notify_only`

**C12** - Com o único sink devolvendo `500` nas 3 tentativas, o `emit` com espera `3` ainda espera e devolve `allow` quando o arquivo aparece em 1 s (AC 7)
Proof: `uv run pytest tests/test_emit_wait.py -k waits_after_failed_delivery`

**C13** - Um segundo `emit` com o mesmo `request_id`, depois de `replies/<request_id>.json` existir com `allow`, imprime o JSON de `allow` em menos de 1 s e `events.jsonl` continua com um único `needs_input` desse id (AC 8)
Proof: `uv run pytest tests/test_emit_wait.py -k repeated_request_reuses_reply`

**C14** - Dois `emit` simultâneos com o mesmo `request_id` e espera `3` entregam um único `needs_input` e, com um `allow` gravado em 1 s, ambos imprimem `allow` (AC 8, AC 61 da agent-run-notify)
Proof: `uv run pytest tests/test_emit_wait.py -k concurrent_same_request`

**C15** - Um arquivo de resposta ilegível (`{` sem fechar, ou `decision` `"maybe"`) faz o `emit` imprimir `{}`, gravar o motivo no `kit.log` e sair com `0` (AC 60 da agent-run-notify; failure)
Proof: `uv run pytest tests/test_emit_wait.py -k unreadable_reply_no_decision`

**C16** - Com o `claude` real 2.x, o hook do kit e espera `120`, um `touch` que pede aprovação fica parado até `grokbot-kit reply <task> <id> allow` e então roda: o arquivo existe e o terminal é `completed`/`ok`/`success` (S1 inteiro)
Proof: `uv run pytest -m integration tests/integration/test_real_hooks.py -k claude_reply_allow`

**C58** - O `needs_input` com os campos novos passa pela entrega de hoje (`deliver.deliver`): com o sink da routine falso em `401`, 1 tentativa e uma linha em `undelivered.jsonl`; em `429`, 3 tentativas; nos dois casos o `emit` segue esperando a resposta (Surface; tabela de retry da agent-run-notify)
Proof: `uv run pytest tests/test_emit_wait.py -k needs_input_delivery_statuses`

**C60** - Com espera `10`, o `emit` não espera (imprime `{}` em menos de 1 s, `reply_deadline` `null`, sem `replies/`) com `--from codex`, com um `question.asked` do opencode mesmo com `GROKBOT_KIT_REPLY=1`, e com `--from opencode` sem `GROKBOT_KIT_REPLY` (door 8)
Proof: `uv run pytest tests/test_emit_wait.py -k only_claude_and_plugin_v2_wait`

### S2 - o bot responde com `grokbot-kit reply` · 4 arquivos · ~35 KB · ~9k

**C17** - `reply <task> <id> allow` para um pedido entregue e sem resposta cria `replies/<id>.json` com `decision` `allow`, `message` `null`, `by` `user` e `at` ISO 8601, imprime `recorded allow for <id> (by user)` e sai com `0` (AC 9)
Proof: `uv run pytest tests/test_reply.py -k allow_recorded`

**C18** - `reply ... deny --message "fora do repo"` grava `decision` `deny` e `message` `fora do repo` (AC 10)
Proof: `uv run pytest tests/test_reply.py -k deny_with_message`

**C19** - `reply ... allow --message x` sai com `2` e não cria `replies/` (AC 11)
Proof: `uv run pytest tests/test_reply.py -k message_with_allow_rejected`

**C20** - `reply` para task dir inexistente sai com `1` com `task not found`; para um `request_id` sem `needs_input` em `events.jsonl`, sai com `1` com `no needs_input with request_id <id>`; nenhum dos dois cria arquivo (AC 12)
Proof: `uv run pytest tests/test_reply.py -k unknown_task_or_request`

**C21** - Com `replies/<id>.json` já gravado com `by` `user`, `reply` sai com `1` com `already answered: <decision>` e o arquivo fica byte a byte igual; com `by` `timeout`, sai com `1` com `no reply before <reply_deadline>; the request was denied` (AC 13)
Proof: `uv run pytest tests/test_reply.py -k already_answered_or_expired`

**C22** - Com `finished_at` preenchido no `meta.json`, `reply` sai com `1` com `task already finished` e não cria arquivo (AC 14)
Proof: `uv run pytest tests/test_reply.py -k task_finished`

**C23** - `reply` com `request_id` `../x`, `a/b` e `a b` sai com `2` sem criar `replies/`; com `sha256:abc` e `chatcmpl-tool-1.x_y` passa da validação (AC 15)
Proof: `uv run pytest tests/test_reply.py -k request_id_charset`

**C24** - Com `reply` e o prazo do `emit` disparados no mesmo instante em 20 rodadas, cada rodada termina com um único arquivo, e o `emit` imprime a decisão que o arquivo tem (AC 16)
Proof: `uv run pytest tests/test_reply.py -k race_single_decision`

**C25** - `reply ... allow --by bot` grava `by` `bot`, imprime `recorded allow for <id> (by bot)` e o `kit.log` ganha `reply: allow for <id> by bot` (AC 17)
Proof: `uv run pytest tests/test_reply.py -k by_bot_logged`

**C26** - `reply ... allow --by robot` sai com `2` e não cria arquivo (AC 18)
Proof: `uv run pytest tests/test_reply.py -k by_invalid`

### S3 - o opencode 2.x espera a resposta pelo plugin · 7 arquivos · ~60 KB · ~15k

**C27** - `install opencode` com o opencode falso respondendo `opencode v2.2.4`, e sem opencode no config nem no `PATH`, grava o asset v2: primeira linha `// grokbot-kit opencode plugin for opencode 2`, `export default` com `id: "grokbot-kit"`, e o caminho absoluto do executável no lugar de `__GROKBOT_KIT_EXE__` (AC 19, door 5)
Proof: `uv run pytest tests/test_opencode_plugin.py -k install_picks_v2`

**C28** - `install opencode` com o opencode falso respondendo `opencode v1.19.3` grava o asset v1, igual ao de hoje mais a primeira linha `// grokbot-kit opencode plugin for opencode 1` (AC 20)
Proof: `uv run pytest tests/test_opencode_plugin.py -k install_picks_v1`

**C29** - O plugin v2 importado no `node` com um `ctx` falso e `GROKBOT_KIT_TASK_ID` definido registra um `permission.hook("evaluate")`; num evento `{effect: "ask", action: "shell", resources: ["touch x"], source: {id: "call-1"}, sessionID: "s1"}` de sessão sem `parentID`, chama o `grokbot-kit` falso com `emit --from opencode` e stdin `{"type": "permission.asked", "properties": {..., "permission": "shell", "patterns": ["touch x"], "id": "call-1"}, "parentID": null}` (AC 21)
Proof: `uv run pytest tests/test_opencode_plugin_v2.py -k evaluate_calls_emit`

**C30** - Enquanto o `grokbot-kit` falso dorme 2 s, um `setInterval` de 100 ms no mesmo processo do `node` dispara pelo menos 10 vezes (o plugin não bloqueia o processo); o plugin passa ao `spawn` um timeout de `ask_wait_seconds + 60` s lido do `meta.json` (AC 21)
Proof: `uv run pytest tests/test_opencode_plugin_v2.py -k does_not_block`

**C31** - Com o `grokbot-kit` falso imprimindo `{"effect":"allow"}`, o evento sai com `effect` `allow`; com `{"effect":"deny","message":"m"}`, `deny` e `message` `m`; com `{}`, saída vazia, saída que não é JSON, exit `1` ou timeout, o `effect` fica `ask` (AC 22)
Proof: `uv run pytest tests/test_opencode_plugin_v2.py -k applies_emit_decision`

**C32** - Num evento com `effect` `allow` ou `deny` vindo da config, ou de sessão com `parentID`, o plugin não chama o `grokbot-kit` (AC 21)
Proof: `uv run pytest tests/test_opencode_plugin_v2.py -k only_root_ask`

**C33** - Sem `GROKBOT_KIT_TASK_ID`, o `setup` do plugin v2 não chama `ctx.permission.hook` nem o `grokbot-kit` (AC 23)
Proof: `uv run pytest tests/test_opencode_plugin_v2.py -k inert_without_task`

**C34** - O `emit --from opencode` com o JSON do C29 e uma resposta `allow` imprime exatamente `{"effect":"allow","message":null}`; com `deny`/`"m"`, `{"effect":"deny","message":"m"}` (door 6)
Proof: `uv run pytest tests/test_emit_wait.py -k opencode_effect_output`

**C35** - O `doctor` com o opencode falso em `v2.2.4` e o plugin com marcador `1` acusa `opencode plugin is for opencode 1, installed opencode is 2; run: grokbot-kit install opencode` e sai com `1`; com opencode `v1.19.3` e marcador `2`, o mesmo ao contrário; um plugin sem marcador conta como `1` (AC 24)
Proof: `uv run pytest tests/test_doctor.py -k plugin_major_mismatch`

**C36** - O `run` de uma tarefa opencode com o opencode falso em `v2.2.4` e o plugin com marcador `1` reescreve o plugin com o asset v2 antes de lançar a CLI (o arquivo já é v2 quando o fake roda) e grava no `kit.log` `opencode plugin rewritten for opencode 2`; com o marcador certo, o arquivo não é tocado (mtime igual); sem plugin instalado, nenhum arquivo é criado (AC 25)
Proof: `uv run pytest tests/test_run_guards.py -k run_rewrites_stale_plugin`

**C37** - Com o diretório de plugins sem permissão de escrita e o marcador errado, o `run` grava o motivo no `kit.log` e a tarefa termina como sem o problema (o fake roda, terminal `completed`) (AC 26)
Proof: `uv run pytest tests/test_run_guards.py -k run_plugin_rewrite_failure`

**C59** - O `run` de uma tarefa opencode sem plugin com o opencode falso em `v2.2.4` lança `run --format json -m <modelo> --standalone <prompt>` (o lugar onde as tarefas de plugin já o passam); com `v1.19.3`, sem `--standalone` (door 9)
Proof: `uv run pytest tests/test_launch.py -k opencode_standalone_by_major`

**C38** - Com o `opencode` 2.x real, `HOME` temporário, plugin do `install`, `"permission": {"bash": "ask"}` e espera `120`, um `touch` fica parado até `reply ... allow`, roda, e o terminal é `completed`/`ok` (S3 inteiro)
Proof: `uv run pytest -m integration tests/integration/test_real_hooks.py -k opencode_reply_allow`

### S4 - o terminal reflete a resposta · 3 arquivos · ~40 KB · ~10k

**C39** - `classify` (ou o leitor de `replies/` que alimenta o `needs_input` dele) com dois `needs_input` respondidos `allow` e `permission_denials` vazio dá `completed`/`ok`/`success` (AC 27)
Proof: `uv run pytest tests/test_terminal.py -k all_allowed_is_success`

**C40** - Com um dos dois `needs_input` em cada caso - sem arquivo, `deny` por `user`, `deny` por `timeout` - o resultado é `completed`/`denied`/`permission_denied`; com os dois `allow` mas `permission_denials` não vazio, também (AC 28)
Proof: `uv run pytest tests/test_terminal.py -k any_unallowed_is_denied`

**C41** - Um `run` com a CLI falsa que dispara o hook, espera o `emit` e sai `0`, com `reply ... allow` em outra thread, termina com o evento terminal `completed`/`ok`/`success` (AC 27, na fronteira)
Proof: `uv run pytest tests/test_run_guards.py -k run_allowed_request_ends_ok`

**C42** - Numa tarefa de plugin com espera `600`, o `emit` não entrega `needs_input`, imprime `{}` e sai em menos de 1 s (AC 29)
Proof: `uv run pytest tests/test_emit_wait.py -k plugin_task_no_wait`

### S5 - o kit atualiza as CLIs e o plugin acompanha · 6 arquivos · ~50 KB · ~13k

**C43** - `setup cli upgrade opencode` com `[cli.opencode] bin` no config e o instalador falso trocando o binário de `1.19.3` para `2.2.4` roda o mesmo argv do `setup cli add` (`curl -fsSL https://opencode.ai/install | bash -s -- --no-modify-path`), imprime `opencode 1.19.3 -> 2.2.4` e sai com `0`; com o instalador mantendo a versão, imprime `opencode 2.2.4 is already the latest` e sai com `0` (AC 30, door 7)
Proof: `uv run pytest tests/test_setup_upgrade.py -k upgrade_prints_versions`

**C44** - `setup cli upgrade` vale para `claude` e `codex` com o argv do `setup cli add` de cada um (`CODEX_HOME` do kit no `codex`) (AC 30)
Proof: `uv run pytest tests/test_setup_upgrade.py -k upgrade_each_tool`

**C45** - `setup cli upgrade claude` sem `[cli.claude] bin` sai com `2` com `claude is not installed by grokbot-kit; run: grokbot-kit setup cli add claude` e não roda instalador; `setup cli upgrade foo` sai com `2` (AC 31)
Proof: `uv run pytest tests/test_setup_upgrade.py -k upgrade_not_installed`

**C46** - Instalador saindo com `1`, ou `--version` de depois saindo com `1`, faz o `setup cli upgrade` sair com `1` com o motivo e deixa o config byte a byte igual (AC 32)
Proof: `uv run pytest tests/test_setup_upgrade.py -k upgrade_failure_keeps_config`

**C47** - Com o plugin v1 instalado, `setup cli upgrade opencode` para `2.2.4` reescreve o plugin com o asset v2 e imprime `opencode plugin rewritten for opencode 2`; sem plugin instalado, não cria o arquivo; com o diretório sem escrita, sai com `1` com `run: grokbot-kit install opencode` (AC 33)
Proof: `uv run pytest tests/test_setup_upgrade.py -k upgrade_rewrites_plugin`

**C48** - O `doctor` com o opencode falso em `v1.19.3` mostra `opencode 1.19.3: replies to needs_input need opencode 2; run: grokbot-kit setup cli upgrade opencode`, o `--json` tem o aviso fora de `problems`, e o exit é o mesmo que sem o aviso (AC 34)
Proof: `uv run pytest tests/test_doctor.py -k opencode_1_warning`

**C49** - Num `HOME` temporário com o opencode instalado pelo instalador oficial, `setup cli upgrade opencode` real sai com `0` e o `<bin> --version` depois é o mesmo da última versão publicada (`opencode upgrade --help` não é usado) (Assumptions: o instalador atualiza)
Proof: `uv run pytest -m integration tests/integration/test_install.py -k upgrade_opencode_real`

**C57** - `update apply` com o opencode falso em `v2.2.4` e o plugin v1 instalado termina com o plugin v2 (marcador `2`), pelo `install opencode` que ele já chama (AC 19, Impact)
Proof: `uv run pytest tests/test_update.py -k apply_rewrites_plugin_for_major`

### S6 - o bot sabe responder, e a doc diz como · 7 arquivos · ~75 KB · ~19k

**C50** - A seção "Quando um evento chega" do `SKILL.md` manda, num `needs_input` de `permission` com `reply_deadline` não nulo, aplicar a regra de risco antes do `reply_deadline`, e, com `reply_deadline` `null`, oferecer o `resume_hint` (AC 35)
Proof: `uv run pytest tests/test_skill_doc.py -k needs_input_reply_flow`

**C51** - A regra de risco do `SKILL.md` lista como baixo risco exatamente: ler, listar ou buscar arquivos; testes, linters, checagem de tipos, build; criar ou editar dentro do `cwd`; `git status`, `git diff`, `git log`, `git show` - e não cita `rm`, `push`, `curl` nem `install` na lista (AC 36)
Proof: `uv run pytest tests/test_skill_doc.py -k risk_rule_low_list`

**C52** - A regra de risco manda perguntar ao usuário e cita: fora do `cwd`, rede (`git fetch`, `git pull`, `git push`, `git clone`, download, instalação de pacote), apagar arquivos, reescrever histórico, segredos (`.env`, `~/.ssh`), `sudo`, e pedido que o bot não consegue classificar (AC 37)
Proof: `uv run pytest tests/test_skill_doc.py -k risk_rule_ask_list`

**C53** - O `SKILL.md` cita `grokbot-kit reply <task_id> <request_id> allow --by bot` com a instrução de contar ao usuário o que aprovou, `--by user` para a resposta do usuário, que o bot nunca nega sozinho e que o kit nega no `reply_deadline`, e oferece `grokbot-kit setup cli upgrade opencode` diante do aviso de opencode 1.x do `doctor`; todo comando citado existe no `--help` (AC 38, 39, 40)
Proof: `uv run pytest tests/test_skill_doc.py -k reply_by_and_upgrade`
Proof: `uv run pytest tests/test_skill_doc.py -k every_cited_command_exists`

**C54** - `README.md` e `docs/pt-BR/README.md` têm `reply` com `--by`, `run --ask-wait` e `setup cli upgrade` em `## Commands`; `docs/event.md` e `docs/pt-BR/event.md` descrevem `needs_input.request_id` e `needs_input.reply_deadline`; o `assets/event.v1.json` aceita um `needs_input` com os dois campos e com `reply_deadline` `null` (AC 41, door 2)
Proof: `uv run pytest tests/test_docs.py -k "gate_repo_clean or gate_flags_repo_clean or gate_event_fields_repo_clean or needs_input_reply_docs"`
Proof: `uv run pytest tests/test_payload.py -k needs_input_schema_new_fields`

**C55** - As duas versões do README dizem que a resposta vale no Claude e no opencode 2.x, que o opencode 1.x só avisa, e citam `grokbot-kit setup cli upgrade opencode` (AC 42)
Proof: `uv run pytest tests/test_docs.py -k opencode_version_note`

**C56** - `CHANGELOG.md` `## [Unreleased]` cita `reply`, `--by`, `--ask-wait`, `[ask] wait`, `request_id`, `reply_deadline`, `denied`, a regra de risco, `setup cli upgrade` e o plugin do opencode 2 (AC 43)
Proof: `uv run pytest tests/test_docs.py -k changelog_needs_input_reply`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `POST <webhook da routine>` statuses, os de hoje (4) | `200` C5 · `401`/`4xx` C58 · `429` C58 · `500`-`599` C12, C58 | - |
| `reply` exit codes (3) | `0` C17 · `1` C20, C21, C22 · `2` C19, C23, C26 | - |
| `reply` recusas com `1` (5) | task dir C20 · request_id C20 · já respondido C21 · prazo vencido C21 · tarefa terminada C22 | - |
| `reply` recusas com `2` (3) | `--message` com `allow` C19 · `request_id` inválido C23 · `--by` inválido C26 | - |
| `setup cli upgrade` exit codes (3) | `0` C43 · `1` C46, C47 · `2` C45 | - |
| `setup cli upgrade` tools (3) | `opencode` C43 · `claude` C44 · `codex` C44 | - |
| `run --ask-wait` / `[ask] wait` precedência (4) | padrão C2 · config C2 · flag C2 · `0` C2 | - |
| `run --ask-wait` inválido (2) | flag C3 · config C4 | - |
| desfechos do `emit` com espera (7) | `allow` C7 · `deny` com mensagem C8 · `deny` sem mensagem C8 · prazo C9 · espera `0` C10 · resposta reaproveitada C13 · resposta ilegível C15 | - |
| saída do `emit` por fonte, door 6 (5) | claude `allow` C7 · claude `deny` C8 · opencode `allow` C34 · opencode `deny` C34 · sem decisão `{}` C10, C15 | - |
| `by` no arquivo de resposta, door 1 (3) | `user` C17 · `bot` C25 · `timeout` C9 | - |
| `reply_deadline` (3) | espera C5 · teto da tarefa C6 · `null` C10 | - |
| `--standalone` por major, door 9 (2) | `2` C59 · `1` C59 | - |
| quem espera, door 8 (5) | claude C7 · opencode com `GROKBOT_KIT_REPLY` C34 · opencode sem ele C60 · codex C60 · `question` C60 | - |
| asset por major, door 5 (3) | `2` C27 · desconhecido C27 · `1` C28 | - |
| resposta do plugin v2 ao `emit` (6) | `allow` C31 · `deny` C31 · `{}` C31 · não JSON C31 · exit `1` C31 · timeout C31 | - |
| eventos que o plugin v2 ignora (4) | sem task C33 · `effect` `allow` C32 · `effect` `deny` C32 · sessão filha C32 | - |
| lugares que escrevem o plugin (4) | `install opencode` C27, C28 · `setup cli upgrade` C47 · `run` C36 · `update apply` C57 | - |
| `doctor` e a versão (3) | v1 no 2.x C35 · v2 no 1.x C35 · aviso do 1.x C48 | - |
| classificação com respostas (5) | todos `allow` C39, C41 · sem resposta C40 · `deny` C40 · `timeout` C40 · `permission_denials` C40 | - |
| campos novos do evento, door 2 (2) | `request_id` C5, C54 · `reply_deadline` C5, C54 | - |
| regra de risco: baixo risco (4) | leitura C51 · testes/lint/tipos/build C51 · editar no `cwd` C51 · `git` de leitura C51 | - |
| regra de risco: pergunta (7) | fora do `cwd` C52 · rede C52 · apagar C52 · histórico C52 · segredos C52 · `sudo` C52 · não classificável C52 | - |
| docs da feature (4) | README C54, C55 · event.md C54 · SKILL.md (sem par, AGENTS.md) C50-C53 · CHANGELOG C56 | - |
| startup config: hook do Claude (2 montagens) | `claude-settings.json` do `run` C1 · harness de plugin (sem espera, AC 29) C42 | - |

- Claims com código de saída, formato de saída ou campo de evento: C3, C7-C10, C17-C26, C34, C43-C48, C54 - cada
  um com prova que atravessa a CLI ou valida o JSON
- O caminho real das CLIs é provado só por C16, C38 e C49 (`-m integration`, host de dev); o CI prova com fakes

## Test policy

As linhas da `## Test policy` de `docs/.specs/features/agent-run-notify/checks.md` valem aqui sem mudança, como na
kit-update e na model-setup-docs.

Evidência:

- `emit.py`, espera e decisão: 7 desfechos e 2 fontes -> decide, alcançado pela CLI (`emit` é a fronteira; C5-C15,
  C34, C42)
- `reply` (módulo novo): 8 recusas e 1 sucesso -> ponto de entrada que decide, na fronteira (C17-C26); análogo:
  `redeliver.py`, provado na CLI em `tests/test_redeliver.py`
- `terminal.py`, `classify` com respostas: 5 linhas -> decide, na própria camada (C39, C40) e na fronteira (C41)
- plugin v2: 6 respostas e 4 filtros -> decide; provado no `node` com `ctx` falso (C29-C33), não só pelo opencode
  real (C38)
- `opencode_plugin.py`, escolha do asset: 3 linhas -> decide (C27, C28); `run.py`/`doctor.py`, marcador: 3 casos
  cada (C35-C37)
- `setup.py`, upgrade: 3 tools e 3 desfechos -> decide, na fronteira (C43-C47); análogo: `cli_add` em
  `tests/test_setup.py`

Custo: ~45 provas no CI em 11 arquivos de teste (4 novos) e 3 `-m integration` no host de dev.

## Swept

- validation: C3, C4, C19, C23, C26
- failure modes: C9, C12, C15, C37, C46, C47
- idempotency: C13, C14, C21
- authorization: n/a - quem roda `reply` é o mesmo usuário do box que é dono do task dir; o kit não tem outro nível de acesso (AD-007), e a validação do `request_id` (C23) impede escrever fora de `replies/`
- concurrency: C14, C24
- data lifecycle: C11 (task dir antigo); `replies/` vive no task dir e sai com o `gc` como o resto (AD-018), sem prova nova
- dependency failure: C12 (sink), C31 (emit do plugin falha ou estoura), C46 (instalador)
- state transitions: C22 (tarefa terminada), C21 (respondido/vencido), C39-C41
- observability: C15, C25, C36, C37 (linhas do `kit.log`)

## Handoff

Arquivos tocados: existentes `emit.py` (5,9 KB), `run.py` (20,9 KB), `launch.py` (5,9 KB), `terminal.py` (5,5 KB),
`setup.py` (6,9 KB), `doctor.py` (10,8 KB), `cli.py` (10,8 KB), `opencode_plugin.py` (1,4 KB), `payload.py` (5,7 KB),
`config.py` (4,8 KB), `assets/opencode/grokbot-kit.ts` (2 KB), `assets/event.v1.json` (~4 KB), `SKILL.md` (15,1 KB),
`README.md` (10,5 KB), `docs/pt-BR/README.md` (10,5 KB), `docs/event.md` (4,1 KB), `docs/pt-BR/event.md` (4,1 KB),
`CHANGELOG.md` (17,1 KB), testes existentes (`test_launch`, `test_terminal`, `test_doctor`, `test_opencode_plugin`,
`test_skill_doc`, `test_docs`, `test_config`, `test_run_guards`, `test_payload`, `fake_agent.py`,
`integration/test_real_hooks.py`, `integration/test_install.py`; ~140 KB) = ~305 KB; novos `reply.py` (~4 KB),
`assets/opencode/grokbot-kit.v2.ts` (~3 KB), `tests/test_emit_wait.py` (~12 KB), `tests/test_reply.py` (~8 KB),
`tests/test_opencode_plugin_v2.py` (~8 KB), `tests/test_setup_upgrade.py` (~6 KB) = ~41 KB. Total ~346 KB ÷ 4 ≈
87k, mais a leitura fixa de `plan.md` (~27 KB) e deste arquivo (~25 KB) ≈ 13k: 100k, abaixo do budget de 150k.

- S1 = 21k; S2 a 30k; S3 a 45k; S4 a 55k; S5 a 68k; S6 a 87k (com sobreposição de arquivos; o total real é o 100k
  acima) -> um builder
- Mechanism: um builder
- C16, C38 e C49 rodam no host de dev (`-m integration`); nenhuma prova precisa do box

- **Boundary:** C1-C59 fechados em `677382b` (CI: 1089 passed; `-m integration` no host de dev: C16 com `claude`
  2.1.318, C38 com `opencode` 2.2.4 e `opencode-go/glm-5.3-flash`, C49 com o instalador oficial)
- **Settled mid-build:** door 8 (o `emit` só espera com `--from claude` ou com `GROKBOT_KIT_REPLY=1` do plugin v2) e
  door 9 (`--standalone` em toda tarefa do opencode 2.x), as duas no `Landing` antes do código; o `emit` não espera
  numa tarefa com `finished_at`; o `reply` recusa com `1` um pedido entregue sem espera (`reply_deadline` `null`)
- **Abandoned:** prazo arredondado para baixo (encurtava a espera em até 1 s; agora arredonda para cima)
