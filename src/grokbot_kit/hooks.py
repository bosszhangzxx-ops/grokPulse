"""Registro dos 9 hooks de progresso do Claude Code (patch local sobre 0.7.0).

Eventos: SessionStart, PreToolUse, PostToolUse, PostToolUseFailure, PostToolBatch, TaskCreated,
TaskCompleted, Notification e SessionEnd. O `emit` encaminha cada evento aqui e devolve `{}`: só
registramos, nunca decidimos (a decisão continua só no PermissionRequest) e nunca propaga exceção
para o Claude Code.

Três arquivos por task, no task dir (um log por task; sessions não se misturam porque cada linha
carrega `session_id`):

- `hooks.log`: linhas `[HOOK] <Evento> | task_id=... | session_id=... | ... | at=<rfc3339>`;
- `hooks-events.jsonl`: um objeto JSON por evento, para um painel de progresso em tempo real;
- `session-metrics.json`: tempos e tokens por session, mais as janelas por `claude_task_id`.

Tempos: o `SessionStart` grava `started_at`, o `SessionEnd` grava `ended_at` e
`duration_seconds = ended_at - started_at` (ambos do `at` do evento, RFC 3339).

Tokens: o agregado real de `message.usage` das entradas `assistant` do transcript da session
(`transcript_path` do hook), com os campos que o transcript traz: `input_tokens`, `output_tokens`,
`cache_creation_input_tokens` e `cache_read_input_tokens`, mais `total_tokens` (soma dos quatro),
`api_requests` (mensagens distintas com uso) e `thinking_tokens` (de `output_tokens_details`, já
incluído em `output_tokens`, por isso fora do `total_tokens`). O mesmo `message.id` aparece uma vez por bloco de
stream, com uso parcial no primeiro e completo no último: cada id conta uma vez, ficando a linha mais
cheia. Sem transcript legível os campos de contagem ficam de fora e `tokens.source = "unavailable"`:
nunca inventamos número. Por task do Claude (`TaskCreated`/`TaskCompleted`, `claude_task_id`)
gravamos o delta da janela quando há instantâneo nos dois eventos; sem ele, sem número.

Nunca gravamos conteúdo de arquivo, resposta de ferramenta, env nem segredos: só nomes de
ferramenta, ids, caminhos, e trechos curtos já truncados e redigidos (segurança: sem tokens).

Com `GROKBOT_SUPABASE_URL`/`GROKBOT_SUPABASE_ANON_KEY` (ou `SUPABASE_URL`/`SUPABASE_ANON_KEY`) na
ambiente, os mesmos tempos e contadores também vão para o Supabase via `supabase_sync` (upsert em
`claude_sessions`/`claude_tasks`); é best-effort — sem configuração fica desligado, com falha só
sobram linhas no `kit.log`."""

import json
import os
import re
from datetime import UTC, datetime
from typing import Any, cast

from . import supabase_sync

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
METRICS_SCHEMA = "grokbot-kit.session-metrics/v1"
METRICS_FILE = "session-metrics.json"
MAX_TEXT = 200
SAFE_VALUE = re.compile(r"^[A-Za-z0-9._:/=+-]+$")
# contadores reais de `message.usage` no transcript; `total_tokens` é a soma destes quatro
TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")

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


def _parse_at(value: object) -> datetime | None:
    """O timestamp RFC 3339 que gravamos, ou `None` quando não é um texto parseável."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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


def _usage(usage: object) -> dict[str, int] | None:
    """Os contadores de tokens não-negativos de um `message.usage`, ou `None` sem nenhum.

    Além dos quatro contadores de `TOKEN_KEYS`, guarda `thinking_tokens` quando o transcript traz
    `output_tokens_details` (raciocínio, já incluso em `output_tokens`; não soma em `total_tokens`)."""
    if not isinstance(usage, dict):
        return None
    counted: dict[str, int] = {}
    for key in TOKEN_KEYS:
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            counted[key] = value
    details = usage.get("output_tokens_details")
    if isinstance(details, dict):
        thinking = details.get("thinking_tokens")
        if isinstance(thinking, int) and not isinstance(thinking, bool) and thinking >= 0:
            counted["thinking_tokens"] = thinking
    return counted or None


def _usage_weight(usage: dict[str, int]) -> tuple[int, int]:
    """A linha mais cheia de um `message.id` vence: os blocos de stream repetem o id com uso parcial
    (sem `output_tokens` ainda); o desempate é a soma dos contadores."""
    return usage.get("output_tokens", 0), sum(usage.values())


def transcript_usage(path: object) -> dict[str, Any] | None:
    """O uso de tokens real da session somado do transcript JSONL do Claude Code, ou `None` ilegível.

    Cada entrada `assistant` traz `message.usage`; o mesmo `message.id` se repete por bloco de stream
    (o primeiro com `output_tokens` parcial) e conta uma vez, com a linha de uso mais completo. Com o
    arquivo legível mas sem nenhum uso registrado devolve `source: "unavailable"`, sem contagens."""
    if not isinstance(path, str) or not path:
        return None
    fullest: dict[str, dict[str, int]] = {}
    anonymous = 0
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict) or entry.get("type") != "assistant":
                    continue
                message = entry.get("message")
                message = message if isinstance(message, dict) else {}
                usage = _usage(message.get("usage"))
                if usage is None:
                    continue
                key = message.get("id")
                if not (isinstance(key, str) and key):
                    anonymous += 1
                    key = f"<anonymous:{anonymous}>"
                previous = fullest.get(key)
                if previous is None or _usage_weight(usage) > _usage_weight(previous):
                    fullest[key] = usage
    except OSError:
        return None
    if not fullest:
        return {"source": "unavailable", "reason": "no usage entries in transcript"}
    totals = {key: sum(u.get(key, 0) for u in fullest.values()) for key in TOKEN_KEYS}
    out: dict[str, Any] = {
        **totals,
        "total_tokens": sum(totals.values()),
        "api_requests": len(fullest),
        "source": "transcript",
    }
    thinking = [u["thinking_tokens"] for u in fullest.values() if "thinking_tokens" in u]
    if thinking:
        out["thinking_tokens"] = sum(thinking)
    return out


def _unavailable(reason: str) -> dict[str, str]:
    return {"source": "unavailable", "reason": reason}


def _counted(usage: object) -> bool:
    return isinstance(usage, dict) and any(isinstance(usage.get(key), int) for key in TOKEN_KEYS)


def _window_delta(started: object, ended: object) -> dict[str, Any] | None:
    """O delta entre dois instantâneos acumulados do transcript, ou `None` quando não fecha a conta."""
    if not (_counted(started) and _counted(ended)):
        return None
    begin_snap = cast("dict[str, Any]", started)
    end_snap = cast("dict[str, Any]", ended)
    delta: dict[str, Any] = {}
    for key in TOKEN_KEYS:
        begin, finish = int(begin_snap.get(key, 0)), int(end_snap.get(key, 0))
        if finish < begin:
            return None
        delta[key] = finish - begin
    delta["total_tokens"] = sum(int(delta[key]) for key in TOKEN_KEYS)
    begin_think, end_think = begin_snap.get("thinking_tokens"), end_snap.get("thinking_tokens")
    if isinstance(begin_think, int) and isinstance(end_think, int):
        if end_think < begin_think:
            return None
        delta["thinking_tokens"] = end_think - begin_think
    begin_req, finish_req = begin_snap.get("api_requests"), end_snap.get("api_requests")
    if isinstance(begin_req, int) and isinstance(finish_req, int) and finish_req >= begin_req:
        delta["api_requests"] = finish_req - begin_req
    delta["source"] = "transcript-window-delta"
    return delta


def _load_metrics(task_dir: str) -> dict[str, Any]:
    try:
        with open(os.path.join(task_dir, METRICS_FILE), encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("sessions"), dict) and isinstance(data.get("tasks"), dict):
            return cast("dict[str, Any]", data)
    except (OSError, ValueError):
        pass
    return {"schema": METRICS_SCHEMA, "sessions": {}, "tasks": {}}


def _save_metrics(task_dir: str, metrics: dict[str, Any]) -> None:
    """Troca atômica do arquivo inteiro: nunca fica pela metade."""
    final = os.path.join(task_dir, METRICS_FILE)
    tmp = f"{final}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, final)


def _snapshot(usage: dict[str, Any]) -> dict[str, int]:
    keys = (*TOKEN_KEYS, "api_requests", "thinking_tokens")
    return {key: int(usage[key]) for key in keys if isinstance(usage.get(key), int)}


def _enrich(record: dict[str, object], data: dict[str, object], task_dir: str) -> None:
    """Completa o registro com tempos e tokens e mantém o `session-metrics.json`; nunca propaga erro.

    Só os eventos de sessão e de task do Claude tocam o arquivo; os demais (ferramentas, notificações)
    não têm o que agregar e ficam só no log/jsonl."""
    event = record["event"]
    if event not in ("SessionStart", "SessionEnd", "TaskCreated", "TaskCompleted"):
        return
    metrics = _load_metrics(task_dir)
    sessions: dict[str, Any] = metrics["sessions"]
    tasks: dict[str, Any] = metrics["tasks"]
    session_id = record.get("session_id")
    key = session_id if isinstance(session_id, str) else "unknown"
    session: dict[str, Any] = sessions.setdefault(key, {"session_id": key})
    at = record["at"]
    if event == "SessionStart":
        record["started_at"] = at
        # uma session retomada (resume/compact) mantém o início mais antigo: a duração real é da primeira
        current, previous = _parse_at(at), _parse_at(session.get("started_at"))
        if current is not None and (previous is None or current < previous):
            session["started_at"] = at
        if isinstance(session.get("started_at"), str):
            # o record acompanha o início mais antigo: duração e `started_at` nunca discordam
            record["started_at"] = session["started_at"]
    elif event == "SessionEnd":
        record["ended_at"] = at
        session["ended_at"] = at
        started, ended = _parse_at(session.get("started_at")), _parse_at(at)
        if started is not None and ended is not None:
            record["duration_seconds"] = session["duration_seconds"] = round((ended - started).total_seconds(), 3)
        if record.get("reason") is not None:
            session["end_reason"] = record["reason"]
        tokens = transcript_usage(data.get("transcript_path"))
        if tokens is None:
            given = data.get("transcript_path")
            tokens = _unavailable(
                "transcript not readable" if isinstance(given, str) and given else "hook input has no transcript_path"
            )
        record["tokens"] = session["tokens"] = tokens
    elif event == "TaskCreated":
        claude_task_id = record.get("claude_task_id")
        if not isinstance(claude_task_id, str) or not claude_task_id:
            return
        task: dict[str, Any] = tasks.setdefault(claude_task_id, {"claude_task_id": claude_task_id})
        task["started_at"] = at
        record["started_at"] = at
        if record.get("subject") is not None:
            task["subject"] = record["subject"]
        usage = transcript_usage(data.get("transcript_path"))
        if usage is not None and _counted(usage):
            task["_snapshot"] = _snapshot(usage)
    elif event == "TaskCompleted":
        claude_task_id = record.get("claude_task_id")
        if not isinstance(claude_task_id, str) or not claude_task_id:
            return
        task = tasks.setdefault(claude_task_id, {"claude_task_id": claude_task_id})
        task["ended_at"] = at
        record["ended_at"] = at
        if isinstance(task.get("started_at"), str):
            record["started_at"] = task["started_at"]
        started, ended = _parse_at(task.get("started_at")), _parse_at(at)
        if started is not None and ended is not None:
            record["duration_seconds"] = task["duration_seconds"] = round((ended - started).total_seconds(), 3)
        snapshot = task.pop("_snapshot", None)
        delta = _window_delta(snapshot, transcript_usage(data.get("transcript_path")))
        if delta is not None:
            record["tokens"] = task["tokens"] = delta
    _save_metrics(task_dir, metrics)


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
        record["started_at"] = record["at"]
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
        record["ended_at"] = record["at"]
    return record


def _quote(value: object) -> str:
    if isinstance(value, str) and SAFE_VALUE.match(value):
        return value
    return json.dumps(value, ensure_ascii=False)


def _token_parts(tokens: object) -> list[str]:
    """Os contadores de `tokens` em pares `campo=valor`; sem contagem, sem parte."""
    if not isinstance(tokens, dict):
        return []
    parts = []
    for key in (*TOKEN_KEYS, "total_tokens", "api_requests", "thinking_tokens"):
        value = tokens.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            parts.append(f"{key}={value}")
    return parts


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
        parts.append(f"started_at={record['started_at']}")
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
        if event == "TaskCompleted":
            if record.get("duration_seconds") is not None:
                parts.append(f"duration_seconds={record['duration_seconds']}")
            parts.extend(_token_parts(record.get("tokens")))
    elif event == "Notification":
        parts.append(f"type={_quote(record.get('type'))}")
        if record.get("message") is not None:
            parts.append(f"message={_quote(record['message'])}")
    elif event == "SessionEnd":
        parts.append(f"reason={_quote(record.get('reason'))}")
        parts.append(f"ended_at={record['ended_at']}")
        if record.get("duration_seconds") is not None:
            parts.append(f"duration_seconds={record['duration_seconds']}")
        parts.extend(_token_parts(record.get("tokens")))
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
        try:
            _enrich(record, data, task_dir)
        except Exception as e:  # noqa: BLE001 - métrica é bônus; o registro do evento continua
            _log_kit(task_dir, f"cannot compute metrics for {record['event']!r}: {type(e).__name__}: {e}")
        line = build_line(record)
        _append(os.path.join(task_dir, "hooks.log"), line + "\n")
        _append(
            os.path.join(task_dir, "hooks-events.jsonl"),
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n",
        )
        try:
            # upsert no Supabase é bônus: gravamos o evento local antes e qualquer falha vira só log
            supabase_sync.sync(record, data, task_dir)
        except Exception as e:  # noqa: BLE001 - o hook nunca pode falhar a task
            _log_kit(task_dir, f"cannot sync {record['event']!r} to supabase: {type(e).__name__}: {e}")
    except Exception as e:  # noqa: BLE001 - o hook nunca pode falhar o agente
        name = data.get("hook_event_name") if isinstance(data, dict) else None
        _log_kit(task_dir, f"cannot record {name!r}: {type(e).__name__}: {e}")
