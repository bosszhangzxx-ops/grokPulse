#!/usr/bin/env python3
# Roda os casos do gate. Não altera findings de exemplo.
# Uso: test-conferir-achados.py
"""Mostra que severidade que não é string vira erro, e que o ledger fecha."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = Path(__file__).resolve().parent / "conferir-achados.py"
MODELO = ROOT / "references" / "modelo-do-resumo.md"


def carregar():
    spec = importlib.util.spec_from_file_location("conferir_achados", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def exemplos() -> list[dict]:
    texto = MODELO.read_text(encoding="utf-8")
    return [json.loads(bloco) for bloco in re.findall(r"```json\n(.*?)```", texto, re.S)]


def main() -> int:
    mod = carregar()
    falhas: list[str] = []

    def ok(nome: str, cond: bool, detalhe: str = "") -> None:
        if cond:
            print(f"ok  {nome}")
        else:
            falhas.append(nome)
            print(f"FAIL {nome} {detalhe}")

    docs = exemplos()
    ok("dois exemplos no modelo", len(docs) == 2)
    for i, data in enumerate(docs, 1):
        try:
            erros = mod.validar(data)
        except Exception as exc:  # noqa: BLE001 — o teste é justamente não estourar
            erros = [f"exceção {type(exc).__name__}: {exc}"]
        ok(f"exemplo {i} passa", erros == [], "; ".join(erros))

    rodada1 = json.loads(json.dumps(docs[0]))
    rodada1["achados"][0]["severidade"] = ["deve-corrigir"]
    try:
        erros = mod.validar(rodada1)
        ok(
            "severidade lista não estoura",
            any("severidade" in e for e in erros) and not any(e.startswith("exceção") for e in erros),
            "; ".join(erros),
        )
    except TypeError as exc:
        ok("severidade lista não estoura", False, str(exc))

    rodada2 = json.loads(json.dumps(docs[1]))
    rodada2["resolucao"][0]["status"] = {"status": "resolvido"}
    try:
        erros = mod.validar(rodada2)
        ok("status objeto não estoura", any("status" in e for e in erros), "; ".join(erros))
    except TypeError as exc:
        ok("status objeto não estoura", False, str(exc))

    rodada1 = json.loads(json.dumps(docs[0]))
    rodada1["achados"][0]["evidencia"] = [{"tipo": ["interna"], "ref": "src/frete.ts:18"}]
    try:
        erros = mod.validar(rodada1)
        ok("tipo lista não estoura", any("tipo" in e for e in erros), "; ".join(erros))
    except TypeError as exc:
        ok("tipo lista não estoura", False, str(exc))

    rodada1 = json.loads(json.dumps(docs[0]))
    rodada1["achados"][0]["side"] = ["RIGHT"]
    try:
        erros = mod.validar(rodada1)
        ok("side lista não estoura", any("side" in e for e in erros), "; ".join(erros))
    except TypeError as exc:
        ok("side lista não estoura", False, str(exc))

    rodada1 = json.loads(json.dumps(docs[0]))
    rodada1["veredito"] = ["comentários"]
    try:
        erros = mod.validar(rodada1)
        ok("veredito lista não estoura", any("veredito" in e for e in erros), "; ".join(erros))
    except TypeError as exc:
        ok("veredito lista não estoura", False, str(exc))

    incompleto = json.loads(json.dumps(docs[1]))
    incompleto["resolucao"] = []
    erros = mod.validar(incompleto)
    ok("ID do ledger ausente na resolucao", any("não cobre o ledger anterior: F1" in e for e in erros), "; ".join(erros))

    desconhecido = json.loads(json.dumps(docs[1]))
    desconhecido["resolucao"].append(
        {
            "id": "F9",
            "severidade": "bloqueante",
            "status": "aberto",
            "nota": "não estava na review anterior",
        }
    )
    erros = mod.validar(desconhecido)
    ok("ID fora do ledger", any("fora do ledger anterior: F9" in e for e in erros), "; ".join(erros))

    trocada = json.loads(json.dumps(docs[1]))
    trocada["resolucao"][0]["severidade"] = "bloqueante"
    erros = mod.validar(trocada)
    ok(
        "severidade trocada",
        any("severidade no ledger anterior é deve-corrigir" in e for e in erros),
        "; ".join(erros),
    )

    sem_ledger = json.loads(json.dumps(docs[1]))
    del sem_ledger["ledger_anterior"]
    erros = mod.validar(sem_ledger)
    ok("rodada 2 sem ledger", any("exige ledger_anterior" in e for e in erros), "; ".join(erros))

    sem_coluna = json.loads(json.dumps(docs[1]))
    sem_coluna["resumo"] = sem_coluna["resumo"].replace(
        "| ID | Severidade | Status | Nota |",
        "| ID | Status | Nota |",
    )
    erros = mod.validar(sem_coluna)
    ok("tabela sem coluna Severidade", any("Severidade" in e for e in erros), "; ".join(erros))

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "findings.json"
        src.write_text(json.dumps(docs[1]), encoding="utf-8")
        bate = subprocess.run(
            [sys.executable, str(GATE), str(src), "--ledger", "F1:deve-corrigir"],
            text=True,
            capture_output=True,
        )
        ok("flag igual ao ledger passa", bate.returncode == 0, bate.stdout + bate.stderr)
        diverge = subprocess.run(
            [sys.executable, str(GATE), str(src), "--ledger", "F1:bloqueante"],
            text=True,
            capture_output=True,
        )
        ok("flag diverge do ledger", diverge.returncode == 1 and "divergem" in diverge.stdout, diverge.stdout)
        lista = json.loads(json.dumps(docs[0]))
        lista["achados"][0]["severidade"] = ["deve-corrigir"]
        src.write_text(json.dumps(lista), encoding="utf-8")
        cli = subprocess.run([sys.executable, str(GATE), str(src)], text=True, capture_output=True)
        ok(
            "cli com severidade lista não estoura",
            cli.returncode == 1 and "Traceback" not in cli.stderr and "severidade" in cli.stdout,
            cli.stdout + cli.stderr,
        )

    print("---")
    if falhas:
        print(f"{len(falhas)} falha(s)")
        return 1
    print("tudo ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
