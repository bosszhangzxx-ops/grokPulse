"""Provas do S0 sobre os workflows e o Dependabot (checks C13-C15, C19, C38)."""

import itertools
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def load(rel: str) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
    # PyYAML lê a chave `on` como o booleano True.
    if True in data:
        data["on"] = data.pop(True)
    return data


def runs(job: dict[str, Any]) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


def job_names(job_id: str, job: dict[str, Any]) -> list[str]:
    name = job.get("name", job_id)
    matrix = job.get("strategy", {}).get("matrix", {})
    if not matrix:
        return [name]
    keys = [key for key in matrix if key not in ("include", "exclude")]
    names = []
    for combo in itertools.product(*(matrix[key] for key in keys)):
        expanded = name
        for key, value in zip(keys, combo, strict=True):
            expanded = expanded.replace(f"${{{{ matrix.{key} }}}}", str(value))
        names.append(expanded)
    return names


# C13 - AC 10
def test_ci_jobs_and_triggers() -> None:
    ci = load(".github/workflows/ci.yml")
    assert ci["on"]["push"]["branches"] == ["main"]
    assert ci["on"]["pull_request"]["branches"] == ["main"]
    jobs = ci["jobs"]
    names = {name: job_id for job_id, job in jobs.items() for name in job_names(job_id, job)}
    # sdlc-gates (door 4): o job `process` entra no `ci.yml`
    assert sorted(names) == sorted(["lint", "typecheck", "test (3.11)", "test (3.12)", "test (3.13)", "process"])
    for job in jobs.values():
        assert job["runs-on"] == "ubuntu-latest"
        assert "uv sync --locked" in runs(job)
    lint = runs(jobs[names["lint"]])
    assert "uv run ruff check" in lint
    assert "uv run ruff format --check" in lint
    assert "uv run mypy" in runs(jobs[names["typecheck"]])
    test_job = jobs[names["test (3.11)"]]
    assert "uv run pytest" in runs(test_job)
    assert [str(v) for v in test_job["strategy"]["matrix"]["python"]] == ["3.11", "3.12", "3.13"]


# C14 - AC 11
def test_release_jobs_and_permissions() -> None:
    release = load(".github/workflows/release.yml")
    assert release["on"] == {"push": {"tags": ["v*"]}}
    build = release["jobs"]["build"]
    publish = release["jobs"]["publish"]
    assert "id-token" not in build.get("permissions", {})
    assert "id-token" not in release.get("permissions", {})
    assert "uv build" in runs(build)
    uploads = [s for s in build["steps"] if s.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(uploads) == 1 and uploads[0]["with"]["path"].rstrip("/") == "dist"
    assert publish["needs"] in ("build", ["build"])
    environment = publish["environment"]
    assert environment == "pypi" or environment.get("name") == "pypi"
    assert publish["permissions"] == {"id-token": "write", "contents": "write"}
    uses = [s.get("uses", "") for s in publish["steps"]]
    assert "pypa/gh-action-pypi-publish@release/v1" in uses
    pypi_step = next(s for s in publish["steps"] if s.get("uses") == "pypa/gh-action-pypi-publish@release/v1")
    assert "password" not in pypi_step.get("with", {})
    attach = [s for s in publish["steps"] if "gh release create" in s.get("run", "")]
    assert len(attach) == 1 and "dist/*" in attach[0]["run"]


# C15 - AC 12
def version_check_step() -> dict[str, Any]:
    build = load(".github/workflows/release.yml")["jobs"]["build"]
    steps = [s for s in build["steps"] if "version" in s.get("name", "").lower() and "run" in s]
    assert len(steps) == 1, "o job build precisa de exatamente um passo de checagem de versão"
    names = [s.get("name") for s in build["steps"]]
    build_step = next(s for s in build["steps"] if "uv build" in s.get("run", ""))
    assert names.index(steps[0]["name"]) < names.index(build_step.get("name")), "checagem depois do build"
    return steps[0]


@pytest.mark.parametrize(("tag", "version", "ok"), [("v0.2.0", "0.1.0", False), ("v0.1.0", "0.1.0", True)])
def test_release_version_mismatch_fails(tmp_path: Path, tag: str, version: str, ok: bool) -> None:
    step = version_check_step()
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "grokbot-kit"\nversion = "{version}"\n')
    result = subprocess.run(
        ["bash", "-e", "-c", step["run"]],
        cwd=tmp_path,
        check=False,
        env={"PATH": "/usr/bin:/bin", "GITHUB_REF_NAME": tag, "GITHUB_REF": f"refs/tags/{tag}"},
        capture_output=True,
    )
    assert (result.returncode == 0) is ok


# C19 - AC 17
def test_dependabot_ecosystems() -> None:
    dependabot = yaml.safe_load((ROOT / ".github/dependabot.yml").read_text(encoding="utf-8"))
    assert dependabot["version"] == 2
    updates = {u["package-ecosystem"]: u for u in dependabot["updates"]}
    assert set(updates) == {"uv", "github-actions"}
    for update in updates.values():
        assert update["schedule"]["interval"] == "weekly"
        assert update["directory"] == "/"


# C149 - AC 125, door 23
SKILL_PATH = "skills/grokbot-kit/SKILL.md"
SKILL_LATEST = "https://github.com/rodrigo-pasini/grokbot-kit/releases/latest/download/SKILL.md"


def test_release_attaches_skill() -> None:
    jobs = load(".github/workflows/release.yml")["jobs"]
    publish = jobs["publish"]
    checkouts = [s for s in publish["steps"] if s.get("uses", "").startswith("actions/checkout@")]
    assert len(checkouts) == 1
    assert SKILL_PATH in str(checkouts[0].get("with", {}).get("sparse-checkout", ""))
    # o checkout limpa o workspace: depois do download, apagaria o `dist/` (AD-035)
    download = next(s for s in publish["steps"] if s.get("uses", "").startswith("actions/download-artifact@"))
    assert publish["steps"].index(checkouts[0]) < publish["steps"].index(download)
    attach = next(s for s in publish["steps"] if "gh release create" in s.get("run", ""))
    assert "dist/*" in attach["run"] and SKILL_PATH in attach["run"]
    assert "SKILL" not in runs(jobs["build"])
    pypi_step = next(s for s in publish["steps"] if s.get("uses") == "pypa/gh-action-pypi-publish@release/v1")
    assert "packages-dir" not in pypi_step.get("with", {})


@pytest.mark.parametrize("readme", ["README.md", "docs/pt-BR/README.md"])
def test_release_attaches_skill_readme_latest(readme: str) -> None:
    text = (ROOT / readme).read_text(encoding="utf-8")
    assert SKILL_LATEST in text
    assert "/v0." not in text
    assert "SKILL.md" not in text.replace(SKILL_LATEST, "").replace("workflows/grokbot-kit/SKILL.md", "")


# C38 - AC 35
def test_release_reads_no_secret() -> None:
    text = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "secrets." not in text
    assert "secrets[" not in text


# sdlc-gates C12 - AC 10, door 4
def process_job() -> dict[str, Any]:
    job: dict[str, Any] = load(".github/workflows/ci.yml")["jobs"]["process"]
    return job


def test_process_job() -> None:
    ci = load(".github/workflows/ci.yml")
    assert sorted(ci["on"]["pull_request"]["types"]) == sorted(["opened", "edited", "synchronize", "reopened"])
    job = process_job()
    assert job["name"] == "process"
    checkout = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["fetch-depth"] == 0
    step = next(s for s in job["steps"] if "tools/sdlc.py pr" in s.get("run", ""))
    base = re.search(r"--base\s+\"?\$\{?(\w+)", step["run"])
    assert base is not None, step["run"]
    assert step["env"][base.group(1)] == "${{ github.event.pull_request.base.sha }}"


# sdlc-gates C13 - AC 10
def test_process_job_no_expression_in_run() -> None:
    job = process_job()
    for step in job["steps"]:
        run = step.get("run", "")
        for expression in ("github.event.pull_request.title", "github.event.pull_request.body", "github.head_ref"):
            assert expression not in run, (expression, run)
    env = {k: v for step in job["steps"] for k, v in step.get("env", {}).items()}
    values = " ".join(env.values())
    for expression in ("github.event.pull_request.title", "github.event.pull_request.body", "github.head_ref"):
        assert expression in values, expression
