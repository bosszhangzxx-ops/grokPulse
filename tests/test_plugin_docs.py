"""Provas do guia de autoria `docs/plugins.md` e da tradução `docs/pt-BR/plugins.md` (checks C57 e C63; AC 64 e 69,
doors 1, 2, 6, 8, 10 e 11; AD-041 e AD-045).

A tabela da matriz de cada guia é comparada com a matriz que `plugin.py` usa; o C8 (S1) prova que essa é a de
`spike.md`.
"""

import re
from pathlib import Path
from typing import NamedTuple

import pytest

from grokbot_kit import plugin

ROOT = Path(__file__).resolve().parent.parent


class Guide(NamedTuple):
    path: Path
    other: str
    warning: str
    layout: str
    manifest: str
    kinds: str
    max_bytes: str
    matrix: str
    result: str
    example: str


GUIDES = [
    Guide(
        ROOT / "docs" / "plugins.md",
        "](pt-BR/plugins.md)",
        "may change before 1.0",
        "Layout",
        "Manifest and capabilities",
        '`"repo"`, `"text"` or `"file"`',
        "`max_bytes` (default `16384`)",
        "Capability matrix",
        "Result",
        "Annotated example: `code-review`",
    ),
    Guide(
        ROOT / "docs" / "pt-BR" / "plugins.md",
        "](../plugins.md)",
        "pode mudar antes da 1.0",
        "Layout",
        "Manifesto e capacidades",
        '`"repo"`, `"text"` ou `"file"`',
        "`max_bytes` (padrão `16384`)",
        "Matriz de capacidades",
        "Resultado",
        "Exemplo comentado: `code-review`",
    ),
]


def section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.DOTALL | re.MULTILINE)
    assert match, f"sem a seção {heading!r}"
    return match.group(1)


# C57 - AC 64
@pytest.mark.parametrize("g", GUIDES, ids=["en", "pt-BR"])
def test_guide_sections(g: Guide) -> None:
    text = g.path.read_text(encoding="utf-8")
    head = text.split("\n## ", 1)[0]
    assert g.warning in head, "o aviso vem antes da primeira seção"
    assert g.other in head, "o guia aponta para a outra língua antes da primeira seção"

    layout = section(text, g.layout)
    for part in (".claude-plugin/plugin.json", "grokbot-kit.toml", "skills/<skill>/SKILL.md"):
        assert part in layout, part
    for refused in ("`hooks/`", "`commands/`", "`agents/`", "`.mcp.json`", "`.lsp.json`"):
        assert refused in layout, refused

    manifest = section(text, g.manifest)
    for needle in (
        '`"grokbot-kit.plugin/v0"`',
        plugin.NAME_RE.pattern,
        g.kinds,
        '`"task-dir"`, `"none"`',
        '`"on"`, `"off"`',
        "`{workspace}`",
        "`{result_file}`",
        "`{task_dir}`",
        g.max_bytes,
    ):
        assert needle in manifest, needle

    rows = re.findall(r"^\| `(claude|opencode|codex)` \| (.*) \|$", section(text, g.matrix), re.MULTILINE)
    table = {cli: [cell.strip(" `") for cell in cells.split("|")] for cli, cells in rows}
    assert table == {cli: [cells[c] for c in plugin.MATRIX_COLUMNS] for cli, cells in plugin.matrix().items()}

    result = section(text, g.result)
    for needle in ("`<task_dir>/result.json`", "`GROKBOT_KIT_RESULT_FILE`", "`result_invalid`", "`max_bytes`"):
        assert needle in result, needle

    example = section(text, g.example)
    builtin = next(p for p in plugin.builtins() if p.name == "code-review")
    assert f"```toml\n{(builtin.path / 'grokbot-kit.toml').read_text(encoding='utf-8')}```" in example
    assert f"```markdown\n{(builtin.path / 'prompt.md').read_text(encoding='utf-8')}```" in example


# C63 - AC 69, AC 70, doors 10 e 11
@pytest.mark.parametrize(
    ("g", "contract", "spelling"),
    [
        (
            GUIDES[0],
            "An allowed command writes wherever its options and the code it runs allow.",
            "Another spelling, such as quotes, gets around them.",
        ),
        (
            GUIDES[1],
            "Um comando liberado escreve onde as opções e o código que ele roda deixam.",
            "Outra grafia, como aspas, contorna a regra.",
        ),
    ],
    ids=["en", "pt-BR"],
)
def test_write_contract(g: Guide, contract: str, spelling: str) -> None:
    matrix = " ".join(section(g.path.read_text(encoding="utf-8"), g.matrix).split())
    assert contract in matrix
    assert spelling in matrix
    assert "`>`" in matrix
    assert "`--output`" in matrix
