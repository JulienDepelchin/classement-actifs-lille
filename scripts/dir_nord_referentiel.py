"""
Extrait le referentiel des stations de comptage DIR Nord (source DIRN) depuis le referentiel
national du reseau routier non concede, et decode l'axe a partir du code_pme.

code_pme DIRN : <lettre><4 chiffres = numero de route><6 caracteres = position>
  A0001... -> A1        A0022... -> A22       A0025... -> A25
  A0023... -> A23       A0027... -> A27       A0002... -> A2
  N0041... -> N41 (La Bassee)     N0356 / N0227 -> radiales lilloises
  A9022 / A9001 / A9025 ... -> bretelles / rocade

Le referentiel national ne fournit ni coordonnees ni libelle pour les stations DIRN
-> on reste a la maille AXE (suffisant pour l'analyse editoriale).

Sortie : data/rt/dir_nord_stations.csv  (a versionner)
"""
from __future__ import annotations
import io
import csv
import re
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "rt" / "dir_nord_stations.csv"
REF = "https://transport.data.gouv.fr/resources/79167/download"

ROUTES = {
    "1": "A1", "2": "A2", "22": "A22", "23": "A23", "25": "A25", "27": "A27",
    "41": "N41", "227": "N227", "356": "N356",
    "9001": "A1 (bretelle)", "9022": "A22 (rocade)", "9025": "A25 (bretelle)",
    "9227": "N227 (bretelle)", "9356": "N356 (bretelle)",
}


def decode(code: str) -> str:
    if code.startswith("A22TC"):
        return "A22 (contournement)"
    m = re.match(r"[A-Z](\d{4})", code)
    if not m:
        return "?"
    n = m.group(1)
    key = n if n.startswith("9") else str(int(n))
    return ROUTES.get(key, f"{code[0]}{int(n) if not n.startswith('9') else n}")


def main() -> None:
    txt = urllib.request.urlopen(urllib.request.Request(REF, headers={"User-Agent": "vdn/1.0"}),
                                 timeout=90).read().decode("utf-8", "ignore")
    rows = list(csv.DictReader(io.StringIO(txt), delimiter=";"))
    dirn = [r for r in rows if r.get("source") == "DIRN"]

    out = []
    for r in dirn:
        c = r["code_pme"]
        out.append({"code_pme": c, "route": decode(c),
                    "position": c[5:] if len(c) > 5 else "",
                    "code_insee_commune": r.get("code_insee_commune", "")})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["code_pme", "route", "position", "code_insee_commune"])
        w.writeheader()
        w.writerows(out)

    import collections
    print(f"{len(out)} stations DIRN")
    for rte, n in collections.Counter(o["route"] for o in out).most_common():
        print(f"  {rte:16s} {n}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
