"""
Genere les requetes JSON pour l'API TomTom Traffic Stats -- Route Analysis, pour les
memes 26 points + 5 troncons que le poller live (data/rt/points_routes.csv /
troncons_routes.csv), avec un an d'historique et une courbe horaire complete.

Autorisation obtenue de TomTom (Vincent Martinier, head of communications, 2026-09-14) :
usage editorial permis pour ce projet, source mentionnee, PAS de calcul derive a partir
de ces donnees (pas d'extrapolation -- on affiche les chiffres tels que Traffic Stats
les sort, avec attribution).

Limites du produit (doc officielle) : 200 km max par route, 20 routes max par requete,
366 jours max par plage de dates (732 jours uniques cumules), 24 plages de dates, 24
"timeSets". D'ou le decoupage en lots de 20 routes.

Limites de l'ESSAI GRATUIT (dashboard TomTom, verifie 2026-09-14, peuvent differer du
produit complet) : 20 reports au total (nos 2 lots = 2/20), 3 reports max EN COURS en
meme temps (soumettre sequentiellement, cf submit_traffic_stats_job.py qui attend la
fin d'un job avant de rendre la main), 200 km/route (idem produit complet), et surtout
**fenetre de donnees limitee a juillet 2026** (pas l'archive ~2 ans du produit payant) --
a garder en tete pour l'analyse : juillet = vacances scolaires, trafic probablement
plus fluide qu'un mois "normal" de rentree.

Sortie : data/rt/traffic_stats_requests/batch1.json, batch2.json -- prets a soumettre
via submit_traffic_stats_job.py des qu'une cle API Traffic Stats est disponible.
"""
from __future__ import annotations
import csv
import json
import sys
import datetime as dt
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
PTS = ROOT / "data" / "rt" / "points_routes.csv"
TRC = ROOT / "data" / "rt" / "troncons_routes.csv"
OUTDIR = ROOT / "data" / "rt" / "traffic_stats_requests"
LILLE = {"latitude": 50.63658, "longitude": 3.07103}

JOURS_SEMAINE = ["MON", "TUE", "WED", "THU", "FRI"]
JOURS_WE = ["SAT", "SUN"]
HEURES_JOUR = range(5, 19)  # 5h -> 18h59, meme fenetre que le poller live (04:00-18:30 UTC ~ 06:00-20:30 Paris ete)


def pt(lat: float, lon: float) -> dict:
    return {"latitude": round(lat, 5), "longitude": round(lon, 5)}


def build_routes() -> list[dict]:
    routes = []
    with open(PTS, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            routes.append({
                "name": f"{r['libelle']} -> Lille",
                "start": pt(float(r["lat"]), float(r["lon"])),
                "end": LILLE,
                "fullTraversal": False,
                "zoneId": "Europe/Paris",
                "probeSource": "ALL",
            })
    with open(TRC, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            routes.append({
                "name": r["libelle"],
                "start": pt(float(r["lat_a"]), float(r["lon_a"])),
                "end": pt(float(r["lat_b"]), float(r["lon_b"])),
                "fullTraversal": False,
                "zoneId": "Europe/Paris",
                "probeSource": "ALL",
            })
    return routes


def build_date_ranges() -> list[dict]:
    # Fenetre imposee par l'essai gratuit Traffic Stats (dashboard TomTom, 2026-09-14) :
    # seul juillet 2026 est interrogeable, pas l'archive ~2 ans du produit complet.
    # A ajuster si le forfait change.
    return [{"name": "Juillet 2026", "from": "2026-07-01", "to": "2026-07-31"}]


def build_time_sets() -> list[dict]:
    # Les timeSets doivent etre mutuellement exclusifs (contrainte API : "inclusively
    # separate") -- pas d'agregat "journee complete" en semaine, il chevaucherait les
    # 14 tranches horaires. On le recalcule nous-memes a partir d'elles a l'analyse.
    sets = []
    for h in HEURES_JOUR:
        sets.append({
            "name": f"Semaine {h}h-{h+1}h",
            "timeGroups": [{"days": JOURS_SEMAINE, "times": [f"{h:02d}:00-{h+1:02d}:00"]}],
        })
    sets.append({
        "name": "Week-end journee complete",
        "timeGroups": [{"days": JOURS_WE, "times": [f"{min(HEURES_JOUR):02d}:00-{max(HEURES_JOUR)+1:02d}:00"]}],
    })
    return sets


def main() -> None:
    routes = build_routes()
    date_ranges = build_date_ranges()
    time_sets = build_time_sets()
    print(f"{len(routes)} routes | {len(date_ranges)} plage(s) de dates "
          f"({date_ranges[0]['from']} -> {date_ranges[0]['to']}) | {len(time_sets)} creneaux horaires")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    n_batch = (len(routes) + 19) // 20
    for i in range(n_batch):
        lot = routes[i * 20:(i + 1) * 20]
        payload = {
            "jobName": f"VDN classement Lille -- lot {i+1}/{n_batch}",
            "distanceUnit": "KILOMETERS",
            "routes": lot,
            "dateRanges": date_ranges,
            "timeSets": time_sets,
        }
        out = OUTDIR / f"batch{i+1}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> {out}  ({len(lot)} routes)")

    print("\nPret a soumettre avec scripts/submit_traffic_stats_job.py une fois la cle "
          "Traffic Stats obtenue (env TRAFFICSTATS_KEY ou data/raw/traffic_stats_key.txt).")


if __name__ == "__main__":
    main()
