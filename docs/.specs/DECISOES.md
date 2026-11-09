# Decisões do projeto `grokbot-kit` (18/10/2026)

Registro das decisões do Rodrigo e do raciocínio por trás delas. O contrato fica em
`features/agent-run-notify/plan.md`; as decisões com ID estão em `STATE.md`.

## Decididas em 18/10/2026

| Tema | Decisão | ID |
| --- | --- | --- |
| Nome | `grokbot-kit` | AD-002 |
| Licença | MIT | AD-012 |
| Linguagem | Python ≥ 3.11, instalado com `uv tool install` (ou `pipx`) | AD-009 |
| Timeout | por tier: `trivial` 30 min, `standard` 2 h, `complex` 4 h; `--timeout` prevalece | AD-013 |
| Entrega | 3 tentativas (esperas de 1 s e 4 s, 10 s cada) + comando `grokbot-kit redeliver <task_id>` | AD-014 |
| Resumo | 2000 caracteres em `summary`; texto inteiro em `output_file` | AD-015 |
| Plugin opencode | global em `~/.config/opencode/plugins/`, inerte fora de uma task, com `uninstall`; testar `OPENCODE_CONFIG` no build e trocar se funcionar | AD-016 |
| `needs_input` | um por permissão distinta | AD-017 |
| Task dirs | guardados; limpeza manual com `grokbot-kit gc --older-than 30d` | AD-018 |
| Fundação | slice S0: repositório e configuração inicial especificados antes do código | AD-019 |
| Webhook de routine | contrato verificado em 18/10/2026 (seção 5) | AD-021 |

## 1. Nome

Checagem de 18/10/2026 (GitHub, npm, PyPI):

| Opção | Colisões |
| --- | --- |
| **`grokbot-kit` (escolhido)** | nenhum repo com o nome exato (3 parecidos: `sparks-grokbot-kit`, `grokbot-backup-kit`, `grokbot-reference-kit`); livre no npm e no PyPI; `rodrigo-pasini/grokbot-kit` ainda não existe |
| `grokbot-bridge` | 3 repos com o nome exato e 24 pontes Grok Bot parecidas |
| `grokbot-relay` | colisão real: `devicki/grokbot-relay`, ativo, mesmo nicho |
| `grokbot-runner`, `grokbot-hooks`, `grokbot-tools` | livres, mas descrevem só parte do projeto ou são genéricos demais |

Risco aceito: "grokbot" remete à marca xAI; se houver pedido de mudança, renomear.

## 2. Licença: MIT

As duas candidatas são permissivas (qualquer um usa, muda, vende e embute, mantendo o aviso de copyright).
A Apache-2.0 acrescenta concessão de patentes, aviso de arquivos alterados e uma cláusula de marca. Para
uma CLI pequena de dev solo/irmãos, o risco de patente é quase nulo; a MIT ganha pela simplicidade.
Mudar depois exige a concordância de quem já contribuiu.

## 3. Linguagem: Python

Comparação feita antes da decisão:

| Critério | Go | Python (escolhido) |
| --- | --- | --- |
| Distribuição | um executável estático | pacote no PyPI; `uv tool install` cria ambiente isolado |
| Início do processo (box, 18/10/2026) | 3-4 ms | `import os,sys` 9 ms; `+json` 15 ms; `+urllib.request` 38 ms; tudo junto 49-75 ms |
| Box compartilhado | nada a quebrar | resolvido com ambiente isolado do `uv tool` e Python gerenciado pelo `uv` |
| Escrever e mudar | mais verboso | mais rápido de escrever e ler |

Como Python fica seguro e rápido aqui (door 6 do plano):

- **Isolamento:** `uv tool install --managed-python grokbot-kit` põe o kit em
  `~/.local/share/uv/tools/grokbot-kit/` com um Python do próprio `uv`; trocar pacotes ou o Python do
  sistema não afeta o kit. `pipx install grokbot-kit` é a alternativa sem `uv` (o `pipx` não está no box).
- **Zero dependências de runtime:** `dependencies = []`; só stdlib (`argparse`, `tomllib`, `json`,
  `urllib.request`, `subprocess`, `signal`). A escrita do `config.toml` usa um serializador próprio e
  mínimo (o `tomllib` só lê); `tomli-w` só se esse serializador crescer.
- **`emit` rápido:** importa só `os`, `sys` e `json` antes do gate de `GROKBOT_KIT_TASK_ID`; o resto
  (`urllib.request`, leitor do config) carrega sob demanda. Meta: sair em até 50 ms de mediana quando não
  há task, conferido com `python -X importtime`.
- **Caminho absoluto:** hooks, plugin e `--settings` chamam `~/.local/bin/grokbot-kit` pelo caminho
  absoluto, sem depender do `PATH` de cada CLI.

## 4. Padrões (decididos)

- **Timeout por tier (30 min / 2 h / 4 h), `--timeout` prevalece.** Mata agente travado sem cortar
  tarefas grandes. Ao estourar: `SIGINT`, `SIGTERM` 10 s depois, `SIGKILL` 10 s depois, evento `timeout`.
- **3 tentativas + `redeliver`.** Cobre instabilidade de segundos sem segurar o fim do `run`; `4xx` não
  tenta de novo. O que falhar fica em `undelivered.jsonl`, e `grokbot-kit redeliver <task_id>` reenvia
  (com lock, para não duplicar).
- **Resumo de 2000 caracteres.** Cabe um resumo útil; o bot só abre `output_file` quando precisa.
- **Plugin opencode global, inerte fora de uma task, com `uninstall`.** No build, testar se
  `OPENCODE_CONFIG` carrega um plugin só naquela execução; se carregar, trocar e remover o plugin global.
- **Um `needs_input` por permissão distinta.** O mesmo pedido repetido não acorda o bot de novo; pedidos
  diferentes sim.
- **Task dirs guardados + `gc` manual.** `grokbot-kit gc --older-than 30d` apaga só tarefas terminadas e
  sem eventos pendentes de entrega; `--dry-run` só lista.

## 5. Webhook de routine (verificado em 18/10/2026 18:38 BRT)

Probe registrado em `/workspace/taskhook/webhook-probe/probe-20261018T183849.json` (sem a key).

- **Endpoint:** `POST https://api2.cursor.sh/automations/webhook/<routine-uuid>`, URL copiada do campo
  "POST para" do painel da routine.
- **Auth:** `Authorization: Bearer crsr_<hex>`; o painel mostra a key e o header pronto. O arquivo de
  segredo guarda **só** a key `crsr_…`; o kit monta o `Bearer`. Sem o header: `401`
  `{"code":"error","message":"Missing Authorization header. Use Authorization: Bearer <key>."}`.
- **Sucesso:** `200` `{"success":true,"runUuid":"<uuid>"}`; o `runUuid` é o recibo, gravado em
  `sent/<chave>` e `events.jsonl`.
- **O que a routine recebe:** envelope `{headers, body, body_digest, timestamp_ms}`. `body` é o texto cru
  exatamente como enviado (a plataforma não faz parse; o prompt da routine faz), acentos UTF-8 intactos,
  `body_digest = "sha256:" + sha256(body)`. Só `content-type`, `user-agent` e `x-request-id` são
  repassados; `Authorization` **não** chega ao agente. Por isso o kit manda `User-Agent: grokbot-kit/<versão>`.
- **Retry:** `401` e demais 4xx não tentam de novo (vão para `undelivered.jsonl`, com dica de
  `secret set` no `401`); `429` e 5xx seguem a política de 3 tentativas.
- **Segurança:** em 18/10/2026 a key vazou num print de tela. A skill avisa antes de o usuário abrir o
  painel, e diante de key em chat ou print pede para regenerá-la. A key desse teste deve ser regenerada.
- **Ainda desconhecido:** tamanho máximo do corpo, rate limit, se corpos não JSON são aceitos.

## 6. Fundação do repositório (S0 - confirmada pelo Rodrigo em 18/10/2026)

Confirmados (AD-020): dono `rodrigo-pasini`, público; README em inglês com `docs/pt-BR/README.md`
opcional; `pyproject.toml` com layout `src/` e `uv_build`; `.python-version` 3.11 e `uv.lock`; `ruff`,
`mypy --strict`, `pytest`, `pre-commit`; CI em Ubuntu com Python 3.11-3.13; release por tag com trusted
publishing; `main` com PR + CI e 0 aprovações; Dependabot; `.specs/` versionado (sem `SPEC.md`);
skill em `skills/grokbot-kit/SKILL.md`.

### Quem executa e em que ordem (AD-022, proposta)

O repositório **ainda não existe**. Quem cria é o agente de código **local** do Rodrigo, que tem o `gh`
autenticado, e só com aprovação explícita dele. Ordem (AC 20-38 do plano):

1. `gh auth status --active --hostname github.com --json hosts` mostra `rodrigo-pasini`, `state: success`
   e, se token clássico, escopo `repo` (o token só aparece com `--show-token`, que é proibido).
2. `gh repo view rodrigo-pasini/grokbot-kit` precisa **falhar**; se existir, parar.
3. Commit inicial local em `main` (scaffold + `.specs/` + `skills/`), com lint, tipos e testes verdes e um
   `git grep` de padrões de token sem resultado.
4. `gh repo create rodrigo-pasini/grokbot-kit --public --description "..." --disable-wiki --source=. --remote=origin`
   (sem `--add-readme`, `--license`, `--push`).
5. `gh repo edit` com as features, merge só squash, auto-merge, topics, secret scanning e push protection.
6. `git push -u origin main`; esperar o `ci.yml` ficar verde (`gh run watch`).
7. Proteção da `main`: `gh api -X PUT .../branches/main/protection --input .github/repo-settings/main-protection.json`
   com os checks `lint`, `typecheck`, `test (3.11)`, `test (3.12)`, `test (3.13)` (app GitHub Actions,
   id `15368`), 0 aprovações, `enforce_admins: true`, histórico linear, sem force push nem exclusão.
8. `PUT .../vulnerability-alerts` e `PUT .../automated-security-fixes`.
9. Environment `pypi` com revisor `rodrigo-pasini` (id `17571964`) e regra de tag `v*`.
10. Labels opcionais; depois verificação de tudo com `gh repo view --json ...` e `gh api ... --jq ...`,
    reportada sem tokens.

Escolhas desta etapa ainda a confirmar: `enforce_admins: true` (o próprio Rodrigo também passa por PR com
CI verde); revisor no environment `pypi` (uma aprovação por release); secret scanning ligado antes do
primeiro push (se a API recusar num repositório vazio, logo depois); a lista de labels.

### Passos só humanos

- **PyPI:** em `https://pypi.org/manage/account/publishing/`, adicionar um *pending publisher*: projeto
  `grokbot-kit`, owner `rodrigo-pasini`, repositório `grokbot-kit`, workflow `release.yml`, environment
  `pypi`. O pending publisher **não reserva o nome** até a primeira publicação; nenhuma tag `v*` antes disso.
- **Aprovar a criação** do repositório público antes de o agente local executar o S0.
- **Aprovar cada publicação** no environment `pypi` (se o revisor for mantido).
