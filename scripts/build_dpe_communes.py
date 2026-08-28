"""
Volet "performance energetique du parc / passoires thermiques" pour les communes candidates.

Source : ADEME, "DPE Logements existants (depuis juillet 2021)", agregats par commune
(data/raw/ademe/dpe_agg_5962.csv, produit par download_dpe_ademe.py). Millesime : cumul
juillet 2021 -> aout 2026 (DPE nouvelle methode, opposable).

Indicateurs :
  part_passoires_pct   = (F + G) / total       -> logements F/G, interdiction progressive de louer
  part_dpe_abc_pct     = (A + B + C) / total    -> parc performant
  dpe_cout_moyen_eur   = cout annuel moyen des 5 usages (chauffage, ECS, clim, eclairage, aux.)
  dpe_conso_ep_m2      = consommation moyenne en energie primaire (kWh/m2/an)

LIMITE MAJEURE (a documenter) : ce n'est PAS le parc complet. Seuls les logements ayant fait
l'objet d'un DPE depuis 07/2021 (ventes, mises en location, renovations, quelques volontaires).
Sur-representation des logements en transaction. Biais possible vers le locatif (plus de
passoires) dans les grandes villes. A lire comme un PROXY, pas un recensement.
On garde dpe_n (taille de l'echantillon) pour ponderer la confiance.

Sortie : data/output/dpe_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "ademe" / "dpe_agg_5962.csv"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "dpe_communes_candidates.csv"
LETTERS = list("ABCDEFG")


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
    df = pd.read_csv(SRC, dtype={"code_insee": str})
    df["code_insee"] = df["code_insee"].map(lambda c: passage.get(c, c))

    # moyennes ponderees par le nb de DPE lors de l'agregation des communes fusionnees
    for m in ["cout_moyen_eur", "conso_ep_m2_moyen", "ges_m2_moyen"]:
        df[f"_w_{m}"] = df[m] * df["dpe_total"]
    agg = {f"dpe_{L}": "sum" for L in LETTERS}
    agg["dpe_total"] = "sum"
    for m in ["cout_moyen_eur", "conso_ep_m2_moyen", "ges_m2_moyen"]:
        agg[f"_w_{m}"] = "sum"
    df = df.groupby("code_insee", as_index=False).agg(agg)
    for m in ["cout_moyen_eur", "conso_ep_m2_moyen", "ges_m2_moyen"]:
        df[m] = df[f"_w_{m}"] / df["dpe_total"]

    df["part_passoires_pct"] = ((df["dpe_F"] + df["dpe_G"]) / df["dpe_total"] * 100).round(1)
    df["part_dpe_abc_pct"] = ((df["dpe_A"] + df["dpe_B"] + df["dpe_C"]) / df["dpe_total"] * 100).round(1)
    df["part_dpe_g_pct"] = (df["dpe_G"] / df["dpe_total"] * 100).round(1)

    cand = pd.read_csv(CAND, dtype={"code_insee": str})
    res = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].merge(
        df[["code_insee", "dpe_total", "part_passoires_pct", "part_dpe_g_pct", "part_dpe_abc_pct",
            "cout_moyen_eur", "conso_ep_m2_moyen", "ges_m2_moyen"]],
        on="code_insee", how="left")
    res = res.rename(columns={"dpe_total": "dpe_n", "cout_moyen_eur": "dpe_cout_moyen_eur",
                              "conso_ep_m2_moyen": "dpe_conso_ep_m2", "ges_m2_moyen": "dpe_ges_m2"})
    res["dpe_cout_moyen_eur"] = res["dpe_cout_moyen_eur"].round(0)
    res["dpe_conso_ep_m2"] = res["dpe_conso_ep_m2"].round(0)
    res["dpe_ges_m2"] = res["dpe_ges_m2"].round(1)
    res["dpe_echantillon_faible"] = res["dpe_n"] < 50

    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # ---------------------------------------------------------------- recap
    print(f"communes : {len(res)} | DPE total couverts : {res['dpe_n'].sum():,.0f}".replace(",", " "))
    print(f"echantillon < 50 DPE : {res['dpe_echantillon_faible'].sum()} communes")
    for c in ["part_passoires_pct", "part_dpe_g_pct", "part_dpe_abc_pct", "dpe_cout_moyen_eur", "dpe_conso_ep_m2"]:
        v = res[c]
        print(f"  {c:22s}: med {v.median():8.1f} | p10 {v.quantile(.1):8.1f} | p90 {v.quantile(.9):8.1f} | NaN {v.isna().sum()}")

    mel = res.groupby(res["dans_MEL"].map({True: "MEL", False: "hors MEL"}))
    print("\n  MEL vs hors MEL (medianes) :")
    print(mel[["part_passoires_pct", "dpe_cout_moyen_eur", "dpe_conso_ep_m2"]].median().to_string())

    print("\n--- 15 communes le + de passoires (pop >= 5000) ---")
    big = res[res["PMUN"] >= 5000]
    print(big.nlargest(15, "part_passoires_pct")[
        ["commune", "dep", "PMUN", "dpe_n", "part_passoires_pct", "dpe_cout_moyen_eur", "dpe_conso_ep_m2"]].to_string(index=False))
    print("\n--- 15 communes le - de passoires (pop >= 5000) ---")
    print(big.nsmallest(15, "part_passoires_pct")[
        ["commune", "dep", "PMUN", "dpe_n", "part_passoires_pct", "dpe_cout_moyen_eur"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
