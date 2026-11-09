#!/usr/bin/env python3
# Confere findings.json e, com --emit, grava o payload de review (evento COMMENT).
# Não altera o findings.json. Uso: conferir-achados.py <findings.json> [--ledger ID:severidade,...] [--emit <payload.json>]
"""Gate determinístico do review. Exit 0 só quando o JSON pode ser postado."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEVERIDADES = {
    "bloqueante": "🔴",
    "deve-corrigir": "🟠",
    "nit": "🟡",
    "pre-existente": "🟣",
}
VEREDITOS = (
    "precisa de mudanças",
    "comentários",
    "pronto para aprovação humana",
)
STATUS = ("resolvido", "aberto", "recusado-aceito")
SECOES = (
    "TL;DR",
    "Achados",
    "Virar regra de lint",
    "Pesquisa",
    "Checks",
    "Arquivos ignorados",
)
LIMITE_CORPO = 900
LIMITE_RESUMO = 60000
MARCADOR = re.compile(r"<!-- revisar-pr round=(\d+) sha=([0-9a-f]{40}) -->")
EXCLAMACAO = re.compile(r"!(?=\s|$)")
SHA40 = re.compile(r"[0-9a-f]{40}")
SHA_NOTA = re.compile(r"[0-9a-f]{7,40}")
ID = re.compile(r"F[1-9][0-9]*")


def uso() -> str:
    return (
        "Uso: conferir-achados.py <findings.json> [--ledger ID:severidade,...] [--emit <payload.json>]\n"
        "Confere o JSON e, com --emit, grava o payload com event COMMENT.\n"
        "Não altera o findings.json. Exit 0 só quando pode postar."
    )


def token_em(valor: object, permitidos: tuple[str, ...] | dict[str, str]) -> bool:
    return isinstance(valor, str) and valor in permitidos


def caminho_ok(valor: str) -> bool:
    if not valor or valor.startswith(("/", "~")) or "\\" in valor:
        return False
    partes = valor.split("/")
    return ".." not in partes and all(partes)


def evidencia_ok(item: dict, onde: str, erros: list[str]) -> None:
    evidencias = item.get("evidencia")
    if not isinstance(evidencias, list) or not evidencias:
        erros.append(f"{onde}.evidencia: todo achado exige ao menos uma evidência")
        return
    for i, ev in enumerate(evidencias):
        loc = f"{onde}.evidencia[{i}]"
        if not isinstance(ev, dict):
            erros.append(f"{loc}: tem que ser objeto")
            continue
        tipo = ev.get("tipo")
        ref = ev.get("ref")
        if not token_em(tipo, ("interna", "externa")) or not isinstance(ref, str):
            erros.append(f"{loc}: tipo interna|externa e ref string")
            continue
        if tipo == "interna":
            m = re.fullmatch(r"(.+):([1-9][0-9]*)", ref)
            if not m or not caminho_ok(m.group(1)):
                erros.append(f"{loc}: evidência interna é path:line relativo (sem .. nem absoluto)")
        elif not re.fullmatch(r"https://\S+", ref):
            erros.append(f"{loc}: evidência externa é URL https://")


def validar_achado(item: dict, i: int, rodada: int, erros: list[str]) -> None:
    onde = f"achados[{i}]"
    if not isinstance(item, dict):
        erros.append(f"{onde}: tem que ser objeto")
        return
    fid = item.get("id")
    sev = item.get("severidade")
    body = item.get("body")
    if not isinstance(fid, str) or not ID.fullmatch(fid):
        erros.append(f"{onde}.id: use F1, F2, … sem zero à esquerda")
        fid = None
    if not token_em(sev, SEVERIDADES):
        erros.append(f"{onde}.severidade: string, uma de {', '.join(SEVERIDADES)}")
        sev = None
    if rodada >= 2 and sev != "bloqueante":
        erros.append(f"{onde}: rodada 2+ só aceita bloqueante novo; o resto fica na resolução ou morre")
    if not isinstance(body, str) or not body.strip():
        erros.append(f"{onde}.body: texto obrigatório")
        body = ""
    if fid and sev and body:
        prefixo = f"{SEVERIDADES[sev]} {fid} "
        if not body.startswith(prefixo):
            erros.append(f"{onde}.body: tem que começar com {prefixo!r}")
    if body and len(body) > LIMITE_CORPO:
        erros.append(f"{onde}.body: {len(body)} caracteres; o teto é {LIMITE_CORPO}")
    if body and EXCLAMACAO.search(body):
        erros.append(f"{onde}.body: sem ponto de exclamação")
    evidencia_ok(item, onde, erros)

    linha = item.get("line", None)
    lado = item.get("side", None)
    path = item.get("path", None)
    tem_linha = "line" in item and linha is not None
    if sev == "pre-existente":
        if tem_linha or ("side" in item and lado is not None):
            erros.append(f"{onde}: pré-existente não tem line nem side (só no resumo)")
        if path is not None and (not isinstance(path, str) or not caminho_ok(path)):
            erros.append(f"{onde}.path: relativo, ou omita")
        return
    if sev is None:
        return
    if not isinstance(path, str) or not caminho_ok(path):
        erros.append(f"{onde}.path: caminho relativo do arquivo no diff")
    if type(linha) is not int or linha < 1:
        erros.append(f"{onde}.line: número da linha no arquivo (não a posição do hunk), a partir de 1")
    if not token_em(lado, ("RIGHT", "LEFT")):
        erros.append(f"{onde}.side: string RIGHT (arquivo novo) ou LEFT (arquivo antigo)")


def validar_resolucao(item: dict, i: int, erros: list[str]) -> None:
    onde = f"resolucao[{i}]"
    if not isinstance(item, dict):
        erros.append(f"{onde}: tem que ser objeto")
        return
    fid = item.get("id")
    sev = item.get("severidade")
    status = item.get("status")
    nota = item.get("nota")
    if not isinstance(fid, str) or not ID.fullmatch(fid):
        erros.append(f"{onde}.id: use o ID antigo (F1, F2, …)")
    if not token_em(sev, SEVERIDADES):
        erros.append(f"{onde}.severidade: string, uma de {', '.join(SEVERIDADES)}")
        sev = None
    if not token_em(status, STATUS):
        erros.append(f"{onde}.status: string resolvido, aberto ou recusado-aceito")
        status = None
    if not isinstance(nota, str) or not nota.strip():
        erros.append(f"{onde}.nota: obrigatória")
    elif status == "resolvido" and not SHA_NOTA.search(nota):
        erros.append(f"{onde}.nota: resolvido cita o sha do commit que corrigiu")


def parse_ledger_flag(texto: str) -> tuple[dict[str, str] | None, list[str]]:
    erros: list[str] = []
    if texto.strip() == "":
        return {}, erros
    out: dict[str, str] = {}
    for parte in texto.split(","):
        parte = parte.strip()
        if ":" not in parte:
            erros.append(f"--ledger: item {parte!r} tem que ser ID:severidade")
            continue
        fid, sev = parte.split(":", 1)
        fid, sev = fid.strip(), sev.strip()
        if not isinstance(fid, str) or not ID.fullmatch(fid):
            erros.append(f"--ledger: ID inválido {fid!r}")
            continue
        if not token_em(sev, SEVERIDADES):
            erros.append(f"--ledger: severidade inválida {sev!r}")
            continue
        if fid in out:
            erros.append(f"--ledger: ID repetido {fid}")
            continue
        out[fid] = sev
    if erros:
        return None, erros
    return out, []


def ler_ledger_json(data: dict, erros: list[str]) -> tuple[bool, dict[str, str], bool]:
    if "ledger_anterior" not in data:
        return False, {}, True
    bruto = data["ledger_anterior"]
    if not isinstance(bruto, list):
        erros.append("ledger_anterior: lista de {id, severidade}")
        return True, {}, False
    out: dict[str, str] = {}
    ok = True
    for i, item in enumerate(bruto):
        onde = f"ledger_anterior[{i}]"
        if not isinstance(item, dict):
            erros.append(f"{onde}: objeto com id e severidade")
            ok = False
            continue
        fid = item.get("id")
        sev = item.get("severidade")
        if not isinstance(fid, str) or not ID.fullmatch(fid):
            erros.append(f"{onde}.id: use F1, F2, …")
            ok = False
            continue
        if not token_em(sev, SEVERIDADES):
            erros.append(f"{onde}.severidade: string, uma de {', '.join(SEVERIDADES)}")
            ok = False
            continue
        if fid in out:
            erros.append(f"ledger_anterior: ID repetido {fid}")
            ok = False
            continue
        out[fid] = sev
    return True, out, ok


def conferir_ledger(
    data: dict,
    resolucao: list,
    rodada: int,
    ledger_flag: dict[str, str] | None,
    erros: list[str],
) -> None:
    presente, mapa, ok = ler_ledger_json(data, erros)
    if rodada == 1:
        if (presente and mapa) or ledger_flag:
            erros.append("rodada 1 não leva ledger anterior")
        return
    if not isinstance(rodada, int) or rodada < 2:
        return
    if presente and ledger_flag is not None and ok and mapa != ledger_flag:
        faltam = sorted(set(mapa) - set(ledger_flag))
        sobram = sorted(set(ledger_flag) - set(mapa))
        trocas = sorted(i for i in mapa.keys() & ledger_flag.keys() if mapa[i] != ledger_flag[i])
        erros.append(
            "ledger_anterior e --ledger divergem"
            + (f"; faltam no flag {', '.join(faltam)}" if faltam else "")
            + (f"; sobram no flag {', '.join(sobram)}" if sobram else "")
            + (f"; severidade diferente {', '.join(trocas)}" if trocas else "")
        )
        return
    if presente and ok:
        esperado = mapa
    elif ledger_flag is not None and not presente:
        esperado = ledger_flag
    elif not presente and ledger_flag is None:
        erros.append(
            "rodada 2+ exige ledger_anterior ou --ledger com cada ID da review anterior"
        )
        return
    else:
        return

    ids_resolucao: dict[str, str] = {}
    resolucao_ok = True
    for item in resolucao:
        if not isinstance(item, dict):
            resolucao_ok = False
            continue
        fid = item.get("id")
        sev = item.get("severidade")
        if not isinstance(fid, str) or not isinstance(sev, str):
            resolucao_ok = False
            continue
        ids_resolucao[fid] = sev
    if not resolucao_ok:
        return
    faltam = sorted(set(esperado) - set(ids_resolucao))
    sobram = sorted(set(ids_resolucao) - set(esperado))
    if faltam:
        erros.append("resolucao não cobre o ledger anterior: " + ", ".join(faltam))
    if sobram:
        erros.append("resolucao traz ID fora do ledger anterior: " + ", ".join(sobram))
    for fid in sorted(set(esperado) & set(ids_resolucao)):
        if esperado[fid] != ids_resolucao[fid]:
            erros.append(
                f"{fid}: severidade no ledger anterior é {esperado[fid]}, "
                f"na resolucao é {ids_resolucao[fid]}"
            )


def secoes(resumo: str, erros: list[str]) -> dict[str, str]:
    partes = re.split(r"(?m)^## (.+?)[ \t]*$", resumo)
    if partes[0].strip():
        erros.append("o resumo tem texto antes de ## TL;DR")
    rest = partes[1:]
    if len(rest) % 2 != 0:
        erros.append("seções do resumo não fecham")
        return {}
    out: dict[str, str] = {}
    ordem: list[str] = []
    for i in range(0, len(rest), 2):
        nome = rest[i].strip()
        if nome in out:
            erros.append(f"seção duplicada: {nome}")
        out[nome] = rest[i + 1]
        ordem.append(nome)
    out["__ordem__"] = "\n".join(ordem)
    return out


def validar_resumo(data: dict, erros: list[str]) -> None:
    resumo = data.get("resumo")
    rodada = data.get("round")
    sha = data.get("head_sha")
    veredito = data.get("veredito")
    if not isinstance(resumo, str):
        erros.append("resumo: string markdown obrigatória")
        return
    if len(resumo) > LIMITE_RESUMO:
        erros.append(f"resumo: {len(resumo)} caracteres; o teto é {LIMITE_RESUMO}")
    blocos = secoes(resumo, erros)
    ordem = [n for n in blocos.get("__ordem__", "").splitlines() if n]
    esperada = ["TL;DR", "Achados"]
    if isinstance(rodada, int) and rodada >= 2:
        esperada.append("Resolução")
    esperada.extend(SECOES[2:])
    encontradas = [n for n in ordem if n != "Nits excedentes"]
    if encontradas != esperada:
        erros.append(
            "seções fora de ordem ou faltando: "
            + " | ".join(encontradas)
            + " — esperado: "
            + " | ".join(esperada)
        )
    if "Nits excedentes" in ordem and ordem[-1] != "Nits excedentes":
        erros.append("## Nits excedentes tem que ser a última seção")
    desconhecidas = [n for n in ordem if n not in esperada and n != "Nits excedentes"]
    for nome in desconhecidas:
        erros.append(f"seção desconhecida: {nome}")
    for nome in esperada:
        if nome in blocos and not blocos[nome].strip():
            erros.append(f"seção vazia: {nome}")
    for nome, corpo in blocos.items():
        if nome in ("Checks", "__ordem__"):
            continue
        if EXCLAMACAO.search(corpo):
            erros.append(f"exclamação na seção {nome} (no Checks o log entra verbatim)")

    if not isinstance(rodada, int) or not isinstance(sha, str) or not isinstance(veredito, str):
        return
    tldr = blocos.get("TL;DR", "")
    if f"Veredito pretendido: {veredito}." not in tldr:
        erros.append(f"TL;DR: falta a frase exata 'Veredito pretendido: {veredito}.'")
    if f"Rodada {rodada}. Commit revisado: `{sha}`." not in tldr:
        erros.append("TL;DR: falta a frase exata 'Rodada N. Commit revisado: `<sha>`.'")
    achados_txt = blocos.get("Achados", "")
    if "| ID | Severidade | Local | Resumo |" not in achados_txt:
        erros.append("Achados: falta o cabeçalho '| ID | Severidade | Local | Resumo |'")
    if rodada >= 2:
        resol_txt = blocos.get("Resolução", "")
        if "| ID | Severidade | Status | Nota |" not in resol_txt:
            erros.append("Resolução: falta o cabeçalho '| ID | Severidade | Status | Nota |'")
    fecho = f"Para nova rodada, comente `/review` no PR. Rodada {rodada} de no máximo 3."
    marcador = f"<!-- revisar-pr round={rodada} sha={sha} -->"
    if fecho not in resumo:
        erros.append(f"resumo: falta o fecho exato: {fecho}")
    linhas = [ln.strip() for ln in resumo.strip().splitlines() if ln.strip()]
    if not linhas or linhas[-1] != marcador:
        erros.append(f"a última linha do resumo tem que ser {marcador}")
    if MARCADOR.findall(resumo) != [(str(rodada), sha)]:
        erros.append("o marcador <!-- revisar-pr round=N sha=... --> tem que aparecer uma vez, batendo com round e head_sha")


def validar(data: dict, ledger_flag: dict[str, str] | None = None) -> list[str]:
    erros: list[str] = []
    if not isinstance(data, dict):
        return ["a raiz tem que ser um objeto JSON"]

    rodada = data.get("round")
    sha = data.get("head_sha")
    veredito = data.get("veredito")
    if type(rodada) is not int or not 1 <= rodada <= 3:
        erros.append("round: inteiro de 1 a 3 (não existe rodada 4)")
        rodada = 0
    if not isinstance(sha, str) or not SHA40.fullmatch(sha):
        erros.append("head_sha: SHA completo de 40 hex minúsculos (headRefOid)")
    if not token_em(veredito, VEREDITOS):
        erros.append("veredito: string, uma de " + " | ".join(VEREDITOS))

    carry = data.get("carryover")
    if not isinstance(carry, dict):
        erros.append("carryover: objeto com bloqueante e deve-corrigir")
        carry = None
    else:
        for chave in ("bloqueante", "deve-corrigir"):
            if type(carry.get(chave)) is not int or carry[chave] < 0:
                erros.append(f"carryover.{chave}: inteiro >= 0")

    achados = data.get("achados")
    if not isinstance(achados, list):
        erros.append("achados: lista (vazia se não houver achado novo)")
        achados = []
    for i, item in enumerate(achados):
        validar_achado(item, i, rodada if isinstance(rodada, int) else 0, erros)

    resolucao = data.get("resolucao", [])
    if rodada == 1:
        if "resolucao" in data and resolucao not in ([], None):
            erros.append("rodada 1 não leva resolucao")
        resolucao = []
    elif isinstance(rodada, int) and rodada >= 2:
        if not isinstance(data.get("resolucao"), list):
            erros.append("resolucao: lista obrigatória na rodada 2+ (vazia só se a rodada 1 não teve achados)")
            resolucao = []
    if not isinstance(resolucao, list):
        resolucao = []
    for i, item in enumerate(resolucao):
        validar_resolucao(item, i, erros)

    ids_novos = [a.get("id") for a in achados if isinstance(a, dict) and isinstance(a.get("id"), str)]
    ids_velhos = [r.get("id") for r in resolucao if isinstance(r, dict) and isinstance(r.get("id"), str)]
    if len(ids_novos) != len(set(ids_novos)):
        erros.append("achados: ID repetido")
    if len(ids_velhos) != len(set(ids_velhos)):
        erros.append("resolucao: ID repetido")
    cruzados = set(ids_novos) & set(ids_velhos)
    if cruzados:
        erros.append("ID não pode estar em achados e em resolucao: " + ", ".join(sorted(cruzados)))

    nits = [a for a in achados if isinstance(a, dict) and a.get("severidade") == "nit"]
    if len(nits) > 5:
        erros.append(f"nits: {len(nits)} inline; o teto é 5 (o excedente vira contagem no resumo)")

    conferir_ledger(data, resolucao, rodada if isinstance(rodada, int) else 0, ledger_flag, erros)
    validar_resumo(data, erros)
    if erros:
        return erros

    abertos_b = sum(
        1 for r in resolucao if r.get("severidade") == "bloqueante" and r.get("status") == "aberto"
    )
    abertos_o = sum(
        1 for r in resolucao if r.get("severidade") == "deve-corrigir" and r.get("status") == "aberto"
    )
    if carry["bloqueante"] != abertos_b or carry["deve-corrigir"] != abertos_o:
        erros.append(
            "carryover não bate com a resolução: "
            f"esperado bloqueante={abertos_b} deve-corrigir={abertos_o}"
        )
    novos_b = sum(1 for a in achados if a.get("severidade") == "bloqueante")
    novos_o = sum(1 for a in achados if a.get("severidade") == "deve-corrigir")
    if abertos_b + novos_b:
        esperado = "precisa de mudanças"
    elif abertos_o + novos_o:
        esperado = "comentários"
    else:
        esperado = "pronto para aprovação humana"
    if veredito != esperado:
        erros.append(f"veredito {veredito!r} não bate com os achados abertos; o esperado é {esperado!r}")

    resumo = data["resumo"]
    achados_txt = ""
    resol_txt = ""
    partes = re.split(r"(?m)^## (.+?)[ \t]*$", resumo)
    blocos: dict[str, str] = {}
    rest = partes[1:]
    for i in range(0, len(rest), 2):
        blocos[rest[i].strip()] = rest[i + 1]
    achados_txt = blocos.get("Achados", "")
    resol_txt = blocos.get("Resolução", "")
    for item in achados:
        fid = item["id"]
        sev = item["severidade"]
        if not re.search(rf"(?m)^\| {re.escape(fid)} \|.*\b{re.escape(sev)}\b", achados_txt):
            erros.append(f"Achados: falta a linha de {fid} com severidade {sev}")
    for item in resolucao:
        fid = item["id"]
        status = item["status"]
        sev = item["severidade"]
        if not re.search(
            rf"(?m)^\| {re.escape(fid)} \|[^|\n]*\b{re.escape(sev)}\b[^|\n]*\| {re.escape(status)} \|",
            resol_txt,
        ):
            erros.append(f"Resolução: falta a linha '| {fid} | {sev} | {status} |'")
    return erros


def payload_de(data: dict) -> dict:
    comments = []
    achados = sorted(
        (a for a in data["achados"] if isinstance(a.get("line"), int)),
        key=lambda a: int(a["id"][1:]),
    )
    for a in achados:
        comments.append(
            {"path": a["path"], "line": a["line"], "side": a["side"], "body": a["body"]}
        )
    payload = {"commit_id": data["head_sha"], "event": "COMMENT", "body": data["resumo"]}
    if comments:
        payload["comments"] = comments
    return payload


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="conferir-achados.py",
        description=(
            "Confere findings.json e, com --emit, grava o payload de review "
            "(evento COMMENT). Não altera o findings.json."
        ),
        usage="%(prog)s <findings.json> [--ledger ID:severidade,...] [--emit <payload.json>]",
    )
    parser.add_argument("findings", help="caminho do findings.json")
    parser.add_argument(
        "--ledger",
        metavar="ID:SEVERIDADE,...",
        help="IDs da review anterior; na rodada 2+ tem que bater com ledger_anterior e com resolucao",
    )
    parser.add_argument("--emit", metavar="PAYLOAD", help="grava o payload COMMENT neste caminho se o gate passar")
    if argv and argv[0] in ("-h", "--help"):
        parser.print_help()
        return 0
    args = parser.parse_args(argv)

    src = Path(args.findings)
    print(f"findings: {src}")
    if args.emit and Path(args.emit).resolve() == src.resolve():
        print("ERRO: --emit não pode ser o próprio findings.json")
        print("não pode postar: 1 erro(s)")
        return 1
    if not src.is_file():
        print("ERRO: arquivo não encontrado")
        print("não pode postar: 1 erro(s)")
        return 1
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"ERRO: JSON inválido: {exc}")
        print("não pode postar: 1 erro(s)")
        return 1

    flag_map = None
    flag_erros: list[str] = []
    if args.ledger is not None:
        flag_map, flag_erros = parse_ledger_flag(args.ledger)
    erros = flag_erros + validar(data, None if flag_erros else flag_map)
    if erros:
        for msg in erros:
            print(f"ERRO: {msg}")
        print(f"não pode postar: {len(erros)} erro(s)")
        if args.emit:
            print(f"payload: não atualizei {args.emit}")
        return 1

    achados = data["achados"]
    inline = sum(1 for a in achados if isinstance(a.get("line"), int))
    so_resumo = sum(1 for a in achados if a.get("severidade") == "pre-existente")
    nits = sum(1 for a in achados if a.get("severidade") == "nit")
    print(f"rodada: {data['round']}")
    print(f"head: {data['head_sha']}")
    print(f"veredito: {data['veredito']}")
    print(f"achados: {len(achados)} (inline {inline}, só no resumo {so_resumo})")
    print(f"nits inline: {nits}")
    print("pode postar")
    if args.emit:
        payload = payload_de(data)
        dest = Path(args.emit)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(dest)
        print(f"payload: {dest}")
        print("evento: COMMENT")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
