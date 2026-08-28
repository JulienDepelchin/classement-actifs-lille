"""
Telecharge les sources ajoutees en v2 du scoring :
- Fiscalite locale des particuliers (DGFiP, via data.economie.gouv.fr) : taux de taxe fonciere
  bati + taxe d'habitation votes, par commune. Filtre 59/62.
- Concentrations annuelles de polluants aux stations de fond Atmo Hauts-de-France (NO2, PM2.5,
  PM10) : ArcGIS FeatureServer mes_hdf_annuel_poll_princ.

Sorties : data/raw/fiscalite/fiscalite_particuliers_5962.csv
          data/raw/atmo/stations_annuel_hdf.csv
"""
from __future__ import annotations
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "vdn-classement-lille/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def fiscalite() -> None:
    out = ROOT / "data" / "raw" / "fiscalite" / "fiscalite_particuliers_5962.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    base = ("https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
            "fiscalite-locale-des-particuliers/records")
    rows, offset = [], 0
    while True:
        url = (f"{base}?where=" + urllib.parse.quote("dep=59 or dep=62")
               + f"&limit=100&offset={offset}")
        d = fetch_json(url)
        res = d.get("results", [])
        rows += res
        if len(res) < 100 or offset > 8000:
            break
        offset += 100
    df = pd.DataFrame(rows)
    df["exercice"] = pd.to_numeric(df["exercice"], errors="coerce")
    df = df[df["exercice"] == df["exercice"].max()]
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"fiscalite : exercice {int(df['exercice'].max())} | {len(df)} communes | "
          f"taux_global_tfb med {pd.to_numeric(df['taux_global_tfb'], errors='coerce').median():.1f}")
    print(f"  -> {out}")


def atmo_stations() -> None:
    out = ROOT / "data" / "raw" / "atmo" / "stations_annuel_hdf.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    base = ("https://services8.arcgis.com/rxZzohbySMKHTNcy/arcgis/rest/services/"
            "mes_hdf_annuel_poll_princ/FeatureServer/0/query")
    rows, offset = [], 0
    while True:
        url = (base + "?where=" + urllib.parse.quote("influence='fond'")
               + "&outFields=nom_station,code_station,nom_com,insee_com,typologie,nom_poll,"
                 "valeur,unite,date_debut,date_fin,statut_valid,x_wgs84,y_wgs84"
               + f"&f=json&resultOffset={offset}&resultRecordCount=1000")
        d = fetch_json(url)
        feats = d.get("features", [])
        rows += [f["attributes"] for f in feats]
        if len(feats) < 1000:
            break
        offset += 1000
    df = pd.DataFrame(rows)
    df["annee"] = pd.to_datetime(df["date_debut"], unit="ms", errors="coerce").dt.year
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"atmo stations : {len(df)} lignes | stations {df['nom_station'].nunique()} | "
          f"polluants {sorted(df['nom_poll'].dropna().unique())} | annees {sorted(df['annee'].dropna().astype(int).unique())}")
    print(f"  -> {out}")


if __name__ == "__main__":
    fiscalite()
    atmo_stations()
