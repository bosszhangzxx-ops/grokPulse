"""Provas da doc para quem usa o kit (model-setup-docs: checks C38-C41, C44-C49; AC 36-39, 42-46, door 7).

O checador da door 7 roda no `uv run pytest` padrão: cada subcomando de topo do parser de `grokbot-kit` aparece como
`grokbot-kit <subcomando>` nos dois READMEs, e todo `README.md`, `CONTRIBUTING.md` e `docs/*.md` tem o par em
`docs/pt-BR/` com o mesmo nome, os dois linkados um ao outro nas 5 primeiras linhas.
"""

import argparse
import json
import re
import shutil
from pathlib import Path

from grokbot_kit.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
READMES = ("README.md", "docs/pt-BR/README.md")
LINK_LINES = 5
LINK_RE = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")


def top_level_commands(parser: argparse.ArgumentParser) -> list[str]:
    """Os subcomandos de topo registrados no parser, na ordem."""
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return list(sub.choices)


def paired_docs(root: Path) -> list[Path]:
    """Os docs em inglês que precisam de par em `docs/pt-BR/`: `README.md`, `CONTRIBUTING.md` e `docs/*.md`."""
    found = [root / name for name in ("README.md", "CONTRIBUTING.md") if (root / name).exists()]
    return found + sorted((root / "docs").glob("*.md"))


def links_to(path: Path, other: Path) -> bool:
    """`path` tem, nas 5 primeiras linhas, um link Markdown relativo que resolve para `other`."""
    head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:LINK_LINES])
    return any((path.parent / target).resolve() == other.resolve() for target in LINK_RE.findall(head))


def check(root: Path, commands: list[str]) -> list[str]:
    """As falhas da door 7 em `root`, cada uma citando o arquivo; vazio quando a doc está em dia."""
    failures = []
    for readme in READMES:
        path = root / readme
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        for command in commands:
            if not re.search(rf"grokbot-kit {re.escape(command)}\b", text):
                failures.append(f"{readme}: no `grokbot-kit {command}` (a top-level subcommand of the parser)")
    for doc in paired_docs(root):
        rel = doc.relative_to(root).as_posix()
        pair = root / "docs" / "pt-BR" / doc.name
        pair_rel = pair.relative_to(root).as_posix()
        if not pair.exists():
            failures.append(f"{rel}: no pt-BR pair at {pair_rel}")
            continue
        if not links_to(doc, pair):
            failures.append(f"{rel}: no link to {pair_rel} in its first {LINK_LINES} lines")
        if not links_to(pair, doc):
            failures.append(f"{pair_rel}: no link to {rel} in its first {LINK_LINES} lines")
    english = {doc.name for doc in paired_docs(root)}
    for pair in sorted((root / "docs" / "pt-BR").glob("*.md")):
        if pair.name not in english:
            failures.append(f"docs/pt-BR/{pair.name}: no English original (README.md, CONTRIBUTING.md or docs/*.md)")
    return failures


def copy_docs(dest: Path) -> Path:
    """Uma cópia dos docs pareados do repositório (e dos pares) em `dest`."""
    for doc in paired_docs(ROOT):
        for path in (doc, ROOT / "docs" / "pt-BR" / doc.name):
            if path.exists():
                target = dest / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    return dest


def section(path: str, heading: str) -> str:
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    start = lines.index(f"## {heading}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def commands() -> list[str]:
    return top_level_commands(build_parser())


# sdlc-gates: os gates de flags, campos do evento e links (AC 36-38)
EVENT_SCHEMA = ROOT / "src" / "grokbot_kit" / "assets" / "event.v1.json"
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def long_options(parser: argparse.ArgumentParser, path: str = "") -> list[tuple[str, str]]:
    """Cada opção longa (menos `--help`) de cada subcomando, como `(caminho do subcomando, opção)`."""
    found = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                found += long_options(child, f"{path} {name}".strip())
        else:
            found += [(path, opt) for opt in action.option_strings if opt.startswith("--") and opt != "--help"]
    return found


def english_text(root: Path) -> str:
    docs = [root / "README.md", *sorted((root / "docs").glob("*.md"))]
    return "\n".join(p.read_text(encoding="utf-8") for p in docs if p.exists())


def portuguese_text(root: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((root / "docs" / "pt-BR").glob("*.md")))


def check_flags(root: Path, options: list[tuple[str, str]]) -> list[str]:
    failures = []
    texts = (("README.md or docs/*.md", english_text(root)), ("docs/pt-BR/*.md", portuguese_text(root)))
    for path, option in options:
        name = f"grokbot-kit {path} {option}".replace("  ", " ")
        for where, text in texts:
            if not re.search(rf"(?<![\w-]){re.escape(option)}(?![\w-])", text):
                failures.append(f"{name}: not in {where}")
    return failures


def event_fields() -> list[str]:
    return list(json.loads(EVENT_SCHEMA.read_text(encoding="utf-8"))["properties"])


def check_event_fields(root: Path, fields: list[str]) -> list[str]:
    failures = []
    for where, text in (("README.md or docs/*.md", english_text(root)), ("docs/pt-BR/*.md", portuguese_text(root))):
        failures += [f"event field `{f}`: not in {where}" for f in fields if f"`{f}`" not in text]
    return failures


def linked_docs(root: Path) -> list[Path]:
    found = [root / name for name in ("README.md", "CONTRIBUTING.md") if (root / name).exists()]
    return found + sorted((root / "docs").glob("*.md")) + sorted((root / "docs" / "pt-BR").glob("*.md"))


def check_links(root: Path) -> list[str]:
    """Cada link Markdown relativo que aponta para arquivo inexistente, como `<arquivo>:<linha>`."""
    failures = []
    for doc in linked_docs(root):
        fenced = False
        for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                continue
            for target in MD_LINK_RE.findall(line):
                path = target.split("#", 1)[0]
                if not path or re.match(r"^[a-z][a-z0-9+.-]*:", path):
                    continue
                if not (doc.parent / path).exists():
                    failures.append(f"{doc.relative_to(root).as_posix()}:{number}: broken link {target}")
    return failures


# C38 - AC 36
def test_readme_commands_section() -> None:
    expected = commands()
    assert len(expected) == 14
    for readme, heading in zip(READMES, ("Commands", "Comandos"), strict=True):
        rows = [line for line in section(readme, heading).splitlines() if line.startswith("| `grokbot-kit ")]
        named = [re.match(r"\| `grokbot-kit ([a-z-]+)", row).group(1) for row in rows]  # type: ignore[union-attr]
        assert named == expected, (readme, named)


# C39 - AC 37
def test_readme_plugins_section() -> None:
    for readme, link in zip(READMES, ("](docs/plugins.md)", "](plugins.md)"), strict=True):
        s = section(readme, "Plugins")
        assert "grokbot-kit run --plugin code-review --input pr=" in s, readme
        assert link in s, readme


# C40 - AC 38
def test_readme_models_and_fallback() -> None:
    for readme in READMES:
        text = (ROOT / readme).read_text(encoding="utf-8")
        for needle in ("grokbot-kit setup providers", "grokbot-kit setup tiers", "model_fallbacks"):
            assert needle in text, (readme, needle)


# C41 - AC 39
def test_contributing_pair() -> None:
    english = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8").splitlines()
    portuguese = (ROOT / "docs" / "pt-BR" / "CONTRIBUTING.md").read_text(encoding="utf-8").splitlines()
    assert english[0] == "# Contributing to grokbot-kit"
    assert portuguese[0] == "# Contribuindo com o grokbot-kit"
    for prefix in ("## ", "### "):
        assert len([h for h in english if h.startswith(prefix)]) == len([h for h in portuguese if h.startswith(prefix)])


# C44 - AC 42, door 7
def test_gate_reports_missing_command(tmp_path: Path) -> None:
    root = copy_docs(tmp_path)
    readme = root / "docs" / "pt-BR" / "README.md"
    lines = readme.read_text(encoding="utf-8").splitlines(keepends=True)
    readme.write_text("".join(line for line in lines if "grokbot-kit redeliver" not in line), encoding="utf-8")
    failures = check(root, commands())
    assert [f for f in failures if "redeliver" in f] == [
        "docs/pt-BR/README.md: no `grokbot-kit redeliver` (a top-level subcommand of the parser)"
    ]
    parser = build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    sub.add_parser("foo")
    failures = check(copy_docs(tmp_path / "foo"), top_level_commands(parser))
    assert {f.split(":")[0] for f in failures if "`grokbot-kit foo`" in f} == set(READMES)


# C45 - AC 43, door 7
def test_gate_reports_missing_pair(tmp_path: Path) -> None:
    root = copy_docs(tmp_path)
    (root / "docs" / "pt-BR" / "plugins.md").unlink()
    (root / "docs" / "novo.md").write_text("# novo\n", encoding="utf-8")
    failures = check(root, commands())
    assert any(f.startswith("docs/plugins.md: no pt-BR pair") for f in failures), failures
    assert any(f.startswith("docs/novo.md: no pt-BR pair") for f in failures), failures


def test_gate_reports_portuguese_only(tmp_path: Path) -> None:
    """Review do PR 29: um doc só em `docs/pt-BR/`, sem o original em inglês, também falha."""
    root = copy_docs(tmp_path)
    (root / "docs" / "pt-BR" / "so-pt.md").write_text("# só pt\n", encoding="utf-8")
    failures = check(root, commands())
    assert any(f.startswith("docs/pt-BR/so-pt.md: no English original") for f in failures), failures


# C46 - AC 44, door 7
def test_gate_reports_missing_link(tmp_path: Path) -> None:
    root = copy_docs(tmp_path)
    readme = root / "README.md"
    lines = readme.read_text(encoding="utf-8").splitlines(keepends=True)
    readme.write_text("".join(line for line in lines if "docs/pt-BR/README.md" not in line), encoding="utf-8")
    plugins = root / "docs" / "pt-BR" / "plugins.md"
    lines = plugins.read_text(encoding="utf-8").splitlines(keepends=True)
    plugins.write_text("".join(line for line in lines if "](../plugins.md)" not in line), encoding="utf-8")
    failures = check(root, commands())
    assert any(f.startswith("README.md: no link to docs/pt-BR/README.md") for f in failures), failures
    assert any(f.startswith("docs/pt-BR/plugins.md: no link to docs/plugins.md") for f in failures), failures


# C47 - AC 42-44
def test_gate_repo_clean() -> None:
    assert check(ROOT, commands()) == []


# C48 - AC 45 (sdlc-gates C47, AD-052: a regra mora no `AGENTS.md`)
def test_agents_md_doc_rule() -> None:
    text = re.sub(r"\s+", " ", (ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    rule = next((s for s in text.split(" - ") if "mesmo PR" in s), "")
    assert "`README.md`" in rule, rule
    assert "inglês" in rule and "pt-BR" in rule, rule
    assert "critério de doc" in rule, rule


# C49 - AC 46
def test_pr_template_doc_item() -> None:
    items = [
        line for line in (ROOT / ".github" / "pull_request_template.md").read_text().splitlines() if "- [ ]" in line
    ]
    doc = [i for i in items if "README.md" in i and "docs" in i and "pt-BR" in i]
    assert doc, items
    # sdlc-gates C56 - AC 43: o escape da door 9 no mesmo item
    assert any("Docs: n/a - <reason>" in i for i in doc), doc


def strip_from(paths: list[Path], needle: str) -> None:
    for path in paths:
        path.write_text(path.read_text(encoding="utf-8").replace(needle, ""), encoding="utf-8")


# sdlc-gates C49 - AC 36
def test_gate_reports_missing_flag(tmp_path: Path) -> None:
    options = long_options(build_parser())
    english = copy_docs(tmp_path / "en")
    strip_from([english / "README.md", *(english / "docs").glob("*.md")], "--timeout")
    failures = check_flags(english, options)
    assert [f for f in failures if "--timeout" in f] == ["grokbot-kit run --timeout: not in README.md or docs/*.md"]

    portuguese = copy_docs(tmp_path / "pt")
    strip_from(list((portuguese / "docs" / "pt-BR").glob("*.md")), "--timeout")
    failures = check_flags(portuguese, options)
    assert [f for f in failures if "--timeout" in f] == ["grokbot-kit run --timeout: not in docs/pt-BR/*.md"]


def test_gate_flags_repo_clean() -> None:
    options = long_options(build_parser())
    assert ("run", "--timeout") in options and ("", "--version") in options
    assert check_flags(ROOT, options) == []


# sdlc-gates C50 - AC 37
def test_gate_reports_missing_event_field(tmp_path: Path) -> None:
    english = copy_docs(tmp_path / "en")
    strip_from([english / "README.md", *(english / "docs").glob("*.md")], "`exit_code`")
    assert [f for f in check_event_fields(english, event_fields()) if "exit_code" in f] == [
        "event field `exit_code`: not in README.md or docs/*.md"
    ]
    portuguese = copy_docs(tmp_path / "pt")
    strip_from(list((portuguese / "docs" / "pt-BR").glob("*.md")), "`exit_code`")
    assert [f for f in check_event_fields(portuguese, event_fields()) if "exit_code" in f] == [
        "event field `exit_code`: not in docs/pt-BR/*.md"
    ]


def test_gate_event_fields_repo_clean() -> None:
    fields = event_fields()
    assert len(fields) == 26
    assert check_event_fields(ROOT, fields) == []


# sdlc-gates C51 - AC 38
def test_gate_reports_broken_link(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "existe.md").write_text("# existe\n", encoding="utf-8")
    (tmp_path / "docs" / "x.md").write_text(
        "# x\n\n[a](nao-existe.md)\n[b](https://example.com/y.md) [c](http://example.com) [d](#secao)\n"
        "[e](existe.md#secao)\n",
        encoding="utf-8",
    )
    assert check_links(tmp_path) == ["docs/x.md:3: broken link nao-existe.md"]


def test_gate_links_repo_clean() -> None:
    assert check_links(ROOT) == []


def contributing_texts() -> list[str]:
    return [(ROOT / p).read_text(encoding="utf-8") for p in ("CONTRIBUTING.md", "docs/pt-BR/CONTRIBUTING.md")]


# sdlc-gates C37 - AC 28
def test_contributing_gates() -> None:
    english, portuguese = contributing_texts()
    for text, pattern in ((english, "<type>/<issue>/<slug>"), (portuguese, "<tipo>/<issue>/<slug>")):
        for needle in ("commit-msg", "pre-push", "`process`", pattern, "Closes #"):
            assert needle in text, needle


# sdlc-gates C44 - AC 33
def test_contributing_agents_md() -> None:
    for text in contributing_texts():
        for needle in ("AGENTS.md", "2.1.277", "CLAUDE.local.md"):
            assert needle in text, needle


# C54 - AC 41 da needs-input-reply
def test_needs_input_reply_docs() -> None:
    for readme, heading in zip(READMES, ("Commands", "Comandos"), strict=True):
        text = section(readme, heading)
        reply_row = next(line for line in text.splitlines() if line.startswith("| `grokbot-kit reply "))
        assert "--by" in reply_row, readme
        assert "--ask-wait" in text, readme
        assert "cli upgrade" in text, readme
    for doc in (ROOT / "docs" / "event.md", ROOT / "docs" / "pt-BR" / "event.md"):
        text = doc.read_text(encoding="utf-8")
        assert "`needs_input.request_id`" in text, doc
        assert "`needs_input.reply_deadline`" in text, doc


# C55 - AC 42 da needs-input-reply
def test_opencode_version_note() -> None:
    for readme, heading in zip(READMES, ("Permission requests", "Pedidos de permissão"), strict=True):
        text = section(readme, heading)
        assert "Claude Code" in text, readme
        assert "opencode 2.x" in text, readme
        assert "opencode 1.x" in text, readme
        assert "`grokbot-kit setup cli upgrade opencode`" in text, readme


# C56 - AC 43 da needs-input-reply (emendado na release: a seção é a da 0.7.0)
def test_changelog_needs_input_reply() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## [0.7.0]", 1)[1].split("\n## [", 1)[0]
    for term in (
        "grokbot-kit reply",
        "--by",
        "--ask-wait",
        "[ask] wait",
        "request_id",
        "reply_deadline",
        "denied",
        "low-risk",
        "setup cli upgrade",
        "opencode 2",
    ):
        assert term in unreleased, term
