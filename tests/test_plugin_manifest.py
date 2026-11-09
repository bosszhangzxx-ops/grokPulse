"""Provas das regras do manifesto na própria camada (check C19; AC 19, door 2).

A mesma tabela é provada na fronteira por `tests/test_plugin.py::test_add_refuses_invalid_manifest`.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import plugin_manifest, write_plugin

from grokbot_kit import plugin


def with_manifest(change: Callable[[dict[str, Any]], None], **kwargs: Any) -> Callable[[Path], None]:
    def build(path: Path) -> None:
        manifest = plugin_manifest()
        change(manifest)
        write_plugin(path, manifest, **kwargs)

    return build


def invalid_toml(path: Path) -> None:
    write_plugin(path)
    (path / "grokbot-kit.toml").write_text('schema = "grokbot-kit.plugin/v0"\nname = \n', encoding="utf-8")


def no_claude_manifest(path: Path) -> None:
    write_plugin(path)
    (path / ".claude-plugin" / "plugin.json").unlink()


def no_prompt_file(path: Path) -> None:
    write_plugin(path)
    (path / "prompt.md").unlink()


# C19: as 15 regras, cada uma com o trecho do erro que a nomeia
INVALID: list[tuple[str, Callable[[Path], None], str]] = [
    ("toml_invalido", invalid_toml, "grokbot-kit.toml is not valid TOML"),
    ("schema_ausente", with_manifest(lambda m: m.pop("schema")), "schema is missing"),
    (
        "schema_v1",
        with_manifest(lambda m: m.update(schema="grokbot-kit.plugin/v1")),
        "schema is 'grokbot-kit.plugin/v1'",
    ),
    ("capacidade_sudo", with_manifest(lambda m: m["capabilities"].update(sudo=True)), "unknown key 'sudo'"),
    (
        "write_anywhere",
        with_manifest(lambda m: m["capabilities"].update(write="anywhere")),
        "capabilities.write is 'anywhere'",
    ),
    (
        "network_maybe",
        with_manifest(lambda m: m["capabilities"].update(network="maybe")),
        "capabilities.network is 'maybe'",
    ),
    (
        "commands_nao_lista",
        with_manifest(lambda m: m["capabilities"].update(commands="git")),
        "capabilities.commands must be a list",
    ),
    ("kind_url", with_manifest(lambda m: m["inputs"]["pr"].update(kind="url")), "inputs.pr.kind is 'url'"),
    ("name_maiusculo", with_manifest(lambda m: m.update(name="Code_Review")), "name 'Code_Review' must match"),
    ("name_41", with_manifest(lambda m: m.update(name="a" * 41)), f"name {'a' * 41!r} must match"),
    (
        "name_diferente_do_plugin_json",
        with_manifest(lambda m: None, claude_name="outro"),
        "differs from .claude-plugin/plugin.json name 'outro'",
    ),
    ("plugin_json_ausente", no_claude_manifest, ".claude-plugin/plugin.json not found"),
    ("prompt_ausente", no_prompt_file, "prompt file 'prompt.md' not found"),
    (
        "placeholder_desconhecido",
        with_manifest(lambda m: None, prompt="Revise {pr} e {desconhecida}.\n"),
        "uses {desconhecida}",
    ),
    ("result_required_ausente", with_manifest(lambda m: m["result"].pop("required")), "result.required must be"),
]
assert len(INVALID) == 15


def symlink_in_skills(path: Path) -> None:
    write_plugin(path)
    (path / "skills" / "teste" / "fora").symlink_to("/etc/passwd")


def prompt_not_utf8(path: Path) -> None:
    write_plugin(path)
    (path / "prompt.md").write_bytes(b"Revise {pr} \xff\xfe\n")


def claude_manifest_not_json(path: Path) -> None:
    write_plugin(path)
    (path / ".claude-plugin" / "plugin.json").write_text("{nome: x", encoding="utf-8")


def prompt_outside_plugin(path: Path) -> None:
    manifest = plugin_manifest()
    manifest["prompt"] = "../fora.md"
    write_plugin(path, manifest)
    (path.parent / "fora.md").write_text("Revise {pr}.\n", encoding="utf-8")


# As outras recusas de `read_plugin` (door 1 e door 2), além das 15 do C19
MORE_INVALID: list[tuple[str, Callable[[Path], None], str]] = [
    ("link_simbolico", symlink_in_skills, "plugin has a symbolic link: skills/teste/fora"),
    ("prompt_nao_utf8", prompt_not_utf8, "is not UTF-8 text"),
    ("version_vazia", with_manifest(lambda m: m.update(version="")), "version must be a non-empty string"),
    ("plugin_json_invalido", claude_manifest_not_json, ".claude-plugin/plugin.json is not valid JSON"),
    (
        "entrada_com_nome_de_variavel",
        with_manifest(lambda m: m["inputs"].update(workspace={"kind": "text"})),
        "input name 'workspace' must match",
    ),
    (
        "required_nao_booleano",
        with_manifest(lambda m: m["inputs"]["pr"].update(required="sim")),
        "inputs.pr.required must be true or false",
    ),
    (
        "duas_entradas_repo",
        with_manifest(lambda m: m["inputs"].update(outro={"kind": "repo"})),
        "at most one input of kind 'repo'",
    ),
    ("capabilities_ausente", with_manifest(lambda m: m.pop("capabilities")), "capabilities is missing"),
    ("capabilities_nao_tabela", with_manifest(lambda m: m.update(capabilities="tudo")), "capabilities must be a table"),
    ("result_ausente", with_manifest(lambda m: m.pop("result")), "result is missing"),
    ("max_bytes_zero", with_manifest(lambda m: m["result"].update(max_bytes=0)), "result.max_bytes must be a positive"),
    ("prompt_fora_do_plugin", prompt_outside_plugin, "prompt file '../fora.md' not found"),
]


@pytest.mark.parametrize(("case", "build", "message"), MORE_INVALID, ids=[c[0] for c in MORE_INVALID])
def test_manifest_rules_more(tmp_path: Path, case: str, build: Callable[[Path], None], message: str) -> None:
    build(tmp_path / "p")
    with pytest.raises(plugin.PluginError) as raised:
        plugin.read_plugin(tmp_path / "p")
    assert raised.value.code == 2
    assert message in str(raised.value)


# C19 - AC 19
def test_manifest_rules_valid_plugin_normalized(tmp_path: Path) -> None:
    manifest = plugin.read_plugin(write_plugin(tmp_path / "p"))
    assert manifest["name"] == "teste"
    assert manifest["inputs"] == {"pr": {"kind": "repo", "required": True}}
    assert manifest["capabilities"] == {"write": "task-dir", "network": "on", "commands": ["git", "gh pr view"]}
    assert manifest["result"] == {"required": ["summary"], "max_bytes": 16384}


@pytest.mark.parametrize(("case", "build", "message"), INVALID, ids=[c[0] for c in INVALID])
def test_manifest_rules(tmp_path: Path, case: str, build: Callable[[Path], None], message: str) -> None:
    build(tmp_path / "p")
    with pytest.raises(plugin.PluginError) as raised:
        plugin.read_plugin(tmp_path / "p")
    assert raised.value.code == 2
    assert message in str(raised.value)


def test_manifest_rules_json_braces_in_prompt_are_not_placeholders(tmp_path: Path) -> None:
    prompt = 'Grave {result_file} com {"summary": "..."} para {pr}.\n'
    manifest = plugin.read_plugin(write_plugin(tmp_path / "p", prompt=prompt))
    assert manifest["prompt"] == "prompt.md"
