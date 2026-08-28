"""
Volet "environnement" pour les communes candidates.

- Qualite de l'air : indice ATMO journalier par commune, 1er janvier -> aujourd'hui 2026
  (`data/raw/atmo/ind_atmo_5962_2026.csv`, WFS Atmo France). Codes : 1 Bon, 2 Moyen, 3 Degrade,
  4 Mauvais, 5 Tres mauvais.
- Artificialisation des sols (flux) : % du territoire communal artificialise entre 2009 et 2024
  (CEREMA / Observatoire de l'artificialisation, `conso2009-2024-resultats-com.csv` du retraite).
- Impermeabilisation des sols (stock) : part de surface impermeabilisee en 2021 + evolution
  2018->2021 (CEREMA, `imper_commune.csv` du retraite).

Tous "moins c'est mieux" (Inverser).

Sortie : data/output/environnement_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
RETRAITE = Path("D:/Classement_retraite/raw")
ATMO = ROOT / "data" / "raw" / "atmo" / "ind_atmo_5962_2026.csv"
ARTIF = RETRAITE / "conso2009-2024-resultats-com.csv"
IMPER = RETRAITE / "imper_commune.csv"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "environnement_communes_candidates.csv"


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

    # --- qualite de l'air ---
    a = pd.read_csv(ATMO, dtype={"code_zone": str})  # deja filtre type_zone='commune' 59/62 au telechargement
    a["date"] = pd.to_datetime(a["date_ech"], errors="coerce")
    a = a[a["date"] <= pd.Timestamp("today").normalize()]
    a["q"] = pd.to_numeric(a["code_qual"], errors="coerce")
    a = a.dropna(subset=["q"])
    a["code_insee"] = a["code_zone"].map(lambda c: passage.get(c, c))
    air = a.groupby("code_insee").agg(
        indice_atmo_moyen=("q", "mean"),
        air_pct_jours_bons=("q", lambda x: (x <= 2).mean() * 100),
        air_pct_jours_degrades=("q", lambda x: (x >= 3).mean() * 100),
        air_pct_jours_mauvais=("q", lambda x: (x >= 4).mean() * 100),
        air_nb_jours=("q", "count"),
    ).round(2).reset_index()
    res = res.merge(air, on="code_insee", how="left")

    # --- artificialisation (flux 2009-2024) ---
    art = pd.read_csv(ARTIF, sep=";", dtype={"idcom": str}, usecols=["idcom", "artcom0924"])
    art["code_insee"] = art["idcom"].map(lambda c: passage.get(c, c))
    art["artcom0924"] = pd.to_numeric(art["artcom0924"].astype(str).str.replace(",", "."), errors="coerce")
    art = art.groupby("code_insee", as_index=False)["artcom0924"].mean()
    res = res.merge(art.rename(columns={"artcom0924": "artif_pct_2009_2024"}), on="code_insee", how="left")

    # --- impermeabilisation (stock 2021 + flux 2018-2021) ---
    imp = pd.read_csv(IMPER, sep=None, engine="python", dtype={"commune_code": str},
                      usecols=["commune_code", "pourcent_imper_2", "flux_percent_1_2"])
    imp["code_insee"] = imp["commune_code"].map(lambda c: passage.get(c, c))
    for c in ["pourcent_imper_2", "flux_percent_1_2"]:
        imp[c] = pd.to_numeric(imp[c], errors="coerce")
    imp = imp.groupby("code_insee", as_index=False)[["pourcent_imper_2", "flux_percent_1_2"]].mean()
    res = res.merge(imp.rename(columns={"pourcent_imper_2": "imper_pct_2021",
                                        "flux_percent_1_2": "imper_flux_2018_2021"}),
                    on="code_insee", how="left")
    res = res.round(2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # --- recap ---
    print(f"communes : {len(res)} | colonnes : {len(res.columns)}")
    print(f"air : jours de donnees mediane {res['air_nb_jours'].median():.0f} "
          f"({res['air_nb_jours'].min():.0f}-{res['air_nb_jours'].max():.0f})")
    for c in ["indice_atmo_moyen", "air_pct_jours_degrades", "air_pct_jours_mauvais",
              "artif_pct_2009_2024", "imper_pct_2021"]:
        print(f"  {c:24s}: mediane {res[c].median():6.2f} | p10 {res[c].quantile(.1):6.2f} | p90 {res[c].quantile(.9):6.2f} | NaN {res[c].isna().sum()}")
    print("\n--- 8 communes air le moins bon (indice moyen) ---")
    print(res.nlargest(8, "indice_atmo_moyen")[["commune", "dep", "indice_atmo_moyen", "air_pct_jours_degrades", "air_pct_jours_mauvais"]].to_string(index=False))
    print("\n--- 8 communes les plus impermeabilisees ---")
    print(res.nlargest(8, "imper_pct_2021")[["commune", "dep", "imper_pct_2021", "artif_pct_2009_2024"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
