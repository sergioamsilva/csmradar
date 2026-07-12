#!/usr/bin/env python3
"""Parser do Movimento Judicial Ordinário (MJO) do CSM.

Lê o texto extraído com `pdftotext -layout` de uma divulgação de movimento
judicial (versão consolidada) e produz JSON estruturado com um registo por
juiz movimentado.

O PDF usa ícones FontAwesome (caracteres na Private Use Area) como
marcadores semânticos, o que torna o parsing determinístico:
   classificação ·  antiguidade/preferência ·  total de
  movimentados · restantes ícones antecedem motivos/notas (transferência,
  comissão de serviço, vaga originária, ...).
"""

import json
import re
import sys
from pathlib import Path

PUA = "-"
PUA_RE = re.compile(f"[{PUA}]")

FOOTER_PATTERNS = [
    re.compile(r"^\s*Página \d+ de \d+\s*$"),
    re.compile(r"Rua Duque de Palmela"),
    re.compile(r"Tel\. 213 220 020"),
    re.compile(r"E-mail: csm@csm\.org\.pt"),
    re.compile(r"^\s*(CSM )?MJO[- ]\d{8,}"),
    re.compile(r"^\s*Documento gerado em(?!.*Movimentados)"),
]

SECTION_RE = re.compile(r"^\s*MJO (\d{4}):\s*(.*)$")
MOVIMENTADOS_RE = re.compile(rf"[{PUA}]\s*Movimentados:\s*(\d+)")
HEADER_RE = re.compile(r"COLOCAÇÃO ATIVA\s+.*?(COLOCAÇÃO MJO)")
NAME_RE = re.compile(
    rf"^(?P<nome>.+?)"
    rf"(?:\s*\s*(?P<classif>[A-Z]{{1,2}}))?"
    rf"(?:\s*\s*(?P<antig>\d+)º)?\s*$"
)


def despace_smallcaps(text: str) -> str:
    """'C ristina M aria' -> 'Cristina Maria' (artefacto das versaletes)."""
    return re.sub(r"\b([A-ZÀ-ÖØ-Þ]) (?=[A-Za-zÀ-ÖØ-Þà-öø-ÿ])", r"\1", text)


def is_footer(line: str) -> bool:
    return any(p.search(line) for p in FOOTER_PATTERNS)


def segments(line: str):
    """Blocos de texto separados por 2+ espaços, com posição inicial."""
    return [(m.start(), m.group()) for m in re.finditer(r"\S(?:.{0,1}\S)*", line)]


# grafias inconsistentes no PDF (com e sem acento)
SPELLING_FIXES = [
    (re.compile(r"\bGuimaraes\b"), "Guimarães"),
    (re.compile(r"\bEvora\b"), "Évora"),
]


def fix_spelling(text: str) -> str:
    for rx, repl in SPELLING_FIXES:
        text = rx.sub(repl, text)
    return text


def parse_place(raw: str) -> dict:
    raw = fix_spelling(raw)
    parts = [p.strip() for p in raw.split(">") if p.strip()]
    tribunal = parts[0] if parts else raw.strip()
    comarca = None
    m = re.match(r"TJ Comarca (.+)", tribunal)
    if m:
        comarca = m.group(1).strip()
    elif tribunal.startswith("Tribunal da Relação"):
        comarca = re.sub(r"^Tribunal da (Relação (?:de |do |dos )?)", r"\1", tribunal)
    return {
        "texto": raw.strip(),
        "tribunal": tribunal,
        "comarca": comarca,
        "juizo": parts[1] if len(parts) > 1 else None,
        "lugar": " > ".join(parts[2:]) if len(parts) > 2 else None,
    }


def parse_motivo_line(stripped: str):
    """Divide uma linha de motivos pelos ícones; devolve lista de tokens."""
    tokens = [despace_smallcaps(t.strip()) for t in PUA_RE.split(stripped) if t.strip()]
    return [t for t in tokens if not re.match(r"^Fim do Documento$", t, re.I)]


def flush(record, records):
    if not record:
        return
    origem = re.sub(r"\s+", " ", " ".join(record["origem_lines"])).strip()
    destino = re.sub(r"\s+", " ", " ".join(record["destino_lines"])).strip()
    preferencia = None
    motivos = []
    for tok in record["motivo_tokens"]:
        pm = re.match(r"^#(\d+)$", tok)
        if pm:
            # 999999 é o código interno para "Colocação Obrigatória"
            preferencia = int(pm.group(1)) if pm.group(1) != "999999" else None
        else:
            motivos.append(tok)
    records.append({
        "seccao": record["seccao"],
        "nome": record["nome"],
        "classificacao": record["classificacao"],
        "antiguidade": record["antiguidade"],
        "origem": parse_place(origem),
        "destino": parse_place(destino),
        "preferencia": preferencia,
        "motivos": motivos,
    })


def parse(lines):
    records = []
    section = None
    record = None
    pending_name = None
    state = "idle"  # idle | colocacao | after

    for line in lines:
        sec = SECTION_RE.match(line)
        if sec:
            flush(record, records)
            record, pending_name, state = None, None, "idle"
            rest = despace_smallcaps(PUA_RE.sub("", sec.group(2)))
            name = re.split(r"\s{2,}|", rest)[0].strip()
            mv = MOVIMENTADOS_RE.search(line)
            section = {
                "ano": int(sec.group(1)),
                "nome": name,
                "declarados": int(mv.group(1)) if mv else None,
            }
            continue
        if section and section["declarados"] is None:
            mv = MOVIMENTADOS_RE.search(line)
            if mv:
                section["declarados"] = int(mv.group(1))
                continue
        if is_footer(line):
            continue
        stripped = line.strip()
        if not stripped:
            if state == "colocacao" and record and record["destino_lines"]:
                state = "after"
            continue

        hdr = HEADER_RE.search(line)
        if hdr:
            flush(record, records)
            nome, classif, antig = None, None, None
            if pending_name:
                nm = NAME_RE.match(pending_name)
                nome = despace_smallcaps(nm.group("nome").strip())
                classif = nm.group("classif")
                antig = int(nm.group("antig")) if nm.group("antig") else None
            record = {
                "seccao": section["nome"] if section else None,
                "nome": nome,
                "classificacao": classif,
                "antiguidade": antig,
                "split": hdr.start(1),
                "origem_lines": [],
                "destino_lines": [],
                "motivo_tokens": [],
            }
            pending_name = None
            state = "colocacao"
            continue

        if PUA_RE.match(stripped):  # linha de motivo (começa com ícone)
            if record:
                record["motivo_tokens"].extend(parse_motivo_line(stripped))
                state = "after"
            continue

        if record and state == "colocacao":
            split = record["split"]
            left = " ".join(t for s, t in segments(line) if s < split - 1)
            right = " ".join(t for s, t in segments(line) if s >= split - 1)
            # motivos inline na mesma linha física (antecedidos por ícone)
            for side in ("left", "right"):
                text = left if side == "left" else right
                m = PUA_RE.search(text)
                if m:
                    record["motivo_tokens"].extend(parse_motivo_line(text[m.start():]))
                    text = text[: m.start()].strip()
                    if side == "left":
                        left = text
                    else:
                        right = text
            if left:
                record["origem_lines"].append(left)
            if right:
                record["destino_lines"].append(right)
            continue

        # estado idle/after: linha de texto simples = candidata a nome
        indent = len(line) - len(line.lstrip())
        if indent <= 10:
            pending_name = stripped
        elif record and record["motivo_tokens"]:
            # continuação de um motivo com quebra de linha
            record["motivo_tokens"][-1] += " " + stripped

    flush(record, records)
    return records


def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw/div_111_2026.txt")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "data/processed/movimentos_2026.json")
    lines = src.read_text(encoding="utf-8").splitlines()
    records = parse(lines)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter
    por_seccao = Counter(r["seccao"] for r in records)
    print(f"{len(records)} registos extraídos")
    for sec, n in por_seccao.items():
        print(f"  {sec}: {n}")


if __name__ == "__main__":
    main()
