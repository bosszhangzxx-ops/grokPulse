"""Provas com as CLIs reais no box (check C55; AC 40-44). Rodam só com `-m integration`.

O kit roda num `HOME` temporário, para não tocar no config nem nos task dirs do usuário. Do `HOME` real só entram,
por symlink, as credenciais do Claude (`~/.claude/.credentials.json`) e do opencode
(`~/.local/share/opencode/auth.json`), mais uma cópia do `opencode.db`, onde o opencode 1.19.5 guarda o login de um
provedor pago. O Codex usa o `CODEX_HOME` isolado da door 7, `~/.grokbot-kit/codex-home` do
`HOME` real, com login próprio; o `~/.codex` do usuário nunca entra (AC 98).

Modelos: `GROKBOT_KIT_IT_CLAUDE_MODEL` ou `haiku` no Claude (alias documentado); no opencode, `GROKBOT_KIT_IT_OPENCODE_MODEL` ou o primeiro modelo
`-free` impresso por `opencode models`; e o id de `GROKBOT_KIT_IT_CODEX_MODEL` no Codex.
O primeiro `-free` listado pode estar indisponível (`opencode-go/beam-free` respondeu `Model unavailable`) e o `haiku`
recusou a skill do spike no C37: as provas da 0.4.1 rodaram com `sonnet` e `opencode/glm-5.3-flash-free`.
"""

import json
import os
import shutil
import sqlite3
import subprocess
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REAL_HOME = Path.home()
REAL_CODEX_HOME = REAL_HOME / ".grokbot-kit" / "codex-home"
PLUGIN = Path(__file__).resolve().parents[2] / "src" / "grokbot_kit" / "assets" / "opencode" / "grokbot-kit.ts"
TERMINAL_EVENTS = ("completed", "error", "timeout")

PROMPTS = {
    "ok": "Reply with exactly the word pong. Do not use any tool.",
    "denied": "Use your shell tool to run exactly this command: touch {work}/criado.txt",
}


def real_bin(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        pytest.fail(f"{tool} não está instalado no box")
    return path


def model_for(tool: str) -> str:
    if tool == "claude":
        return os.environ.get("GROKBOT_KIT_IT_CLAUDE_MODEL") or "haiku"
    if tool == "opencode":
        if os.environ.get("GROKBOT_KIT_IT_OPENCODE_MODEL"):
            return os.environ["GROKBOT_KIT_IT_OPENCODE_MODEL"]
        listed = subprocess.run(
            [real_bin("opencode"), "models"], capture_output=True, text=True, stdin=subprocess.DEVNULL, check=True
        ).stdout.split()
        free = [m for m in listed if m.endswith("-free")]
        if not free:
            pytest.fail("opencode models não listou nenhum modelo -free")
        return free[0]
    model = os.environ.get("GROKBOT_KIT_IT_CODEX_MODEL")
    if not model:
        pytest.fail("defina GROKBOT_KIT_IT_CODEX_MODEL com um id aceito pelo codex exec")
    return model


def link(src: Path, dest: Path) -> None:
    if src.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.symlink_to(src)


def copy_opencode_db(home: Path) -> None:
    """Uma cópia consistente do `opencode.db` real no `HOME` temporário. No opencode 1.19.5 do box o login de um
    provedor pago (opencode-go) fica nesse banco, não no `auth.json` (`opencode auth list`: `0 credentials`); a cópia,
    e não um link, deixa o banco real sem as sessões do teste."""
    src = REAL_HOME / ".local" / "share" / "opencode" / "opencode.db"
    if not src.exists():
        return
    dest = home / ".local" / "share" / "opencode" / "opencode.db"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{src}?mode=ro", uri=True) as source, sqlite3.connect(dest) as target:
        source.backup(target)


def install_plugin(home: Path) -> None:
    """O plugin do opencode no `HOME` temporário, com o caminho do `grokbot-kit` do teste, como o `install opencode`."""
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    dest = home / ".config" / "opencode" / "plugins" / "grokbot-kit.ts"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(PLUGIN.read_text(encoding="utf-8").replace("__GROKBOT_KIT_EXE__", exe), encoding="utf-8")


def prepare_home(tmp_path: Path, tool: str, case: str) -> tuple[Path, Path, str]:
    home = tmp_path / "home"
    work = tmp_path / "work"
    work.mkdir(parents=True)
    # o `codex exec` só roda dentro de um repositório git (ou com `--skip-git-repo-check`), como uma task real
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    link(REAL_HOME / ".claude" / ".credentials.json", home / ".claude" / ".credentials.json")
    link(
        REAL_HOME / ".local" / "share" / "opencode" / "auth.json", home / ".local" / "share" / "opencode" / "auth.json"
    )
    if tool == "opencode":
        copy_opencode_db(home)
    if tool == "opencode" and case == "denied":
        opencode_config = home / ".config" / "opencode" / "opencode.json"
        opencode_config.parent.mkdir(parents=True)
        opencode_config.write_text(json.dumps({"permission": {"bash": "ask", "edit": "ask"}}), encoding="utf-8")
    if tool == "opencode":
        install_plugin(home)
    if tool == "codex" and not (REAL_CODEX_HOME / "auth.json").exists():
        pytest.fail(f"Codex sem login no CODEX_HOME isolado: rode CODEX_HOME={REAL_CODEX_HOME} codex login")

    model = model_for(tool)
    sink = tmp_path / "sink.jsonl"
    cli = [f"[cli.{tool}]", f"bin = {json.dumps(real_bin(tool))}", f"models = [{json.dumps(model)}]"]
    if tool == "codex":
        cli.append(f"codex_home = {json.dumps(str(REAL_CODEX_HOME))}")
    config = "\n".join(
        [
            "[setup]",
            "version = 1",
            f'installed = ["{tool}"]',
            f'default_cli = "{tool}"',
            "",
            *cli,
            f"[cli.{tool}.tiers]",
            f"standard = [{json.dumps(model)}]",
            "",
            # as provas de antes da needs-input-reply cobram o aviso sem espera; as de resposta passam `--ask-wait`
            "[ask]",
            'wait = "0"',
            "",
            "[routes.it]",
            'sinks = ["arquivo"]',
            "",
            "[sinks.arquivo]",
            'type = "file"',
            f"path = {json.dumps(str(sink))}",
            "",
        ]
    )
    config_path = home / ".config" / "grokbot-kit" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config, encoding="utf-8")
    return home, work, PROMPTS[case].format(work=work)


# C55 - AC 40-44, 57
@pytest.mark.parametrize("case", ["ok", "denied"])
@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_completed_ok_and_denied_per_tool(tmp_path: Path, tool: str, case: str) -> None:
    home, work, prompt = prepare_home(tmp_path, tool, case)
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    env = {**os.environ, "HOME": str(home)}
    result = subprocess.run(
        [exe, "run", "--tool", tool, "--target", "it", "--label", f"it-{case}", "--cwd", str(work), "--", prompt],
        capture_output=True,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=600,
    )
    sink = tmp_path / "sink.jsonl"
    lines = sink.read_text(encoding="utf-8").splitlines() if sink.exists() else []
    # desde o S3 o sink também recebe os `needs_input` do emit; o check fala da linha terminal
    terminal = [e for e in map(json.loads, lines) if e["event"] in TERMINAL_EVENTS]
    assert len(terminal) == 1, result.stderr
    event = terminal[0]
    # o `codex exec` não pede permissão (AD-027): o `touch` negado termina `completed`/`ok`, sem `needs_input`
    expected = ("completed", "ok") if case == "ok" or tool == "codex" else ("completed", "denied")
    assert (event["event"], event["status"]) == expected, (event, result.stderr)


def refresh_home(tmp_path: Path, tool: str) -> tuple[Path, Path, dict[str, str]]:
    """`HOME` temporário com o login da CLI e um config só com `setup` e `[cli.<tool>]`, sem modelos."""
    home, work, _ = prepare_home(tmp_path, tool, "ok")
    sink = tmp_path / "sink.jsonl"
    cli = {"bin": real_bin(tool)}
    if tool == "codex":
        cli["codex_home"] = str(REAL_CODEX_HOME)
    lines = ["[setup]", "version = 1", f'installed = ["{tool}"]', f'default_cli = "{tool}"', "", f"[cli.{tool}]"]
    lines += [f"{k} = {json.dumps(v)}" for k, v in cli.items()]
    lines += ["", "[routes.it]", 'sinks = ["arquivo"]', "", "[sinks.arquivo]", 'type = "file"']
    lines += [f"path = {json.dumps(str(sink))}", ""]
    (home / ".config" / "grokbot-kit" / "config.toml").write_text("\n".join(lines), encoding="utf-8")
    return home, work, {**os.environ, "HOME": str(home)}


# C107 - AC 84, 85, 86
@pytest.mark.parametrize("tool", ["claude", "opencode", "codex"])
def test_models_refresh_real(tmp_path: Path, tool: str) -> None:
    home, work, env = refresh_home(tmp_path, tool)
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    add = ["--add", model_for("codex")] if tool == "codex" else []
    refreshed = subprocess.run(
        [exe, "setup", "models", "refresh", tool, *add],
        capture_output=True,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=900,
    )
    config_path = home / ".config" / "grokbot-kit" / "config.toml"
    cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
    ids = cfg["cli"][tool].get("models", [])
    assert ids, (refreshed.returncode, refreshed.stderr)

    first = ids[0]
    config_path.write_text(
        config_path.read_text(encoding="utf-8") + f"\n[cli.{tool}.tiers]\ntrivial = [{json.dumps(first)}]\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [exe, "run", "--tier", "trivial", "--target", "it", "--label", "it-modelo", "--cwd", str(work), "--"]
        + [PROMPTS["ok"]],
        capture_output=True,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=600,
    )
    sink = tmp_path / "sink.jsonl"
    lines = sink.read_text(encoding="utf-8").splitlines() if sink.exists() else []
    terminal = [e for e in map(json.loads, lines) if e["event"] in TERMINAL_EVENTS]
    assert len(terminal) == 1, result.stderr
    event = terminal[0]
    assert (event["model"], event["model_source"], event["tier"]) == (first, "tier", "trivial")
    assert (event["event"], event["status"]) == ("completed", "ok"), (event, result.stderr)


# model-setup-docs: o fallback de modelo do tier com as CLIs reais (C36 no box, C37 no host de dev)
MISSING = {"opencode": "opencode/nao-existe-grokbot-kit", "claude": "claude-nao-existe-grokbot-kit"}
READ_PROMPT = "Use your file read tool to read {work}/nota.txt and reply with its exact content. Do not use the shell."


def opencode_go_model() -> str:
    """`GROKBOT_KIT_IT_OPENCODE_GO_MODEL` ou o primeiro id `opencode-go/` pago listado por `opencode models`."""
    if os.environ.get("GROKBOT_KIT_IT_OPENCODE_GO_MODEL"):
        return os.environ["GROKBOT_KIT_IT_OPENCODE_GO_MODEL"]
    listed = subprocess.run(
        [real_bin("opencode"), "models"], capture_output=True, text=True, stdin=subprocess.DEVNULL, check=True
    ).stdout.split()
    paid = [m for m in listed if m.startswith("opencode-go/") and not m.endswith("-free")]
    if not paid:
        pytest.fail("opencode models não listou nenhum id opencode-go/ pago")
    return paid[0]


def fallback_run(tmp_path: Path, tool: str, second: str, prompt: str, label: str) -> dict[str, object]:
    """`run --tier standard` com `standard = [<id inexistente>, second]`, gravado direto no config (o `--add` e o
    `setup tiers` recusam o id inexistente)."""
    home, work, _ = prepare_home(tmp_path, tool, "ok")
    (work / "nota.txt").write_text("grokbot-kit-leu-o-arquivo\n", encoding="utf-8")
    ids = json.dumps([MISSING[tool], second])
    config_path = home / ".config" / "grokbot-kit" / "config.toml"
    text = config_path.read_text(encoding="utf-8")
    text = text.replace(f"models = [{json.dumps(model_for(tool))}]", f"models = {ids}", 1)
    text = text.replace(f"standard = [{json.dumps(model_for(tool))}]", f"standard = {ids}", 1)
    config_path.write_text(text, encoding="utf-8")
    exe = shutil.which("grokbot-kit")
    assert exe is not None
    result = subprocess.run(
        [exe, "run", "--tool", tool, "--tier", "standard", "--target", "it", "--label", label, "--cwd", str(work)]
        + ["--", prompt.format(work=work)],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home)},
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=900,
    )
    sink = tmp_path / "sink.jsonl"
    lines = sink.read_text(encoding="utf-8").splitlines() if sink.exists() else []
    terminal = [e for e in map(json.loads, lines) if e["event"] in TERMINAL_EVENTS]
    assert len(terminal) == 1, result.stderr
    event: dict[str, object] = terminal[0]
    return event


# C36 - AC 26, AC 31 e as suposições do opencode 1.19.3 (roda no box, pelo bot)
def test_opencode_fallback_real(tmp_path: Path) -> None:
    second = opencode_go_model()
    event = fallback_run(tmp_path / "fallback", "opencode", second, PROMPTS["ok"], "it-fallback")
    assert (event["event"], event["status"]) == ("completed", "ok"), event
    assert event["model"] == second
    fallbacks = event["model_fallbacks"]
    assert isinstance(fallbacks, list) and [f["model"] for f in fallbacks] == [MISSING["opencode"]], event
    # a outra metade: uma tarefa que lê um arquivo grava `type` `tool_use` no `out.jsonl` (door 4)
    read = fallback_run(tmp_path / "read", "opencode", second, READ_PROMPT, "it-tool-use")
    output = Path(str(read["output_file"])).read_text(encoding="utf-8")
    kinds = {json.loads(line).get("type") for line in output.splitlines() if line.strip().startswith("{")}
    assert "tool_use" in kinds, (kinds, read)


# C37 - a suposição do `claude` (`is_error`, `terminal_reason` `api_error`, `num_turns` ≤ 1); roda no host de dev
def test_claude_fallback_real(tmp_path: Path) -> None:
    event = fallback_run(tmp_path, "claude", "haiku", PROMPTS["ok"], "it-fallback")
    assert event["model"] == "haiku", event
    fallbacks = event["model_fallbacks"]
    assert isinstance(fallbacks, list) and [f["model"] for f in fallbacks] == [MISSING["claude"]], event
