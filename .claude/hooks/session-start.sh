#!/usr/bin/env bash
# Início de sessão (SessionStart): instala os hooks git se faltarem e avisa de um CLAUDE.md que esconde o AGENTS.md.
#
# Sem `commit-msg` no diretório de hooks do repositório, roda `uv run pre-commit install` na raiz (AC 9). Um
# `CLAUDE.md` ou `CLAUDE.local.md` na raiz faz o Claude Code não ler o `AGENTS.md` (AC 32, door 8). Cada resultado
# vira uma linha em `additionalContext`. Nunca falha a sessão: sai sempre com 0.
set -uo pipefail

input="$(cat)"
cwd="$(jq -r '.cwd // empty' <<<"$input" 2>/dev/null)"
dir="${CLAUDE_PROJECT_DIR:-${cwd:-$PWD}}"
top="$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)" || exit 0
hooks="$(cd "$top" && git rev-parse --git-path hooks)"
case "$hooks" in /*) ;; *) hooks="$top/$hooks" ;; esac

lines=()
if [ ! -e "$hooks/commit-msg" ]; then
  if out="$(cd "$top" && uv run pre-commit install 2>&1)"; then
    lines+=("git hooks installed: uv run pre-commit install (pre-commit, commit-msg, pre-push)")
  else
    lines+=("git hooks not installed: uv run pre-commit install failed ($(tail -n 1 <<<"$out")); run it by hand")
  fi
fi
if [ -e "$top/CLAUDE.md" ] || [ -e "$top/CLAUDE.local.md" ]; then
  lines+=("CLAUDE.md or CLAUDE.local.md found: AGENTS.md is not loaded; move its content to AGENTS.md")
fi

[ "${#lines[@]}" = 0 ] && exit 0
context="$(printf '%s\n' "${lines[@]}")"
jq -n --arg c "$context" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$c}}'
exit 0
