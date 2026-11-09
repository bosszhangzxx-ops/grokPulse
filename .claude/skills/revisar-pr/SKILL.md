---
name: revisar-pr
description: |
  Revisa um pull request no GitHub e posta um único review consolidado (evento
  COMMENT, com comentários inline), com evidência em cada achado e no máximo 3
  rodadas. A rodada 1 é completa; as seguintes só conferem o ledger e bloqueante
  novo introduzido pela correção.
  Use quando o usuário disser "revisa esse PR", "revisa o pull request",
  "faz o code review", "code review desse PR", "julga esse PR", "/review",
  "revisa de novo", "roda o review de novo", "re-review".
  NÃO use para corrigir o código, responder comentário de review, nem
  diagnosticar ou consertar falha de CI.
---

# Revisar PR

Revisa como engenheiro sênior com barra alta: poucos comentários, cada um com
evidência, num único review. Três achados que importam vencem quinze observações.

O contrato de convergência adapta a skill the-judge, de Felipe Rodrigues
(tech-leads-club), sob CC-BY-4.0.

## Invariantes

1. **Evidência ou silêncio.** Afirmação interna exige `path:line` que você leu;
   afirmação sobre biblioteca ou API exige URL oficial buscada nesta review. Sem
   evidência, pergunte ou cale — palpite faz o autor perder tempo.
2. **Não comente o que o ferramental pega.** Lint, typecheck, teste e CI vêm antes.
   O que eles apontam fica fora do review, senão o fio repete o bot.
3. **No máximo 5 nits inline.** O excedente é uma contagem no resumo. Não empilhe
   nit em código que um achado estrutural vai reescrever: o conserto apaga os dois.
4. **A rodada 1 é a review inteira.** Tudo que está visível entra agora. Segurar
   achado para depois é o que vira pingue-pongue.
5. **Rodada 2+ verifica, não abre frente.** Contrato em `references/contrato-convergencia.md`.
6. **O evento é sempre COMMENT.** Aprovar, pedir mudanças, fazer merge, fechar, dar push
   ou editar o PR não é desta skill. O veredito vai no texto — o botão do GitHub não
   pode dizer que a skill aprovou.
7. **Idioma pedido, com acento.** Se ninguém pediu, português. Nunca poste segredo:
   aponte o `path:line` e não cole o valor.

## Severidade

| severidade | emoji | o que é | veredito pretendido |
|---|---|---|---|
| bloqueante | 🔴 | não deveria mergear: perda de dado, segurança explorável, dinheiro errado, auth quebrada, migração irreversível, PII em log | `precisa de mudanças` |
| deve-corrigir | 🟠 | defeito real, sem risco de merge | `comentários` |
| nit | 🟡 | menor; teto de 5 inline | nenhum |
| pre-existente | 🟣 | o PR não introduziu; só no resumo, nunca inline | nenhum |

Aberto = novo nesta rodada + `carryover`. Algum 🔴 aberto → `precisa de mudanças`.
Nenhum 🔴 e algum 🟠 → `comentários`. Nenhum dos dois → `pronto para aprovação humana`.
Nit e pré-existente não mudam o veredito. As três frases são exatas, sem ponto.

## Passo 0 — Contexto e rodada

```bash
gh auth status
```

Se falhar, pare e peça autenticação. Não invente token.

`ALVO` é o número ou a URL que o usuário passou. Se não passou:

```bash
gh pr view --json number --jq .number
```

Se não houver PR, pare e diga. Abrir PR não é desta skill. Metadata e reviews
anteriores, ainda sem o diff:

```bash
gh pr view "$ALVO" --json number,url,title,body,author,baseRefName,headRefName,additions,deletions,changedFiles,headRefOid
gh pr view "$ALVO" --json files --jq '.files[] | "\(.path) +\(.additions) -\(.deletions)"'
LOGIN=$(gh api user --jq .login)
OWNER_REPO=$(gh pr view "$ALVO" --json url --jq '.url | capture("github\\.com/(?<owner>[^/]+)/(?<repo>[^/]+)/pull/") | "\(.owner)/\(.repo)"')
NUM=$(gh pr view "$ALVO" --json number --jq .number)
HEAD_SHA=$(gh pr view "$ALVO" --json headRefOid --jq .headRefOid)
gh api --paginate "repos/${OWNER_REPO}/pulls/${NUM}/reviews" --jq ".[] | select(.user.login==\"${LOGIN}\" and ((.body // \"\") | test(\"<!-- revisar-pr round=[0-9]+ sha=[0-9a-f]+ -->\"))) | {id, html_url, submitted_at, body}"
```

Preencha antes de buscar o diff:

| parâmetro | de onde vem |
|---|---|
| `LOGIN` | `gh api user` |
| `OWNER_REPO`, `NUM`, `HEAD_SHA` | o PR |
| `RODADA` | 1 se não houver marcador deste `LOGIN`; senão, o maior `round=` + 1 |
| `SHA_ANTERIOR` | o `sha=` desse maior marcador |

Review sem o marcador `<!-- revisar-pr round=N sha=... -->` não é rodada: não há ledger
para conferir. Comece na 1.

Rodada 1, o diff inteiro do PR:

```bash
gh pr diff "$ALVO"
```

Rodada 2 ou 3, e só se `HEAD_SHA` for diferente de `SHA_ANTERIOR` — o diff desde aquele
SHA, não o PR inteiro. Se o compare falhar (force-push), siga `references/contrato-convergencia.md`.

```bash
gh api "repos/${OWNER_REPO}/compare/${SHA_ANTERIOR}...${HEAD_SHA}" --jq '{status, ahead_by, files: [.files[]? | {filename, status, additions, deletions, patch}]}'
```

| situação | o que fazer |
|---|---|
| sem marcador deste revisor | rodada 1: passos 1 a 5 em cima do `gh pr diff` |
| `HEAD_SHA` igual ao `SHA_ANTERIOR`, ou compare com zero arquivos | não poste. Se o pedido veio de um comentário no PR, `gh pr comment "$ALVO"` com o texto de `references/contrato-convergencia.md`; senão, só ao usuário. Sem marcador |
| rodada calculada ≥ 4 | não poste review. Aponte a review da rodada 3. Mesma regra de resposta |
| rodada 2 ou 3, com diff novo | leia `references/contrato-convergencia.md` e siga só o contrato. Não rode o passo 3. Passo 1 só para não repetir o que o CI já marcou nesse delta. Passo 2 só se o 🔴 novo afirmar algo de biblioteca ou API. Passos 4 e 5 |

Parou na tabela: não crie worktree. Vai postar review: o diff acima é remoto. Ler arquivo
ou rodar lint/teste no checkout da sessão usa outra revisão sempre que `HEAD` não for
`HEAD_SHA`. Não use `gh pr checkout`: isso move a sessão.

```bash
REPO_ATUAL=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)
SHA_ATUAL=$(git rev-parse HEAD 2>/dev/null || true)
```

`ARVORE` é o checkout atual só se `REPO_ATUAL` é `OWNER_REPO`, `SHA_ATUAL` é `HEAD_SHA` e
`git status --porcelain` está vazio. Senão, worktree descartável do head do PR — e confira
o SHA antes de abrir qualquer arquivo:

```bash
git fetch origin "pull/${NUM}/head"
git worktree remove --force "/tmp/revisar-pr-${HEAD_SHA}" 2>/dev/null || true
git worktree add --detach "/tmp/revisar-pr-${HEAD_SHA}" FETCH_HEAD
git -C "/tmp/revisar-pr-${HEAD_SHA}" rev-parse HEAD
```

A última saída tem que ser `HEAD_SHA`. `ARVORE=/tmp/revisar-pr-${HEAD_SHA}`. Arquivo,
caller, callee, lint, typecheck e teste rodam aí (`git -C "$ARVORE"`, cwd `$ARVORE`).
Apague a worktree antes de encerrar, em qualquer saída — review postado, parada ou erro:

```bash
git worktree remove --force "/tmp/revisar-pr-${HEAD_SHA}"
```

Se o fetch ou a worktree falhar (outro repo, SHA que não vem no `pull/${NUM}/head`), não
leia o working tree e não rode check local. Leia cada arquivo core pela API:

```bash
gh api -H "Accept: application/vnd.github.raw" "repos/${OWNER_REPO}/contents/<path>?ref=${HEAD_SHA}"
```

Em Checks, escreva que o checkout não era o `HEAD_SHA` e que lint/teste local não rodou.
`gh pr checks` continua valendo: é do head do PR.

Quando a rota acima for postar review, classifique cada arquivo desse diff como **core**
ou **mecânico** (lockfile, código gerado, snapshot, saída de build). Não leia o miolo do
mecânico; liste-o em Arquivos ignorados. Bloco que sai de um arquivo e reaparece igual
noutro é mudança de lugar, não código novo. Leia em `ARVORE` os arquivos core que o diff
toca; abra caller ou callee só para cravar um achado. Não leia o repo inteiro.

## Passo 1 — Checks determinísticos

```bash
gh pr checks "$ALVO"
```

Exit code 1 aqui é check falho, não comando quebrado: leia a tabela. No job que falhou,
`gh run view <id> --log-failed`. Se o head ainda não tem check e `ARVORE` é um checkout de
`HEAD_SHA` com o ferramental do repo, rode lá o lint, o typecheck e os testes focados que
o próprio repo declara (cwd `$ARVORE`). Não instale nada e não rode isso num checkout que
não seja `HEAD_SHA`. O que essa saída apontar fica fora do review. Sem ferramental, ou sem
`ARVORE` no SHA certo, anote em Checks e siga.

No diff, bypass é candidato, não achado automático. Nu (sem justificativa e sem link de
issue) segue para o passo 3; justificado com link não vira achado.

- supressão de lint ou tipo (`eslint-disable`, `noqa`, `@ts-ignore`, `@ts-expect-error`, `type: ignore`)
- teste skipped ou only (`.skip`, `.only`, `xit`, `fit`, `pytest.mark.skip`)
- TLS desligado (`verify=False`, `InsecureSkipVerify`, `NODE_TLS_REJECT_UNAUTHORIZED=0`)
- `any` ou cast para calar o tipo
- `catch` vazio
- `sleep` / `time.sleep` / `setTimeout` como sincronização

Teste skipped cai no passe G; TLS no B; o resto em A ou E.

## Passo 2 — Pesquisa

Liste superfície externa que o diff toca: dependência nova ou com bump, API, feature de
framework, feature de linguagem que depende de versão. Para cada uma, busque doc oficial,
changelog ou advisory **nesta** review. Memória não é fonte. Inconclusivo vira pergunta ou
morre. Zero superfícies: escreva `nenhuma superfície externa` em Pesquisa. Na rodada 2+,
pesquise só se um 🔴 novo afirmar algo de biblioteca ou API.

## Passo 3 — Passes (somente rodada 1)

Todos os arquivos core, todos os passes, numa tacada. Não deixe "para uma segunda olhada".
Não comente nit dentro do bloco que um 🔴 ou 🟠 manda reestruturar.

- **A. Correção.** Invariante quebrado, falha que perde dado, estado pela metade, concorrência concreta.
- **B. Segurança.** Explorável, com confiança alta, introduzido por este PR.
- **C. Dados e migração.** Reversibilidade, índice, N+1, transação, compatibilidade.
- **D. IA / LLM.** Só se o diff tiver prompt, chamada de modelo ou eval: injeção, custo ou token sem teto, timeout, retry, vazamento para o provedor.
- **E. Estrutura.** Duplicação, fronteira, arquivo que inchou, código morto ou comentado, comentário que repete o código, abstração especulativa.
- **F. Alegação do PR.** "Corrige X" sem teste ou repro vira pergunta, não afirmação de que o conserto está errado.
- **G. Testes** do comportamento que importa.

Cada passe produz candidato: afirmação, severidade tentativa, `path:line`.

## Passo 4 — Verificar

Releia o código em `ARVORE`, em cada `path:line`. Mate o que não tiver evidência. Deduplique. Severidade
conservadora: 🔴 incerto vira 🟠 em forma de pergunta. Pequeno mas real é 🟡, não descarte.
Na rodada 2+, 🔴 incerto morre (não pode virar 🟠). ID estável: `F1`, `F2`, … nunca muda;
ID novo continua a sequência do ledger.

## Passo 5 — Escrever e postar

Leia `references/voz-do-comentario.md` e `references/modelo-do-resumo.md`. Grave o
`findings.json` fora do repo. Na rodada 2+, `ledger_anterior` lista cada ID da review
anterior com a severidade, e `--ledger` repete a mesma lista (`F1:deve-corrigir,F2:bloqueante`).
Lista vazia só se aquela review não tinha ID. O gate recusa ID faltando, ID desconhecido
e severidade trocada.

```bash
~/.claude/skills/revisar-pr/scripts/conferir-achados.py /tmp/revisar-pr-findings.json --emit /tmp/revisar-pr-payload.json
```

Na rodada 2+, acrescente `--ledger "$LEDGER"` nesse comando.

Se o exit code não for 0, corrija o JSON e rode de novo. Não poste. Com exit 0:

```bash
gh api --method POST "repos/${OWNER_REPO}/pulls/${NUM}/reviews" --input /tmp/revisar-pr-payload.json
```

Uma chamada, todos os inline no mesmo payload. O `event` do arquivo emitido é `COMMENT` —
não troque, não use `gh pr review`, não mande um POST por comentário. COMMENT também vale
no PR do próprio usuário.

422 (âncora fora do diff): a chamada é atômica, nada foi postado. Mova o `line` para uma
linha que o diff mostra, rode o gate de novo e poste o payload novo. Não mude o evento.

## Depois de postar

Diga ao usuário: link do PR, rodada, veredito pretendido, contagem por severidade (na rodada
2+, também resolvido / aberto / recusado-aceito), os 1–3 piores achados em uma linha cada,
e que o review foi postado (a `html_url` que a API devolveu). Se não postou, diga por quê.

## Referências

- `references/contrato-convergencia.md` — rodada 2+, recusa, teto de 3, diff desde o SHA
- `references/voz-do-comentario.md` — forma do inline, o que não escrever
- `references/modelo-do-resumo.md` — frases fixas, seções, `findings.json`
- `scripts/conferir-achados.py` — gate; só poste com exit 0
