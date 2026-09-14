"""
Analyse des resultats TomTom Traffic Stats -- Route Analysis, juillet 2026, 31 routes
(26 points + 5 troncons, memes coordonnees que le poller live).

Autorisation TomTom (Vincent Martinier, 2026-09-14) : chiffres affiches TELS QUELS,
source mentionnee, aucun calcul derive/extrapole a partir de ces donnees.

Sources : data/raw/traffic_stats/results/batch{1,2}.json  (gitignore, brut TomTom)
Sortie  : data/output/traffic_stats_juillet_routes.csv (par route x creneau)
          data/output/traffic_stats_juillet_synthese.csv (par route, vue synthetique)
"""
from __future__ import annotations
import sys
import json
import re
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "traffic_stats" / "results"
OUT = ROOT / "data" / "output"


def charger(fichier: Path) -> pd.DataFrame:
    d = json.loads(fichier.read_text(encoding="utf-8"))
    ts_name = {t["@id"]: t["name"] for t in d["timeSets"]}
    dr_name = {r["@id"]: r["name"] for r in d["dateRanges"]}

    rows = []
    for route in d["routes"]:
        for s in route["summaries"]:
            rows.append({
                "route": route["routeName"],
                "date_range": dr_name.get(s["dateRange"]),
                "creneau": ts_name.get(s["timeSet"]),
                "distance_km": s["distance"] / 1000,
                "vitesse_harmonique_kmh": s["harmonicAverageSpeed"],
                "temps_median_s": s["medianTravelTime"],
                "temps_moyen_s": s["averageTravelTime"],
                "planning_time_index": s.get("planningTimeIndex"),
                "echantillon_moy": s["averageSampleSize"],
            })
    return pd.DataFrame(rows)


def main() -> None:
    d = pd.concat([charger(SRC / "batch1.json"), charger(SRC / "batch2.json")], ignore_index=True)
    print(f"{d.route.nunique()} routes | {d.creneau.nunique()} creneaux | {len(d)} lignes")

    d["heure"] = d["creneau"].str.extract(r"Semaine (\d+)h").astype(float)
    d["weekend"] = d["creneau"].str.contains("Week-end")
    semaine = d[d["heure"].notna()].copy()

    print("\n=== courbe horaire (semaine, moyenne des routes, vitesse harmonique km/h) ===")
    courbe = semaine.groupby("heure")["vitesse_harmonique_kmh"].mean().round(1)
    print(courbe.to_string())

    print("\n=== routes les moins fiables (planning time index max sur la journee) ===")
    pti = semaine.groupby("route")["planning_time_index"].max().sort_values(ascending=False)
    print(pti.head(12).round(2).to_string())
    print("\n=== routes les plus fiables ===")
    print(pti.tail(8).round(2).to_string())

    print("\n=== routes les plus lentes (vitesse harmonique minimale en semaine, heure de pointe) ===")
    pointe = semaine[semaine["heure"].between(6, 9) | semaine["heure"].between(15, 18)]
    lent = pointe.groupby("route")["vitesse_harmonique_kmh"].min().sort_values()
    print(lent.head(12).round(1).to_string())

    # synthese par route : vitesse pointe matin/soir, creux, we, pti max
    synth = semaine.groupby("route").apply(lambda g: pd.Series({
        "distance_km": g["distance_km"].iloc[0],
        "v_pointe_matin_kmh": g.loc[g.heure.between(7, 8), "vitesse_harmonique_kmh"].mean(),
        "v_pointe_soir_kmh": g.loc[g.heure.between(16, 17), "vitesse_harmonique_kmh"].mean(),
        "v_creux_kmh": g.loc[g.heure.between(10, 13), "vitesse_harmonique_kmh"].mean(),
        "pti_max": g["planning_time_index"].max(),
        "echantillon_min": g["echantillon_moy"].min(),
    }), include_groups=False).round(2)
    we = d[d.weekend].set_index("route")["vitesse_harmonique_kmh"].rename("v_weekend_kmh")
    synth = synth.join(we).sort_values("v_pointe_matin_kmh")

    semaine.to_csv(OUT / "traffic_stats_juillet_routes.csv", index=False, encoding="utf-8-sig")
    synth.to_csv(OUT / "traffic_stats_juillet_synthese.csv", encoding="utf-8-sig")
    print(f"\n=== synthese par route (extrait) ===")
    print(synth.head(15).to_string())
    print(f"\n-> data/output/traffic_stats_juillet_routes.csv + traffic_stats_juillet_synthese.csv")
    print("\nSource : TomTom Traffic Stats (Route Analysis), juillet 2026 -- usage editorial "
          "autorise par TomTom (V. Martinier, 2026-09-14), source a mentionner, chiffres non derives.")


if __name__ == "__main__":
    main()
