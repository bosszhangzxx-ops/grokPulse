"""Prova do C29: configurações do repositório no GitHub batem com a door 11 (AC 25, AC 33).

Roda só com `-m integration`, com o `gh` autenticado.
"""

import json
import subprocess
from typing import Any

import pytest

REPO = "rodrigo-pasini/grokbot-kit"
TOPICS = [
    "grokbot",
    "ai-agents",
    "coding-agents",
    "cli",
    "python",
    "webhooks",
    "opencode",
    "claude-code",
    "codex",
    "automation",
]

pytestmark = pytest.mark.integration


def gh_json(*args: str) -> Any:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_repo_settings_match_door_11() -> None:
    view = gh_json(
        "repo",
        "view",
        REPO,
        "--json",
        "visibility,hasIssuesEnabled,hasWikiEnabled,hasProjectsEnabled,hasDiscussionsEnabled,"
        "squashMergeAllowed,mergeCommitAllowed,rebaseMergeAllowed,deleteBranchOnMerge,"
        "repositoryTopics,licenseInfo,defaultBranchRef",
    )
    assert view["visibility"] == "PUBLIC"
    assert view["hasIssuesEnabled"] is True
    assert view["hasWikiEnabled"] is False
    assert view["hasProjectsEnabled"] is False
    assert view["hasDiscussionsEnabled"] is False
    assert view["squashMergeAllowed"] is True
    assert view["mergeCommitAllowed"] is False
    assert view["rebaseMergeAllowed"] is False
    assert view["deleteBranchOnMerge"] is True
    assert sorted(t["name"] for t in view["repositoryTopics"] or []) == sorted(TOPICS)
    assert view["licenseInfo"]["key"] == "mit"
    assert view["defaultBranchRef"]["name"] == "main"

    api = gh_json("api", f"repos/{REPO}")
    assert api["allow_auto_merge"] is True
    assert api["allow_update_branch"] is True
    assert api["squash_merge_commit_title"] == "PR_TITLE"
    assert api["squash_merge_commit_message"] == "PR_BODY"
    security = api["security_and_analysis"]
    assert security["secret_scanning"]["status"] == "enabled"
    assert security["secret_scanning_push_protection"]["status"] == "enabled"
