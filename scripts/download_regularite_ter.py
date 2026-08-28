"""
Historique de la regularite mensuelle TER Hauts-de-France (SNCF open data).
NIVEAU REGIONAL uniquement (pas de ventilation par ligne/gare) -> sert a l'encadre methodo et a
un graphe compagnon, PAS au scoring.

Sortie : data/raw/sncf/regularite_ter_hdf.csv
"""
from __future__ import annotations
import sys
import json
import urllib.request
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "sncf" / "regularite_ter_hdf.csv"
API = ("https://data.sncf.com/api/explore/v2.1/catalog/datasets/regularite-mensuelle-ter/records"
       "?where=region%20in%20(%22Hauts-de-France%22%2C%22Etoile%20Amiens%22)"
       "&order_by=date&limit=100")


def main() -> None:
    rows, offset = [], 0
    while True:
        with urllib.request.urlopen(urllib.request.Request(API + f"&offset={offset}",
                                    headers={"User-Agent": "vdn/1.0"}), timeout=40) as r:
            d = json.load(r)
        rows += d["results"]
        if len(d["results"]) < 100:
            break
        offset += 100

    df = pd.DataFrame(rows)
    df["taux_annulation"] = (df["nombre_de_trains_annules"] / df["nombre_de_trains_programmes"] * 100).round(2)
    keep = ["date", "region", "nombre_de_trains_programmes", "nombre_de_trains_annules",
            "nombre_de_trains_en_retard_a_l_arrivee", "taux_de_regularite", "taux_annulation"]
    df = df[keep].sort_values(["region", "date"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")

    hdf = df[df["region"] == "Hauts-de-France"]
    d12 = hdf.tail(12)
    print(f"{len(df)} lignes ({df['date'].min()} -> {df['date'].max()})")
    print(f"\nHauts-de-France, 12 derniers mois :")
    print(f"  regularite moyenne : {d12['taux_de_regularite'].mean():.1f} %  "
          f"(min {d12['taux_de_regularite'].min():.1f} le {d12.loc[d12['taux_de_regularite'].idxmin(),'date']})")
    print(f"  annulations moyenne: {d12['taux_annulation'].mean():.1f} %  "
          f"(max {d12['taux_annulation'].max():.1f} le {d12.loc[d12['taux_annulation'].idxmax(),'date']})")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
