"""
Volet "amenagements cyclables" pour les communes candidates.

Source : Ecolab / Tableau de bord des mobilites durables, indicateur "Lineaire d'amenagements
cyclables pour 1000 hab" (fournisseur Geovelo), data.gouv.fr. Millesimes 2022 -> 2025
(date_mesure = 1er janvier). Fichier commune national, filtre 59/62.
  data/raw/ecolab/cyclable_commune_national.csv

Format long : 1 ligne par commune x type_amenagement (7 types).
On distingue :
  - reseau UTILITAIRE (trajet domicile-travail) = pistes + bandes + double-sens + mixtes + voies bus
  - voies vertes = plutot loisir/nature, et gonfle artificiellement les petites communes rurales
    traversees par une veloroute -> sorti du pilier utilitaire, garde pour info
  - "autre" = non qualifie, souvent chemins forestiers -> ignore

L'indicateur natif est en km / 1000 hab : winsoriser au scoring (une veloroute dans un village
de 150 hab = valeur delirante). On fournit aussi le lineaire ABSOLU.

Sortie : data/output/cyclable_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "ecolab" / "cyclable_commune_national.csv"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "cyclable_communes_candidates.csv"

UTILITAIRE = ["pistes cyclables", "bandes cyclables", "double-sens cyclables",
              "amenagements mixtes", "voies bus partagees"]
AN_REF, AN_BASE = "2025", "2022"


def norm(s: pd.Series) -> pd.Series:
    # les libelles arrivent en latin-1 mal decode ("am\xe9nagements") selon la lecture ;
    # on retire les accents pour matcher de facon robuste
    return (s.str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii"))


def passage_map() -> dict[str, str]:
    m = pd.read_csv(MVT, dtype=str)
    mg = m[(m.TYPECOM_AV == "COM") & (m.TYPECOM_AP == "COM") & (m.COM_AV != m.COM_AP)
           & (m.DATE_EFF >= "2024-06-01")]
    mp = dict(zip(mg.COM_AV, mg.COM_AP))
    for _ in range(5):
        mp = {k: mp.get(v, v) for k, v in mp.items()}
    return mp


def main() -> None:
    passage = passage_map()
    cand = pd.read_csv(CAND, dtype={"code_insee": str})
    res = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].copy()

    df = pd.read_csv(SRC, dtype={"geocode_commune": str})
    df = df[df["geocode_commune"].str.startswith(("59", "62"))].copy()
    df["an"] = df["date_mesure"].str[:4]
    df["type"] = norm(df["type_amenagement"])
    df["km"] = pd.to_numeric(df["numerateur"], errors="coerce")
    df["pop"] = pd.to_numeric(df["denominateur"], errors="coerce")
    df["code_insee"] = df["geocode_commune"].map(lambda c: passage.get(c, c))

    util = [norm(pd.Series([t]))[0] for t in UTILITAIRE]

    def lineaire(an: str, types: list[str]) -> pd.Series:
        s = df[(df["an"] == an) & (df["type"].isin(types))]
        return s.groupby("code_insee")["km"].sum()

    # population du territoire (identique quel que soit le type, on prend le max par securite)
    pop25 = df[df["an"] == AN_REF].groupby("code_insee")["pop"].max()

    km_util = lineaire(AN_REF, util)
    km_pistes = lineaire(AN_REF, [norm(pd.Series(["pistes cyclables"]))[0]])
    km_vv = lineaire(AN_REF, [norm(pd.Series(["voies vertes"]))[0]])
    km_util_2022 = lineaire(AN_BASE, util)

    res = res.set_index("code_insee")
    res["cyclable_util_km"] = km_util.round(2)
    res["cyclable_util_km_1000hab"] = (km_util / pop25 * 1000).round(2)
    res["pistes_protegees_km_1000hab"] = (km_pistes / pop25 * 1000).round(2)
    res["part_amenagements_proteges_pct"] = (km_pistes / km_util * 100).round(0)
    res["voie_verte_km_1000hab"] = (km_vv / pop25 * 1000).round(2)
    res["cyclable_util_km_2022"] = km_util_2022.round(2)
    res["cyclable_util_evol_km"] = (km_util - km_util_2022).round(2)
    res["cyclable_util_evol_pct"] = ((km_util / km_util_2022 - 1) * 100).round(0)
    res = res.reset_index()

    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # ---------------------------------------------------------------- recap
    print(f"communes : {len(res)} | colonnes : {len(res.columns)}")
    for c in ["cyclable_util_km", "cyclable_util_km_1000hab", "pistes_protegees_km_1000hab",
              "part_amenagements_proteges_pct", "voie_verte_km_1000hab", "cyclable_util_evol_pct"]:
        v = res[c]
        print(f"  {c:32s}: med {v.median():7.2f} | p10 {v.quantile(.1):7.2f} | "
              f"p90 {v.quantile(.9):7.2f} | max {v.max():8.2f} | NaN {v.isna().sum()}")

    mel = res.groupby(res["dans_MEL"].map({True: "MEL", False: "hors MEL"}))
    print("\n  MEL vs hors MEL (medianes) :")
    print(mel[["cyclable_util_km_1000hab", "pistes_protegees_km_1000hab", "cyclable_util_evol_pct"]].median().to_string())

    print("\n--- 12 communes les mieux dotees (km utilitaire / 1000 hab, pop >= 5000) ---")
    big = res[res["PMUN"] >= 5000]
    print(big.nlargest(12, "cyclable_util_km_1000hab")[
        ["commune", "dep", "PMUN", "cyclable_util_km", "cyclable_util_km_1000hab",
         "part_amenagements_proteges_pct", "cyclable_util_evol_pct"]].to_string(index=False))
    print("\n--- 12 communes les moins dotees (pop >= 10000) ---")
    print(res[res["PMUN"] >= 10000].nsmallest(12, "cyclable_util_km_1000hab")[
        ["commune", "dep", "PMUN", "cyclable_util_km", "cyclable_util_km_1000hab", "cyclable_util_evol_pct"]].to_string(index=False))
    print("\n--- 10 plus fortes progressions 2022->2025 (pop >= 5000, base >= 5 km) ---")
    prog = res[(res["PMUN"] >= 5000) & (res["cyclable_util_km_2022"] >= 5)]
    print(prog.nlargest(10, "cyclable_util_evol_km")[
        ["commune", "dep", "cyclable_util_km_2022", "cyclable_util_km", "cyclable_util_evol_km", "cyclable_util_evol_pct"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
