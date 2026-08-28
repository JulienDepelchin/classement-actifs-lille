"""
Poller "fiabilite des autoroutes vers Lille" : temps de trajet EN DIRECT (trafic live TomTom)
depuis 12 villes d'entree de l'agglomeration lilloise vers Lille-Flandres.

Pendant delta au TER : on ne veut pas un temps moyen mais la DISTRIBUTION jour apres jour ->
temps median, "temps tampon" (p95 - median), pire jour, frequence des jours galere.

Cle : env TOMTOM_KEY (GitHub Actions secret) ou data/raw/tomtom_key.txt (local).
A lancer regulierement (Cloudflare Worker -> workflow_dispatch, ~toutes les 10-15 min).

Sortie : data/rt/autoroutes/<date>.csv   (append)
  poll_utc, origine, autoroute, temps_live_min, temps_libre_min, retard_min, distance_km
"""
from __future__ import annotations
import os
import sys
import csv
import json
import time
import datetime as dt
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
CORR = ROOT / "data" / "rt" / "corridors_autoroutes.csv"
OUTDIR = ROOT / "data" / "rt" / "autoroutes"
LILLE = "50.63658,3.07103"
COLS = ["poll_utc", "origine", "autoroute", "temps_live_min", "temps_libre_min",
        "retard_min", "distance_km"]

KEY = os.environ.get("TOMTOM_KEY", "").strip()
if not KEY:
    kf = ROOT / "data" / "raw" / "tomtom_key.txt"
    KEY = kf.read_text().strip() if kf.exists() else ""
if not KEY:
    sys.exit("TOMTOM_KEY manquant (env ou data/raw/tomtom_key.txt)")


def route(lat: float, lon: float) -> dict | None:
    # pas de departAt -> trafic LIVE (etat de la route maintenant)
    url = (f"https://api.tomtom.com/routing/1/calculateRoute/{lat:.5f},{lon:.5f}:{LILLE}/json"
           f"?key={KEY}&traffic=true&travelMode=car&routeType=fastest&computeTravelTimeFor=all")
    req = urllib.request.Request(url, headers={"User-Agent": "vdn-classement-lille/1.0"})
    for essai in (1, 2, 3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                s = json.load(r)["routes"][0]["summary"]
            live = s["travelTimeInSeconds"] / 60
            libre = s.get("noTrafficTravelTimeInSeconds", s["travelTimeInSeconds"]) / 60
            return {"temps_live_min": round(live, 1), "temps_libre_min": round(libre, 1),
                    "retard_min": round(live - libre, 1),
                    "distance_km": round(s["lengthInMeters"] / 1000, 1)}
        except Exception as e:
            if essai == 3:
                print(f"  ! {lat},{lon} : {e}")
                return None
            time.sleep(4)


def one_pass() -> None:
    poll_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    d_service = dt.date.today().strftime("%Y%m%d")
    rows = []
    with open(CORR, encoding="utf-8-sig") as f:
        corridors = list(csv.DictReader(f))
    for c in corridors:
        r = route(float(c["lat"]), float(c["lon"]))
        if r:
            rows.append({"poll_utc": poll_utc, "origine": c["origine"],
                         "autoroute": c["autoroute"], **r})
        time.sleep(0.3)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    path = OUTDIR / f"{d_service}.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerows(rows)
    med_ret = sorted(r["retard_min"] for r in rows)[len(rows) // 2] if rows else 0
    print(f"{poll_utc} | {len(rows)}/{len(corridors)} corridors | retard median {med_ret:.0f} min")


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "--loop":
        fin = time.monotonic() + float(sys.argv[2]) * 60
        while True:
            try:
                one_pass()
            except Exception as e:
                print(f"  pass KO : {e}")
            if time.monotonic() >= fin:
                break
            time.sleep(90)
    else:
        one_pass()


if __name__ == "__main__":
    main()
