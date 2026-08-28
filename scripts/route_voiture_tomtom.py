"""
Temps voiture commune -> Lille-Flandres AVEC TRAFIC (heure de pointe), via TomTom Routing API.

departAt = mardi 2026-09-15 08:00 (arrivee au travail). TomTom applique son modele de trafic
recurrent (`historicTrafficTravelTimeInSeconds`).

Cle : data/raw/tomtom_key.txt (une ligne). Quota gratuit 2500 req/j, 5 req/s -> 411 requetes OK.

Sortie : data/interim/voiture_lille_tomtom.csv
  tt_voiture_min        temps de pointe (trafic recurrent)
  tt_voiture_libre_min  temps a vide (sans trafic)
  tt_bouchons_min       minutes perdues dans les bouchons (= pointe - libre)
  tt_voiture_km         distance routiere
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
KEYFILE = ROOT / "data" / "raw" / "tomtom_key.txt"
CENTROIDS = ROOT / "data" / "interim" / "communes_centroids_5962.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "interim" / "voiture_lille_tomtom.csv"

LILLE = "50.63658,3.07103"
DEPART = "2026-09-15T08:00:00"
KEY = KEYFILE.read_text().strip()
PAUSE = 0.35


def route(lat: float, lon: float) -> dict:
    url = (f"https://api.tomtom.com/routing/1/calculateRoute/{lat:.5f},{lon:.5f}:{LILLE}/json"
           f"?key={KEY}&traffic=true&departAt={DEPART}&travelMode=car&routeType=fastest"
           f"&computeTravelTimeFor=all")
    req = urllib.request.Request(url, headers={"User-Agent": "vdn-classement-lille/1.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        s = json.load(r)["routes"][0]["summary"]
    pointe = s.get("historicTrafficTravelTimeInSeconds", s["travelTimeInSeconds"]) / 60
    libre = s.get("noTrafficTravelTimeInSeconds", s["travelTimeInSeconds"]) / 60
    return {"tt_voiture_min": round(pointe, 1), "tt_voiture_libre_min": round(libre, 1),
            "tt_bouchons_min": round(pointe - libre, 1), "tt_voiture_km": round(s["lengthInMeters"] / 1000, 1)}


def main() -> None:
    cand = pd.read_csv(CAND, dtype={"code_insee": str})[["code_insee"]]
    cent = pd.read_csv(CENTROIDS, dtype={"code_insee": str})
    df = cand.merge(cent[["code_insee", "lat", "lon"]], on="code_insee", how="left")

    done = {}
    if OUT.exists():
        done = pd.read_csv(OUT, dtype={"code_insee": str}).set_index("code_insee").to_dict("index")

    rows, ko = [], 0
    for i, r in enumerate(df.itertuples(), 1):
        if r.code_insee in done and pd.notna(done[r.code_insee].get("tt_voiture_min")):
            rows.append({"code_insee": r.code_insee, **done[r.code_insee]})
            continue
        for essai in (1, 2, 3):
            try:
                rows.append({"code_insee": r.code_insee, **route(r.lat, r.lon)})
                break
            except Exception as e:
                if essai == 3:
                    ko += 1
                    rows.append({"code_insee": r.code_insee})
                    print(f"  ! {r.code_insee} : {e}")
                time.sleep(3)
        time.sleep(PAUSE)
        if i % 50 == 0:
            pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8-sig")
            print(f"  {i}/{len(df)}...")

    res = pd.DataFrame(rows)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")
    ok = res["tt_voiture_min"].notna()
    print(f"\n{int(ok.sum())}/{len(res)} OK (echecs {ko})")
    print(f"temps pointe (min) : med {res['tt_voiture_min'].median():.0f} | max {res['tt_voiture_min'].max():.0f}")
    print(f"bouchons (min)     : med {res['tt_bouchons_min'].median():.0f} | max {res['tt_bouchons_min'].max():.0f}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
