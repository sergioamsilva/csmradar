#!/usr/bin/env python3
"""Parser dos Quadros de Juízes do CSM (PDFs tabulares, via pdfplumber).

Cada linha de output: ano, instancia, comarca/tribunal, juizo/seccao, lugar,
nome, notas (conteúdo entre parênteses junto ao nome, p.ex. comissões de
serviço). Ficheiros sem tabelas extraíveis (formatos antigos em texto) são
assinalados e ficam de fora — continuam registados na tabela `documentos`.
"""

import json
import re
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/quadros"
OUT = ROOT / "data/processed/quadro_juizes.json"

HDR_MAP = [
    (re.compile(r"comarca|tribunal / ju|relação$", re.I), "grupo"),
    (re.compile(r"ju[íi]zo|sec[çc][ãa]o|bolsa", re.I), "unidade"),
    (re.compile(r"lugar|posi[çc][ãa]o|vaga", re.I), "lugar"),
    (re.compile(r"nome|juiz$|magistrado", re.I), "nome"),
]


def classify_header(row):
    """Devolve mapa índice-de-coluna -> papel, se a linha parecer um cabeçalho."""
    roles = {}
    for i, cell in enumerate(row):
        if not cell:
            continue
        for rx, role in HDR_MAP:
            if rx.search(cell.strip()):
                roles[i] = role
                break
    return roles if "nome" in roles.values() else None


def clean(cell):
    if cell is None:
        return None
    return re.sub(r"\s+", " ", cell).strip() or None


def split_notas(nome):
    notas = re.findall(r"\(([^()]*)\)", nome)
    base = re.sub(r"\s*\([^()]*\)", "", nome).strip()
    return base, "; ".join(n.strip() for n in notas) or None


HEADERISH = re.compile(
    r"^(JUIZ DE DIREITO|AFETAÇÕES|TRIBUNAL|INÍCIO DA AFETAÇÃO|Nome|Juiz|Comarca.*|Relação|Secção|Lugar|Posição.*)$",
    re.I,
)


def roles_por_posicao(ncols, bolsa=False):
    if bolsa:
        return {0: "grupo", 1: "nome", 2: "unidade", 3: "lugar"}
    return {
        4: {0: "grupo", 1: "unidade", 2: "lugar", 3: "nome"},
        3: {0: "grupo", 1: "unidade", 2: "nome"},
        2: {0: "unidade", 1: "nome"},
        1: {0: "nome"},
    }.get(ncols, {ncols - 1: "nome"})


def parse_file(path, ano, instancia, bolsa=False):
    rows_out = []
    fill = {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                eff = [i for i in range(len(table[0]))
                       if any(r[i] for r in table if r and len(r) > i)]
                base = roles_por_posicao(len(eff), bolsa)
                roles = {col: base[j] for j, col in enumerate(eff) if j in base}
                for row in table:
                    cells = [clean(c) for c in row]
                    cells = [None if (c and HEADERISH.match(c)) else c for c in cells]
                    if classify_header(cells):
                        continue
                    rec = {}
                    for i, cell in enumerate(cells):
                        role = roles.get(i)
                        if not role:
                            continue
                        if cell is None:
                            cell = fill.get(role)
                        else:
                            fill[role] = cell
                        rec[role] = cell
                    nome = rec.get("nome")
                    if not nome or re.match(r"^\d+$", nome) or HEADERISH.match(nome):
                        continue
                    nome, notas = split_notas(nome)
                    if not nome or not re.match(r"^[A-ZÀ-Ú]", nome):
                        continue
                    grupo = rec.get("grupo")
                    if grupo and re.match(r"^([A-Z]\s+)+[A-Z]$", grupo):
                        grupo = grupo.replace(" ", "").title()  # "L I S B O A" vertical
                    rows_out.append({
                        "ano": ano,
                        "instancia": instancia,
                        "grupo": grupo,
                        "unidade": rec.get("unidade"),
                        "lugar": rec.get("lugar"),
                        "nome": nome,
                        "notas": notas,
                    })
    lugarish = sum(1 for r in rows_out if r["nome"].startswith(("Tribunal", "TJ Comarca", "Juízo")))
    if rows_out and lugarish > len(rows_out) / 2:
        for r in rows_out:
            r["nome"], r["unidade"] = (r["unidade"] or ""), r["nome"]
        rows_out = [r for r in rows_out if r["nome"] and not r["nome"].startswith(("Tribunal", "TJ", "Juízo"))]
    return rows_out


def parse_lista_texto(path, ano, instancia, grupo=None):
    """Listas simples de nomes (com notas em parênteses, possivelmente
    quebradas em várias linhas) sem grelha de tabela."""
    rows = []
    with pdfplumber.open(path) as pdf:
        buf = ""
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                s = re.sub(r"\s+", " ", line).strip()
                if not s or re.match(r"^(TRIBUNA|QUADRO|CONSELHO|Página|\d+/\d+)", s, re.I):
                    continue
                buf = (buf + " " + s).strip() if buf else s
                if buf.count("(") > buf.count(")"):
                    continue  # nota quebrada em duas linhas
                if re.match(r"^[A-ZÀ-Ú][a-zà-ú]", buf):
                    nome, notas = split_notas(buf)
                    rows.append({"ano": ano, "instancia": instancia, "grupo": grupo,
                                 "unidade": None, "lugar": None, "nome": nome, "notas": notas})
                buf = ""
    return rows


def parse_stj_texto(path, ano):
    """STJ: lista numerada simples (tabela nem sempre reconhecida)."""
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                m = re.match(r"^\s*(\d{1,3})\s+([A-ZÀ-Ú][A-Za-zÀ-ÿ' .-]+)$", line)
                if m:
                    nome, notas = split_notas(m.group(2).strip())
                    rows.append({
                        "ano": ano, "instancia": "STJ", "grupo": "Supremo Tribunal de Justiça",
                        "unidade": None, "lugar": None, "nome": nome, "notas": notas,
                    })
    return rows


def main():
    manifest = (RAW / "manifest.tsv").read_text().strip().splitlines()
    all_rows = []
    for entry in manifest:
        ano, tipo, _url = entry.split("\t")
        ano = int(ano)
        path = RAW / f"quadro_{ano}_{tipo}.pdf"
        if not path.exists():
            continue
        if tipo == "stj":
            candidatos = [parse_stj_texto(path, ano), parse_file(path, ano, "STJ"),
                          parse_lista_texto(path, ano, "STJ", grupo="Supremo Tribunal de Justiça")]
            rows = max(candidatos, key=len)
        else:
            instancia = {"relacao": "Relação", "1instancia": "1.ª Instância",
                         "geral": "Geral"}.get(tipo, "Bolsa/QCJ" if tipo.startswith(("bolsa", "afeta")) else tipo)
            rows = parse_file(path, ano, instancia, bolsa=tipo.startswith(("bolsa", "afeta")))
            if len(rows) < 30 and tipo == "relacao":
                rows = parse_lista_texto(path, ano, "Relação", grupo="Tribunais da Relação")
        print(f"quadro_{ano}_{tipo:24s} {len(rows):5d} lugares")
        all_rows.extend(rows)
    OUT.write_text(json.dumps(all_rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"TOTAL {len(all_rows)} -> {OUT}")


if __name__ == "__main__":
    main()
