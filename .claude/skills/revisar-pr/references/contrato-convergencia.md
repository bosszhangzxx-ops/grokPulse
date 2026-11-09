# Contrato de convergência

Adapta a skill the-judge, de Felipe Rodrigues (tech-leads-club), sob CC-BY-4.0.
A rodada 1 é exaustiva; cada rodada seguinte encolhe. O que isto mata é o pingue-pongue
em que toda volta descobre uma frente nova.

O evento continua **COMMENT** em todas as rodadas. "Pronto para aprovação humana" é texto:
quem aprova é uma pessoa. Não aprove, não peça changes, não mergeie.

## Escopo da rodada N (N ≥ 2)

Exatamente duas coisas:

1. **Conferência do ledger.** Para cada ID da review anterior, olhe os commits novos e
   marque um status: `resolvido` (cite o sha), `aberto`, ou `recusado-aceito` (a razão de
   quem recusou se sustenta). Todos aparecem na tabela Resolução. Isto é checklist, não
   caçada nova.
2. **🔴 novo, e só 🔴.** O diff desde o SHA da última rodada é lido só para achar bloqueante
   introduzido pela correção (incluindo resolução de conflito dessa correção). Sem 🟠 novo,
   sem 🟡 novo, sem 🟣 novo. Código que estava visível na rodada 1 e não foi apontado está
   perdido: quem revisa engole o miss.

A única exceção ao item 2 é um 🔴 genuíno descoberto tarde (perda de dado, segurança
explorável, dinheiro errado, auth quebrada, migração irreversível, PII em log). Ele entra,
com ID novo, e o corpo diz, em uma frase factual, que não foi apontado na rodada 1.
Bloqueante incerto **não** vira 🟠 nesta rodada — 🟠 novo é proibido. Sem evidência que você
sustentaria sozinho, o candidato morre.

Código que chegou de outra frente num merge não é frente nova: ignore, a menos que a
resolução do conflito tenha criado o 🔴.

## Ledger

A fonte é o corpo da última review **deste** revisor que tem o marcador
`<!-- revisar-pr round=N sha=... -->`. Leia a tabela Achados e, se existir, a Resolução.

- O ID nasce na rodada 1 (`F1`, `F2`, …) e **não muda** nunca. Não renumere.
- O próximo ID novo continua a sequência. Se a rodada 1 parou em `F4`, o 🔴 tardio é `F5`.
- A Resolução da rodada corrente lista **todo** ID já aberto, inclusive `resolvido` e
  `recusado-aceito`, com a severidade original. A review mais recente tem que bastar sem
  abrir as anteriores: a coluna Severidade é o que permite reconstruir o carryover.
- `carryover` conta só o que segue `aberto` em `bloqueante` e `deve-corrigir`. Nit e
  pré-existente abertos não entram no carryover e não mudam o veredito.
- No `findings.json`, `ledger_anterior` é essa lista (`id` + `severidade`) copiada da
  tabela anterior — Achados, se a rodada anterior era a 1; Resolução, da rodada 2 em
  diante. `resolucao` tem exatamente esses IDs, a mesma severidade, e nenhum ID a mais.

Colunas, com este espaçamento: `| F1 | deve-corrigir | resolvido | nota sem pipe |`

| status | quando | nota |
|---|---|---|
| `resolvido` | o commit novo corrige o achado | cita o sha (7–40 hex) |
| `aberto` | continua valendo, ou a recusa não se sustentou | o que ainda falta; se for o único reargumento, comece a nota com `reargumentado:` e a evidência nova (`path:line` ou URL) |
| `recusado-aceito` | a razão de quem recusou se sustenta | a razão, em uma linha |

Não crie ID novo para achado velho. Não republique comentário inline de ID velho: na rodada
2+ o array `achados` só leva 🔴 novo. O reargumento mora na nota, não num fio novo.

## Recusa

Quem recusa está mais perto do código e pode estar certo. Se a razão se sustenta do ponto
de vista da saúde do código, marque `recusado-aceito` e largue para sempre. Se não se
sustenta, reargumente **uma vez**, com evidência nova, na nota (`reargumentado:`). Depois
disso, se seguir sem acordo: deixe `aberto`, escreva que a divergência sai do fio, e não
levante de novo. Fio de review não resolve filosofia.

Na rodada seguinte, repita a linha `recusado-aceito` sem argumento novo.

## Teto: 3 rodadas

Na rodada 3, cada item ainda `aberto` termina de um destes jeitos, dito na nota:

- corrigido num commit (`resolvido`), ou
- proposto como follow-up **no texto** (não abra issue nem edite o PR por conta própria), ou
- escalado para uma pessoa, fora deste fio.

Não existe rodada 4. Se pedirem de novo, não poste review e não rode o gate. Responda ao
usuário. Se o pedido veio de um comentário no PR, um `gh pr comment` curto, **sem** o
marcador:

```
Rodada 3 já encerrou este review (máximo de 3): <url da review>. Item ainda aberto sai deste fio — follow-up ou decisão humana.
```

## Sem commit novo

SHA do head igual ao `sha=` da última rodada, ou compare com zero arquivos no diff: não
poste review. Responda uma linha — no PR, se o pedido veio de um comentário `/review`;
senão, só ao usuário:

```
Não há commits novos desde <sha> (rodada N). Não postei outro review.
```

Sem marcador nesse comentário.

## Diff desde o SHA anterior

```bash
gh api "repos/${OWNER_REPO}/compare/${SHA_ANTERIOR}...${HEAD_SHA}" --jq '{status, ahead_by, files: [.files[]? | {filename, status, additions, deletions, patch}]}'
```

Se o compare falhar porque o SHA sumiu (force-push), diga isso no TL;DR, use `gh pr diff`
só para caçar 🔴 novo, e **não** recomece na rodada 1. O ledger anterior continua valendo.

## O que o gate exige nesta rodada

`round` 2 ou 3; `ledger_anterior` com cada ID antigo e a severidade; `resolucao` com
exatamente esses IDs e a mesma severidade (falta, ID desconhecido ou severidade trocada
recusa); `--ledger ID:severidade,...`, se passado, igual ao campo; `achados` vazio ou só
`bloqueante`; `carryover` batendo com os `aberto`; seção `## Resolução` com a coluna
Severidade; veredito calculado pelo que ainda está aberto (carryover + 🔴 novo). Detalhe
do JSON em `references/modelo-do-resumo.md`.
