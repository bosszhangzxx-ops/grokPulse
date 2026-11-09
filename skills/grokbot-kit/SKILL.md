---
name: grokbot-kit
description: Instala e configura o grokbot-kit e delega tarefas a agentes de código headless, acordando a routine deste bot quando a tarefa termina ou precisa de permissão. Use quando o usuário disser "configurar grokbot-kit", "delegar para opencode/claude/codex" ou "rodar tarefa headless".
---

# grokbot-kit

O `grokbot-kit` roda uma tarefa num agente de código headless (`opencode`, `claude` ou `codex`) e, quando ela termina
ou esbarra numa permissão, acorda a routine deste bot com um evento JSON. Esta skill faz o setup na primeira vez e
depois delega as tarefas. O próximo passo é sempre um comando `grokbot-kit`.

Instalação desta skill: copie a pasta `skills/grokbot-kit/` do repositório `rodrigo-pasini/grokbot-kit` para o
diretório de workflows do Grok Bot; no box, `/home/box/agent-data/workflows/grokbot-kit/`.

## Regras

- Só chame `grokbot-kit`, `uv` ou `pipx` (para instalar o kit) e as CLIs oficiais `opencode`, `claude` e `codex`.
  Nada de editar o config à mão, `curl` ou scripts próprios.
- Nunca invente um id de modelo, um comando ou uma flag. Use só o que esta skill cita e o que o `--help` do
  `grokbot-kit` mostra; um id de modelo só existe depois que `grokbot-kit setup models refresh` o descobriu.
- Nunca peça que o usuário cole no chat uma API key, uma sender key ou uma URL secreta (a URL do webhook da routine
  é secreta). Segredo entra só por `grokbot-kit secret set <nome>`, com o valor na entrada padrão: lido pelas suas
  próprias ferramentas (a URL e a key de uma routine deste bot) ou pedido ao usuário num campo mascarado de
  segredos, que guarda o valor fora do chat. Nunca passe o valor como argumento, nunca o mostre, repita ou registre.
  Só sem campo mascarado peça que o usuário rode `grokbot-kit secret set <nome>` num terminal do box, que lê o
  valor sem eco.
- Se o usuário colar um segredo no chat ou mandar um print em que a key aparece: não grave o valor, não repita o
  valor, e avise que ele vazou e precisa regenerar a key no painel da routine (ou no painel de quem a emitiu) e
  gravar a nova com `grokbot-kit secret set <nome>` pelo campo mascarado de segredos.

## Atualização

Antes do Setup e antes de delegar uma Tarefa, se `grokbot-kit` estiver no `PATH`, rode
`grokbot-kit update check --json` para saber se há versão nova do kit.

Com `ask` `false`, ou com `error` preenchido, siga sem mencionar atualização.

Com `ask` `true`, faça uma única pergunta de escolha múltipla, com três opções, e rode o comando da opção escolhida,
trocando `<latest>` pelo campo `latest` da saída:

- Atualizar agora para a `<latest>`: `grokbot-kit update apply`.
- Agora não (pergunta de novo em 24 h): `grokbot-kit update later`.
- Pular a `<latest>` (pergunta de novo só quando sair uma versão maior): `grokbot-kit update skip <latest>`.

Se o `grokbot-kit update apply` sair com `0`, baixe com suas próprias ferramentas, seguindo redirects,
`https://github.com/rodrigo-pasini/grokbot-kit/releases/latest/download/SKILL.md`, sobrescreva o `SKILL.md` do
diretório de workflows desta skill (no box, `/home/box/agent-data/workflows/grokbot-kit/SKILL.md`) e releia a skill
antes de seguir.

Se o `grokbot-kit update apply` sair com `1` ou `2`, conte ao usuário a mensagem de stderr e siga com o que ele pediu
na versão instalada.

## Setup (primeira vez)

### 1. Instalar o kit

Confira se o kit está no `PATH`:

```sh
grokbot-kit --version
```

Se `grokbot-kit` não estiver no `PATH` (o comando não existe), instale antes de qualquer outro passo com `uv tool install --managed-python grokbot-kit`
(ambiente isolado, com Python gerenciado pelo `uv`); sem `uv` no box, use `pipx install grokbot-kit`. Depois rode o
`grokbot-kit --version` de novo.

```sh
uv tool install --managed-python grokbot-kit
```

```sh
pipx install grokbot-kit
```

### 2. Ver o estado

```sh
grokbot-kit doctor --json
```

A saída diz o que já está feito: `setup.installed` (CLIs instaladas), `setup.default_cli`, o login de cada CLI, as
rotas e os segredos; `problems` lista o que corrigir, com o comando. Pule os passos que já estão feitos.
Com `cli.opencode.reply.warning` preenchido (opencode 1.x, que só avisa os pedidos de permissão e não espera a
resposta), ofereça ao usuário atualizar o opencode, que também reescreve o plugin:

```sh
grokbot-kit setup cli upgrade opencode
```

### 3. CLIs e login

Com `setup.installed` vazio no `grokbot-kit doctor --json`, faça uma única pergunta de múltipla escolha: quais CLIs instalar entre `opencode`,
`claude` e `codex` (o `opencode` tem modelos gratuitos e não exige login para eles).

Para cada CLI escolhida, instale com `grokbot-kit setup cli add <tool>`, que usa o instalador oficial:

```sh
grokbot-kit setup cli add <tool>
```

Com o `opencode`, instale também o plugin que avisa quando o agente pede permissão (fora de uma tarefa ele não faz
nada):

```sh
grokbot-kit install opencode
```

Depois, para cada CLI, pergunte o método de login: assinatura ou API key.

- Assinatura: peça que o usuário rode `grokbot-kit login <tool> --method subscription` num terminal do box e siga o
  que a CLI pedir.
- API key: peça a key no campo mascarado de segredos (nunca no chat) e grave-a pela entrada padrão de
  `grokbot-kit secret set <tool>-api-key`; depois rode `grokbot-kit login <tool> --method api-key`.

```sh
grokbot-kit login <tool> --method subscription
```

```sh
grokbot-kit login <tool> --method api-key
```

### 4. CLI padrão

Pergunte qual CLI usar quando o usuário não pedir nenhuma e grave a escolha:

```sh
grokbot-kit setup default <tool>
```

### 5. Modelos e tiers

Descubra os modelos de cada CLI instalada:

```sh
grokbot-kit setup models refresh --json
```

A saída é um objeto JSON: `models` traz um item por modelo descoberto, com `tool` (a CLI), `id` e `provider` (no
opencode, o provedor do id; no `claude` e no `codex`, `null`). Use só ids da lista descoberta.

Com o `opencode` instalado, faça uma única pergunta de múltipla escolha com os provedores do opencode: os valores
distintos do campo `provider` nos itens do `opencode`, cada um com quantos ids ele tem na lista (por exemplo,
"`opencode-go` (30 ids)"). Grave os provedores escolhidos, na ordem de preferência do usuário:

```sh
grokbot-kit setup providers opencode <provider> [<provider>...]
```

Um provedor pago (o usuário paga por assinatura ou API key, como o `opencode-go`) só funciona com login no opencode:
pergunte se o usuário já fez esse login no box; se não, peça que ele rode `grokbot-kit login opencode` num terminal do
box antes de seguir. Não decida pelo `login` do `grokbot-kit doctor --json`: ele não enxerga todo login do opencode.

Depois, para cada CLI instalada, faça uma pergunta por tier (`trivial`, `standard` e `complex`, nessa ordem), com até
4 ids da lista descoberta e o recomendado primeiro; no opencode, só ids dos provedores escolhidos. O usuário escolhe
um ou mais ids, ou digita outro id da lista, e a ordem da escolha é a ordem do tier: o primeiro id vence, e se o
provedor dele falhar antes de o agente agir, o kit tenta o próximo. Grave cada tier:

```sh
grokbot-kit setup tiers <tool> <tier> <id> [<id>...]
```

O que recomendar primeiro em cada pergunta:

- com só o provedor `opencode` escolhido, recomende os modelos gratuitos do opencode primeiro em `trivial` e
  `standard` (são os ids que a lista do opencode marca com o sufixo `-free`);
- com algum provedor que não é `opencode` escolhido, recomende primeiro os ids desse provedor em todos os tiers: o
  usuário paga por ele;
- em `complex`, nunca recomende modelo gratuito (veja a rubrica).

Quando o usuário pedir para trocar os modelos, refaça só este passo: `grokbot-kit setup models refresh --json`, a
pergunta de provedores e as perguntas dos tiers. As CLIs, o acesso delas e a routine ficam como estão.

Se o usuário quiser no `claude` ou no `codex` um id que não está na lista, teste e grave com
`grokbot-kit setup models refresh <tool> --add <id>` antes de usá-lo; um id recusado não entra.

### 6. Routine do bot

Este bot é acordado por uma routine com webhook trigger. Use como nome do bot (`<bot>`) um nome curto deste bot, só
com letras, dígitos, `.`, `_` e `-`.

Antes de tudo, avise: a key da routine (`crsr_…`) não pode aparecer em print, colagem ou mensagem, porque um print
vai para o chat e a key vaza (já aconteceu).

1. Crie uma routine para este bot com webhook trigger, usando o prompt de routine abaixo. Se suas ferramentas criam
   routines, crie você mesmo; senão, peça ao usuário: abra o painel do Grok Bot e crie a routine.
2. Grave a URL de "POST para" da routine com `grokbot-kit secret set <bot>-url` e depois a key `crsr_…` com
   `grokbot-kit secret set <bot>-key`, cada valor pela entrada padrão do comando, nesta ordem de preferência:
   - leia os dois valores da routine com suas próprias ferramentas, sem mostrá-los;
   - senão, peça cada um ao usuário num campo mascarado de segredos (ele copia do painel da routine e cola no campo);
   - só sem campo mascarado, peça que o usuário rode os dois comandos num terminal do box.
3. Crie a rota e teste a entrega:

```sh
grokbot-kit route add <bot> --url-secret <bot>-url --key-secret <bot>-key
```

```sh
grokbot-kit route test <bot>
```

O `route test` envia um evento `test` à routine. Exit `0` é entrega confirmada; exit `1` mostra o status HTTP (um
`401` é key errada: grave de novo com `grokbot-kit secret set <bot>-key`).

#### Prompt da routine

Proponha este prompt para a routine, trocando `<bot>` pelo nome deste bot:

```text
Você recebe um webhook do grokbot-kit. O campo `body` chega como texto: faça o parse dele como JSON.
Se o parse falhar ou o campo `schema` não for "grokbot-kit.event/v1", ignore o webhook.
Se o campo `target` não for "<bot>", ignore o evento: ele é de outro bot.
Senão, siga a skill grokbot-kit, seção "Quando um evento chega", com o evento lido.
```

## Plugins

Plugins são tarefas prontas do kit, como o `code-review` (revisa um PR do GitHub): cada um traz o próprio prompt,
declara as entradas e as capacidades - o que o agente pode fazer (`write`, `network`, `commands`) - e devolve um
resultado estruturado no evento.

Quando o usuário pergunta o que o kit sabe fazer, e antes de delegar uma tarefa, rode:

```sh
grokbot-kit plugin list --json
```

Mostre ao usuário o `name`, a `description` e as `capabilities` de cada plugin.

Quando o pedido casa com um plugin listado, não escreva prompt: rode `grokbot-kit run --plugin <nome>` com uma
`--input <entrada>=<valor>` para cada entrada de `inputs` (as `required` são obrigatórias). Uma entrada `repo` é a URL
de um PR (`https://github.com/<owner>/<repo>/pull/<n>`) ou de uma branch (`https://github.com/<owner>/<repo>/tree/<branch>`)
do GitHub, que o kit clona. Não passe `--cwd`: o agente de um plugin roda sempre no diretório da tarefa.

```sh
grokbot-kit run --plugin <nome> --input <entrada>=<valor> --target <este bot> --label <rótulo>
```

Se o `run` sair com `2` dizendo que a CLI não consegue impor uma capacidade (`cannot enforce`), conte ao usuário e
ofereça rodar com outra CLI, por `--tool`, que o `support` do plugin marque como `os` ou `tool` em todas as
capacidades.

Quando o usuário pede para instalar um plugin (um diretório ou uma URL git), siga esta ordem:

1. Rode `grokbot-kit plugin show <origem> --json` e mostre ao usuário as `capabilities` e o `support` de cada CLI.
2. Pergunte se ele quer instalar o plugin com essas capacidades.
3. Só com o sim, rode `grokbot-kit plugin add <origem> --yes`.

## Tarefa

Antes de escrever um prompt, veja em [Plugins](#plugins) se um plugin faz a tarefa.

Toda tarefa vai a `grokbot-kit run` com `--target <este bot>` (o mesmo `<bot>` da rota) e um `--label` curto que
descreve a tarefa (letras, dígitos, `.`, `_` e `-`). Passe o diretório do projeto com `--cwd <dir>` e o prompt depois
de `--`. O `run` só termina quando o agente termina; o resultado chega pela routine, então não fique esperando. O
caminho do task dir sai em stderr.

Quando o usuário pede CLI e modelo:

```sh
grokbot-kit run --tool <cli> --model <id> --target <este bot> --label <rótulo> --cwd <dir> -- "<prompt>"
```

Omita `--tool` quando o usuário não pede uma CLI: o kit usa a CLI padrão.

Quando o usuário não pede modelo, classifique a tarefa em `trivial`, `standard` ou `complex` pela rubrica abaixo,
passe `--tier <tier>` e diga ao usuário a classe escolhida em uma linha (por exemplo: "Classifiquei como `trivial`:
renomear variáveis num arquivo.").

```sh
grokbot-kit run --tier <tier> --target <este bot> --label <rótulo> --cwd <dir> -- "<prompt>"
```

O tier também decide o timeout (`trivial` 30 min, `standard` 2 h, `complex` 4 h); `--timeout <duração>` (`30m`,
`2h`) prevalece.

### Rubrica de tiers

| Tier | Quando |
| --- | --- |
| `trivial` | mudança pequena e mecânica, sem decisão: renomear, formatar, corrigir um typo, ajustar uma linha |
| `standard` | trabalho comum de código: uma função, um teste, um bug localizado, uma refatoração contida |
| `complex` | revisão de segurança, decisões de arquitetura, checagem de fatos, e tudo o que toca produção, credenciais ou dados sensíveis |

Tarefas `complex` nunca vão a modelos gratuitos: sem modelo pedido, use `--tier complex`; se o usuário pedir um modelo
gratuito para uma delas, explique o motivo e proponha um id do tier `complex`. Na dúvida entre dois tiers, escolha o
maior.

## Quando um evento chega

A routine acorda este bot com o webhook. Faça o parse de `body` como JSON e leia `event`, `status`, `summary` e
`output_file` (a saída completa do agente; `log_file` tem o log do kit).

- `completed` com `status` `ok`: conte ao usuário o resultado a partir do `summary`.
- `error` (`failed` ou `interrupted`) e `timeout`: conte o que houve e o que o `summary` diz; ofereça rodar de novo.
- `model_fallbacks` com algum item: o modelo de cada item falhou no provedor (o motivo está em `error`) e o kit rodou
  o próximo id do tier; o modelo que rodou por último está em `model`. Conte isso ao usuário e ofereça trocar os
  modelos do tier.
- `needs_input` de `permission` com `needs_input.reply_deadline` preenchido: o agente está parado esperando a
  resposta. Antes do `reply_deadline`, aplique a regra de risco de [Pedido de permissão](#pedido-de-permissão) e
  responda com `grokbot-kit reply`.
- `needs_input` com `needs_input.reply_deadline` `null` (`permission` ou `question`), ou `completed` com `status`
  `denied`: mostre ao usuário o que o agente pediu (`needs_input.tool_name` e `needs_input.detail`) e ofereça retomar
  com o comando de `resume_hint` depois de ajustar a permissão. Um `needs_input` chega enquanto a tarefa ainda roda; o
  evento final vem depois.
- Tarefa de plugin (campo `plugin` preenchido): com `status` `ok`, conte o resultado a partir de `result`, o objeto
  que o plugin promete (o `summary` repete o dele). `error` com `exit_reason` `result_invalid` quer dizer que o agente
  terminou sem gravar um resultado válido; o motivo está no `summary`. Uma tarefa de plugin nunca chega como `denied`.
- `test`: é o `grokbot-kit route test`; só confirme que a rota funciona.

### Pedido de permissão

O agente espera a resposta até `needs_input.reply_deadline`; sem resposta até lá, o kit nega o pedido. Leia
`needs_input.tool_name` e `needs_input.detail` (o comando, o arquivo ou o caminho pedido) e o `cwd` do evento (o
diretório da tarefa), e classifique o risco.

Baixo risco é só isto:

- ler, listar ou buscar arquivos;
- rodar os testes, os linters, a checagem de tipos ou o build do projeto;
- criar ou editar arquivos dentro do `cwd` do evento;
- `git status`, `git diff`, `git log` e `git show`.

Pergunte ao usuário todo pedido fora dessa lista, e sempre que ele tiver:

- caminho fora do `cwd` do evento, inclusive por `..` ou por link;
- mais de um comando no mesmo pedido (`;`, `&&`, `||`, `|`), substituição (`$(...)` ou crase) ou redirecionamento
  (`>`), mesmo que comece por teste ou build;
- rede: download, instalação de pacote, `git fetch`, `git pull`, `git push`, `git clone`;
- apagar arquivos;
- reescrever o histórico do `git` (`reset`, `rebase`, `commit --amend`, push forçado);
- segredos, credenciais, `.env` ou `~/.ssh`;
- `sudo` ou mudança no sistema (pacotes, serviços, usuários, permissões);
- qualquer pedido que você não consegue classificar com certeza.

De baixo risco, responda sozinho e conte ao usuário, em uma linha, o que aprovou:

```sh
grokbot-kit reply <task_id> <request_id> allow --by bot
```

Nos outros casos, mostre ao usuário `needs_input.tool_name` e `needs_input.detail`, pergunte se libera e responda com
o que ele disser, antes do `reply_deadline`; numa negação, passe o motivo dele em `--message`:

```sh
grokbot-kit reply <task_id> <request_id> allow --by user
grokbot-kit reply <task_id> <request_id> deny --by user --message "<motivo>"
```

`<task_id>` é o `task_id` do evento e `<request_id>` é o `needs_input.request_id`. Você nunca nega sozinho: o que não
aprova vai ao usuário, e sem resposta dele o kit nega no `reply_deadline`. Se o `reply` sair com `1` dizendo que o
prazo venceu ou que a tarefa terminou, conte ao usuário e ofereça retomar com o `resume_hint` do evento final.

## Evento que não chegou

Se o usuário pergunta por uma tarefa cujo evento não chegou, veja o `undelivered.jsonl` no task dir da tarefa
(`~/.grokbot-kit/tasks/<task_id>/`): cada linha é uma entrega que falhou, com o motivo. Corrija a causa (rota ou key)
e ofereça reenviar com `grokbot-kit redeliver <task_id>`.

```sh
grokbot-kit redeliver <task_id>
```
