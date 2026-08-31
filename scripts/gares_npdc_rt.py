"""
Construit la liste des gares TER du Nord (59) et du Pas-de-Calais (62) a suivre dans le
GTFS-RT, pour l'article "les lignes TER les plus fiables du NPDC".

Source : data/interim/gares_ter_communes.csv (gares TER geolocalisees + commune, deja
produit par le pipeline). On garde celles dont la commune est dans le 59 ou le 62.

Sortie : data/rt/gares_npdc.csv  (uic, nom, dep, commune, role)
  role = "lille" pour Lille-Flandres / Lille-Europe, "npdc" sinon.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "interim" / "gares_ter_communes.csv"
OUT = ROOT / "data" / "rt" / "gares_npdc.csv"
LILLE = {"87286005", "87223263"}


def main() -> None:
    g = pd.read_csv(SRC, dtype=str)
    g["code_insee_commune"] = g["code_insee_commune"].fillna("")
    g = g[g["code_insee_commune"].str.match(r"^(59|62)\d{3}$")].copy()
    g["uic"] = g["uic"].str.zfill(8)
    g = g.drop_duplicates("uic").sort_values("stop_name")
    g["dep"] = g["code_insee_commune"].str[:2]
    g["role"] = g["uic"].apply(lambda u: "lille" if u.lstrip("0") in LILLE else "npdc")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out = g.rename(columns={"stop_name": "nom", "code_insee_commune": "code_insee"})[
        ["uic", "nom", "dep", "code_insee", "commune", "role"]
    ]
    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    print(f"{len(out)} gares TER 59/62  ->  {OUT}")
    print(f"  Nord {int((out.dep == '59').sum())} | Pas-de-Calais {int((out.dep == '62').sum())}")
    print("  Lille :", list(out.loc[out.role == "lille", "nom"]))


if __name__ == "__main__":
    main()
