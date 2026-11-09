#!/usr/bin/env bash
# Copia para a worktree os arquivos gitignored que o checkout não traz, e cria os dirs
# exigidos por volume mount. Idempotente. Uso: setup-worktree.sh <repo> <worktree> [extras...]
#
# A lista vem de .claude/worktree-handoff.json ("copy"/"mkdir") quando existir; senão usa os
# defaults abaixo. Extras na linha de comando são sempre somados.
set -uo pipefail

repo="${1:?uso: setup-worktree.sh <repo> <worktree> [extras...]}"
wt="${2:?uso: setup-worktree.sh <repo> <worktree> [extras...]}"
shift 2
repo="$(cd "$repo" && pwd)"; wt="$(cd "$wt" && pwd)"
[ "$repo" = "$wt" ] && { echo "ERRO: repo e worktree são o mesmo diretório" >&2; exit 1; }

cfg="$repo/.claude/worktree-handoff.json"
copy=(); mkdirs=()
if [ -f "$cfg" ] && command -v python3 >/dev/null 2>&1; then
  while IFS= read -r l; do [ -n "$l" ] && copy+=("$l"); done < <(python3 -c 'import json,sys
d=json.load(open(sys.argv[1]));print("\n".join(d.get("copy",[])))' "$cfg" 2>/dev/null)
  while IFS= read -r l; do [ -n "$l" ] && mkdirs+=("$l"); done < <(python3 -c 'import json,sys
d=json.load(open(sys.argv[1]));print("\n".join(d.get("mkdir",[])))' "$cfg" 2>/dev/null)
fi
[ ${#copy[@]} -eq 0 ] && copy=(.env .claude CLAUDE.local.md .env.local)
[ ${#mkdirs[@]} -eq 0 ] && mkdirs=(logs)
copy+=("$@")

for item in "${copy[@]}"; do
  src="$repo/$item"; dst="$wt/$item"
  if [ ! -e "$src" ]; then echo "  skip  $item (não existe no repo)"; continue; fi
  if [ -e "$dst" ]; then echo "  já ok $item"; continue; fi
  mkdir -p "$(dirname "$dst")"
  if cp -r "$src" "$dst" 2>/dev/null; then echo "  copia $item"; else echo "  FALHA $item" >&2; fi
done
for d in "${mkdirs[@]}"; do mkdir -p "$wt/$d" && echo "  mkdir $d"; done

echo
echo "worktree pronta: $wt"
echo "⚠️ Se um agente já bootou nesta worktree, a cópia do .claude/ chegou TARDE para ele:"
echo "   o registro de skills só carrega no boot. Mande no prompt o fallback de ler"
echo "   .claude/skills/<skill>/SKILL.md na mão."
