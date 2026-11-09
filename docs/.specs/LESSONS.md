# LESSONS - auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Plan/Checks)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation - do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 - Write repository-state proofs against refs and facts that stay true after the step, never against a local branch ref or a one-time precondition
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `repo-setup` · harmful: 0
- features: agent-run-notify
- evidence: C30 checks.md:109; C25 checks.md:94 (repo-setup)
- last seen: 2026-10-21T00:07:45Z

### L-002 - Give every usage refusal an entry point has its own boundary test, not only the refusals the acceptance criteria name
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `cli-guards` · harmful: 0
- features: agent-run-notify
- evidence: src/grokbot_kit/run.py:49,54,57,63 (cli-guards)
- last seen: 2026-10-21T00:07:45Z

### L-003 - When a check names an open flag such as O_EXCL, assert the flag or a behaviour only that flag produces
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `locking` · harmful: 0
- features: agent-run-notify
- evidence: C86 tests/test_redeliver.py:133 (locking)
- last seen: 2026-10-21T00:07:45Z

### L-004 - When a workflow step depends on files an earlier step produced, assert the step order, not only that each step exists
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `ci-workflows` · harmful: 0
- features: agent-run-notify
- evidence: F4 C149 .github/workflows/release.yml:45-52 tests/test_workflows.py:128-135 (ci-workflows)
- last seen: 2026-10-21T18:42:44Z

### L-005 - Give every input a parser maps to the same fallback its own test, including a file that exists but lacks the expected line
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `doctor` · harmful: 0
- features: agent-run-notify
- evidence: F9 C150 door 24 plan.md:176 src/grokbot_kit/doctor.py:49-56 (doctor)
- last seen: 2026-10-21T18:42:44Z

### L-006 - When a new case reaches code that picks between fixed problem messages, the check names which message that case gets and its proof asserts that text
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `doctor` · harmful: 0
- features: agent-run-notify
- evidence: P1 C151 tests/test_doctor.py:251 plan.md:176 src/grokbot_kit/doctor.py:108-114 (doctor)
- last seen: 2026-10-21T19:01:35Z

### L-007 - Quando um valor pode vir de duas fontes (PyPI e o --version do executável novo), o teste deve fazer as duas responderem valores diferentes, senão a fonte errada passa
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `update` · harmful: 0
- features: kit-update
- evidence: F3 src/grokbot_kit/update.py:286 (C22) (update)
- last seen: 2026-10-21T20:03:47Z

### L-008 - Ao contar os caminhos de saída de um ponto de entrada, conte também o except OSError de um subprocesso (executável ausente no PATH) e dê a ele uma prova
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `update` · harmful: 0
- features: kit-update
- evidence: src/grokbot_kit/update.py:280-281 (Test policy: ponto de entrada) (update)
- last seen: 2026-10-21T20:03:47Z

### L-009 - Uma guarda de comparação de versão precisa de prova nos dois lados do limite (igual e menor), não só na igualdade
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `update` · harmful: 0
- features: kit-update
- evidence: F11 src/grokbot_kit/update.py:288 (C39) (update)
- last seen: 2026-10-21T21:03:18Z

### L-010 - Quando um AC diz que um caminho de erro não muda o estado, afirme cada campo nomeado com uma precondição não nula
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `update` · harmful: 0
- features: kit-update
- evidence: F14 src/grokbot_kit/update.py:290 (C39, AC 37) (update)
- last seen: 2026-10-21T21:03:18Z

### L-011 - Prova de prazo/timeout afirma um limite perto do prazo mais a folga (ex.: < 6 s para 4 s), nunca um teto folgado que também passa um prazo por tentativa
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `run` · harmful: 0
- features: model-setup-docs
- evidence: tests/test_run_fallback.py:203 (run)
- last seen: 2026-10-29T00:30:23Z

### L-012 - Quando um check enumera N validadores ou regras rodados por um dispatcher, prove cada um com um caso que só ele reprova; um caso verde com todos presentes não mata a remoção de um.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tools` · harmful: 0
- features: sdlc-gates
- evidence: F1 tools/sdlc.py:36 (tools)
- last seen: 2026-10-29T13:34:44Z

### L-013 - Quando a AC enumera uma família de arquivos (README, CONTRIBUTING, docs/<x>.md), o check nomeia cada membro, não só o primeiro exemplo.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `checks` · harmful: 0
- features: sdlc-gates
- evidence: C52 / AC 39 (checks)
- last seen: 2026-10-29T13:34:44Z

### L-014 - Quando a AC enumera a lista de palavras que um classificador reconhece, o check põe um caso por palavra; casos por forma de invocação não matam a remoção de uma palavra.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `hooks` · harmful: 0
- features: sdlc-gates
- evidence: M12 .claude/hooks/gate-humano.sh:97 (hooks)
- last seen: 2026-10-29T16:41:04Z

### L-015 - Quando o gate lê uma opção de CLI que leva valor, o check põe um caso com --opção=valor e outro com --opção valor; tratar só uma grafia deixa a outra passar.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `hooks` · harmful: 0
- features: sdlc-gates
- evidence: AC 47 / C61 .claude/hooks/gate-humano.sh:85 (hooks)
- last seen: 2026-10-29T17:24:29Z

### L-016 - Quando dois mecanismos tratam o mesmo caractere, o check põe um caso que só cada mecanismo decide; um caso que os dois resolvem não mata a remoção de um deles.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `hooks` · harmful: 0
- features: sdlc-gates
- evidence: N7 .claude/hooks/gate-humano.sh:125 (hooks)
- last seen: 2026-10-29T17:24:29Z

### L-017 - Cada exceção de um parser de comando (o trecho que ele deixa de cortar ou ler) tem um check que a derruba, ou sai; sem check, ela esconde o comando que fica dentro.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `hooks` · harmful: 0
- features: sdlc-gates
- evidence: N6 .claude/hooks/gate-humano.sh:128 (hooks)
- last seen: 2026-10-29T17:24:29Z

### L-018 - Quando um fix faz o corte do comando separar num ponto novo, o check prova também o comando de fora com palavras depois do corte (git -C $(pwd) push origin main); o resto perde o nome do comando e sai sem decisão.
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `hooks` · harmful: 0
- features: sdlc-gates
- evidence: R5 regressão .claude/hooks/gate-humano.sh:146 (hooks)
- last seen: 2026-10-29T17:53:22Z

### L-019 - Quando o gate decide o conteúdo de substituições aninhadas, o check põe o comando perigoso em cada nível do aninhamento, também no de fora e dentro de crase; extrair só o nível mais de dentro deixa o de fora sem decisão.
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `hooks` · harmful: 0
- features: sdlc-gates
- evidence: R6 regressão .claude/hooks/gate-humano.sh:163 (hooks)
- last seen: 2026-10-29T18:12:25Z

### L-020 - Quando o gate imita uma regra do shell, o check põe um caso do lado em que o shell não aplica a regra (aspas simples, heredoc com 'EOF', caractere escapado); sem ele, o gate decide texto literal e nega comando inofensivo.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `hooks` · harmful: 0
- features: sdlc-gates
- evidence: AC 23 / AC 53 .claude/hooks/gate-humano.sh:163 (hooks)
- last seen: 2026-10-29T18:12:25Z

### L-021 - Quando o gate descarta um trecho como dado até um marcador de fim (corpo de heredoc), o check põe um caso em que o gate não acha o marcador que o shell acha (delimitador com aspas no meio, com '-', ou '<<' aritmético) seguido de um comando perigoso; sem ele, o gate descarta o comando junto.
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `hooks` · harmful: 0
- features: sdlc-gates
- evidence: R7 regressão .claude/hooks/gate-humano.sh:193-225 (hooks)
- last seen: 2026-10-29T19:43:50Z

### L-022 - Quando o gate trata texto entre aspas ou de heredoc como dado, o check põe um caso com o texto em várias linhas e uma linha que começa com o comando perigoso; ler o resultado linha a linha corta o texto de novo.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `hooks` · harmful: 0
- features: sdlc-gates
- evidence: C70/C71 AC 55-56 .claude/hooks/gate-humano.sh:190 (hooks)
- last seen: 2026-10-29T19:43:50Z

### L-023 - Um check de hook pre-push do pre-commit prova um push com dois refs (git push origin feat/x main): o pre-commit só passa ao hook o primeiro ref com commits.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `hooks` · harmful: 0
- features: sdlc-gates
- evidence: N1 AC 21 / C28 .pre-commit-config.yaml:48 (hooks)
- last seen: 2026-10-30T17:17:02Z

### L-024 - Com um allow largo como Bash(git push *), o check das regras ask prova as formas de refspec (HEAD:refs/tags/v1, :v1, --mirror): o ask casa texto, e o allow pega o que o ask não escreveu.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `claude-permissions` · harmful: 0
- features: sdlc-gates
- evidence: N2 AC 20 / C27 .claude/settings.json:27 (claude-permissions)
- last seen: 2026-10-30T17:17:02Z

### L-025 - Uma regra ask de flag escrita Bash(cmd * --flag *) não casa a flag como primeiro argumento (git push --follow-tags): cada flag ganha o par Bash(cmd --flag *), e o check prova cada membro com um comando concreto, não só pela igualdade da lista.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `claude-permissions` · harmful: 0
- features: sdlc-gates
- evidence: N5 plan.md:73 / C27 .claude/settings.json:35 (claude-permissions)
- last seen: 2026-10-30T17:25:45Z

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
