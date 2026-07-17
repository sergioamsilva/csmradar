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
    # entradas e saídas do SISTEMA (união STJ+Relação+1.ª instância+Geral):
    # entrada = primeira aparição do nome em qualquer quadro anual;
    # saída = última aparição (robusto a falhas de extração num ano isolado).
    from genero import fold as fold_nome
    # STJ excluído: os quadros do STJ têm falhas (2022 ausente, 2024-25
    # parciais) que geravam falsas "últimas aparições"
    anos_nome = {}
    for ano, nome in con.execute(
            """SELECT ano, nome FROM quadro_juizes
               WHERE instancia IN ('Relação', '1.ª Instância', 'Geral')"""):
        anos_nome.setdefault(fold_nome(nome), set()).add(ano)
    anos_q = sorted({a for s in anos_nome.values() for a in s})
    prim, ult = {}, {}
    for s in anos_nome.values():
        prim[min(s)] = prim.get(min(s), 0) + 1
        ult[max(s)] = ult.get(max(s), 0) + 1
    quadro_renov = []
    for i, a in enumerate(anos_q):
        total = sum(1 for s in anos_nome.values() if a in s)
        # fronteiras: entradas só a partir do 2.º ano com série contínua (2017+),
        # saídas até ao penúltimo ano
        novos = prim.get(a, 0) if a >= 2017 else None
        saidos = ult.get(a, 0) if 2016 <= a < anos_q[-1] else None
        quadro_renov.append([a, total, novos, saidos])
    comissoes = [list(r) for r in con.execute(
        """SELECT ano, COUNT(*) FROM quadro_juizes
           WHERE instancia IN ('Relação', 'STJ') AND notas LIKE '%omiss%'
           GROUP BY ano ORDER BY ano""")]

    mapa = json.loads((ROOT / "data/processed/mapa_portugal.json").read_text())
    # ---- demografia do sistema (agregados; nomes nunca saem daqui) ----
    genero_fold = {}
    ultima_comarca = {}
    for ano, nome, gen, grupo, inst in con.execute(
            """SELECT ano, nome, genero, grupo, instancia FROM quadro_juizes
               WHERE instancia IN ('Relação', '1.ª Instância', 'Geral')"""):
        f = fold_nome(nome)
        if gen and f not in genero_fold:
            genero_fold[f] = gen
        if inst == "1.ª Instância" and grupo:
            atual = ultima_comarca.get(f)
            if atual is None or ano >= atual[0]:
                ultima_comarca[f] = (ano, re.sub(r"^TJ Comarca (?:d[aeo]s? )?", "", grupo))

    primeira_mov = {}
    for ano, nome in con.execute("SELECT ano, nome FROM movimentos"):
        f = fold_nome(nome)
        if f not in primeira_mov or ano < primeira_mov[f]:
            primeira_mov[f] = ano

    ULTIMO_Q = anos_q[-1]
    primeira_vista, ultima_vista = {}, {}
    for f, s in anos_nome.items():
        primeira_vista[f] = min(min(s), primeira_mov.get(f, 9999))
        ultima_vista[f] = max(s)

    saidos = {f for f in anos_nome if 2016 <= ultima_vista[f] < ULTIMO_Q}
    ativos = {f for f in anos_nome if ultima_vista[f] == ULTIMO_Q}

    # género de quem entra vs quem sai, por ano
    renov_gen = []
    for a in range(2017, ULTIMO_Q + 1):
        novos = [f for f in anos_nome if min(anos_nome[f]) == a]
        sai = [f for f in anos_nome if ultima_vista[f] == a and a < ULTIMO_Q]
        def gf(grupo_):
            gs = [genero_fold.get(f) for f in grupo_]
            gs = [g for g in gs if g]
            return [sum(1 for g in gs if g == "F"), len(gs)]
        renov_gen.append([a] + gf(novos) + gf(sai))

    # duração de carreira observável à saída
    import statistics
    tenures = [ultima_vista[f] - primeira_vista[f] for f in saidos
               if primeira_vista[f] < 9999]
    buckets = [("<5", 0, 4), ("5–9", 5, 9), ("10–14", 10, 14), ("15–19", 15, 19), ("20+", 20, 99)]
    carreira_saida = {
        "med": round(statistics.median(tenures)) if tenures else None,
        "n": len(tenures),
        "hist": [[b[0], sum(1 for x in tenures if b[1] <= x <= b[2])] for b in buckets],
    }

    # anos observáveis de carreira até à promoção à Relação (2014+)
    anos_promo = []
    for ano, nome in con.execute(
            """SELECT ano, nome FROM movimentos
               WHERE instancia = 'Relação' AND motivo LIKE 'Promo%' AND ano >= 2014"""):
        f = fold_nome(nome)
        pv = primeira_vista.get(f, primeira_mov.get(f, 9999))
        if pv < 9999 and 0 < ano - pv <= 40:
            anos_promo.append(ano - pv)
    promo_anos = {
        "med": round(statistics.median(anos_promo)) if anos_promo else None,
        "n": len(anos_promo),
    }

    # taxa de saída por comarca (última comarca conhecida na 1.ª instância)
    saidas_com = {}
    for f in saidos:
        uc = ultima_comarca.get(f)
        if uc:
            saidas_com[uc[1]] = saidas_com.get(uc[1], 0) + 1
    quadro_medio = {}
    for grupo, media in con.execute(
            """SELECT REPLACE(grupo, 'TJ Comarca ', ''), COUNT(*) * 1.0 / COUNT(DISTINCT ano)
               FROM quadro_juizes WHERE instancia = '1.ª Instância' AND grupo IS NOT NULL
               GROUP BY 1 HAVING COUNT(DISTINCT ano) >= 5"""):
        quadro_medio[grupo] = media
    from parse_mjo_iudex import COMARCAS as COMARCAS_CANON
    n_anos_saida = ULTIMO_Q - 2016
    saidas_comarca = sorted(
        ([c, saidas_com[c], round(quadro_medio[c]),
          round(100 * saidas_com[c] / n_anos_saida / quadro_medio[c], 1)]
         for c in saidas_com
         if c in COMARCAS_CANON and quadro_medio.get(c, 0) >= 20),
        key=lambda x: -x[3])

    # projeção de saídas até 2030: ritmo médio dos últimos 5 anos completos
    coortes = [("20+ anos", 20, 99), ("15–19", 15, 19), ("10–14", 10, 14),
               ("5–9", 5, 9), ("<5", 0, 4)]
    ten_ativos = {f: ULTIMO_Q - primeira_vista[f] for f in ativos if primeira_vista[f] < 9999}
    saidas_por_ano = {a: sum(1 for f in saidos if ultima_vista[f] == a) for a in range(2016, ULTIMO_Q)}
    ult5 = [saidas_por_ano[a] for a in sorted(saidas_por_ano)[-5:]]
    media5 = sum(ult5) / len(ult5)
    projecao = {
        "coortes": [[c[0], sum(1 for v in ten_ativos.values() if c[1] <= v <= c[2])] for c in coortes],
        "media5": round(media5),
        "est2030": round(media5 * (2030 - ULTIMO_Q)),
        "ativos": len(ten_ativos),
    }

    # pipeline de entradas do CEJ: vagas para a magistratura JUDICIAL por
    # concurso (avisos DR) e ano previsto de colocação (aviso + ~3 anos,
    # calibrado: 34.º curso 48 vagas/2018 -> 42 colocações no MJO 2021;
    # 40.º curso 52 vagas/2023 -> 56 colocações no MJO 2026).
    # Fontes: Aviso 225/2023 (40.º: 52), Aviso 25126/2023 (41.º: 52),
    # Aviso 7191-B/2025 (42.º: 75), Aviso 1435-A/2026 (43.º: 79).
    cej_pipeline = [[2027, 52, "41.º curso"], [2028, 75, "42.º curso"], [2029, 79, "43.º curso"]]

    # série oficial de cessações (Relatório Anual do CSM de 2023, quadro
    # "Juízes que deixaram de exercer funções", anos civis, todas as causas)
    saidas_oficiais = [[2019, 34], [2020, 25], [2021, 64], [2022, 77], [2023, 55]]

    # ---- o gargalo do STJ: cenários de vagas no Supremo 2026-2038 ----
    # Modelo de cadeiras com pressupostos declarados no cartão: 70 lugares
    # (quadro STJ de 2023, último ano completo na BD); coorte instalada no
    # início de 2026 com idades uniformes 61-70 — calibra com o observado no
    # 18.º Concurso (17 posses em jul-2026 + ~10 anunciadas para set/out;
    # 30-40+ promoções esperadas até ago-2028); novos conselheiros entram
    # aos ~58 anos (Div. 109/2026 + relato de magistrado: maioria <60).
    # Até 2028 (concurso em curso) a saída dá-se aos 67 em ambos os cenários;
    # depois divergem: A mantém a saída à idade da aposentação (67),
    # B é a retenção até ao limite de idade (70).
    def simula_stj(limite_pos_2028):
        idades = [61 + i // 7 for i in range(70)]
        serie = []
        for ano in range(2026, 2039):
            limite = 67 if ano <= 2028 else limite_pos_2028
            saem = sum(1 for i in idades if i >= limite)
            idades = [i + 1 for i in idades if i < limite] + [59] * saem
            serie.append(saem)
        return serie

    # ---- idades estimadas (lista de antiguidade CSM, 31-12-2025) ----
    # idade = tempo de serviço na magistratura + idade típica de nomeação da
    # época de ingresso (âncoras: ~26 no início dos anos 80 — autocalibrado
    # pelo limite dos 70 —, ~34 hoje: auditores do CEJ entram aos ~31 + 2 anos
    # de curso; interpolação linear entre âncoras). Incerteza ±3-4 anos.
    # Conselheiros de entrada lateral (PGA/juristas, <20 anos de magistratura)
    # ficam de fora. Só agregados saem daqui (RGPD).
    ANCORAS = [(1982, 26.0), (1992, 28.0), (2002, 30.0), (2012, 32.0), (2022, 34.0)]

    def idade_nomeacao(ano):
        if ano <= ANCORAS[0][0]:
            return ANCORAS[0][1]
        if ano >= ANCORAS[-1][0]:
            return ANCORAS[-1][1]
        for (a0, v0), (a1, v1) in zip(ANCORAS, ANCORAS[1:]):
            if a0 <= ano <= a1:
                return v0 + (v1 - v0) * (ano - a0) / (a1 - a0)

    import math
    from collections import Counter
    piram = Counter()
    rel66, rel70 = Counter(), Counter()
    idades_cat = {}
    tem_antiguidade = con.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name = 'antiguidade'").fetchone()[0]
    idades_payload = None
    if tem_antiguidade:
        for cat, mag, gen in con.execute(
                """SELECT categoria, anos_magistratura, genero FROM antiguidade
                   WHERE ano_ref = 2025"""):
            if cat == "Juiz Conselheiro" and mag < 20:
                continue
            idade = idade_nomeacao(2026.0 - mag) + mag
            idades_cat.setdefault(cat, []).append(idade)
            piram[(min(65, int(idade // 5) * 5), gen)] += 1
            a66 = max(2026, 2026 + math.ceil(66 - idade))
            a70 = max(2026, 2026 + math.ceil(70 - idade))
            if a66 <= 2040:
                rel66[a66] += 1
            if a70 <= 2040:
                rel70[a70] += 1
        bandas = sorted(set(b for b, _ in piram))
        des = sorted(idades_cat["Juiz Desembargador"])
        idades_payload = {
            "piramide": [[("65+" if b == 65 else f"{b}–{b + 4}"),
                          piram[(b, "F")], piram[(b, "M")]] for b in bandas],
            "relogio": [[a, rel66[a], rel70[a]] for a in range(2026, 2041)],
            "med": {c: round(statistics.median(v)) for c, v in
                    (("cons", idades_cat["Juiz Conselheiro"]),
                     ("des", idades_cat["Juiz Desembargador"]),
                     ("jd", idades_cat["Juiz de Direito"]),
                     ("global", [x for v in idades_cat.values() for x in v]))},
            "des60": round(100 * sum(1 for x in des if x >= 60) / len(des)),
            "n": sum(len(v) for v in idades_cat.values()),
        }

    # ---- listas de antiguidade 2015-2025: saídas exatas, promoções datadas
    # e a fila para o Supremo (terço superior dos desembargadores) ----
    fila_payload = None
    if tem_antiguidade and idades_payload:
        pres = {}
        for ano_r, nome, cat, mag, gen, o in con.execute(
                """SELECT ano_ref, nome, categoria, anos_magistratura, genero, ord
                   FROM antiguidade"""):
            pres.setdefault(fold_nome(nome), {})[ano_r] = (cat, mag, gen, o)
        anos_l = sorted({a for d in pres.values() for a in d})
        ult_l = anos_l[-1]

        # saídas: presente a 31-12-Y, ausente das listas seguintes -> sai em Y+1
        saidas_l = {a: Counter() for a in range(anos_l[0] + 1, ult_l + 1)}
        for f, d in pres.items():
            u = max(d)
            if u < ult_l:
                saidas_l[u + 1][d[u][0]] += 1
        saidas_listas = [[a, sum(c.values()), c["Juiz Conselheiro"],
                          c["Juiz Desembargador"], c["Juiz de Direito"]]
                         for a, c in sorted(saidas_l.items())]

        # idade estimada à promoção (mudança de categoria entre listas anuais)
        p_stj, p_rel = {}, {}
        for f, d in pres.items():
            ss = sorted(d)
            for a0, a1 in zip(ss, ss[1:]):
                c0, c1 = d[a0][0], d[a1][0]
                idade_p = idade_nomeacao(a1 + 1.0 - d[a1][1]) + d[a1][1]
                if c0 == "Juiz Desembargador" and c1 == "Juiz Conselheiro":
                    p_stj.setdefault(a1, []).append(idade_p)
                elif c0 == "Juiz de Direito" and c1 == "Juiz Desembargador":
                    p_rel.setdefault(a1, []).append(idade_p)
        promo_idade = []
        for a in range(anos_l[0] + 1, ult_l + 1):
            promo_idade.append([
                a,
                round(statistics.median(p_stj[a]), 1) if a in p_stj else None, len(p_stj.get(a, [])),
                round(statistics.median(p_rel[a]), 1) if a in p_rel else None, len(p_rel.get(a, []))])

        # a fila: terço superior da lista de 2025
        des_fila = con.execute(
            """SELECT genero, anos_categoria, anos_magistratura FROM antiguidade
               WHERE ano_ref = 2025 AND categoria = 'Juiz Desembargador'
               ORDER BY ord""").fetchall()
        n3 = len(des_fila) // 3
        fila, resto = des_fila[:n3], des_fila[n3:]
        id_fila = sorted(idade_nomeacao(2026.0 - m) + m for _, _, m in fila)
        fila_payload = {
            "n": n3, "nDes": len(des_fila),
            "medIdade": round(statistics.median(id_fila)),
            "minIdade": round(id_fila[0]), "maxIdade": round(id_fila[-1]),
            "pctFfila": round(100 * sum(1 for g, _, _ in fila if g == "F") / n3),
            "pctFresto": round(100 * sum(1 for g, _, _ in resto if g == "F") / len(resto)),
            "medCat": round(statistics.median([c for _, c, _ in fila])),
            "promoIdade": promo_idade,
            "saidasListas": saidas_listas,
            "nPromoSTJ": sum(len(v) for v in p_stj.values()),
            "nPromoRel": sum(len(v) for v in p_rel.values()),
        }

    promo_rel = [n for (n,) in con.execute(
        """SELECT COUNT(*) FROM movimentos
           WHERE instancia = 'Relação' AND motivo LIKE 'Promo%' AND ano >= 2015
           GROUP BY ano""")]
    gargalo = {"anos": list(range(2026, 2039)),
               "cenA": simula_stj(67), "cenB": simula_stj(70),
               "promoRelMedia": round(sum(promo_rel) / len(promo_rel))}
    payload = json.dumps({"recs": recs, "quadroGen": quadro_gen, "mapa": mapa,
                          "quadroRenov": quadro_renov, "comissoes": comissoes,
                          "saidasOficiais": saidas_oficiais, "renovGen": renov_gen,
                          "cejPipeline": cej_pipeline,
                          "carreiraSaida": carreira_saida, "promoAnos": promo_anos,
                          "saidasComarca": saidas_comarca, "projecao": projecao,
                          "gargalo": gargalo, "idades": idades_payload,
                          "fila": fila_payload},
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
