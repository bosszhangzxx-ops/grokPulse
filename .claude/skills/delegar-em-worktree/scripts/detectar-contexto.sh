#!/usr/bin/env bash
# Imprime o contexto necessário para criar uma worktree de tarefa neste repo.
# Não altera nada. Uso: detectar-contexto.sh [caminho-do-repo]
set -uo pipefail

repo="$(cd "${1:-$PWD}" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null)" || true
if [ -z "${repo:-}" ]; then
  echo "ERRO: não estou dentro de um repositório git (${1:-$PWD})" >&2
  exit 1
fi
name="$(basename "$repo")"
parent="$(dirname "$repo")"

echo "## repo"
echo "caminho:        $repo"
echo "nome:           $name"
echo "pai:            $parent"
echo "branch atual:   $(git -C "$repo" branch --show-current 2>/dev/null || echo '(detached)')"
echo "é worktree:     $([ -f "$repo/.git" ] && echo sim || echo 'não (clone principal)')"

echo
echo "## orca"
echo "TERM_PROGRAM:       ${TERM_PROGRAM:-<vazio>}"
echo "ORCA_WORKTREE_ID:   ${ORCA_WORKTREE_ID:-<vazio>}"
if [ -n "${TERM_PROGRAM:-}" ] && [ "${TERM_PROGRAM:-}" = "Orca" ] && [ -n "${ORCA_WORKTREE_ID:-}" ]; then
  echo "rota:               A (dentro do Orca — delegar)"
  echo "wt da sessão:       ${ORCA_WORKTREE_ID#*::}"
else
  echo "rota:               B (fora do Orca — EnterWorktree nesta sessão)"
fi
echo "executável:         ${ORCA_CLI_COMMAND:-<resolver pela skill orca-cli; em Linux fora do Orca use orca-ide, nunca orca nu>}"

echo
echo "## worktrees"
echo "base esperada:  $parent/worktrees  (o Orca aninha: $parent/worktrees/$name/<NOME_WT>)"
git -C "$repo" worktree list 2>/dev/null | sed 's/^/  /'

echo
echo "## base branch (NUNCA assumir)"
def="$(git -C "$repo" symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null | sed 's#.*/##')"
echo "default do remoto: ${def:-<desconhecido>}"
for b in main master staging develop; do
  git -C "$repo" show-ref --verify --quiet "refs/heads/$b" && echo "  existe local:  $b"
done
[ -n "${def:-}" ] && [ "$def" != "staging" ] && git -C "$repo" show-ref --verify --quiet refs/heads/staging \
  && echo "  ⚠️ GitFlow provável (default=$def + staging): PERGUNTE a base, não assuma"

echo
echo "## padrão de branch"
found=0
for f in "$repo/.githooks/pre-push" "$repo/.git/hooks/pre-push" "$repo/.husky/pre-push"; do
  [ -f "$f" ] || continue
  found=1
  echo "hook: ${f#$repo/}"
  grep -oE '\^\(?[a-z|]+\)?/[^"'"'"']*\$' "$f" 2>/dev/null | head -3 | sed 's/^/  regex: /'
done
[ -f "$repo/.claude/worktree-handoff.json" ] && { found=1; echo "config: .claude/worktree-handoff.json"; sed 's/^/  /' "$repo/.claude/worktree-handoff.json"; }
for f in CLAUDE.md CONTRIBUTING.md AGENTS.md docs/project-context.md; do
  [ -f "$repo/$f" ] || continue
  hits="$(grep -oE '(feature|bugfix|fix|hotfix|chore|refactor|docs)/[A-Za-z-]*[0-9<][^ `"'"'"']*' "$repo/$f" 2>/dev/null | sort -u | head -3)"
  [ -n "$hits" ] && { found=1; echo "exemplos em $f:"; echo "$hits" | sed 's/^/  /'; }
done
[ "$found" = 0 ] && echo "nenhum validador encontrado — pergunte o padrão ao usuário antes de inventar"

echo
echo "## gitignored no topo (candidatos a copiar para a worktree)"
git -C "$repo" ls-files --others --ignored --exclude-standard --directory 2>/dev/null \
  | grep -vE '^(node_modules|\.venv|venv|__pycache__|dist|build|target|\.mypy_cache|\.pytest_cache|\.ruff_cache)/' \
  | grep -E '^[^/]+/?$' | head -20 | sed 's/^/  /'
echo "  (sempre inclua .claude/ se existir — sem ele a sessão filha não enxerga as skills)"
