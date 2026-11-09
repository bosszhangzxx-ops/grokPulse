"""Status terminal de uma task a partir do exit e da saída do agente (AC 43-46, 51, 87, 88)."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUMMARY_LIMIT = 2000


@dataclass(frozen=True)
class AgentOutput:
    error: bool
    permission_denied: bool
    summary: str
    session_id: str | None = None


def _json_objects(text: str) -> list[dict[str, Any]]:
    objects = []
    for line in text.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            objects.append(obj)
    return objects


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def _error_message(tool: str, objects: list[dict[str, Any]]) -> str:
    """A mensagem do último erro da saída do opencode ou do codex (door 6 da model-setup-docs); `""` sem erro."""
    for obj in reversed(objects):
        kind = obj.get("type")
        if tool == "opencode" and kind == "error" and isinstance(obj.get("error"), dict):
            error = obj["error"]
            data = error.get("data")
            name = error.get("name") or error.get("type")
            message = data.get("message") if isinstance(data, dict) else None
            message = message or error.get("message")
            return ": ".join(p for p in (name, message) if isinstance(p, str) and p)
        if tool == "codex" and kind == "turn.failed" and isinstance(obj.get("error"), dict):
            message = obj["error"].get("message")
            return message if isinstance(message, str) else ""
        if tool == "codex" and kind == "error":
            message = obj.get("message")
            return message if isinstance(message, str) else ""
    return ""


def read_output(tool: str, task_dir: Path) -> AgentOutput:
    """Lê `out.jsonl` (e `last-message.txt` do codex) do task dir."""
    objects = _json_objects(_read(task_dir / "out.jsonl"))
    error = denied = False
    summary = ""
    session_id = None
    if tool == "claude":
        results = [o for o in objects if o.get("type") == "result"] or objects
        if results:
            result = results[-1]
            error = result.get("is_error") is True
            denied = bool(result.get("permission_denials"))
            text = result.get("result")
            summary = text if isinstance(text, str) else ""
            session_id = result.get("session_id")
    elif tool == "codex":
        error = any(o.get("type") in ("turn.failed", "error") for o in objects)
        summary = _read(task_dir / "last-message.txt") or _error_message(tool, objects)
        session_id = next((o.get("thread_id") for o in objects if o.get("type") == "thread.started"), None)
    elif tool == "opencode":
        error = any(o.get("type") == "error" for o in objects)
        texts = [o["part"].get("text") for o in objects if o.get("type") == "text" and isinstance(o.get("part"), dict)]
        texts = [t for t in texts if isinstance(t, str)]
        summary = texts[-1] if texts else _error_message(tool, objects)
        session_id = next((o["sessionID"] for o in objects if o.get("sessionID")), None)
    return AgentOutput(
        error=error,
        permission_denied=denied,
        summary=summary[:SUMMARY_LIMIT],
        session_id=session_id if isinstance(session_id, str) and session_id else None,
    )


def fallback_eligible(tool: str, task_dir: Path, stopped: str | None) -> bool:
    """A tentativa falhou no provedor antes de qualquer ferramenta e pode ir para o próximo id do tier (door 4 da
    model-setup-docs). O codex nunca: nenhuma saída de erro de provedor dele foi observada."""
    if stopped is not None:
        return False
    objects = _json_objects(_read(task_dir / "out.jsonl"))
    if tool == "opencode":
        kinds = {o.get("type") for o in objects}
        return "error" in kinds and "tool_use" not in kinds
    if tool == "claude":
        results = [o for o in objects if o.get("type") == "result"]
        if not results:
            return False
        result = results[-1]
        turns = result.get("num_turns")
        return (
            result.get("is_error") is True
            and result.get("terminal_reason") == "api_error"
            and isinstance(turns, int)
            and turns <= 1
        )
    return False


def unanswered(task_dir: Path, asked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Os `needs_input` sem `allow` gravado em `replies/` (AC 27 e 28 da needs-input-reply): sem resposta, com `deny`
    do usuário ou do bot, ou negados pelo prazo."""
    from grokbot_kit.emit import read_reply

    left = []
    for event in asked:
        info = event.get("needs_input")
        request_id = info.get("request_id") if isinstance(info, dict) else None
        reply = read_reply(task_dir / "replies" / f"{request_id}.json") if isinstance(request_id, str) else None
        if reply is None or reply["decision"] != "allow":
            left.append(event)
    return left


def classify(
    exit_code: int,
    output: AgentOutput,
    *,
    needs_input: bool,
    stopped: str | None = None,
    plugin: bool = False,
    result_valid: bool = False,
) -> tuple[str, str, str]:
    """`(event, status, exit_reason)`; timeout e interrupção (`stopped`) vencem tudo, erro na saída vence exit
    diferente de 0, e os dois vencem `denied`. Numa tarefa de plugin (AC 41-45) não há `denied`: depois dessas
    linhas vale o resultado, `success` se válido e `result_invalid` se não."""
    if stopped == "timeout":
        return "timeout", "timeout", "timeout"
    if stopped == "interrupted":
        return "error", "interrupted", "interrupted"
    if output.error:
        return "error", "failed", "agent_error"
    if exit_code != 0:
        return "error", "failed", "nonzero_exit"
    if plugin:
        return ("completed", "ok", "success") if result_valid else ("error", "failed", "result_invalid")
    if needs_input or output.permission_denied:
        return "completed", "denied", "permission_denied"
    return "completed", "ok", "success"
