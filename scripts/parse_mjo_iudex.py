#!/usr/bin/env python3
"""Parser dos Movimentos Judiciais Ordinários 2014–2025 (formato "iudex").

Estrutura dos PDFs (pdftotext -layout), em 3 colunas:

  <cód> - <nome>                       [destino, alinhado à direita]
  <origem/situação atual>   <ordem>   [destino cont.] / <tipo - motivo (pref)>
  [notas à esquerda]                   [notas à direita]

Variantes:
  - 2014–2016: coluna central "MB | 5 | 45" (classificação | ordem mov. | antiguidade)
  - 2017–2025: coluna central "176" (n.º de ordem/antiguidade) ou "1º 7CCATR"
  - 2016 usa soft-hyphen (U+00AD) em vez de hífen.
"""

import json
import re
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data/raw/movimentos"
OUT = Path(__file__).resolve().parent.parent / "data/processed/movimentos_2014_2025.json"

# ficheiro -> (ano, secções a ingerir; None = todas, com deteção pelos cabeçalhos)
FONTES = [
    ("mjo_2014_1instancia.txt", 2014, "1.ª Instância", None),
    ("mjo_2014_relacao_efetivos.txt", 2014, "Relação", None),
    ("mjo_2014_relacao_auxiliares.txt", 2014, "Relação (auxiliares)", None),
    ("mjo_2015_1instancia.txt", 2015, "1.ª Instância", None),
    ("mjo_2015_relacao_efetivos.txt", 2015, "Relação", None),
    ("mjo_2015_relacao_auxiliares.txt", 2015, "Relação (auxiliares)", None),
    ("mjo_2016_1instancia.txt", 2016, "1.ª Instância", None),
    ("mjo_2016_relacao_efetivos.txt", 2016, "Relação", None),
    ("mjo_2016_relacao_auxiliares.txt", 2016, "Relação (auxiliares)", None),
    ("mjo_2017_final.txt", 2017, None, None),
    ("mjo_2018_consolidada.txt", 2018, None, None),
    ("mjo_2019_final_consolidada.txt", 2019, None, None),
    ("mjo_2020_final_consolidada.txt", 2020, None, None),
    ("mjo_2021_final_consolidada.txt", 2021, None, None),
    ("mjo_2022_final.txt", 2022, None, None),
    ("mjo_2023_aprovada.txt", 2023, None, "Relação"),   # só a Relação (1.ª vem da retificada)
    ("mjo_2023_retificada.txt", 2023, None, None),
    ("mjo_2024_consolidada.txt", 2024, None, None),
    ("mjo_2025_consolidada.txt", 2025, None, None),
]

SECTION_RE = re.compile(
    r"Movimento Judicial Ordinário(?: de)? \d{4}\s*-\s*(Tribunais d[ae] [A-Za-zÀ-ú ]+|Relação)"
)
HEADER_RE = re.compile(r"Cód\.? Magistrado")
NAME_RE = re.compile(r"^(\d{3,5})\s*-\s*(\S.*)$")
ORDEM_SIMPLES_RE = re.compile(r"^\d{1,4}$")
ORDEM_CURSO_RE = re.compile(r"^(\d{1,3})º(?:\s+(\d*\s*CCATR))?$")
ORDEM_TRIPLA_RE = re.compile(r"^([A-Z]{1,2})?\s*\|\s*(\d+)\s*\|\s*(\d+)$")
MOTIVO_RE = re.compile(
    r"^(Efe[ct]{1,2}ivo|Auxiliar(?: de [A-Za-zÀ-ú ]+)?|Destacamento|Interino)"
    r"\s*-\s*(.+?)\s*(?:\((\d+)\))?$"
)
# variante 2014 (Relação): "Transferência a pedido – Efectivo (1)"
MOTIVO_INV_RE = re.compile(
    r"^([A-ZÀ-Ú][a-zà-ú].+?)\s*[-–]\s*(Efe[ct]{1,2}ivo|Auxiliar(?: de [A-Za-zÀ-ú ]+)?)"
    r"\s*(?:\((\d+)\))?$"
)
FOOTER_RES = [
    re.compile(r"^\s*CONSELHO SUPERIOR DA MAGISTRATURA\s*$"),
    re.compile(r"^\s*JU\s*I\s*Z\s+S\s*EC\s*RE\s*T"),
    re.compile(r"^\s*\d+\s*/\s*\d+\s*$"),
    re.compile(r"Rua Duque de Palmela|Telefone: 213|csm@csm\.org\.pt|www\.csm\.org\.pt"),
]
# notas da coluna esquerda (tipo de saída/observações da situação atual)
NOTAS_ESQ = re.compile(
    r"^-?\s*(Colocação(?: a pedido| obrigatória)?|Promoção e [Cc]olocação|Transferência a pedido|Nomeação a pedido|"
    r"Requerimento|Acumulação de funções|Contratação|Destacamento a pedido|Promoção|"
    r"Nomeação|Transferência|Permuta|Regresso[a-zà-ú ]*|Cessação[a-zà-ú ]*|"
    r"Jubilação|Aposentação[a-zà-ú /]*|Fim de [a-zà-ú ]+|Desligado[a-zà-ú ]*)\s*$"
)


def segments(line):
    return [(m.start(), m.group()) for m in re.finditer(r"\S(?:.{0,1}\S)*", line)]


COMARCAS = [
    "Lisboa Norte", "Lisboa Oeste", "Porto Este", "Viana do Castelo",
    "Castelo Branco", "Vila Real", "Açores", "Aveiro", "Beja", "Braga",
    "Bragança", "Coimbra", "Évora", "Faro", "Guarda", "Leiria", "Lisboa",
    "Madeira", "Portalegre", "Porto", "Santarém", "Setúbal", "Viseu",
]
RELACOES = {"Lisboa": "de Lisboa", "Porto": "do Porto", "Coimbra": "de Coimbra",
            "Évora": "de Évora", "Evora": "de Évora", "Guimarães": "de Guimarães",
            "Guimaraes": "de Guimarães"}


def canon_comarca(texto):
    """Normaliza para o nome canónico da comarca (lista fechada de 23)."""
    t = texto.strip()
    for c in COMARCAS:
        if t == c or t.startswith(c + " ") or t.startswith(c + "-"):
            return c
    return t or None


def parse_place(raw):
    parts = [p.strip() for p in raw.split(">") if p.strip()]
    tribunal = parts[0] if parts else raw.strip()
    comarca, i_comarca = None, 0
    for i, p in enumerate(parts):
        m = re.match(r"TJ Comarca (?:d[aeo]s? )?(.+)", p)
        if m:
            comarca, i_comarca = canon_comarca(m.group(1)), i
            break
    if comarca is None:
        m = re.match(r"Tribunal da Relação d[aeo]s? ([A-Za-zÀ-ú]+)", tribunal)
        if m:
            comarca = "Relação " + RELACOES.get(m.group(1), "de " + m.group(1))
    resto = parts[i_comarca + 1:] if comarca else parts[1:]
    return {
        "texto": raw.strip(),
        "tribunal": tribunal or None,
        "comarca": comarca,
        "juizo": resto[0] if resto else None,
        "lugar": " > ".join(resto[1:]) if len(resto) > 1 else None,
    }


def norm(text):
    return re.sub(r"\s+", " ", text.replace("­", "-")).strip()


class Doc:
    def __init__(self, ano, override):
        self.ano = ano
        self.override = override
        self.seccao = override
        self.pos_ordem = 60
        self.started = False
        self.records = []
        self.rec = None

    def flush(self):
        r = self.rec
        if not r:
            return
        origem, notas_esq = [], []
        for part in r["left"]:
            if NOTAS_ESQ.match(part) and origem:
                notas_esq.append(re.sub(r"^-\s*", "", part))
            elif notas_esq:
                notas_esq.append(re.sub(r"^-\s*", "", part))
            else:
                origem.append(re.sub(r"^-\s*", "", part) if part.startswith("- ") else part)
        destino, motivo, tipo_lugar, pref, notas_dir = [], None, None, None, []
        for part in r["right"]:
            m = MOTIVO_RE.match(part)
            mi = MOTIVO_INV_RE.match(part) if not m else None
            if m and motivo is None:
                tipo_lugar, motivo = m.group(1), m.group(2)
                pref = int(m.group(3)) if m.group(3) else None
            elif mi and motivo is None:
                motivo, tipo_lugar = mi.group(1), mi.group(2)
                pref = int(mi.group(3)) if mi.group(3) else None
            elif motivo is None:
                destino.append(part)
            else:
                notas_dir.append(part)
        destino_txt = norm(" ".join(destino))
        if motivo is None:
            mt = re.match(
                r"^(?:\d+\s+)?(.*?Tribunal da Rela[çc][ãa]o d\S+(?: \S+)?)\s+"
                r"([A-ZÀ-Ú][a-zà-ú].+?)\s*\((\d+)\)$", destino_txt)
            if mt:
                destino = [mt.group(1)]
                motivo = mt.group(2)
                pref = int(mt.group(3))
        if motivo is None and notas_esq:
            motivo = re.sub(r"^-\s*", "", notas_esq[0])
        self.records.append({
            "ano": self.ano,
            "seccao": self.seccao,
            "codigo": r["codigo"],
            "nome": norm(r["nome"]),
            "classificacao": r["classificacao"],
            "antiguidade": r["antiguidade"],
            "ordem_raw": r["ordem_raw"],
            "origem": parse_place(norm(" ".join(origem))),
            "destino": parse_place(norm(" ".join(destino))),
            "tipo_lugar": tipo_lugar,
            "motivo": motivo,
            "preferencia": pref,
            "notas": [norm(n) for n in notas_esq + notas_dir if norm(n)],
        })
        self.rec = None

    def feed(self, line):
        line = line.replace("­", "-")
        if any(rx.search(line) for rx in FOOTER_RES):
            return
        sec = SECTION_RE.search(line)
        if sec:
            if not self.override:
                novo = "Relação" if "Relação" in sec.group(1) else "1.ª Instância"
                if novo != self.seccao:
                    self.flush()
                    self.seccao = novo
            return
        if HEADER_RE.search(line):
            i = line.find("N.º Ordem")
            if i == -1:
                i = line.find("N.º de Ordem")
            if i != -1:
                self.pos_ordem = i
            self.started = True
            return
        if not line.strip() or not self.started:
            return

        segs = segments(line)
        first = segs[0] if segs else None
        nm = NAME_RE.match(first[1]) if first and first[0] <= 15 else None
        resto = segs[1:]
        # variante 2014 (Relação): "779    - Nome" em dois segmentos
        if not nm and first and first[0] <= 15 and re.match(r"^\d{3,5}$", first[1]) \
                and len(segs) > 1 and segs[1][1].startswith("- "):
            nm = re.match(r"^(\d{3,5})()$", first[1])
            nome_2014 = segs[1][1][2:]
            resto = segs[2:]
        else:
            nome_2014 = None
        if nm and not re.match(r"^\d+\s*-\s*(Instância|Secção|Juízo)", first[1]):
            self.flush()
            self.rec = {
                "codigo": int(nm.group(1)), "nome": nome_2014 or nm.group(2),
                "classificacao": None, "antiguidade": None, "ordem_raw": None,
                "left": [], "right": [],
            }
            for s, t in resto:
                self.rec["right"].append(t)
            return
        if not self.rec:
            return
        for s, t in segs:
            if s > 15 and self.rec["ordem_raw"] is None:
                m3 = ORDEM_TRIPLA_RE.match(t)
                mc = ORDEM_CURSO_RE.match(t)
                if m3:
                    self.rec["classificacao"] = m3.group(1)
                    self.rec["antiguidade"] = int(m3.group(3))
                    self.rec["ordem_raw"] = t
                    continue
                if mc:
                    self.rec["antiguidade"] = int(mc.group(1))
                    self.rec["ordem_raw"] = t
                    continue
                if ORDEM_SIMPLES_RE.match(t) and abs(s - self.pos_ordem) <= 25:
                    self.rec["antiguidade"] = int(t)
                    self.rec["ordem_raw"] = t
                    continue
            if s <= 15:
                self.rec["left"].append(t)
            else:
                self.rec["right"].append(t)


def main():
    all_records = []
    for fname, ano, override, keep in FONTES:
        path = RAW / fname
        if not path.exists():
            print(f"AVISO: falta {fname}")
            continue
        doc = Doc(ano, override)
        for line in path.read_text(encoding="utf-8").splitlines():
            doc.feed(line)
        doc.flush()
        recs = [r for r in doc.records
                if (keep is None or r["seccao"] == keep)
                and not re.search(r"Graduad[oa]\(?a?\)?", r["nome"])]
        print(f"{fname:38s} {len(recs):4d} registos" + (f" (filtrado de {len(doc.records)})" if keep else ""))
        all_records.extend(recs)
    OUT.write_text(json.dumps(all_records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"TOTAL {len(all_records)} -> {OUT}")


if __name__ == "__main__":
    main()
