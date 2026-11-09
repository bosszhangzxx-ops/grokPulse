# Provas no box, 0.4.1

Saídas que o bot devolveu das provas `-m integration` no box. O host de dev não alcança o box, então estes arquivos
são a evidência que o Verifier lê. Copiados sem edição do que o bot mandou.

- `0.4.1-doctor.txt` (27-28/10/2026): `grokbot-kit` 0.4.1 instalado por `update apply`; `opencode` 1.19.3.
  O `claude` rodou com `sonnet` (`launch claude model=sonnet` no `kit.log` do C50); a versão dele não veio nos logs.
- `0.4.1-pytest.log` (28/10/2026): `tests/integration/test_plugin_caps.py` e `tests/integration/test_builtin_plugins.py`
  a partir da tag `v0.4.1`, com `GROKBOT_KIT_IT_OPENCODE_MODEL=opencode/glm-5.3-flash-free`: 18 passed, 10 skipped,
  1 failed. A falha é o `git commit` do próprio teste do C50 (`test_builtin_plugins.py:121`), sem identidade git no
  box (`Author identity unknown`, exit 128), depois de o primeiro review já ter sido postado
  (https://github.com/rodrigo-pasini/grokbot-kit-fixtures/pull/1#pullrequestreview-5680620067).
- `0.4.1-c50.log` (28/10/2026): só o C50 de novo, com `GIT_AUTHOR_*` e `GIT_COMMITTER_*` no ambiente: 1 passed.
  Reviews postados:
  https://github.com/rodrigo-pasini/grokbot-kit-fixtures/pull/1#pullrequestreview-5683162673 (primeiro run) e
  https://github.com/rodrigo-pasini/grokbot-kit-fixtures/pull/1#pullrequestreview-5683173344 (segundo run, depois do
  commit novo).
