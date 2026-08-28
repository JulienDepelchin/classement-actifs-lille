"""
Scoring v2 du classement "Ou vivre quand on travaille a Lille".
Pilote par data/output/grille_ponderation_lille.csv + grille_bonus_malus_lille.csv.

  0. perimetre : on ne garde que les communes a <= 63 min porte-a-porte de Lille
     (meilleur du TER realiste ou de la voiture en pointe) ; 60-63 min = "a la limite"
  1. table maitre : merge des fichiers criteres sur code_insee
  2. par critere : imputation -> transformation (log / winsor / aucune) -> min-max 0-20
  3. score_theme = somme(score_critere x poids) / somme(poids)                       -> 0-20
  4. bonus / malus : +-0,2 a 0,4 pt sur la note thematique concernee, puis borne [0 ; 20]
  5. score_global = somme(score_theme x etoiles_defaut) / somme(etoiles)   -> note /20, sans rescale
  6. rang + tranche (5 seuils de note fixes, cf. BINS)

Sorties (data/output/) :
  scores_0_20.csv        detail (scores criteres + themes + bonus/malus + global + rang + tranche)
  classement_final.json  1 objet/commune : rang, tranche, score_global, score_<theme>  (Lovable)
  scores_detail.json     1 objet/commune : score_<critere>                              (Lovable)
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
BM = OUT / "grille_bonus_malus_lille.csv"
CAND = OUT / "communes_candidates.csv"

# tranches par seuils de note fixes (choix editorial) sur la note /20 = moyenne
# ponderee des 10 notes thematiques. Toutes ces communes sont a < 1 h de Lille :
# la derniere tranche est "Peu adapte" (a ce projet de vie), pas "Defavorable".
TRANCHES = ["Peu adapté", "Peu favorable", "Moyen", "Favorable", "Très favorable"]
BINS = [-0.01, 9.0, 9.7, 10.5, 11.5, 20.01]


def load_col(fichier: str, col: str) -> pd.Series:
    df = pd.read_csv(OUT / fichier, dtype={"code_insee": str})
    if col == "vols_vehicules_taux":
        s = df["vols_de_vehicule_taux"].fillna(0) + df["vols_dans_vehicules_taux"].fillna(0)
    else:
        s = df[col]
    return pd.Series(s.values, index=df["code_insee"], name=col)


def transform(x: pd.Series, mode: str) -> pd.Series:
    if mode == "log":
        return np.log1p(x - min(0, x.min()))
    if mode == "winsor_p95":
        return x.clip(upper=x.quantile(0.95))
    if mode == "winsor_p90":
        return x.clip(upper=x.quantile(0.90))
    if mode == "winsor_p5_p95":
        return x.clip(lower=x.quantile(0.05), upper=x.quantile(0.95))
    return x


def normalise(x: pd.Series, sens: str) -> pd.Series:
    lo, hi = x.min(), x.max()
    if hi == lo:
        return pd.Series(20.0, index=x.index)
    return ((20 * (x - lo) / (hi - lo)) if sens == "normal"
            else (20 * (hi - x) / (hi - lo))).round(2)


def cond_mask(s: pd.Series, cond: str) -> pd.Series:
    op, _, val = cond.partition(" ")
    if op == "truthy":
        return s.fillna(0).astype(bool)
    if op == "falsy":
        return ~s.fillna(0).astype(bool)
    v = float(val)
    x = pd.to_numeric(s, errors="coerce")
    return {"==": x.eq(v), ">": x.gt(v), "<": x.lt(v)}[op].fillna(False)


def main() -> None:
    grille = pd.read_csv(GRILLE)
    bm = pd.read_csv(BM)
    cand = pd.read_csv(CAND, dtype={"code_insee": str})

    # --- perimetre "moins d'une heure de Lille" -------------------------------
    # temps porte-a-porte = min(TER realiste, voiture en pointe), rabattement
    # voiture+TER inclus. <= 60 min : coeur ; 60-63 min : a la limite (garde,
    # signale) ; > 63 min : hors perimetre (exclu du classement).
    SEUIL, TOL = 60.0, 63.0
    tps = (pd.read_csv(OUT / "transport_communes_candidates.csv", dtype={"code_insee": str})
             .set_index("code_insee")["meilleur_temps_vers_lille_min"])
    cand["temps_lille_min"] = cand["code_insee"].map(tps).fillna(999)
    cand["perimetre"] = np.where(cand["temps_lille_min"] <= SEUIL, "coeur",
                         np.where(cand["temps_lille_min"] <= TOL, "limite", "hors"))
    n_hors = int((cand["perimetre"] == "hors").sum())
    n_lim = int((cand["perimetre"] == "limite").sum())
    cand = cand[cand["perimetre"] != "hors"].copy()
    print(f"perimetre : {len(cand)} communes gardees "
          f"({n_hors} exclues > {TOL:.0f} min ; {n_lim} 'a la limite' {SEUIL:.0f}-{TOL:.0f} min)\n")

    master = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL",
                   "perimetre", "temps_lille_min"]].set_index("code_insee")

    themes = grille[["theme", "theme_libelle", "etoiles_defaut"]].drop_duplicates().set_index("theme")
    cols_by_theme = {t: [] for t in themes.index}
    poids = {}

    for r in grille.itertuples():
        raw = load_col(r.fichier_source, r.critere_colonne).reindex(master.index)
        x = pd.to_numeric(raw, errors="coerce")
        na = int(x.isna().sum())
        x = x.fillna(x.median()) if r.imputation == "mediane" else x.fillna(0.0)
        x = transform(x, r.transform)
        sc = normalise(x, r.sens)
        col = f"score_{r.critere_colonne}"
        master[col] = sc
        cols_by_theme[r.theme].append(col)
        poids[col] = r.poids
        print(f"  {r.theme:14s} {r.critere_colonne:32s} {r.sens:8s} w{r.poids} "
              f"{r.transform:13s} NA={na:3d}  med {sc.median():5.1f}")

    # --- scores thematiques ---
    theme_cols = []
    for t, cols in cols_by_theme.items():
        w = np.array([poids[c] for c in cols])
        master[f"score_{t}"] = ((master[cols].to_numpy() * w).sum(axis=1) / w.sum()).round(2)
        theme_cols.append(f"score_{t}")

    # --- bonus / malus ---
    print("\nbonus / malus :")
    for r in bm.itertuples():
        s = load_col(r.fichier_source, r.colonne).reindex(master.index)
        m = cond_mask(s, r.condition)
        master.loc[m, f"score_{r.theme}"] = (master.loc[m, f"score_{r.theme}"] + r.delta).clip(0, 20)
        print(f"  {r.theme:14s} {r.libelle:44s} {r.delta:+.2f}  -> {int(m.sum())} communes")
    for t in themes.index:
        master[f"score_{t}"] = master[f"score_{t}"].round(2)

    # --- note globale (preset defaut) + rang + tranche ---
    # PAS de rescale min-max : la note publiee est directement la moyenne ponderee
    # des 10 notes thematiques /20 (explicable, robuste aux ajouts/retraits de communes).
    et = themes["etoiles_defaut"]
    master["score_global"] = (sum(master[f"score_{t}"] * et[t] for t in themes.index)
                              / et.sum()).round(2)

    master = master.sort_values("score_global", ascending=False, kind="stable")
    master.insert(0, "rang", range(1, len(master) + 1))
    # tranches par SEUILS DE NOTE fixes (choix editorial), pas par quintiles : les tailles
    # refletent la distribution reelle (le "Moyen" gonfle -> c'est la realite).
    master["tranche"] = pd.cut(master["score_global"], bins=BINS, labels=TRANCHES)
    # le rang n'est fiable que dans le haut du tableau ; ailleurs -> fourchette (robustesse)
    master["top15"] = master["rang"] <= 15
    master = master.reset_index()

    # --- exports ---
    master.to_csv(OUT / "scores_0_20.csv", index=False, encoding="utf-8-sig")
    base = ["code_insee", "commune", "dep", "PMUN", "dans_MEL", "perimetre", "temps_lille_min",
            "rang", "top15", "tranche", "score_global"]
    master[base + theme_cols].to_json(OUT / "classement_final.json", orient="records",
                                      force_ascii=False, indent=1)
    detail = ["code_insee", "commune"] + [c for c in master.columns if c.startswith("score_")
              and c not in theme_cols and c != "score_global"]
    master[detail].to_json(OUT / "scores_detail.json", orient="records", force_ascii=False, indent=1)

    # ---------------------------------------------------------------- recap
    s = master["score_global"]
    print(f"\nnote /20 : moy {s.mean():.1f} | med {s.median():.1f} | "
          f"min {s.min():.2f} | max {s.max():.2f} | ecart-type {s.std():.1f}")
    print("\nmediane des scores thematiques :")
    for t in themes.index:
        print(f"  {themes.loc[t,'theme_libelle']:28s} ({et[t]}*) : {master[f'score_{t}'].median():.1f}")

    ren = {f"score_{t}": t[:5] for t in themes.index}
    show = ["rang", "commune", "dep", "tranche", "score_global"] + theme_cols
    print("\n=== TOP 15 (rang ordonnancable) ===")
    print(master.head(15)[show].rename(columns=ren).to_string(index=False))
    print(f"\n=== communes par tranche (seuils {BINS[1:-1]}) ===")
    vc = master["tranche"].value_counts().reindex(TRANCHES[::-1])
    for t, n in vc.items():
        pop = master.loc[master["tranche"] == t, "PMUN"].sum()
        print(f"  {t:16s} : {n:3d} communes | {pop:>10,.0f} hab")
    print("\n--- reperes ---")
    for n in ["Marcq-en-Barœul", "Cysoing", "Lille", "Villeneuve-d'Ascq", "Gondecourt",
              "Templeuve-en-Pévèle", "Fromelles", "Péronne-en-Mélantois", "Denain", "Gruson"]:
        r = master[master.commune == n]
        if len(r):
            print(f"  {n:24s} rang {int(r.rang.iloc[0]):3d}  {r.tranche.iloc[0]:16s} ({r.score_global.iloc[0]:.1f})")
    print(f"\n-> {OUT/'scores_0_20.csv'} + classement_final.json + scores_detail.json")


if __name__ == "__main__":
    main()
