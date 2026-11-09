"""Provas do `AGENTS.md`, o único arquivo de instruções do projeto (sdlc-gates: C34-C36, C48; AC 26, 27, 35)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def text() -> str:
    return (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def section(heading: str) -> str:
    lines = text().splitlines()
    assert f"## {heading}" in lines, heading
    start = lines.index(f"## {heading}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def table(body: str) -> list[list[str]]:
    rows = [line for line in body.splitlines() if line.startswith("|")]
    cells = [[c.strip() for c in row.strip().strip("|").split("|")] for row in rows]
    return [row for row in cells if not all(re.fullmatch(r":?-+:?", c) for c in row)]


# C34 - AC 26
def test_sections_and_autonomy() -> None:
    for heading in ("Fluxo", "Autonomia", "Skills", "Ambiente"):
        section(heading)
    rows = table(section("Autonomia"))
    header, body = rows[0], rows[1:]
    rodrigo = next(i for i, name in enumerate(header) if "Rodrigo" in name)
    cells = [row[rodrigo] for row in body if len(row) > rodrigo and row[rodrigo] and row[rodrigo] != "-"]
    assert len(cells) == 3, cells
    for word in ("plano", "merge", "tag"):
        assert len([c for c in cells if word in c.lower()]) == 1, (word, cells)


# C35 - AC 26
def test_skills_and_environment() -> None:
    skills = section("Skills")
    for needle in ("tlc-spec-lean", "tlc-discover", "## Intent", "tools/sdlc.py spec", "--root docs"):
        assert needle in skills, needle
    no_spec = [row for row in table(skills) if "sem spec" in row[-1]]
    assert len(no_spec) == 1, table(skills)
    for kind in ("dependências", "docs", "release"):
        assert kind in no_spec[0][0], (kind, no_spec)
    environment = section("Ambiente")
    assert "opencode-go" in environment
    assert re.search(r"box.*só pelo bot|só pelo bot.*box", environment), environment


# C36 - AC 27
def test_carries_former_claude_md() -> None:
    body = text()
    for needle in (
        "gate-worktree.sh",
        "GROKBOT_KIT_ALLOW_MAIN_EDIT=1",
        "508cc3e",
        "Co-Authored-By",
        "profile: standard",
        "budget: 150k",
    ):
        assert needle in body, needle


# C48 - AC 35, door 9
def test_documentation_section() -> None:
    docs = section("Documentação")
    for needle in (
        "docs/pt-BR/",
        "mesmo commit",
        "CHANGELOG.md",
        "## [Unreleased]",
        "docs/plugins.md",
        "docs/event.md",
        "Docs: n/a -",
    ):
        assert needle in docs, needle
    flat = re.sub(r"\s+", " ", docs)
    assert "inglês" in flat and "5 primeiras linhas" in flat
    assert re.search(r"Fora da regra: `docs/\.specs/`.*`AGENTS\.md`.*`CHANGELOG\.md`.*SKILL\.md", flat), flat
    rows = {row[0]: row[1] for row in table(docs)[1:]}
    assert "`README.md`" in rows["subcomando ou flag"] and "doc do tema" in rows["subcomando ou flag"]
    assert "`docs/event.md`" in rows["campo do evento `grokbot-kit.event/v1`"]
    assert "`docs/plugins.md`" in rows["plugin, manifesto ou capacidade"]
    assert "`CHANGELOG.md`" in rows["qualquer comportamento visível"]
