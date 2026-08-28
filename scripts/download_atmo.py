"""
Telecharge l'indice ATMO journalier par commune, Nord + Pas-de-Calais, 1er janvier 2026 -> today.

Source : Atmo Hauts-de-France, FeatureServer ArcGIS "Indices communaux ... (annee en cours)"
(le WFS national data.atmo-france.org renvoie des 504). Pagination par resultOffset (1000/page).

Sortie : data/raw/atmo/ind_atmo_5962_2026.csv  (colonnes date_ech, code_qual, code_zone)
"""
from __future__ import annotations
import sys
import time
import json
import urllib.request
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "atmo" / "ind_atmo_5962_2026.csv"

URL = ("https://services8.arcgis.com/rxZzohbySMKHTNcy/arcgis/rest/services/"
       "ind_hdf_2021/FeatureServer/0/query")
WHERE = "type_zone='commune' AND (code_zone LIKE '59%' OR code_zone LIKE '62%')"
PAGE = 1000


def page(offset: int) -> list[dict]:
    params = {
        "where": WHERE, "outFields": "date_ech,code_qual,code_zone",
        "returnGeometry": "false", "orderByFields": "ObjectId",
        "resultOffset": str(offset), "resultRecordCount": str(PAGE), "f": "json",
    }
    q = "&".join(f"{k}={urllib.request.quote(v)}" for k, v in params.items())
    req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": "vdn-classement-lille/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    if "error" in d:
        raise RuntimeError(d["error"])
    return d.get("features", [])


def main() -> None:
    rows, offset = [], 0
    while True:
        for essai in (1, 2, 3):
            try:
                feats = page(offset)
                break
            except Exception as e:
                print(f"  offset {offset} echec {essai} : {e}")
                time.sleep(10)
        else:
            raise RuntimeError(f"echec offset {offset}")
        if not feats:
            break
        rows.extend(f["attributes"] for f in feats)
        offset += PAGE
        if offset % 20000 == 0:
            print(f"  {offset:,} lignes...")
        time.sleep(0.2)

    df = pd.DataFrame(rows)
    df["date_ech"] = pd.to_datetime(df["date_ech"], unit="ms").dt.date
    df = df.drop_duplicates(["code_zone", "date_ech"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\n-> {OUT}  ({len(df):,} lignes, {df['code_zone'].nunique()} communes, "
          f"{df['date_ech'].min()} -> {df['date_ech'].max()})")


if __name__ == "__main__":
    main()
