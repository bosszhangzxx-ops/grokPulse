# Config por projeto e regras de detecção

A skill funciona **sem config nenhuma** — detecta o que der e pergunta o resto. O arquivo abaixo
existe para o projeto congelar o que já se sabe, e é o que torna a skill reaproveitável entre
repos com convenções diferentes.

## `.claude/worktree-handoff.json` (opcional)

```json
{
  "worktree_base": "../worktrees",
  "base_branches": { "default": "staging", "bugfix": "main", "hotfix": "main" },
  "branch_pattern": "<tipo>/<id>/<slug>",
  "branch_validator": "scripts/validar_branch.sh",
  "copy": [".env", ".claude", "CLAUDE.local.md"],
  "mkdir": ["logs"],
  "agent": "claude",
  "handoff_skill": "bmad-dev-story",
  "notes": "docker compose colide com a stack do clone principal (container_name fixo)"
}
```

| chave | o que faz | default quando ausente |
|---|---|---|
| `worktree_base` | onde as worktrees nascem, relativo ao repo | `../worktrees` (irmão do repo) |
| `base_branches` | base por tipo de trabalho | detecção (abaixo) + pergunta |
| `branch_pattern` | molde do nome da branch | `<tipo>/<id>/<slug>` |
| `branch_validator` | script do repo que valida o nome | regex do hook `pre-push`, se houver |
| `copy` | arquivos/dirs gitignored a copiar | `.env`, `.claude`, `CLAUDE.local.md` se existirem |
| `mkdir` | dirs vazios exigidos por volume mount | `logs` se estiver no `.gitignore` |
| `agent` | agente do `orca worktree create --agent` | `claude` |
| `handoff_skill` | skill que o filho deve executar | vem do workflow que chamou |
| `notes` | avisos repassados ao usuário/filho | — |

## Detecção quando não há config

- **Base branch:** `git symbolic-ref refs/remotes/origin/HEAD` dá o default do remoto. Se o repo
  tiver branch `staging`/`develop` além do default, é GitFlow: **pergunte** qual base, em uma
  linha, em vez de assumir. Bugfix de produção costuma sair do default, não da branch de
  integração.
- **Padrão de branch:** procure um regex em `.githooks/pre-push`, `.husky/`, `.pre-commit-config.yaml`
  ou em `CLAUDE.md`/`CONTRIBUTING.md`. ⚠️ **Validar de cabeça aprova o que o hook depois rejeita** —
  a armadilha clássica é trocar a barra por hífen entre o id e o slug.
- **Arquivos a copiar:** o que está no topo do repo **e** ignorado pelo git é candidato:
  `git ls-files --others --ignored --exclude-standard --directory` no topo. Sempre inclua
  `.claude/` quando existir — sem ele a sessão filha não enxerga as skills do projeto.
- **Dirs a criar:** entradas do `.gitignore` que sejam dir e apareçam em `docker-compose*.yml`
  como volume (`logs`, `storage`, `tmp`).

## Onde o ID vem

O nome da worktree é `<ID>-<slug>` e o ID vem do rastreador do projeto (work item do Azure,
issue do GitHub, card do Jira legado). A skill **não** cria nem valida card — isso é do guardião
de fluxo do projeto, se houver. Ela só usa o ID como nome.
