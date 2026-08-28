"""
Volet "cadre urbain / logement" pour les communes candidates.

- Logement (Insee RP 2023, base chiffres cles logement, geo 01/01/2026) :
  part de logements vacants, part de proprietaires, part de menages sans voiture / avec 2+
  voitures (motorisation = revelateur de dependance auto), part de maisons.
- Prix / loyers : voir build_immobilier_communes.py (DVF transactions reelles + Carte des loyers).
- Dynamique demographique 2016 -> 2022 (Insee, evol. et structure de la population).

Sortie : data/output/cadre_urbain_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "data" / "raw" / "insee" / "base_cc_logement_2023" / "base_cc_logement_2023.xlsx"
POP = ROOT / "data" / "raw" / "insee" / "evol_struct_pop_2022" / "base-cc-evol-struct-pop-2022.CSV"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "cadre_urbain_communes_candidates.csv"


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

    # --- logement RP 2023 (deja geo 2026) ---
    lg = pd.read_excel(LOG, sheet_name="COM_2023", engine="calamine", dtype=str)
    lg = lg.rename(columns={lg.columns[0]: "code_insee"})
    num = {"Logements (princ)": "tot", "Logements vacants (princ)": "vac", "Maisons (princ)": "mais",
           "Résid princ occupées Propriétaires (princ)": "prop", "Résid principales (princ)": "rp",
           "Résid princ HLM louée vide (princ)": "hlm",
           "Ménages au moins une voiture (princ)": "men_1v", "Ménages (princ)": "men",
           "Ménages deux voitures ou plus (princ)": "men_2v"}
    for src, dst in num.items():
        lg[dst] = pd.to_numeric(lg[src], errors="coerce")
    lg["code_insee"] = lg["code_insee"].map(lambda c: passage.get(c, c))
    lg = lg.groupby("code_insee", as_index=False)[list(num.values())].sum()
    lg["part_logts_vacants"] = (lg["vac"] / lg["tot"] * 100).round(1)
    lg["part_maisons"] = (lg["mais"] / lg["tot"] * 100).round(1)
    lg["part_proprietaires"] = (lg["prop"] / lg["rp"] * 100).round(1)
    lg["part_hlm"] = (lg["hlm"] / lg["rp"] * 100).round(1)
    lg["part_menages_sans_voiture"] = ((1 - lg["men_1v"] / lg["men"]) * 100).round(1)
    lg["part_menages_2voit_plus"] = (lg["men_2v"] / lg["men"] * 100).round(1)
    res = res.merge(lg[["code_insee", "part_logts_vacants", "part_maisons", "part_proprietaires",
                        "part_hlm", "part_menages_sans_voiture", "part_menages_2voit_plus"]],
                    on="code_insee", how="left")

    # prix / loyers immobilier -> desormais dans build_immobilier_communes.py (DVF + Carte des loyers)

    # --- dynamique demographique 2016 -> 2022 ---
    pop = pd.read_csv(POP, sep=";", dtype={"CODGEO": str}, usecols=["CODGEO", "P22_POP", "P16_POP"])
    pop["code_insee"] = pop["CODGEO"].map(lambda c: passage.get(c, c))
    for c in ["P22_POP", "P16_POP"]:
        pop[c] = pd.to_numeric(pop[c], errors="coerce")
    pop = pop.groupby("code_insee", as_index=False)[["P22_POP", "P16_POP"]].sum()
    pop["evol_pop_2016_2022_pct"] = ((pop["P22_POP"] / pop["P16_POP"] - 1) * 100).round(1)
    res = res.merge(pop[["code_insee", "evol_pop_2016_2022_pct"]], on="code_insee", how="left")
    res = res.round(2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # --- recap ---
    print(f"communes : {len(res)} | colonnes : {len(res.columns)}")
    for c in ["part_logts_vacants", "part_maisons", "part_proprietaires", "part_hlm",
              "part_menages_sans_voiture", "part_menages_2voit_plus", "evol_pop_2016_2022_pct"]:
        v = res[c]
        print(f"  {c:26s}: med {v.median():8.1f} | p10 {v.quantile(.1):8.1f} | p90 {v.quantile(.9):8.1f} | NaN {v.isna().sum()}")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
