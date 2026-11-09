"""`grokbot-kit emit`: chamado pelos hooks dos agentes dentro de uma task (AC 54-63).

Antes do gate de `GROKBOT_KIT_TASK_ID` só entram `os`, `sys` e `json` (door 6); o resto é carregado sob demanda.
O emit nunca envia evento terminal (door 5): só `needs_input`, normalizado de cada fonte (door 14). Em qualquer
caso sai com `0`; erros vão para o `kit.log`. Sem decisão, escreve `{}` em stdout (o Codex exige JSON em alguns
eventos). Com espera (needs-input-reply, doors 1, 6 e 8), segura o pedido de permissão até
`<task_dir>/replies/<request_id>.json` aparecer ou o prazo vencer, e escreve a decisão no formato da CLI.
"""

import json
import os
import sys

TYPE_CHECKING = False
if TYPE_CHECKING:
    from datetime import datetime

SOURCES = ("opencode", "claude", "codex")
POLL_SECONDS = 0.2
DECISIONS = ("allow", "deny")
_SAFE_ID = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")


def _hash(*parts: object) -> str:
    import hashlib

    canonical = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _discriminator(request_id: object, tool_name: object, tool_input: object) -> str:
    if isinstance(request_id, str) and request_id and set(request_id) <= _SAFE_ID:
        return request_id
    if isinstance(request_id, str) and request_id:
        return _hash(request_id)
    return _hash(tool_name, tool_input)


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _detail(tool_input: object) -> str | None:
    if isinstance(tool_input, dict):
        for key in ("command", "file_path", "path"):
            if isinstance(tool_input.get(key), str):
                return str(tool_input[key])
    return json.dumps(tool_input, ensure_ascii=False) if tool_input is not None else None


def normalize(source: str, data: object) -> dict[str, str | None] | None:
    """O `needs_input` que o JSON do hook representa, ou `None` quando o hook não é um pedido ao usuário."""
    if not isinstance(data, dict):
        return None
    if source in ("claude", "codex"):
        if data.get("hook_event_name") != "PermissionRequest" or not _str(data.get("tool_name")):
            return None
        tool_input = data.get("tool_input")
        return {
            "kind": "permission",
            "tool_name": data["tool_name"],
            "detail": _detail(tool_input),
            "discriminator": _discriminator(data.get("tool_use_id"), data["tool_name"], tool_input),
            "session_id": _str(data.get("session_id")),
            "transcript_path": _str(data.get("transcript_path")),
        }
    if source == "opencode":
        props = data.get("properties")
        if not isinstance(props, dict):
            return None
        if data.get("type") == "permission.asked":
            if data.get("parentID"):
                return None
            patterns = props.get("patterns")
            detail = ", ".join(p for p in patterns if isinstance(p, str)) if isinstance(patterns, list) else None
            kind, tool_name = "permission", _str(props.get("permission"))
        elif data.get("type") == "question.asked":
            questions = props.get("questions")
            first = questions[0] if isinstance(questions, list) and questions else None
            detail = _str(first.get("question")) if isinstance(first, dict) else None
            kind, tool_name = "question", None
        else:
            return None
        return {
            "kind": kind,
            "tool_name": tool_name,
            "detail": detail or None,
            "discriminator": _discriminator(props.get("id"), tool_name, props),
            "session_id": _str(props.get("sessionID")),
            "transcript_path": None,
        }
    return None


def _log(task_dir: str, message: str) -> None:
    from datetime import UTC, datetime

    try:
        with open(os.path.join(task_dir, "kit.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')} emit: {message}\n")
    except OSError:
        pass


def write_once(path: "os.PathLike[str] | str", body: dict[str, object]) -> bool:
    """Cria `path` com `body` de uma vez (door 1): grava num temporário e o liga ao nome final, que falha se ele já
    existe; quem chega depois recebe `False` e lê o que está lá, então nunca há arquivo pela metade nem sobrescrito."""
    import secrets

    directory = os.path.dirname(os.fspath(path))
    os.makedirs(directory, mode=0o700, exist_ok=True)
    tmp = os.path.join(directory, f".{os.path.basename(path)}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False)
    try:
        os.link(tmp, path)
    except FileExistsError:
        return False
    finally:
        os.unlink(tmp)
    return True


def read_reply(path: "os.PathLike[str] | str") -> dict[str, object] | None:
    """A resposta gravada em `path` (door 1), ou `None` quando ela não é um objeto com `decision` válida."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("decision") not in DECISIONS:
        return None
    message = data.get("message")
    return {**data, "message": message if isinstance(message, str) else None}


def _answer(source: str, reply: dict[str, object] | None) -> str:
    """A decisão no formato de cada CLI (door 6); `{}` sem decisão."""
    if reply is None:
        return "{}"
    allow = reply["decision"] == "allow"
    message = reply.get("message") or None
    if source == "opencode":
        out: dict[str, object] = {"effect": reply["decision"], "message": None if allow else message}
    else:
        decision: dict[str, object] = {"behavior": "allow"}
        if not allow:
            decision = {"behavior": "deny", "message": message or "denied by the user"}
        out = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def _can_wait(source: str, kind: object) -> bool:
    """Door 8: o Claude sempre; o opencode só pelo plugin v2, que passa `GROKBOT_KIT_REPLY=1`; o Codex nunca."""
    if kind != "permission":
        return False
    return source == "claude" or (source == "opencode" and os.environ.get("GROKBOT_KIT_REPLY") == "1")


def _wait_reply(path: str, deadline: "datetime", deadline_text: str, task_dir: str, request_id: str) -> None:
    """Espera a resposta até `deadline`; no prazo grava o `deny` por `timeout` (AC 5), a menos que alguém tenha
    respondido antes (o `write_once` decide a disputa, AC 16)."""
    import time
    from datetime import UTC, datetime

    while not os.path.exists(path):
        now = datetime.now(UTC)
        if now >= deadline:
            body: dict[str, object] = {
                "decision": "deny",
                "message": f"no reply before {deadline_text}",
                "by": "timeout",
                "at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            }
            if write_once(path, body):
                _log(task_dir, f"no reply for {request_id} before {deadline_text}: denied")
            return
        time.sleep(min(POLL_SECONDS, max((deadline - now).total_seconds(), 0.01)))


def _emit(source: str, task_id: str, task_dir: str) -> str:
    from pathlib import Path

    try:
        data = json.loads(sys.stdin.read())
    except ValueError as e:
        _log(task_dir, f"--from {source}: stdin is not JSON: {e}")
        return "{}"
    if isinstance(data, dict) and isinstance(data.get("hook_event_name"), str):
        # os 9 hooks de progresso do Claude Code: só registro (grokbot_kit.hooks), sem decisão
        from grokbot_kit import hooks

        if data["hook_event_name"] in hooks.EVENTS:
            hooks.handle(data, task_id, task_dir)
            return "{}"
    asked = normalize(source, data)
    if asked is None:
        return "{}"

    from datetime import UTC, datetime, timedelta

    from grokbot_kit import config, deliver, payload

    directory = Path(task_dir)
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    if meta.get("plugin"):
        # numa tarefa de plugin a negação é esperada e não muda o status (plugins, AC 44)
        _log(task_dir, f"--from {source}: {asked['kind']} request in a plugin task, not sent: {asked['tool_name']}")
        return "{}"
    request_id = str(asked["discriminator"])
    reply_path = str(directory / "replies" / f"{request_id}.json")
    wait = meta.get("ask_wait_seconds")
    deadline = None
    # numa tarefa já terminada não há CLI esperando a decisão
    if isinstance(wait, int) and wait > 0 and not meta.get("finished_at") and _can_wait(source, asked["kind"]):
        if os.path.exists(reply_path):
            # o mesmo pedido já respondido: vale a resposta gravada, sem outro `needs_input` (AC 8)
            return _reply_answer(source, reply_path, task_dir, request_id)
        started = datetime.fromisoformat(str(meta["started_at"]))
        end = started + timedelta(seconds=int(meta["timeout_seconds"]))
        # o prazo vai no evento em segundos inteiros: arredondado para cima, a espera nunca fica menor que a pedida
        asked_until = datetime.now(UTC) + timedelta(seconds=wait)
        if asked_until.microsecond:
            asked_until = asked_until.replace(microsecond=0) + timedelta(seconds=1)
        deadline = min(asked_until, end)
    deadline_text = payload.rfc3339(deadline) if deadline else None
    event = payload.needs_input_event(
        meta,
        directory,
        kind=str(asked["kind"]),
        tool_name=asked["tool_name"],
        detail=asked["detail"],
        session_id=asked["session_id"],
        transcript_path=asked["transcript_path"],
        request_id=request_id,
        reply_deadline=deadline_text,
    )
    deliver.deliver(directory, config.load(), meta["target"], event, request_id)
    if deadline is None or deadline_text is None:
        return "{}"
    _wait_reply(reply_path, deadline, deadline_text, task_dir, request_id)
    return _reply_answer(source, reply_path, task_dir, request_id)


def _reply_answer(source: str, reply_path: str, task_dir: str, request_id: str) -> str:
    reply = read_reply(reply_path)
    if reply is None:
        _log(task_dir, f"--from {source}: unreadable reply for {request_id}: {reply_path}")
        return "{}"
    return _answer(source, reply)


def main(argv: list[str] | None = None) -> int:
    task_id = os.environ.get("GROKBOT_KIT_TASK_ID")
    if not task_id:
        return 0
    args = sys.argv[1:] if argv is None else argv
    source = args[1] if len(args) == 2 and args[0] == "--from" else None
    task_dir = os.environ.get("GROKBOT_KIT_TASK_DIR") or os.path.join(
        os.path.expanduser("~"), ".grokbot-kit", "tasks", task_id
    )
    out = "{}"
    try:
        if source not in SOURCES:
            _log(task_dir, f"usage: grokbot-kit emit --from {{{','.join(SOURCES)}}}, got {args!r}")
        else:
            out = _emit(source, task_id, task_dir)
    except Exception as e:  # noqa: BLE001 - o hook nunca pode falhar o agente (AC 60)
        _log(task_dir, f"--from {source}: {type(e).__name__}: {e}")
    sys.stdout.write(out)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
