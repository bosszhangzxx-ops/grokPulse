"""Provas da matriz de capacidades da door 8 (checks C1, C7, C8; AC 1, 6-8).

`spike.md` registra a matriz numa tabela com uma linha por célula: CLI, versão, capacidade, valor, sondagem do host, o
comando que provou e a saída observada. A matriz do pacote (`assets/capabilities.json`) tem de ser igual a ela.
"""

import json
import re
from pathlib import Path

import pytest

from grokbot_kit import plugin

SPIKE = Path(__file__).resolve().parent.parent / "docs" / ".specs" / "features" / "plugins" / "spike.md"
VALUES = {"os", "tool", "unsupported"}
ROW_RE = re.compile(r"^\| `(claude|opencode|codex)` \| (.*) \|$", re.MULTILINE)


def spike_rows() -> list[dict[str, str]]:
    match = re.search(r"^## Matriz\n(.*?)(?=^## |\Z)", SPIKE.read_text(encoding="utf-8"), re.DOTALL | re.MULTILINE)
    assert match, "spike.md sem a seção ## Matriz"
    rows = []
    for tool, rest in ROW_RE.findall(match.group(1)):
        version, capability, value, probe, command, output = [c.strip() for c in rest.split(" | ")]
        rows.append(
            {
                "tool": tool,
                "version": version.strip("`"),
                "capability": capability.strip("`"),
                "value": value.strip("`"),
                "probe": probe.strip("`"),
                "command": command,
                "output": output,
            }
        )
    return rows


# C1 - AC 1
def test_matrix_complete() -> None:
    rows = spike_rows()
    cells = [(r["tool"], r["capability"]) for r in rows]
    expected = [(tool, cap) for tool in ("claude", "opencode", "codex") for cap in plugin.MATRIX_COLUMNS]
    assert sorted(cells) == sorted(expected), "exatamente 15 células, uma por CLI e capacidade"
    for r in rows:
        assert r["value"] in VALUES, r
        assert re.search(r"\d+\.\d+", r["version"]), r
        assert r["command"] and r["command"] != "-", r
        assert r["output"] and r["output"] != "-", r


# C7 - AC 7
def test_cli_excluded_when_write_or_workspace_unsupported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cells = {column: "tool" for column in plugin.MATRIX_COLUMNS}
    data = {
        "claude": {**cells, "write": "unsupported"},
        "opencode": {**cells, "workspace_config": "unsupported"},
        "codex": dict(cells),
    }
    path = tmp_path / "capabilities.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("GROKBOT_KIT_CAPABILITIES", str(path))
    matrix = plugin.matrix()
    assert set(matrix["claude"].values()) == {"unsupported"}
    assert set(matrix["opencode"].values()) == {"unsupported"}
    assert matrix["codex"] == cells


# C7 - AC 8
def test_host_dependent_cell_has_probe() -> None:
    for r in spike_rows():
        if r["value"] == "os":
            assert r["probe"] not in ("", "-"), f"célula os sem sondagem do host: {r}"


# C8 - AC 6
def test_package_matrix_matches_spike(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROKBOT_KIT_CAPABILITIES", raising=False)
    spike = {(r["tool"], r["capability"]): r["value"] for r in spike_rows()}
    package = json.loads(plugin.MATRIX_PATH.read_text(encoding="utf-8"))
    assert {(tool, cap): package[tool][cap] for tool in package for cap in package[tool]} == spike
