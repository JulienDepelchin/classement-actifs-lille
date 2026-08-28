"""
Volet "fiscalite locale" pour les communes candidates.

Source : DGFiP, "Fiscalite locale des particuliers" (data.economie.gouv.fr), exercice le plus
recent. `taux_global_tfb` = taux GLOBAL de taxe fonciere sur le bati (commune + interco +
syndicats + GEMAPI + TSE) -> c'est ce taux qui determine la facture, pas le seul taux communal.

Pour "ou acheter/vivre", la taxe fonciere est un cout recurrent : ~500 a 1500 EUR/an d'ecart
entre communes pour une meme maison.

Sortie : data/output/fiscalite_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "fiscalite" / "fiscalite_particuliers_5962.csv"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "fiscalite_communes_candidates.csv"


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
    f = pd.read_csv(SRC, dtype={"insee_com": str})
    f["code_insee"] = f["insee_com"].str.zfill(5).map(lambda c: passage.get(c, c))
    for c in ["taux_global_tfb", "taux_global_th", "thsurtaxrstau"]:
        f[c] = pd.to_numeric(f[c], errors="coerce")
    f = f.groupby("code_insee", as_index=False).agg(
        taux_taxe_fonciere_bati=("taux_global_tfb", "mean"),
        taux_taxe_habitation=("taux_global_th", "mean"),
        surtaxe_residence_secondaire_pct=("thsurtaxrstau", "max"),
    )
    f["surtaxe_residence_secondaire_pct"] = f["surtaxe_residence_secondaire_pct"].fillna(0)

    cand = pd.read_csv(CAND, dtype={"code_insee": str})
    res = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].merge(f, on="code_insee", how="left")
    res = res.round(2)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    v = res["taux_taxe_fonciere_bati"]
    print(f"communes : {len(res)} | NaN taux_tfb : {v.isna().sum()}")
    print(f"taux_taxe_fonciere_bati : med {v.median():.1f} | p10 {v.quantile(.1):.1f} | p90 {v.quantile(.9):.1f}")
    print("\n--- 10 taux les plus eleves (pop >= 3000) ---")
    b = res[res["PMUN"] >= 3000]
    print(b.nlargest(10, "taux_taxe_fonciere_bati")[["commune", "dep", "taux_taxe_fonciere_bati", "dans_MEL"]].to_string(index=False))
    print("\n--- 10 taux les plus bas (pop >= 3000) ---")
    print(b.nsmallest(10, "taux_taxe_fonciere_bati")[["commune", "dep", "taux_taxe_fonciere_bati", "dans_MEL"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
