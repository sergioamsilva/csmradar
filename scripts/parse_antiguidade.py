#!/usr/bin/env python3
"""Parser da Lista de Antiguidade dos Magistrados Judiciais (CSM, PDF anual).

Estrutura do PDF (2025): secções "Categoria: Juiz Conselheiro / Juiz
Desembargador / Juiz de Direito"; cada magistrado numa linha
  <ord> <nome> (<n.º mecanográfico>) <tempo na categoria> <tempo na magistratura>
seguida das linhas de colocação. Os tempos vêm como "X anos, Y meses, Z dias"
(componentes opcionais). Não há datas de nascimento — a idade só pode ser
estimada por fora (ano de ingresso = referência − tempo na magistratura).

Uso: python3 scripts/parse_antiguidade.py data/raw/lista_antiguidade_2025.pdf 2025
Cria/substitui as linhas do ano na tabela `antiguidade` de data/csmradar.db.
"""

import re
import sqlite3
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from genero import inferir_genero  # noqa: E402

ENT = re.compile(r"(?m)^(\d{1,4})\s+(\D[^(\n]*?)\s*\((\d+)\)\s*(.*)$")
CAT = re.compile(r"Categoria:\s*([^\n]+)")
TEMPO = re.compile(r"(\d+)\s+(anos?|m(?:ês|eses)|dias?)")
RUIDO = re.compile(
    r"^(CONSELHO SUPERIOR|Antiguidade referente|Ord Identificação|\d+ / \d+|LISTA DE ANTIGUIDADE|31 DE DEZEMBRO)"
)

RANK = {"a": 0, "m": 1, "d": 2}


def parse_tempos(s):
    """Separa a string em dois tempos de serviço; devolve anos decimais."""
    pares = [(int(n), u[0]) for n, u in TEMPO.findall(s)]
    tempos, atual = [], []
    for n, u in pares:
        if atual and RANK[u] <= RANK[atual[-1][1]]:
            tempos.append(atual)
            atual = []
        atual.append((n, u))
    if atual:
        tempos.append(atual)
    if len(tempos) != 2:
        return None
    out = []
    for t in tempos:
        anos = 0.0
        for n, u in t:
            anos += n * {"a": 1, "m": 1 / 12, "d": 1 / 365.25}[u]
        out.append(round(anos, 2))
    return out


def main(pdf_path, ano_ref):
    with pdfplumber.open(pdf_path) as pdf:
        txt = "\n".join(p.extract_text() or "" for p in pdf.pages)

    linhas = txt.split("\n")
    categoria = None
    regs = []
    i = 0
    while i < len(linhas):
        ln = linhas[i]
        mcat = CAT.search(ln)
        if mcat:
            categoria = mcat.group(1).strip()
            i += 1
            continue
        m = ENT.match(ln)
        if m and categoria:
            tempos = parse_tempos(m.group(4))
            if tempos:
                # primeira linha de colocação (salta cabeçalhos de página)
                coloc = ""
                j = i + 1
                while j < len(linhas) and (RUIDO.match(linhas[j]) or not linhas[j].strip()):
                    j += 1
                if j < len(linhas) and not ENT.match(linhas[j]):
                    coloc = linhas[j].strip()
                nome = re.sub(r"\s+", " ", m.group(2)).strip()
                regs.append((ano_ref, categoria, int(m.group(1)), nome,
                             int(m.group(3)), tempos[0], tempos[1], coloc,
                             inferir_genero(nome)))
        i += 1

    con = sqlite3.connect(ROOT / "data/csmradar.db")
    con.execute("""CREATE TABLE IF NOT EXISTS antiguidade (
        ano_ref INTEGER, categoria TEXT, ord INTEGER, nome TEXT, num INTEGER,
        anos_categoria REAL, anos_magistratura REAL, colocacao TEXT, genero TEXT)""")
    con.execute("DELETE FROM antiguidade WHERE ano_ref = ?", (ano_ref,))
    con.executemany("INSERT INTO antiguidade VALUES (?,?,?,?,?,?,?,?,?)", regs)
    con.commit()
    for cat, n in con.execute(
            "SELECT categoria, COUNT(*) FROM antiguidade WHERE ano_ref = ? GROUP BY categoria",
            (ano_ref,)):
        print(f"{cat}: {n}")
    print(f"total: {len(regs)}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
