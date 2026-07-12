#!/usr/bin/env python3
"""Gera data/processed/mapa_portugal.json: contornos dos distritos projetados
para coordenadas SVG (continente + insets Açores/Madeira) e posições das sedes
das 23 comarcas, para o mapa de bolhas do dashboard."""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data/raw/portugal_distritos.geojson"
OUT = ROOT / "data/processed/mapa_portugal.json"

W, H = 340, 560  # viewBox do continente

# sedes das comarcas (lat, lon)
SEDES = {
    "Açores": (37.741, -25.675), "Aveiro": (40.641, -8.654), "Beja": (38.015, -7.863),
    "Braga": (41.545, -8.427), "Bragança": (41.806, -6.757), "Castelo Branco": (39.820, -7.492),
    "Coimbra": (40.211, -8.429), "Évora": (38.571, -7.913), "Faro": (37.019, -7.930),
    "Guarda": (40.537, -7.268), "Leiria": (39.744, -8.807), "Lisboa": (38.722, -9.139),
    "Lisboa Norte": (38.830, -9.169), "Lisboa Oeste": (38.801, -9.378),
    "Madeira": (32.650, -16.908), "Portalegre": (39.291, -7.428), "Porto": (41.150, -8.610),
    "Porto Este": (41.208, -8.283), "Santarém": (39.236, -8.686), "Setúbal": (38.526, -8.890),
    "Viana do Castelo": (41.694, -8.831), "Vila Real": (41.301, -7.742), "Viseu": (40.657, -7.914),
}
# relações (bolhas quadradas/anéis junto às sedes)
RELACOES = {
    "Relação de Lisboa": (38.722, -9.139), "Relação do Porto": (41.150, -8.610),
    "Relação de Coimbra": (40.211, -8.429), "Relação de Évora": (38.571, -7.913),
    "Relação de Guimarães": (41.444, -8.296),
}

# projeção equiretangular simples com correção de latitude média
def make_proj(lon0, lon1, lat0, lat1, x0, y0, w, h):
    k = math.cos(math.radians((lat0 + lat1) / 2))
    sx = w / ((lon1 - lon0) * k)
    sy = h / (lat1 - lat0)
    s = min(sx, sy)
    def proj(lon, lat):
        return (x0 + (lon - lon0) * k * s, y0 + (lat1 - lat) * s)
    return proj

CONT = make_proj(-9.60, -6.15, 36.90, 42.20, 6, 6, W - 12, H - 12)
# insets (caixas no canto inferior esquerdo)
ACORES = make_proj(-31.4, -24.9, 36.8, 39.9, 8, 388, 120, 78)
MADEIRA = make_proj(-17.35, -16.20, 32.55, 33.20, 8, 492, 62, 40)

INSET_BOXES = [
    {"x": 4, "y": 380, "w": 128, "h": 90, "label": "Açores"},
    {"x": 4, "y": 484, "w": 70, "h": 52, "label": "Madeira"},
]


def project_feature(name, geom):
    proj = ACORES if name == "Azores" else MADEIRA if name == "Madeira" else CONT
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    d = []
    for poly in polys:
        ring = poly[0]
        step = 2 if len(ring) > 120 else 1
        pts = ring[::step]
        if len(pts) < 4:
            continue
        d.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in
                                (proj(lon, lat) for lon, lat in pts)) + "Z")
    return "".join(d)


def main():
    g = json.loads(SRC.read_text())
    paths = []
    for f in g["features"]:
        name = f["properties"].get("name")
        d = project_feature(name, f["geometry"])
        if d:
            paths.append({"n": name, "d": d})
    sedes = {}
    for nome, (lat, lon) in SEDES.items():
        proj = ACORES if nome == "Açores" else MADEIRA if nome == "Madeira" else CONT
        x, y = proj(lon, lat)
        sedes[nome] = [round(x, 1), round(y, 1)]
    relacoes = {}
    for nome, (lat, lon) in RELACOES.items():
        x, y = CONT(lon, lat)
        relacoes[nome] = [round(x, 1), round(y, 1)]
    OUT.write_text(json.dumps({
        "w": W, "h": H, "paths": paths, "sedes": sedes,
        "relacoes": relacoes, "insets": INSET_BOXES,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{OUT} ({OUT.stat().st_size/1024:.0f} KiB, {len(paths)} contornos)")


if __name__ == "__main__":
    main()
