# Relatório do S0 - repositório `grokbot-kit` criado e constituído

Saída dos comandos de verificação dos AC 29, 30, 31 e 33 (AC 38), coletada em 2026-10-19T12:44:25Z contra
`rodrigo-pasini/grokbot-kit`, com `main` em `39be31b`. Nenhum token foi exibido nem gravado.

## AC 29

```sh
gh api repos/rodrigo-pasini/grokbot-kit/branches/main/protection --jq '{checks: [.required_status_checks.checks[].context], strict: .required_status_checks.strict, approvals: .required_pull_request_reviews.required_approving_review_count, admins: .enforce_admins.enabled, force: .allow_force_pushes.enabled, deletions: .allow_deletions.enabled, linear: .required_linear_history.enabled}'
```

```json
{"admins":true,"approvals":0,"checks":["lint","typecheck","test (3.11)","test (3.12)","test (3.13)"],"deletions":false,"force":false,"linear":true,"strict":true}
```

## AC 30

```sh
gh api repos/rodrigo-pasini/grokbot-kit/vulnerability-alerts
gh api repos/rodrigo-pasini/grokbot-kit/automated-security-fixes --jq .enabled
```

```text
vulnerability-alerts: exit 0 (HTTP 204)
automated-security-fixes .enabled: true
```

## AC 31

```sh
gh api repos/rodrigo-pasini/grokbot-kit/environments/pypi --jq '{name, rules: [.protection_rules[].type]}'
gh api repos/rodrigo-pasini/grokbot-kit/environments/pypi/deployment-branch-policies --jq '[.branch_policies[] | {name, type}]'
```

```json
{"name":"pypi","rules":["required_reviewers","branch_policy"]}
[{"name":"v*","type":"tag"}]
```

## AC 33

```sh
gh repo view rodrigo-pasini/grokbot-kit --json visibility,hasIssuesEnabled,hasWikiEnabled,hasProjectsEnabled,hasDiscussionsEnabled,squashMergeAllowed,mergeCommitAllowed,rebaseMergeAllowed,deleteBranchOnMerge,repositoryTopics,licenseInfo,defaultBranchRef
gh api repos/rodrigo-pasini/grokbot-kit --jq '{allow_auto_merge, allow_update_branch, secret_scanning: .security_and_analysis.secret_scanning.status, push_protection: .security_and_analysis.secret_scanning_push_protection.status}'
gh label list -R rodrigo-pasini/grokbot-kit --limit 100 --json name --jq '.[].name'
```

```json
{"defaultBranchRef":{"name":"main"},"deleteBranchOnMerge":true,"hasDiscussionsEnabled":false,"hasIssuesEnabled":true,"hasProjectsEnabled":false,"hasWikiEnabled":false,"licenseInfo":{"key":"mit","name":"MIT License","nickname":""},"mergeCommitAllowed":false,"rebaseMergeAllowed":false,"repositoryTopics":[{"name":"ai-agents"},{"name":"automation"},{"name":"claude-code"},{"name":"cli"},{"name":"codex"},{"name":"coding-agents"},{"name":"grokbot"},{"name":"opencode"},{"name":"python"},{"name":"webhooks"}],"squashMergeAllowed":true,"visibility":"PUBLIC"}
{"allow_auto_merge":true,"allow_update_branch":true,"push_protection":"enabled","secret_scanning":"enabled"}
```

```text
accessibility
bug
documentation
duplicate
enhancement
good first issue
help wanted
invalid
question
wontfix
area:cli
area:hooks
area:skill
area:webhook
cli:claude
cli:opencode
cli:codex
dependencies
security
needs-triage
python:uv
```
