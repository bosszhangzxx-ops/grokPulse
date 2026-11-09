# plugins checks

Profile: standard
Plan: `docs/.specs/features/plugins/plan.md`

67 checks em 8 slices · 13 one-way doors · 2 open, das quais 1 bloqueia (matriz da door 8, respondida pelo S1)

Convenções das provas:

- `uv run pytest <arquivo> -k <nome>` roda no CI: `HOME` isolado em `tmp_path`, fixture `kit` do `tests/conftest.py`,
  receptor HTTP local como sink da routine, CLIs falsas de `tests/fakes/` (gravam `cwd`, argv e env, e gravam
  `result.json` quando `FAKE_RESULT` aponta um conteúdo).
- O `gh` das provas de CI é falso (`tests/fakes/gh`): `gh repo clone`/`gh pr checkout` clonam um repositório git local
  criado em `tmp_path`; `FAKE_GH_EXIT` força falha; `gh auth status` sai com `FAKE_GH_AUTH_EXIT`.
- `uv run pytest -m integration <arquivo> -k <nome>` roda só no box, com as CLIs reais e o `gh` real; fica fora do CI.
  Toda célula da matriz e toda imposição de capacidade são provadas aqui, porque dependem da versão da CLI e do host.
- A matriz da door 8 é um dado do pacote (lido por `plugin.py`) e uma tabela em `spike.md`; C8 garante que os dois
  são iguais.

## Checks

### S1 - a matriz de capacidades está provada no box · 2 arquivos novos · ~12 KB · ~3k (mais as rodadas no box) · verde no host de dev (AD-042): C1, C7, C8 no CI; C2-C5 nas 3 CLIs (Codex fora pela matriz), C6 sem célula a provar; a rodada no box vem com a release, pelo bot

**C1** - `docs/.specs/features/plugins/spike.md` tem a matriz com exatamente 15 células (3 CLIs × `write`, `network`, `commands`, `workspace_config`, `skills`), cada uma `os`, `tool` ou `unsupported`, cada uma com a versão da CLI, o comando que a provou e a saída observada (AC 1, door 8)
Proof: `uv run pytest tests/test_plugin_spike.py -k matrix_complete`

**C2** - Para cada CLI com `write` diferente de `unsupported`, um agente real instruído a criar `~/grokbot-kit-spike-write` numa tarefa com `write = "task-dir"` termina sem que o arquivo exista (AC 2)
Proof: `uv run pytest -m integration tests/integration/test_plugin_caps.py -k write_outside_denied`

**C3** - Para cada CLI com `commands` diferente de `unsupported`, um agente instruído a rodar `touch <task_dir>/spike-cmd` com `commands = ["git"]` termina sem que o arquivo exista (AC 3)
Proof: `uv run pytest -m integration tests/integration/test_plugin_caps.py -k command_outside_denied`

**C4** - Para cada CLI com `workspace_config` diferente de `unsupported`, um workspace com hook/plugin de projeto que cria `<task_dir>/spike-hook` ao iniciar termina sem o marcador (AC 4)
Proof: `uv run pytest -m integration tests/integration/test_plugin_caps.py -k workspace_config_ignored`

**C5** - Para cada CLI com `skills` diferente de `unsupported`, um plugin cuja skill manda gravar a palavra `spike-skill-ok` no `result.json` gera um resultado com essa palavra (AC 5)
Proof: `uv run pytest -m integration tests/integration/test_plugin_caps.py -k plugin_skill_loaded`

**C6** - Para cada CLI com `network` diferente de `unsupported`, um agente com `network = "off"` instruído a rodar `git ls-remote https://github.com/rodrigo-pasini/grokbot-kit` não obtém resposta (AC 36 do S3, provado com a matriz)
Proof: `uv run pytest -m integration tests/integration/test_plugin_caps.py -k network_off_denied`

**C7** - Uma CLI com `unsupported` em `write` ou `workspace_config` na matriz tem todas as capacidades tratadas como sem suporte por `plugin.py`; uma célula que depende do host tem um comando de sondagem registrado ou é `unsupported` (AC 7, AC 8)
Proof: `uv run pytest tests/test_plugin_spike.py -k cli_excluded_when_write_or_workspace_unsupported`
Proof: `uv run pytest tests/test_plugin_spike.py -k host_dependent_cell_has_probe`

**C8** - A matriz que `plugin.py` usa é igual, célula a célula, à tabela de `spike.md` (AC 6, door 8)
Proof: `uv run pytest tests/test_plugin_spike.py -k package_matrix_matches_spike`

### S2 - o plugin é instalado, listado e removido · 4 arquivos · ~70 KB · ~18k · done (C9-C26)

**C9** - `plugin list --json` imprime `{"plugins": [...]}` com `code-review` e `bug-verify` (`source` `builtin`) e um plugin instalado de diretório (`source` `dir`), ordenados por `name`; cada item tem exatamente as chaves `name`, `version`, `description`, `source`, `origin`, `commit`, `inputs`, `capabilities`, `support` (AC 9, door 4)
Proof: `uv run pytest tests/test_plugin.py -k list_json_shape`

**C10** - `plugin list` sem `--json` imprime uma linha `<nome> <versão> <source> - <description>` por plugin e sai com `0` (AC 10)
Proof: `uv run pytest tests/test_plugin.py -k list_text_lines`

**C11** - `plugin show code-review --json` imprime o item da door 4 com `support` para `claude`, `opencode` e `codex`, cada um com as 5 capacidades (AC 11)
Proof: `uv run pytest tests/test_plugin.py -k show_by_name`

**C12** - `plugin show <diretório>` de um plugin válido imprime o mesmo item que o `plugin add` gravaria e não cria nada em `~/.grokbot-kit/plugins/`; com um diretório inválido sai com `2` com o mesmo erro do `plugin add` (AC 12)
Proof: `uv run pytest tests/test_plugin.py -k show_origin_without_writing`

**C13** - `plugin show nao-existe` sai com `2` e stderr `no plugin named nao-existe; run: grokbot-kit plugin list` (AC 13)
Proof: `uv run pytest tests/test_plugin.py -k show_unknown_name`

**C14** - `plugin add <dir>` com stdin de terminal (pty) e resposta `y` imprime as capacidades, grava a cópia e o `origin.json` com `source` `dir`, `origin` absoluto, `ref` `null`, `commit` `null` e `installed_at` RFC 3339, e sai com `0`; com resposta `n` não grava e sai com `2` (AC 14, door 3)
Proof: `uv run pytest tests/test_plugin.py -k add_dir_confirms_on_tty`

**C15** - `plugin add <dir> --yes` com stdin fechado imprime as capacidades e grava sem perguntar (AC 15)
Proof: `uv run pytest tests/test_plugin.py -k add_yes_skips_prompt`

**C16** - `plugin add <dir>` sem `--yes` com stdin que não é terminal sai com `2` sem gravar (AC 16)
Proof: `uv run pytest tests/test_plugin.py -k add_without_tty_refuses`

**C17** - `plugin add <repo git local> --ref <tag>` grava `source` `git`, `ref` = a tag e `commit` = o sha de 40 caracteres da tag; sem `--ref` grava o commit da branch padrão (AC 17, door 3)
Proof: `uv run pytest tests/test_plugin.py -k add_git_pins_commit`

**C18** - `plugin add` sai com `2` nomeando o caminho, sem gravar, para cada um de `hooks/`, `commands/`, `agents/`, `.mcp.json`, `.lsp.json` na origem (AC 18, door 1)
Proof: `uv run pytest tests/test_plugin.py -k add_refuses_executable_parts`

**C19** - `plugin add` sai com `2` nomeando o erro, sem gravar, para: TOML inválido, `schema` ausente, `schema` `grokbot-kit.plugin/v1`, capacidade `sudo`, `write = "anywhere"`, `network = "maybe"`, `commands` que não é lista de strings, `kind = "url"`, `name` `Code_Review`, `name` com 41 caracteres, `name` diferente do `plugin.json`, `.claude-plugin/plugin.json` ausente, arquivo de prompt ausente, `{desconhecida}` no prompt, `result.required` ausente (AC 19, door 2)
Proof: `uv run pytest tests/test_plugin.py -k add_refuses_invalid_manifest`
Proof: `uv run pytest tests/test_plugin_manifest.py -k manifest_rules`

**C20** - `plugin add` de um plugin chamado `code-review` sai com `2` (AC 20)
Proof: `uv run pytest tests/test_plugin.py -k add_refuses_builtin_name`

**C21** - `plugin add` de um nome já instalado sai com `2` sem `--replace`; com `--replace` troca a cópia e o `origin.json` (AC 21)
Proof: `uv run pytest tests/test_plugin.py -k add_existing_needs_replace`

**C22** - `plugin add` de um diretório ilegível ou de uma URL git que o `git` não clona sai com `1`, e `~/.grokbot-kit/plugins/` fica sem diretório novo nem temporário (AC 22, door 3)
Proof: `uv run pytest tests/test_plugin.py -k add_io_failure_leaves_nothing`

**C23** - `plugin rm <instalado>` sem tarefa rodando apaga o diretório, imprime `removed <nome>` e sai com `0` (AC 23)
Proof: `uv run pytest tests/test_plugin.py -k rm_installed`

**C24** - `plugin rm code-review` e `plugin rm nao-existe` saem com `2` (AC 24)
Proof: `uv run pytest tests/test_plugin.py -k rm_refuses_builtin_and_unknown`

**C25** - O predicado de tarefa do plugin rodando: `meta.json` com `plugin.name` igual, `finished_at` `null` e dentro da janela → rodando; terminada, janela vencida, outro plugin, sem `plugin`, `meta.json` ausente ou ilegível → não rodando (AC 25)
Proof: `uv run pytest tests/test_plugin.py -k running_task_predicate`

**C26** - Com uma tarefa do plugin rodando, `plugin rm` e `plugin add --replace` saem com `2` listando o `task_id` em stderr, sem mudar a cópia (AC 25)
Proof: `uv run pytest tests/test_plugin.py -k rm_and_replace_refuse_running_task`

### S3 - o run executa um plugin · 6 arquivos · ~85 KB · ~22k · done no host de dev: C27-C36, C38, C39 verdes (C34 fechado com a matriz de teste, ok do Rodrigo em 22/10/2026); C37 verde com o `claude` real no host de dev (AD-042)

**C27** - `run --plugin <teste> --input pr=https://github.com/o/r/pull/7` com a CLI falsa: o task dir tem `plugin/` igual à origem, `work/` é um clone com o PR 7 em checkout (o `gh` falso registra `pr checkout 7`), a CLI foi lançada com `cwd` = `<task_dir>/work` e o prompt tem `{pr}`, `{workspace}`, `{result_file}` e `{task_dir}` substituídos (AC 26, doors 3 e 7)
Proof: `uv run pytest tests/test_run_plugin.py -k launches_in_clone_with_prompt`

**C28** - `--input repo=https://github.com/o/r/tree/feat/x` clona e faz checkout da branch `feat/x` (AC 26, door 7)
Proof: `uv run pytest tests/test_run_plugin.py -k branch_url_checkout`

**C29** - Saem com `2` sem criar task dir: entrada `required` ausente, `--input extra=1` não declarado, `--input` sem `=`, `pr=https://gitlab.com/o/r/-/merge_requests/1`, `pr=https://github.com/o/r/pull/abc`, `pr=https://github.com/o/r` (AC 27, door 7)
Proof: `uv run pytest tests/test_run_plugin.py -k refuses_bad_inputs_before_task_dir`

**C30** - Saem com `2` sem task dir: entrada `file` inexistente, `file` com 1 MiB + 1 byte, `text` com 64 KiB + 1 byte; aceitos: `file` com exatamente 1 MiB e `text` com exatamente 64 KiB (AC 28)
Proof: `uv run pytest tests/test_run_plugin.py -k input_size_bounds`

**C31** - Uma entrada `file` é copiada para `<task_dir>/inputs/<nome>` e `{<nome>}` no prompt vira esse caminho (AC 29)
Proof: `uv run pytest tests/test_run_plugin.py -k file_input_copied`

**C32** - `run --plugin nao-existe` sai com `2` sem task dir (AC 30)
Proof: `uv run pytest tests/test_run_plugin.py -k unknown_plugin`

**C33** - Saem com `2` sem task dir: `--plugin` com `--prompt-file`, com argumentos depois de `--`, e com `--cwd` num plugin com entrada `repo` (AC 31)
Proof: `uv run pytest tests/test_run_plugin.py -k plugin_flag_conflicts`

**C34** - Com uma matriz de teste que marca `network` `unsupported` no `opencode`, `run --plugin <network off> --tool opencode` sai com `2` sem task dir e stderr `plugin <nome> needs network=off, which opencode cannot enforce`; o mesmo plugin com uma CLI que suporta roda (AC 32, door 8)
Proof: `uv run pytest tests/test_run_plugin.py -k refuses_unenforceable_capability`

**C35** - Com o `gh` falso saindo com `1` no clone, o kit não lança a CLI e a routine recebe `error`/`failed`/`agent_error` com a saída do `gh` no `summary` (AC 33)
Proof: `uv run pytest tests/test_run_plugin.py -k clone_failure_event`

**C36** - O argv e os arquivos de harness gerados para cada CLI, a partir de `write = "task-dir"`, `network`, `commands = ["git", "gh pr view"]` e das skills do plugin, são os da linha da door 8 para aquela CLI, mais, no fim do `bash` do opencode, `"*>*": "deny"` (door 10) e `"*--output*": "deny"` (door 11), e no `permissions.deny` do claude `Bash(*--output*)` (door 11); tabela sobre as 3 CLIs × 5 capacidades (AC 34-38, AC 68, AC 70, doors 8, 10 e 11; emendado pelas AD-044 e AD-045)
Proof: `uv run pytest tests/test_launch_plugin.py -k harness_per_cli_and_capability`

**C37** - No box, com o `claude` real, o `run --plugin` de teste não consegue criar `~/grokbot-kit-c37`, não roda `touch` fora de `commands`, não dispara o hook de projeto do workspace e carrega a skill do plugin (AC 34-38)
Proof: `uv run pytest -m integration tests/integration/test_plugin_caps.py -k run_plugin_claude_end_to_end`

**C38** - O `meta.json` de uma tarefa de plugin tem `plugin` com exatamente `name`, `version`, `source`, `commit`, `capabilities` e `support`, este com as 5 capacidades da CLI usada (AC 39)
Proof: `uv run pytest tests/test_run_plugin.py -k meta_records_plugin`

**C39** - `run` sem `--plugin` gera o mesmo argv, o mesmo `claude-settings.json` e a mesma classificação de antes desta feature para as 3 CLIs (AC 40)
Proof: `uv run pytest tests/test_launch_plugin.py -k argv_without_plugin_matches_baseline`
Proof: `uv run pytest tests/test_run_plugin.py -k run_without_plugin_unchanged`

### S4 - o resultado chega estruturado à routine · 4 arquivos · ~45 KB · ~12k · done (C40-C46, C59)

**C40** - Com a CLI falsa saindo `0` e `result.json` válido, a routine recebe `completed`/`ok`/`success` com `result` igual ao objeto e `plugin` = `{"name", "version", "source", "commit"}` (AC 41, door 5)
Proof: `uv run pytest tests/test_run_plugin.py -k valid_result_delivered`

**C41** - O `summary` do evento é o `summary` do resultado; com 2001 caracteres chega com 2000 (AC 42)
Proof: `uv run pytest tests/test_run_plugin.py -k summary_from_result`

**C42** - Com a CLI saindo `0`, a routine recebe `error`/`failed`/`result_invalid` com `result` `null` para: `result.json` ausente, `[]`, `{not json`, sem um campo de `result.required`, e com `max_bytes` + 1 bytes; com exatamente `max_bytes` é `ok` (AC 43, door 6)
Proof: `uv run pytest tests/test_run_plugin.py -k invalid_result_cases`

**C43** - Numa tarefa de plugin com resultado válido e a CLI falsa registrando uma negação de permissão (`permission_denials` do `claude`), o evento é `completed`/`ok` e o `kit.log` tem a linha da negação (AC 44)
Proof: `uv run pytest tests/test_terminal.py -k plugin_task_never_denied`
Proof: `uv run pytest tests/test_run_plugin.py -k denial_logged_not_status`

**C44** - Numa tarefa de plugin, timeout, interrupção, binário ausente, erro do agente e exit `3` dão a mesma classificação de hoje, com `result` `null` e `plugin` preenchido (AC 45)
Proof: `uv run pytest tests/test_terminal.py -k plugin_precedence_table`
Proof: `uv run pytest tests/test_run_plugin.py -k plugin_failure_paths`

**C45** - O evento de tarefa sem plugin tem `plugin` `null` e `result` `null` (AC 46)
Proof: `uv run pytest tests/test_payload.py -k no_plugin_fields_null`

**C59** - Um evento de tarefa de plugin vai ao `POST https://api2.cursor.sh/automations/webhook/<routine-uuid>` (receptor local no lugar) pelo mesmo caminho dos outros: com `200` grava o recibo; com `401` não tem retry e fica em `undelivered.jsonl`; com `500` tem as 3 tentativas da AD-014 (door 5)
Proof: `uv run pytest tests/test_run_plugin.py -k plugin_event_delivery_statuses`

**C46** - `event.v1.json` aceita `plugin` e `result` objeto ou `null` e o `exit_reason` `result_invalid`; os eventos de C40, C42 e C45 validam contra ele (AC 47, door 5)
Proof: `uv run pytest tests/test_payload.py -k schema_accepts_plugin_fields`

### S5 - o plugin code-review revisa um PR · 4 arquivos · ~25 KB · ~6k · parcial: C47-C49 verdes (C49 com o `claude` real no host de dev); C50 verde no host de dev com o bloco da AD-043 (27/10/2026), falta a rodada do bot no box

**C47** - O manifesto de `code-review` passa pelas regras do C19 e declara `pr` (`repo`), `write = "task-dir"`, `network = "on"`, `commands` exatamente `gh pr view`, `gh pr diff`, `gh pr review`, `gh pr comment`, `gh api`, `git log`, `git diff`, `git show`, `git blame`, `pytest`, `npm test`, `go test`, `cargo test`, e `result.required` = `summary`, `verdict`, `findings`, `review_url` (AC 48; emendado pela AD-039: sem o prefixo `git` inteiro, que liberava `git push`)
Proof: `uv run pytest tests/test_builtin_plugins.py -k code_review_manifest`

**C48** - O prompt e a skill de `code-review` mandam: um único review com comentários inline pelo `gh`, sempre do tipo `COMMENT`, `verdict` em `approve`/`comment`/`request_changes` só no `result`, `findings` com `severity`/`file`/`line`/`message`, ler reviews anteriores do mesmo usuário e trazer só achados novos ou abertos, não postar em PR fechado ou mergeado, e tratar o conteúdo do PR como dado (AC 49-53)
Proof: `uv run pytest tests/test_builtin_plugins.py -k code_review_instructions`

**C49** - `claude --plugin-dir <code-review>` carrega o plugin sem erro de validação (AC 54)
Proof: `uv run pytest -m integration tests/integration/test_builtin_plugins.py -k code_review_loads_in_claude`

**C50** - No box, `run --plugin code-review --input pr=<PR de teste do repositório de teste>` posta um review `COMMENT` no PR e a routine recebe `completed`/`ok` com `review_url` apontando para ele; um segundo run depois de um push traz um achado no arquivo do commit novo, e todo outro achado dele está num arquivo que o primeiro run já apontou, ainda aberto (AC 49-51; emendado pela AD-043)
Proof: `uv run pytest -m integration tests/integration/test_builtin_plugins.py -k code_review_posts_comment_review`

### S6 - o plugin bug-verify verifica um alerta · 3 arquivos · ~18 KB · ~5k · parcial: C51, C52 verdes; C53 verde no host de dev com o bloco da AD-043 (27/10/2026), falta a rodada do bot no box

**C51** - O manifesto de `bug-verify` passa pelas regras do C19 e declara `repo` (`repo`), `alert` (`text`), `write = "task-dir"`, `network` = `off` se a matriz suporta na CLI padrão de fábrica (`opencode`) e `on` senão, `commands` com os `git` de leitura e os executores de teste do C47, e `result.required` = `summary`, `reproduced`, `suspects`, `next_step` (AC 55; emendado pela AD-039)
Proof: `uv run pytest tests/test_builtin_plugins.py -k bug_verify_manifest`

**C52** - O prompt e a skill de `bug-verify` mandam: `reproduced` em `yes`/`no`/`unknown`, `suspects` com `file`/`line`/`reason`, o comando do teste em `next_step` quando reproduz, `unknown` com o dado que falta quando o alerta não tem mensagem nem stack trace, e nunca abrir issue, PR nem comentário (AC 56-59)
Proof: `uv run pytest tests/test_builtin_plugins.py -k bug_verify_instructions`

**C53** - No box, com o repositório de teste que tem um `ZeroDivisionError` conhecido e o alerta dele, a routine recebe `reproduced` `yes` e o arquivo do bug em `suspects` (AC 56, AC 57)
Proof: `uv run pytest -m integration tests/integration/test_builtin_plugins.py -k bug_verify_reproduces`

### S7 - o bot e quem escreve plugins sabem usar · 5 arquivos · ~45 KB · ~12k · done: C54-C58 verdes (C57 contra a matriz do pacote, que o C8 iguala à de `spike.md`)

**C54** - O `SKILL.md` manda rodar `grokbot-kit plugin list --json` quando o usuário pergunta o que o kit sabe fazer e antes de delegar, mostrar nome, descrição e capacidades, e usar `run --plugin <nome>` com as entradas quando o pedido casa com um plugin (AC 60, AC 61)
Proof: `uv run pytest tests/test_skill_doc.py -k plugin_list_and_run`

**C55** - O `SKILL.md` manda, para instalar, `plugin show <origem> --json`, mostrar as capacidades, perguntar e só com o sim `plugin add <origem> --yes`, nessa ordem (AC 62)
Proof: `uv run pytest tests/test_skill_doc.py -k plugin_install_confirms`

**C56** - O `SKILL.md` segue sem `curl` e todo comando `grokbot-kit ...` e flag citados existem no `--help` (AC 63)
Proof: `uv run pytest tests/test_skill_doc.py -k commands_exist_in_help`

**C57** - `docs/plugins.md`, em inglês, tem as seções do layout (door 1), do manifesto e das capacidades (door 2), da matriz (door 8, igual à de `spike.md`), do resultado (door 6), do `code-review` comentado, e o aviso `may change before 1.0`; `docs/pt-BR/plugins.md` tem as mesmas seções em pt-BR, a mesma matriz e o mesmo exemplo, e o aviso `pode mudar antes da 1.0`; cada um aponta para o outro (AC 64; emendado pela AD-041)
Proof: `uv run pytest tests/test_plugin_docs.py -k guide_sections`

**C58** - `doctor --json` tem `plugins` com `name`, `version` e `source` de cada plugin; um `grokbot-kit.toml` ilegível num plugin instalado põe uma entrada em `problems`; com um plugin de entrada `repo` e o `gh` falso com `FAKE_GH_AUTH_EXIT=1`, `gh.logged_in` é `false`, o texto tem a linha `gh: not logged in; plugins with repo inputs cannot run; run: gh auth login`, e `problems` e o exit code não mudam (AC 65, AC 66; emendado pela AD-040)
Proof: `uv run pytest tests/test_doctor.py -k plugins_listed_and_problems`

### S8 - o agente sabe o que o ambiente permite · 4 arquivos · ~40 KB · ~10k · AD-043 a AD-047, depois da rodada do bot no box · C60, C63 a C66 verdes; C61, C62 e C67 no host de dev

**C60** - `run --plugin` com a CLI falsa lança o agente com o prompt do plugin seguido, depois de uma linha em branco, do bloco `## Ambiente desta tarefa` da door 9, texto exato: com `commands = ["git", "gh pr view"]` e `write = "task-dir"`, as linhas dos prefixos `` `git`, `gh pr view` ``, do comando por chamada, da leitura, de `Você só escreve dentro de <task_dir>.` e da negação; com `commands = []`, `write = "none"` e `network = "off"`, as linhas `O shell não aceita nenhum comando.`, da leitura, de `Você só escreve o arquivo de resultado, <result_file>.`, de `Sem acesso à rede.` e da negação, sem a do comando por chamada (AC 67, door 9)
Proof: `uv run pytest tests/test_run_plugin.py -k environment_block`

**C61** - Para cada CLI com `commands` diferente de `unsupported`, numa tarefa com `write = "task-dir"` e `commands = ["git log"]`, um agente instruído a rodar exatamente `git log -1 --format=x > <fora>`, `... >> <fora>`, `... 2> <fora>`, `git log -1; touch <fora>`, `git log -1 && touch <fora>`, `git log -1 | tee <fora>` e `git log -1 --format=$(touch <fora>)`, cada um com um arquivo próprio fora do task dir, termina sem que nenhum dos 7 arquivos exista (AC 2, AC 68, door 10)
Proof: `uv run pytest -m integration tests/integration/test_plugin_caps.py -k shell_escape_denied`

**C62** - Para cada CLI com `commands` diferente de `unsupported`, numa tarefa com `write = "task-dir"` e `commands = ["git log", "git show", "git diff"]`, um agente instruído a rodar exatamente `git log -1 --format=%h --output=<fora>`, `git log -1 --format=%h --output <fora>`, `git show --stat --output=<fora>` e `git diff --output=<fora>`, cada um com um arquivo próprio fora do task dir, termina sem que nenhum dos 4 exista, e o `git log -1 --format=%h` sem `--output` roda (AC 70, door 11)
Proof: `uv run pytest -m integration tests/integration/test_plugin_caps.py -k output_option_denied`

**C63** - A seção da matriz de `docs/plugins.md` tem a frase `An allowed command writes wherever its options and the code it runs allow.` e a de `docs/pt-BR/plugins.md`, `Um comando liberado escreve onde as opções e o código que ele roda deixam.`, e cada uma cita a negação de `>` no opencode e de `--output` nas duas CLIs, com a frase `Another spelling, such as quotes, gets around them.` / `Outra grafia, como aspas, contorna a regra.` (AC 69, AC 70, doors 10 e 11; emendado pelas AD-046 e AD-047)
Proof: `uv run pytest tests/test_plugin_docs.py -k write_contract`

**C64** - Com o `gh` falso clonando um repositório com os symlinks commitados `fora.txt` -> `/etc/hostname` e `docs` -> `..`, e o interno `leia.txt` -> `README.md`, o kit não lança a CLI e a routine recebe `error`/`failed`/`agent_error` com `summary` = `the clone has symbolic links that point outside it: docs, fora.txt`; com só o symlink interno, a CLI é lançada (AC 71, door 12)
Proof: `uv run pytest tests/test_run_plugin.py -k symlink_outside_clone`

**C65** - Com o `gh` falso clonando um repositório com 7 symlinks commitados para `/etc/hostname`, de nomes `g`, `b`, `f`, `a`, `e`, `c` e `d` (criados nessa ordem), a routine recebe `summary` = `the clone has symbolic links that point outside it: a, b, c, d, e (+2 more)` (AC 71, door 12)
Proof: `uv run pytest tests/test_run_plugin.py -k test_symlink_summary_shape`

**C66** - `run --plugin nota --input nota=oi --cwd <dir>` com a CLI falsa lança a CLI com `cwd` e `PWD` = `<task_dir>/work`, que existe e está vazio, o `{workspace}` do prompt vira `<task_dir>/work`, o `meta.json` grava `cwd` = `<task_dir>/work`, nada é criado em `<dir>`, e o `kit.log` tem `--cwd ignored: a plugin task runs in <task_dir>/work`; sem `--cwd`, o mesmo `cwd`, sem essa linha (AC 72, door 13)
Proof: `uv run pytest tests/test_run_plugin.py -k test_plugin_without_repo_runs_in_task_dir`

**C67** - Para cada CLI com `write` diferente de `unsupported`, num plugin sem entrada `repo` rodado com `--cwd <chamador>`, um agente instruído a criar `<chamador>/fora-cwd.txt` pela ferramenta de escrita termina sem que o arquivo exista (AC 2, AC 72, door 13)
Proof: `uv run pytest -m integration tests/integration/test_plugin_caps.py -k test_caller_cwd_not_writable`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `POST https://api2.cursor.sh/automations/webhook/<routine-uuid>` com evento de plugin: statuses (3) | `200` C40, C59 · `401` C59 · `500` C59 | - |
| matriz: CLIs × capacidades (15) | C1 table-driven sobre as 15; imposição real: `write` C2 · `commands` C3 · `workspace_config` C4 · `skills` C5 · `network` C6 | - |
| `plugin list` exit (1) | `0` C9, C10 | - |
| `plugin show` exit (2) | `0` C11, C12 · `2` C12, C13 | - |
| `plugin add` exit (3) | `0` C14, C15, C17, C21 · `1` C22 · `2` C14, C16, C18, C19, C20, C21, C26 | - |
| `plugin rm` exit (2) | `0` C23 · `2` C24, C26 | - |
| `run --plugin` exit de recusa (1) | `2` C29, C30, C32, C33, C34 | - |
| partes executáveis recusadas (5) | `hooks/` C18 · `commands/` C18 · `agents/` C18 · `.mcp.json` C18 · `.lsp.json` C18 | - |
| regras do manifesto (15) | C19, table-driven sobre as 15 | - |
| `kind` de entrada (3) | `repo` C27, C28 · `text` C30 · `file` C30, C31 | - |
| URLs da door 7, 2 aceitas e 4 recusadas (6) | PR C27 · branch C28 · GitLab C29 · PR não numérico C29 · repo sem PR/branch C29 · `--input` sem `=` C29 | - |
| escapes do shell por prefixo liberado (7) | `>` C61 · `>>` C61 · `2>` C61 · `;` C61 · `&&` C61 · pipe C61 · `$(...)` C61 | - |
| `--output` de comando liberado (4) | `git log --output=` C62 · `git log --output <f>` C62 · `git show --output=` C62 · `git diff --output=` C62 | - |
| symlinks no clone (3) | alvo absoluto fora C64 · alvo relativo fora C64 · alvo interno C64 | - |
| `summary` da door 12 (2) | até 5 caminhos, ordenados C65 · `(+N more)` C65 | - |
| `cwd` do agente de plugin (2) | com entrada `repo` C27 · sem entrada `repo` C66, C67 | - |
| bloco de ambiente: variações (2) | commands com prefixos e `write = "task-dir"` C60 · `commands = []`, `write = "none"`, `network = "off"` C60 | - |
| variáveis do prompt (4) | `{<entrada>}` C27, C31 · `{workspace}` C27 · `{result_file}` C27 · `{task_dir}` C27 | - |
| `source` de plugin (3) | `builtin` C9 · `dir` C9, C14 · `git` C17 | - |
| predicado de tarefa rodando (7) | rodando C25 · terminada C25 · janela vencida C25 · outro plugin C25 · sem `plugin` C25 · `meta.json` ausente C25 · ilegível C25 | - |
| resultado inválido (5) | ausente C42 · não objeto C42 · não JSON C42 · campo faltando C42 · acima de `max_bytes` C42 | - |
| precedência em tarefa de plugin (7) | timeout C44 · interrompida C44 · binário ausente C44 · erro do agente C44 · exit diferente de `0` C44 · resultado inválido C42 · negação com resultado válido C43 | - |
| doors do plano (13) | 1 layout C18, C49 · 2 manifesto C19 · 3 armazenamento C14, C17, C22, C27 · 4 comandos C9, C11 · 5 evento C40, C46 · 6 resultado C42 · 7 workspace C27, C28, C29 · 8 matriz C1, C8, C34, C36 · 9 ambiente no prompt C27, C60 · 10 redirecionamento C36, C61 · 11 `--output` C36, C62 · 12 symlink C64, C65 · 13 `cwd` no task dir C66, C67 | - |
| plugins próprios (2) | `code-review` C47-C50 · `bug-verify` C51-C53 | - |

- Claims que nomeiam exit code, campo de evento ou formato: C9-C26, C29-C35, C40-C46, C58 - cada um tem prova que cruza
  a fronteira (subprocesso `grokbot-kit` contra o receptor local)
- C19, C25, C36 e C44 provam a tabela na própria camada e têm prova na fronteira (C19: o primeiro `Proof:` via
  `plugin add`; C25: C26; C36: C37 no box; C44: o segundo `Proof:`)
- Imposição de capacidade (AC 34-38) é provada só no box (C2-C6, C37): no CI a CLI é falsa e só o harness gerado (C36)
  é verificável

## Test policy

As linhas da `## Test policy` de `docs/.specs/features/agent-run-notify/checks.md` valem aqui sem mudança (o repo
não tem guia de testes; essas linhas são o padrão do projeto).

Evidência:

- `plugin.py`, validação do manifesto: 15 regras -> decide, alcançado pela CLI (C19, duas provas)
- `plugin.py`, tarefa rodando: 7 casos -> decide (C25 + C26); análogo: o predicado de `update.py` (`tests/test_update.py`)
- `launch.py`, harness por CLI e capacidade: 15 células -> decide (C36 + C37 no box); análogo: `agent_argv` já provado
  por CLI em `tests/test_launch.py`
- `terminal.py`, classificação com plugin: 7 linhas -> decide (C44 + C43)
- `run.py`, validação de entradas: 10 casos -> ponto de entrada que decide, provado na fronteira (C29-C33)
- `doctor.py`: repassa a lista -> instrumentação, coberta por C58

## Swept

- validation: C19 (manifesto), C29, C30 (entradas e limites), C42 (resultado)
- failure modes: C22 (`plugin add` sem resto parcial), C35 (clone falhou), C42, C44
- idempotency: C21 (`add` repetido exige `--replace`), C50 (re-review traz só achados novos, sem estado no kit)
- authorization: C2-C6, C34, C37 (o que o agente pode fazer é a capacidade declarada; CLI sem suporte recusa); C14-C16 (instalar exige confirmação); rate limit n/a - comandos locais, o GitHub limita o `gh` do box como hoje
- concurrency: C26 (`rm`/`--replace` com tarefa rodando), C27 (a tarefa roda a cópia do task dir), C22 (gravação por temporário + rename); dois runs no mesmo PR têm task dirs separados e o C50 cobre o review repetido
- data lifecycle: existing - `gc` apaga o task dir com o clone (`tests/test_gc.py`); plugins instalados só saem por `plugin rm` (C23)
- dependency failure: C35 (`gh`/clone), C58 (`gh` sem login no `doctor`), C22 (`git` no `plugin add`)
- state transitions: C40-C44 (classificação do fim da tarefa de plugin)
- observability: C38 (`meta.json` com plugin e capacidades em vigor), C43 (negação no `kit.log`), C35 (saída do `gh` no `summary`)

## Handoff

Arquivos tocados: existentes `cli.py` (7,4 KB), `run.py` (9,6 KB), `launch.py` (2 KB), `terminal.py` (3,3 KB),
`payload.py` (6,2 KB), `doctor.py` (8,5 KB), `assets/event.v1.json` (6 KB), `SKILL.md` (11 KB), `tests/conftest.py`
(9 KB), `tests/test_launch.py`, `tests/test_terminal.py`, `tests/test_payload.py`, `tests/test_doctor.py`,
`tests/test_skill_doc.py` (~45 KB juntos), `CHANGELOG.md` (8 KB) ≈ 116 KB; novos `plugin.py` (~15 KB), 2 plugins
próprios (~12 KB), `docs/plugins.md` (~10 KB), `spike.md` (~8 KB), fake `gh` (~3 KB), 7 arquivos de teste novos
(~60 KB) ≈ 108 KB. Total ~224 KB ÷ 4 ≈ 56k, mais `plan.md` (~30 KB) e este arquivo (~22 KB) ≈ 13k: ~69k, abaixo do
budget de 150k.

- S1 = 3k + rodadas no box; S2 a 21k; S3 a 43k; S4 a 55k; S5 a 61k; S6 a 66k; S7 a 78k (com sobreposição; o total
  real é o ~69k acima) → um builder
- Mechanism: um builder
- S1 roda no box (CLIs reais, `-m integration`); S2 e S4 não dependem da matriz e podem andar antes; S3 só fecha
  C34, C36 e C37 com a matriz preenchida. C2-C6, C37, C49, C50 e C53 rodam só no box
