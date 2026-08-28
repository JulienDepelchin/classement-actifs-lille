"""
Scoring du classement "Ou vivre quand on travaille a Lille".
Methode = notebook 12 du classement retraite, pilotee par data/output/grille_ponderation_lille.csv.

  1. table maitre : merge des fichiers criteres sur code_insee (411 communes)
  2. imputation   : mediane (defaut) ou 0, selon la colonne 'imputation'
  3. winsorisation: p95 / p90 (haute) ou p5_p95 (deux queues), selon la colonne 'winsor'
  4. normalisation: 0-20 min-max ; 'normal' = haut meilleur, 'inverser' = bas meilleur
  5. score_theme  = somme(score_critere x poids) / somme(poids)          -> 0-20
  6. score_global = somme(score_theme x etoiles_defaut) / somme(etoiles)  -> 0-20 (preset editorial)

Sorties (data/output/) :
  scores_0_20.csv        detail complet (scores criteres + themes + global + rang)
  classement_final.json  1 objet/commune : rang, score_global, score_<theme>  (appli Lovable)
  scores_detail.json     1 objet/commune : score_<critere>                    (appli Lovable)
"""
from __future__ import annotations
import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output"
GRILLE = OUT / "grille_ponderation_lille.csv"
CAND = OUT / "communes_candidates.csv"


def load_column(fichier: str, col: str) -> pd.Series:
    df = pd.read_csv(OUT / fichier, dtype={"code_insee": str})
    if col == "vols_vehicules_taux":  # fusion demandee dans la grille
        s = df["vols_de_vehicule_taux"].fillna(0) + df["vols_dans_vehicules_taux"].fillna(0)
    else:
        s = df[col]
    return pd.Series(s.values, index=df["code_insee"], name=col)


def winsorise(x: pd.Series, mode: str) -> pd.Series:
    if mode == "p95":
        return x.clip(upper=x.quantile(0.95))
    if mode == "p90":
        return x.clip(upper=x.quantile(0.90))
    if mode == "p5_p95":
        return x.clip(lower=x.quantile(0.05), upper=x.quantile(0.95))
    return x


def normalise(x: pd.Series, sens: str) -> pd.Series:
    lo, hi = x.min(), x.max()
    if hi == lo:
        return pd.Series(20.0, index=x.index)
    if sens == "normal":
        return (20 * (x - lo) / (hi - lo)).round(2)
    return (20 * (hi - x) / (hi - lo)).round(2)


def main() -> None:
    grille = pd.read_csv(GRILLE)
    cand = pd.read_csv(CAND, dtype={"code_insee": str})
    master = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].set_index("code_insee")

    themes = (grille[["theme", "theme_libelle", "etoiles_defaut"]]
              .drop_duplicates().set_index("theme"))

    score_cols_by_theme: dict[str, list[str]] = {t: [] for t in themes.index}
    poids: dict[str, int] = {}

    for r in grille.itertuples():
        raw = load_column(r.fichier_source, r.critere_colonne).reindex(master.index)
        win = str(r.winsor) if pd.notna(r.winsor) else ""
        x = pd.to_numeric(raw, errors="coerce")
        n_na = int(x.isna().sum())
        x = x.fillna(x.median()) if r.imputation == "mediane" else x.fillna(0.0)
        x = winsorise(x, win)
        sc = normalise(x, r.sens)
        col = f"score_{r.critere_colonne}"
        master[col] = sc
        score_cols_by_theme[r.theme].append(col)
        poids[col] = r.poids
        print(f"  {r.theme:15s} {r.critere_colonne:32s} {r.sens:8s} w{r.poids} "
              f"win={win or '-':6s} NA={n_na:3d}  score med {sc.median():5.1f}")

    # --- scores thematiques ---
    theme_score_cols = []
    for t, cols in score_cols_by_theme.items():
        w = np.array([poids[c] for c in cols])
        num = (master[cols].to_numpy() * w).sum(axis=1)
        tcol = f"score_{t}"
        master[tcol] = (num / w.sum()).round(2)
        theme_score_cols.append(tcol)

    # --- score global (preset d'etoiles par defaut) ---
    et = themes["etoiles_defaut"]
    num = sum(master[f"score_{t}"] * et[t] for t in themes.index)
    g_brut = num / et.sum()
    master["score_global_brut"] = g_brut.round(2)      # 0-20 theorique, en pratique tasse ~7-13
    # rescale min-max sur 0-20 pour la lisibilite du classement (rangs inchanges)
    lo, hi = g_brut.min(), g_brut.max()
    master["score_global"] = (20 * (g_brut - lo) / (hi - lo)).round(2)

    master = master.sort_values("score_global", ascending=False)
    master.insert(0, "rang", range(1, len(master) + 1))
    master = master.reset_index()

    # --- exports ---
    master.to_csv(OUT / "scores_0_20.csv", index=False, encoding="utf-8-sig")

    base = ["code_insee", "commune", "dep", "PMUN", "dans_MEL", "rang", "score_global"]
    (master[base + theme_score_cols]
     .to_json(OUT / "classement_final.json", orient="records", force_ascii=False, indent=1))
    detail_cols = ["code_insee", "commune"] + [
        c for c in master.columns if c.startswith("score_")
        and c not in theme_score_cols and c not in ("score_global", "score_global_brut")]
    (master[detail_cols]
     .to_json(OUT / "scores_detail.json", orient="records", force_ascii=False, indent=1))

    # ---------------------------------------------------------------- recap
    s = master["score_global"]
    print(f"\nscore_global : moy {s.mean():.2f} | med {s.median():.2f} | "
          f"min {s.min():.2f} | max {s.max():.2f} | ecart-type {s.std():.2f}")
    print("\nmediane des scores thematiques :")
    for t in themes.index:
        print(f"  {themes.loc[t,'theme_libelle']:28s} ({et[t]}*) : {master[f'score_{t}'].median():.1f}")

    show = ["rang", "commune", "dep", "PMUN", "score_global"] + theme_score_cols
    ren = {f"score_{t}": t[:4] for t in themes.index}
    print("\n=== TOP 25 ===")
    print(master.head(25)[show].rename(columns=ren).to_string(index=False))
    print("\n=== FLOP 20 ===")
    print(master.tail(20)[show].rename(columns=ren).to_string(index=False))

    print("\n--- TOP 15 hors MEL ---")
    print(master[~master["dans_MEL"]].head(15)[["rang", "commune", "dep", "score_global"]].to_string(index=False))
    print(f"\n-> {OUT/'scores_0_20.csv'} + classement_final.json + scores_detail.json")


if __name__ == "__main__":
    main()
