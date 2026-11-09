"""Linha de comando de cada CLI de agente (AC 40-42, doors 7 e 13)."""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

TOOLS = ("opencode", "claude", "codex")
DEFAULT_CODEX_HOME = "~/.grokbot-kit/codex-home"


def kit_executable() -> str:
    """Caminho absoluto do executável `grokbot-kit` que os hooks chamam (door 6)."""
    argv0 = sys.argv[0]
    if os.path.basename(argv0) == "grokbot-kit":
        return os.path.abspath(argv0)
    found = shutil.which("grokbot-kit")
    return os.path.abspath(found or argv0)


def emit_command(kit_exe: str, tool: str) -> str:
    return f"{shlex.quote(kit_exe)} emit --from {tool}"


# os 9 hooks de progresso do Claude Code registrados além do PermissionRequest (patch local sobre 0.7.0)
PROGRESS_HOOK_EVENTS = (
    "SessionStart",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "PostToolBatch",
    "TaskCreated",
    "TaskCompleted",
    "Notification",
    "SessionEnd",
)
# sem suporte a matcher: o matcher seria ignorado em silêncio (ver documentação de hooks)
NO_MATCHER_EVENTS = ("PostToolBatch", "TaskCreated", "TaskCompleted")
# o SessionEnd tem orçamento de 1.5 s por padrão; o timeout do handler sobe o orçamento até 60 s
SESSION_END_TIMEOUT = 30


def claude_settings(kit_exe: str, ask_wait: int = 0) -> dict[str, Any]:
    """Os hooks do Claude da task: o `PermissionRequest` de sempre (espera o `reply`, com `timeout`
    acima da espera em 60 s, AC 1 da needs-input-reply) e os 9 hooks de progresso, todos apontando
    para o mesmo `emit --from claude`, que só registra em `hooks.log`/`hooks-events.jsonl`."""
    hook: dict[str, Any] = {"type": "command", "command": emit_command(kit_exe, "claude")}
    if ask_wait > 0:
        hook["timeout"] = ask_wait + 60
    events: dict[str, Any] = {"PermissionRequest": [{"matcher": "*", "hooks": [hook]}]}
    for name in PROGRESS_HOOK_EVENTS:
        handler: dict[str, Any] = {"type": "command", "command": emit_command(kit_exe, "claude")}
        if name == "SessionEnd":
            handler["timeout"] = SESSION_END_TIMEOUT
        group: dict[str, Any] = {"hooks": [handler]}
        if name not in NO_MATCHER_EVENTS:
            group["matcher"] = "*"
        events[name] = [group]
    return {"hooks": events}


def codex_hooks_override(kit_exe: str) -> str:
    command = json.dumps(emit_command(kit_exe, "codex"))
    return f'hooks.PermissionRequest=[{{hooks=[{{type="command",command={command}}}]}}]'


CLAUDE_PLUGIN_TOOLS = ("Read", "Glob", "Grep", "Edit", "Write", "Skill")


class Harness(NamedTuple):
    """O que a CLI recebe numa tarefa de plugin para impor as capacidades (door 8): argumentos antes do prompt,
    variáveis de ambiente e, no Claude, as `permissions` do `claude-settings.json`."""

    args: list[str]
    env: dict[str, str]
    permissions: dict[str, list[str]]


def plugin_harness(tool: str, caps: dict[str, Any], task_dir: Path, plugin_dir: Path, major: int | None) -> Harness:
    """Harness da linha da door 8 para `tool`; `major` é a versão principal da CLI (o opencode 2 pede `--standalone`).

    `write` vale para as ferramentas de arquivo; o resultado (`<task_dir>/result.json`) é sempre gravável. O shell só
    roda os prefixos de `commands`, com ou sem argumentos. A config do workspace não carrega e as skills do plugin sim,
    pela própria CLI; o agente lê a cópia do plugin em `plugin_dir` (uma skill lê os arquivos de apoio da pasta dela), mas
    não a altera.
    """
    commands: list[str] = caps["commands"]
    result_file = str(task_dir / "result.json")
    if tool == "claude":
        writable = f"//{str(task_dir).lstrip('/')}/**" if caps["write"] == "task-dir" else "/" + result_file
        allow = [f"{verb}({writable})" for verb in ("Edit", "Write")]
        allow += [rule for prefix in commands for rule in (f"Bash({prefix})", f"Bash({prefix} *)")]
        hidden = f"//{str(plugin_dir).lstrip('/')}/**"
        deny = [f"{verb}({hidden})" for verb in ("Edit", "Write")]
        deny += ["WebFetch", "WebSearch"] if caps["network"] == "off" else []
        # `git log|diff|show --output=<fora>` escreveria fora do task dir com um prefixo liberado (door 11)
        deny += ["Bash(*--output*)"] if commands else []
        tools = [*CLAUDE_PLUGIN_TOOLS, "Bash"] if commands else list(CLAUDE_PLUGIN_TOOLS)
        args = ["--restricted", "--strict-mcp-config", "--tools", ",".join(tools), "--add-dir", str(task_dir)]
        # `--permission-mode` por último: `--add-dir` e `--plugin-dir` são variádicos e engoliriam o prompt
        args += ["--plugin-dir", str(plugin_dir), "--permission-mode", "dontAsk"]
        return Harness(args, {}, {"allow": allow, "deny": deny})
    if tool == "opencode":
        edit = (
            {"*": "allow", f"{plugin_dir}/*": "deny"}
            if caps["write"] == "task-dir"
            else {"*": "deny", result_file: "allow"}
        )
        # vale a última regra que casa: `>` e `--output` por último, senão `<prefixo> ... > <fora>` escreve fora (doors 10 e 11)
        bash = {
            "*": "deny",
            **{p: "allow" for prefix in commands for p in (prefix, f"{prefix} *")},
            "*>*": "deny",
            "*--output*": "deny",
        }
        permission = {
            "edit": edit,
            "external_directory": {"*": "deny", f"{task_dir}/*": "allow"},
            "bash": bash,
            "skill": "allow",
        }
        if caps["network"] == "off":
            permission.update(webfetch="deny", websearch="deny")
        content = {"permission": permission, "skills": {"paths": [str(plugin_dir / "skills")]}}
        env = {
            "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
            "OPENCODE_DISABLE_CLAUDE_CODE_SKILLS": "1",
            "OPENCODE_CONFIG_CONTENT": json.dumps(content),
        }
        # no opencode 2 o `run` usa um serviço compartilhado, que não lê o env desta tarefa
        return Harness(["--standalone"] if major is not None and major >= 2 else [], env, {})
    raise ValueError(f"{tool} has no plugin harness")


def cli_major(bin_path: str) -> int | None:
    """Versão principal impressa por `<cli> --version` (`opencode v2.1.3` -> 2), ou `None`."""
    try:
        out = subprocess.run(
            [bin_path, "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30, check=False
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"(\d+)\.\d+", out)
    return int(match.group(1)) if match else None


def agent_argv(tool: str, bin_path: str, model: str, task_dir: Path, kit_exe: str, extras: list[str]) -> list[str]:
    if tool == "claude":
        settings = str(task_dir / "claude-settings.json")
        head = ["-p", "--output-format", "json", "--model", model, "--settings", settings]
    elif tool == "opencode":
        head = ["run", "--format", "json", "-m", model]
    elif tool == "codex":
        last_message = str(task_dir / "last-message.txt")
        head = ["exec", "--json", "-m", model, "-o", last_message, "--dangerously-bypass-hook-trust"]
        head += ["-c", codex_hooks_override(kit_exe)]
    else:
        raise ValueError(f"unknown tool: {tool}")
    return [bin_path, *head, *extras]
