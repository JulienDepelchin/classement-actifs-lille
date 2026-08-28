"""
Robustesse du classement : de combien un rang / une tranche bouge quand on perturbe les choix
subjectifs (poids d'etoiles par theme) ?

Methode : on recalcule score_global 1000 fois en tirant, pour chaque theme, un poids d'etoiles
au hasard dans {max(1, defaut-1), defaut, defaut+1} (uniforme). On observe la distribution du
rang et de la tranche de chaque commune.

Conclusion visee : le classement fin (rang 1, 2, 3...) n'est pas robuste ; les TRANCHES le sont.

Lit data/output/scores_0_20.csv (les score_<theme> + bonus/malus deja calcules) et
grille_ponderation_lille.csv (etoiles par defaut).

Sortie : data/output/robustesse_classement.csv (rang_median, rang_p05, rang_p95, tranche_modale,
         part_runs_meme_tranche)
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output"
N = 1000
RNG = np.random.default_rng(42)
TRANCHES = ["Défavorable", "Peu favorable", "Moyen", "Favorable", "Très favorable"]


def main() -> None:
    s = pd.read_csv(OUT / "scores_0_20.csv", dtype={"code_insee": str})
    grille = pd.read_csv(OUT / "grille_ponderation_lille.csv")
    themes = grille[["theme", "etoiles_defaut"]].drop_duplicates().set_index("theme")["etoiles_defaut"]
    tcols = [f"score_{t}" for t in themes.index]
    M = s[tcols].to_numpy()                       # 411 x n_themes

    ranks = np.zeros((len(s), N), dtype=int)
    tr = np.empty((len(s), N), dtype=object)
    for i in range(N):
        w = np.array([RNG.choice([max(1, d - 1), d, d + 1]) for d in themes.values], dtype=float)
        g = (M * w).sum(axis=1) / w.sum()
        order = pd.Series(g).rank(ascending=False, method="first").astype(int).to_numpy()
        ranks[:, i] = order
        q = pd.qcut(pd.Series(g), 5, labels=TRANCHES)
        tr[:, i] = q.to_numpy()

    res = s[["code_insee", "commune", "dep", "rang", "tranche", "score_global"]].copy()
    res["rang_median"] = np.median(ranks, axis=1).astype(int)
    res["rang_p05"] = np.percentile(ranks, 5, axis=1).astype(int)
    res["rang_p95"] = np.percentile(ranks, 95, axis=1).astype(int)
    res["rang_amplitude"] = res["rang_p95"] - res["rang_p05"]
    res["tranche_modale"] = [pd.Series(r).mode().iloc[0] for r in tr]
    res["part_runs_meme_tranche"] = [
        round((pd.Series(r) == t).mean(), 2) for r, t in zip(tr, res["tranche"])]

    res["position"] = np.where(res["part_runs_meme_tranche"] >= 0.75, "solide", "à nuancer")
    res.to_csv(OUT / "robustesse_classement.csv", index=False, encoding="utf-8-sig")

    # enrichit les exports Lovable avec la stabilite
    cf = pd.read_json(OUT / "classement_final.json")
    cf["code_insee"] = cf["code_insee"].astype(str).str.zfill(5)
    cf = cf.merge(res[["code_insee", "rang_p05", "rang_p95", "part_runs_meme_tranche", "position"]],
                  on="code_insee", how="left")
    cf.to_json(OUT / "classement_final.json", orient="records", force_ascii=False, indent=1)

    print(f"{N} tirages | poids d'etoiles perturbes +-1 par theme\n")
    print(f"amplitude de rang (p95 - p05) : med {res['rang_amplitude'].median():.0f} | "
          f"p90 {res['rang_amplitude'].quantile(.9):.0f} | max {res['rang_amplitude'].max():.0f}")
    print(f"communes qui restent dans leur tranche > 80 % des tirages : "
          f"{int((res['part_runs_meme_tranche'] > 0.8).sum())}/{len(res)}")
    print(f"communes qui restent dans leur tranche > 60 % des tirages : "
          f"{int((res['part_runs_meme_tranche'] > 0.6).sum())}/{len(res)}")

    print("\n--- stabilite par tranche ---")
    for t in TRANCHES[::-1]:
        sub = res[res["tranche"] == t]
        print(f"  {t:16s}: {len(sub):3d} communes | reste dans la tranche {sub['part_runs_meme_tranche'].mean()*100:.0f} % | "
              f"amplitude rang med {sub['rang_amplitude'].median():.0f}")

    print("\n--- 10 communes les plus instables (amplitude de rang) ---")
    print(res.nlargest(10, "rang_amplitude")[
        ["commune", "dep", "rang", "rang_p05", "rang_p95", "tranche", "part_runs_meme_tranche"]].to_string(index=False))
    print("\n--- top 10 : sont-elles solides ? ---")
    print(res.nsmallest(10, "rang")[
        ["commune", "rang", "rang_p05", "rang_p95", "part_runs_meme_tranche"]].to_string(index=False))
    print(f"\n-> {OUT/'robustesse_classement.csv'}")


if __name__ == "__main__":
    main()
