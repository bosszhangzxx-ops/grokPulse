#!/usr/bin/env bash
# Gate de implementação: edição de código só acontece numa worktree dedicada.
#
# PreToolUse em Edit|Write|MultiEdit|NotebookEdit. Se o arquivo alvo está no clone
# principal (git-dir == git-common-dir) e fora da allowlist de artefatos de processo,
# nega a chamada e manda invocar a skill `delegar-em-worktree`. Numa worktree linkada,
# ou fora de um repo git, libera.
#
# Escape consciente (trabalho deliberado no clone principal): GROKBOT_KIT_ALLOW_MAIN_EDIT=1.
set -uo pipefail

[ "${GROKBOT_KIT_ALLOW_MAIN_EDIT:-0}" = 1 ] && exit 0

input="$(cat)"
file="$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' <<<"$input")"
[ -z "$file" ] && exit 0

cwd="$(jq -r '.cwd // empty' <<<"$input")"
case "$file" in /*) ;; *) file="${cwd:-$PWD}/$file" ;; esac

# O arquivo pode não existir ainda: sobe até o primeiro diretório existente.
dir="$(dirname "$file")"
while [ ! -d "$dir" ] && [ "$dir" != / ]; do dir="$(dirname "$dir")"; done

top="$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)" || exit 0
gitdir="$(git -C "$dir" rev-parse --absolute-git-dir 2>/dev/null)"
common="$(cd "$dir" && cd "$(git rev-parse --git-common-dir)" && pwd -P)"

# Worktree linkada: gate cumprido.
[ "$gitdir" != "$common" ] && exit 0

# Clone principal: só artefatos de processo (specs, docs, config do agente).
rel="${file#"$top"/}"
case "$rel" in
  .claude/*|.agents/*|.specs/*|docs/*|CLAUDE.md|CLAUDE.local.md|AGENTS.md) exit 0 ;;
esac

reason="Gate de implementação: '$rel' está no clone principal ($top). Antes de editar código, invoque a skill delegar-em-worktree para criar a worktree dedicada da tarefa e mover/delegar a sessão. Só specs, docs e .claude/ são editáveis aqui. Trabalho deliberado no clone principal: GROKBOT_KIT_ALLOW_MAIN_EDIT=1."

jq -n --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
exit 0
