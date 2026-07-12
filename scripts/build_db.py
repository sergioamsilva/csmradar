#!/usr/bin/env python3
"""Constrói data/csmradar.db a partir dos JSON processados.

Tabelas:
  documentos    — todos os PDFs descarregados do CSM (fonte de cada dado)
  movimentos    — uma linha por colocação nos MJO 2014–2026
  quadro_juizes — uma linha por lugar nos quadros de juízes 2014–2026

Vistas: v_fluxos (fluxos entre comarcas por ano), v_resumo_ano.
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from genero import inferir_genero

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data/csmradar.db"

SCHEMA = """
PRAGMA journal_mode = WAL;

DROP TABLE IF EXISTS documentos;
CREATE TABLE documentos (
  id        INTEGER PRIMARY KEY,
  categoria TEXT NOT NULL CHECK (categoria IN ('movimento', 'quadro')),
  ano       INTEGER NOT NULL,
  tipo      TEXT NOT NULL,
  url       TEXT NOT NULL,
  ficheiro  TEXT NOT NULL
);

DROP TABLE IF EXISTS movimentos;
CREATE TABLE movimentos (
  id              INTEGER PRIMARY KEY,
  ano             INTEGER NOT NULL,
  instancia       TEXT NOT NULL,          -- 'Relação' | '1.ª Instância'
  seccao          TEXT,                   -- secção original no documento
  codigo          INTEGER,                -- código de magistrado (quando existe)
  nome            TEXT NOT NULL,
  genero          TEXT,                   -- F/M inferido do nome próprio
  classificacao   TEXT,                   -- MB, BD, B, S, M; P/N = sem classificação
  antiguidade     INTEGER,                -- n.º de ordem na lista de antiguidade
  origem          TEXT,
  origem_tribunal TEXT,
  origem_comarca  TEXT,
  origem_juizo    TEXT,
  origem_lugar    TEXT,
  destino         TEXT,
  destino_tribunal TEXT,
  destino_comarca TEXT,
  destino_juizo   TEXT,
  destino_lugar   TEXT,
  tipo_lugar      TEXT,                   -- Efectivo / Auxiliar / ...
  motivo          TEXT,                   -- Transferência, Promoção, 1º Acesso, ...
  preferencia     INTEGER,                -- n.º do pedido satisfeito
  notas           TEXT                    -- JSON com notas adicionais
);
CREATE INDEX idx_mov_ano ON movimentos (ano);
CREATE INDEX idx_mov_nome ON movimentos (nome);
CREATE INDEX idx_mov_comarcas ON movimentos (origem_comarca, destino_comarca);

DROP TABLE IF EXISTS quadro_juizes;
CREATE TABLE quadro_juizes (
  id        INTEGER PRIMARY KEY,
  ano       INTEGER NOT NULL,
  instancia TEXT NOT NULL,                -- STJ | Relação | 1.ª Instância | Bolsa/QCJ | Geral
  grupo     TEXT,                         -- comarca / tribunal / relação
  unidade   TEXT,                         -- juízo / secção
  lugar     TEXT,                         -- Juiz 1, Lugar de Efectivo, ...
  nome      TEXT NOT NULL,
  genero    TEXT,
  notas     TEXT                          -- comissões de serviço, ausências, ...
);
CREATE INDEX idx_qj_ano ON quadro_juizes (ano);
CREATE INDEX idx_qj_nome ON quadro_juizes (nome);

DROP VIEW IF EXISTS v_fluxos;
CREATE VIEW v_fluxos AS
SELECT ano, origem_comarca, destino_comarca, COUNT(*) AS n
FROM movimentos
WHERE origem_comarca IS NOT NULL AND destino_comarca IS NOT NULL
  AND origem_comarca <> destino_comarca
GROUP BY ano, origem_comarca, destino_comarca;

DROP VIEW IF EXISTS v_resumo_ano;
CREATE VIEW v_resumo_ano AS
SELECT ano,
       COUNT(*)                                            AS movimentados,
       SUM(instancia = 'Relação')                          AS na_relacao,
       SUM(preferencia = 1)                                AS pref_1,
       SUM(preferencia IS NOT NULL)                        AS com_preferencia,
       SUM(origem_comarca IS NOT NULL
           AND destino_comarca IS NOT NULL
           AND origem_comarca <> destino_comarca)          AS mudam_comarca
FROM movimentos
GROUP BY ano;
"""


def place_cols(prefix, place):
    return {
        prefix: place.get("texto") or None,
        f"{prefix}_tribunal": place.get("tribunal"),
        f"{prefix}_comarca": place.get("comarca"),
        f"{prefix}_juizo": place.get("juizo"),
        f"{prefix}_lugar": place.get("lugar"),
    }


def main():
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)

    # documentos
    docs = []
    for categoria, sub in (("movimento", "movimentos"), ("quadro", "quadros")):
        prefixo = "mjo" if categoria == "movimento" else "quadro"
        for line in (ROOT / f"data/raw/{sub}/manifest.tsv").read_text().strip().splitlines():
            ano, tipo, url = line.split("\t")
            ext = url.rsplit(".", 1)[-1]
            docs.append((categoria, int(ano), tipo, url, f"data/raw/{sub}/{prefixo}_{ano}_{tipo}.{ext}"))
    con.executemany(
        "INSERT INTO documentos (categoria, ano, tipo, url, ficheiro) VALUES (?,?,?,?,?)", docs)

    # movimentos 2014–2025 (iudex)
    rows = []
    for r in json.loads((ROOT / "data/processed/movimentos_2014_2025.json").read_text()):
        instancia = "Relação" if r["seccao"].startswith("Relação") else "1.ª Instância"
        row = {
            "ano": r["ano"], "instancia": instancia, "seccao": r["seccao"],
            "codigo": r["codigo"], "nome": r["nome"], "genero": inferir_genero(r["nome"]),
            "classificacao": r["classificacao"], "antiguidade": r["antiguidade"],
            "tipo_lugar": r["tipo_lugar"], "motivo": r["motivo"],
            "preferencia": r["preferencia"],
            "notas": json.dumps(r["notas"], ensure_ascii=False) if r["notas"] else None,
        }
        row.update(place_cols("origem", r["origem"]))
        row.update(place_cols("destino", r["destino"]))
        rows.append(row)

    # movimentos 2004–2013 (formatos antigos)
    RELS = ("Lisboa", "Porto", "Coimbra", "Évora", "Guimarães")

    def comarca_antiga(texto, seccao):
        if not texto:
            return None
        m2 = re.search(r"Tribunal da Rela[çc][ãa]o d[aeo]s? (\w+)", texto)
        if m2 and m2.group(1) in RELS:
            lig = "do" if m2.group(1) == "Porto" else "de"
            return f"Relação {lig} {m2.group(1)}"
        if seccao == "Relação":
            m3 = re.match(r"^([A-ZÀ-Ú][a-zà-ú]+(?: [A-ZÀ-Ú][a-zà-ú]+)?)\b", texto)
            if m3 and m3.group(1) in RELS:
                lig = "do" if m3.group(1) == "Porto" else "de"
                return f"Relação {lig} {m3.group(1)}"
        return None

    for r in json.loads((ROOT / "data/processed/movimentos_2004_2013.json").read_text()):
        instancia = "Relação" if r["seccao"] == "Relação" else "1.ª Instância"
        row = {
            "ano": r["ano"], "instancia": instancia, "seccao": r["seccao"],
            "codigo": r.get("codigo"), "nome": r["nome"],
            "genero": r.get("genero_hint") or inferir_genero(r["nome"]),
            "classificacao": r.get("classificacao"), "antiguidade": r.get("antiguidade"),
            "tipo_lugar": None, "motivo": r.get("motivo"),
            "preferencia": r.get("preferencia"), "notas": None,
            "origem": r.get("origem"), "origem_tribunal": None,
            "origem_comarca": comarca_antiga(r.get("origem"), r["seccao"]),
            "origem_juizo": None, "origem_lugar": None,
            "destino": r.get("destino"), "destino_tribunal": None,
            "destino_comarca": comarca_antiga(r.get("destino"), r["seccao"]),
            "destino_juizo": None, "destino_lugar": None,
        }
        rows.append(row)

    # movimentos 2026 (formato novo)
    for r in json.loads((ROOT / "data/processed/movimentos_2026.json").read_text()):
        instancia = "Relação" if r["seccao"] == "Relação" else "1.ª Instância"
        row = {
            "ano": 2026, "instancia": instancia, "seccao": r["seccao"],
            "codigo": None, "nome": r["nome"], "genero": inferir_genero(r["nome"]),
            "classificacao": r["classificacao"], "antiguidade": r["antiguidade"],
            "tipo_lugar": None, "motivo": r["motivos"][0] if r["motivos"] else None,
            "preferencia": r["preferencia"],
            "notas": json.dumps(r["motivos"], ensure_ascii=False) if r["motivos"] else None,
        }
        row.update(place_cols("origem", r["origem"]))
        row.update(place_cols("destino", r["destino"]))
        rows.append(row)

    cols = list(rows[0].keys())
    con.executemany(
        f"INSERT INTO movimentos ({','.join(cols)}) VALUES ({','.join(':' + c for c in cols)})",
        rows)

    # quadros de juízes
    qj = json.loads((ROOT / "data/processed/quadro_juizes.json").read_text())
    for row in qj:
        row["genero"] = inferir_genero(row["nome"])
    con.executemany(
        "INSERT INTO quadro_juizes (ano, instancia, grupo, unidade, lugar, nome, genero, notas) "
        "VALUES (:ano, :instancia, :grupo, :unidade, :lugar, :nome, :genero, :notas)", qj)

    con.commit()
    for tabela in ("documentos", "movimentos", "quadro_juizes"):
        n = con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        print(f"{tabela:14s} {n:6d} linhas")
    print("\nv_resumo_ano:")
    for row in con.execute("SELECT * FROM v_resumo_ano ORDER BY ano"):
        print("  ", row)
    con.close()
    print(f"\nBase de dados: {DB} ({DB.stat().st_size/1024:.0f} KiB)")


if __name__ == "__main__":
    main()
