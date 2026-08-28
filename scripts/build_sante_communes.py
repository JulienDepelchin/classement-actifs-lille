"""
Volet "sante / acces aux soins de premier recours" pour les communes candidates.

Source : DREES-Irdes, indicateur d'Accessibilite Potentielle Localisee (APL), millesime 2024
(methodologie la plus recente ; data.gouv.fr / data.drees).
L'APL est un indicateur COMMUNAL d'adequation offre/demande de soins qui tient compte de l'offre
des communes environnantes (decroissance avec la distance), du niveau d'activite des
professionnels et de la structure par age de la population.

Unites :
  - medecins generalistes : nombre de consultations/visites accessibles par habitant (standardise) et par an
  - infirmieres, kinesitherapeutes, sages-femmes, chirurgiens-dentistes : ETP pour 100 000 habitants

Plus la valeur est elevee, meilleur est l'acces. On retient aussi l'APL medecins generalistes
"de 65 ans ou moins" (offre hors medecins proches de la retraite) comme indicateur prospectif.

Sortie : data/output/sante_communes_candidates.csv  (1 ligne par commune candidate)

Geographie : commune 2024. Reagregee vers la geo 2026 via v_mvt_commune_2026 (memes fusions que
le perimetre), ponderation par population standardisee pour l'APL, somme pour les populations.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import duckdb

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
APL = ROOT / "data" / "raw" / "apl"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
BPE_PARQUET = ROOT / "data" / "raw" / "bpe_acces" / "donnees_2025_reg32.parquet"
OUT = ROOT / "data" / "output" / "sante_communes_candidates.csv"

# equipements BPE (domaine D) : temps d'acces routier Metric-OSRM, millesime 2025
BPE_TYPES = {
    "urgences": "D106",     # SAMU-SMUR + service d'accueil des urgences
    "maternite": "D107",    # gynecologie-obstetrique
    "hopital": "D101",      # etablissement de sante court sejour (MCO)
    "pharmacie": "D307",    # pharmacie d'officine
    "msp": "D113",          # maison de sante pluridisciplinaire (signal anti-desertification)
}

FILES = {
    "mg": ("apl_mg.xlsx", "APL aux médecins généralistes"),
    "mg_m65": ("apl_mg.xlsx", "APL aux médecins généralistes de 65 ans ou moins"),
    "inf": ("apl_inf.xlsx", None),
    "kine": ("apl_kine.xlsx", None),
    "dent": ("apl_dent.xlsx", None),
    "sf": ("apl_sf.xlsx", None),
}


def pick_col(df: pd.DataFrame, target: str | None) -> str:
    apl_cols = [c for c in df.columns if str(c).startswith("APL")]
    if target is None:
        return apl_cols[0]
    for c in apl_cols:
        if str(c).strip() == target.strip():
            return c
    raise KeyError(f"{target!r} absente ; colonnes APL = {apl_cols}")


def build_passage() -> dict[str, str]:
    m = pd.read_csv(MVT, dtype=str)
    mg = m[(m.TYPECOM_AV == "COM") & (m.TYPECOM_AP == "COM") & (m.COM_AV != m.COM_AP)
           & (m.DATE_EFF >= "2024-06-01")]
    mp = dict(zip(mg.COM_AV, mg.COM_AP))
    for _ in range(5):
        mp = {k: mp.get(v, v) for k, v in mp.items()}
    return mp


def read_apl_sheet(path: Path, sheet: str = "APL 2024") -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str, engine="calamine")
    hdr = raw.index[raw[0].astype(str).str.strip() == "Code commune INSEE"]
    if len(hdr) == 0:
        raise RuntimeError(f"entete introuvable dans {path.name}")
    h = int(hdr[0])
    df = pd.read_excel(path, sheet_name=sheet, header=h, dtype=str, engine="calamine")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={df.columns[0]: "code_insee", df.columns[1]: "libelle"})
    df = df[df["code_insee"].str.match(r"^\d[0-9AB]\d{3}$", na=False)].copy()
    return df


def main() -> None:
    passage = build_passage()
    cand = pd.read_csv(CAND, dtype={"code_insee": str})

    apl_cols = {}
    pop_std = None
    pop_tot = None
    for key, (fname, col) in FILES.items():
        df = read_apl_sheet(APL / fname)
        col = pick_col(df, col)
        val = pd.to_numeric(df[col].str.replace(",", "."), errors="coerce")
        std = pd.to_numeric(df[[c for c in df.columns if "standardisée" in str(c)][0]].str.replace(",", "."), errors="coerce")
        tot = pd.to_numeric(df[[c for c in df.columns if "totale" in str(c)][0]].str.replace(",", "."), errors="coerce")
        t = pd.DataFrame({"code_insee": df["code_insee"], f"apl_{key}": val,
                          "_std": std, "_tot": tot})
        t["code_insee"] = t["code_insee"].map(lambda c: passage.get(c, c))
        # reagregation geo 2026 : moyenne ponderee par pop standardisee
        g = t.groupby("code_insee").apply(
            lambda x: pd.Series({
                f"apl_{key}": np.average(x[f"apl_{key}"], weights=x["_std"].fillna(0) + 1e-9)
                if x[f"apl_{key}"].notna().any() else np.nan,
                "_std": x["_std"].sum(), "_tot": x["_tot"].sum(),
            }), include_groups=False).reset_index()
        apl_cols[key] = g[["code_insee", f"apl_{key}"]]
        if key == "mg":
            pop_std = g[["code_insee", "_std"]].rename(columns={"_std": "pop_std_sante"})
            pop_tot = g[["code_insee", "_tot"]].rename(columns={"_tot": "pop_totale_2022"})

    res = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].copy()
    for key, t in apl_cols.items():
        res = res.merge(t, on="code_insee", how="left")
    res = res.merge(pop_std, on="code_insee", how="left").merge(pop_tot, on="code_insee", how="left")

    # --- trajectoire : evolution APL medecins generalistes 2022 -> 2024 (meme methodo) ---
    #     NB DREES : la standardisation ne corrige pas le vieillissement -> lire en tendance.
    df22 = read_apl_sheet(APL / "apl_mg.xlsx", sheet="APL 2022")
    v22 = pd.to_numeric(df22[pick_col(df22, "APL aux médecins généralistes")].str.replace(",", "."), errors="coerce")
    s22 = pd.to_numeric(df22[[c for c in df22.columns if "standardisée" in str(c)][0]].str.replace(",", "."), errors="coerce")
    t22 = pd.DataFrame({"code_insee": df22["code_insee"].map(lambda c: passage.get(c, c)),
                        "apl22": v22, "std22": s22})
    g22 = (t22.groupby("code_insee")
           .apply(lambda x: np.average(x["apl22"], weights=x["std22"].fillna(0) + 1e-9)
                  if x["apl22"].notna().any() else np.nan, include_groups=False)
           .rename("apl_mg_2022").reset_index())
    res = res.merge(g22, on="code_insee", how="left")
    res["apl_mg_evol_pct"] = ((res["apl_mg"] - res["apl_mg_2022"]) / res["apl_mg_2022"] * 100)

    # --- temps d'acces routier BPE (urgences / maternite / hopital / pharmacie) ---
    con = duckdb.connect()
    types_sql = ", ".join(f"'{c}'" for c in BPE_TYPES.values())
    bpe = con.execute(f"""
        WITH d AS (
            SELECT depcom, typeeq_id, duree, pop
            FROM read_parquet('{BPE_PARQUET.as_posix()}')
            WHERE dep IN ('59','62') AND typeeq_id IN ({types_sql})
        )
        SELECT depcom, typeeq_id,
               sum(duree*pop)/nullif(sum(pop),0) AS duree_moy,
               min(duree)                        AS duree_min
        FROM d GROUP BY depcom, typeeq_id
    """).df()
    bpe["depcom"] = bpe["depcom"].map(lambda c: passage.get(c, c))
    code2name = {v: k for k, v in BPE_TYPES.items()}
    for typ, name in code2name.items():
        sub = bpe[bpe["typeeq_id"] == typ].groupby("depcom", as_index=False).agg(
            duree_moy=("duree_moy", "mean"), duree_min=("duree_min", "min"))
        sub = sub.rename(columns={"depcom": "code_insee",
                                  "duree_moy": f"acces_{name}_moy_min",
                                  "duree_min": f"acces_{name}_min_min"})
        res = res.merge(sub, on="code_insee", how="left")

    res = res.round(2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # --- controle / verif ---
    miss = res[res["apl_mg"].isna()]
    print(f"communes candidates : {len(res)} | APL medecin generaliste manquant : {len(miss)}")
    if len(miss):
        print("  ", miss["commune"].tolist())
    # reference nationale (toutes communes du fichier MG, ponderee pop standardisee)
    natdf = read_apl_sheet(APL / "apl_mg.xlsx")
    nv = pd.to_numeric(natdf["APL aux médecins généralistes"].str.replace(",", "."), errors="coerce")
    ns = pd.to_numeric(natdf[[c for c in natdf.columns if "standardisée" in str(c)][0]].str.replace(",", "."), errors="coerce")
    nat_mg = np.average(nv.dropna(), weights=ns[nv.notna()].fillna(0) + 1e-9)
    print(f"\nAPL medecins generalistes 2024 :")
    print(f"  France (pondere pop std)          : {nat_mg:.2f} consult./hab/an")
    for lbl, sub in [("candidats (411)", res), ("dont MEL", res[res.dans_MEL]), ("dont hors MEL", res[~res.dans_MEL])]:
        w = np.average(sub["apl_mg"].dropna(), weights=sub.loc[sub["apl_mg"].notna(), "pop_std_sante"].fillna(1))
        print(f"  {lbl:32s}: {w:.2f}  (min {sub.apl_mg.min():.2f} / med {sub.apl_mg.median():.2f} / max {sub.apl_mg.max():.2f})")
    print("\n--- 8 communes les moins bien dotees (APL MG) ---")
    print(res.nsmallest(8, "apl_mg")[["commune", "dep", "PMUN", "apl_mg", "apl_mg_m65", "apl_inf", "apl_kine", "apl_dent"]].to_string(index=False))
    print("\n--- 8 communes les mieux dotees (APL MG) ---")
    print(res.nlargest(8, "apl_mg")[["commune", "dep", "PMUN", "apl_mg", "apl_mg_m65", "apl_inf", "apl_kine", "apl_dent"]].to_string(index=False))

    print("\n=== temps d'acces routier BPE (min) ===")
    for name in BPE_TYPES:
        c = f"acces_{name}_moy_min"
        print(f"  {name:10s}: mediane {res[c].median():.1f} | q90 {res[c].quantile(.9):.1f} | max {res[c].max():.1f} "
              f"| communes > 20 min : {(res[c] > 20).sum()}")
    print("\n  communes les plus eloignees d'une maternite :")
    print(res.nlargest(6, "acces_maternite_moy_min")[["commune", "dep", "acces_maternite_moy_min", "acces_urgences_moy_min", "acces_pharmacie_moy_min"]].to_string(index=False))

    print("\n=== trajectoire APL medecins generalistes 2022 -> 2024 ===")
    e = res["apl_mg_evol_pct"].dropna()
    print(f"  evolution mediane : {e.median():+.1f} %  | communes en baisse : {(e < 0).sum()} / {len(e)}")
    print("  communes ou l'acces se degrade le plus :")
    print(res.nsmallest(6, "apl_mg_evol_pct")[["commune", "dep", "apl_mg_2022", "apl_mg", "apl_mg_evol_pct"]].round(2).to_string(index=False))

    print("\n=== maison de sante pluridisciplinaire (D113) ===")
    res["msp_sur_place"] = res["acces_msp_min_min"] <= 2
    print(f"  communes avec une MSP sur le territoire (acces <= 2 min) : {int(res['msp_sur_place'].sum())} / {len(res)}")
    res.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\n-> {OUT}  ({len(res.columns)} colonnes)")


if __name__ == "__main__":
    main()
