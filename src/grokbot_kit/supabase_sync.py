"""Sincronização best-effort das métricas de sessão/task para o Supabase (PostgREST).

Configuração por variáveis de ambiente (mesmos nomes de `kit-tasks/supabase.env`):
`GROKBOT_SUPABASE_URL` + `GROKBOT_SUPABASE_ANON_KEY`, com fallback para `SUPABASE_URL` +
`SUPABASE_ANON_KEY`. Sem configuração nada é enviado; com configuração, cada evento de ciclo de
vida (`SessionStart`, `SessionEnd`, `TaskCreated`, `TaskCompleted`) faz upsert de uma linha:

- `SessionStart`/`SessionEnd` → `claude_sessions` (conflito em `session_id`);
- `TaskCreated`/`TaskCompleted` → `claude_tasks` (conflito em `session_id,claude_task_id`).

O payload só leva contadores numéricos, ids, timestamps, modelo/cwd e o `subject` já truncado e
redigido por `hooks._clip`: nenhum conteúdo de arquivo, resposta de ferramenta, env ou segredo
sai daqui. Falha de rede/HTTP vira linha em `kit.log` e nunca propaga exceção para o hook."""

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

TABLE_SESSIONS = "claude_sessions"
TABLE_TASKS = "claude_tasks"
LIFECYCLE_EVENTS = ("SessionStart", "SessionEnd", "TaskCreated", "TaskCompleted")
TIMEOUT_SECONDS = 5.0
# `message.usage` do transcript → colunas das tabelas do Supabase
SESSION_TOKEN_COLUMNS = {
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cache_read_input_tokens": "cache_read_tokens",
    "cache_creation_input_tokens": "cache_creation_tokens",
    "total_tokens": "total_tokens",
}
TASK_TOKEN_COLUMNS = {
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "total_tokens": "total_tokens",
}


def _config() -> tuple[str, str] | None:
    """`(url, anon_key)` do projeto Supabase, ou `None` quando não configurado (sync desligado)."""
    url = os.environ.get("GROKBOT_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = os.environ.get("GROKBOT_SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    return url.rstrip("/"), key


def _log(task_dir: str, message: str) -> None:
    try:
        with open(os.path.join(task_dir, "kit.log"), "a", encoding="utf-8") as f:
            now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
            f.write(f"{now} supabase_sync: {message}\n")
    except OSError:
        pass


def _upsert(url: str, key: str, table: str, on_conflict: str, row: dict[str, Any]) -> None:
    """POST no PostgREST com `resolution=merge-duplicates`; levanta erro HTTP/URLError para o chamador."""
    request = urllib.request.Request(
        f"{url}/rest/v1/{table}?on_conflict={on_conflict}",
        data=json.dumps(row, ensure_ascii=False).encode("utf-8"),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        status = getattr(response, "status", 200)
        if not 200 <= int(status) < 300:
            raise urllib.error.HTTPError(request.full_url, int(status), "unexpected status", response.headers, None)


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _tokens(record: dict[str, object]) -> dict[str, int]:
    tokens = record.get("tokens")
    return tokens if isinstance(tokens, dict) else {}


def _token_fields(row: dict[str, Any], record: dict[str, object], columns: dict[str, str]) -> dict[str, Any]:
    """Contadores nas colunas próprias da tabela; o resto (cache, api_requests, thinking) vai em jsonb."""
    extra: dict[str, Any] = {}
    tokens = _tokens(record)
    for source, column in columns.items():
        counted = _int_or_none(tokens.get(source))
        if counted is not None:
            row[column] = counted
    for source, column in (
        ("cache_read_input_tokens", "cache_read_tokens"),
        ("cache_creation_input_tokens", "cache_creation_tokens"),
    ):
        counted = _int_or_none(tokens.get(source))
        if counted is not None and column not in row:
            extra[column] = counted
    for key in ("api_requests", "thinking_tokens"):
        counted = _int_or_none(tokens.get(key))
        if counted is not None:
            extra[key] = counted
    tokens_source = tokens.get("source")
    if isinstance(tokens_source, str):
        extra["tokens_source"] = tokens_source
    return extra


def _session_row(record: dict[str, object], data: dict[str, object]) -> dict[str, Any]:
    """A linha de `claude_sessions` do evento; `{}` quando não há `session_id` nem o que gravar."""
    event = record.get("event")
    session_id = record.get("session_id")
    if not isinstance(session_id, str) or not session_id or event not in ("SessionStart", "SessionEnd"):
        return {}
    row: dict[str, Any] = {
        "session_id": session_id,
        "kit_task_id": record.get("task_id"),
        "status": "ended" if event == "SessionEnd" else "running",
        "updated_at": record["at"],
    }
    for field, column in (("started_at", "started_at"), ("ended_at", "ended_at")):
        value = record.get(field)
        if isinstance(value, str):
            row[column] = value
    duration = record.get("duration_seconds")
    if isinstance(duration, int | float) and not isinstance(duration, bool):
        row["duration_seconds"] = duration
    model = record.get("model") if isinstance(record.get("model"), str) else data.get("model")
    if isinstance(model, str) and model:
        row["model"] = model
    cwd = data.get("cwd")
    if isinstance(cwd, str) and cwd:
        row["cwd"] = cwd
    summary = _token_fields(row, record, SESSION_TOKEN_COLUMNS)
    reason = record.get("reason")
    if isinstance(reason, str) and reason:
        summary["end_reason"] = reason
    if summary:
        row["summary"] = summary
    return row


def _task_row(record: dict[str, object], data: dict[str, object]) -> dict[str, Any]:
    """A linha de `claude_tasks` do evento; `{}` sem `claude_task_id` (não há conflito que upsert resolva)."""
    event = record.get("event")
    claude_task_id = record.get("claude_task_id")
    session_id = record.get("session_id")
    if not isinstance(claude_task_id, str) or not claude_task_id or event not in ("TaskCreated", "TaskCompleted"):
        return {}
    row: dict[str, Any] = {
        "session_id": session_id if isinstance(session_id, str) and session_id else "unknown",
        "claude_task_id": claude_task_id,
        "kit_task_id": record.get("task_id"),
        "status": "completed" if event == "TaskCompleted" else "running",
        "updated_at": record["at"],
    }
    for field, column in (("started_at", "started_at"), ("ended_at", "ended_at")):
        value = record.get(field)
        if isinstance(value, str):
            row[column] = value
    duration = record.get("duration_seconds")
    if isinstance(duration, int | float) and not isinstance(duration, bool):
        row["duration_seconds"] = duration
    subject = record.get("subject")
    if isinstance(subject, str) and subject:
        row["title"] = subject
    cwd = data.get("cwd")
    if isinstance(cwd, str) and cwd:
        row["meta"] = {"cwd": cwd}
    meta = _token_fields(row, record, TASK_TOKEN_COLUMNS)
    if meta:
        row.setdefault("meta", {}).update(meta)
    return row


def sync(record: dict[str, object], data: dict[str, object], task_dir: str) -> None:
    """Faz o upsert do evento de ciclo de vida no Supabase; nunca propaga exceção (só `kit.log`).

    Eventos de ferramenta/notificação não têm linha própria e voltam sem rede; sem URL/chave na
    ambiente o sync fica desligado, silencioso. O `record` é o mesmo (já enriquecido) do log."""
    try:
        if record.get("event") not in LIFECYCLE_EVENTS:
            return
        config = _config()
        if config is None:
            return
        url, key = config
        if record.get("event") in ("SessionStart", "SessionEnd"):
            row = _session_row(record, data)
            if row:
                _upsert(url, key, TABLE_SESSIONS, "session_id", row)
        else:
            row = _task_row(record, data)
            if row:
                _upsert(url, key, TABLE_TASKS, "session_id,claude_task_id", row)
    except Exception as e:  # noqa: BLE001 - sync é bônus; o registro local do evento continua
        _log(task_dir, f"cannot upsert {record.get('event')!r} to supabase: {type(e).__name__}: {e}")
