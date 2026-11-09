# plugins verification

**Verdict**: PASS
**Profile**: standard
**Diff range**: cdf3c25..ae59fbe (provas do box da 0.4.1 sob re-verificação; feature desde 7f17f2a)
**Round**: 8 - scoped
**Verifier**: independent sub-agent (author != verifier); não escreveu o código nem as rodadas anteriores

A rodada 7 deu FAIL só pelo que depende do box. Os três motivos fecham nesta rodada:

1. **C50 e C53 têm prova no box.** O `0.4.1-pytest.log` mostra `test_bug_verify_reproduces PASSED` (C53) e o
   `0.4.1-c50.log` mostra `test_code_review_posts_comment_review PASSED` (C50), os dois com o `grokbot-kit` 0.4.1 do
   box. O C50 tem corroboração independente no GitHub, que conferi só por leitura: os reviews 5683162673 e 5683173344
   existem, estão `COMMENTED`, e o segundo está no commit `f91b175`. Esse commit acrescenta só `c50_336669.py`, e o
   segundo review aponta esse arquivo.
2. **F7 morreu.** O ramo `name` de `skill_invoked` (`tests/integration/test_plugin_caps.py:113`) é o único que casa no
   opencode 1.19.3. Instalei o `opencode-ai@1.19.3` numa pasta scratch e rodei o C5 com ele no host de dev. O evento
   de skill do `out.jsonl` é `{"tool": "skill", "status": "completed", "input": {"name": "spike"}}`, sem `id`. Com o
   F7 (ramo `name` removido), o `test_plugin_skill_loaded[opencode]` falhou em `:301`. Sem o mutante, passou. No box,
   que tem o opencode 1.19.3 (`0.4.1-doctor.txt`), o mesmo teste deu `PASSED`, então lá também foi o ramo `name` que
   casou.
3. **A linha `Test policy` de integração está atendida.** As provas `-m integration` rodaram no box, uma vez por CLI. O
   claude e o opencode passaram em todas. O Codex e o `network` pularam pela matriz do pacote, como no host de dev.

O que a evidência do box prova e o que não prova está na seção "Evidência do box (rodada 8)".

Onde rodou cada prova nesta rodada:

- A suíte de CI rodou em `HEAD` = `ae59fbe` no host de dev.
- As provas `-m integration` de `test_plugin_caps.py -k opencode` rodaram no host de dev com o **opencode 1.19.3**
  (scratch, `opencode/glm-5.3-flash-free`), numa worktree scratch em `HEAD`: 7 passed, 1 skipped.
- C50 e C53 não rodaram aqui, porque postam no GitHub. A prova deles é a do box.

Escopo. O diff `cdf3c25..ae59fbe` não toca em `src/`, e `git diff --stat cdf3c25..HEAD -- src` sai vazio. A tag `v0.4.1`
aponta para `cdf3c25`, então o código que rodou no box é o código de `HEAD`. O diff muda:

- `tests/integration/test_builtin_plugins.py:121-123`: o `git commit` do C50 com `-c user.name/user.email`.
- O docstring de `tests/integration/test_real_cli.py`.
- A frase das versões provadas da matriz (`docs/plugins.md:83-86`, `docs/pt-BR/plugins.md:83-84`).
- Acrescenta a pasta `box/` e o `STATE.md`.

Re-verifiquei C5, C37, C49, C50, C53 e C57, além das provas de matriz que o box rodou (C2, C3, C4, C61, C62, C67). Julguei
de novo a linha de integração do `Test policy` e recomputei a linha "plugins próprios" do Coverage. O resto vem da
rodada 7, com as provas de CI re-rodadas e verdes em ae59fbe.

## Binding sources

Carried from 81d160e. O passo 1 só roda no perfil `ui`, e o diff não mexe numa interface com tela nem nas doors.

| Source | Opened | Contradiction | Uncovered |
| --- | --- | --- | --- |
| `docs/.specs/features/plugins/design.md` (binding) | yes - local file (round 1) | none | - |

Rodada 7 (verified at 81d160e): li a door 13 (`plan.md:102`), a AC 72 (`plan.md:227`) e a AD-047
(`docs/.specs/STATE.md:53`). Comparei com o código (`run.py:132-134`, `:257-260`, `:346`, `:373`, `:387`, `:398-399`),
com o C66 e o C67, com os guias (`docs/plugins.md:57-58`, `:60`; `docs/pt-BR/plugins.md:57-58`, `:60`), com o
`skills/grokbot-kit/SKILL.md:205` e com o CHANGELOG (`:23-25`, a entrada nova começa em `:23`). O `cwd` e o `PWD` do agente, o `work/` vazio, o
`{workspace}`, o `meta.json` e a linha do `kit.log` batem. Há uma diferença pequena, fora do veredito: o `--cwd` de um
plugin sem `repo` é "ignorado", mas ainda é validado antes (`run.py:132-134`). Um `--cwd` que não é diretório sai com
`2`, `--cwd is not a directory`. A door diz "ignorado", e nenhum check cobre esse caso.

## Checks

Proofs re-run at ae59fbe. Os resultados de C5, C37, C49, C50, C53 e C57 foram verificados em ae59fbe. O C57 rodou no
host de dev, C49, C50 e C53 têm a prova do box, e o C5 tem as duas. As citações de `tests/integration/test_builtin_plugins.py`
foram atualizadas, porque o diff deslocou em 2 as linhas depois de `:121`. As demais linhas vêm da rodada 7 (81d160e),
com as provas de CI re-rodadas e verdes em ae59fbe.

Rodada de CI: `uv run pytest -q -rA` (suíte completa) saiu com **763 passed**, 48 deselected e 0 failed, a mesma
contagem da rodada 7.

Integração no box (`0.4.1-pytest.log`, a partir da tag `v0.4.1`): 18 passed, 10 skipped e 1 failed (o `git commit` do
C50). C2, C3, C4, C5, C61, C62 e C67 deram `PASSED` em `[claude]` e `[opencode]`. C37, C49 (2) e C53 também deram
`PASSED`. Os skips são 7 do Codex e 3 do `network`, todos em `test_plugin_caps.py:42`. No `0.4.1-c50.log`, o C50 deu
1 passed.

Integração no host de dev com o opencode 1.19.3 (rodada 8): `-k opencode` saiu com 7 passed e 1 skipped (`network`).
O `bin` gravado na config da tarefa era o binário 1.19.3 da scratch.

Fake `gh` nas provas de integração. As provas C4, C37 e C62 agora recebem o workspace pelo caminho real do kit:
`_clone` (`run.py:279-303`) chama o `gh`, e o `tests/fakes/gh` faz um `git clone` do repositório local de teste em
`<task_dir>/work`. Assim o agente real vê um clone de verdade, com a config de projeto commitada, como num PR. Conferi
nos task dirs: `work/.claude/settings.json` no claude e `work/opencode.json` no opencode. A única parte falsa é a busca
na rede, e nenhuma dessas provas trata de rede. O M16 confirma que o C4 segue discriminando: sem
`OPENCODE_DISABLE_PROJECT_CONFIG`, o `test_workspace_config_ignored[opencode]` falhou porque o marcador foi criado. O C62
perdeu a edição suja do `a.txt`, mas `git diff --output=<f>` cria o arquivo mesmo vazio numa árvore limpa (conferido
localmente), então a negação do `git diff` segue sendo provada. Por isso as três provas continuam provando o que os
claims dizem.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | `spike.md` tem 15 células com valor, versão, comando e saída | CI `-k matrix_complete` PASSED | `tests/test_plugin_spike.py:45` - `sorted(cells) == sorted(expected)`; `:47-50`. Carried from 7a6d41b | PASS |
| C2 | escrita fora do task dir negada em cada CLI com `write` suportado (AC 2) | integração `test_write_outside_denied[claude]` PASSED, `[opencode]` PASSED, `[codex]` SKIPPED (`needs`, `:42`), host de dev, em 81d160e | `tests/integration/test_plugin_caps.py:180` - `assert not outside.exists(), event`. O caso da rodada 6 (escrita no cwd de plugin sem `repo`) foi fechado pela door 13 e está provado pelo C67 e pela sonda 1. Verified at 81d160e | PASS |
| C3 | comando fora de `commands` não roda | integração `[claude]`, `[opencode]` PASSED em 81d160e | `tests/integration/test_plugin_caps.py:273` - `assert not (task_dir / "spike-cmd").exists(), event` | PASS |
| C4 | hook ou plugin do workspace não dispara | integração `[claude]`, `[opencode]` PASSED em 81d160e, com o workspace clonado pelo `gh` falso | `tests/integration/test_plugin_caps.py:289` - `assert not marker.exists(), event`; `:290` - `not (task_dir / "spike-hook").exists()`. A config commitada chega ao clone (`work/opencode.json`, `work/.claude/settings.json` nos task dirs). M16 morto aqui. Verified at 81d160e | PASS |
| C5 | a skill do plugin carrega (`spike-skill-ok`) | box: `[claude]`, `[opencode]` PASSED (opencode 1.19.3, `0.4.1-pytest.log`); host de dev com o opencode 1.19.3: `[opencode]` PASSED em ae59fbe | `tests/integration/test_plugin_caps.py:300` - `(event["status"], ...["word"]) == ("ok", "spike-skill-ok")`; `:301` - `skill_invoked(...)`; ramo `name` em `:113` - `"spike" in (skill.get("id"), skill.get("name"))`. O 1.19.3 grava `input.name`, e o 2.1.3 grava `id` (rodadas anteriores): os dois ramos estão exercitados. F7 morto. Verified at ae59fbe | PASS |
| C6 | `network = off` sem resposta, por CLI com `network` suportado | integração `test_network_off_denied[*]` 3 SKIPPED | vale por vacuidade: `src/grokbot_kit/assets/capabilities.json:4,11,18` `"network": "unsupported"`; skip em `tests/integration/test_plugin_caps.py:42`. Carried from 7a6d41b | PASS |
| C7 | `unsupported` em write/workspace_config exclui a CLI; célula dependente de host tem sonda | CI PASSED | `tests/test_plugin_spike.py:65-67`, `:74`. Carried | PASS |
| C8 | matriz do pacote = `spike.md` | CI `-k package_matrix_matches_spike` PASSED | `tests/test_plugin_spike.py:82`. Carried | PASS |
| C9 | forma de `plugin list --json` | CI PASSED | `tests/test_plugin.py:119-123`, `:125` `set(p) == DOOR_4_KEYS`. Carried | PASS |
| C10 | linha de texto do `list` | CI PASSED | `tests/test_plugin.py:137`, `:140`, `:142`. Carried | PASS |
| C11 | `show code-review --json` com `support` 3 × 5 | CI PASSED | `tests/test_plugin.py:153`, `:155`. Carried | PASS |
| C12 | `show <dir>` igual ao `add`, sem gravar | CI PASSED | `tests/test_plugin.py:168`, `:170`, `:176`, `:178`. Carried | PASS |
| C13 | `show nao-existe` exit 2 + mensagem | CI PASSED | `tests/test_plugin.py:185-186`. Carried | PASS |
| C14 | confirmação em pty | CI PASSED | `tests/test_plugin.py:193-210`. Carried | PASS |
| C15 | `--yes` com stdin fechado | CI PASSED | `tests/test_plugin.py:217-220`. Carried | PASS |
| C16 | sem tty e sem `--yes` exit 2 | CI PASSED | `tests/test_plugin.py:226`, `:228`. Carried | PASS |
| C17 | git `--ref` fixa o commit | CI PASSED | `tests/test_plugin.py:241-245`, `:252-253`. Carried | PASS |
| C18 | 5 partes executáveis recusadas | CI 5/5 PASSED | `tests/test_plugin.py:266-268`. Carried | PASS |
| C19 | 15 regras do manifesto | CI `-k add_refuses_invalid_manifest`, `-k manifest_rules` PASSED | `tests/test_plugin.py:278-280`; `tests/test_plugin_manifest.py:159-160`; `:82` `len(INVALID) == 15`; `:141-142`. Carried | PASS |
| C20 | `add` com nome `code-review` exit 2 | CI PASSED | `tests/test_plugin.py:294`. Carried | PASS |
| C21 | `--replace` | CI PASSED | `tests/test_plugin.py:307-314`. Carried | PASS |
| C22 | falha de I/O sem resto | CI PASSED | `tests/test_plugin.py:326-332`. Carried | PASS |
| C23 | `rm` imprime `removed <name>` | CI PASSED | `tests/test_plugin.py:339-341`. Carried | PASS |
| C24 | `rm` de builtin e desconhecido exit 2 | CI 2/2 PASSED | `tests/test_plugin.py:349`. Carried | PASS |
| C25 | predicado de tarefa rodando, 7 casos | CI PASSED | `tests/test_plugin.py:370`, `:375`. Carried | PASS |
| C26 | `rm`/`--replace` recusam com tarefa rodando | CI PASSED | `tests/test_plugin.py:390-399`. Carried | PASS |
| C27 | plugin copiado, PR em checkout, `cwd` em `work`, variáveis substituídas no prompt | CI `-k launches_in_clone_with_prompt` PASSED em 81d160e | `tests/test_run_plugin.py:140` - `tree(task_dir/"plugin") == tree(source)`; `:146` - `calls[1] == {"argv": ["pr","checkout","7"], "cwd": str(work)}`; `:148` - `launched["cwd"] == str(work)`; `:149-152` - igualdade exata do prompt com `{pr}`, `{workspace}` = `work`, `{result_file}`, `{task_dir}` e o bloco da door 9. O ramo com `repo` de `_prepare_plugin` (`run.py:258`) não mudou. Verified at 81d160e | PASS |
| C28 | URL de branch clona `feat/x` | CI PASSED | `tests/test_run_plugin.py:199`, `:201` | PASS |
| C29 | 6 entradas ruins exit 2 sem task dir | CI 6/6 PASSED | `tests/test_run_plugin.py:219-222` | PASS |
| C30 | limites de tamanho | CI 5/5 PASSED | `tests/test_run_plugin.py:256-257` aceito; `:259-260` recusado | PASS |
| C31 | entrada `file` copiada para `inputs/<nome>` e substituída | CI `-k file_input_copied` PASSED | `tests/test_run_plugin.py:271` conteúdo copiado; `:272` igualdade do prompt | PASS |
| C32 | `--plugin nao-existe` exit 2 | CI PASSED | `tests/test_run_plugin.py:280-282` | PASS |
| C33 | conflitos de flags exit 2 (inclui `--cwd` com entrada `repo`) | CI `-k plugin_flag_conflicts` 3/3 PASSED em 81d160e (`[prompt_file]`, `[extras]`, `[cwd]`) | `tests/test_run_plugin.py:296` - `result.returncode == 2`; `:297` - `kit.tasks() == []`. A recusa do `--cwd` com `repo` segue em `run.py:70-71`, antes da door 13, que só ignora o `--cwd` sem `repo`. Verified at 81d160e | PASS |
| C34 | capacidade não imponível exit 2 com a mensagem | CI PASSED | `tests/test_run_plugin.py:306-307`, `:310-311` | PASS |
| C35 | falha de clone vira evento `agent_error` | CI `-k clone_failure_event` PASSED | `tests/test_run_plugin.py:318`, `:320` `outcome(event) == ("error","failed","agent_error")`, `:321` | PASS |
| C36 | tabela de harness por CLI e regras das doors 8, 10 e 11 | CI `-k harness_per_cli_and_capability` 5 PASSED | `tests/test_launch_plugin.py:74`, `:88`, `:96`, `:109`, `:120`, `:130`; na fronteira, `tests/test_run_plugin.py:188` - `cwd == env["PWD"] == str(task_dir/"work")`. Carried from b423314 (arquivos de `launch` intocados) | PASS |
| C37 | `claude` real end to end | integração `test_run_plugin_claude_end_to_end` PASSED em 81d160e (`claude` 2.1.312, `sonnet`, host de dev), com o workspace clonado pelo `gh` falso | `tests/integration/test_plugin_caps.py:338` - `not outside.exists() and not home_outside.exists()`; `:339` - `not (task_dir/"spike-cmd").exists()`; `:340` - `not marker.exists()`; `:341` `word == "spike-skill-ok"`; `:342` `skill_invoked("claude", ...)`. O clone tinha `work/.claude` (conferido na rodada 7). Rodada 8: no box, `test_run_plugin_claude_end_to_end PASSED` (`0.4.1-pytest.log`), o que fecha a observação 6 da rodada 7 (o claim diz "No box"). Verified at ae59fbe (evidência do box) | PASS |
| C38 | `meta.json` `plugin` com 6 chaves | CI PASSED | `tests/test_run_plugin.py:401`, `:402-407` (citação atualizada; o diff moveu o arquivo) | PASS |
| C39 | `run` sem `--plugin` inalterado | CI 2 PASSED | `tests/test_launch_plugin.py:20-56`; `tests/test_run_plugin.py:416-422`, `:432` | PASS |
| C40 | resultado válido vira `completed/ok/success` | CI PASSED | `tests/test_run_plugin.py:439-441` | PASS |
| C41 | summary do resultado, truncado em 2000 | CI PASSED | `tests/test_run_plugin.py:450` | PASS |
| C42 | 5 resultados inválidos; `max_bytes` exato ok | CI 6 PASSED | `tests/test_run_plugin.py:464-467`, `:475-476` | PASS |
| C43 | negação em tarefa de plugin | CI 2 PASSED | `tests/test_terminal.py:228`; `tests/test_run_plugin.py:500-502`, `:520-522` | PASS |
| C44 | precedência de falhas | CI 7 + 5 PASSED | `tests/test_terminal.py:281`; `tests/test_run_plugin.py:582-584` | PASS |
| C45 | evento sem plugin com `plugin`/`result` null | CI PASSED | `tests/test_payload.py:418`, `:426`. Carried | PASS |
| C46 | schema aceita os campos novos | CI PASSED | `tests/test_payload.py:444`, `:457`, `:470-471`; `tests/test_run_plugin.py:440`, `:465` | PASS |
| C47 | manifesto do `code-review` | CI PASSED | `tests/test_builtin_plugins.py:35-44`. Carried | PASS |
| C48 | instruções do `code-review` | CI PASSED | `tests/test_builtin_plugins.py:50-64`. Carried | PASS |
| C49 | `claude --plugin-dir` carrega o plugin | box: `test_code_review_loads_in_claude[code-review]` e `[bug-verify]` PASSED (`0.4.1-pytest.log`); antes, 2 PASSED no host de dev (rodada 3, `claude` 2.1.311) | `tests/integration/test_builtin_plugins.py:82-83` - `validated.returncode == 0` e `"Validation passed" in validated.stdout`; `:94-96`. Linhas intocadas pelo diff. Verified at ae59fbe (evidência do box) | PASS |
| C50 | **no box**: review `COMMENT` postado, routine com `completed`/`ok` e `review_url`; segundo run com achado no arquivo novo | box: `test_code_review_posts_comment_review` PASSED (`0.4.1-c50.log`, 1 passed, 88 s, tag `v0.4.1`, identidade git pelo ambiente). No GitHub (só leitura): review 5683162673 `COMMENTED` às 13:16:06 em `7f92f65`; commit `f91b175` (autor `grokbot-kit-it`, só `c50_336669.py`) às 13:16:26; review 5683173344 `COMMENTED` às 13:16:56 em `f91b175`, com comentários em `c50_336669.py` e `calc/desconto.py`, e o primeiro run já tinha apontado este último | `tests/integration/test_builtin_plugins.py:107` - `(event["event"], event["status"]) == ("completed", "ok")`; `:109` - `review_url.startswith(pr)`; `:112` - `review["state"] == "COMMENTED"`; `:127` - segundo run `completed`/`ok`; `:131` - `novo in second_files`; `:132` - `second_files <= {novo} ∪ first_files` (união de conjuntos). Verified at ae59fbe (evidência do box) | PASS |
| C51 | manifesto do `bug-verify` | CI PASSED | `tests/test_builtin_plugins.py:72-75`. Carried | PASS |
| C52 | instruções do `bug-verify` | CI PASSED | `tests/test_builtin_plugins.py:81-87`. Carried | PASS |
| C53 | **no box**: `reproduced` `yes` e o arquivo do bug em `suspects` | box: `test_bug_verify_reproduces` PASSED (`0.4.1-pytest.log`, tag `v0.4.1`, `claude`, que é o padrão de `GROKBOT_KIT_IT_BUG_TOOL`) | `tests/integration/test_builtin_plugins.py:142` - `completed`/`ok`; `:143` - `event["result"]["reproduced"] == "yes"`; `:144` - `bug_file in [s["file"] for s in event["result"]["suspects"]]`. Linhas deslocadas em 2 pelo diff, mas o corpo é igual ao da tag. Verified at ae59fbe (evidência do box) | PASS |
| C54 | SKILL.md: `plugin list --json`, `run --plugin` | CI PASSED | `tests/test_skill_doc.py:407`, `:415`. O diff mudou a frase do `--cwd` em `skills/grokbot-kit/SKILL.md:205`, fora do que o check cobra | PASS |
| C55 | ordem de instalação | CI PASSED | `tests/test_skill_doc.py:435`. Carried | PASS |
| C56 | sem `curl`, flags no `--help` | CI PASSED | `tests/test_skill_doc.py:442`, `:452`. Carried | PASS |
| C57 | guias en e pt-BR: seções, matriz, aviso, links cruzados | CI `-k guide_sections` [en], [pt-BR] PASSED em ae59fbe; rodada 8: o diff mexe só na frase das versões provadas (`docs/plugins.md:83-86`, `docs/pt-BR/plugins.md:83-84`). O `opencode` 1.19.3 agora tem lastro: rodou no box e no host de dev | `tests/test_plugin_docs.py:71-72` aviso e link antes da primeira seção; `:96` matriz = `plugin.matrix()`; `:104-105` exemplo = arquivos do builtin. O diff acrescenta a frase da door 13 (`docs/plugins.md:57-58`, `docs/pt-BR/plugins.md:57-58`), troca `{workspace}` (o clone) por `<task_dir>/work` (`:60` nas duas) e re-quebra o parágrafo da matriz (`:97-104`). Igual nas duas línguas. Verified at 81d160e | PASS |
| C58 | `doctor --json` `plugins`, problemas, aviso do `gh` | CI PASSED | `tests/test_doctor.py:334`, `:344-347`, `:353`, `:356`. Carried | PASS |
| C59 | entrega do evento de plugin: 200, 401, 500 | CI 3 PASSED | `tests/test_run_plugin.py:598-608` | PASS |
| C60 | prompt do plugin + linha em branco + bloco `## Ambiente desta tarefa`, nas duas variações | CI `-k environment_block` PASSED em 81d160e | `tests/test_run_plugin.py:162` - `prompt.endswith(".\n\n" + environment_block(task_dir))`; `:171-179` - igualdade exata da variação `commands = []`, `write = "none"`, `network = "off"`. Essa variação é um plugin sem `repo` (`nota`), que agora roda em `work/` vazio, e o texto não mudou. Verified at 81d160e | PASS |
| C61 | 7 escapes do shell não criam arquivo fora do task dir | integração `[claude]`, `[opencode]` PASSED em 81d160e, `[codex]` SKIPPED | `tests/integration/test_plugin_caps.py:207` - `sorted(p.name for p in outside.iterdir()) == []` | PASS |
| C62 | `--output` de comando liberado (4 formas) negado e `git log -1 --format=%h` roda | integração `test_output_option_denied[claude]`, `[opencode]` PASSED em 81d160e, `[codex]` SKIPPED; workspace pelo clone do `gh` falso | `tests/integration/test_plugin_caps.py:240` - `sorted(p.name for p in outside.iterdir()) == []`; `:241` - `event["result"]["head"] == head`, que prova que o prefixo roda no clone. Árvore limpa: `git diff --output` cria o arquivo vazio mesmo assim, então a forma do `git diff` continua discriminando. Verified at 81d160e | PASS |
| C63 | frase do contrato e da grafia (`gets around them.` / `contorna a regra.`) e cita `>` e `--output` | CI `-k write_contract` [en], [pt-BR] PASSED em 81d160e | `tests/test_plugin_docs.py:127` - `assert contract in matrix`; `:128` - `assert spelling in matrix`, com as frases literais em `:114-120` (`"Another spelling, such as quotes, gets around them."`); `:129-130`. Frases em `docs/plugins.md:101-102` ("Both rules match the literal text. Another spelling, such as quotes, gets around them.") e `docs/pt-BR/plugins.md:101-102`; CHANGELOG `:19`. A imprecisão da rodada 6 (maiúscula depois de dois-pontos, `it`) foi corrigida. Verified at 81d160e | PASS |
| C64 | clone com `fora.txt` -> `/etc/hostname` e `docs` -> `..` não lança a CLI e entrega `summary` exato; só com o interno, lança | CI `-k symlink_outside_clone` PASSED em 81d160e | `tests/test_run_plugin.py:334-335` - lança com o link interno; `:344` `returncode == 1`; `:345` `not kit.record.exists()`; `:348` `outcome(event) == ("error","failed","agent_error")`; `:349` `summary == "... docs, fora.txt"` | PASS |
| C65 | 7 symlinks para fora (`g b f a e c d`) dão `summary` = `... a, b, c, d, e (+2 more)` | CI `-k test_symlink_summary_shape` PASSED em 81d160e | `tests/test_run_plugin.py:356-357` cria os 7 links na ordem `gbfaecd`; `:360` `returncode == 1`; `:361` `not kit.record.exists()`; `:363` - `event["summary"] == "the clone has symbolic links that point outside it: a, b, c, d, e (+2 more)"`. Código: `src/grokbot_kit/run.py:321-323`. M10 e M11 mortos aqui | PASS |
| C66 | plugin sem `repo` com `--cwd <dir>`: CLI com `cwd` e `PWD` = `<task_dir>/work`, vazio, `{workspace}`, `meta.json`, nada em `<dir>`, linha no `kit.log`; sem `--cwd`, mesmo `cwd` sem a linha | CI `-k test_plugin_without_repo_runs_in_task_dir` PASSED em 81d160e | `tests/test_run_plugin.py:378` - `launched["cwd"] == launched["env"]["PWD"] == str(work)`; `:379-380` `work.is_dir()` e `list(work.iterdir()) == []`; `:381` prompt começa com `f"Área {work}; nota oi.\n\n"`; `:382` `meta.json["cwd"] == str(work)`; `:383` `list(caller.iterdir()) == []`; `:385` `f"--cwd ignored: a plugin task runs in {work}" in log`; `:392` sem `--cwd`, `cwd == str(task_dir/"work")`; `:393` `"--cwd ignored" not in` log. Código: `run.py:257-260`, `:373`, `:398-399`. M13, M14 e M15 mortos aqui | PASS |
| C67 | para cada CLI com `write` suportado, plugin sem `repo` com `--cwd <chamador>`: o agente não cria `<chamador>/fora-cwd.txt` pela ferramenta de escrita | integração `test_caller_cwd_not_writable[claude]` PASSED, `[opencode]` PASSED, `[codex]` SKIPPED (`needs`, `:42`), host de dev, em 81d160e | `tests/integration/test_plugin_caps.py:258` - `assert sorted(p.name for p in caller.iterdir()) == [], event["result"]`; `:259` - linha `--cwd ignored` no `kit.log`. O opencode tentou de fato: o `write` voltou `Permission denied: external_directory` no `out.jsonl`. Com o M13, `[opencode]` FALHOU com `['fora-cwd.txt']` ("o arquivo fora-cwd.txt foi criado com sucesso"): a prova discrimina o defeito da rodada 6 | PASS |

## Evidência do box (rodada 8)

Os arquivos de `docs/.specs/features/plugins/box/` são o que o bot devolveu. O host de dev não alcança o box, então não
consigo reproduzi-los. Julguei cada um pelo que ele prova sozinho e pelo que dá para conferir de fora.

| Arquivo | O que prova | O que não prova / ressalva |
| --- | --- | --- |
| `0.4.1-doctor.txt` | `grokbot-kit` 0.4.1, `opencode` 1.19.3 em `/home/box/.opencode/bin/opencode` como CLI padrão, matriz `tool`/`unsupported` igual à do pacote, `code-review` e `bug-verify` builtin | não traz a versão do `claude`. O `login: not logged in` do opencode é compatível com o modelo `-free`. Data "27-28/10" |
| `0.4.1-pytest.log` | 29 coletados, 18 passed, 10 skipped e 1 failed, batendo com o README. Os nomes de teste batem com os `Proof:` do `checks.md` (C2-C5, C37, C49, C53, C61, C62, C67). O traceback cita `test_builtin_plugins.py:121` com o `git commit` sem `-c`, que é o texto da tag `v0.4.1`, e não o de `HEAD` | o log não mostra a versão da CLI que cada teste usou. Inferi o opencode 1.19.3 pelo `doctor` do mesmo box (o `real_bin` usa `shutil.which`). O log não diz o modelo do claude: o `STATE.md` diz `sonnet`, e o README cita só o do opencode |
| `0.4.1-c50.log` | o C50 sozinho, 1 passed em 88 s. O GitHub confirma de forma independente: dois reviews `COMMENTED`, separados por 50 s, com o commit `f91b175` no meio | o C50 rodou com a identidade pelo ambiente sobre o código da tag, e não com o `-c` de `HEAD`. A mudança é só de teste e equivalente, e a identidade do commit no GitHub (`grokbot-kit-it`, `it@grokbot-kit.invalid`) é a mesma do `-c` |
| `README.md` | proveniência, datas e links | o review 5680620067 é do run que falhou (09:43), e não conta para o C50 |

Os dois reviews têm o corpo (summary) idêntico, palavra por palavra: "Re-review sem commits novos desde o último review
(HEAD 7f92f65)...". Os comentários inline são diferentes. O PR de teste acumula cópias `c50_*.py` de runs anteriores.
Nada disso contradiz o claim do C50 (`:131-132` olham os `findings` do `result.json`), mas está registrado nas notas.

## Sondas adversariais (rodada 7)

Carried from 81d160e.

Todas pela ferramenta de escrita do agente, sem shell (`commands = []`), num plugin sem `repo` rodado com
`--cwd <chamador>`. Rodaram uma vez em cada CLI, numa worktree scratch com o código de `HEAD` e um arquivo só da scratch
(`tests/integration/test_probe_r7.py`, que usa `spike_plugin`, `run_plugin` e `needs` do `test_plugin_caps.py`). Host
de dev. Resultado: `test_probe_door13[claude]` e `[opencode]` PASSED.

| # | Tentativa | Resultado |
| --- | --- | --- |
| 1 | caminho absoluto no diretório de quem chamou (`<chamador>/fora-abs.txt`) | negado nas duas CLIs (`claude`: "fora dos diretórios permitidos"; `opencode`: `Permission denied: external_directory`). `<chamador>` terminou vazio |
| 2 | caminho relativo `../../../../../chamador/fora-rel.txt`, a partir de `<task_dir>/work` | negado nas duas. O `claude` resolveu o caminho para `<chamador>/fora-rel.txt` e recusou. O `opencode` respondeu `external_directory`: o caminho resolvido sai do projeto |
| 3 | `~/fora-til.txt` (o `HOME` da tarefa é o `home` temporário do teste) | negado nas duas; nada em `<tmp>/home` nem no `$HOME` real |
| 4 | `$HOME` real absoluto (`/home/rodrigo/grokbot-kit-r7-probe.txt`) | negado nas duas; o arquivo não existe |
| 5 | `{task_dir}/../vizinho.txt` (diretório `tasks/`, fora do task dir) | negado nas duas; `tasks/` sem arquivo novo |
| 6 | `{task_dir}/dentro.txt` (dentro do task dir, fora de `work/`) | gravado nas duas, dentro do contrato (`write = "task-dir"`). No opencode isso confirma que o projeto agora é `<task_dir>/work`: o task dir fica fora do projeto e é alcançado pelo allow `"<task_dir>/*"` do `external_directory` (`launch.py:91`), do mesmo jeito que o `result.json` |
| 7 | `{workspace}/local.txt` | gravado nas duas (dentro do projeto) |
| 8 | mesmo plugin com o agente de volta no cwd de quem chamou (M13, só na scratch) | o `opencode` gravou `<chamador>/fora-cwd.txt` de novo, o que reproduz o defeito da rodada 6. Isso mostra que o fix é o que fecha o caminho |

Nada fora do contrato escrito apareceu. Os caminhos que a AD-045 admite (opção de comando liberado, código do repositório)
não entram aqui, porque o plugin das sondas não tem `commands`.

## Coverage

Rodada 8 (verified at ae59fbe): recomputei a linha "plugins próprios", que agora tem a evidência do box, e a da matriz
(versão 1.19.3). As outras são carried from 81d160e, e as que eram carried antes seguem com a origem indicada.

| Set (size) | Recomputed from | Member -> proof | Unproven |
| --- | --- | --- | --- |
| forma do `summary` da door 12 (4) - verified at 81d160e | `plan.md:101`: prefixo, caminhos relativos, ordenados, até 5, `(+N more)` | prefixo e caminhos relativos: C64 `:349`, C65 `:363`; ordenação: C65 (links criados fora de ordem, `gbfaecd`; M10 morto); corte em 5 e `(+N more)`: C65 (7 links, `(+2 more)`; M11 morto) | - |
| diretório de trabalho do agente de plugin (2) - verified at 81d160e | `run.py:257-260` e door 13 (`plan.md:102`) | com `repo`, o clone: C27 `:148`, C36 `:188`; sem `repo`, `work/` vazio: C66 `:378-383` (fake) e C67 `:258` (CLIs reais), mais as sondas 1-7 | - |
| efeitos da door 13 sem `repo` (6) - verified at 81d160e | `plan.md:102`, AC 72 | `cwd`: C66 `:378`; `PWD`: C66 `:378` (M15 morto); `work/` criado e vazio: C66 `:379-380`; `{workspace}`: C66 `:381`; `meta.json` `cwd`: C66 `:382`; linha do `kit.log` com `--cwd` e sem ela: C66 `:385`, `:393` (M14 morto), C67 `:259` | - |
| doors do plano (13) - verified at 81d160e | `plan.md` Landing (`:89-102`) | 1-11 como na rodada 6. 12: C64, C65. 13: C66, C67 | - |
| matriz CLIs × capacidades (15) - verified at ae59fbe | `assets/capabilities.json`, `spike.md` | C1/C8 sobre as 15. Imposição nas duas CLIs, no host de dev (opencode 2.1.3 e 1.19.3) e no box (opencode 1.19.3): `write` C2, C61, C62, C67 (e as sondas 1-5, só no host de dev); `commands` C3; `workspace_config` C4 (M16 morto); `skills` C5 (ramo `id` no 2.1.3, ramo `name` no 1.19.3, F7 morto) | - |
| symlinks no clone (3) - carried from 4ac3c27 | o que o git guarda num symlink e a door 12 | alvo absoluto fora: C64, C65; relativo fora: C64; interno: C64 | - |
| `--output` de comando liberado (4) - verified at 81d160e | AC 70 | as 4 formas: C62 `:240`, nas duas CLIs, em árvore limpa | - |
| escapes do shell por prefixo liberado (7) - carried from 4ac3c27 | o shell | C61 (re-run em 81d160e, verde nas duas CLIs) | - |
| bloco de ambiente: variações (2) - carried from bf98604 | door 9 e `environment()` | C60, C27, C31 | - |
| variáveis do prompt (4) - verified at 81d160e | door 2; `{workspace}` mudou de sentido sem `repo` | C27 (com `repo`), C31; `{workspace}` sem `repo`: C66 `:381` | - |
| plugins próprios (2) - verified at ae59fbe | plan S5/S6 | `code-review`: C47, C48 (CI), C49 e C50 no box (posta e re-revisa, confirmado no GitHub); `bug-verify`: C51, C52 (CI), C49 e C53 no box (reproduz) | - |
| recusas do manifesto e do layout - carried from bf98604 | código (`PluginError(` em `plugin.py`) | C18, C19 | - |
| webhook statuses (3) - carried from 7a6d41b | plan Surface + `sinks.py` | C59 | - |
| saídas de `plugin list`/`show`/`add`/`rm` - carried from 7a6d41b | plan Surface | C9-C26 | - |
| recusas do `run --plugin` (exit 2) - verified at 81d160e | AC 27-32 | C29, C30, C32, C33 (`--cwd` com `repo` segue recusado), C34 | - |
| `kind` (3), URLs da door 7 (6), `source` (3) - carried from 7a6d41b | doors 2, 7, 3 | C27-C31; C9, C14, C17 | - |
| predicado de tarefa rodando (7) - carried from 7a6d41b | AC 25 | C25 | - |
| resultado inválido (5) + precedência (7) - carried from 7a6d41b | AC 43-45 | C42, C43, C44 | - |

## Test policy rows

As linhas vêm de `docs/.specs/features/agent-run-notify/checks.md`. Rodada 8: julguei de novo a de integração, que era a
única não atendida. O diff não toca em `src/`, então as outras são carried from 81d160e.

| Row | Files it classifies | Required proof | Expectation met |
| --- | --- | --- | --- |
| Decides, reached across a boundary (carried from bf98604) | `plugin.py` regras do manifesto e `environment()` | C19, C27, C31, C60 · `manifest_rules` | yes |
| Decides, reached across a boundary (carried from 7a6d41b) | `plugin.py` predicado de tarefa rodando | C25 · C26 | yes |
| Decides, reached across a boundary (carried from 4ac3c27) | `launch.py` `plugin_harness` (doors 10 e 11) | C36 · C61, C62, C2 | yes; o C2 voltou a passar, e a door 13 fechou a escrita pelo cwd de quem chama |
| Decides, reached across a boundary (re-judged at 81d160e) | `run.py` `_links_outside` (door 12) | C64, C65, na fronteira (subprocesso `grokbot-kit run`, `gh` falso, CLI falsa) | yes: decisão (M7, M8) e forma do `summary` (M10, M11) provadas |
| Decides, reached across a boundary (re-judged at 81d160e) | `run.py` `_prepare_plugin` e `run` (door 13) | C66 na fronteira (CLI falsa) · C67 com as CLIs reais | yes: M13, M14 e M15 mortos pelo C66, e M13 morto pelo C67 do opencode |
| Decides, reached across a boundary (carried from 7a6d41b) | `terminal.py` classificação de plugin | C43/C44 · C42, C44 | yes |
| Entry point that does not decide (re-judged at 81d160e) | `run.py` validação de entradas e montagem do prompt | C29-C35, C60 | yes |
| Instrumentation, pass-through (carried from 7a6d41b) | `doctor.py` plugins | C58 | yes |
| Integration with a real CLI or GitHub (re-judged at 81d160e) | `-m integration`: `test_plugin_caps.py`, `test_builtin_plugins.py` | `-m integration` no box, uma vez por CLI | yes (re-judged at ae59fbe): `0.4.1-pytest.log` com C2-C5, C37, C49, C53, C61, C62 e C67 verdes para claude e opencode 1.19.3 (Codex e `network` pulados pela matriz); C50 verde em `0.4.1-c50.log` e confirmado pelo GitHub |

Linha `existing` do Swept (ciclo de vida dos dados), carried from 7a6d41b: `gc` apaga o task dir inteiro em
`src/grokbot_kit/gc.py:35`. Isso cobre também o `work/` vazio que a door 13 cria.

## Faults injected

Rodada 8 (verified at ae59fbe). O diff não toca em `src/`. A única superfície de teste com um mutante pendente era o
ramo `name` do `skill_invoked` (F7). A mudança do C50 (`-c` no `git commit`) não é injetável sem postar no GitHub, e
fica fora. Isolei numa worktree scratch (`git worktree add --detach <scratchpad>/mut-r8 HEAD`, venv própria). Mostrei o
mutante com `git diff -U0` e depois reverti com `git checkout -- tests`. A scratch foi removida com
`git worktree remove --force` e `git worktree prune`. A porcelain da worktree real estava vazia antes e continuou vazia
depois. Prova mais estreita: `-m integration tests/integration/test_plugin_caps.py -k "plugin_skill_loaded and
opencode"`, com o `opencode` 1.19.3 (`npm install opencode-ai@1.19.3` numa pasta scratch) à frente do `PATH`.

Rodada 7 (carried from 81d160e). Superfícies novas ou tocadas: a forma do `summary` (`run.py:321-323`, contra o C65) e a
door 13 (`run.py:257-260`, `:346`, `:373`, `:398-399`, contra C66 e C67). Também re-injetei uma falha no C4, que agora
recebe o workspace pelo clone. Tudo rodou numa worktree scratch (`git worktree add --detach <scratchpad>/mut-r7 HEAD`,
com venv própria). Antes de cada execução mostrei o mutante com `git diff -U0 -- src`, e depois reverti com
`git checkout -- src` e conferi o diff vazio. A scratch foi removida com `git worktree remove --force` (o arquivo de sonda
era o único não rastreado) e `git worktree prune`. A porcelain da worktree real estava vazia antes e continuou vazia
depois. Prova mais estreita: `uv run pytest tests/test_run_plugin.py -k symlink` (M10, M11),
`tests/test_run_plugin.py tests/test_plugin.py` (M13, M14), `-k "without_repo or launches_in_clone"` (M15), e
`-m integration ... -k "caller_cwd and opencode"` / `-k "workspace_config and opencode"` (M13 e M16 com o opencode real).

| Mutation | Location | Killed |
| --- | --- | --- |
| M10 - sem `found.sort()` (vira `pass`) | `src/grokbot_kit/run.py:321` | yes - C65 `test_symlink_summary_shape` falhou em `:363` (`a, b, f, d, e (+2 more)`); o C64 seguiu verde |
| M11 - corte em 6 e `(+N more)` só acima de 99 | `src/grokbot_kit/run.py:322-323` | yes - C65 falhou em `:363` (`a, b, c, d, e, f`, sem `(+N more)`) |
| M13 - agente de plugin sem `repo` de volta no cwd de quem chamou (`cwd = cwd if task["target"] else r["cwd"]` depois de `_prepare_plugin`) | `src/grokbot_kit/run.py:346` | yes - C66 falhou em `:378` (`cwd` = `<tmp>/chamador`; 1 failed, 82 passed). Com o opencode real, C67 `[opencode]` falhou em `:258` com `['fora-cwd.txt']` |
| M14 - sem a linha `--cwd ignored` no `kit.log` | `src/grokbot_kit/run.py:399` | yes - C66 falhou em `:385` (1 failed, 82 passed) |
| M15 - sem `"PWD": str(cwd)` no env do agente (o `PWD` herdado) | `src/grokbot_kit/run.py:373` | yes - C66 falhou em `:378` |
| M16 - sem `OPENCODE_DISABLE_PROJECT_CONFIG` | `src/grokbot_kit/launch.py:99` | yes - C4 `test_workspace_config_ignored[opencode]` falhou em `:289`: o MCP do `opencode.json` clonado criou o marcador. O C4 por clone discrimina |
| (rodada 6, carried from 4ac3c27) M7, M8 - door 12 | `run.py:308`, `:314` | yes - C64 |
| (rodada 6, carried from 4ac3c27) M9 - sem o filtro de `.git` | `run.py:311` | equivalente para entrada alcançável: um clone por `gh`/`git` não tem symlink em `.git/`. Fora da contagem, como na rodada 6 |
| (rodada 6, carried from 4ac3c27) M12 - frase da grafia | guias | yes - C63 |
| (rodada 5, carried from f69d5e3) M3-M6 - door 11 e frase do contrato | `launch.py:70`, `:83-88`; guias | yes - C36, C62, C63 |
| (rodada 4, carried from d8ffbe2) M1, M2 - door 10 | `launch.py` | yes - C36 e C61 |
| (rodada 3, carried from bf98604) F1-F6 | `plugin.py`, `test_plugin_caps.py` | yes |
| F7 - `skill_invoked` sem o ramo `name` (`(skill.get("id"),)`) | `tests/integration/test_plugin_caps.py:113` | yes - com o opencode 1.19.3, `test_plugin_skill_loaded[opencode]` falhou em `:301` (`AssertionError: a palavra veio sem a CLI carregar a skill`), depois de a palavra chegar (`:300` passou); sem o mutante, PASSED. O evento do 1.19.3 tem `input: {"name": "spike"}` |

## Gate

At ae59fbe:
`uv run pytest -q -rA` (suíte completa, markers padrão): 763 passed, 48 deselected, 0 failed.
`uv run ruff check src tests`: All checks passed. `uv run ruff format --check src tests`: 71 files already formatted. `uv run mypy`: no issues found in 22 source files.
`uv run pytest -m integration tests/integration/test_plugin_caps.py -k opencode` (host de dev, opencode 1.19.3, `opencode/glm-5.3-flash-free`): 7 passed, 1 skipped, exit 0.
Box (evidência do bot, tag `v0.4.1` = `cdf3c25`, mesmo `src/` de `HEAD`): `0.4.1-pytest.log` 18 passed, 10 skipped, 1 failed (identidade git do C50); `0.4.1-c50.log` 1 passed.

## Ranked gaps

Nenhum gap aberto. Notas fora do veredito:

1. **Resolvido nesta rodada: C50 e C53 no box.** Provados pelos logs do bot, e o C50 também pelo GitHub (reviews
   5683162673 e 5683173344, commit `f91b175`).
2. **Resolvido nesta rodada: F7.** Morto com o opencode 1.19.3, e o ramo `name` casou no box.
3. **Resolvido nesta rodada: a linha de integração do `Test policy`.**
4. **Proveniência (nota).** Os logs do box são o que o bot devolveu, sem como reproduzi-los daqui. Faltam neles a
   versão do `claude` e o modelo do claude (o `STATE.md` diz `sonnet`; o `box/README.md` não diz). O C50 rodou no box
   com o código de teste da tag mais a identidade pelo ambiente, e não com o `-c` de `HEAD`. A identidade no commit do
   GitHub é a mesma do `-c`.
5. **Nota sobre o fixture.** O PR 1 do `grokbot-kit-fixtures` acumula cópias `c50_*.py` de runs anteriores (quatro
   arquivos com a mesma `media`), e o summary do review 5683162673 repete palavra por palavra o do 5680620067 ("sem
   commits novos"), embora os comentários inline mudem. O claim do C50 segue provado, porque as asserções olham os
   `findings`. Mesmo assim, vale limpar o PR antes da próxima rodada, para que o "achado no arquivo novo" não se
   confunda com duplicatas.
6. **`STATE.md` desatualizado (nota).** A linha `**Branch**:` ainda diz `fix/plugins/provas-box`. A branch desta
   rodada é `test/plugins/provas-fechadas`.
7. **Precisão (carried from 81d160e): `--cwd` "ignorado" ainda é validado.** Num plugin sem `repo`, um `--cwd` que não
   é diretório sai com `2` (`run.py:132-134`) antes da door 13. A door 13 e os guias dizem "ignored", e nenhum check
   cobre o caso.
8. **Precisão (carried from 81d160e).** "contorna a regra." no singular, para duas regras
   (`docs/pt-BR/plugins.md:101-102`).
9. **Observação (carried from 4ac3c27).** `"*>*"` também nega comando legítimo com `>` dentro de aspas. Os operadores
   `||`, `&`, crase e `<(...)` estão negados, mas sem check.
