"""`grokbot-kit run`: valida, cria o task dir (door 4), lança o agente e envia um único evento terminal (AC 39-53, 87-89)."""

import argparse
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from grokbot_kit import config, deliver, launch, payload, resolve, terminal
from grokbot_kit import plugin as plugins
from grokbot_kit.payload import rfc3339

SECRET_KEYS = ("url_secret", "key_secret", "token_secret", "webhook_secret")
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
EXIT_NOT_FOUND = 127
EXIT_TIMEOUT = 124
EXIT_INTERRUPTED = 130
GRACE_SECONDS = 10.0
POLL_SECONDS = 0.05


class UsageError(Exception):
    pass


PR_URL_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/([0-9]+)/?$")
BRANCH_URL_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/tree/([A-Za-z0-9_.][A-Za-z0-9_./-]*?)/?$"
)
MAX_FILE_BYTES = 1024 * 1024
MAX_TEXT_BYTES = 64 * 1024


def _repo_target(key: str, url: str) -> tuple[str, str | None, str | None]:
    """`(owner/repo, número do PR, branch)` de uma entrada `repo` (door 7)."""
    pr = PR_URL_RE.match(url)
    if pr:
        return pr.group(1), pr.group(2), None
    branch = BRANCH_URL_RE.match(url)
    if branch and ".." not in branch.group(2):
        return branch.group(1), None, branch.group(2)
    raise UsageError(
        f"--input {key} must be https://github.com/<owner>/<repo>/pull/<n> or "
        f"https://github.com/<owner>/<repo>/tree/<branch>, not {url!r}"
    )


def _plugin_task(args: argparse.Namespace, tool: str) -> dict[str, Any] | None:
    """O plugin, as entradas e o alvo do clone de `run --plugin`, validados antes do task dir (AC 27-32)."""
    if not args.plugin:
        if args.input:
            raise UsageError("--input needs --plugin")
        return None
    if args.prompt_file or args.extras:
        raise UsageError("--plugin takes its prompt from the plugin; remove --prompt-file and the arguments after --")
    found = plugins.find(args.plugin)
    if found is None:
        raise UsageError(f"no plugin named {args.plugin}; run: grokbot-kit plugin list")
    name = found.name
    declared: dict[str, dict[str, Any]] = found.manifest["inputs"]
    repo = next((k for k, spec in declared.items() if spec["kind"] == "repo"), None)
    if repo and args.cwd:
        raise UsageError(f"--cwd does not apply to plugin {name}: its workspace is the clone of input {repo}")
    values: dict[str, str] = {}
    for raw in args.input:
        key, sep, value = raw.partition("=")
        if not sep:
            raise UsageError(f"--input {raw!r} must be KEY=VALUE")
        if key not in declared:
            raise UsageError(f"plugin {name} has no input {key!r}; inputs: {', '.join(declared) or 'none'}")
        if key in values:
            raise UsageError(f"--input {key} given twice")
        values[key] = value
    for key, spec in declared.items():
        if spec["required"] and key not in values:
            raise UsageError(f"plugin {name} needs --input {key}=<{spec['kind']}>")
    target = None
    for key, value in values.items():
        kind = declared[key]["kind"]
        if kind == "repo":
            target = _repo_target(key, value)
        elif kind == "text" and len(value.encode("utf-8")) > MAX_TEXT_BYTES:
            raise UsageError(f"--input {key} has more than {MAX_TEXT_BYTES} bytes")
        elif kind == "file":
            path = Path(value).expanduser().resolve()
            if not path.is_file():
                raise UsageError(f"--input {key}: file not found: {path}")
            if path.stat().st_size > MAX_FILE_BYTES:
                raise UsageError(f"--input {key}: {path} has more than {MAX_FILE_BYTES} bytes")
            values[key] = str(path)
    refused = plugins.unenforceable(found, tool)
    if refused:
        raise UsageError(f"plugin {name} needs {refused}, which {tool} cannot enforce")
    return {"plugin": found, "values": values, "target": target}


def _resolve(args: argparse.Namespace, cfg: dict[str, Any]) -> dict[str, Any]:
    """Tudo o que o AC 47 manda recusar com `2` antes de existir task dir."""
    try:
        agent = resolve.resolve(cfg, tool=args.tool, model=args.model, tier=args.tier, timeout=args.timeout)
    except resolve.ResolveError as e:
        raise UsageError(str(e)) from None
    if agent.tool == "claude" and "--bare" in args.extras:
        raise UsageError("--bare disables the hooks grokbot-kit relies on; remove it")
    cli = cfg.get("cli", {}).get(agent.tool, {})
    if agent.tool == "claude" and "api_key_secret" in cli:
        config.check_secret(cli["api_key_secret"])
    route = cfg.get("routes", {}).get(args.target)
    if route is None:
        raise UsageError(f"target {args.target!r} has no route; run: grokbot-kit route add {args.target}")
    for name in route.get("sinks", []):
        sink = cfg.get("sinks", {}).get(name)
        if sink is None:
            raise UsageError(f"route {args.target!r} uses sink {name!r}, which is not in [sinks]")
        for key in SECRET_KEYS:
            if key in sink:
                config.check_secret(sink[key])
    try:
        wait = resolve.ask_wait(cfg, args.ask_wait)
    except resolve.ResolveError as e:
        raise UsageError(str(e)) from None
    if not LABEL_RE.match(args.label):
        raise UsageError("--label must use only letters, digits, '.', '_' and '-'")
    try:
        task = _plugin_task(args, agent.tool)
    except plugins.PluginError as e:
        raise UsageError(str(e)) from None
    cwd = Path(args.cwd or os.getcwd()).resolve()
    if not cwd.is_dir():
        raise UsageError(f"--cwd is not a directory: {cwd}")
    extras = list(args.extras)
    if args.prompt_file:
        try:
            extras.append(Path(args.prompt_file).read_text(encoding="utf-8"))
        except OSError as e:
            raise UsageError(f"cannot read --prompt-file: {e}") from None
    return {
        **agent._asdict(),
        "cli": cli,
        "cwd": cwd,
        "extras": extras,
        "task": task,
        "ask_wait": wait,
    }


def _recorded_needs_input(task_dir: Path) -> list[dict[str, Any]]:
    """Os `needs_input` registrados em `events.jsonl` pelo `emit`, na ordem."""
    try:
        lines = (task_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    found = []
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        event = record.get("event") if isinstance(record, dict) else None
        if isinstance(event, dict) and event.get("event") == "needs_input":
            found.append(event)
    return found


def _signal_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop_group(proc: "subprocess.Popen[bytes]", sent_at: float, grace: float = GRACE_SECONDS) -> None:
    """Escada do AC 87 depois do primeiro sinal, mandado em `sent_at`: `SIGTERM` ao grupo `grace` s depois e
    `SIGKILL` `grace` s depois disso, a menos que o agente saia e o grupo dele esvazie antes."""
    for sig, at in ((signal.SIGTERM, sent_at + grace), (signal.SIGKILL, sent_at + 2 * grace)):
        while time.monotonic() < at:
            if proc.poll() is not None and not _group_alive(proc.pid):
                return
            time.sleep(POLL_SECONDS)
        _signal_group(proc.pid, sig)
    proc.wait()


def _supervise(
    argv: list[str], timeout_seconds: int, deadline: float, task_dir: Path, **popen: Any
) -> tuple[int | None, str | None]:
    """Lança o agente num grupo próprio e espera até `deadline` (`time.monotonic()`); devolve `(returncode, stopped)`,
    com `returncode` `None` quando o binário não existe e `stopped` `"timeout"` ou `"interrupted"` quando o kit
    encerrou o agente (AC 87, 88)."""
    received: list[tuple[int, float]] = []
    group: list[int] = []

    def forward(signum: int, frame: object) -> None:
        received.append((signum, time.monotonic()))
        if group:
            _signal_group(group[0], signum)

    previous = {sig: signal.signal(sig, forward) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        try:
            proc = subprocess.Popen(argv, process_group=0, **popen)
        except FileNotFoundError:
            return None, None
        group.append(proc.pid)
        if received:
            _signal_group(proc.pid, received[0][0])
        while proc.poll() is None and not received and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
        stopped = None
        if received:
            stopped = "interrupted"
            _log(task_dir, f"{signal.Signals(received[0][0]).name} received: forwarded to the agent's process group")
            stop_group(proc, received[0][1])
        elif proc.returncode is None:
            stopped = "timeout"
            _log(task_dir, f"timeout after {timeout_seconds}s: SIGINT to the agent's process group")
            sent_at = time.monotonic()
            _signal_group(proc.pid, signal.SIGINT)
            stop_group(proc, sent_at)
        return proc.returncode, stopped
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _log(task_dir: Path, message: str) -> None:
    with (task_dir / "kit.log").open("a", encoding="utf-8") as f:
        f.write(f"{rfc3339(datetime.now(UTC))} {message}\n")


def _write_meta(task_dir: Path, meta: dict[str, Any]) -> None:
    (task_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _prepare_plugin(task: dict[str, Any], task_dir: Path) -> tuple[dict[str, Any], Path, str]:
    """Copia o plugin e as entradas `file` para o task dir (door 3) e devolve `(meta["plugin"], cwd, prompt)`."""
    source: plugins.Plugin = task["plugin"]
    copy = task_dir / "plugin"
    shutil.copytree(
        source.path,
        copy,
        ignore=lambda d, names: [n for n in names if Path(d) == source.path and n in (".git", "origin.json")],
    )
    plugin = plugins.Plugin(copy, source.manifest, source.source, source.origin, source.commit)
    declared = plugin.manifest["inputs"]
    # door 13: o agente de plugin roda sempre no task dir; sem `repo`, num `work/` vazio, nunca no cwd de quem chamou
    workspace = task_dir / "work"
    if not task["target"]:
        workspace.mkdir(mode=0o700)
    values = {"workspace": str(workspace), "result_file": str(task_dir / "result.json"), "task_dir": str(task_dir)}
    for key, value in task["values"].items():
        if declared[key]["kind"] == "file":
            (task_dir / "inputs").mkdir(exist_ok=True)
            value = str(shutil.copyfile(value, task_dir / "inputs" / key))
        values[key] = value
    meta = {
        "name": plugin.name,
        "version": plugin.manifest["version"],
        "source": plugin.source,
        "commit": plugin.commit,
        "capabilities": plugin.manifest["capabilities"],
        "support": plugins.matrix()[task["tool"]],
    }
    return meta, workspace, plugins.render_prompt(plugin, values)


def _clone(target: tuple[str, str | None, str | None], workspace: Path, timeout: int) -> str | None:
    """Clona o PR ou a branch (door 7) com o `gh` do box; devolve o motivo da falha, ou `None`."""
    slug, number, branch = target
    steps: list[tuple[list[str], Path | None]] = [
        (["gh", "repo", "clone", slug, str(workspace), *(["--", "--branch", branch] if branch else [])], None)
    ]
    if number:
        steps.append((["gh", "pr", "checkout", number], workspace))
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GH_PROMPT_DISABLED": "1"}
    for argv, cwd in steps:
        try:
            proc = subprocess.run(
                argv,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            return "gh not found; install the GitHub CLI and run: gh auth login"
        except subprocess.TimeoutExpired:
            return f"{' '.join(argv)} timed out after {timeout}s"
        if proc.returncode != 0:
            output = (proc.stderr.strip() + "\n" + proc.stdout.strip()).strip()
            return f"{' '.join(argv)} failed with exit {proc.returncode}: {output}"
    return _links_outside(workspace)


def _links_outside(workspace: Path) -> str | None:
    """Recusa o clone com symlink cujo alvo sai dele (door 12): a ferramenta de escrita do opencode segue o link."""
    root = workspace.resolve()
    found = []
    for dirpath, dirnames, filenames in os.walk(workspace):
        dirnames[:] = [d for d in dirnames if not (dirpath == str(workspace) and d == ".git")]
        for name in [*dirnames, *filenames]:
            path = Path(dirpath, name)
            if path.is_symlink() and not Path(os.path.realpath(path)).is_relative_to(root):
                found.append(path.relative_to(workspace).as_posix())
    if not found:
        return None
    found.sort()
    more = f" (+{len(found) - 5} more)" if len(found) > 5 else ""
    return f"the clone has symbolic links that point outside it: {', '.join(found[:5])}{more}"


def run(args: argparse.Namespace) -> int:
    try:
        cfg = config.load()
        r = _resolve(args, cfg)
    except (config.ConfigError, UsageError) as e:
        print(f"grokbot-kit run: {e}", file=sys.stderr)
        return 2

    tool: str = r["tool"]
    started = datetime.now(UTC)
    started_clock = time.monotonic()
    task_id = f"{started:%Y%m%dT%H%M%S}-{args.label}-{secrets.token_hex(3)}"
    task_dir = config.tasks_dir() / task_id
    task_dir.mkdir(parents=True, mode=0o700)
    print(f"grokbot-kit: task dir {task_dir}", file=sys.stderr)

    task = r["task"]
    cwd: Path = r["cwd"]
    extras: list[str] = r["extras"]
    plugin_meta = None
    if task:
        plugin_meta, cwd, prompt = _prepare_plugin({**task, "tool": tool}, task_dir)
        extras = [prompt]

    kit_exe = launch.kit_executable()
    bin_path = os.path.expanduser(r["cli"].get("bin", tool))
    major = launch.cli_major(bin_path) if tool == "opencode" else None
    # door 9 da needs-input-reply: o serviço compartilhado do opencode 2 não vê o env da tarefa, e o plugin dele precisa
    harness = launch.Harness(["--standalone"] if major is not None and major >= 2 else [], {}, {})
    if task:
        caps = task["plugin"].manifest["capabilities"]
        harness = launch.plugin_harness(tool, caps, task_dir, task_dir / "plugin", major)
    extras = [*harness.args, *extras]
    if tool == "claude":
        claude_settings: dict[str, Any] = launch.claude_settings(kit_exe, r["ask_wait"])
        if harness.permissions:
            claude_settings["permissions"] = harness.permissions
        settings = json.dumps(claude_settings, indent=2) + "\n"
        (task_dir / "claude-settings.json").write_text(settings, encoding="utf-8")
    env = {
        **os.environ,
        "GROKBOT_KIT_TASK_ID": task_id,
        "GROKBOT_KIT_TARGET": args.target,
        "GROKBOT_KIT_LABEL": args.label,
        "GROKBOT_KIT_TASK_DIR": str(task_dir),
        **config.cli_env(tool, r["cli"]),
        **harness.env,
        # o herdado apontaria para onde o kit foi chamado; o opencode acha o projeto pelo `PWD`, não pelo cwd
        "PWD": str(cwd),
    }
    if task:
        env["GROKBOT_KIT_RESULT_FILE"] = str(task_dir / "result.json")
    if tool == "claude":
        # modelos servidos por gateway (ex.: mimo) não recebem as Task tools por padrão; sem elas os
        # hooks TaskCreated/TaskCompleted nunca disparam (tools-reference#task-tool-availability).
        # O opt-in oficial é o env abaixo; um valor do usuário tem precedência.
        env.setdefault("CLAUDE_CODE_ENABLE_TODO_TOOLS", "1")

    meta: dict[str, Any] = {
        "task_id": task_id,
        "task_label": args.label,
        "target": args.target,
        "tool": tool,
        "model": r["model"],
        "model_source": r["model_source"],
        "model_fallbacks": [],
        "tier": r["tier"],
        "timeout_seconds": r["timeout_seconds"],
        "ask_wait_seconds": r["ask_wait"],
        "cwd": str(cwd),
        "started_at": rfc3339(started),
        "finished_at": None,
        "exit_code": None,
    }
    if tool == "codex":
        meta["codex_home"] = env["CODEX_HOME"]
    if plugin_meta:
        meta["plugin"] = plugin_meta
    _write_meta(task_dir, meta)

    if tool == "opencode":
        # o plugin global acompanha o major do opencode (AC 25 e 26 da needs-input-reply); falhar não segura a tarefa
        from grokbot_kit import opencode_plugin

        try:
            rewritten = opencode_plugin.sync(major)
        except OSError as e:
            _log(task_dir, f"cannot rewrite the opencode plugin at {opencode_plugin.plugin_path()}: {e}")
        else:
            if rewritten:
                _log(task_dir, rewritten)
    if task and not task["target"] and args.cwd:
        _log(task_dir, f"--cwd ignored: a plugin task runs in {cwd}")
    if task and task["target"]:
        _log(task_dir, f"clone {task['target'][0]} into {cwd}")
        failure = _clone(task["target"], cwd, r["timeout_seconds"])
        if failure:
            _log(task_dir, f"clone failed, agent not launched: {failure}")
            return _finish(task_dir, cfg, args.target, meta, "error", "failed", "agent_error", 1, failure)

    # door 5 da model-setup-docs: com o modelo do tier, uma tentativa que caiu no provedor antes de qualquer
    # ferramenta passa ao próximo id; todas dividem o prazo contado do início da task
    candidates = r["cli"].get("tiers", {}).get(r["tier"], []) if r["model_source"] == "tier" else [r["model"]]
    deadline = started_clock + r["timeout_seconds"]
    for attempt, model in enumerate(candidates):
        if attempt:
            (task_dir / "out.jsonl").rename(task_dir / f"out.{attempt}.jsonl")
            (task_dir / "stderr.log").rename(task_dir / f"stderr.{attempt}.log")
            meta["model"] = model
            _write_meta(task_dir, meta)
        argv = launch.agent_argv(tool, bin_path, model, task_dir, kit_exe, extras)
        _log(task_dir, f"launch {tool} model={model} timeout={r['timeout_seconds']}s")
        with (task_dir / "out.jsonl").open("wb") as out, (task_dir / "stderr.log").open("wb") as err:
            returncode, stopped = _supervise(
                argv,
                r["timeout_seconds"],
                deadline,
                task_dir,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                cwd=cwd,
                env=env,
            )
        if returncode is None or attempt + 1 == len(candidates):
            break
        if not terminal.fallback_eligible(tool, task_dir, stopped):
            break
        reason = terminal.read_output(tool, task_dir).summary
        meta["model_fallbacks"].append({"model": model, "error": reason})
        nxt = candidates[attempt + 1]
        _log(task_dir, f"model {model} failed at the provider before any tool call ({reason}); trying {nxt}")
    if returncode is None:
        _log(task_dir, f"binary not found: {bin_path}")
        exit_code = EXIT_NOT_FOUND
        output = terminal.AgentOutput(error=True, permission_denied=False, summary=f"binary not found: {bin_path}")
    else:
        exit_code = returncode if returncode >= 0 else 128 - returncode
        output = terminal.read_output(tool, task_dir)
    if stopped == "timeout":
        exit_code = EXIT_TIMEOUT
    elif stopped == "interrupted":
        exit_code = EXIT_INTERRUPTED
    asked = _recorded_needs_input(task_dir)
    result, invalid = None, ""
    if task:
        result, invalid = plugins.read_result(task_dir / "result.json", task["plugin"].manifest["result"])
        if output.permission_denied or asked:
            _log(task_dir, "the CLI denied a permission; in a plugin task this does not change the status")
    event_name, status, exit_reason = terminal.classify(
        exit_code,
        output,
        needs_input=bool(terminal.unanswered(task_dir, asked)),
        stopped=stopped,
        plugin=bool(task),
        result_valid=result is not None,
    )
    summary = output.summary
    if exit_reason == "result_invalid":
        summary = invalid
    elif task and exit_reason == "success" and result is not None and isinstance(result.get("summary"), str):
        summary = result["summary"][: terminal.SUMMARY_LIMIT]
    transcripts = [e["transcript_path"] for e in asked if isinstance(e.get("transcript_path"), str)]
    return _finish(
        task_dir,
        cfg,
        args.target,
        meta,
        event_name,
        status,
        exit_reason,
        exit_code,
        summary,
        session_id=output.session_id,
        transcript_path=transcripts[-1] if transcripts else None,
        result=result if exit_reason == "success" else None,
    )


def _finish(
    task_dir: Path,
    cfg: dict[str, Any],
    target: str,
    meta: dict[str, Any],
    event_name: str,
    status: str,
    exit_reason: str,
    exit_code: int,
    summary: str,
    **fields: Any,
) -> int:
    """Monta e entrega o evento terminal e fecha o `meta.json`."""
    event = payload.task_event(
        meta,
        task_dir,
        event=event_name,
        status=status,
        exit_reason=exit_reason,
        exit_code=exit_code,
        summary=summary[: terminal.SUMMARY_LIMIT],
        **fields,
    )
    _log(task_dir, f"exit {exit_code}: {event_name}/{status}/{exit_reason}")
    deliver.deliver(task_dir, cfg, target, event, "terminal")
    meta.update(finished_at=event["timestamp"], exit_code=exit_code)
    _write_meta(task_dir, meta)
    return exit_code
