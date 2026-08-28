"""
Volet "education / petite enfance" pour les communes candidates (thème nouveau vs le retraite).

- Temps d'acces routier (BPE 2025, Metric-OSRM) : creche, ecole maternelle, ecole elementaire,
  college, lycee.
- Presence sur le territoire communal (BPE 2024 stock) : ecole, college, creche.
- Places de creche (BPE 2024 stock, capacite D502) + taux de couverture ESTIME.
- Contexte : part des 0-14 ans (Insee, evol. et structure de la population 2022).

Codes BPE 2024 : C107 ecole maternelle, C108 ecole primaire (mat.+elem.), C109 ecole elementaire,
C201 college, C301/C302 lycee general-techno / professionnel, D502 EAJE (creche).

Sortie : data/output/education_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import glob
import numpy as np
import pandas as pd
import duckdb

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
ACCES = ROOT / "data" / "raw" / "bpe_acces" / "donnees_2025_reg32.parquet"
STOCK = ROOT / "data" / "raw" / "bpe_stock" / "BPE24.parquet"
POP = ROOT / "data" / "raw" / "insee" / "evol_struct_pop_2022" / "base-cc-evol-struct-pop-2022.CSV"
APPART = ROOT / "data" / "raw" / "insee" / "table_appartenance_2026" / "table-appartenance-geo-communes-2026.xlsx"
CNAF = ROOT / "data" / "raw" / "cnaf" / "txcouv_pe_epci.csv"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "education_communes_candidates.csv"

ACCES_GROUPES = {
    "creche":      ["D502"],
    "maternelle":  ["C107", "C108"],
    "elementaire": ["C108", "C109"],
    "college":     ["C201"],
    "lycee":       ["C301", "C302"],
}
SUR_PLACE = {
    "ecole":   ["C107", "C108", "C109"],
    "college": ["C201"],
    "creche":  ["D502"],
}


def passage_map() -> dict[str, str]:
    m = pd.read_csv(MVT, dtype=str)
    mg = m[(m.TYPECOM_AV == "COM") & (m.TYPECOM_AP == "COM") & (m.COM_AV != m.COM_AP)
           & (m.DATE_EFF >= "2024-06-01")]
    mp = dict(zip(mg.COM_AV, mg.COM_AP))
    for _ in range(5):
        mp = {k: mp.get(v, v) for k, v in mp.items()}
    return mp


def acces(con, codes, name):
    lst = ", ".join(f"'{c}'" for c in codes)
    return con.execute(f"""
        WITH g AS (
            SELECT idSrc, depcom, iris, pop, duree
            FROM read_parquet('{ACCES.as_posix()}')
            WHERE dep IN ('59','62') AND typeeq_id IN ({lst})
            QUALIFY row_number() OVER (PARTITION BY idSrc, depcom, iris ORDER BY duree) = 1
        )
        SELECT depcom AS code_insee,
               round(sum(duree*pop)/nullif(sum(pop),0),1) AS acces_{name}_moy_min,
               round(min(duree),1)                        AS acces_{name}_min_min
        FROM g GROUP BY depcom
    """).df()


def main() -> None:
    passage = passage_map()
    cand = pd.read_csv(CAND, dtype={"code_insee": str})
    res = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].copy()

    con = duckdb.connect()
    for name, codes in ACCES_GROUPES.items():
        t = acces(con, codes, name)
        t["code_insee"] = t["code_insee"].map(lambda c: passage.get(c, c))
        res = res.merge(t.groupby("code_insee", as_index=False).min(), on="code_insee", how="left")

    # --- stock BPE 2024 : presence + places de creche ---
    codes = sorted({c for v in SUR_PLACE.values() for c in v})
    st = con.execute(f"""
        SELECT DEPCOM AS code_insee, TYPEQU, count(*) n, sum(COALESCE(CAPACITE,0)) capa
        FROM read_parquet('{STOCK.as_posix()}')
        WHERE (DEP='59' OR DEP='62') AND TYPEQU IN ({", ".join(f"'{c}'" for c in codes)})
        GROUP BY 1,2
    """).df()
    st["code_insee"] = st["code_insee"].map(lambda c: passage.get(c, c))
    piv_n = st.pivot_table(index="code_insee", columns="TYPEQU", values="n", aggfunc="sum", fill_value=0)
    piv_n = piv_n.reindex(columns=codes, fill_value=0)
    capa_creche = st[st["TYPEQU"] == "D502"].groupby("code_insee")["capa"].sum()

    flags = pd.DataFrame({"code_insee": piv_n.index})
    for name, cs in SUR_PLACE.items():
        flags[f"{name}_sur_place"] = (piv_n[cs].sum(axis=1) > 0).astype(int).values
    flags["places_creche"] = flags["code_insee"].map(capa_creche).fillna(0).astype(int)
    res = res.merge(flags, on="code_insee", how="left")
    for c in ["ecole_sur_place", "college_sur_place", "creche_sur_place"]:
        res[c] = res[c].fillna(0).astype(int)
    res["places_creche"] = res["places_creche"].fillna(0).astype(int)

    # --- contexte demographique (Insee 2022) ---
    pop = pd.read_csv(POP, sep=";", dtype={"CODGEO": str}, usecols=["CODGEO", "P22_POP", "P22_POP0014"])
    pop["code_insee"] = pop["CODGEO"].map(lambda c: passage.get(c, c))
    pop = pop.groupby("code_insee", as_index=False)[["P22_POP", "P22_POP0014"]].sum()
    res = res.merge(pop, on="code_insee", how="left")
    res["part_0_14ans"] = (res["P22_POP0014"] / res["P22_POP"] * 100).round(1)
    # <3 ans estime = 0-14 x 3/15 ; places creche collective / 100 <3 ans (hors assistantes maternelles)
    enf_moins3 = (res["P22_POP0014"] * 3 / 15).clip(lower=1)
    res["places_creche_col_pour_100_moins3"] = (res["places_creche"] / enf_moins3 * 100).round(0)
    res = res.drop(columns=["P22_POP", "P22_POP0014"])

    # --- taux de couverture petite enfance CNAF (tous modes), a l'echelle de l'EPCI ---
    ap = pd.read_excel(APPART, sheet_name="COM", engine="calamine", dtype=str, header=5)[["CODGEO", "EPCI"]]
    ap["code_insee"] = ap["CODGEO"].map(lambda c: passage.get(c, c))
    epci_of = ap.drop_duplicates("code_insee").set_index("code_insee")["EPCI"]
    cnaf = pd.read_csv(CNAF, sep=";", dtype={"numepci": str})
    cnaf = cnaf[cnaf["annee"] == cnaf["annee"].max()]
    cmap = cnaf.set_index("numepci")
    res["_epci"] = res["code_insee"].map(epci_of)
    res["couverture_petite_enfance_epci"] = res["_epci"].map(cmap["txcouv_epci"]).round(1)
    res["couverture_creche_epci"] = res["_epci"].map(cmap["txcouv_eaje_epci"]).round(1)
    res["couverture_assmat_epci"] = res["_epci"].map(cmap["txcouv_am_ind_epci"]).round(1)
    res = res.drop(columns=["_epci"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # --- recap ---
    print(f"communes : {len(res)} | colonnes : {len(res.columns)}")
    print("\n=== temps d'acces (min) : mediane | q90 | max | > 15 min ===")
    for name in ACCES_GROUPES:
        c = f"acces_{name}_moy_min"
        print(f"  {name:12s}: {res[c].median():5.1f} | {res[c].quantile(.9):5.1f} | {res[c].max():5.1f} | {(res[c] > 15).sum()}")
    print(f"\n=== sur le territoire communal ===")
    for c in ["ecole_sur_place", "college_sur_place", "creche_sur_place"]:
        print(f"  {c:22s}: {int(res[c].sum())} / {len(res)}")
    print(f"\n=== petite enfance ===")
    print(f"  communes avec >=1 place de creche collective : {(res['places_creche'] > 0).sum()} / {len(res)}")
    print(f"  couverture petite enfance CNAF (tous modes, EPCI) : "
          f"mediane {res['couverture_petite_enfance_epci'].median():.0f} "
          f"| min {res['couverture_petite_enfance_epci'].min():.0f} | max {res['couverture_petite_enfance_epci'].max():.0f}")
    print(res.groupby("couverture_petite_enfance_epci").agg(n=("commune", "size")).sort_index().to_string())
    print(f"  part des 0-14 ans : mediane {res['part_0_14ans'].median():.1f} %")
    print("\n--- 8 communes sans creche ni école sur place ---")
    dep = res[(res.ecole_sur_place == 0)]
    print(dep.nlargest(8, "PMUN")[["commune", "dep", "PMUN", "acces_maternelle_moy_min", "acces_college_moy_min", "creche_sur_place"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
