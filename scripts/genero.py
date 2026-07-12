#!/usr/bin/env python3
"""Inferência de género a partir do primeiro nome próprio (português).

Regras: primeiro token do nome; terminação em -a => F, listas explícitas para
os restantes. Devolve 'F', 'M' ou None (indeterminado). A precisão é elevada
nos nomes próprios portugueses convencionais; casos não cobertos ficam None
e são excluídos das percentagens.
"""

import re
import unicodedata

MASCULINOS = {
    "abel", "abilio", "adelino", "adriano", "afonso", "agostinho", "alberto",
    "albano", "alcides", "alexandre", "alfredo", "alipio", "alvaro", "amadeu",
    "americo", "amilcar", "andre", "anibal", "antonio", "antero", "aquilino",
    "armando", "armenio", "arnaldo", "arlindo", "artur", "augusto", "aurelio",
    "baltasar", "belmiro", "benjamim", "bernardino", "bernardo", "bruno",
    "camilo", "candido", "carlos", "casimiro", "celso", "cesar", "claudio",
    "cristiano", "cristovao", "custodio", "daniel", "david", "diamantino",
    "dinis", "diogo", "domingos", "duarte", "edgar", "edmundo", "eduardo",
    "elias", "eliseu", "emanuel", "emidio", "ernesto", "eugenio", "eurico",
    "evaristo", "ezequiel", "fabio", "fausto", "feliciano", "fernando",
    "fernao", "filipe", "firmino", "flavio", "francisco", "frederico",
    "gabriel", "gaspar", "gastao", "gil", "gilberto", "gonçalo", "goncalo",
    "gregorio", "guilherme", "gustavo", "heitor", "helder", "helio",
    "henrique", "herculano", "herminio", "hernani", "hilario", "horacio",
    "hugo", "humberto", "ilidio", "inacio", "isaias", "ivan", "ivo", "jacinto",
    "jaime", "jeronimo", "joao", "joaquim", "joel", "jorge", "jose", "josue",
    "julio", "juliano", "justino", "laurindo", "lauro", "leandro", "leonardo",
    "leonel", "lino", "lourenço", "lourenco", "lucas", "luciano", "lucio",
    "ludgero", "luis", "manuel", "marcelino", "marcelo", "marco", "marcos",
    "mario", "martim", "martinho", "mateus", "matias", "mauricio", "mauro",
    "maximiano", "micael", "michael", "miguel", "moises", "narciso", "nelson",
    "nicolau", "norberto", "nuno", "octavio", "olegario", "olimpio", "orlando",
    "oscar", "osvaldo", "patricio", "paulo", "pedro", "plinio", "quirino",
    "rafael", "raimundo", "ramiro", "raul", "reinaldo", "renato", "ricardo",
    "roberto", "rodolfo", "rodrigo", "rogerio", "rolando", "romao", "romeu",
    "ronaldo", "ruben", "rui", "salvador", "samuel", "sandro", "santiago",
    "saul", "sebastiao", "serafim", "sergio", "silvano", "silverio", "silvino",
    "silvio", "simao", "telmo", "teodoro", "tiago", "tomas", "tome", "ulisses",
    "urbano", "valdemar", "valentim", "valter", "vasco", "vicente", "victor",
    "virgilio", "vitor", "vitorino", "vladimiro", "xavier", "grumecindo",
    "adelio", "adolfo", "aires", "aleixo", "anselmo", "argemiro", "aristides",
    "arsenio", "atilio", "avelino", "belarmino", "bento", "boaventura",
    "caetano", "calisto", "celestino", "cirilo", "clemente", "conrado",
    "cosme", "damiao", "delfim", "dionisio", "efigenio", "elio", "eloi",
    "estevao", "faustino", "felix", "florencio", "fortunato", "fructuoso",
    "frutuoso", "gervasio", "gino", "godofredo", "hermes", "higino",
    "hipolito", "honorio", "jonas", "juvenal", "ladislau", "laurentino",
    "lazaro", "libanio", "liberto", "lucilio", "marciano", "marinho",
    "maximino", "medeiros", "nemesio", "nestor", "otelo", "ovidio",
    "paulino", "policarpo", "porfirio", "primo", "prudencio", "querubim",
    "remigio", "ricardino", "rosendo", "rufino", "sabino", "salustiano",
    "saturnino", "severino", "sidonio", "teofilo", "tercio", "timoteo",
    "tobias", "valerio", "venancio", "veridiano", "virgolino", "zacarias",
}
FEMININOS_SEM_A = {
    "ines", "isabel", "beatriz", "conceiçao", "conceicao", "dores", "lurdes",
    "luz", "ceu", "raquel", "ester", "esther", "carmen", "carmem", "merces",
    "solange", "ivone", "alice", "berenice", "eunice", "clarice", "doriceu",
    "filomene", "irene", "matilde", "cremilde", "clotilde", "deolinda",
    "salome", "noemi", "judite", "edite", "odete", "arlete", "iolande",
    "belmire", "rosalinde", "leonor", "flor", "guiomar", "piedade",
    "trindade", "natividade", "soledade", "caridade", "cidalia", "miriam",
    "iris", "liz", "mercedes", "nazare", "remedios", "rute", "ruth",
    "consolaçao", "consolacao", "encarnaçao", "encarnacao", "assunçao",
    "assuncao", "anunciaçao", "anunciacao", "visitaçao", "visitacao",
    "elisabete", "elizabete", "elisabeth", "elizabeth", "marlene", "celeste",
    "hortense", "celine", "goreti", "gorete", "milene", "lisete", "nelly",
    "adelaide", "marily", "marisol", "karin", "karen", "ingrid", "yvette",
    "yvonne", "aldegundes", "mafalda" , "gisele", "giselle", "michele",
    "michelle", "nicole", "denise", "simone", "jacqueline", "doris",
    "clarisse", "susete", "dulce", "melanie", "karolen", "tayoane", "anizabel",
    "ascensao", "suzete", "marize", "maribel", "jenny", "vivien", "haydee",
}
MASCULINOS_EM_A = {"luca", "jonatha", "elia", "barnabe"}
MASCULINOS.update({"william", "fabien", "adeodato", "brazilino", "noe", "geraldo", "aderito", "leonidas", "menezes", "salazar", "aparicio", "eleuterio", "juvencio", "olavo", "onofre", "ottomar", "abraao", "izidoro", "isidoro", "acacio", "vidal"})


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if not unicodedata.combining(c))


def inferir_genero(nome):
    """'F', 'M' ou None a partir do nome completo."""
    if not nome:
        return None
    primeiro = fold(re.split(r"[\s\-]+", nome.strip())[0])
    if not primeiro or not primeiro.isalpha():
        return None
    if primeiro in MASCULINOS or primeiro in MASCULINOS_EM_A:
        return "M"
    if primeiro in FEMININOS_SEM_A:
        return "F"
    if primeiro.endswith("a"):
        return "F"
    if primeiro.endswith("o") and primeiro not in {"rosario", "sacramento"}:
        return "M"
    return None


if __name__ == "__main__":
    import json
    import sys
    from collections import Counter
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    recs = json.loads((root / "data/processed/movimentos_2014_2025.json").read_text())
    c = Counter(inferir_genero(r["nome"]) for r in recs)
    print("movimentos:", dict(c), f"({100*c[None]/len(recs):.1f}% indeterminados)")
    desconhecidos = Counter()
    for r in recs:
        if inferir_genero(r["nome"]) is None:
            desconhecidos[r["nome"].split()[0]] += 1
    print("primeiros nomes não classificados mais comuns:", desconhecidos.most_common(15))
