"""
Temps et distance routiers reels commune -> Lille-Flandres (voiture), via OSRM (serveur public).

Requete le service `route` d'OSRM pour chaque centroide de commune candidate.
OSRM = trafic fluide (pas de congestion) -> on appliquera un facteur de pointe au moment de
l'integration (build_transport_multimodal.py).

Sortie : data/interim/voiture_lille_osrm.csv  (code_insee, osrm_voiture_min, osrm_voiture_km)
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
CENTROIDS = ROOT / "data" / "interim" / "communes_centroids_5962.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "interim" / "voiture_lille_osrm.csv"

OSRM = "https://router.project-osrm.org"
LILLE_FLANDRES = (50.63658, 3.07103)          # lat, lon
PAUSE_S = 0.15


def route(lat1: float, lon1: float, lat2: float, lon2: float):
    url = (f"{OSRM}/route/v1/driving/{lon1:.5f},{lat1:.5f};{lon2:.5f},{lat2:.5f}"
           f"?overview=false&alternatives=false")
    req = urllib.request.Request(url, headers={"User-Agent": "vdn-classement-lille/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if d.get("code") != "Ok":
        return None, None
    rt = d["routes"][0]
    return rt["duration"] / 60.0, rt["distance"] / 1000.0


def main() -> None:
    cand = pd.read_csv(CAND, dtype={"code_insee": str})[["code_insee"]]
    cent = pd.read_csv(CENTROIDS, dtype={"code_insee": str})
    df = cand.merge(cent[["code_insee", "lat", "lon"]], on="code_insee", how="left")

    done = {}
    if OUT.exists():
        done = pd.read_csv(OUT, dtype={"code_insee": str}).set_index("code_insee").to_dict("index")

    rows, ko = [], 0
    for i, r in enumerate(df.itertuples(), 1):
        if r.code_insee in done:
            rows.append({"code_insee": r.code_insee, **done[r.code_insee]})
            continue
        try:
            mn, km = route(r.lat, r.lon, *LILLE_FLANDRES)
        except Exception as e:
            mn, km, ko = None, None, ko + 1
            print(f"  ! {r.code_insee} : {e}")
        rows.append({"code_insee": r.code_insee, "osrm_voiture_min": round(mn, 1) if mn else None,
                     "osrm_voiture_km": round(km, 1) if km else None})
        time.sleep(PAUSE_S)
        if i % 50 == 0:
            pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8-sig")
            print(f"  {i}/{len(df)}...")

    res = pd.DataFrame(rows)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")
    ok = res["osrm_voiture_min"].notna()
    print(f"\n{int(ok.sum())}/{len(res)} routes OK (echecs : {int((~ok).sum())})")
    print(f"temps (min) fluide : med {res['osrm_voiture_min'].median():.0f} | "
          f"min {res['osrm_voiture_min'].min():.0f} | max {res['osrm_voiture_min'].max():.0f}")
    print(f"distance routiere (km) : med {res['osrm_voiture_km'].median():.0f} | max {res['osrm_voiture_km'].max():.0f}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
