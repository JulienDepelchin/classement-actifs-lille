"""
Volet "securite" pour les communes candidates.

Source : SSMSI, base statistique communale de la delinquance enregistree (police + gendarmerie),
parquet recupere dans le projet retraite (`D:\\Classement_retraite\\raw\\ssmsi.parquet`,
millesimes 2016-2025, colonne cle `CODGEO_2025`).

Millesime : moyenne des taux 2022-2024 (robustesse — bcp de petites communes, ~45 % des cellules
sous secret statistique). Colonnes `*_2024` fournies aussi (annee de l'atlas officiel).
Le taux publie (`taux_pour_mille`) est utilise ; pour les cellules sous secret statistique
(`est_diffuse = 'ndiff'`), on prend l'estimation lissee SSMSI (`complement_info_taux`).

Unites SSMSI : cambriolages = pour 1 000 LOGEMENTS ; autres = pour 1 000 HABITANTS.
Sans effet sur le classement (normalisation par indicateur).

Indicateurs (tous "moins c'est mieux", a winsoriser p95 au scoring) :
  cambriolages_taux, vols_sans_violence_taux, vols_dans_vehicules_taux, vols_de_vehicule_taux,
  degradations_taux (+ violences_hors_famille_taux, non retenu par le retraite, fourni en option)

Sortie : data/output/securite_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SSMSI = Path("D:/Classement_retraite/raw/ssmsi.parquet")
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "securite_communes_candidates.csv"

ANNEES = [2022, 2023, 2024]
ANNEE_REF = 2024
INDICATEURS = {
    "Cambriolages de logement":                 "cambriolages_taux",
    "Vols sans violence contre des personnes":   "vols_sans_violence_taux",
    "Vols dans les véhicules":                   "vols_dans_vehicules_taux",
    "Vols de véhicule":                          "vols_de_vehicule_taux",
    "Destructions et dégradations volontaires":  "degradations_taux",
    "Violences physiques hors cadre familial":   "violences_hors_famille_taux",  # option
}


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

    d = pd.read_parquet(SSMSI, columns=["CODGEO_2025", "annee", "indicateur", "nombre",
                                        "taux_pour_mille", "est_diffuse", "complement_info_taux"])
    d = d[d["annee"].isin(ANNEES) & d["indicateur"].isin(INDICATEURS)].copy()
    d["code_insee"] = d["CODGEO_2025"].astype(str).map(lambda c: passage.get(c, c))
    d["taux"] = d["taux_pour_mille"].fillna(d["complement_info_taux"])   # publie, sinon estimation lissee
    d["var"] = d["indicateur"].map(INDICATEURS)

    res = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].copy()
    # moyenne 2022-2024 (principal) + 2024 seul (secondaire)
    moy = d.pivot_table(index="code_insee", columns="var", values="taux", aggfunc="mean").round(2)
    y24 = (d[d["annee"] == ANNEE_REF].pivot_table(index="code_insee", columns="var", values="taux", aggfunc="mean")
           .round(2).add_suffix("_2024"))
    res = res.merge(moy.reset_index(), on="code_insee", how="left").merge(y24.reset_index(), on="code_insee", how="left")

    # part des cellules sous secret statistique (transparence)
    secret = (d[d["annee"] == ANNEE_REF].assign(sec=lambda x: x["est_diffuse"] == "ndiff")
              .groupby("code_insee")["sec"].mean())
    res["securite_pct_estime"] = res["code_insee"].map(secret).round(2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # --- recap ---
    cols = [v for v in INDICATEURS.values() if v in res.columns]
    print(f"communes : {len(res)} | SSMSI moyenne {ANNEES[0]}-{ANNEES[-1]} (+ {ANNEE_REF} seul)")
    print(f"communes sans donnee : {res[cols[0]].isna().sum()}")
    print(f"\ntaux — mediane | p95 | max :")
    for c in cols:
        print(f"  {c:30s}: {res[c].median():6.2f} | {res[c].quantile(.95):6.2f} | {res[c].max():7.2f}")
    print(f"\ncellules sous secret statistique (part moyenne par commune) : {res['securite_pct_estime'].mean():.0%}")
    print("\n--- 8 communes les plus touchees (cambriolages) ---")
    print(res.nlargest(8, "cambriolages_taux")[["commune", "dep", "PMUN", "cambriolages_taux",
          "vols_sans_violence_taux", "degradations_taux"]].to_string(index=False))
    print("\n--- 8 communes les plus sures (cambriolages) ---")
    print(res.nsmallest(8, "cambriolages_taux")[["commune", "dep", "PMUN", "cambriolages_taux",
          "vols_sans_violence_taux", "degradations_taux"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
