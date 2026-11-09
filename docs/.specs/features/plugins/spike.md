# plugins - spike da matriz de capacidades (S1)

Rodado em 22/10/2026 no host de desenvolvimento (Linux 6.17, `kernel.apparmor_restrict_unprivileged_userns = 1`, a
mesma restrição do box: `bwrap --ro-bind / / --unshare-net true` sai com `bwrap: loopback: Failed RTM_NEWADDR:
Operation not permitted`). O box só é acessível pelo bot; a rodada lá, com a release, fica para a próxima task
(AD-042). Versões: `claude` 2.1.308, `opencode` 2.1.3 (o box estava no 1.19.3), `codex-cli` 0.163.0.

Cada célula foi provada pelas provas `-m integration` de `tests/integration/test_plugin_caps.py`, rodando
`grokbot-kit run --plugin` com o harness de `launch.plugin_harness` e um agente real (`claude` com `sonnet` e `haiku`,
`opencode` com `opencode/deepseek-v4.1-flash-free`), 3 rodadas verdes cada, e cada uma matou a falha injetada no
harness correspondente (shell liberado, escrita em qualquer lugar, config do workspace carregada, sem a skill).

## Matriz

| CLI | versão | capacidade | valor | sondagem | comando | saída observada |
| --- | --- | --- | --- | --- | --- | --- |
| `claude` | `2.1.308` | `write` | `tool` | `-` | `pytest -m integration tests/integration/test_plugin_caps.py -k "write_outside_denied and claude"` | `permission_denials`: `Write` fora do task dir (recusado pelo `--restricted`) e `Bash printf x > ...` (negado pelo `dontAsk`); o arquivo não existe |
| `claude` | `2.1.308` | `network` | `unsupported` | `bwrap --ro-bind / / --unshare-net true` | `bwrap --ro-bind / / --unshare-net true` | `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`; só o sandbox do Claude (bwrap) cortaria a rede dos comandos permitidos |
| `claude` | `2.1.308` | `commands` | `tool` | `-` | `pytest -m integration tests/integration/test_plugin_caps.py -k "command_outside_denied and claude"` | `permission_denials`: `Bash touch <task_dir>/spike-cmd`; `git status` (prefixo `git`) rodou; `spike-cmd` não existe |
| `claude` | `2.1.308` | `workspace_config` | `tool` | `-` | `pytest -m integration tests/integration/test_plugin_caps.py -k "workspace_config_ignored and claude"` | o hook `SessionStart` de `.claude/settings.json` do workspace não rodou (marcador ausente); sem `--restricted` o marcador aparece |
| `claude` | `2.1.308` | `skills` | `tool` | `-` | `pytest -m integration tests/integration/test_plugin_caps.py -k "skill_loaded and claude"` | transcript com `"name":"Skill","input":{"skill":"spike-skill:spike"`; `result.word` = `spike-skill-ok`; sem `--plugin-dir` a prova falha |
| `opencode` | `2.1.3` | `write` | `tool` | `-` | `pytest -m integration tests/integration/test_plugin_caps.py -k "write_outside_denied and opencode"` | `Permission denied: external_directory` na escrita e `Permission denied: shell` no `printf`; o arquivo não existe |
| `opencode` | `2.1.3` | `network` | `unsupported` | `-` | `opencode run --help` e a config de `https://opencode.ai/config.json` | nenhum mecanismo de rede no opencode: `webfetch`/`websearch` negados não cortam a rede dos comandos do shell |
| `opencode` | `2.1.3` | `commands` | `tool` | `-` | `pytest -m integration tests/integration/test_plugin_caps.py -k "command_outside_denied and opencode"` | `Permission denied: shell` no `touch`; `git status` rodou; `spike-cmd` não existe |
| `opencode` | `2.1.3` | `workspace_config` | `tool` | `-` | `pytest -m integration tests/integration/test_plugin_caps.py -k "workspace_config_ignored and opencode"` | o MCP local do `opencode.json` do workspace não subiu (marcador ausente) com `OPENCODE_DISABLE_PROJECT_CONFIG=1` e `PWD` no workspace; sem a variável o marcador aparece |
| `opencode` | `2.1.3` | `skills` | `tool` | `-` | `pytest -m integration tests/integration/test_plugin_caps.py -k "skill_loaded and opencode"` | `"tool":"skill","state":{"status":"completed","input":{"id":"spike"`; `result.word` = `spike-skill-ok`; sem `skills.paths` a prova falha |
| `codex` | `0.163.0` | `write` | `unsupported` | `codex sandbox -- true` | `codex sandbox -- true` | exit `1`, `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`; `workspace-write` depende do sandbox, que não sobe neste host nem no box |
| `codex` | `0.163.0` | `network` | `unsupported` | `codex sandbox -- true` | `codex sandbox -- true` | exit `1`; `network_access = false` é imposto pelo mesmo sandbox |
| `codex` | `0.163.0` | `commands` | `unsupported` | `-` | `codex exec --help` e `https://learn.chatgpt.com/docs/agent-configuration/rules` | sem lista de permissão por tarefa: `prefix_rule` só lê `rules/` de uma camada de config, e o que não casa cai no sandbox |
| `codex` | `0.163.0` | `workspace_config` | `unsupported` | `-` | `codex exec --help` | `-c projects."<work>".trust_level="untrusted"` ignora `.codex/`, mas `.agents/skills` do repositório carrega mesmo assim; e a CLI já sai pela `write` (AC 7) |
| `codex` | `0.163.0` | `skills` | `unsupported` | `-` | `codex exec --help` | nenhuma opção acrescenta um diretório de skills por execução; só `HOME` trocado, que muda o ambiente dos comandos |

## Notas

- `tool` aqui é permissão da CLI: impede as ferramentas do agente, não um processo que um comando permitido rode (um
  `pytest` roda código do repositório com as permissões do usuário do box). O guia diz isso em `commands`.
- O opencode 2 roda o `run` contra um serviço compartilhado que não lê o env da tarefa; o harness passa `--standalone`
  quando `opencode --version` dá 2 ou mais. O box tem o 1.19.3, que não foi provado aqui.
- O opencode acha o projeto pelo `PWD`, não pelo cwd: o kit passava o `PWD` herdado de quem chamou o `run`, e o
  workspace do opencode virava esse diretório. O `run` agora passa `PWD` = cwd do agente, para toda CLI.
- O agente lê a cópia do plugin no task dir (skills leem os arquivos de apoio da pasta delas), mas não a altera.
- Uma célula `os` precisaria do sandbox do sistema (`bwrap`), que este host e o box não sobem sem root; a sondagem
  registrada é o comando que diria se o host passou a subir.
