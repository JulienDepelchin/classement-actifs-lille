"""
Compare l'instantane TomTom Routing (departAt mardi 8h, fige fin aout, dans le classement)
a la vraie distribution TomTom Traffic Stats de juillet 2026, sur l'echantillon de 18
communes stratifie sur le rang (build_verif_traffic_stats_sample.py).

Source : data/raw/traffic_stats/results/verif_classement.json (gitignore, brut TomTom).
Sortie : data/output/verif_classement_comparaison.csv
"""
from __future__ import annotations
import sys
import json
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    d = json.loads((ROOT / "data" / "raw" / "traffic_stats" / "results" / "verif_classement.json")
                    .read_text(encoding="utf-8"))
    ts_name = {t["@id"]: t["name"] for t in d["timeSets"]}

    rows = []
    for route in d["routes"]:
        commune = route["routeName"].replace(" -> Lille", "")
        vals = {}
        for s in route["summaries"]:
            vals[ts_name[s["timeSet"]]] = {
                "median_min": round(s["medianTravelTime"] / 60, 1),
                "moyenne_min": round(s["averageTravelTime"] / 60, 1),
                "pti": s.get("planningTimeIndex"),
                "n": round(s["averageSampleSize"]),
            }
        rows.append({"commune": commune,
                     "juillet_7_8h_median_min": vals.get("Semaine 7h-8h", {}).get("median_min"),
                     "juillet_8_9h_median_min": vals.get("Semaine 8h-9h", {}).get("median_min"),
                     "juillet_pti_7_8h": vals.get("Semaine 7h-8h", {}).get("pti"),
                     "juillet_n_7_8h": vals.get("Semaine 7h-8h", {}).get("n")})
    ts = pd.DataFrame(rows)

    ech = pd.read_csv(ROOT / "data" / "output" / "verif_classement_echantillon.csv", dtype={"code_insee": str})
    t = pd.read_csv(ROOT / "data" / "output" / "transport_communes_candidates.csv", dtype={"code_insee": str})
    m = ech.merge(t[["code_insee", "voiture_min", "voiture_bouchons_min"]], on="code_insee")
    m = m.merge(ts, on="commune", how="left")

    m["voiture_min_sans_parking"] = m["voiture_min"] - 8  # cf memoire : voiture_min = pointe TomTom + 8 (parking)
    m["ecart_7_8h_min"] = (m["voiture_min_sans_parking"] - m["juillet_7_8h_median_min"]).round(1)
    m["ecart_7_8h_pct"] = (m["ecart_7_8h_min"] / m["juillet_7_8h_median_min"] * 100).round(0)

    show = ["rang", "commune", "tranche", "voiture_min", "juillet_7_8h_median_min",
            "juillet_8_9h_median_min", "ecart_7_8h_min", "ecart_7_8h_pct", "juillet_pti_7_8h", "juillet_n_7_8h"]
    print(m[show].to_string(index=False))

    print(f"\necart median (instantane - juillet reel) : {m['ecart_7_8h_min'].median():.1f} min "
          f"({m['ecart_7_8h_pct'].median():.0f} %)")
    print(f"ecart min/max : {m['ecart_7_8h_min'].min():.1f} / {m['ecart_7_8h_min'].max():.1f} min")
    print(f"correlation rang Traffic Stats vs instantane (les 18 communes gardent-elles leur ordre ?) : "
          f"{m['voiture_min_sans_parking'].corr(m['juillet_7_8h_median_min']):.2f}")

    out = ROOT / "data" / "output" / "verif_classement_comparaison.csv"
    m[show].to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
