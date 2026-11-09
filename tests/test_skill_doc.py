"""Provas do S8 sobre o `skills/grokbot-kit/SKILL.md` (checks C126-C145; AC 102-119, doors 8 e 22).

As provas são do nível do documento: afirmam o que o `SKILL.md` instrui, não o que um bot faz com ele.
"""

import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "grokbot-kit" / "SKILL.md"


def text() -> str:
    return SKILL.read_text(encoding="utf-8")


def frontmatter() -> dict[str, Any]:
    match = re.match(r"^---\n(.*?)\n---\n", text(), re.DOTALL)
    assert match, "SKILL.md sem frontmatter"
    data: dict[str, Any] = yaml.safe_load(match.group(1))
    return data


def body() -> str:
    return text().split("\n---\n", 1)[1]


def section(heading: str) -> str:
    """O trecho de um título (`#`, `##` ou `###`) cujo texto contém `heading` até o próximo título de nível igual ou acima."""
    lines = body().splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#+) (.*)$", line)
        if m and heading.lower() in m.group(2).lower():
            level = len(m.group(1))
            end = next(
                (j for j in range(i + 1, len(lines)) if re.match(rf"^#{{1,{level}}} ", lines[j])),
                len(lines),
            )
            return "\n".join(lines[i:end])
    raise AssertionError(f"sem título com {heading!r}")


def paragraph_with(needle: str) -> str:
    """O parágrafo (ou item de lista) do corpo que contém `needle`."""
    for block in re.split(r"\n\s*\n|\n(?=\s*(?:[-*]|\d+\.) )", body()):
        if needle in block:
            return block
    raise AssertionError(f"nenhum parágrafo com {needle!r}")


def fenced(lang: str | None = None) -> list[str]:
    blocks = re.findall(r"^```([\w-]*)\n(.*?)^```", body(), re.DOTALL | re.MULTILINE)
    return [code for tag, code in blocks if lang is None or tag == lang]


def sh_commands() -> list[str]:
    return [line.strip() for code in fenced("sh") for line in code.splitlines() if line.strip()]


def cited_commands() -> list[str]:
    """Cada `grokbot-kit ...` citado em código: spans inline e linhas dos blocos `sh`."""
    spans = re.findall(r"`([^`\n]+)`", re.sub(r"^```.*?^```", "", body(), flags=re.DOTALL | re.MULTILINE))
    found = [s for s in spans + sh_commands() if s.startswith("grokbot-kit ")]
    return found


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


# C126 - AC 102, door 8
def test_frontmatter_name_and_triggers() -> None:
    fm = frontmatter()
    assert fm["name"] == "grokbot-kit"
    for trigger in ("configurar grokbot-kit", "delegar para opencode/claude/codex", "rodar tarefa headless"):
        assert f'"{trigger}"' in fm["description"], trigger


# C127 - AC 103
def test_install_first_step() -> None:
    first = paragraph_with("uv tool install --managed-python grokbot-kit")
    assert "PATH" in first
    assert "`pipx install grokbot-kit`" in first
    assert "sem `uv`" in first
    commands = [c for c in sh_commands() if c != "grokbot-kit --version"]
    assert commands[0] == "uv tool install --managed-python grokbot-kit"
    assert commands[1] == "pipx install grokbot-kit"
    setup = section("Setup")
    first_step = re.search(r"^### (.*)$", setup, re.MULTILINE)
    assert first_step and "1." in first_step.group(1)
    assert setup.index("uv tool install --managed-python grokbot-kit") < setup.index("### 2.")


# C128 - AC 104
def test_single_multichoice_cli_question() -> None:
    p = norm(paragraph_with("múltipla escolha"))
    assert "`setup.installed` vazio no `grokbot-kit doctor --json`" in p
    assert "uma única pergunta" in p
    assert "múltipla escolha" in p
    for tool in ("`opencode`", "`claude`", "`codex`"):
        assert tool in p, tool


# C129 - AC 105
def test_cli_add_and_login_per_cli() -> None:
    s = norm(section("CLIs"))
    assert "`grokbot-kit setup cli add <tool>`" in s
    assert "para cada CLI" in s
    assert "assinatura" in s
    assert "API key" in s
    assert "grokbot-kit login <tool> --method subscription" in s
    assert "grokbot-kit login <tool> --method api-key" in s
    assert s.index("grokbot-kit setup cli add <tool>") < s.index("grokbot-kit login <tool>")


# C130 - AC 106, AD-031
def test_never_ask_secret_in_chat() -> None:
    p = norm(paragraph_with("sender key"))
    assert p.lower().count("nunca") >= 1
    for needle in ("API key", "sender key", "URL secreta", "no chat"):
        assert needle in p, needle
    assert re.search(r"`grokbot-kit secret set <\w+>`", p)
    assert "entrada padrão" in p
    assert "ferramentas" in p
    assert "campo mascarado" in p
    assert re.search(r"[Nn]unca passe o valor como argumento", p)
    assert "Só sem campo mascarado" in p
    assert p.index("campo mascarado") < p.index("Só sem campo mascarado") < p.index("terminal do box")


# C131 - AC 107
def test_leaked_secret_handling() -> None:
    p = norm(paragraph_with("regenerar"))
    assert "colar" in p or "colado" in p
    assert "print" in p
    assert "painel" in p
    assert "`grokbot-kit secret set" in p
    assert "não grave" in p
    assert "não repita" in p


# C132 - AC 108
def test_default_cli_step() -> None:
    s = norm(section("CLI padrão"))
    assert "Pergunte" in s
    assert "grokbot-kit setup default <tool>" in s


# C133 - AC 109, door 22
def test_models_refresh_and_free_first() -> None:
    s = norm(section("Modelos e tiers"))
    assert "grokbot-kit setup models refresh" in s
    assert "só ids da lista descoberta" in s
    assert "gratuitos do opencode primeiro" in s
    assert "`trivial`" in s and "`standard`" in s
    assert "grokbot-kit setup tiers <tool> <tier> <id>" in s
    assert s.index("grokbot-kit setup models refresh") < s.index("grokbot-kit setup tiers")


# C134 - AC 110, AD-031
def test_routine_setup_order() -> None:
    s = norm(section("Routine"))
    steps = [
        "webhook trigger",
        "grokbot-kit secret set <bot>-url",
        "grokbot-kit secret set <bot>-key",
        "grokbot-kit route add <bot>",
        "grokbot-kit route test <bot>",
    ]
    positions = [s.index(step) for step in steps]
    assert positions == sorted(positions), positions
    secrets = s[positions[1] : positions[3]]
    assert "entrada padrão" in secrets
    preference = [secrets.index(needle) for needle in ("da routine", "campo mascarado", "terminal do box")]
    assert preference == sorted(preference), preference
    assert "só sem campo mascarado" in secrets


# C135 - AC 111
def test_print_warning_before_panel() -> None:
    s = section("Routine")
    warning = next(i for i, line in enumerate(s.splitlines()) if "print" in line and "colagem" in line)
    line = s.splitlines()[warning]
    assert "mensagem" in line and "key" in line
    panel = next(i for i, line in enumerate(s.splitlines()) if "abra o painel" in line.lower())
    assert warning < panel


# C136 - AC 112
def test_routine_prompt_parse_schema_target() -> None:
    blocks = re.findall(r"^```text\n(.*?)^```", section("Prompt da routine"), re.DOTALL | re.MULTILINE)
    assert len(blocks) == 1
    prompt = norm(blocks[0])
    assert "`body`" in prompt and "JSON" in prompt and "parse" in prompt
    assert '"grokbot-kit.event/v1"' in prompt
    assert "`schema`" in prompt
    assert "`target`" in prompt and "ignore" in prompt.lower()


# C137 - AC 113
def test_run_with_tool_and_model() -> None:
    assert any(c.startswith("grokbot-kit run --tool <cli> --model <id> --target <este bot>") for c in sh_commands())


# C138 - AC 114
def test_omit_tool_for_default() -> None:
    p = norm(paragraph_with("Omita `--tool`"))
    assert "CLI padrão" in p
    runs = [c for c in sh_commands() if c.startswith("grokbot-kit run ")]
    assert any("--tool" not in c for c in runs)


# C139 - AC 115
def test_tier_classification_one_line() -> None:
    p = norm(paragraph_with("--tier <tier>"))
    for tier in ("`trivial`", "`standard`", "`complex`"):
        assert tier in p, tier
    assert "uma linha" in p
    runs = [c for c in sh_commands() if c.startswith("grokbot-kit run ")]
    assert any("--tier <tier>" in c and "--model" not in c for c in runs)


COMPLEX_CLASSES = [
    ("revisão de segurança",),
    ("decisões de arquitetura",),
    ("checagem de fatos",),
    ("produção", "credenciais", "dados sensíveis"),
]


# C140 - AC 116
@pytest.mark.parametrize("words", COMPLEX_CLASSES)
def test_rubric_complex_classes_never_free(words: tuple[str, ...]) -> None:
    rubric = section("Rubrica")
    rows = [line for line in rubric.splitlines() if line.startswith("| `complex`")]
    assert len(rows) == 1
    for word in words:
        assert word in rows[0], word
    rule = norm(paragraph_with("nunca vão a modelos gratuitos"))
    assert "`complex`" in rule


# C141 - AC 117
def test_event_handling() -> None:
    s = norm(section("Quando um evento chega"))
    assert "parse" in s and "`body`" in s and "JSON" in s
    for field in ("`event`", "`status`", "`summary`", "`output_file`"):
        assert field in s, field
    p = norm(paragraph_with("`resume_hint`"))
    assert "`needs_input`" in p and "`denied`" in p
    assert "mostre" in p.lower()


# C142 - AC 118
def test_undelivered_and_redeliver() -> None:
    p = norm(paragraph_with("`undelivered.jsonl`"))
    assert "task dir" in p
    assert "`grokbot-kit redeliver <task_id>`" in p


def help_of(words: list[str]) -> subprocess.CompletedProcess[str]:
    exe = shutil.which("grokbot-kit")
    assert exe is not None, "console script grokbot-kit não instalado"
    return subprocess.run([exe, *words, "--help"], capture_output=True, text=True, check=False, timeout=60)


# C143 - AC 119
def test_every_cited_command_exists() -> None:
    commands = cited_commands()
    assert len(commands) >= 15
    for command in commands:
        tokens = shlex.split(command.replace("<", "'<").replace(">", ">'"))[1:]
        words: list[str] = []
        for token in tokens:
            if not re.fullmatch(r"[a-z][a-z-]*", token):
                break
            words.append(token)
        result = help_of(words)
        assert result.returncode == 0, (command, result.stderr)
        for flag in re.findall(r"(?<!\S)(--[a-z][a-z-]*)", command.split(" -- ")[0]):
            assert flag in result.stdout, (command, flag)
    rule = norm(paragraph_with("Nunca invente"))
    for needle in ("id de modelo", "comando", "flag"):
        assert needle in rule, needle


ALLOWED = {"grokbot-kit", "uv", "pipx", "opencode", "claude", "codex"}


# C144 - door 8
def test_install_location_and_allowed_commands() -> None:
    p = norm(paragraph_with("/home/box/agent-data/workflows/grokbot-kit/"))
    assert "copi" in p.lower()
    assert "workflows" in p
    commands = sh_commands()
    assert commands
    for command in commands:
        assert command.split()[0] in ALLOWED, command
    rule = norm(paragraph_with("Só chame"))
    for program in ("`grokbot-kit`", "`uv`", "`pipx`"):
        assert program in rule, program


MODEL_ID_PATTERNS = [
    r"\b(haiku|sonnet|opus|fable)\b",
    r"\b(gpt|gemini|claude|llama|mistral|deepseek|qwen|grok|glm|kimi|minimax|nemotron)-[\w.]+",
    r"\b[\w.]+-free\b",
    r"\b(opencode|anthropic|openai|google|xai|deepseek|mistral|meta|qwen|openrouter|groq|zai|moonshotai)/(?!(claude|codex|opencode)\b)[\w.-]+",
    r"\bo[1-9](-\w+)?\b",
]


# C145 - AC 109, AC 119, AD-011
@pytest.mark.parametrize("pattern", MODEL_ID_PATTERNS)
def test_no_literal_model_ids(pattern: str) -> None:
    assert not re.search(pattern, text(), re.IGNORECASE), re.search(pattern, text(), re.IGNORECASE)


# --- kit-update (checks C32-C36; AC 27-33) ------------------------------------------------------------------------

LATEST_URL = "https://github.com/rodrigo-pasini/grokbot-kit/releases/latest/download/SKILL.md"
UPDATE_COMMANDS = (
    "grokbot-kit update check --json",
    "grokbot-kit update apply",
    "grokbot-kit update later",
    "grokbot-kit update skip <latest>",
)


# C32 - AC 27
def test_update_check_before_setup_and_task() -> None:
    b = body()
    s = section("Atualização")
    assert b.index(s) < b.index("## Setup (primeira vez)") < b.index("## Tarefa")
    p = norm(paragraph_with("`grokbot-kit update check --json`"))
    assert p in norm(s)
    assert "antes do setup" in p.lower()
    assert "antes de delegar uma tarefa" in p.lower()
    assert "`PATH`" in p


# C33 - AC 28, AC 29
def test_update_three_options() -> None:
    s = norm(section("Atualização"))
    p = norm(paragraph_with("três opções"))
    assert p in s
    assert "`ask` `true`" in p
    assert "uma única pergunta" in p
    assert "escolha múltipla" in p
    assert "`latest`" in p
    options = [
        ("Atualizar agora", "`grokbot-kit update apply`"),
        ("Agora não", "`grokbot-kit update later`"),
        ("Pular a `<latest>`", "`grokbot-kit update skip <latest>`"),
    ]
    for label, command in options:
        item = norm(paragraph_with(label))
        assert item in s, label
        assert command in item, (label, command)


# C34 - AC 30
def test_update_refreshes_skill() -> None:
    s = norm(section("Atualização"))
    p = norm(paragraph_with(LATEST_URL))
    assert p in s
    assert "`grokbot-kit update apply` sair com `0`" in p
    assert "redirects" in p
    assert "sobrescreva o `SKILL.md`" in p
    assert "diretório de workflows" in p
    assert "releia a skill" in p
    assert p.index("baixe") < p.index("sobrescreva") < p.index("releia")


# C35 - AC 31, AC 32
def test_update_failure_and_silence() -> None:
    s = norm(section("Atualização"))
    failure = norm(paragraph_with("sair com `1` ou `2`"))
    assert failure in s
    assert "stderr" in failure
    assert "siga com o que ele pediu" in failure
    silence = norm(paragraph_with("sem mencionar atualização"))
    assert silence in s
    assert "`ask` `false`" in silence
    assert "`error`" in silence


# C36 - AC 33: os quatro `update` estão entre os comandos citados, e nenhum comando citado é `curl`
def test_every_cited_command_exists_includes_update() -> None:
    commands = cited_commands()
    for command in UPDATE_COMMANDS:
        assert command in commands, command
    assert not any(c.split()[0] == "curl" for c in sh_commands())
    assert not re.search(r"`curl\s", text())


# C54 - AC 60, AC 61
def test_plugin_list_and_run() -> None:
    s = norm(section("Plugins"))
    assert "```sh grokbot-kit plugin list --json ```" in s
    p = norm(paragraph_with("o que o kit sabe fazer"))
    assert "antes de delegar uma tarefa" in p
    shown = norm(paragraph_with("Mostre ao usuário o `name`"))
    for field in ("`name`", "`description`", "`capabilities`"):
        assert field in shown, field
    run = norm(paragraph_with("casa com um plugin listado"))
    assert "não escreva prompt" in run
    assert "`grokbot-kit run --plugin <nome>`" in run
    assert "`--input <entrada>=<valor>`" in run
    assert (
        "grokbot-kit run --plugin <nome> --input <entrada>=<valor> --target <este bot> --label <rótulo>"
        in sh_commands()
    )
    assert "[Plugins](#plugins)" in section("Tarefa")


# C55 - AC 62
def test_plugin_install_confirms() -> None:
    s = norm(section("Plugins"))
    steps = [
        "`grokbot-kit plugin show <origem> --json`",
        "mostre ao usuário as `capabilities`",
        "Pergunte se ele quer instalar",
        "Só com o sim, rode `grokbot-kit plugin add <origem> --yes`",
    ]
    positions = [s.find(step) for step in steps]
    assert -1 not in positions, list(zip(steps, positions, strict=True))
    assert positions == sorted(positions)
    assert s.count("plugin add") == 1, "o `plugin add` só aparece depois do sim"


# C56 - AC 63
def test_plugin_commands_exist_in_help() -> None:
    for command in sh_commands():
        assert not command.startswith("curl"), command
    assert not [c for c in cited_commands() if "curl" in c]
    plugin_commands = [c for c in cited_commands() if "plugin" in c]
    assert len(plugin_commands) >= 4, plugin_commands
    for command in plugin_commands:
        tokens = shlex.split(command.replace("<", "'<").replace(">", ">'"))[1:]
        words = [t for t in tokens[:2] if re.fullmatch(r"[a-z][a-z-]*", t)]
        result = help_of(words)
        assert result.returncode == 0, (command, result.stderr)
        for flag in re.findall(r"(?<!\S)(--[a-z][a-z-]*)", command):
            assert flag in result.stdout, (command, flag)


# --- model-setup-docs (checks C13-C18; AC 14-20) ------------------------------------------------------------------


# C13 - AC 14
def test_models_refresh_json_first() -> None:
    s = norm(section("Modelos e tiers"))
    assert "grokbot-kit setup models refresh --json" in s
    first = s.index("grokbot-kit setup models refresh --json")
    assert first < s.index("grokbot-kit setup providers")
    assert first < s.index("grokbot-kit setup tiers")


# C14 - AC 15
def test_providers_question() -> None:
    p = norm(paragraph_with("provedores do opencode"))
    assert "única pergunta de múltipla escolha" in p
    assert "`provider`" in p
    assert "quantos ids" in p
    assert "grokbot-kit setup providers opencode <provider>" in norm(section("Modelos e tiers"))
    assert "`opencode` instalado" in p


# C15 - AC 16
def test_paid_provider_login() -> None:
    p = norm(paragraph_with("provedor pago"))
    assert "login" in p
    assert "grokbot-kit login opencode" in p


# C16 - AC 17
def test_tier_question_per_tier() -> None:
    p = norm(paragraph_with("uma pergunta por tier"))
    for tier in ("`trivial`", "`standard`", "`complex`"):
        assert tier in p, tier
    assert "até 4 ids" in p
    assert "lista descoberta" in p
    assert "recomendado primeiro" in p
    assert "só ids dos provedores escolhidos" in p
    assert "grokbot-kit setup tiers <tool> <tier> <id>" in norm(section("Modelos e tiers"))


# C17 - AC 18, AC 19
def test_free_first_only_without_paid() -> None:
    free = norm(paragraph_with("gratuitos do opencode primeiro"))
    assert "só o provedor `opencode`" in free
    assert "`trivial` e `standard`" in free
    paid = norm(paragraph_with("provedor que não é `opencode`"))
    assert "primeiro" in paid
    assert "todos os tiers" in paid


# C18 - AC 20
def test_change_models_redo_steps() -> None:
    p = norm(paragraph_with("trocar os modelos"))
    assert "grokbot-kit setup models refresh --json" in p
    assert "provedores" in p and "tiers" in p
    for absent in ("setup cli add", "login", "route add"):
        assert absent not in p, absent


# C50 - AC 35 da needs-input-reply
def test_needs_input_reply_flow() -> None:
    s = norm(section("Quando um evento chega"))
    waiting = norm(paragraph_with("`needs_input.reply_deadline` preenchido"))
    assert "regra de risco" in waiting and "`reply_deadline`" in waiting and "`grokbot-kit reply`" in waiting
    notify = norm(paragraph_with("`needs_input.reply_deadline` `null`"))
    assert "`resume_hint`" in notify
    assert "Pedido de permissão" in s


def low_list() -> str:
    s = section("Pedido de permissão")
    return s.split("Baixo risco é só isto:", 1)[1].split("Pergunte ao usuário", 1)[0]


# C51 - AC 36 da needs-input-reply
def test_risk_rule_low_list() -> None:
    items = [line[2:] for line in low_list().splitlines() if line.startswith("- ")]
    assert len(items) == 4
    joined = norm(" ".join(items))
    for needle in ("ler, listar ou buscar arquivos", "testes", "linters", "checagem de tipos", "build"):
        assert needle in joined, needle
    assert "dentro do `cwd`" in joined
    for cmd in ("`git status`", "`git diff`", "`git log`", "`git show`"):
        assert cmd in joined, cmd
    for forbidden in ("rm", "push", "curl", "install"):
        assert not re.search(rf"\b{forbidden}\b", joined), forbidden


# C52 - AC 37 da needs-input-reply
def test_risk_rule_ask_list() -> None:
    s = section("Pedido de permissão")
    ask = norm(s.split("Pergunte ao usuário", 1)[1].split("De baixo risco", 1)[0])
    for needle in (
        "fora do `cwd`",
        "`..`",
        "mais de um comando",
        "`;`",
        "`&&`",
        "`|`",
        "`$(...)`",
        "redirecionamento",
        "`git fetch`",
        "`git pull`",
        "`git push`",
        "`git clone`",
        "download",
        "instalação de pacote",
        "apagar arquivos",
        "histórico",
        "`.env`",
        "`~/.ssh`",
        "`sudo`",
        "não consegue classificar",
    ):
        assert needle in ask, needle


# C53 - AC 38, 39 e 40 da needs-input-reply
def test_reply_by_and_upgrade() -> None:
    s = norm(section("Pedido de permissão"))
    commands = cited_commands()
    assert "grokbot-kit reply <task_id> <request_id> allow --by bot" in commands
    assert "conte ao usuário, em uma linha, o que aprovou" in s
    assert any(c.startswith("grokbot-kit reply <task_id> <request_id> allow --by user") for c in commands)
    assert "nunca nega sozinho" in s and "o kit nega no `reply_deadline`" in s
    state = norm(section("Ver o estado"))
    assert "`cli.opencode.reply.warning`" in state
    assert "grokbot-kit setup cli upgrade opencode" in commands
