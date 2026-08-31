"""
Telecharge les jeux open data ilevia / MEL utiles a l'angle "fiabilite du reseau ilevia" :

  - dsp_ilevia:ponctualite         indices mensuels par ligne (retards / avances / services
                                   non effectues), ~4 ans, ~10 000 lignes
  - dsp_ilevia:vitesse_moyenne_bus vitesse moyenne inter-arret par ligne / mois / type de jour
                                   (~820 000 lignes)
  - dsp_ilevia:perturbations       instantane des perturbations en cours (pour reference)

Source : OGC API Features GeoServer de la MEL (Licence Ouverte, sans cle).
Sortie : data/raw/ilevia/<collection>.csv
"""
from __future__ import annotations
import csv
import io
import sys
import time
import json
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "ilevia"
BASE = "https://data.lillemetropole.fr/geoserver/ogc/features/v1/collections"
PAGE = 10000

COLLECTIONS = {
    "ponctualite": "dsp_ilevia:ponctualite",
    "vitesse_moyenne_bus": "dsp_ilevia:vitesse_moyenne_bus",
    "perturbations": "dsp_ilevia:perturbations",
}


def fetch_json(url: str) -> dict:
    for essai in (1, 2, 3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vdn-classement-lille/1.0"})
            return json.loads(urllib.request.urlopen(req, timeout=120).read())
        except Exception as e:
            if essai == 3:
                raise
            print(f"    retry ({e})")
            time.sleep(8)


def dump(nom: str, coll: str) -> None:
    rows: list[dict] = []
    offset = 0
    while True:
        url = f"{BASE}/{coll}/items?f=application/json&limit={PAGE}&offset={offset}"
        fc = fetch_json(url)
        feats = fc.get("features", [])
        rows.extend(f.get("properties", {}) for f in feats)
        matched = fc.get("numberMatched")
        print(f"  {nom}: {len(rows)}"
              + (f" / {matched}" if matched is not None else ""))
        if len(feats) < PAGE:
            break
        offset += PAGE

    if not rows:
        print(f"  {nom}: vide, ignore")
        return
    cols = list({k for r in rows for k in r})
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{nom}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"  -> {path}  ({len(rows)} lignes, {len(cols)} colonnes)")


def main() -> None:
    only = sys.argv[1:] or list(COLLECTIONS)
    for nom in only:
        if nom not in COLLECTIONS:
            print(f"inconnu : {nom} (choix : {', '.join(COLLECTIONS)})")
            continue
        print(f"\n== {nom} ==")
        dump(nom, COLLECTIONS[nom])


if __name__ == "__main__":
    main()
