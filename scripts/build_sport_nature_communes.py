"""
Volet "sport & nature" pour les communes candidates.

- Acces (BPE 2025) : piscine F101, salle de remise en forme F120, randonnee F203, gymnase F121.
- Clubs sportifs licencies : nb de clubs actifs pour 1 000 hab (INJEP 2023,
  D:\\Classement_retraite\\raw\\clubs-data-2023.csv).
- Espaces verts : part de la population a moins de 300 m d'un espace vert (parc, jardin, bois...).
  Meme methode que le retraite : carreaux 200 m Insee + espaces verts OSM, buffer 300 m, test du
  centroide. Fichiers du dossier retraite : espaces_verts_osm.gpkg + carreaux_59_62.gpkg.
- Surface d'espace vert par habitant (m2) : intersection espaces verts x contour communal (IGN
  Admin Express COG-CARTO 2026).

Sortie : data/output/sport_nature_communes_candidates.csv
"""
from __future__ import annotations
import sys
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import duckdb

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
RETRAITE = Path("D:/Classement_retraite/raw")
ACCES = ROOT / "data" / "raw" / "bpe_acces" / "donnees_2025_reg32.parquet"
MVT = ROOT / "data" / "raw" / "insee" / "v_mvt_commune_2026.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "sport_nature_communes_candidates.csv"

EV_GPKG = ROOT / "data" / "raw" / "geo" / "espaces_verts_osm_5962.gpkg"   # re-extrait sur tout le 59/62
CARR_GPKG = RETRAITE / "carreaux_59_62.gpkg"
IGN_GPKG = RETRAITE / "ADE-COG-CARTO-PE_4-0_GPKG_LAMB93_FXX-ED2026-01-01.gpkg"
CLUBS = RETRAITE / "clubs-data-2023.csv"

ACCES_GROUPES = {"piscine": ["F101"], "fitness": ["F120"], "randonnee": ["F203"], "gymnase": ["F121"]}


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

    # --- BPE acces ---
    con = duckdb.connect()
    for name, codes in ACCES_GROUPES.items():
        lst = ", ".join(f"'{c}'" for c in codes)
        t = con.execute(f"""
            WITH g AS (SELECT idSrc,depcom,iris,pop,duree FROM read_parquet('{ACCES.as_posix()}')
                       WHERE dep IN ('59','62') AND typeeq_id IN ({lst})
                       QUALIFY row_number() OVER (PARTITION BY idSrc,depcom,iris ORDER BY duree)=1)
            SELECT depcom code_insee, round(sum(duree*pop)/nullif(sum(pop),0),1) acces_{name}_moy_min,
                   round(min(duree),1) acces_{name}_min_min FROM g GROUP BY depcom
        """).df()
        t["code_insee"] = t["code_insee"].map(lambda c: passage.get(c, c))
        res = res.merge(t.groupby("code_insee", as_index=False).min(), on="code_insee", how="left")

    # --- INJEP clubs sportifs ---
    cl = pd.read_csv(CLUBS, dtype=str, sep=";", encoding="utf-8-sig")
    cl.columns = [c.strip().strip('"') for c in cl.columns]
    cl = cl.rename(columns={"Code Commune": "code_insee"})
    cl["n"] = pd.to_numeric(cl["Clubs_actifs"], errors="coerce").fillna(0)
    cl = cl[cl["code_insee"].str.match(r"^(59|62)\d{3}$", na=False)]
    cl["code_insee"] = cl["code_insee"].map(lambda c: passage.get(c, c))
    clubs = cl.groupby("code_insee", as_index=False)["n"].sum().rename(columns={"n": "nb_clubs_actifs"})
    res = res.merge(clubs, on="code_insee", how="left")
    res["nb_clubs_actifs"] = res["nb_clubs_actifs"].fillna(0).astype(int)
    res["clubs_pour_1000hab"] = (res["nb_clubs_actifs"] / res["PMUN"] * 1000).round(2)

    # --- espaces verts : part de la population a <300 m ---
    print("chargement espaces verts + carreaux...")
    ev = gpd.read_file(EV_GPKG, layer="espaces_verts").to_crs(2154)
    carr = gpd.read_file(CARR_GPKG, layer="carreaux").to_crs(2154)
    carr["code_insee"] = carr["lcog_geo"].str.split(",").str[0].map(lambda c: passage.get(c, c))
    print("  buffer 300 m + union (~1 min)...")
    ev_buf = ev.geometry.buffer(300).union_all()
    carr_pts = carr.set_geometry(carr.geometry.centroid)
    carr["accessible"] = carr_pts.geometry.within(ev_buf)
    agg = carr.groupby("code_insee").apply(
        lambda g: pd.Series({"pop_tot": g["ind"].sum(),
                             "pop_acc": g.loc[g["accessible"], "ind"].sum()}),
        include_groups=False)
    agg["part_pop_ev_300m"] = (agg["pop_acc"] / agg["pop_tot"].replace(0, np.nan) * 100).round(1)
    res = res.merge(agg[["part_pop_ev_300m"]].reset_index(), on="code_insee", how="left")

    # --- surface d'espace vert par habitant ---
    print("  surface espaces verts par commune (intersection contours IGN)...")
    com = gpd.read_file(IGN_GPKG, layer="commune", columns=["code_insee"]).to_crs(2154)
    com = com[com["code_insee"].str.match(r"^(59|62)")].copy()
    com["code_insee"] = com["code_insee"].map(lambda c: passage.get(c, c))
    com = com.dissolve("code_insee").reset_index()
    inter = gpd.overlay(ev[["geometry"]], com, how="intersection", keep_geom_type=True)
    inter["surf_m2"] = inter.geometry.area
    surf = inter.groupby("code_insee", as_index=False)["surf_m2"].sum()
    res = res.merge(surf, on="code_insee", how="left")
    res["surf_ev_m2_par_hab"] = (res["surf_m2"].fillna(0) / res["PMUN"]).round(0)
    res = res.drop(columns=["surf_m2"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # --- recap ---
    print(f"\ncommunes : {len(res)} | colonnes : {len(res.columns)}")
    print("acces (min) mediane | max :")
    for n in ACCES_GROUPES:
        c = f"acces_{n}_moy_min"
        print(f"  {n:10s}: {res[c].median():5.1f} | {res[c].max():5.1f}")
    print(f"\nclubs sportifs / 1000 hab : mediane {res['clubs_pour_1000hab'].median():.2f} | p95 {res['clubs_pour_1000hab'].quantile(.95):.2f} | max {res['clubs_pour_1000hab'].max():.2f}")
    print(f"part pop a <300m d'un espace vert : mediane {res['part_pop_ev_300m'].median():.0f} % "
          f"| q25 {res['part_pop_ev_300m'].quantile(.25):.0f} | min {res['part_pop_ev_300m'].min():.0f}")
    print(f"surface espace vert / hab : mediane {res['surf_ev_m2_par_hab'].median():.0f} m2 | max {res['surf_ev_m2_par_hab'].max():.0f}")
    print("\n--- 8 communes les moins vertes (part <300m) ---")
    print(res.nsmallest(8, "part_pop_ev_300m")[["commune", "dep", "part_pop_ev_300m", "surf_ev_m2_par_hab", "clubs_pour_1000hab"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
