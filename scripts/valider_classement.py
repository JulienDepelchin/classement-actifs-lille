"""
Validation EXTERNE du classement : le score reflete-t-il des dynamiques reelles ?

Principe : une commune bien classee pour "vivre en travaillant a Lille" devrait, toutes choses
egales, ATTIRER des menages actifs et voir sa population croitre -- pas se vider. On confronte
`score_global` (data/output/scores_0_20.csv) aux signaux de dynamique recente
(data/output/dynamiques_communes_candidates.csv), qui n'entrent PAS dans le calcul du score.

Attention : correlation attendue MODEREE et positive, pas parfaite -- l'attractivite fait monter
les prix, que le classement penalise (prix inverse). Endogeneite assumee.

Sortie : impression console (+ data/output/validation_classement.csv)
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "data" / "output" / "scores_0_20.csv"
D = ROOT / "data" / "output" / "dynamiques_communes_candidates.csv"
OUT = ROOT / "data" / "output" / "validation_classement.csv"

SIGNAUX = {
    "taux_var_pop_16_22_pct_an": "+ (croissance pop)",
    "accel_pop_pts": "+ (accelere)",
    "arrivants_actifs_pour_1000hab": "+ (attire des actifs)",
    "taux_migration_entrante_pct": "+ (migration entrante)",
    "evol_prix_maison_24_25_pct": "+ (marche qui monte)",
    "part_actifs_tc_pct_2022": "+ (usage TC reel)",
    "evol_part_tc_16_22_pts": "+ (report vers le TC)",
    "indice_vieillissement_2022": "- (moins la commune vieillit, mieux c'est)",
}


def main() -> None:
    s = pd.read_csv(S, dtype={"code_insee": str})
    d = pd.read_csv(D, dtype={"code_insee": str})
    m = s.merge(d, on="code_insee", suffixes=("", "_d"))

    print(f"n = {len(m)} communes\n")
    print(f"{'signal':32s} {'r(score)':>9s}  attendu")
    rows = []
    for c, attendu in SIGNAUX.items():
        r = m["score_global"].corr(m[c])
        flag = "  <-- ?" if ((attendu.startswith("+") and r < 0.05) or
                             (attendu.startswith("-") and r > -0.05)) else ""
        print(f"{c:32s} {r:>9.2f}  {attendu}{flag}")
        rows.append({"signal": c, "r_score_global": round(r, 3), "sens_attendu": attendu})

    # deciles de score -> dynamique moyenne
    m["decile"] = pd.qcut(m["score_global"], 10, labels=False) + 1
    g = m.groupby("decile").agg(
        n=("code_insee", "size"),
        score=("score_global", "mean"),
        var_pop=("taux_var_pop_16_22_pct_an", "mean"),
        arrivants=("arrivants_actifs_pour_1000hab", "mean"),
        evol_prix=("evol_prix_maison_24_25_pct", "mean"),
        part_tc=("part_actifs_tc_pct_2022", "mean"),
        vieil=("indice_vieillissement_2022", "mean"),
    ).round(2)
    print("\n--- dynamique moyenne par decile de score (1 = pire, 10 = meilleur) ---")
    print(g.to_string())

    # top vs flop
    top, flop = m.nlargest(50, "score_global"), m.nsmallest(50, "score_global")
    print("\n--- top 50 vs flop 50 ---")
    for c in ["taux_var_pop_16_22_pct_an", "arrivants_actifs_pour_1000hab",
              "evol_prix_maison_24_25_pct", "part_actifs_tc_pct_2022", "indice_vieillissement_2022"]:
        print(f"  {c:32s}: top {top[c].median():7.2f} | flop {flop[c].median():7.2f}")
    print(f"\n  top 50 en declin (pop) : {int((top['taux_var_pop_16_22_pct_an'] < -0.3).sum())}/50")
    print(f"  flop 50 en croissance  : {int((flop['taux_var_pop_16_22_pct_an'] > 0.3).sum())}/50")

    # cas qui detonnent : bien classes mais en declin, mal classes mais en plein boom
    print("\n--- bien classes (top 120) MAIS pop en declin marque ---")
    x = m[(m["rang"] <= 120) & (m["taux_var_pop_16_22_pct_an"] <= -0.5)]
    print(x.nsmallest(10, "taux_var_pop_16_22_pct_an")[
        ["rang", "commune", "score_global", "taux_var_pop_16_22_pct_an", "evol_prix_maison_24_25_pct"]].to_string(index=False))
    print("\n--- mal classes (rang > 250) MAIS en plein boom ---")
    y = m[(m["rang"] > 250) & (m["taux_var_pop_16_22_pct_an"] >= 1.5)]
    print(y.nlargest(10, "taux_var_pop_16_22_pct_an")[
        ["rang", "commune", "score_global", "taux_var_pop_16_22_pct_an", "arrivants_actifs_pour_1000hab"]].to_string(index=False))

    pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
