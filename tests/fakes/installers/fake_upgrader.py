#!/usr/bin/env python3
"""`uv` e `pipx` falsos (pelo nome do link) do `grokbot-kit update apply` (door 5).

Grava a chamada em `FAKE_CALLS` (`tool` = `upgrader:<uv|pipx>`, argv), escreve `FAKE_UPGRADE_STDERR_LINES` linhas
`installer line NN` em stderr, dorme `FAKE_UPGRADE_SLEEP` segundos e sai com `FAKE_UPGRADE_EXIT` (padrão `0`). Saindo
com `0`, troca o executável `FAKE_KIT_EXE` por um `grokbot-kit` novo: `--version` imprime `grokbot-kit <FAKE_NEW_VERSION>`
(padrão `9.0.0`); o resto
grava a chamada em `FAKE_CALLS` (`tool` = `new-kit`) e sai com `FAKE_NEW_KIT_EXIT` (padrão `0`).
"""

import json
import os
import sys
import time

NEW_KIT = """#!{python}
import json, os, sys
args = sys.argv[1:]
if args == ["--version"]:
    print("grokbot-kit {version}")
    sys.exit(0)
calls = os.environ.get("FAKE_CALLS")
if calls:
    with open(calls, "a", encoding="utf-8") as f:
        f.write(json.dumps({{"tool": "new-kit", "argv": args}}) + "\\n")
sys.exit(int(os.environ.get("FAKE_NEW_KIT_EXIT", "0")))
"""

name, args = os.path.basename(sys.argv[0]), sys.argv[1:]
calls = os.environ.get("FAKE_CALLS")
if calls:
    with open(calls, "a", encoding="utf-8") as f:
        f.write(json.dumps({"tool": f"upgrader:{name}", "argv": args}) + "\n")
for i in range(1, int(os.environ.get("FAKE_UPGRADE_STDERR_LINES", "0")) + 1):
    print(f"installer line {i:02d}", file=sys.stderr)
time.sleep(float(os.environ.get("FAKE_UPGRADE_SLEEP", "0")))
code = int(os.environ.get("FAKE_UPGRADE_EXIT", "0"))
if code == 0 and os.environ.get("FAKE_KIT_EXE"):
    exe = os.environ["FAKE_KIT_EXE"]
    tmp = exe + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(NEW_KIT.format(python=sys.executable, version=os.environ.get("FAKE_NEW_VERSION", "9.0.0")))
    os.chmod(tmp, 0o755)
    os.replace(tmp, exe)
    print(f"Upgraded grokbot-kit to 9.0.0 ({name} fake)")
sys.exit(code)
