"""
Analyse exploratoire : quelles communes perdent le plus de temps dans les bouchons
pour rejoindre Lille (piste d'article a part).

Source : data/interim/voiture_lille_tomtom.csv (TomTom, departAt mardi 08:00, trafic recurrent).
  tt_voiture_min       temps de pointe
  tt_voiture_libre_min temps a vide (sans trafic)
  tt_bouchons_min      minutes perdues (pointe - libre)
  tt_voiture_km        distance routiere

Indicateurs construits :
  indice_congestion     = pointe / libre            (1,00 = fluide ; 1,40 = +40 %)
  part_trajet_bouchons  = bouchons / pointe * 100    (% du trajet passe a l'arret/ralenti)
  min_perdues_jour      = bouchons * 2               (aller-retour)
  h_perdues_an          = bouchons * 2 * 220 / 60    (220 jours travailles)
  vitesse_pointe_kmh    = km / (pointe/60)

Sortie : data/output/bouchons_communes_lille.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
TT = ROOT / "data" / "interim" / "voiture_lille_tomtom.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
TRANSPORT = ROOT / "data" / "output" / "transport_communes_candidates.csv"
OUT = ROOT / "data" / "output" / "bouchons_communes_lille.csv"

JOURS_AN = 220


def main() -> None:
    tt = pd.read_csv(TT, dtype={"code_insee": str})
    cand = pd.read_csv(CAND, dtype={"code_insee": str})[
        ["code_insee", "commune", "dep", "PMUN", "dans_MEL"]]
    tr = pd.read_csv(TRANSPORT, dtype={"code_insee": str})[
        ["code_insee", "temps_sans_voiture_min", "mode_sans_voiture",
         "meilleur_temps_vers_lille_min", "gare_utile_sur_place"]]

    d = cand.merge(tt, on="code_insee", how="left").merge(tr, on="code_insee", how="left")
    d = d.rename(columns={"tt_voiture_min": "voiture_pointe_min",
                          "tt_voiture_libre_min": "voiture_libre_min",
                          "tt_bouchons_min": "bouchons_min",
                          "tt_voiture_km": "voiture_km"})

    d["indice_congestion"] = (d["voiture_pointe_min"] / d["voiture_libre_min"]).round(3)
    d["part_trajet_bouchons_pct"] = (d["bouchons_min"] / d["voiture_pointe_min"] * 100).round(1)
    d["min_perdues_jour"] = (d["bouchons_min"] * 2).round(0)
    d["h_perdues_an"] = (d["bouchons_min"] * 2 * JOURS_AN / 60).round(0)
    d["vitesse_pointe_kmh"] = (d["voiture_km"] / (d["voiture_pointe_min"] / 60)).round(0)
    d["vitesse_libre_kmh"] = (d["voiture_km"] / (d["voiture_libre_min"] / 60)).round(0)
    d["sans_alternative"] = d["temps_sans_voiture_min"].isna()

    d = d.sort_values("bouchons_min", ascending=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT, index=False, encoding="utf-8-sig")

    def show(df, cols, n=15):
        print(df.head(n)[cols].to_string(index=False))

    base = ["commune", "dep", "voiture_pointe_min", "voiture_libre_min", "bouchons_min",
            "indice_congestion", "part_trajet_bouchons_pct", "vitesse_pointe_kmh"]

    print(f"=== {len(d)} communes | mediane bouchons {d['bouchons_min'].median():.0f} min "
          f"| indice congestion median {d['indice_congestion'].median():.2f} ===\n")

    print("--- 1. MINUTES perdues (absolu) : top 15 ---")
    show(d.sort_values("bouchons_min", ascending=False), base)

    print("\n--- 2. INDICE DE CONGESTION (pointe/libre) : top 15 ---")
    show(d.sort_values("indice_congestion", ascending=False), base)

    print("\n--- 3. PART DU TRAJET dans les bouchons : top 15 ---")
    show(d.sort_values("part_trajet_bouchons_pct", ascending=False), base)

    print("\n--- 4. DOUBLE PEINE : bouchons eleves ET aucune alternative sans voiture ---")
    dp = d[d["sans_alternative"] & (d["bouchons_min"] >= d["bouchons_min"].median())]
    show(dp.sort_values("bouchons_min", ascending=False),
         base + ["PMUN"], n=20)
    print(f"  ({len(dp)} communes, {dp['PMUN'].sum():,.0f} hab)".replace(",", " "))

    print("\n--- 5. Les plus EPARGNEES (indice de congestion le plus bas, hors MEL) ---")
    show(d[~d["dans_MEL"]].sort_values("indice_congestion"), base)

    print("\n--- 6. Heures perdues par an (aller-retour, 220 j) : top 10 ---")
    show(d.sort_values("h_perdues_an", ascending=False),
         ["commune", "dep", "bouchons_min", "min_perdues_jour", "h_perdues_an", "PMUN"], n=10)

    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
