"""
Echantillon de communes du classement pour verifier l'instantane TomTom Routing
(departAt mardi 8h, fige fin aout) contre la vraie distribution TomTom Traffic Stats
(juillet 2026) -- 1 seul report Traffic Stats, echantillon stratifie sur le rang.

Sortie : data/rt/traffic_stats_requests/verif_classement.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "data" / "rt" / "traffic_stats_requests"
LILLE = {"latitude": 50.63658, "longitude": 3.07103}
N_ECH = 18


def main() -> None:
    s = pd.read_csv(ROOT / "data" / "output" / "scores_0_20.csv", dtype={"code_insee": str})
    s = s.sort_values("rang").reset_index(drop=True)
    idx = [round(i * (len(s) - 1) / (N_ECH - 1)) for i in range(N_ECH)]
    ech = s.iloc[idx][["code_insee", "commune", "dep", "rang", "tranche"]].drop_duplicates("code_insee")

    cent = pd.read_csv(ROOT / "data" / "interim" / "communes_centroids_5962.csv", dtype={"code_insee": str})
    ech = ech.merge(cent, on="code_insee", how="left")
    manquants = ech[ech.lat.isna()]
    if len(manquants):
        print("!! sans centroide :", manquants.commune.tolist())
        ech = ech.dropna(subset=["lat"])

    print(f"{len(ech)} communes echantillonnees (rangs {ech.rang.min()}-{ech.rang.max()} / {len(s)})")
    print(ech[["rang", "commune", "dep", "tranche"]].to_string(index=False))

    routes = [{
        "name": f"{r.commune} -> Lille",
        "start": {"latitude": round(r.lat, 5), "longitude": round(r.lon, 5)},
        "end": LILLE,
        "fullTraversal": False,
        "zoneId": "Europe/Paris",
        "probeSource": "ALL",
    } for r in ech.itertuples()]

    payload = {
        "jobName": "VDN verif classement -- echantillon rang",
        "distanceUnit": "KILOMETERS",
        "routes": routes,
        "dateRanges": [{"name": "Juillet 2026", "from": "2026-07-01", "to": "2026-07-31"}],
        "timeSets": [{
            "name": "Semaine 7h-8h",
            "timeGroups": [{"days": ["MON", "TUE", "WED", "THU", "FRI"], "times": ["07:00-08:00"]}],
        }, {
            "name": "Semaine 8h-9h",
            "timeGroups": [{"days": ["MON", "TUE", "WED", "THU", "FRI"], "times": ["08:00-09:00"]}],
        }],
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / "verif_classement.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    ech[["code_insee", "commune", "rang", "tranche"]].to_csv(
        ROOT / "data" / "output" / "verif_classement_echantillon.csv", index=False, encoding="utf-8-sig")
    print(f"\n-> {out}  ({len(routes)} routes, 1 report)")


if __name__ == "__main__":
    main()
