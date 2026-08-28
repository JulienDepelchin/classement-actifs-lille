"""
Volet "retrait-gonflement des argiles" (RGA) par commune candidate.

RGA = 1er poste de sinistralite CatNat en France depuis les secheresses 2018-2022. En Nord/
Pas-de-Calais : plaine argileuse de la Flandre interieure, Pevele, Ostrevent, Cambresis.
Depuis la loi ELAN (2020), une etude de sol est OBLIGATOIRE avant de construire en zone
d'alea moyen ou fort -> surcout ~2 000-5 000 EUR + fondations renforcees.

Source : DREAL Hauts-de-France, "Alea retrait-gonflement des argiles" (georisques / BRGM),
shapefile regional n_alea_rga_s_r32 (15 polygones : 5 depts x Faible/Moyen/Fort).
  data/raw/rga/dataset/n_alea_rga_s_r32.shp
Zones non couvertes = alea nul/negligeable.

Contours communes : IGN ADMIN-EXPRESS-COG-CARTO 2026 (dossier retraite), Lambert-93.

Indicateurs (surfaciques) :
  rga_pct_moyen_fort   part de la surface communale en alea MOYEN ou FORT (l'indicateur qui compte)
  rga_pct_fort         part en alea FORT
  rga_alea_dominant    classe couvrant la plus grande part (nul / faible / moyen / fort)

Sortie : data/output/rga_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import geopandas as gpd
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
RETRAITE = Path("D:/Classement_retraite/raw")
RGA_SHP = ROOT / "data" / "raw" / "rga" / "dataset" / "n_alea_rga_s_r32.shp"
IGN_GPKG = RETRAITE / "ADE-COG-CARTO-PE_4-0_GPKG_LAMB93_FXX-ED2026-01-01.gpkg"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "rga_communes_candidates.csv"


def main() -> None:
    cand = pd.read_csv(CAND, dtype={"code_insee": str})

    com = gpd.read_file(IGN_GPKG, layer="commune", columns=["code_insee"]).to_crs(2154)
    com = com[com["code_insee"].isin(cand["code_insee"])].copy()
    com["surface_com_m2"] = com.geometry.area
    print(f"communes : {len(com)}")

    rga = gpd.read_file(RGA_SHP).to_crs(2154)
    rga["ALEA"] = rga["ALEA"].str.lower()
    rga["geometry"] = rga.geometry.make_valid()
    rga = rga.dissolve("ALEA").reset_index()[["ALEA", "geometry"]]
    rga["geometry"] = rga.geometry.make_valid()
    print(f"classes RGA : {list(rga['ALEA'])}")

    res = com[["code_insee", "surface_com_m2"]].copy()
    for lvl in ["faible", "moyen", "fort"]:
        geom = rga.loc[rga["ALEA"] == lvl, "geometry"]
        if geom.empty:
            res[f"_a_{lvl}"] = 0.0
            continue
        inter = gpd.overlay(com[["code_insee", "geometry"]],
                            gpd.GeoDataFrame(geometry=geom, crs=2154),
                            how="intersection", keep_geom_type=True)
        inter["a"] = inter.geometry.area
        res = res.merge(inter.groupby("code_insee")["a"].sum().rename(f"_a_{lvl}"),
                        on="code_insee", how="left")
    res[[f"_a_{l}" for l in ["faible", "moyen", "fort"]]] = res[[f"_a_{l}" for l in ["faible", "moyen", "fort"]]].fillna(0.0)

    for lvl in ["faible", "moyen", "fort"]:
        res[f"rga_pct_{lvl}"] = (res[f"_a_{lvl}"] / res["surface_com_m2"] * 100).round(1)
    res["rga_pct_moyen_fort"] = (res["rga_pct_moyen"] + res["rga_pct_fort"]).round(1)
    res["rga_pct_nul"] = (100 - res["rga_pct_faible"] - res["rga_pct_moyen_fort"]).clip(lower=0).round(1)

    def dominant(r):
        parts = {"nul": r["rga_pct_nul"], "faible": r["rga_pct_faible"],
                 "moyen": r["rga_pct_moyen"], "fort": r["rga_pct_fort"]}
        return max(parts, key=parts.get)
    res["rga_alea_dominant"] = res.apply(dominant, axis=1)

    out = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].merge(
        res[["code_insee", "rga_pct_faible", "rga_pct_moyen", "rga_pct_fort",
             "rga_pct_moyen_fort", "rga_alea_dominant"]], on="code_insee", how="left")
    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    # ---------------------------------------------------------------- recap
    print(f"\ncolonnes : {len(out.columns)} | NaN rga_pct_moyen_fort : {out['rga_pct_moyen_fort'].isna().sum()}")
    v = out["rga_pct_moyen_fort"]
    print(f"rga_pct_moyen_fort : med {v.median():.0f} | p10 {v.quantile(.1):.0f} | p90 {v.quantile(.9):.0f} | max {v.max():.0f}")
    print("\nalea dominant :")
    print(out["rga_alea_dominant"].value_counts().to_string())
    print(f"\ncommunes majoritairement en alea moyen+fort : {int((out['rga_pct_moyen_fort'] >= 50).sum())} "
          f"({out.loc[out['rga_pct_moyen_fort'] >= 50, 'PMUN'].sum():,.0f} hab)".replace(",", " "))
    print("\n--- 15 communes les plus exposees (moyen + fort) ---")
    print(out.nlargest(15, "rga_pct_moyen_fort")[
        ["commune", "dep", "PMUN", "rga_pct_moyen", "rga_pct_fort", "rga_pct_moyen_fort", "dans_MEL"]].to_string(index=False))
    print("\n--- part en alea FORT : top 10 ---")
    print(out.nlargest(10, "rga_pct_fort")[["commune", "dep", "rga_pct_fort", "rga_pct_moyen_fort"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
