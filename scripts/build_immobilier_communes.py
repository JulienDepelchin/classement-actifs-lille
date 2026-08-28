"""
Volet "immobilier" pour les communes candidates -- sources OFFICIELLES.

PRIX de vente : DVF geolocalisees (transactions reelles DGFiP), millesimes 2023-2025 mis en commun.
  Filtres : nature_mutation = Vente ; type_local Maison / Appartement ; une mutation ne portant
  QUE sur ce type ; surface et prix/m2 dans des bornes plausibles. Mediane communale du prix/m2.
LOYERS d'annonce : "Carte des loyers" 2025 (indicateur predit par commune, CGDD/ANIL).

Remplace l'ancienne estimation SeLoger/MeilleursAgents (prix_avril_2026.xlsx).

Sortie : data/output/immobilier_communes_candidates.csv
"""
from __future__ import annotations
import sys
import gzip
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DVF_DIR = ROOT / "data" / "raw" / "dvf"
LOY_DIR = ROOT / "data" / "raw" / "loyers"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "immobilier_communes_candidates.csv"

ANNEES = ["2023", "2024", "2025"]
BORNES = {  # (surface_min, surface_max, prix_m2_min, prix_m2_max)
    "Maison": (20, 500, 300, 9000),
    "Appartement": (9, 300, 500, 9000),
}
COLS = ["id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere",
        "code_commune", "type_local", "surface_reelle_bati"]


def passage_map() -> dict[str, str]:
    m = pd.read_csv(MVT, dtype=str)
    mg = m[(m.TYPECOM_AV == "COM") & (m.TYPECOM_AP == "COM") & (m.COM_AV != m.COM_AP)
           & (m.DATE_EFF >= "2024-06-01")]
    mp = dict(zip(mg.COM_AV, mg.COM_AP))
    for _ in range(5):
        mp = {k: mp.get(v, v) for k, v in mp.items()}
    return mp


def load_dvf() -> pd.DataFrame:
    frames = []
    for an in ANNEES:
        for dep in ("59", "62"):
            with gzip.open(DVF_DIR / f"{dep}_{an}.csv.gz", "rt", encoding="utf-8") as f:
                d = pd.read_csv(f, usecols=COLS, dtype={"code_commune": str})
            d["annee"] = int(an)
            frames.append(d)
    return pd.concat(frames, ignore_index=True)


def ventes_m2(dvf: pd.DataFrame, type_local: str) -> pd.DataFrame:
    smin, smax, pmin, pmax = BORNES[type_local]
    d = dvf[(dvf["nature_mutation"] == "Vente") & (dvf["type_local"] == type_local)].copy()
    d["valeur_fonciere"] = pd.to_numeric(d["valeur_fonciere"], errors="coerce")
    d["surface_reelle_bati"] = pd.to_numeric(d["surface_reelle_bati"], errors="coerce")
    # une mutation qui touche plusieurs types de local OU plusieurs communes -> ecartee
    g = dvf.groupby("id_mutation")
    mono = g["type_local"].nunique().eq(1) & g["code_commune"].nunique().eq(1)
    d = d[d["id_mutation"].isin(mono[mono].index)]
    # agrege les lignes d'une meme mutation (plusieurs lots du meme type)
    a = d.groupby(["id_mutation", "code_commune", "annee"], as_index=False).agg(
        valeur=("valeur_fonciere", "first"), surface=("surface_reelle_bati", "sum"))
    a = a[(a["surface"].between(smin, smax)) & a["valeur"].gt(0)]
    a["prix_m2"] = a["valeur"] / a["surface"]
    a = a[a["prix_m2"].between(pmin, pmax)]
    return a


def load_loyers(name: str) -> pd.Series:
    d = pd.read_csv(LOY_DIR / name, sep=";", dtype={"INSEE_C": str}, encoding="latin-1")
    d["loy"] = pd.to_numeric(d["loypredm2"].astype(str).str.replace(",", "."), errors="coerce")
    return d.set_index("INSEE_C")["loy"]


def main() -> None:
    passage = passage_map()
    remap = lambda c: passage.get(c, c)
    cand = pd.read_csv(CAND, dtype={"code_insee": str})
    res = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].set_index("code_insee")

    dvf = load_dvf()
    dvf["code_commune"] = dvf["code_commune"].map(remap)

    for typ, pref in [("Maison", "maison"), ("Appartement", "appart")]:
        v = ventes_m2(dvf, typ)
        v["code_commune"] = v["code_commune"].map(remap)
        med = v.groupby("code_commune")["prix_m2"].median()
        n = v.groupby("code_commune")["prix_m2"].size()
        res[f"prix_{pref}_m2"] = med.reindex(res.index).round(0)
        res[f"n_ventes_{pref}"] = n.reindex(res.index).fillna(0).astype(int)
        if typ == "Maison":
            m24 = v[v["annee"] == 2024].groupby("code_commune")["prix_m2"].median()
            m25 = v[v["annee"] == 2025].groupby("code_commune")["prix_m2"].median()
            n2 = v[v["annee"].isin([2024, 2025])].groupby("code_commune").size()
            evol = ((m25 / m24 - 1) * 100).where(n2 >= 30)
            res["evol_prix_maison_24_25_pct"] = evol.reindex(res.index).round(1)

    res["loyers_maison_m2"] = load_loyers("pred-mai-2025.csv").reindex(res.index).round(2)
    res["loyers_appart_m2"] = load_loyers("pred-app-2025.csv").reindex(res.index).round(2)

    # petites communes sans assez de ventes : mediane EPCI en repli pour le prix
    res["prix_maison_faible_echantillon"] = res["n_ventes_maison"] < 15

    res = res.reset_index()
    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # ---------------------------------------------------------------- recap
    print(f"communes : {len(res)}")
    print(f"ventes exploitees : maison {res['n_ventes_maison'].sum():,} | appart {res['n_ventes_appart'].sum():,}".replace(",", " "))
    print(f"echantillon maison < 15 ventes : {res['prix_maison_faible_echantillon'].sum()} communes")
    for c in ["prix_maison_m2", "prix_appart_m2", "loyers_maison_m2", "loyers_appart_m2", "evol_prix_maison_24_25_pct"]:
        v = res[c]
        print(f"  {c:26s}: med {v.median():8.1f} | p10 {v.quantile(.1):8.1f} | p90 {v.quantile(.9):8.1f} | NaN {v.isna().sum()}")
    print("\n--- 8 communes maison la plus chere / la moins chere (pop >= 3000) ---")
    b = res[res["PMUN"] >= 3000]
    print(b.nlargest(8, "prix_maison_m2")[["commune", "dep", "prix_maison_m2", "n_ventes_maison", "loyers_maison_m2"]].to_string(index=False))
    print(b.nsmallest(8, "prix_maison_m2")[["commune", "dep", "prix_maison_m2", "n_ventes_maison", "evol_prix_maison_24_25_pct"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
