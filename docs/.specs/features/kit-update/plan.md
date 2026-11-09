# kit-update

## Problem

Um Grok Bot que instalou o kit fica para sempre na versão do dia da instalação. Nada no kit nem na skill consulta se
há release nova: o `doctor` mostra só a versão instalada e só roda no setup, e a skill só chama `uv tool install`
quando o comando não existe. Quem paga é o dono do bot, que não recebe as correções (a `0.2.1` mudou o fluxo de
segredos depois do vazamento de key do UAT; a `0.2.2` passou a conferir o plugin do opencode) sem ir ao GitHub
por conta própria. A cópia local do `SKILL.md` também envelhece: o bot só a baixa no quick start.

Atualizar também não é só trocar o pacote: o plugin do opencode é uma cópia do asset do kit em
`~/.config/opencode/plugins/grokbot-kit.ts` e o `SKILL.md` do bot é outra cópia; os dois ficam da versão antiga.

A fonte não traz números; a evidência é o histórico de releases (`0.1.0` a `0.2.2` em três dias, 19 a 21/10/2026).

Quando isto sai: ao ser usado para setup ou para delegar uma tarefa, o bot vê que há versão nova e pergunta, com
opções para clicar, se o usuário quer atualizar agora, depois ou pular aquela versão; escolhendo atualizar, o kit, o
plugin e a skill ficam na versão nova sem nenhum comando digitado pelo usuário.

## Flow

Reusa o que existe: o `doctor` (door 21) só ganha um campo, o `install opencode` (`opencode_plugin.install`) regrava o
plugin, `launch.kit_executable()` dá o executável, o `meta.json` do task dir (door 4 da agent-run-notify) diz quais
tarefas rodam, e a skill continua baixando o `SKILL.md` da URL `latest` do release (AD-032).

1. a skill, antes do setup ou de delegar, roda `grokbot-kit update check --json` -> `cli.py` (exists) despacha para
   `update.py` (door 1)
2. `update.py` lê `~/.grokbot-kit/update.json` (door 2); se o resultado guardado venceu, consulta o PyPI (door 3) e
   regrava o estado
3. out: o objeto JSON da door 4; com `ask` verdadeiro a skill faz uma pergunta de múltipla escolha
4. "Pular" -> `update skip`, "Agora não" -> `update later` (door 1) -> `update.py` só grava o estado da door 2
5. "Atualizar" -> `grokbot-kit update apply` -> `update.py` confere tarefas em `config.tasks_dir()` (exists), acha o
   instalador (door 5), roda o upgrade, e chama o executável novo (`launch.kit_executable()`, exists) para
   `install opencode` (`opencode_plugin`, exists) quando o plugin existe
6. a skill baixa de novo `/releases/latest/download/SKILL.md` (exists, AD-032) para o diretório de workflows e relê
7. `doctor.py` (exists) põe o mesmo objeto da door 4 em `kit.update`

## Impact

| Front | What changes |
| --- | --- |
| domain | novo termo: `update` - a checagem de release no PyPI e o upgrade do kit pelo instalador que o instalou; vive em `update.py` |
| domain | `doctor --json` ganha `kit.update`; `problems` e o exit code não mudam (versão velha não é problema a corrigir) - quem lê `kit` hoje: só a skill, que não usa o campo |
| skill | `SKILL.md` ganha a seção de atualização antes do Setup e da Tarefa; quem já tem a skill `0.2.x` não vê nada até baixar a skill nova uma vez (aviso no `CHANGELOG.md`) |
| stored data | arquivo novo `~/.grokbot-kit/update.json`; nada existente migra |
| tarefas rodando | `apply` recusa enquanto uma tarefa roda; tarefas paradas não são tocadas |

## Relations

None - nenhuma entidade nova com relação; o estado da door 2 é um arquivo único por usuário.

## Surface

Rota HTTP de saída (door 3):

| Route | In | Out | Status |
| --- | --- | --- | --- |
| `GET https://pypi.org/pypi/grokbot-kit/json` (ou `GROKBOT_KIT_PYPI_URL`) | `User-Agent: grokbot-kit/<versão>`, timeout 5 s | `{"info": {"version": "<X.Y.Z>"}, ...}` | `200` com `info.version` em `X.Y.Z` vira `latest`; `200` sem ele, qualquer outro status, timeout ou falha de conexão vira `error` (AC 5), sem retry |

Comandos sem contrato HTTP (exit codes):

| Comando | In | Out | Exit |
| --- | --- | --- | --- |
| `grokbot-kit update check [--json]` | `--json` (padrão: texto) | objeto da door 4 (JSON) ou uma linha de texto | `0` |
| `grokbot-kit update apply` | nada | linha `grokbot-kit <antiga> -> <nova>` ou `grokbot-kit <v> is the latest`; erro em stderr | `0`, `1`, `2` |
| `grokbot-kit update skip <version>` | versão `X.Y.Z` | `skipping grokbot-kit <version>` | `0`, `2` |
| `grokbot-kit update later` | nada | `asking again after <RFC 3339>` | `0` |
| `grokbot-kit doctor --json` | (existe) | campo novo `kit.update` com o objeto da door 4 | (existentes) |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. comandos `update` | `grokbot-kit update check [--json]`, `update apply`, `update skip <version>`, `update later`; exit `2` = recusa (tarefa rodando, instalador desconhecido, `apply` já em curso, versão inválida), `1` = o instalador falhou | a skill rodar `uv tool upgrade` direto - teria de escolher entre `uv` e `pipx` e lembrar do plugin; um `--yes` automático - o usuário pediu que o bot pergunte |
| 2. estado em disco | `~/.grokbot-kit/update.json` = `{"checked_at": "<RFC 3339>", "latest": "<X.Y.Z>" \| null, "error": "<texto>" \| null, "skipped": "<X.Y.Z>" \| null, "later_until": "<RFC 3339>" \| null}`, gravado por arquivo temporário + `os.replace` | guardar no `config.toml` - o config é do usuário e o `doctor` o valida; estado de cache não é configuração |
| 3. fonte da versão | `GET https://pypi.org/pypi/grokbot-kit/json`, campo `info.version`, timeout 5 s, `User-Agent: grokbot-kit/<versão>`, `urllib.request` (zero dependências, AD-009); `GROKBOT_KIT_PYPI_URL` troca a URL (testes); resultado vale 24 h, falha vale 1 h | API de releases do GitHub - limite de 60 req/h sem token e o pacote instalado vem do PyPI, não do GitHub |
| 4. objeto de checagem (consumido pela skill) | `{"installed": "0.2.2", "latest": "0.3.0" \| null, "update_available": bool, "ask": bool, "skipped": "<X.Y.Z>" \| null, "later_until": "<RFC 3339>" \| null, "checked_at": "<RFC 3339>", "installer": "uv" \| "pipx" \| null, "error": "<texto>" \| null}`; `ask` = `update_available` e `latest != skipped` e agora ≥ `later_until` | só `update_available` - a skill teria de recalcular skip e adiamento, e é onde um bot erra |
| 5. detecção do instalador | `sys.prefix/uv-receipt.toml` existe -> `uv` -> `uv tool upgrade grokbot-kit`; `sys.prefix/pipx_metadata.json` existe -> `pipx` -> `pipx upgrade grokbot-kit`; senão `null` | pelo caminho (`~/.local/share/uv/tools/`) - `UV_TOOL_DIR` e `PIPX_HOME` mudam o caminho; o arquivo de recibo vai junto |

- Nada mais aqui é difícil de reverter: comparação de versão, textos e o tempo de adiamento mudam num refactor.

## Criteria

### S1: o kit sabe se há versão nova (P1)

`grokbot-kit update check --json` responde se há release nova, sem travar nem falhar quando o PyPI não responde.

**Acceptance Criteria**

1. WHEN `grokbot-kit update check --json` roda e o estado da door 2 não existe ou tem `checked_at` com mais de 24 h (ou mais de 1 h quando `error` não é `null`) THEN o kit SHALL fazer um único `GET` na URL da door 3 e gravar `checked_at`, `latest` (o `info.version`) e `error` `null` no estado
2. WHEN `update check` roda e o estado tem `checked_at` com menos de 24 h e `error` `null` THEN o kit SHALL responder do estado sem nenhuma requisição de rede
3. WHEN o `latest` é maior que a versão instalada, comparando os três números de `X.Y.Z` THEN o objeto da door 4 SHALL ter `update_available` `true`
4. WHEN o `latest` é igual ou menor que a versão instalada THEN o objeto SHALL ter `update_available` `false` e `ask` `false`
5. IF o `GET` falha (sem conexão, timeout de 5 s, HTTP diferente de `200` ou JSON sem `info.version` em `X.Y.Z`) THEN o `update check` SHALL sair com `0`, com `latest` `null`, `update_available` `false`, `ask` `false` e `error` com o motivo, e gravar `checked_at` e `error` no estado
6. IF o estado da door 2 não é JSON válido THEN o `update check` SHALL tratá-lo como ausente e regravá-lo
7. The `update check --json` SHALL imprimir em stdout só o objeto da door 4, com as nove chaves dela
8. WHEN `update check` roda sem `--json` THEN o kit SHALL imprimir uma linha: `grokbot-kit <latest> available (installed <installed>); run: grokbot-kit update apply` quando `update_available`, `grokbot-kit <installed> is the latest` quando não, ou `update check failed: <error>` quando `error` não é `null`
9. The kit SHALL preencher `installer` pela regra da door 5
10. The requisição da door 3 SHALL levar o header `User-Agent: grokbot-kit/<versão instalada>`

**Independent test:** com `GROKBOT_KIT_PYPI_URL` apontando para um servidor local que responde `{"info": {"version": "9.0.0"}}`, `update check --json` mostra `update_available` `true` e `ask` `true`; com o servidor desligado, sai `0` com `error`.

### S2: o usuário adia ou pula uma versão (P1)

**Acceptance Criteria**

11. WHEN `grokbot-kit update skip <version>` roda com `<version>` em `X.Y.Z` THEN o kit SHALL gravar `skipped` = `<version>` no estado e sair com `0`
12. IF `<version>` não está em `X.Y.Z` THEN o `update skip` SHALL sair com `2` sem mudar o estado
13. WHILE o `latest` é igual ao `skipped` o objeto da door 4 SHALL ter `ask` `false` com `update_available` `true`
14. WHEN sai uma versão maior que o `skipped` THEN o objeto SHALL ter `ask` `true` de novo
15. WHEN `grokbot-kit update later` roda THEN o kit SHALL gravar `later_until` = agora + 24 h no estado e sair com `0`
16. WHILE agora é anterior a `later_until` o objeto da door 4 SHALL ter `ask` `false`

**Independent test:** com o servidor local em `9.0.0`, `update skip 9.0.0` faz `ask` virar `false`; trocando para `9.0.1`, `ask` volta a `true`; `update later` faz `ask` `false` com `later_until` daqui a 24 h.

### S3: o kit se atualiza pelo instalador que o instalou (P1)

**Acceptance Criteria**

17. WHEN `grokbot-kit update apply` roda com `installer` `uv` e uma checagem nova (sem usar o estado) mostra `update_available` THEN o kit SHALL rodar `uv tool upgrade grokbot-kit` (com `installer` `pipx`: `pipx upgrade grokbot-kit`), com timeout de 300 s
18. WHEN o upgrade sai com `0` e `opencode_plugin.plugin_path()` existe THEN o kit SHALL rodar `<launch.kit_executable()> install opencode` (o executável novo, não o código já carregado)
19. WHEN o upgrade e o plugin terminam com `0` THEN o `apply` SHALL imprimir `grokbot-kit <antiga> -> <nova>`, com `<nova>` lida de `<launch.kit_executable()> --version`, limpar `skipped` e `later_until` do estado e sair com `0`
20. WHEN a checagem nova mostra `update_available` `false` e `error` `null` THEN o `apply` SHALL imprimir `grokbot-kit <installed> is the latest`, não rodar instalador e sair com `0`
21. IF a checagem nova falha (`error` não `null`) THEN o `apply` SHALL sair com `1` com `update check failed: <error>` em stderr, sem rodar instalador
22. IF `installer` é `null` THEN o `apply` SHALL sair com `2` com `cannot tell how grokbot-kit was installed; upgrade it with the tool that installed it` em stderr
23. IF algum task dir em `config.tasks_dir()` tem `meta.json` com `finished_at` `null` e `started_at` + `timeout_seconds` + 60 s depois de agora THEN o `apply` SHALL sair com `2` listando em stderr o `task_id` de cada uma, sem rodar instalador
24. IF o upgrade sai com código diferente de `0` ou passa de 300 s THEN o `apply` SHALL sair com `1`, com o código e as últimas 20 linhas de stderr do instalador em stderr, sem chamar `install opencode`
25. IF o `install opencode` depois do upgrade sai com código diferente de `0` THEN o `apply` SHALL sair com `1` com `upgraded to <nova>, but the opencode plugin was not rewritten; run: grokbot-kit install opencode` em stderr
26. IF outro `apply` está em curso (lock `~/.grokbot-kit/update.lock` criado com `O_CREAT | O_EXCL` cujo pid existe) THEN o `apply` SHALL sair com `2`; um lock cujo pid não existe é tomado
37. IF o upgrade sai com `0` mas `<launch.kit_executable()> --version` não é maior que a versão instalada (instalação fixada numa versão: o `uv tool upgrade` não atualiza e sai com `0`) THEN o `apply` SHALL sair com `1`, com `<instalador> left grokbot-kit at <versão>; it may be pinned to a version: reinstall the latest grokbot-kit with the tool that installed it` e as últimas 20 linhas de stderr do instalador em stderr, sem chamar `install opencode` e sem mudar `skipped` nem `later_until` (AD-037, achado no smoke test da `0.3.0`)

**Independent test:** no box, num `HOME` limpo com a `0.2.2` instalada por `uv tool install --managed-python grokbot-kit==0.2.2` e o plugin instalado, `update apply` leva a `<latest>` e o plugin passa a ser o asset da versão nova.

### S4: o bot pergunta e atualiza tudo (P1)

**Acceptance Criteria**

27. The `SKILL.md` SHALL mandar, antes do Setup e antes de delegar uma Tarefa, com `grokbot-kit` no `PATH`, rodar `grokbot-kit update check --json`
28. WHEN o `ask` é `true` THEN o `SKILL.md` SHALL mandar fazer uma única pergunta de múltipla escolha com três opções: atualizar agora para `<latest>`, agora não, e pular a `<latest>`
29. The `SKILL.md` SHALL mapear as opções para `grokbot-kit update apply`, `grokbot-kit update later` e `grokbot-kit update skip <latest>`, com `<latest>` lido do objeto
30. WHEN o `update apply` sai com `0` THEN o `SKILL.md` SHALL mandar baixar `https://github.com/rodrigo-pasini/grokbot-kit/releases/latest/download/SKILL.md` (seguindo redirects) com as próprias ferramentas do bot, sobrescrever o `SKILL.md` do diretório de workflows da skill e reler a skill antes de seguir
31. IF o `update apply` sai com `1` ou `2` THEN o `SKILL.md` SHALL mandar contar ao usuário a mensagem de stderr e seguir com o que ele pediu na versão instalada
32. WHEN o `ask` é `false` ou o `update check` traz `error` THEN o `SKILL.md` SHALL mandar seguir sem mencionar atualização
33. The `SKILL.md` SHALL continuar sem `curl` e sem nenhum comando ou flag fora do `--help` do `grokbot-kit` (AC 119 da agent-run-notify)

**Independent test:** `tests/test_skill_doc.py` acha a chamada de `update check --json` antes das seções Setup e Tarefa, as três opções com os três comandos e a URL `latest` do `SKILL.md`.

### S5: o doctor mostra a atualização (P2)

**Acceptance Criteria**

34. WHEN `grokbot-kit doctor --json` roda THEN a saída SHALL ter `kit.update` com o objeto da door 4, obtido pelas mesmas regras de estado dos AC 1 e 2
35. The `doctor` SHALL manter `problems`, `ok` e o exit code independentes de `kit.update`
36. WHEN `kit.update.update_available` é `true` THEN o `doctor` em texto SHALL imprimir `update: grokbot-kit <latest> available; run: grokbot-kit update apply`

**Independent test:** com o servidor local em `9.0.0` e uma config sem problemas, `doctor --json` sai `0` com `kit.update.update_available` `true`.

## Out of scope

| Excluded | Why |
| --- | --- |
| Atualizar sem perguntar | o usuário pediu que o bot pergunte; o box é compartilhado e o upgrade troca o executável dos hooks |
| Avisar o bot por push (Action no release, cron no box) | o GitHub não conhece a URL secreta da routine de cada usuário; cron é supervisor de longa duração (mesmo motivo do watchdog na agent-run-notify) |
| Atualizar as CLIs `opencode`, `claude` e `codex` | cada CLI tem o próprio updater; o kit só as instala |
| Detectar skill velha com o kit já atualizado à mão | a skill não carrega versão; só o `apply` sabe que precisa trocar a skill |
| Downgrade e versão alvo escolhida (`apply <version>`) | o caso é seguir a última release |
| Pré-releases | o `info.version` do PyPI já ignora pré-release; o kit não publica nenhuma |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Quando checar | a cada uso da skill para setup ou tarefa, com cache de 24 h | escolha do usuário em 21/10/2026 | y |
| "Agora não" e "Pular" | três opções; pular vale até sair versão maior, agora não vale 24 h | escolha do usuário em 21/10/2026 ("só na próxima versão") | y |
| Checar ao receber evento da routine | não: só antes de Setup e Tarefa | o evento acorda o bot sem o usuário ter pedido nada; perguntar ali mistura o resultado da tarefa com o upgrade | n |
| Tarefa rodando durante o `apply` | recusa com exit `2` (AC 23), sem `--force` | o upgrade troca o executável que os hooks da tarefa chamam; uma tarefa `complex` pode segurar o upgrade até 4 h | n |
| Instalação por `git+https` | segue a door 5 (`uv tool upgrade` reinstala da mesma origem) e compara com o PyPI | é o caminho de antes do primeiro release; quem usa sabe o que instalou | n |
| Falha na checagem vale 1 h | 1 h antes de tentar de novo | offline, cada uso da skill pagaria o timeout de 5 s | n |

**Open questions:** none - all resolved or logged above.

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| comando `update check` | formato de saída e verbosidade | AC 7, AC 8 |
| comando `update check` | flags e padrão | AC 7, AC 8 (`--json` opcional, texto por padrão) |
| comando `update check` | exit codes | AC 5 (sempre `0`) |
| comando `update check` | falha no meio | AC 5, AC 6 |
| comando `update apply` | formato de saída | AC 19, AC 20 |
| comando `update apply` | flags e padrão | n/a - sem flags; não há `--force` (Assumptions) |
| comando `update apply` | exit codes | AC 19-26, AC 37 |
| comando `update apply` | falha no meio | AC 24 (instalador), AC 37 (instalador sai com `0` sem atualizar), AC 25 (plugin depois do upgrade) |
| comandos `update skip`, `update later` | saída, exit codes | AC 11, AC 12, AC 15 |
| `doctor --json` | campo novo, exit code | AC 34, AC 35 |
| `doctor` texto | linha nova | AC 36 |
| documento `SKILL.md` | estrutura | AC 27 (antes de Setup e Tarefa) |
| documento `SKILL.md` | o que o leitor faz em seguida | AC 28-32 |
| documento `SKILL.md` | tom e profundidade | existing - imperativo curto, um comando por bloco, como o resto da skill |
| `CHANGELOG.md` | o que o leitor faz em seguida | existing - seção da versão com o aviso de baixar a skill nova uma vez (Impact) |

## Sources

- Pedido do usuário nesta sessão (21/10/2026): o bot vê a versão nova e pergunta com opções para clicar, como no setup
- `docs/.specs/STATE.md` - AD-009 (zero dependências), AD-016/AD-028/AD-033 (plugin global), AD-032 (`SKILL.md` no release)
