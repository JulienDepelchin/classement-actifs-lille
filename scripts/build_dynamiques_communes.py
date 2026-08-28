"""
Volet "dynamiques recentes" : la commune attire-t-elle / se vide-t-elle ? sert surtout a VALIDER
le classement (une commune bien classee devrait attirer des actifs, pas les perdre).

Sources (deja telechargees) :
- Insee, evolution et structure de la population (RP 2022, series 2011/2016/2022) :
  data/raw/insee/evol_struct_pop_2022/base-cc-evol-struct-pop-2022.CSV
  * trajectoire de population 2011 -> 2016 -> 2022 (accelere / ralentit / rebond / declin)
  * indice de vieillissement (65+ / -20 ans) 2011, 2016, 2022
  * taux d'arrivants ACTIFS : part des 25-54 ans qui, 1 an avant, residaient dans une autre
    commune (variable IRAN3P) -> migration residentielle entrante d'age actif
- Ecolab / Tableau de bord des mobilites durables, "part d'actifs selon le mode de transport"
  (RP 2016 + 2022) : data/raw/ecolab/part_modale_actifs_com.csv
  * part modale MESUREE transports en commun + velo (et son evolution 2016->2022)
- Prix DVF : evol_prix_maison_24_25_pct (deja dans immobilier_communes_candidates.csv)

Sortie : data/output/dynamiques_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
POP = ROOT / "data" / "raw" / "insee" / "evol_struct_pop_2022" / "base-cc-evol-struct-pop-2022.CSV"
MOD = ROOT / "data" / "raw" / "ecolab" / "part_modale_actifs_com.csv"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
IMMO = ROOT / "data" / "output" / "immobilier_communes_candidates.csv"
OUT = ROOT / "data" / "output" / "dynamiques_communes_candidates.csv"


def passage_map() -> dict[str, str]:
    m = pd.read_csv(MVT, dtype=str)
    mg = m[(m.TYPECOM_AV == "COM") & (m.TYPECOM_AP == "COM") & (m.COM_AV != m.COM_AP)
           & (m.DATE_EFF >= "2024-06-01")]
    mp = dict(zip(mg.COM_AV, mg.COM_AP))
    for _ in range(5):
        mp = {k: mp.get(v, v) for k, v in mp.items()}
    return mp


def taux_annuel(p_fin, p_deb, n):
    return ((p_fin / p_deb) ** (1 / n) - 1) * 100


def main() -> None:
    passage = passage_map()
    remap = lambda c: passage.get(c, c)
    cand = pd.read_csv(CAND, dtype={"code_insee": str})
    res = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].copy()

    # --- population : trajectoire + vieillissement + arrivants actifs ---
    use = ["CODGEO", "P22_POP", "P16_POP", "P11_POP",
           "P22_H0019", "P22_F0019", "P22_H65P", "P22_F65P",
           "P16_H0019", "P16_F0019", "P16_H65P", "P16_F65P",
           "P22_POP2554_IRAN3P",
           "P22_POP01P_IRAN1", "P22_POP01P_IRAN2", "P22_POP01P_IRAN3", "P22_POP01P_IRAN4",
           "P22_POP01P_IRAN5", "P22_POP01P_IRAN6", "P22_POP01P_IRAN7"]
    p = pd.read_csv(POP, sep=";", dtype={"CODGEO": str}, usecols=use)
    p["code_insee"] = p["CODGEO"].map(remap)
    for c in use[1:]:
        p[c] = pd.to_numeric(p[c], errors="coerce")
    p = p.groupby("code_insee", as_index=False).sum(numeric_only=True)

    p["taux_var_pop_16_22_pct_an"] = taux_annuel(p["P22_POP"], p["P16_POP"], 6).round(2)
    p["taux_var_pop_11_16_pct_an"] = taux_annuel(p["P16_POP"], p["P11_POP"], 5).round(2)
    p["accel_pop_pts"] = (p["taux_var_pop_16_22_pct_an"] - p["taux_var_pop_11_16_pct_an"]).round(2)

    p["indice_vieillissement_2022"] = ((p["P22_H65P"] + p["P22_F65P"])
                                       / (p["P22_H0019"] + p["P22_F0019"]) * 100).round(0)
    iv16 = (p["P16_H65P"] + p["P16_F65P"]) / (p["P16_H0019"] + p["P16_F0019"]) * 100
    p["evol_vieillissement_16_22_pts"] = (p["indice_vieillissement_2022"] - iv16).round(0)

    # migration residentielle entrante (tous ages) : IRAN >= 3 = residait dans une autre commune
    iran_tot = p[[f"P22_POP01P_IRAN{i}" for i in range(1, 8)]].sum(axis=1)
    iran_autre_com = p[[f"P22_POP01P_IRAN{i}" for i in range(3, 8)]].sum(axis=1)
    p["taux_migration_entrante_pct"] = (iran_autre_com / iran_tot * 100).round(1)
    # arrivants d'age actif (25-54) rapportes a la population : signal d'attractivite "menages actifs"
    p["arrivants_actifs_pour_1000hab"] = (p["P22_POP2554_IRAN3P"] / p["P22_POP"] * 1000).round(1)

    def dyn(r):
        t = r["taux_var_pop_16_22_pct_an"]
        a = r["accel_pop_pts"]
        if t >= 0.3 and a > 0:
            return "croissance qui accelere"
        if t >= 0.3:
            return "croissance qui ralentit"
        if t <= -0.3 and a < 0:
            return "declin qui s'aggrave"
        if t <= -0.3:
            return "declin qui se tasse"
        return "stable"
    p["dynamique_pop"] = p.apply(dyn, axis=1)

    res = res.merge(p[["code_insee", "P22_POP", "taux_var_pop_16_22_pct_an", "taux_var_pop_11_16_pct_an",
                       "accel_pop_pts", "dynamique_pop", "indice_vieillissement_2022",
                       "evol_vieillissement_16_22_pts", "taux_migration_entrante_pct",
                       "arrivants_actifs_pour_1000hab"]],
                    on="code_insee", how="left")

    # --- part modale mesuree (RP 2016 + 2022) ---
    m = pd.read_csv(MOD, dtype={"code_com": str, "annee": str}, encoding="utf-8")
    m["valeur"] = pd.to_numeric(m["valeur"], errors="coerce")
    m["code_insee"] = m["code_com"].map(remap)
    m = m[m["code_insee"].isin(res["code_insee"])]

    def part(annee, contient):
        s = m[(m["annee"] == annee) & (m["mode_transport"].str.contains(contient, case=False))]
        return s.groupby("code_insee")["valeur"].mean()

    d = pd.DataFrame(index=res["code_insee"])
    d["part_actifs_tc_pct_2022"] = part("2022", "commun").round(1)
    d["part_actifs_velo_pct_2022"] = part("2022", "vélo").round(1)
    d["part_actifs_voiture_pct_2022"] = part("2022", "voiture").round(1)
    d["evol_part_tc_16_22_pts"] = (part("2022", "commun") - part("2016", "commun")).round(1)
    res = res.merge(d.reset_index(), on="code_insee", how="left")

    # --- prix DVF (deja calcule) ---
    im = pd.read_csv(IMMO, dtype={"code_insee": str})[["code_insee", "evol_prix_maison_24_25_pct", "n_ventes_maison"]]
    res = res.merge(im, on="code_insee", how="left")

    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # ---------------------------------------------------------------- recap
    print(f"communes : {len(res)}")
    for c in ["taux_var_pop_16_22_pct_an", "accel_pop_pts", "indice_vieillissement_2022",
              "taux_migration_entrante_pct", "arrivants_actifs_pour_1000hab",
              "part_actifs_tc_pct_2022", "part_actifs_velo_pct_2022", "evol_part_tc_16_22_pts"]:
        v = res[c]
        print(f"  {c:30s}: med {v.median():7.1f} | p10 {v.quantile(.1):7.1f} | p90 {v.quantile(.9):7.1f} | NaN {v.isna().sum()}")
    print("\n  dynamique_pop :")
    print(res["dynamique_pop"].value_counts().to_string())
    for pair in [["Seclin", "Templeuve-en-Pévèle"], ["Gondecourt", "Cysoing"]]:
        print(f"\n  {pair}:")
        print(res[res.commune.isin(pair)][["commune", "taux_var_pop_16_22_pct_an", "accel_pop_pts",
              "dynamique_pop", "arrivants_actifs_pour_1000hab", "part_actifs_tc_pct_2022",
              "evol_prix_maison_24_25_pct"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
