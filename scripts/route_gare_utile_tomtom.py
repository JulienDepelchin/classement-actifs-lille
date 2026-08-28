"""
Temps voiture commune -> gare utile (rabattement / park & ride) AVEC TRAFIC, via TomTom.

Remplace l'estimation calibree a vol d'oiseau (2,02 + 1,32 x gc_km) de build_transport_communes.py
pour les 348 communes dont la gare utile n'est PAS sur le territoire. Cohérent avec voiture_min
(lui aussi route TomTom avec trafic).

departAt = mardi 2026-09-15 07:30 : le rabattement se fait plus tot que 8h pour attraper le train
qui met a Lille vers 8h30-9h.

Cle : data/raw/tomtom_key.txt. Sortie : data/interim/acces_gare_utile_tomtom.csv
  acces_gare_tt_min        temps de pointe (trafic recurrent)
  acces_gare_tt_libre_min  temps a vide
  acces_gare_tt_km         distance routiere
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
KEY = (ROOT / "data" / "raw" / "tomtom_key.txt").read_text().strip()
TRANSPORT = ROOT / "data" / "output" / "transport_communes_candidates.csv"
CENTROIDS = ROOT / "data" / "interim" / "communes_centroids_5962.csv"
GARES = ROOT / "data" / "interim" / "gares_ter_communes.csv"
OUT = ROOT / "data" / "interim" / "acces_gare_utile_tomtom.csv"

DEPART = "2026-09-15T07:30:00"
PAUSE = 0.35


def route(lat1, lon1, lat2, lon2) -> dict:
    url = (f"https://api.tomtom.com/routing/1/calculateRoute/"
           f"{lat1:.5f},{lon1:.5f}:{lat2:.5f},{lon2:.5f}/json"
           f"?key={KEY}&traffic=true&departAt={DEPART}&travelMode=car&routeType=fastest"
           f"&computeTravelTimeFor=all")
    req = urllib.request.Request(url, headers={"User-Agent": "vdn-classement-lille/1.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        s = json.load(r)["routes"][0]["summary"]
    pointe = s.get("historicTrafficTravelTimeInSeconds", s["travelTimeInSeconds"]) / 60
    libre = s.get("noTrafficTravelTimeInSeconds", s["travelTimeInSeconds"]) / 60
    return {"acces_gare_tt_min": round(pointe, 1), "acces_gare_tt_libre_min": round(libre, 1),
            "acces_gare_tt_km": round(s["lengthInMeters"] / 1000, 1)}


def main() -> None:
    tr = pd.read_csv(TRANSPORT, dtype={"code_insee": str, "gare_utile_uic": str})
    tr = tr[~tr["gare_utile_sur_place"].astype(bool)][["code_insee", "gare_utile", "gare_utile_uic"]]
    cent = pd.read_csv(CENTROIDS, dtype={"code_insee": str}).set_index("code_insee")[["lat", "lon"]]
    gx = (pd.read_csv(GARES, dtype={"uic": str}).dropna(subset=["stop_lat"])
          .drop_duplicates("uic").set_index("uic")[["stop_lat", "stop_lon"]].astype(float))

    done = {}
    if OUT.exists():
        done = pd.read_csv(OUT, dtype={"code_insee": str}).set_index("code_insee").to_dict("index")

    rows, ko = [], 0
    for i, r in enumerate(tr.itertuples(), 1):
        if r.code_insee in done and pd.notna(done[r.code_insee].get("acces_gare_tt_min")):
            rows.append({"code_insee": r.code_insee, "gare_utile_uic": r.gare_utile_uic, **done[r.code_insee]})
            continue
        try:
            c = cent.loc[r.code_insee]
            g = gx.loc[r.gare_utile_uic]
        except KeyError as e:
            print(f"  ! coords manquantes {r.code_insee} / {r.gare_utile_uic} ({e})")
            rows.append({"code_insee": r.code_insee, "gare_utile_uic": r.gare_utile_uic})
            ko += 1
            continue
        for essai in (1, 2, 3):
            try:
                rows.append({"code_insee": r.code_insee, "gare_utile_uic": r.gare_utile_uic,
                             **route(c.lat, c.lon, g.stop_lat, g.stop_lon)})
                break
            except Exception as e:
                if essai == 3:
                    ko += 1
                    rows.append({"code_insee": r.code_insee, "gare_utile_uic": r.gare_utile_uic})
                    print(f"  ! {r.code_insee} : {e}")
                time.sleep(3)
        time.sleep(PAUSE)
        if i % 50 == 0:
            pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8-sig")
            print(f"  {i}/{len(tr)}")

    res = pd.DataFrame(rows)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")
    ok = res["acces_gare_tt_min"].notna()
    print(f"\n{int(ok.sum())}/{len(res)} OK (echecs {ko})")
    print(f"acces gare (pointe, min) : med {res['acces_gare_tt_min'].median():.1f} | "
          f"p90 {res['acces_gare_tt_min'].quantile(.9):.1f} | max {res['acces_gare_tt_min'].max():.1f}")
    d = (res["acces_gare_tt_min"] - res["acces_gare_tt_libre_min"])
    print(f"bouchons sur le rabattement : med {d.median():.1f} | max {d.max():.1f}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
