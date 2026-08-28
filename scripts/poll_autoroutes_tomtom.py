"""
Poller "fiabilite des routes vers Lille" -- version gratuite optimisee.

Trafic LIVE TomTom (sans departAt) : on veut la DISTRIBUTION jour apres jour, pas un temps moyen.
  -> temps median, "temps tampon" (p95 - median), pire jour, % de jours galere, courbe horaire.

Echantillonnage adapte a l'heure pour tenir sous le quota gratuit (2500 appels/j) :
  - POINTE matin (04:45-07:15 UTC) et soir (14:15-17:15 UTC) : tous les points + tous les
    troncons a chaque run (cron ~10 min) ; le RETOUR (Lille -> point) uniquement le soir.
  - EPAULE / journee (jusqu'a 18:30 UTC) : seulement aux minutes 00 et 30 (~toutes les 30 min).
  - NUIT : rien.
Budget estime ~1650 appels/j.

Cle : env TOMTOM_KEY (secret GitHub Actions) ou data/raw/tomtom_key.txt (local).

Entrees : data/rt/points_routes.csv  (libelle,zone,type,lat,lon,retour)
          data/rt/troncons_routes.csv (libelle,axe,lat_a,lon_a,lat_b,lon_b)
Sortie  : data/rt/autoroutes/<date>.csv  (append)
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
PTS = ROOT / "data" / "rt" / "points_routes.csv"
TRC = ROOT / "data" / "rt" / "troncons_routes.csv"
OUTDIR = ROOT / "data" / "rt" / "autoroutes"
LILLE = (50.63658, 3.07103)
COLS = ["poll_utc", "categorie", "libelle", "zone_axe", "type", "sens",
        "temps_live_min", "temps_libre_min", "retard_min", "distance_km"]

# fenetres UTC (ete : Paris = UTC+2)
POINTE_MATIN = (dt.time(4, 45), dt.time(7, 15))
POINTE_SOIR = (dt.time(14, 15), dt.time(17, 15))
JOURNEE = (dt.time(4, 0), dt.time(18, 30))

KEY = os.environ.get("TOMTOM_KEY", "").strip()
if not KEY:
    kf = ROOT / "data" / "raw" / "tomtom_key.txt"
    KEY = kf.read_text().strip() if kf.exists() else ""
if not KEY:
    sys.exit("TOMTOM_KEY manquant")


def _summary(url: str) -> dict | None:
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
                print(f"  ! {e}")
                return None
            time.sleep(4)


def route(a: tuple[float, float], b: tuple[float, float]) -> dict | None:
    url = (f"https://api.tomtom.com/routing/1/calculateRoute/"
           f"{a[0]:.5f},{a[1]:.5f}:{b[0]:.5f},{b[1]:.5f}/json"
           f"?key={KEY}&traffic=true&travelMode=car&routeType=fastest&computeTravelTimeFor=all")
    return _summary(url)


def _in(win, t):
    return win[0] <= t < win[1]


def one_pass() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    t = now.time()
    matin, soir = _in(POINTE_MATIN, t), _in(POINTE_SOIR, t)
    pointe = matin or soir
    if not _in(JOURNEE, t):
        print(f"{now:%H:%M}Z nuit -> skip"); return
    if not pointe and now.minute not in (0, 1, 2, 30, 31, 32):
        print(f"{now:%H:%M}Z epaule, pas l'heure -> skip"); return

    poll_utc = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(PTS, encoding="utf-8-sig") as f:
        points = list(csv.DictReader(f))
    with open(TRC, encoding="utf-8-sig") as f:
        troncons = list(csv.DictReader(f))

    rows = []
    for p in points:
        o = (float(p["lat"]), float(p["lon"]))
        r = route(o, LILLE)
        if r:
            rows.append({"poll_utc": poll_utc, "categorie": "point", "libelle": p["libelle"],
                         "zone_axe": p["zone"], "type": p["type"], "sens": "vers_lille", **r})
        time.sleep(0.3)
        if soir and p["retour"] == "1":
            r = route(LILLE, o)
            if r:
                rows.append({"poll_utc": poll_utc, "categorie": "point", "libelle": p["libelle"],
                             "zone_axe": p["zone"], "type": p["type"], "sens": "depuis_lille", **r})
            time.sleep(0.3)

    if pointe:
        for tr in troncons:
            r = route((float(tr["lat_a"]), float(tr["lon_a"])),
                      (float(tr["lat_b"]), float(tr["lon_b"])))
            if r:
                rows.append({"poll_utc": poll_utc, "categorie": "troncon", "libelle": tr["libelle"],
                             "zone_axe": tr["axe"], "type": "troncon", "sens": "vers_lille", **r})
            time.sleep(0.3)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    path = OUTDIR / f"{now.date():%Y%m%d}.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerows(rows)
    ret = [r["retard_min"] for r in rows]
    med = sorted(ret)[len(ret) // 2] if ret else 0
    tag = "POINTE" if pointe else "epaule"
    print(f"{poll_utc} [{tag}] {len(rows)} lignes | retard median {med:.0f} min")


if __name__ == "__main__":
    one_pass()
