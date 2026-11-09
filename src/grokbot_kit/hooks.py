"""Registro dos 9 hooks de progresso do Claude Code (patch local sobre 0.7.0).

Eventos: SessionStart, PreToolUse, PostToolUse, PostToolUseFailure, PostToolBatch, TaskCreated,
TaskCompleted, Notification e SessionEnd. O `emit` encaminha cada evento aqui e devolve `{}`: só
registramos, nunca decidimos (a decisão continua só no PermissionRequest) e nunca propaga exceção
para o Claude Code.

Dois arquivos por task, no task dir (um log por task; sessions não se misturam porque cada linha
carrega `session_id`):

- `hooks.log`: linhas `[HOOK] <Evento> | task_id=... | session_id=... | ... | at=<rfc3339>`;
- `hooks-events.jsonl`: um objeto JSON por evento, para um painel de progresso em tempo real.

Nunca gravamos conteúdo de arquivo, resposta de ferramenta, env nem segredos: só nomes de
ferramenta, ids, caminhos, e trechos curtos já truncados e redigidos (segurança: sem tokens)."""

import json
import os
import re
from datetime import UTC, datetime

EVENTS = (
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
SCHEMA = "grokbot-kit.hook/v1"
MAX_TEXT = 200
SAFE_VALUE = re.compile(r"^[A-Za-z0-9._:/=+-]+$")

# trechos que parecem segredo viram `<redacted>` (a chave continua visível para diagnóstico);
# o `bearer` primeiro, senão o valor dele escapa da regra de `chave=valor`
_REDACTIONS = (
    re.compile(r"(?i)\b(bearer)\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password|passwd|authorization)\b(\s*[=:]\s*|\s+)\S+"),
    re.compile(r"\b(?:sk|crsr|sk-ant)-[A-Za-z0-9_-]{8,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{8,}"),
)


def rfc3339(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _redact(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        if (match.lastindex or 0) >= 2:
            return f"{match.group(1)}{match.group(2)}<redacted>"
        return "<redacted>"

    for pattern in _REDACTIONS:
        text = pattern.sub(repl, text)
    return text


def _clip(value: object, limit: int = MAX_TEXT) -> str | None:
    """Texto curto, sem quebras de linha, truncado e redigido; `None` para vazio ou não-texto."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = _redact(" ".join(value.split()))
    return text if len(text) <= limit else text[:limit] + f"... [+{len(text) - limit} chars]"


def _detail(tool_input: object) -> str | None:
    """O alvo da ferramenta (comando, caminho, URL, padrão) — nunca `content`/`old_string`/`new_string`."""
    if isinstance(tool_input, dict):
        for key in ("command", "file_path", "path", "url", "pattern", "query", "prompt"):
            found = _clip(tool_input.get(key))
            if found is not None:
                return found
        return None
    return _clip(tool_input)


def build_record(data: dict[str, object], task_id: str) -> dict[str, object]:
    """O evento recebido em campos próprios do `grokbot-kit.hook/v1`, com tolerância a entradas estranhas."""
    event = str(data.get("hook_event_name") or "unknown")
    record: dict[str, object] = {
        "schema": SCHEMA,
        "at": rfc3339(datetime.now(UTC)),
        "event": event,
        "task_id": task_id,
        "session_id": data.get("session_id") if isinstance(data.get("session_id"), str) else None,
    }
    for key in ("prompt_id", "permission_mode", "agent_id", "agent_type", "transcript_path"):
        value = data.get(key)
        if isinstance(value, str) and value:
            record[key] = value
    if event == "SessionStart":
        record["source"] = data.get("source")
        model = _clip(data.get("model"), 100)
        if model:
            record["model"] = model
    elif event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        record["tool_name"] = data.get("tool_name") if isinstance(data.get("tool_name"), str) else None
        record["tool_use_id"] = data.get("tool_use_id") if isinstance(data.get("tool_use_id"), str) else None
        detail = _detail(data.get("tool_input"))
        if detail is not None:
            record["detail"] = detail
        if event == "PostToolUse":
            record["status"] = "success"
        elif event == "PostToolUseFailure":
            record["status"] = "failed"
            error = _clip(data.get("error"))
            if error is not None:
                record["error"] = error
            if isinstance(data.get("is_interrupt"), bool):
                record["is_interrupt"] = data["is_interrupt"]
        duration = data.get("duration_ms")
        if isinstance(duration, int | float) and not isinstance(duration, bool):
            record["duration_ms"] = duration
    elif event == "PostToolBatch":
        calls = data.get("tool_calls")
        calls = calls if isinstance(calls, list) else []
        tools: list[str] = []
        ids: list[str] = []
        for call in calls:
            if not isinstance(call, dict):
                continue
            name = call.get("tool_name")
            if isinstance(name, str) and name not in tools:
                tools.append(name)
            use_id = call.get("tool_use_id")
            if isinstance(use_id, str):
                ids.append(use_id)
        record["count"] = len(calls)
        record["tools"] = tools
        if ids:
            record["tool_use_ids"] = ids[:16]
    elif event in ("TaskCreated", "TaskCompleted"):
        # `task_id` do evento é o id da ferramenta de tasks do Claude (ex.: task-001), não o da task do kit
        inner = data.get("task_id")
        if isinstance(inner, str) and inner:
            record["claude_task_id"] = inner
        subject = _clip(data.get("task_subject"))
        if subject is not None:
            record["subject"] = subject
    elif event == "Notification":
        record["type"] = data.get("notification_type") if isinstance(data.get("notification_type"), str) else None
        message = _clip(data.get("message"))
        if message is not None:
            record["message"] = message
    elif event == "SessionEnd":
        record["reason"] = data.get("reason") if isinstance(data.get("reason"), str) else None
    return record


def _quote(value: object) -> str:
    if isinstance(value, str) and SAFE_VALUE.match(value):
        return value
    return json.dumps(value, ensure_ascii=False)


def build_line(record: dict[str, object]) -> str:
    """A linha `[HOOK] ...` do `hooks.log`, no formato de referência da tarefa."""
    parts = [f"[HOOK] {record['event']}", f"task_id={record['task_id']}"]
    session = record.get("session_id")
    parts.append(f"session_id={session if isinstance(session, str) else 'unknown'}")
    event = record["event"]
    if event == "SessionStart":
        parts.append(f"source={_quote(record.get('source'))}")
        if record.get("model"):
            parts.append(f"model={_quote(record['model'])}")
    elif event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        parts.append(f"tool={_quote(record.get('tool_name'))}")
        parts.append(f"tool_use_id={_quote(record.get('tool_use_id'))}")
        if event == "PostToolUse":
            parts.append("status=success")
        elif event == "PostToolUseFailure":
            parts.append("status=failed")
        if record.get("duration_ms") is not None:
            parts.append(f"duration={record['duration_ms']}ms")
        if record.get("error") is not None:
            parts.append(f"error={_quote(record['error'])}")
        elif record.get("detail") is not None:
            parts.append(f"detail={_quote(record['detail'])}")
    elif event == "PostToolBatch":
        parts.append(f"count={record['count']}")
        parts.append(f"tools={','.join(record['tools'])}")  # type: ignore[arg-type]
    elif event in ("TaskCreated", "TaskCompleted"):
        if record.get("claude_task_id"):
            parts.append(f"claude_task_id={_quote(record['claude_task_id'])}")
        if record.get("subject") is not None:
            parts.append(f"subject={_quote(record['subject'])}")
    elif event == "Notification":
        parts.append(f"type={_quote(record.get('type'))}")
        if record.get("message") is not None:
            parts.append(f"message={_quote(record['message'])}")
    elif event == "SessionEnd":
        parts.append(f"reason={_quote(record.get('reason'))}")
    parts.append(f"at={record['at']}")
    return " | ".join(parts)


def _append(path: str, text: str) -> None:
    """Uma escrita `O_APPEND` por linha: eventos concorrentes (ferramentas em paralelo) não se misturam."""
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)


def _log_kit(task_dir: str, message: str) -> None:
    try:
        with open(os.path.join(task_dir, "kit.log"), "a", encoding="utf-8") as f:
            f.write(f"{rfc3339(datetime.now(UTC))} hooks: {message}\n")
    except OSError:
        pass


def handle(data: object, task_id: str, task_dir: str) -> None:
    """Registra um evento de hook na task; engole qualquer erro (o hook nunca pode falhar a task)."""
    try:
        if not isinstance(data, dict):
            raise TypeError(f"hook input is {type(data).__name__}, not an object")
        os.makedirs(task_dir, mode=0o700, exist_ok=True)
        record = build_record(data, task_id)
        line = build_line(record)
        _append(os.path.join(task_dir, "hooks.log"), line + "\n")
        _append(
            os.path.join(task_dir, "hooks-events.jsonl"),
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n",
        )
    except Exception as e:  # noqa: BLE001 - o hook nunca pode falhar o agente
        name = data.get("hook_event_name") if isinstance(data, dict) else None
        _log_kit(task_dir, f"cannot record {name!r}: {type(e).__name__}: {e}")
