# Voz do comentário

Leia antes de redigir qualquer `body` e o resumo. O gate recusa parte disto por regex;
o resto é critério. Escrever em cima da regex e manter o tom errado continua errado.

## Forma do inline

Um achado, um comentário, uma linha do diff. O `body` começa com o emoji da severidade,
espaço, o ID, espaço:

```
🟠 F2 `aplicarFrete` soma trechos já arredondados (src/frete.ts:18). Dois trechos de 0,005 viram 0 e o frete sai de graça. Some em milésimos e arredonde uma vez no fim.
```

Nesta ordem, em prosa corrida, sem título e sem lista:

1. O que está errado, com o símbolo e o `path:line` que você leu.
2. O efeito concreto (dado, dinheiro, segurança, estado pela metade). "Fica mais limpo" não é efeito.
3. A menor correção concreta. Se a evidência não fecha, uma pergunta — e a severidade não é 🔴.
   Na rodada 2+ essa pergunta não se posta: ou é 🔴 com evidência, ou morre.

Teto: 900 caracteres, contando emoji e ID. O gate mede `len` do `body`.

`line` é o número da linha no arquivo: lado `RIGHT`, arquivo novo; lado `LEFT`, arquivo
antigo. Não é a posição do hunk. Pré-existente não tem `line` nem `side`: só a tabela do
resumo.

## O que não entra

- Elogio, pedido de desculpa, "vale ressaltar", "só um detalhe", "espero ter ajudado", LGTM.
- Ponto de exclamação. O gate recusa `!` seguido de espaço ou fim de texto no `body` e em
  toda seção do resumo fora de `## Checks` (o log do CI entra verbatim e pode ter `!`).
- Dois problemas no mesmo ID. Deduplique no passo 4.
- Segredo, token, PII, connection string. Aponte o `path:line` e não reproduza o valor.
- Nit em código que um 🔴 ou 🟠 estrutural manda reescrever. Anote no resumo: "nits retidos
  nas linhas que o conserto estrutural reescreve".
- Afirmação sobre biblioteca, API ou advisory sem URL `https://` oficial consultada nesta
  review. Sem a URL, vira pergunta ou morre.

## Idioma

O texto corrido sai no idioma que o usuário ou o time pediu. Se ninguém pediu, português,
com acento. Identificador, string citada e saída de ferramenta ficam como estão.

Os títulos `##`, a frase do veredito, a linha do commit, o fecho e o marcador são fixos,
mesmo quando o texto corrido for outro idioma. A rodada seguinte e o gate casam essas
frases. Elas estão em `references/modelo-do-resumo.md`.

## Exemplos

Ruim (elogio, exclamação, sem evidência, sem conserto):

```
Ótimo PR! Só um detalhe: será que não seria melhor tratar o caso vazio?
```

Bom:

```
🔴 F1 `cobrar` persiste a fatura antes de debitar o estoque (src/pedido.ts:88). Se o débito falha, fica fatura paga de item que não saiu. Débite na mesma transação e só então grave a fatura.
```
