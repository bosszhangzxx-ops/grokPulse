"""Plugins: leitura e validação (doors 1 e 2), armazenamento (door 3), `grokbot-kit plugin list|show|add|rm` (door 4)
e a matriz de capacidades por CLI (door 8)."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from grokbot_kit.launch import TOOLS
from grokbot_kit.payload import rfc3339

SCHEMA = "grokbot-kit.plugin/v0"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
INPUT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z0-9_-]+)\}")
VARIABLES = ("workspace", "result_file", "task_dir")
KINDS = ("repo", "text", "file")
CAPABILITY_VALUES = {"write": ("task-dir", "none"), "network": ("on", "off")}
FORBIDDEN = ("hooks", "commands", "agents", ".mcp.json", ".lsp.json")
MATRIX_COLUMNS = ("write", "network", "commands", "workspace_config", "skills")
STRENGTHS = ("os", "tool", "unsupported")
DEFAULT_MAX_BYTES = 16384
MANIFEST = "grokbot-kit.toml"
CLAUDE_MANIFEST = Path(".claude-plugin") / "plugin.json"
BUILTIN_DIR = Path(__file__).parent / "assets" / "plugins"
MATRIX_PATH = Path(__file__).parent / "assets" / "capabilities.json"
GIT_URL_RE = re.compile(r"^(https?|ssh|git|file)://|^[^/\s]+@[^/\s]+:")


class PluginError(Exception):
    """Recusa (`code` 2) ou falha de E/S ou do `git` (`code` 1), door 4."""

    def __init__(self, message: str, code: int = 2) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Plugin:
    path: Path
    manifest: dict[str, Any]
    source: str
    origin: str | None = None
    commit: str | None = None

    @property
    def name(self) -> str:
        return str(self.manifest["name"])


def plugins_dir() -> Path:
    return Path.home() / ".grokbot-kit" / "plugins"


def matrix() -> dict[str, dict[str, str]]:
    """A matriz da door 8: `{cli: {capacidade: os|tool|unsupported}}`; `GROKBOT_KIT_CAPABILITIES` troca o arquivo."""
    path = os.environ.get("GROKBOT_KIT_CAPABILITIES") or MATRIX_PATH
    data: dict[str, dict[str, str]] = json.loads(Path(path).read_text(encoding="utf-8"))
    cells = {tool: {column: data[tool][column] for column in MATRIX_COLUMNS} for tool in TOOLS}
    # uma CLI que não confina a escrita ou não ignora a config do workspace fica fora de toda tarefa de plugin (AC 7)
    for row in cells.values():
        if "unsupported" in (row["write"], row["workspace_config"]):
            row.update(dict.fromkeys(MATRIX_COLUMNS, "unsupported"))
    return cells


def is_git_url(origin: str) -> bool:
    return bool(GIT_URL_RE.match(origin))


def _check_layout(path: Path) -> None:
    try:
        entries = os.listdir(path)
    except OSError as e:
        raise PluginError(f"cannot read {path}: {e.strerror or e}", 1) from None
    found = [name for name in FORBIDDEN if name in entries]
    if found:
        raise PluginError(
            f"plugin has {', '.join(found)}; hooks, commands, agents, MCP and LSP are not allowed in a grokbot-kit plugin"
        )
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not (root == str(path) and d == ".git")]
        for name in dirs + files:
            if os.path.islink(os.path.join(root, name)):
                rel = os.path.relpath(os.path.join(root, name), path)
                raise PluginError(f"plugin has a symbolic link: {rel}")


def _read_text(path: Path, what: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PluginError(f"{what} not found") from None
    except UnicodeDecodeError:
        raise PluginError(f"{what} is not UTF-8 text") from None
    except OSError as e:
        raise PluginError(f"cannot read {path}: {e.strerror or e}", 1) from None


def _table(value: Any, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PluginError(f"{key} must be a table")
    return value


def _unknown(table: dict[str, Any], allowed: tuple[str, ...], key: str) -> None:
    extra = sorted(set(table) - set(allowed))
    if extra:
        raise PluginError(f"{key} has unknown key {extra[0]!r}; allowed: {', '.join(allowed)}")


def _manifest_rules(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    """O manifesto normalizado (padrões preenchidos), ou `PluginError` com a primeira regra violada (door 2)."""
    if "schema" not in data:
        raise PluginError(f"{MANIFEST}: schema is missing; expected {SCHEMA!r}")
    if data["schema"] != SCHEMA:
        raise PluginError(f"{MANIFEST}: schema is {data['schema']!r}; expected {SCHEMA!r}")
    _unknown(
        data,
        ("schema", "name", "version", "description", "prompt", "inputs", "capabilities", "result"),
        MANIFEST,
    )
    name = data.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise PluginError(f"{MANIFEST}: name {name!r} must match {NAME_RE.pattern}")
    for key in ("version", "description", "prompt"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise PluginError(f"{MANIFEST}: {key} must be a non-empty string")

    claude = path / CLAUDE_MANIFEST
    try:
        meta = json.loads(_read_text(claude, str(CLAUDE_MANIFEST)))
    except ValueError:
        raise PluginError(f"{CLAUDE_MANIFEST} is not valid JSON") from None
    if not isinstance(meta, dict) or meta.get("name") != name:
        found = meta.get("name") if isinstance(meta, dict) else None
        raise PluginError(f"{MANIFEST}: name {name!r} differs from {CLAUDE_MANIFEST} name {found!r}")

    inputs: dict[str, dict[str, Any]] = {}
    for key, spec in _table(data.get("inputs", {}), "inputs").items():
        if not INPUT_RE.match(key) or key in VARIABLES:
            raise PluginError(
                f"{MANIFEST}: input name {key!r} must match {INPUT_RE.pattern} and not be one of {VARIABLES}"
            )
        spec = _table(spec, f"inputs.{key}")
        _unknown(spec, ("kind", "required"), f"inputs.{key}")
        if spec.get("kind") not in KINDS:
            raise PluginError(f"{MANIFEST}: inputs.{key}.kind is {spec.get('kind')!r}; expected one of {KINDS}")
        required = spec.get("required", True)
        if not isinstance(required, bool):
            raise PluginError(f"{MANIFEST}: inputs.{key}.required must be true or false")
        inputs[key] = {"kind": spec["kind"], "required": required}
    if sum(spec["kind"] == "repo" for spec in inputs.values()) > 1:
        raise PluginError(f"{MANIFEST}: at most one input of kind 'repo' (the task has one workspace)")

    if "capabilities" not in data:
        raise PluginError(f"{MANIFEST}: capabilities is missing")
    caps = _table(data["capabilities"], "capabilities")
    _unknown(caps, ("write", "network", "commands"), "capabilities")
    for key, values in CAPABILITY_VALUES.items():
        if caps.get(key) not in values:
            raise PluginError(f"{MANIFEST}: capabilities.{key} is {caps.get(key)!r}; expected one of {values}")
    commands = caps.get("commands")
    if not isinstance(commands, list) or not all(isinstance(c, str) and c.strip() for c in commands):
        raise PluginError(f"{MANIFEST}: capabilities.commands must be a list of command prefixes (strings)")

    if "result" not in data:
        raise PluginError(f"{MANIFEST}: result is missing")
    result = _table(data["result"], "result")
    _unknown(result, ("required", "max_bytes"), "result")
    required_fields = result.get("required")
    if not isinstance(required_fields, list) or not all(isinstance(f, str) and f for f in required_fields):
        raise PluginError(f"{MANIFEST}: result.required must be a list of field names")
    max_bytes = result.get("max_bytes", DEFAULT_MAX_BYTES)
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise PluginError(f"{MANIFEST}: result.max_bytes must be a positive integer")

    prompt_path = (path / data["prompt"]).resolve()
    if not prompt_path.is_relative_to(path.resolve()) or not prompt_path.is_file():
        raise PluginError(f"{MANIFEST}: prompt file {data['prompt']!r} not found in the plugin")
    prompt = _read_text(prompt_path, f"prompt file {data['prompt']!r}")
    for found in PLACEHOLDER_RE.findall(prompt):
        if found not in inputs and found not in VARIABLES:
            raise PluginError(
                f"prompt {data['prompt']!r} uses {{{found}}}, which is neither an input nor one of "
                + ", ".join(f"{{{v}}}" for v in VARIABLES)
            )

    return {
        "name": name,
        "version": data["version"],
        "description": data["description"],
        "prompt": data["prompt"],
        "inputs": inputs,
        "capabilities": {"write": caps["write"], "network": caps["network"], "commands": list(commands)},
        "result": {"required": list(required_fields), "max_bytes": max_bytes},
    }


def read_plugin(path: Path) -> dict[str, Any]:
    """Valida layout (door 1) e manifesto (door 2) do diretório `path`."""
    _check_layout(path)
    text = _read_text(path / MANIFEST, MANIFEST)
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise PluginError(f"{MANIFEST} is not valid TOML: {e}") from None
    return _manifest_rules(path, data)


def builtins() -> list[Plugin]:
    return [Plugin(d, read_plugin(d), "builtin") for d in sorted(BUILTIN_DIR.iterdir()) if d.is_dir()]


def installed() -> tuple[list[Plugin], list[str]]:
    """Os plugins instalados legíveis e uma mensagem por diretório ilegível."""
    root = plugins_dir()
    plugins: list[Plugin] = []
    problems: list[str] = []
    if not root.is_dir():
        return plugins, problems
    for d in sorted(root.iterdir()):
        if d.name.startswith(".") or not d.is_dir():
            continue
        try:
            origin = json.loads((d / "origin.json").read_text(encoding="utf-8"))
            plugins.append(Plugin(d, read_plugin(d), origin["source"], origin["origin"], origin["commit"]))
        except PluginError as e:
            problems.append(f"plugin {d.name}: {e}")
        except (OSError, ValueError, KeyError, TypeError) as e:
            problems.append(f"plugin {d.name}: unreadable origin.json: {e}")
    return plugins, problems


def all_plugins() -> list[Plugin]:
    return sorted([*builtins(), *installed()[0]], key=lambda p: p.name)


def find(name: str) -> Plugin | None:
    return next((p for p in all_plugins() if p.name == name), None)


def item(plugin: Plugin) -> dict[str, Any]:
    """O objeto de um plugin em `plugin list --json` (door 4)."""
    m = plugin.manifest
    return {
        "name": m["name"],
        "version": m["version"],
        "description": m["description"],
        "source": plugin.source,
        "origin": plugin.origin,
        "commit": plugin.commit,
        "inputs": m["inputs"],
        "capabilities": m["capabilities"],
        "support": matrix(),
    }


def _describe(plugin: Plugin) -> list[str]:
    m = plugin.manifest
    caps = m["capabilities"]
    lines = [f"{m['name']} {m['version']} ({plugin.source}{f' {plugin.origin}' if plugin.origin else ''})"]
    lines.append(m["description"])
    inputs = [f"{k} ({v['kind']}, {'required' if v['required'] else 'optional'})" for k, v in m["inputs"].items()]
    lines.append(f"inputs: {', '.join(inputs) or 'none'}")
    lines.append(f"capabilities: write={caps['write']} network={caps['network']}")
    lines.append(f"  commands: {', '.join(caps['commands']) or 'none'}")
    lines.append("support (os = system sandbox, tool = tool permission):")
    for tool, cells in matrix().items():
        lines.append(f"  {tool}: " + " ".join(f"{k}={v}" for k, v in cells.items()))
    return lines


# ---------- tarefa de plugin ----------


def unenforceable(plugin: Plugin, tool: str) -> str | None:
    """`<capacidade>=<valor>` da primeira capacidade que o plugin pede e a matriz marca `unsupported` em `tool`."""
    cells = matrix()[tool]
    caps = plugin.manifest["capabilities"]
    needed = [("write", caps["write"]), ("commands", ",".join(caps["commands"]) or "none")]
    if caps["network"] == "off":
        needed.insert(1, ("network", "off"))
    needed.append(("workspace_config", "ignored"))
    if (plugin.path / "skills").is_dir():
        needed.append(("skills", "loaded"))
    return next((f"{cap}={value}" for cap, value in needed if cells[cap] == "unsupported"), None)


def environment(caps: dict[str, Any], values: dict[str, str]) -> str:
    """O bloco `## Ambiente desta tarefa` da door 9: o que as capacidades deixam o agente fazer, em pt-BR."""
    if caps["commands"]:
        prefixes = ", ".join(f"`{c}`" for c in caps["commands"])
        lines = [
            f"O shell só aceita comandos que começam por um destes prefixos: {prefixes}. Qualquer outro é negado.",
            "Um comando por chamada, sem `;`, `&&`, `||`, `|` nem `cd`.",
        ]
    else:
        lines = ["O shell não aceita nenhum comando."]
    lines.append("Leia, liste e procure arquivos com as ferramentas de leitura e busca da CLI, não com o shell.")
    if caps["write"] == "none":
        lines.append(f"Você só escreve o arquivo de resultado, {values['result_file']}.")
    else:
        lines.append(f"Você só escreve dentro de {values['task_dir']}.")
    if caps["network"] == "off":
        lines.append("Sem acesso à rede.")
    lines.append("Uma permissão negada não encerra a tarefa: siga com as ferramentas e os comandos liberados.")
    return "## Ambiente desta tarefa\n\n" + "".join(f"- {line}\n" for line in lines)


def render_prompt(plugin: Plugin, values: dict[str, str]) -> str:
    """O prompt do plugin com `{<entrada>}` e as variáveis da door 2 substituídas (entrada opcional ausente vira ``),
    seguido do bloco de ambiente da door 9."""
    text = (plugin.path / plugin.manifest["prompt"]).read_text(encoding="utf-8")
    text = PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), ""), text)
    return text.rstrip("\n") + "\n\n" + environment(plugin.manifest["capabilities"], values)


def read_result(path: Path, spec: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """`(objeto, "")` com o resultado válido (door 6), ou `(None, motivo)`."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None, f"the agent did not write {path.name}"
    except OSError as e:
        return None, f"cannot read {path}: {e.strerror or e}"
    if len(data) > spec["max_bytes"]:
        return None, f"{path.name} has {len(data)} bytes, more than result.max_bytes ({spec['max_bytes']})"
    try:
        obj = json.loads(data)
    except ValueError:
        return None, f"{path.name} is not valid JSON"
    if not isinstance(obj, dict):
        return None, f"{path.name} is not a JSON object"
    missing = [f for f in spec["required"] if f not in obj]
    if missing:
        return None, f"{path.name} lacks required field(s): {', '.join(missing)}"
    return obj, ""


# ---------- origens ----------


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            check=False,
        )
    except OSError as e:
        raise PluginError(f"cannot run git: {e.strerror or e}", 1) from None


def _clone(url: str, ref: str | None, into: Path) -> str:
    """Clona `url` em `into`, faz checkout de `ref` (padrão: a branch padrão) e devolve o commit completo."""
    proc = _git("clone", "--quiet", url, str(into))
    if proc.returncode != 0:
        raise PluginError(f"git clone {url} failed: {proc.stderr.strip()}", 1)
    commit = None
    for candidate in [ref, f"origin/{ref}"] if ref else ["HEAD"]:
        found = _git("rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}", cwd=into)
        if found.returncode == 0:
            commit = found.stdout.strip()
            break
    if commit is None:
        raise PluginError(f"ref {ref!r} not found in {url}", 1)
    checkout = _git("checkout", "--quiet", "--detach", commit, cwd=into)
    if checkout.returncode != 0:
        raise PluginError(f"git checkout {commit} failed: {checkout.stderr.strip()}", 1)
    return commit


def _with_origin(origin: str, ref: str | None, action: Any) -> Any:
    """Lê a origem (diretório ou URL git) e chama `action(plugin)` com ela legível; o clone some depois."""
    if is_git_url(origin):
        with tempfile.TemporaryDirectory(prefix="grokbot-kit-plugin-") as tmp:
            into = Path(tmp) / "clone"
            commit = _clone(origin, ref, into)
            return action(Plugin(into, read_plugin(into), "git", origin, commit), ref)
    if ref is not None:
        raise PluginError("--ref only applies to a git URL")
    path = Path(origin).expanduser().absolute()
    if not path.is_dir():
        raise PluginError(f"cannot read {path}: not a directory", 1)
    return action(Plugin(path, read_plugin(path), "dir", str(path), None), None)


# ---------- tarefas rodando ----------


def running_tasks(name: str, now: datetime | None = None) -> list[str]:
    """`task_id` das tarefas do plugin `name` ainda rodando (AC 25), pelo predicado de `update.task_running`."""
    from grokbot_kit import config, update

    now = now or datetime.now(UTC)
    root = config.tasks_dir()
    if not root.is_dir():
        return []
    found = []
    for d in sorted(root.iterdir()):
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            if not isinstance(meta, dict) or not isinstance(meta.get("plugin"), dict):
                continue
            if meta["plugin"].get("name") != name:
                continue
        except (OSError, ValueError):
            continue
        if update.task_running(d, now):
            found.append(d.name)
    return found


# ---------- comandos ----------


def _fail(action: str, e: PluginError) -> int:
    print(f"grokbot-kit plugin {action}: {e}", file=sys.stderr)
    return e.code


def list_cmd(as_json: bool) -> int:
    plugins = all_plugins()
    if as_json:
        print(json.dumps({"plugins": [item(p) for p in plugins]}, ensure_ascii=False, indent=2))
    else:
        for p in plugins:
            m = p.manifest
            print(f"{m['name']} {m['version']} {p.source} - {m['description']}")
    return 0


def _print(plugin: Plugin, as_json: bool) -> None:
    if as_json:
        print(json.dumps(item(plugin), ensure_ascii=False, indent=2))
    else:
        print("\n".join(_describe(plugin)))


def show(target: str, as_json: bool) -> int:
    try:
        if NAME_RE.match(target) and not is_git_url(target):
            plugin = find(target)
            if plugin is None:
                raise PluginError(f"no plugin named {target}; run: grokbot-kit plugin list")
            _print(plugin, as_json)
        else:
            _with_origin(target, None, lambda p, ref: _print(p, as_json))
    except PluginError as e:
        return _fail("show", e)
    return 0


def _confirm(plugin: Plugin) -> bool:
    if not sys.stdin.isatty():
        raise PluginError("confirmation needs a terminal; review the capabilities above and rerun with --yes")
    print(f"install {plugin.name} {plugin.manifest['version']}? [y/N] ", end="", file=sys.stderr, flush=True)
    return sys.stdin.readline().strip().lower() in ("y", "yes")


def _install(plugin: Plugin, ref: str | None, *, replace: bool, yes: bool) -> int:
    name = plugin.name
    if any(b.name == name for b in builtins()):
        raise PluginError(f"{name} is a builtin plugin and cannot be replaced")
    root = plugins_dir()
    dest = root / name
    if dest.exists() and not replace:
        raise PluginError(f"{name} is already installed; use --replace to install over it")
    if dest.exists():
        running = running_tasks(name)
        if running:
            raise PluginError(f"tasks of plugin {name} still running: {', '.join(running)}")
    print("\n".join(_describe(plugin)))
    if not yes and not _confirm(plugin):
        raise PluginError("not confirmed; nothing installed")
    origin = {
        "source": plugin.source,
        "origin": plugin.origin,
        "ref": ref,
        "commit": plugin.commit,
        "installed_at": rfc3339(datetime.now(UTC)),
    }
    tmp = root / f".{name}.{os.getpid()}.tmp"
    old = root / f".{name}.{os.getpid()}.old"
    try:
        root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(plugin.path, tmp, ignore=shutil.ignore_patterns(".git"))
        (tmp / "origin.json").write_text(json.dumps(origin, indent=2) + "\n", encoding="utf-8")
        if dest.exists():
            os.rename(dest, old)
        os.rename(tmp, dest)
    except OSError as e:
        shutil.rmtree(tmp, ignore_errors=True)
        if old.exists() and not dest.exists():
            os.rename(old, dest)
        raise PluginError(f"cannot write {dest}: {e.strerror or e}", 1) from None
    shutil.rmtree(old, ignore_errors=True)
    print(f"installed {name} {plugin.manifest['version']} ({plugin.commit or plugin.origin})")
    return 0


def add(origin: str, ref: str | None, replace: bool, yes: bool) -> int:
    try:
        code: int = _with_origin(origin, ref, lambda p, r: _install(p, r, replace=replace, yes=yes))
    except PluginError as e:
        return _fail("add", e)
    return code


def rm(name: str) -> int:
    try:
        if any(b.name == name for b in builtins()):
            raise PluginError(f"{name} is a builtin plugin and cannot be removed")
        dest = plugins_dir() / name
        if not NAME_RE.match(name) or not dest.is_dir():
            raise PluginError(f"no plugin named {name}; run: grokbot-kit plugin list")
        running = running_tasks(name)
        if running:
            raise PluginError(f"tasks of plugin {name} still running: {', '.join(running)}")
        try:
            shutil.rmtree(dest)
        except OSError as e:
            raise PluginError(f"cannot remove {dest}: {e.strerror or e}", 1) from None
    except PluginError as e:
        return _fail("rm", e)
    print(f"removed {name}")
    return 0
