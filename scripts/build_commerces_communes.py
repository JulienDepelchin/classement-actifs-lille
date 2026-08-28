"""
Volet "commerces / services du quotidien" pour les communes candidates.

Temps d'acces routier (voiture, Metric-OSRM, BPE millesime 2025, parquet reg=32) : moyenne
ponderee population sur les carreaux de la commune + temps mini. Pour les criteres a plusieurs
codes (supermarche, epicerie, poste), on prend le MIN par carreau avant d'agreger.

Densite : restaurants pour 1 000 habitants (BPE 2024 stock, code A504).

Sortie : data/output/commerces_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import duckdb

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
ACCES = ROOT / "data" / "raw" / "bpe_acces" / "donnees_2025_reg32.parquet"
STOCK = ROOT / "data" / "raw" / "bpe_stock" / "BPE24.parquet"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "commerces_communes_candidates.csv"

# nom -> liste de codes BPE (min par carreau si plusieurs)
ACCES_GROUPES = {
    "supermarche": ["B104", "B105"],   # hypermarche + supermarche
    "epicerie":    ["B201", "B202"],   # superette + epicerie (proximite)
    "boulangerie": ["B207"],
    "boucherie":   ["B204"],
    "poste":       ["A206", "A207", "A208"],  # bureau + relais + agence postale
    "decheterie":  ["A133"],
}


def passage_map() -> dict[str, str]:
    m = pd.read_csv(MVT, dtype=str)
    mg = m[(m.TYPECOM_AV == "COM") & (m.TYPECOM_AP == "COM") & (m.COM_AV != m.COM_AP)
           & (m.DATE_EFF >= "2024-06-01")]
    mp = dict(zip(mg.COM_AV, mg.COM_AP))
    for _ in range(5):
        mp = {k: mp.get(v, v) for k, v in mp.items()}
    return mp


def acces_par_commune(con, codes: list[str], name: str) -> pd.DataFrame:
    lst = ", ".join(f"'{c}'" for c in codes)
    return con.execute(f"""
        WITH g AS (
            SELECT idSrc, depcom, iris, pop, duree
            FROM read_parquet('{ACCES.as_posix()}')
            WHERE dep IN ('59','62') AND typeeq_id IN ({lst})
            QUALIFY row_number() OVER (PARTITION BY idSrc, depcom, iris ORDER BY duree) = 1
        )
        SELECT depcom AS code_insee,
               round(sum(duree*pop)/nullif(sum(pop),0), 1) AS acces_{name}_moy_min,
               round(min(duree), 1)                        AS acces_{name}_min_min
        FROM g GROUP BY depcom
    """).df()


def main() -> None:
    passage = passage_map()
    cand = pd.read_csv(CAND, dtype={"code_insee": str})
    res = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].copy()

    con = duckdb.connect()
    for name, codes in ACCES_GROUPES.items():
        t = acces_par_commune(con, codes, name)
        t["code_insee"] = t["code_insee"].map(lambda c: passage.get(c, c))
        t = t.groupby("code_insee", as_index=False).min()          # fusions geo 2026
        res = res.merge(t, on="code_insee", how="left")

    # --- stock BPE 2024 : densite restaurants + panier de commerces essentiels sur place ---
    # categories "essentielles" : au moins 1 equipement de chaque categorie present dans la commune
    ESSENTIELS = {
        "alimentaire_gd_surface": ["B104", "B105"],
        "boulangerie":            ["B207"],
        "epicerie":               ["B201", "B202"],
        "boucherie":              ["B204"],
        "pharmacie":              ["D307"],
        "poste":                  ["A206", "A207", "A208"],
        "banque":                 ["A203"],
    }
    if STOCK.exists():
        allc = [c for cats in ESSENTIELS.values() for c in cats] + ["A504"]
        lst = ", ".join(f"'{c}'" for c in allc)
        st = con.execute(f"""
            SELECT DEPCOM AS code_insee, TYPEQU, count(*) AS n
            FROM read_parquet('{STOCK.as_posix()}')
            WHERE (DEP = '59' OR DEP = '62') AND TYPEQU IN ({lst})
            GROUP BY 1, 2
        """).df()
        st["code_insee"] = st["code_insee"].map(lambda c: passage.get(c, c))
        piv = st.pivot_table(index="code_insee", columns="TYPEQU", values="n", aggfunc="sum", fill_value=0)
        piv = piv.reindex(columns=allc, fill_value=0).reset_index()

        cat = pd.DataFrame({"code_insee": piv["code_insee"]})
        for name, codes in ESSENTIELS.items():
            cat[name] = (piv[codes].sum(axis=1) > 0).astype(int)
        cat["commerces_essentiels_sur_place"] = cat[list(ESSENTIELS)].sum(axis=1)
        cat["n_resto"] = piv["A504"]
        res = res.merge(cat[["code_insee", "commerces_essentiels_sur_place", "n_resto"]],
                        on="code_insee", how="left")
        res["commerces_essentiels_sur_place"] = res["commerces_essentiels_sur_place"].fillna(0).astype(int)
        res["n_resto"] = res["n_resto"].fillna(0).astype(int)
        res["resto_pour_1000hab"] = (res["n_resto"] / res["PMUN"] * 1000).round(2)
    else:
        print("!! BPE24.parquet absent -> stock non calcule")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # --- recap ---
    print(f"communes : {len(res)} | colonnes : {len(res.columns)}")
    print("\n=== temps d'acces (min) : mediane | q90 | max | communes > 15 min ===")
    for name in ACCES_GROUPES:
        c = f"acces_{name}_moy_min"
        print(f"  {name:12s}: {res[c].median():5.1f} | {res[c].quantile(.9):5.1f} | {res[c].max():5.1f} | {(res[c] > 15).sum()}")
    if "commerces_essentiels_sur_place" in res:
        c = res["commerces_essentiels_sur_place"]
        print(f"\n=== panier de commerces essentiels sur place (0-7) : mediane {c.median():.0f} ===")
        print(c.value_counts().sort_index().to_string())
        print("  communes les plus depourvues (0-2) :",
              ", ".join(res[c <= 2].sort_values("PMUN", ascending=False)["commune"].head(8)))
        r = res["resto_pour_1000hab"]
        print(f"\n=== restaurants / 1000 hab : mediane {r.median():.1f} | p95 {r.quantile(.95):.1f} | max {r.max():.1f} ===")
        print(res.nlargest(5, "resto_pour_1000hab")[["commune", "PMUN", "n_resto", "resto_pour_1000hab"]].to_string(index=False))
    print("\n--- 6 communes les moins bien pourvues en commerces (supermarché) ---")
    print(res.nlargest(6, "acces_supermarche_moy_min")[["commune", "dep", "acces_supermarche_moy_min",
          "acces_boulangerie_moy_min", "acces_epicerie_moy_min"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
