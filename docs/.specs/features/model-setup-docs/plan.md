# model-setup-docs

## Problem

O setup escolhe os modelos das tarefas por uma regra fixa, sem perguntar nada ao usuário. A skill descobre os ids
com `grokbot-kit setup models refresh` e propõe os tiers pondo os ids `-free` do opencode primeiro em `trivial` e
`standard` (AC 109 da agent-run-notify); o usuário só confirma ou não a tabela. O opencode expõe vários provedores na
mesma lista (`opencode models` no host de dev, opencode 2.1.3, em 28/10/2026: 65 ids `opencode/`, 30 `opencode-go/`,
83 `openai/`, 29 `google/`, 3 `ollama/`), e nada no kit nem na skill separa os ids por provedor ou pergunta qual o
usuário paga. Quem paga é o dono do bot com assinatura: no box do Rodrigo, que assina o opencode-go, o tier
`standard` ficou com `opencode/nemotron-3-ultra-free` primeiro, e o `code-review` no PR 118 do `radar`
(28/10/2026, task `20261028T174423-review-opencode-25b819`) morreu em 2 s com
`UnknownError: Unexpected server error` do provedor; com um id do opencode-go o mesmo review funcionou.

Quando o provedor recusa a chamada, o kit também não tenta outro modelo: usa só o primeiro id do tier
(`resolve.py:52`), e o evento chega com `summary` vazio, porque o `summary` do opencode só lê partes `text`
(`terminal.py:57-61`) e a mensagem do `type: error` se perde. O bot recebe `agent_error` sem motivo.

A documentação para quem usa o kit ficou atrás do código. O `README.md` e o `docs/pt-BR/README.md` não citam
`plugin`, `run --plugin`, `update`, `redeliver`, `setup models refresh` nem `setup tiers` (0 ocorrências em cada,
contadas em 28/10/2026), e não linkam o `docs/plugins.md`; o `CONTRIBUTING.md` existe só em pt-BR, contra a regra de
idioma do `CLAUDE.md` (AD-041). Nada no processo pega isso: o PR template cobra só o `CHANGELOG.md`, e nenhum teste
compara os comandos do `--help` com o README. O projeto é open source; quem chega pelo README não descobre metade
do que o kit faz.

Quando isto sai: no setup, o bot mostra os provedores do opencode com a contagem de modelos e pergunta quais o usuário
usa; propõe cada tier só com ids desses provedores e o usuário escolhe; uma falha do provedor antes de o agente agir
faz o kit tentar o próximo id do tier, e uma falha final chega com o motivo no `summary`. O README mostra todos os
comandos e os plugins, nas duas línguas, e o CI quebra quando um comando novo entra sem doc.

## Flow

Reusa o que existe: a descoberta de `models.py` (o prefixo do provedor já vem no id), o `setup tiers` de `setup.py`
(door 22 da agent-run-notify), a leitura de erro de `terminal.read_output`, o `_supervise` de `run.py` para cada
tentativa, o `doctor --json` (door 21) e o estilo de prova de documento de `tests/test_skill_doc.py`.

1. a skill roda `grokbot-kit setup models refresh --json` -> `models.py` (exists) imprime o objeto da door 1, com o
   `provider` de cada id
2. a skill pergunta os provedores do opencode e roda o comando da door 2 -> `setup.py` (exists) grava `[cli.opencode] providers` (door 2)
3. a skill propõe cada tier só com ids desses provedores, o usuário escolhe, e `setup tiers` (exists) grava, recusando
   id de provedor fora da lista (door 3)
4. `doctor.py` (exists) mostra `cli.opencode.providers` e acusa id de tier fora dos provedores (door 3)
5. na tarefa, `run.py` (exists) lança o primeiro id do tier; `terminal.py` (exists) diz se a tentativa falhou no
   provedor antes de qualquer ferramenta (door 4); se falhou e há próximo id, `run.py` guarda a saída da tentativa
   (door 5) e lança o próximo
6. out: um evento terminal com `model` = o último id lançado, `model_fallbacks` (door 5) e, em erro, o motivo no
   `summary` (door 6)
7. `README.md`, `docs/pt-BR/README.md`, `CONTRIBUTING.md` e `docs/pt-BR/CONTRIBUTING.md` (exists ou criados) ganham
   comandos e plugins; `tests/test_docs.py` (door 7) compara o `--help` com os dois READMEs no CI

## Impact

| Front | What changes |
| --- | --- |
| domain | novo termo: `provider` - o prefixo antes do primeiro `/` de um id do opencode (`opencode-go` em `opencode-go/glm-5.3`); vive em `models.py`; nas outras CLIs é `null` |
| domain | `model` no evento passa a ser o último id lançado, que pode não ser o primeiro do tier - quem lê `model` hoje: a skill, que só o repete ao usuário |
| domain | AC 109 da agent-run-notify (gratuitos primeiro em `trivial`/`standard`) vale só quando os provedores escolhidos são só `opencode`; supersedida em parte por uma AD nova; AD-034 (gratuito = sufixo `-free`) segue |
| skill | o passo 5 do Setup ganha a pergunta de provedores e a escolha por tier; quem tem a skill velha segue com a regra antiga até o `update apply` baixar a nova (AD-036) |
| stored data | `[cli.opencode] providers` é opcional; configs existentes sem ele continuam válidos e sem restrição de provedor; nada migra |
| task dir | tentativas que caíram no provedor deixam `out.<n>.jsonl` e `stderr.<n>.log`; `out.jsonl` e `stderr.log` continuam sendo da última tentativa, como hoje |
| docs | `docs/SPEC.md` (cópia local gerada, já no `.gitignore`) é apagado e sai do `CLAUDE.md`; a linha do `.gitignore` fica (C20 da agent-run-notify) |

## Relations

`[cli.opencode] providers` (lista ordenada de provedores) restringe `[cli.opencode.tiers]`: com o campo presente, todo
id de tier tem o `provider` na lista (door 3). Sem o campo, nenhuma restrição.

## Surface

O corpo que a routine recebe muda (aditivo, AD-006); a rota e os status da entrega são os da door 3 da
agent-run-notify:

| Route | In | Out | Status |
| --- | --- | --- | --- |
| `POST <webhook da routine>` (sink `grokbot-routine`, existe) | corpo `grokbot-kit.event/v1` com o campo novo `model_fallbacks` e o `summary` da door 6 | (o de hoje) | `200` entregue; `401` e demais `4xx` falha sem retry; `429` e `500`-`599` retry (os de hoje) |

Comandos (exit codes):

| Comando | In | Out | Exit |
| --- | --- | --- | --- |
| `grokbot-kit setup models refresh [<tool>] --json` | `--json` (novo; sem ele, a saída de hoje) | objeto da door 1 em stdout | `0`, `1`, `2` (os de hoje) |
| `grokbot-kit setup providers opencode <provider> [<provider>...]` (door 2) | provedores, na ordem | uma linha `opencode providers: <p>, <p>`; avisos em stderr | `0`, `2` |
| `grokbot-kit setup tiers opencode <tier> <id>...` | (existe) | (existe) | `0`, `2` (nova recusa da door 3) |
| `grokbot-kit doctor --json` | (existe) | `cli.opencode.providers` (lista ou `null`); problema novo da door 3 | `0`, `1` |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. saída `--json` do `setup models refresh` (a skill lê) | `{"models": [{"tool": "opencode", "id": "opencode-go/glm-5.3", "provider": "opencode-go"}, {"tool": "claude", "id": "sonnet", "provider": null}]}`, na ordem da descoberta; `provider` = texto antes do primeiro `/` no opencode, `null` no `claude` e no `codex`; com `--json` nenhuma linha `<tool>\t<id>` em stdout; avisos e erros seguem em stderr | provedores de `opencode auth list` - mostra nomes de exibição (`OpenCode Console`, `Google`) que não batem com os prefixos dos ids, e o formato mudou da 1.19 (linha `<n> credentials`) para a 2.1.3 (uma linha por credencial, sem total); a skill agrupar o texto `<tool>\t<id>` - o bot erra parse de texto, e o prefixo seria regra repetida na skill |
| 2. comando e campo de provedores | `grokbot-kit setup providers opencode <provider> [<provider>...]` grava `[cli.opencode] providers = ["opencode-go", ...]` na ordem dada, sem tocar outros campos; `2` quando a tool não é `opencode` ("providers apply only to opencode"), quando `opencode` não está em `setup.installed` (citando `grokbot-kit setup cli add opencode`) ou quando um provedor não é prefixo de nenhum id em `[cli.opencode] models` (citando o provedor e `grokbot-kit setup models refresh opencode`); `0` e uma linha em stdout | filtrar só nos tiers, sem gravar a escolha - a próxima proposta de tiers (troca de modelo, `refresh`) perguntaria tudo de novo; a skill escrever o TOML - rejeitado pela door 16 da agent-run-notify |
| 3. restrição de provedor | com `providers` presente: `setup tiers opencode` sai com `2`, sem mudar o config, para id cujo provider não está na lista (citando o id e `grokbot-kit setup providers opencode`); `setup providers` grava mesmo com tier fora e avisa em stderr cada `cli.opencode.tiers.<tier>` com id fora; o `doctor` põe em `problems` `cli.opencode.tiers.<tier> has <id>, whose provider is not in cli.opencode.providers; run: grokbot-kit setup tiers opencode <tier> ...`; `config.load()` não valida (o `run` não recusa) | validar no `config.load()` como as constraints da door 3 - trocar de provedor exigiria uma ordem exata de comandos, e um passo esquecido derrubaria todo `run`; `setup providers` recusar com tier fora - a troca de `opencode` para `opencode-go` não teria ordem que funcione |
| 4. falha de provedor antes de ferramenta | tentativa elegível ao fallback quando não houve timeout nem interrupção e: `opencode` - `out.jsonl` tem objeto `type` `error` e nenhum `type` `tool_use`; `claude` - o `result` tem `is_error` `true`, `terminal_reason` `api_error` e `num_turns` ≤ 1; `codex` - nunca | tentar de novo em todo `agent_error` - um agente que já editou arquivos ou postou no GitHub repetiria efeitos; usar o exit code - o `claude` sai com `0` em `api_error` (observado com modelo inválido no `claude` do host de dev, 28/10/2026); incluir o `codex` - nenhuma saída de erro de provedor dele foi observada, e ele não roda plugin nem está no box |
| 5. tentativas no evento e no task dir | só com `model_source` `tier`: o próximo id do mesmo tier, na ordem, até acabar a lista; antes de cada nova tentativa `out.jsonl` -> `out.<n>.jsonl` e `stderr.log` -> `stderr.<n>.log` (`n` = 1, 2, ...) e uma linha no `kit.log`: `model <id> failed at the provider before any tool call (<motivo>); trying <próximo>`; o `meta.json` e o evento trazem `model` = o último id lançado e `model_fallbacks` = `[{"model": "<id>", "error": "<motivo>"}]` (vazio sem fallback, presente em todo evento terminal); todas as tentativas dividem o mesmo `timeout_seconds`, contado do `started_at` | um campo só com a contagem - o bot não saberia qual modelo falhou para propor trocar o tier; uma task nova por tentativa - dois `task_id` para um pedido e duas entregas |
| 6. motivo no `summary` | com `output.error` e `summary` vazio: `opencode` - `<error.name ou error.type>: <error.data.message ou error.message>` do último objeto `type` `error` (só a parte que existir); `codex` - `error.message` do último `turn.failed`, ou `message` do último `error`; `claude` - o `result` de hoje; sempre cortado em 2000 caracteres (AD-015) | um campo novo `error` no evento - a skill já conta o `summary` ao usuário; dois campos com o mesmo texto |
| 7. prova da doc no CI | `tests/test_docs.py`, no `uv run pytest` padrão: cada subcomando de topo do parser de `grokbot-kit` aparece como `grokbot-kit <subcomando>` no `README.md` e no `docs/pt-BR/README.md`; todo `README.md`, `CONTRIBUTING.md` e `docs/*.md` tem o par em `docs/pt-BR/<mesmo nome>` e os dois linkam um ao outro nas 5 primeiras linhas | lista fixa de comandos no teste - um comando novo passaria sem doc, que é o furo de hoje; checagem só no PR template - depende de alguém lembrar, como hoje |

- Nada mais aqui é difícil de reverter: textos da skill e do README, a redação das mensagens e a ordem das seções
  mudam num commit.

## Criteria

### S1: o kit mostra e grava os provedores do opencode (P1)

O setup sabe de que provedor é cada id e guarda quais o usuário escolheu.

**Acceptance Criteria**

1. WHEN `grokbot-kit setup models refresh --json` roda THEN o kit SHALL imprimir em stdout só o objeto da door 1, com um item por id descoberto de cada tool, e sair com o mesmo código da saída sem `--json`
2. The item de um id do opencode SHALL ter `provider` igual ao texto antes do primeiro `/` do id, e o de um id do `claude` ou do `codex` SHALL ter `provider` `null`
3. WHEN `grokbot-kit setup models refresh` roda sem `--json` THEN o kit SHALL imprimir as linhas `<tool>\t<id>` de hoje, sem mudança
4. WHEN `grokbot-kit setup providers opencode opencode-go` roda com `opencode` em `setup.installed` e um id `opencode-go/...` em `[cli.opencode] models` THEN o kit SHALL gravar `[cli.opencode] providers = ["opencode-go"]`, imprimir `opencode providers: opencode-go` e sair com `0`
5. IF a tool de `setup providers` não é `opencode` THEN o kit SHALL sair com `2` com `providers apply only to opencode` em stderr, sem mudar o config
6. IF `opencode` não está em `setup.installed` THEN o `setup providers` SHALL sair com `2` citando `grokbot-kit setup cli add opencode`, sem mudar o config
7. IF um provedor dado não é prefixo de nenhum id em `[cli.opencode] models` THEN o `setup providers` SHALL sair com `2` citando o provedor e `grokbot-kit setup models refresh opencode`, sem mudar o config
8. WHILE `[cli.opencode] providers` está presente, IF `setup tiers opencode <tier>` recebe um id cujo provider não está na lista THEN o kit SHALL sair com `2` citando o id e `grokbot-kit setup providers opencode`, sem mudar o config
9. WHILE `[cli.opencode] providers` está ausente the `setup tiers opencode` SHALL aceitar qualquer id descoberto, como hoje
10. WHEN `setup providers` grava uma lista que deixa algum id de `[cli.opencode.tiers]` fora THEN o kit SHALL gravar e avisar em stderr cada `cli.opencode.tiers.<tier>` com o id fora
11. The `doctor --json` SHALL trazer `cli.opencode.providers` com a lista gravada, ou `null` sem o campo
12. WHILE algum id de `[cli.opencode.tiers]` tem provider fora de `providers` the `doctor` SHALL pôr em `problems` a linha da door 3 e sair com `1`
13. The `config.load()` SHALL não recusar um config com id de tier fora de `providers` (o `run` segue)

**Independent test:** com um `opencode` falso que lista `opencode/a-free` e `opencode-go/b`, `setup models refresh --json` traz os dois provedores; `setup providers opencode opencode-go` grava; `setup tiers opencode standard opencode/a-free` sai com `2`.

### S2: o bot pergunta provedores e modelos (P1)

O setup do bot pergunta, em vez de aplicar a regra dos gratuitos sozinho.

**Acceptance Criteria**

14. The `SKILL.md` SHALL mandar descobrir os modelos com `grokbot-kit setup models refresh --json` no passo 5 do Setup
15. WHEN o `opencode` está em `setup.installed` THEN o `SKILL.md` SHALL mandar fazer uma única pergunta de múltipla escolha com os provedores do opencode lidos do campo `provider`, cada um com a contagem de ids dele, e gravar a escolha com `grokbot-kit setup providers opencode <provider>...`
16. The `SKILL.md` SHALL dizer que um provedor pago precisa de login no opencode antes do uso (`grokbot-kit login opencode`)
17. WHEN os provedores estão gravados THEN o `SKILL.md` SHALL mandar, para cada tier (`trivial`, `standard`, `complex`) de cada CLI, uma pergunta com até 4 ids da lista descoberta (no opencode, só dos provedores escolhidos), com o recomendado primeiro, e gravar a escolha com `grokbot-kit setup tiers`
18. WHERE os provedores escolhidos são só `opencode` the `SKILL.md` SHALL recomendar os ids `-free` primeiro em `trivial` e `standard`, como o AC 109 da agent-run-notify
19. WHERE algum provedor escolhido não é `opencode` the `SKILL.md` SHALL recomendar ids desse provedor primeiro em todos os tiers
20. The `SKILL.md` SHALL mandar refazer os passos de provedores e tiers quando o usuário pede para trocar os modelos, sem refazer instalação, login nem routine
21. The `SKILL.md` SHALL continuar sem id de modelo literal, sem `curl` e sem comando ou flag fora do `--help` do `grokbot-kit` (AC 119 da agent-run-notify)

**Independent test:** `tests/test_skill_doc.py` acha `setup models refresh --json`, a pergunta de provedores com `setup providers opencode`, a pergunta por tier e a regra dos gratuitos condicionada aos provedores.

### S3: o erro do agente chega com o motivo (P1)

**Acceptance Criteria**

22. WHEN uma tarefa do opencode termina com um objeto `type` `error` em `out.jsonl` e nenhuma parte `text` THEN o evento SHALL ter `summary` = `<error.name>: <error.data.message>` (formato 1.19) ou `<error.type>: <error.message>` (formato 2.x), com só a parte que existir
23. WHEN uma tarefa do codex termina com `turn.failed` ou `error` e `last-message.txt` vazio ou ausente THEN o evento SHALL ter `summary` = a mensagem do último desses objetos
24. WHEN a saída do agente tem erro e também texto final do agente THEN o `summary` SHALL ser o texto final, como hoje
25. The `summary` derivado do erro SHALL ter no máximo 2000 caracteres

**Independent test:** com um `opencode` falso que imprime `{"type":"error","error":{"name":"UnknownError","data":{"message":"Unexpected server error"}}}`, o evento chega com `summary` `UnknownError: Unexpected server error`.

### S4: o kit tenta o próximo modelo do tier quando o provedor falha (P1)

**Acceptance Criteria**

26. WHEN a tentativa com o id `n` de um tier é elegível pela door 4 e o tier tem id depois dele THEN o `run` SHALL lançar o próximo id na mesma task, no mesmo cwd e com o mesmo prompt
27. WHEN o `run` vai lançar outra tentativa THEN o kit SHALL renomear `out.jsonl` para `out.<n>.jsonl` e `stderr.log` para `stderr.<n>.log` e gravar no `kit.log` a linha da door 5
28. The evento terminal SHALL ter `model` = o último id lançado e `model_fallbacks` = um item `{"model", "error"}` por tentativa elegível que levou a outra, na ordem, com `error` = o `summary` da door 6 daquela tentativa
29. The evento terminal SHALL ter `model_fallbacks` `[]` quando nenhuma tentativa levou a outra
30. IF o modelo veio de `--model` (`model_source` `explicit`) THEN o `run` SHALL não tentar outro id
31. IF a tentativa falhou depois de uma ferramenta (opencode com `tool_use`; claude com `num_turns` > 1 ou `terminal_reason` diferente de `api_error`) THEN o `run` SHALL não tentar outro id
32. IF todas as tentativas do tier são elegíveis THEN o evento SHALL ser `error`/`failed`/`agent_error` com o `summary` da última e `model_fallbacks` com todas menos a última
33. WHILE há tentativas, the `run` SHALL aplicar um único prazo de `timeout_seconds` contado do `started_at`, e o timeout numa tentativa SHALL terminar a task como `timeout` sem tentar outro id
34. The `codex` SHALL nunca ter tentativa elegível
35. WHERE a task é de plugin the fallback SHALL valer igual, com o clone de `<task_dir>/work` reaproveitado sem clonar de novo

**Independent test:** com um `opencode` falso que falha com `type: error` no primeiro id e responde texto no segundo, `run --tier standard` com dois ids termina `completed`/`ok`, com `model` = o segundo, `model_fallbacks` com o primeiro e `out.1.jsonl` no task dir.

### S5: a doc mostra o kit inteiro, nas duas línguas (P1)

**Acceptance Criteria**

36. The `README.md` e o `docs/pt-BR/README.md` SHALL ter uma seção de comandos com uma linha por subcomando de topo do `grokbot-kit --help` (13 em 28/10/2026), cada um escrito como `grokbot-kit <subcomando>`
37. The `README.md` e o `docs/pt-BR/README.md` SHALL ter uma seção de plugins com o que é um plugin, o comando `grokbot-kit run --plugin code-review --input pr=<url> --target <bot> --label review` e o link para `docs/plugins.md` (`docs/pt-BR/plugins.md` na versão pt-BR)
38. The `README.md` e o `docs/pt-BR/README.md` SHALL descrever a escolha de provedores e modelos do setup e o fallback de modelo do tier
39. The repositório SHALL ter `CONTRIBUTING.md` em inglês e `docs/pt-BR/CONTRIBUTING.md` com o conteúdo do `CONTRIBUTING.md` de hoje, cada um com o link para o outro logo abaixo do título
40. The `docs/SPEC.md` SHALL não existir, e o `CLAUDE.md` SHALL não citá-lo
41. The `CHANGELOG.md` SHALL ter, sob `## [Unreleased]`, o `setup providers`, o `--json` do `refresh`, o `model_fallbacks` e o `summary` de erro

**Independent test:** `grep -c "grokbot-kit plugin" README.md docs/pt-BR/README.md` dá ≥ 1 em cada; `ls docs/pt-BR/CONTRIBUTING.md` existe; `ls docs/SPEC.md` falha.

### S6: o CI quebra quando a doc fica para trás (P1)

**Acceptance Criteria**

42. WHEN um subcomando de topo do parser não aparece como `grokbot-kit <subcomando>` no `README.md` ou no `docs/pt-BR/README.md` THEN o `uv run pytest` SHALL falhar citando o subcomando e o arquivo
43. WHEN um `README.md`, `CONTRIBUTING.md` ou `docs/*.md` não tem o par em `docs/pt-BR/` com o mesmo nome THEN o `uv run pytest` SHALL falhar citando o arquivo
44. WHEN um par não linka o outro nas 5 primeiras linhas THEN o `uv run pytest` SHALL falhar citando o arquivo
45. The `CLAUDE.md` SHALL ter a regra: mudança de comportamento visível (comando, flag, config, evento, plugin) atualiza o `README.md` e o doc do tema nas duas línguas no mesmo PR, e o plano de cada feature tem critério de doc
46. The `.github/pull_request_template.md` SHALL ter o item `README.md` e docs atualizados em inglês e pt-BR quando o comportamento visível mudou

**Independent test:** apagar a linha de `grokbot-kit redeliver` do `docs/pt-BR/README.md` faz `uv run pytest tests/test_docs.py` falhar citando `redeliver` e o arquivo.

## Out of scope

| Excluded | Why |
| --- | --- |
| testar cada provedor com uma chamada real no setup | cada chamada gasta cota do provedor; o fallback da S4 cobre o provedor que falha no `run` |
| provedores no `claude` e no `codex` | as duas CLIs têm um provedor cada no kit; `provider` fica `null` |
| fallback no `codex` | nenhuma saída de erro de provedor dele foi observada; ele não roda plugin nem está no box |
| fallback entre tiers ou entre CLIs | o usuário escolheu os ids do tier; trocar de tier ou de CLI muda custo e capacidade sem pedido |
| gerar de novo o `docs/SPEC.md` | decisão do Rodrigo em 28/10/2026: apagar |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| uma feature só, com setup, erro, fallback, docs e processo | uma feature, seis slices | decisão do Rodrigo em 28/10/2026 | y |
| fallback de modelo | sim, só dentro do tier e só antes de ferramenta | decisão do Rodrigo em 28/10/2026; o limite "antes de ferramenta" evita repetir efeito | y |
| `claude` com `num_turns` ≤ 1 e `terminal_reason` `api_error` é falha antes de ferramenta | usar essa regra | observado com modelo inválido no `claude` do host de dev (28/10/2026); uma ferramenta exige um segundo turno | n |
| o opencode 1.19.3 do box grava `tool_use` como o 2.1.3 | usar `type` `tool_use` nas duas | observado no 2.1.3 (28/10/2026); a prova no box confere o 1.19.3 | y - o box está no 1.19.5, e o C36 passou nele em 29/10/2026 (`box/c36.md`) |
| a skill pergunta até 4 ids por tier | 4, o limite de opções de uma pergunta de múltipla escolha | o usuário pode digitar outro id da lista | n |

**Open questions:** none - all resolved or logged above.

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| command `setup models refresh --json` | output format | AC 1, AC 2 |
| command `setup models refresh` | flag default (sem `--json`) | AC 3 |
| command `setup models refresh --json` | exit codes, falha no meio | AC 1 (os códigos de hoje; uma tool que falha não entra e o resto sai) |
| command `setup providers` | output, verbosity | AC 4, AC 10 |
| command `setup providers` | exit codes | AC 4-7 |
| command `setup providers` | falha no meio | n/a - grava o config de uma vez por `config.save` (existe) ou não grava |
| command `setup tiers` | exit code novo | AC 8, AC 9 |
| command `doctor --json` | output format, exit code | AC 11, AC 12 |
| command `run` | output, exit codes | AC 26-35 (os exit codes do `run` não mudam) |
| webhook evento `grokbot-kit.event/v1` | response shape | AC 22-25, AC 28, AC 29 |
| webhook evento | versioning | existing - AD-006: campo aditivo em `0.x`, com entrada no `CHANGELOG.md` (AC 41) |
| webhook evento | rate limit | n/a - um evento terminal por task, como hoje |
| document `SKILL.md` | structure, what the reader does next | AC 14-21 |
| document `README.md` / `docs/pt-BR/README.md` | structure, depth, next step | AC 36-38 |
| document `CONTRIBUTING.md` | structure, tone | AC 39 (o conteúdo de hoje, traduzido) |
| document `CHANGELOG.md` | structure | AC 41 |

## Sources

- sessão de 28/10/2026 com o Rodrigo - assinatura do opencode-go, falha do `code-review` no PR 118 do `radar`, e as decisões: uma feature, fallback sim, apagar o `docs/SPEC.md`
- `docs/.specs/features/agent-run-notify/plan.md` - AC 109, doors 3, 16, 21 e 22
- `CLAUDE.md` - regra de idioma dos docs (AD-041)
