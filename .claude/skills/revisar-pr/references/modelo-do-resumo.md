# Modelo do resumo e do findings.json

Leia antes de escrever o JSON. O gate em `scripts/conferir-achados.py` é a autoridade: se
este arquivo e o script divergirem, o script ganha e o JSON não passa.

Grave fora do repo (`/tmp/revisar-pr-findings.json`). Não versione.

## Frases fixas

O gate casa estas strings, com acento e pontuação:

- `Veredito pretendido: <veredito>.` — o veredito é exatamente uma destas:
  `precisa de mudanças`, `comentários`, `pronto para aprovação humana`
- `Rodada N. Commit revisado: `<sha>`.` — SHA de 40 hex minúsculos, o `headRefOid`
- `Para nova rodada, comente `/review` no PR. Rodada N de no máximo 3.`
- última linha: `<!-- revisar-pr round=N sha=<sha> -->` (uma vez, e só esta)

Nit nunca muda o veredito. Algum bloqueante aberto (novo ou `carryover`) → `precisa de
mudanças`. Sem bloqueante e com deve-corrigir aberto → `comentários`. Sem os dois →
`pronto para aprovação humana`.

## Seções, nesta ordem

`## TL;DR`, `## Achados`, `## Resolução` (só rodada 2+; na rodada 1 o gate recusa),
`## Virar regra de lint`, `## Pesquisa`, `## Checks`, `## Arquivos ignorados`,
`## Nits excedentes` (opcional, e tem que ser a última seção).

Nenhuma outra linha `## `. Se o log do CI tiver uma, recue quatro espaços. Uma linha que
começa com `## ` abre seção.

O bloco abaixo é o mapa das seções, não um resumo de rodada 1 para copiar: na rodada 1
não existe `## Resolução`, e `## Nits excedentes` só entra se o teto de 5 estourou.

```markdown
## TL;DR

Uma a três frases: o que o PR faz.
Veredito pretendido: comentários.
Rodada N. Commit revisado: `<sha>`.

## Achados

| ID | Severidade | Local | Resumo |
|---|---|---|---|
| F1 | 🟠 deve-corrigir | `src/frete.ts:18` | arredonda cada trecho antes de somar |

## Resolução

| ID | Severidade | Status | Nota |
|---|---|---|---|
| F1 | deve-corrigir | resolvido | corrigido em abcdef0 |

## Virar regra de lint

nenhuma

## Pesquisa

nenhuma superfície externa

## Checks

lint ok, testes 10 passed / 0 failed

## Arquivos ignorados

nenhum

## Nits excedentes

3 nits não postados um a um

Para nova rodada, comente `/review` no PR. Rodada N de no máximo 3.

<!-- revisar-pr round=N sha=<sha> -->
```

Na rodada 1, apague `## Resolução`. `## Nits excedentes` só entra se o teto de 5 estourou;
o número é a contagem, não a lista. Sem arquivo mecânico, escreva `nenhum` em Arquivos
ignorados. Sem superfície externa, a frase canônica é `nenhuma superfície externa`. Sem
regra de lint a promover, `nenhuma`. Checks é o resultado **verbatim** (contagens, nome do
check, pass/fail) — sem interpretar. URL consultada vai em Pesquisa, uma por linha, com a
afirmação que ela sustenta ou derruba. Fonte que matou um candidato também entra.

A coluna Severidade usa o token: `bloqueante`, `deve-corrigir`, `nit`, `pre-existente`
(o emoji pode acompanhar). Na Resolução ela é a segunda coluna, com o mesmo token da
rodada em que o ID nasceu: sem isso a rodada 3 não reconstrói o carryover. A coluna
Status usa `resolvido`, `aberto`, `recusado-aceito`. Não use `|` dentro da nota.
Pré-existente na coluna Local pode ser o `path:line` antigo; ele não ganha comentário
inline. `severidade`, `status`, `side` e `tipo` são string. Lista ou objeto é erro do
gate, não exceção.

## findings.json

| chave | regra |
|---|---|
| `round` | inteiro 1–3 |
| `head_sha` | 40 hex minúsculos |
| `veredito` | uma das três frases, sem ponto |
| `carryover` | `{"bloqueante": N, "deve-corrigir": N}`; na rodada 1 os dois são 0; depois, conta status `aberto` |
| `resumo` | o markdown acima |
| `achados` | lista do que é **novo** nesta rodada; vazia é válida |
| `resolucao` | ausente ou `[]` na rodada 1; obrigatória na rodada 2+; exatamente os IDs de `ledger_anterior`, com a mesma severidade |
| `ledger_anterior` | ausente ou `[]` na rodada 1; na rodada 2+, cada ID da review anterior como `{"id","severidade"}`. Lista vazia só se aquela review não tinha ID |

Cada item de `achados`:

| chave | regra |
|---|---|
| `id` | `F1`, `F2`, … sem zero à esquerda; único; não repete ID da `resolucao` |
| `severidade` | `bloqueante`, `deve-corrigir`, `nit`, `pre-existente`. Na rodada 2+ só `bloqueante` |
| `path` | caminho relativo, sem `..` e sem absoluto. Obrigatório fora do pré-existente |
| `line` | inteiro ≥ 1, linha no arquivo. Proibido no pré-existente; obrigatório nos outros |
| `side` | `RIGHT` ou `LEFT`. Proibido no pré-existente |
| `body` | começa com `{emoji} {ID} `; ≤ 900 caracteres; sem exclamação |
| `evidencia` | lista não vazia de `{"tipo": "interna", "ref": "path:line"}` ou `{"tipo": "externa", "ref": "https://..."}` |

Cada item de `resolucao`: `id`, `severidade`, `status`, `nota`. Nota de `resolvido` cita um sha.
A severidade copia o ledger; não se reclassifica um bloqueante como nit para zerar o carryover.
Opcional, `--ledger F1:deve-corrigir,F2:bloqueante` tem que ser igual a `ledger_anterior`.
ID que falta, ID desconhecido ou severidade diferente recusa o gate.

O gate ignora um campo `event` se alguém colocar no JSON. O payload emitido é sempre
`COMMENT`. Não edite o evento no arquivo emitido.

Rodada 1, um deve-corrigir:

```json
{
  "round": 1,
  "head_sha": "0123456789abcdef0123456789abcdef01234567",
  "veredito": "comentários",
  "carryover": {"bloqueante": 0, "deve-corrigir": 0},
  "resumo": "## TL;DR\n\nO PR adiciona o cálculo de frete por trecho.\nVeredito pretendido: comentários.\nRodada 1. Commit revisado: `0123456789abcdef0123456789abcdef01234567`.\n\n## Achados\n\n| ID | Severidade | Local | Resumo |\n|---|---|---|---|\n| F1 | 🟠 deve-corrigir | `src/frete.ts:18` | arredonda cada trecho antes de somar |\n\n## Virar regra de lint\n\nnenhuma\n\n## Pesquisa\n\nnenhuma superfície externa\n\n## Checks\n\nlint ok, testes 10 passed / 0 failed\n\n## Arquivos ignorados\n\nnenhum\n\nPara nova rodada, comente `/review` no PR. Rodada 1 de no máximo 3.\n\n<!-- revisar-pr round=1 sha=0123456789abcdef0123456789abcdef01234567 -->\n",
  "achados": [
    {
      "id": "F1",
      "severidade": "deve-corrigir",
      "path": "src/frete.ts",
      "line": 18,
      "side": "RIGHT",
      "body": "🟠 F1 `calcular` arredonda cada trecho antes de somar (src/frete.ts:18). Dois trechos de 0,005 viram 0 e o frete sai de graça. Some em milésimos e arredonde uma vez no fim.",
      "evidencia": [{"tipo": "interna", "ref": "src/frete.ts:18"}]
    }
  ]
}
```

Rodada 2, achado anterior resolvido, sem 🔴 novo:

```json
{
  "round": 2,
  "head_sha": "abcdef0123456789abcdef0123456789abcdef01",
  "veredito": "pronto para aprovação humana",
  "carryover": {"bloqueante": 0, "deve-corrigir": 0},
  "ledger_anterior": [
    {"id": "F1", "severidade": "deve-corrigir"}
  ],
  "resolucao": [
    {
      "id": "F1",
      "severidade": "deve-corrigir",
      "status": "resolvido",
      "nota": "corrigido em abcdef0"
    }
  ],
  "achados": [],
  "resumo": "## TL;DR\n\nO cálculo de frete passou a somar em milésimos e arredondar uma vez.\nVeredito pretendido: pronto para aprovação humana.\nRodada 2. Commit revisado: `abcdef0123456789abcdef0123456789abcdef01`.\n\n## Achados\n\n| ID | Severidade | Local | Resumo |\n|---|---|---|---|\n\n## Resolução\n\n| ID | Severidade | Status | Nota |\n|---|---|---|---|\n| F1 | deve-corrigir | resolvido | corrigido em abcdef0 |\n\n## Virar regra de lint\n\nnenhuma\n\n## Pesquisa\n\nnenhuma superfície externa\n\n## Checks\n\nlint ok, testes 12 passed / 0 failed\n\n## Arquivos ignorados\n\nnenhum\n\nPara nova rodada, comente `/review` no PR. Rodada 2 de no máximo 3.\n\n<!-- revisar-pr round=2 sha=abcdef0123456789abcdef0123456789abcdef01 -->\n"
}
```
