#!/usr/bin/env python3
"""Gera dist/index.html: dashboard multi-ano alimentado por data/csmradar.db.

Embebe um payload compacto (arrays) com uma linha por colocação:
  [ano, instancia(0=1.ª/1=Relação), nome, classificacao, antiguidade,
   origem, origem_comarca, destino, destino_comarca, motivo, preferencia]
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from math import asin, cos, radians, sin, sqrt

from build_mapa import RELACOES as RELACOES_GEO
from build_mapa import SEDES

COORDS = dict(SEDES)
COORDS.update(RELACOES_GEO)


def dist_km(c1, c2):
    if c1 not in COORDS or c2 not in COORDS:
        return None
    (la1, lo1), (la2, lo2) = COORDS[c1], COORDS[c2]
    la1, lo1, la2, lo2 = map(radians, (la1, lo1, la2, lo2))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return round(12742 * asin(sqrt(h)))


PRECARIO_MOTIVO = {"Interino", "Destacamento", "Renovação"}

MOTIVOS = [
    (re.compile(r"^Transfer", re.I), "Transferência"),
    (re.compile(r"^Promo[çc]", re.I), "Promoção"),
    (re.compile(r"^(1º Acesso|Primeiro Acesso)", re.I), "1.º acesso"),
    (re.compile(r"Renova[çc][ãa]o", re.I), "Renovação"),
    (re.compile(r"^Destacamento", re.I), "Destacamento"),
    (re.compile(r"Comiss[ãa]o de Servi[çc]o", re.I), "Comissão de serviço"),
    (re.compile(r"^Interino", re.I), "Interino"),
    (re.compile(r"^Permuta", re.I), "Permuta"),
    (re.compile(r"^Nomea[çc]", re.I), "Nomeação"),
    (re.compile(r"^Requerimento", re.I), "Requerimento"),
    (re.compile(r"^(Coloca[çc]|Vaga Origin)", re.I), "Colocação"),
]


def norm_motivo(m):
    if not m:
        return None
    m = re.sub(r"^Vaga d[oe] \d+\s*-\s*", "", m)
    if re.match(r"^Auxiliares?$", m, re.I):
        return "Colocação"
    for rx, canon in MOTIVOS:
        if rx.search(m):
            return canon
    return "Outro"


_PSEUDO = {}


def pseud(nome):
    """RGPD: o payload publicado não contém nomes — só IDs opacos estáveis
    dentro do ficheiro, para as agregações de carreira."""
    if nome not in _PSEUDO:
        _PSEUDO[nome] = "J" + str(len(_PSEUDO) + 1)
    return _PSEUDO[nome]


def main():
    con = sqlite3.connect(ROOT / "data/csmradar.db")
    recs = []
    for (ano, inst, nome, gen, cls, ant, o, oc, d, dc, motivo, pref, tl) in con.execute(
        """SELECT ano, instancia, nome, genero, classificacao, antiguidade,
                  origem, origem_comarca, destino, destino_comarca, motivo, preferencia,
                  tipo_lugar
           FROM movimentos ORDER BY ano, nome"""):
        mot = norm_motivo(motivo)
        prec = 1 if (mot in PRECARIO_MOTIVO
                     or (tl and tl.startswith("Auxiliar"))
                     or "Auxiliar" in (d or "")) else 0
        recs.append([
            ano, 1 if inst == "Relação" else 0, pseud(nome), cls, ant,
            o or "", oc, d or "", dc, mot, pref, gen,
            dist_km(oc, dc) if (oc and dc and oc != dc) else None, prec,
        ])
    # % de mulheres nos quadros anuais, por instância
    quadro_gen = [list(r) for r in con.execute(
        """SELECT ano, instancia, SUM(genero IS NOT NULL), SUM(genero = 'F')
           FROM quadro_juizes
           WHERE instancia IN ('STJ', 'Relação', '1.ª Instância')
           GROUP BY ano, instancia HAVING SUM(genero IS NOT NULL) >= 40
           ORDER BY ano""")]
    # renovação do corpo (quadros da 1.ª instância, série completa 2016-2025)
    por_ano = {}
    for ano, nome in con.execute(
            "SELECT ano, nome FROM quadro_juizes WHERE instancia = '1.ª Instância'"):
        por_ano.setdefault(ano, set()).add(nome)
    anos_q = sorted(por_ano)
    quadro_renov = []
    for i, a in enumerate(anos_q):
        atual = por_ano[a]
        prev = por_ano[anos_q[i - 1]] if i else None
        prox = por_ano[anos_q[i + 1]] if i + 1 < len(anos_q) else None
        quadro_renov.append([
            a, len(atual),
            len(atual - prev) if prev is not None else None,
            len(atual - prox) if prox is not None else None,
        ])
    comissoes = [list(r) for r in con.execute(
        """SELECT ano, COUNT(*) FROM quadro_juizes
           WHERE instancia IN ('Relação', 'STJ') AND notas LIKE '%omiss%'
           GROUP BY ano ORDER BY ano""")]

    mapa = json.loads((ROOT / "data/processed/mapa_portugal.json").read_text())
    payload = json.dumps({"recs": recs, "quadroGen": quadro_gen, "mapa": mapa,
                          "quadroRenov": quadro_renov, "comissoes": comissoes},
                         ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")

    template = (ROOT / "web/template.html").read_text(encoding="utf-8")
    if "__DATA_JSON__" not in template:
        sys.exit("placeholder __DATA_JSON__ não encontrado no template")
    html = template.replace("__DATA_JSON__", payload)

    out = ROOT / "dist/index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"{out} ({out.stat().st_size / 1024 / 1024:.2f} MiB, {len(recs)} colocações)")


if __name__ == "__main__":
    main()
