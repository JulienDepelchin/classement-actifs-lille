"""
Volet "risques naturels et miniers" pour les communes candidates.

Source : API Georisques (data/raw/georisques/georisques_communes.csv, via download_georisques.py).
  - gaspar/risques : risques recenses au DDRM (flags)
  - gaspar/catnat  : historique des arretes CatNat depuis 1982 (frequence)

Indicateur inedit pour un classement "ou vivre" en Nord/Pas-de-Calais :
  * ALEA MINIER (affaissements, effondrements, gaz de mine) : ~1/4 des communes candidates,
    tout l'ex-bassin minier -> contraintes de construction, remontees de nappe post-exhaure.
  * INONDATION : frequence reelle des arretes (Lys, Aa, Scarpe, Escaut, Deule + coulees de boue
    sur les plateaux limoneux). Tres actualise apres les crues du Pas-de-Calais 2023-2024.
  * SECHERESSE / retrait-gonflement des argiles : nb d'arretes CatNat secheresse = proxy des
    degats reels sur le bati (fissures) — discrimine la Pevele et le Melantois argileux.

Sortie : data/output/georisques_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "georisques" / "georisques_communes.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "georisques_communes_candidates.csv"


def main() -> None:
    g = pd.read_csv(SRC, dtype={"code_insee": str})
    cand = pd.read_csv(CAND, dtype={"code_insee": str})
    res = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].merge(
        g.drop(columns=["commune", "georisques_libelle"]), on="code_insee", how="left")

    for c in ["risque_inondation", "risque_remontee_nappe", "risque_minier",
              "risque_mvt_terrain", "risque_techno"]:
        res[c] = res[c].fillna(0).astype(int)
    res["nb_risques_naturels"] = (res["risque_inondation"] + res["risque_remontee_nappe"]
                                  + res["risque_minier"] + res["risque_mvt_terrain"])
    res["catnat_inondation_par_decennie"] = (res["catnat_inondation_n"] / 4.3).round(1)  # 1982->2025

    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # ---------------------------------------------------------------- recap
    print(f"communes : {len(res)} | colonnes : {len(res.columns)}")
    for c in ["risque_minier", "risque_inondation", "risque_remontee_nappe", "risque_mvt_terrain", "risque_techno"]:
        n = int(res[c].sum())
        pop = res.loc[res[c] == 1, "PMUN"].sum()
        print(f"  {c:22s}: {n:3d} communes | {pop:,.0f} hab".replace(",", " "))
    for c in ["catnat_inondation_n", "catnat_secheresse_n", "catnat_inondation_depuis_2010_n", "catnat_total_n"]:
        v = res[c]
        print(f"  {c:32s}: med {v.median():.0f} | p90 {v.quantile(.9):.0f} | max {v.max():.0f}")

    print(f"\n  communes avec aléa minier ET dans le périmètre MEL : "
          f"{int(((res['risque_minier'] == 1) & res['dans_MEL']).sum())}")

    print("\n--- 15 communes le plus souvent inondées (arrêtés CatNat inondation) ---")
    print(res.nlargest(15, "catnat_inondation_n")[
        ["commune", "dep", "PMUN", "catnat_inondation_n", "catnat_inondation_depuis_2010_n",
         "catnat_derniere_annee", "risque_minier"]].to_string(index=False))

    print("\n--- 15 communes le plus touchées par la sécheresse / argiles (arrêtés) ---")
    print(res.nlargest(15, "catnat_secheresse_n")[
        ["commune", "dep", "catnat_secheresse_n", "dans_MEL"]].to_string(index=False))

    print("\n--- cumul de risques : communes avec 4 risques naturels ---")
    print(res[res["nb_risques_naturels"] == 4][
        ["commune", "dep", "PMUN", "catnat_inondation_n", "catnat_secheresse_n"]].to_string(index=False))

    print("\n--- communes SANS aléa minier ni inondation DDRM (les plus sûres sur ces 2 axes) ---")
    safe = res[(res["risque_minier"] == 0) & (res["risque_inondation"] == 0)]
    print(f"  {len(safe)} communes ; ex. : {', '.join(safe.nsmallest(10, 'catnat_total_n')['commune'])}")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
