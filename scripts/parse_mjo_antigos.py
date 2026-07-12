#!/usr/bin/env python3
"""Parsers dos Movimentos Judiciais Ordinários 2004–2013 (formatos antigos).

Quatro famílias:
  A) 2004–2008 — tabela numerada (n.º | Dr(a). nome | n.º ordem | class+origem
     | vaga | destino | n.º pedido); Dr./Dr.ª dá o género diretamente.
  B) 2011 — proto-iudex do definitivo da 1.ª instância ("Cód Magistrado /
     Situação | Classificação – N.º Ordem | Onde vai ser colocado").
  C) 2012–2013 — DOC convertido a texto com colunas separadas por tabs.
  D) 2009–2010 (+ Relação 2011) — prosa do Diário da República
     («Dr. X, juiz …, transferido a pedido para …»), extraída em modo de
     fluxo (pdftotext sem -layout).
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/movimentos"
OUT = ROOT / "data/processed/movimentos_2004_2013.json"

CLASS_MAP = {"Muito Bom": "MB", "Bom com distinção": "BD", "Bom Com Distinção": "BD",
             "Bom": "B", "Suficiente": "S", "MB": "MB", "BD": "BD", "B": "B",
             "S": "S", "s/c": None, "SB": "BD"}


def rec(ano, seccao, nome, destino, origem=None, **kw):
    return {
        "ano": ano, "seccao": seccao, "codigo": kw.get("codigo"),
        "nome": re.sub(r"\s+", " ", nome).strip(),
        "genero_hint": kw.get("genero_hint"),
        "classificacao": kw.get("classificacao"),
        "antiguidade": kw.get("antiguidade"),
        "origem": re.sub(r"\s+", " ", origem).strip() if origem else None,
        "destino": re.sub(r"\s+", " ", destino).strip() if destino else None,
        "motivo": kw.get("motivo"),
        "preferencia": kw.get("preferencia"),
    }


# ---------------------------------------------------------------- A) 2004-08
SECCAO_REL = re.compile(r"^TRIBUNAIS? DA REDA[ÇC]|^TRIBUNAIS? DA RELA[ÇC][ÃA]O")
SECCAO_1A = re.compile(r"^(1\s*ª\s*INST[ÂA]NCIA|PRIMEIRA INST[ÂA]NCIA|ACESSO FINAL|"
                       r"PRIMEIRO ACESSO|A AGUARDAR|TRIBUNAIS? DE\b|JU[ÍI]ZES DE DIREITO)")
MOTIVO_A = re.compile(r"^\s*(TRANSFER[ÊE]NCIAS?[/ A-ZÀ-Ú]*|PROMO[ÇC][ÕO]ES|"
                      r"COLOCA[ÇC][ÕO]ES|AUXILIARES[/ A-ZÀ-Ú]*|NOMEA[ÇC][ÕO]ES|"
                      r"DESTACAMENTOS?[/ A-ZÀ-Ú]*)\s*$")
ROW_A = re.compile(r"^\s*\d+\s+(Dr\.?ªa?\.?|Dra\.|Dr\.)\s")


def parse_tabular(path, ano):
    out, seccao, motivo = [], None, None
    for linha in path.read_text(encoding="utf-8").splitlines():
        s = linha.strip()
        if not s:
            continue
        s_semnum = re.sub(r"^\d+\s+", "", s)
        if MOTIVO_A.match(s_semnum):
            motivo = s_semnum.title().split("/")[0].strip()
            continue
        if SECCAO_REL.match(s_semnum):
            seccao = "Relação"
            continue
        if SECCAO_1A.match(s_semnum):
            seccao = "1.ª Instância"
            continue
        if not ROW_A.match(linha):
            continue
        segs = [(m.start(), m.group()) for m in re.finditer(r"\S(?:.{0,1}\S)*", linha)]
        txts = [g for _, g in segs]
        # nalgumas linhas o n.º de ordem e o nome fundem-se num só segmento
        m0 = re.match(r"^(\d+)\s+(Dr.*)$", txts[0])
        if m0:
            nome_raw, resto = m0.group(2), txts[1:]
        elif len(txts) > 1:
            nome_raw, resto = txts[1], txts[2:]
        else:
            continue
        if len(resto) < 2:
            continue
        pedido = resto[-1] if re.match(r"^\d{1,3}$", resto[-1]) else None
        destino = resto[-2] if pedido else resto[-1]
        meio = resto[:-2] if pedido else resto[:-1]
        ordem = None
        if meio and re.match(r"^\d+(/[A-Z])?$", meio[0]):
            m_ord = re.match(r"^(\d+)", meio[0])
            ordem = int(m_ord.group(1))
            meio = meio[1:]
        destino = re.sub(r"^\(?\d+\)?\s+", "", destino)
        classif, origem = None, None
        if meio:
            m_co = re.match(r"^(MB|BD|S/C|s/c|SB|B|S)?\s*(.*)$", meio[0])
            classif = CLASS_MAP.get(m_co.group(1)) if m_co.group(1) else None
            origem = m_co.group(2) or None
            if origem:
                origem = re.sub(r"^\(?\d+\)?\s+|^/C\s+", "", origem) or None
            meio = meio[1:]
        # o que sobrar no meio é o n.º da vaga — ignorado
        if re.match(r"^Renova", destino, re.I):
            motivo_rec = "Renovação"
            destino = origem
        else:
            motivo_rec = motivo
        gh = "F" if re.match(r"^Dr\.?ª|^Dra\.", nome_raw) else "M"
        nome = re.sub(r"^(Dr\.?ªa?\.?|Dra\.|Dr\.)\s*", "", nome_raw)
        out.append(rec(ano, seccao or "1.ª Instância", nome, destino, origem,
                       classificacao=classif, antiguidade=ordem,
                       preferencia=int(pedido) if pedido else None,
                       motivo=motivo_rec, genero_hint=gh))
    return out


# ---------------------------------------------------------------- B) 2011
NAME_B = re.compile(r"^(\d{3,4})\s+([A-ZÀ-Ú][A-Za-zÀ-ÿ' .-]+)$")
CLASSORD_B = re.compile(r"(Muito Bom|Bom com distinção|Bom|Suficiente)\s*-\s*(\d+)")
MOTIVO_B = re.compile(r"^(.+?)\s*-\s*(Efe[ct]{1,2}ivo|Auxiliar[A-Za-zÀ-ú ]*)\s*(?:\((\d+)\))?$")
SECCAO_B = re.compile(r"^\s*[A-ZÀ-Ú][A-ZÀ-Ú /–-]{8,}\s*$")


def parse_2011(path, ano=2011):
    out, seccao, atual = [], "1.ª Instância", None
    for linha in path.read_text(encoding="utf-8").splitlines():
        s = linha.strip()
        if not s or "Conselho Superior" in s or "Movimento Judicial" in s \
                or s.startswith("Cód Magistrado") or re.match(r"^\d+/\d+$", s):
            continue
        segs = [(m.start(), m.group()) for m in re.finditer(r"\S(?:.{0,1}\S)*", linha)]
        nm = NAME_B.match(segs[0][1]) if segs and segs[0][0] < 10 else None
        if nm and not SECCAO_B.match(segs[0][1]):
            if atual:
                out.append(atual)
            atual = rec(ano, seccao, nm.group(2), None, codigo=int(nm.group(1)))
            atual["_dest"] = [g for pos, g in segs[1:]]
            continue
        if SECCAO_B.match(s):
            if atual:
                out.append(atual)
                atual = None
            continue
        if not atual:
            continue
        for pos, g in segs:
            co = CLASSORD_B.search(g)
            if co:
                atual["classificacao"] = CLASS_MAP.get(co.group(1))
                atual["antiguidade"] = int(co.group(2))
                continue
            if pos < 12:
                if g.startswith("- ") and not atual["origem"] and not re.match(r"^- \d{4}-", g):
                    atual["origem"] = g[2:].strip()
                continue
            mm = MOTIVO_B.match(g)
            if mm and not atual["motivo"]:
                atual["motivo"] = mm.group(1)
                atual["preferencia"] = int(mm.group(3)) if mm.group(3) else None
            elif not atual["motivo"]:
                atual["_dest"].append(g)
    if atual:
        out.append(atual)
    for r in out:
        r["destino"] = re.sub(r"\s+", " ", " ".join(r.pop("_dest", []) or [])).strip() or None
    return [r for r in out if r["destino"]]


# ---------------------------------------------------------------- C) 2012-13
ROW_C1 = re.compile(r"^\t?\s?(\d{3,4})\s*\t+\s*-?\s*(.+?)\t+(.+?)\s*$")
ROW_C2 = re.compile(r"^\s*\t+\s*-\s*(.+?)\t+(.+?)\s*$")
ROW_C3 = re.compile(r"^\s*\t+\s*-?\s*\d{4}-\d\d-\d\d\s*-\s*(.+?)\s*\t*$")


def parse_doc(path, ano):
    out, seccao, atual = [], None, None
    for linha in path.read_text(encoding="utf-8").splitlines():
        s = linha.strip()
        if not s:
            continue
        if re.match(r"^[A-ZÀ-Ú][A-ZÀ-Ú /–-]{8,}$", s):
            seccao = "Relação" if "RELA" in s else "1.ª Instância"
            if atual:
                out.append(atual)
                atual = None
            continue
        m1 = ROW_C1.match(linha)
        if m1 and re.match(r"^\t?\s?\d{3,4}\t", linha):
            if atual:
                out.append(atual)
            atual = rec(ano, seccao or "1.ª Instância", m1.group(2), m1.group(3),
                        codigo=int(m1.group(1)))
            continue
        if not atual:
            continue
        m3 = ROW_C3.match(linha)
        if m3:
            co = CLASSORD_B.search(linha)
            if co:
                atual["classificacao"] = CLASS_MAP.get(co.group(1))
                atual["antiguidade"] = int(co.group(2))
            else:
                mn = re.search(r"\t(\d{1,4})\s*\t*$", linha)
                if mn:
                    atual["antiguidade"] = int(mn.group(1))
            continue
        m2 = ROW_C2.match(linha)
        if m2:
            if atual["origem"] is None:
                atual["origem"] = m2.group(1).strip()
            mm = MOTIVO_B.match(re.sub(r"^Vaga d[oe] \d+\s*-\s*", "", m2.group(2).strip()))
            if mm and not atual["motivo"]:
                atual["motivo"] = mm.group(1)
                atual["preferencia"] = int(mm.group(3)) if mm.group(3) else None
    if atual:
        out.append(atual)
    return out


# ---------------------------------------------------------------- D) DR prosa
PAPEL_D = re.compile(r"ju[íi]za?\s+(de direito|desembargadora?)|desembargadora?", re.I)
VERBO_D = re.compile(
    r"\b(transferid[oa]|promovid[oa](?:\s+e\s+colocad[oa])?|recolocad[oa]|colocad[oa]|"
    r"nomead[oa]|destacad[oa]|renovad[oa] [oa] destacamento)\b([^A-Z]*?)\s+"
    r"(?:para|n[oa]s?|como)\s+(.+)$", re.S)
VERBO_MOTIVO = [("transferid", "Transferência"), ("promovid", "Promoção"),
                ("nomead", "Nomeação"), ("destacad", "Destacamento"),
                ("renovad", "Renovação"), ("colocad", "Colocação")]


def parse_dr(pdf_path, ano, so_relacao=False):
    txt = subprocess.run(["pdftotext", str(pdf_path), "-"],
                         capture_output=True, text=True).stdout
    corpo = re.sub(r"-\n", "", txt)
    corpo = re.sub(r"\s+", " ", corpo)
    out = []
    partes = re.split(r"(?=\bDra?\.?ª?\s+[A-ZÀ-Ú])", corpo)
    for parte in partes:
        m = re.match(r"^(Dr\.?ª|Dra\.?|Dr\.?)\s+([A-ZÀ-Ú][^,]{4,70}?),\s*(.*)$", parte, re.S)
        if not m:
            continue
        titulo, nome, resto = m.groups()
        resto = resto[:400]
        if not PAPEL_D.search(resto[:150]):
            continue
        v = VERBO_D.search(resto)
        if not v:
            continue
        verbo, _, destino = v.groups()
        destino = re.split(r"[.;,]|\s+Dr\.", destino)[0].strip()
        destino = re.sub(r",?\s*(mantendo|acumulando|com efeitos|sem prejuízo).*$", "", destino).strip()
        if not destino or len(destino) > 140:
            continue
        situacao = resto[:v.start()].strip(" ,")
        rel = "Relação" in situacao[:120] or "desembargador" in situacao[:60].lower()             or "Relação" in destino
        if so_relacao and not rel:
            continue
        motivo = next((mo for vb, mo in VERBO_MOTIVO if vb in verbo), None)
        origem = re.sub(r"^ju[íi]za?\s*(de direito|desembargadora?)?,?\s*", "", situacao, flags=re.I)
        origem = re.sub(r"^(servindo como.*?n[oa]|d[oa]s?|em|no|na)\s+", "", origem).strip(" ,") or None
        if origem and len(origem) > 140:
            origem = origem[:140]
        if "permuta" in v.group(0).lower():
            motivo = "Permuta"
        out.append(rec(ano, "Relação" if rel else "1.ª Instância", nome.strip(),
                       destino, origem, motivo=motivo,
                       genero_hint="F" if ("a" in titulo[2:] or "ª" in titulo) else "M"))
    return out


def main():
    todos = []
    fontes = [
        (parse_tabular, "mjo_2004_final.txt", 2004, {}),
        (parse_tabular, "mjo_2005_final.txt", 2005, {}),
        (parse_tabular, "mjo_2006_final.txt", 2006, {}),
        (parse_tabular, "mjo_2007_final.txt", 2007, {}),
        (parse_tabular, "mjo_2008_final.txt", 2008, {}),
        (parse_dr, "mjo_2009_publicacao.pdf", 2009, {}),
        (parse_dr, "mjo_2010_publicacao.pdf", 2010, {}),
        (parse_2011, "mjo_2011_definitivo.txt", 2011, {}),
        (parse_dr, "mjo_2011_publicacao.pdf", 2011, {"so_relacao": True}),
        (parse_doc, "mjo_2012_definitivo_doc.txt", 2012, {}),
        (parse_doc, "mjo_2013_definitivo_doc.txt", 2013, {}),
    ]
    rx_1a = re.compile(r"J[zu][íi]?[zo]?|Comarca|Vara|C[íi]rculo|Inst[âa]ncia|Bolsa", re.I)
    for fn, nome_f, ano, kw in fontes:
        regs = fn(RAW / nome_f, ano, **kw)
        for r in regs:
            if r["seccao"] == "Relação" and r["destino"] and "Relação" not in r["destino"] \
                    and rx_1a.search(r["destino"]):
                r["seccao"] = "1.ª Instância"
        print(f"{nome_f:34s} {len(regs):5d} registos")
        todos.extend(regs)
    OUT.write_text(json.dumps(todos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"TOTAL {len(todos)} -> {OUT}")


if __name__ == "__main__":
    main()
