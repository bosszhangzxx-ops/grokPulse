#!/usr/bin/env python3
"""CLI falsa: faz o papel de `claude`, `opencode` ou `codex` (pelo nome do link) nos testes do `run`.

Comportamento por env: `FAKE_RECORD` (grava argv, stdin, env e cwd), `FAKE_STDOUT` (saída), `FAKE_LAST_MESSAGE`
(conteúdo do `-o` do codex), `FAKE_NEEDS_INPUT=1` (registra um `needs_input` no task dir; um objeto JSON no lugar
do `1` entra como campos extras desse evento, ex. `transcript_path`), `FAKE_EMIT` (lista JSON de stdins para
`grokbot-kit emit --from <tool>`), `FAKE_RESULT` (conteúdo gravado em `GROKBOT_KIT_RESULT_FILE`, antes de qualquer
espera) e `FAKE_EXIT` (exit code).

Descoberta de modelos: `opencode models` imprime `FAKE_OPENCODE_MODELS` e sai com `FAKE_MODELS_EXIT`. Com
`FAKE_ACCEPT_MODELS` (lista JSON) no env, `claude`/`codex` fazem o papel da chamada de teste de um modelo: aceitam os
ids da lista e recusam os outros com erro de modelo e exit `1`; os ids de `FAKE_ERROR_EXIT0` saem com `0` e erro na
saída JSON. `FAKE_CALLS` acumula uma linha JSON por chamada (argv, stdin, cwd e `CODEX_HOME`).

Setup e login: `--version` imprime o conteúdo de `~/.fake-version-<tool>` (gravado pelo instalador falso), senão
`FAKE_VERSION` (padrão `9.9.9 (<tool> fake)`), e sai com `FAKE_VERSION_EXIT`; `claude auth login`,
`opencode auth login` e `codex login --device-auth|--with-api-key` saem com `FAKE_LOGIN_EXIT` (o `codex login`
grava `auth.json` em `CODEX_HOME`, ou em `~/.codex` sem ele, como a CLI real); `claude auth status` e
`codex login status` saem com `1` quando a tool está em `FAKE_LOGGED_OUT` (lista separada por vírgula) e `0` senão;
`opencode auth list` imprime `<FAKE_OPENCODE_CREDENTIALS> credentials` (padrão `0`) e sai com `0`. Toda chamada do
`codex` cria `tmp/` em `CODEX_HOME`, quando ele existe, ou em `~/.codex`, como a CLI real faz ao iniciar. A linha de
`FAKE_CALLS` do `codex login --with-api-key` traz o stdin lido, e a de todo `claude` traz `ANTHROPIC_API_KEY`.

Sinais: com `FAKE_TRAP` (arquivo), o agente grava uma linha JSON `ready` (pid e pgid) e uma por `SIGINT`/`SIGTERM`
recebido (pid, sinal, `time.monotonic()`); um sinal fora de `FAKE_IGNORE` (ex. `SIGINT,SIGTERM`) o encerra com
`128 + n`. `FAKE_CHILD=1` lança um filho no mesmo grupo com a mesma armadilha, e `FAKE_SLEEP` (segundos) segura o
agente antes de escrever a saída.

Por modelo: `FAKE_STDOUT_BY_MODEL`, `FAKE_EXIT_BY_MODEL`, `FAKE_SLEEP_BY_MODEL` e `FAKE_RESULT_BY_MODEL` (objetos JSON
`{"<id>": <valor>}`) escolhem o valor pelo id de `-m`/`--model` do argv; sem o id, vale o `FAKE_*` sem o sufixo.
"""

import json
import os
import signal
import subprocess
import sys
import time


def trap_signals(path: str) -> None:
    ignore = set(os.environ.get("FAKE_IGNORE", "").split(","))

    def on_signal(signum: int, frame: object) -> None:
        name = signal.Signals(signum).name
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"pid": os.getpid(), "signal": name, "at": time.monotonic()}) + "\n")
        if name not in ignore:
            sys.exit(128 + signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, on_signal)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"pid": os.getpid(), "pgid": os.getpgid(0), "ready": True}) + "\n")


def hold(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        time.sleep(0.05)


def by_model(name: str, default: str | None) -> str | None:
    """`FAKE_<name>_BY_MODEL[<id do argv>]`, ou o `FAKE_<name>` de sempre quando o id não está no objeto."""
    table = json.loads(os.environ.get(f"FAKE_{name}_BY_MODEL", "{}"))
    flag = "--model" if tool == "claude" else "-m"
    model = args[args.index(flag) + 1] if flag in args[:-1] else None
    return str(table[model]) if model in table else default


if os.environ.get("FAKE_ROLE") == "child":
    trap_signals(os.environ["FAKE_TRAP"])
    hold(float(os.environ.get("FAKE_SLEEP", "0")))
    sys.exit(0)

tool = os.path.basename(sys.argv[0])
args = sys.argv[1:]

login_stdin = sys.stdin.read() if tool == "codex" and args[:2] == ["login", "--with-api-key"] else None

calls = os.environ.get("FAKE_CALLS")
if calls:
    with open(calls, "a", encoding="utf-8") as f:
        call = {
            "tool": tool,
            "argv": args,
            "stdin_target": os.readlink("/proc/self/fd/0"),
            "cwd": os.getcwd(),
            "codex_home": os.environ.get("CODEX_HOME"),
        }
        if login_stdin is not None:
            call["stdin"] = login_stdin
        if tool == "claude":
            call["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY")
        f.write(json.dumps(call) + "\n")

if tool == "codex":
    # como o codex real, que cria os aliases de PATH no seu home a cada chamada, mesmo no `--version`
    codex_dir = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    if "CODEX_HOME" not in os.environ or os.path.isdir(codex_dir):
        os.makedirs(os.path.join(codex_dir, "tmp"), exist_ok=True)

logged_out = os.environ.get("FAKE_LOGGED_OUT", "").split(",")
if args == ["--version"]:
    installed = os.path.join(os.path.expanduser("~"), f".fake-version-{tool}")
    if os.path.exists(installed):
        with open(installed, encoding="utf-8") as f:
            print(f.read())
    else:
        print(os.environ.get("FAKE_VERSION", f"9.9.9 ({tool} fake)"))
    sys.exit(int(os.environ.get("FAKE_VERSION_EXIT", "0")))
if (tool, args[:2]) in (("claude", ["auth", "login"]), ("opencode", ["auth", "login"])):
    sys.exit(int(os.environ.get("FAKE_LOGIN_EXIT", "0")))
if tool == "codex" and args[:2] in (["login", "--device-auth"], ["login", "--with-api-key"]):
    code = int(os.environ.get("FAKE_LOGIN_EXIT", "0"))
    if code == 0:
        home = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
        with open(os.path.join(home, "auth.json"), "w", encoding="utf-8") as f:
            json.dump({"fake": True}, f)
    sys.exit(code)
if (tool, args[:2]) in (("claude", ["auth", "status"]), ("codex", ["login", "status"])):
    print("Not logged in" if tool in logged_out else "Logged in")
    sys.exit(1 if tool in logged_out else 0)
if tool == "opencode" and args[:2] == ["auth", "list"]:
    print(f"{os.environ.get('FAKE_OPENCODE_CREDENTIALS', '0')} credentials")
    sys.exit(0)

if tool == "opencode" and args[:1] == ["models"]:
    sys.stdout.write(os.environ.get("FAKE_OPENCODE_MODELS", ""))
    sys.exit(int(os.environ.get("FAKE_MODELS_EXIT", "0")))

if "FAKE_ACCEPT_MODELS" in os.environ and tool in ("claude", "codex"):
    flag = "--model" if tool == "claude" else "-m"
    model = args[args.index(flag) + 1]
    accepted = model in json.loads(os.environ["FAKE_ACCEPT_MODELS"])
    error_exit0 = model in json.loads(os.environ.get("FAKE_ERROR_EXIT0", "[]"))
    failed = error_exit0 or not accepted
    if tool == "claude":
        result = f"model {model} not found" if failed else "ok"
        sys.stdout.write(json.dumps({"type": "result", "is_error": failed, "result": result}) + "\n")
    elif failed:
        sys.stdout.write(json.dumps({"type": "error", "message": f"model {model} is not supported"}) + "\n")
    else:
        sys.stdout.write(json.dumps({"type": "thread.started", "thread_id": "th-1"}) + "\n")
    sys.exit(1 if failed and not error_exit0 else 0)

record = os.environ.get("FAKE_RECORD")
if record:
    with open(record, "w", encoding="utf-8") as f:
        json.dump(
            {
                "tool": tool,
                "argv": args,
                "stdin_target": os.readlink("/proc/self/fd/0"),
                "stdin_read": sys.stdin.read(),
                "env": {
                    k: v
                    for k, v in os.environ.items()
                    if k.startswith(("GROKBOT_KIT_", "OPENCODE_"))
                    or k in ("CODEX_HOME", "ANTHROPIC_API_KEY", "PWD", "CLAUDE_CODE_ENABLE_TODO_TOOLS")
                },
                "cwd": os.getcwd(),
            },
            f,
        )

fake_result = by_model("RESULT", os.environ.get("FAKE_RESULT"))
if fake_result is not None:
    with open(os.environ["GROKBOT_KIT_RESULT_FILE"], "w", encoding="utf-8") as f:
        f.write(fake_result)

if "FAKE_LAST_MESSAGE" in os.environ and "-o" in args:
    with open(args[args.index("-o") + 1], "w", encoding="utf-8") as f:
        f.write(os.environ["FAKE_LAST_MESSAGE"])

needs_input = os.environ.get("FAKE_NEEDS_INPUT")
if needs_input:
    extra = {} if needs_input == "1" else json.loads(needs_input)
    with open(os.path.join(os.environ["GROKBOT_KIT_TASK_DIR"], "events.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"event": {"event": "needs_input", "status": "permission", **extra}}) + "\n")

for payload in json.loads(os.environ.get("FAKE_EMIT", "[]")):
    subprocess.run(
        ["grokbot-kit", "emit", "--from", tool], input=json.dumps(payload), text=True, capture_output=True, check=False
    )

trap = os.environ.get("FAKE_TRAP")
if trap:
    trap_signals(trap)
    if os.environ.get("FAKE_CHILD") == "1":
        subprocess.Popen([sys.executable, os.path.realpath(__file__)], env={**os.environ, "FAKE_ROLE": "child"})
hold(float(by_model("SLEEP", os.environ.get("FAKE_SLEEP", "0")) or "0"))

sys.stdout.write(by_model("STDOUT", os.environ.get("FAKE_STDOUT", "")) or "")
sys.exit(int(by_model("EXIT", os.environ.get("FAKE_EXIT", "0")) or "0"))
