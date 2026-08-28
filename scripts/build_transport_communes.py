"""
Volet "desserte ferroviaire vers Lille" pour les communes candidates.

Pour chaque commune : temps d'acces a une gare + qualite de la desserte directe TER vers Lille
de la gare qu'un actif utiliserait realistement.

Deux notions d'acces :
  - acces_gare_proche_min : temps routier (voiture) vers la gare LA PLUS PROCHE, quelle qu'elle
    soit (source BPE / distancier Metric-OSRM). Indicateur de proximite ferroviaire brute.
  - gare_utile + acces_gare_utile_min : gare LA PLUS PROCHE PARMI CELLES qui offrent une desserte
    directe reguliere vers Lille (>= SEUIL_DIRECTS trains/j et >= SEUIL_MATIN arrivees a Lille en
    pointe matin). Temps estime par un modele calibre sur les donnees BPE :
        duree_routiere_min ~= 2.0 + 1.32 * distance_vol_oiseau_km   (R2 = 0.93, MAE 1.2 min)
    C'est cette gare qui porte les indicateurs de desserte de la commune.

Entrees :
  data/output/communes_candidates.csv
  data/interim/acces_gare_communes_5962.parquet      (BPE, temps routier gare la plus proche)
  data/interim/communes_centroids_5962.csv           (centroides communes)
  data/interim/gares_ter_communes.csv                (gare GTFS -> commune, geocodee)
  data/output/desserte_ter_lille_<DATE>.csv          (indicateurs par gare)

Sortie : data/output/transport_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output" / "transport_communes_candidates.csv"
DATE = "20260915"

CAND = ROOT / "data" / "output" / "communes_candidates.csv"
ACCES = ROOT / "data" / "interim" / "acces_gare_communes_5962.parquet"
CENTROIDS = ROOT / "data" / "interim" / "communes_centroids_5962.csv"
GARES = ROOT / "data" / "interim" / "gares_ter_communes.csv"
DESSERTE = ROOT / "data" / "output" / f"desserte_ter_lille_{DATE}.csv"

# modele calibre gc_km -> duree routiere (min), cf. docstring
ROAD_A, ROAD_B = 2.02, 1.32

SEUIL_DIRECTS = 5      # trains directs / jour minimum pour qualifier une "gare utile"
SEUIL_MATIN = 2        # arrivees a Lille en pointe matin minimum
EGRESS_LILLE_MIN = 6   # gare de Lille -> lieu de travail (marche / metro), forfait

DESSERTE_COLS = [
    "trains_directs_jour", "trains_pointe_matin", "trains_arr_lille_matin", "trains_pointe_soir",
    "tps_trajet_median_min", "tps_trajet_min_min", "premier_train", "dernier_train", "amplitude_h",
    "gares_lille_desservies", "lignes", "retour_trains_directs_jour", "retour_pointe_soir",
    "retour_dernier_depart_lille", "autocars_directs_jour",
]


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    d = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(d))


def main() -> None:
    cand = pd.read_csv(CAND, dtype={"code_insee": str})
    cent = pd.read_csv(CENTROIDS, dtype={"code_insee": str})
    acces = pd.read_parquet(ACCES).rename(columns={"depcom": "code_insee"})
    acces["code_insee"] = acces["code_insee"].astype(str)

    # rabattement voiture -> gare utile route avec trafic (TomTom, mardi 07:30) quand dispo
    tt_gare = {}
    _p = ROOT / "data" / "interim" / "acces_gare_utile_tomtom.csv"
    if _p.exists():
        _t = pd.read_csv(_p, dtype={"code_insee": str, "gare_utile_uic": str})
        tt_gare = {(r.code_insee, r.gare_utile_uic): r.acces_gare_tt_min
                   for r in _t.itertuples() if pd.notna(r.acces_gare_tt_min)}
        print(f"acces gare utile route TomTom (trafic) : {len(tt_gare)} communes")

    gares = pd.read_csv(GARES, dtype={"uic": str, "code_insee_commune": str}).dropna(subset=["code_insee_commune"])
    dess = pd.read_csv(DESSERTE, dtype={"uic": str})
    g = gares.merge(dess[["uic"] + DESSERTE_COLS], on="uic", how="left")
    for c in ["trains_directs_jour", "trains_arr_lille_matin"]:
        g[c] = g[c].fillna(0)
    g["stop_lat"] = g["stop_lat"].astype(float)
    g["stop_lon"] = g["stop_lon"].astype(float)

    # gares "utiles" = desserte directe reguliere vers Lille
    gu = g[(g["trains_directs_jour"] >= SEUIL_DIRECTS) & (g["trains_arr_lille_matin"] >= SEUIL_MATIN)].copy()
    gu = gu.sort_values("trains_directs_jour", ascending=False).drop_duplicates("uic")
    print(f"gares 'utiles' (>= {SEUIL_DIRECTS} directs/j et >= {SEUIL_MATIN} arr. pointe matin) : {len(gu)}")

    # gares "sur place" avec au moins 1 direct (evite de renvoyer une commune vers une gare
    # lointaine alors qu'elle a sa propre gare, meme faiblement desservie -- ex. Boulogne)
    g_place = g[(g["trains_directs_jour"] >= 1) & (~g["code_insee_commune"].isin(gu["code_insee_commune"]))]
    g_place = g_place.sort_values("trains_directs_jour", ascending=False).drop_duplicates("code_insee_commune")

    lat_u = gu["stop_lat"].to_numpy()
    lon_u = gu["stop_lon"].to_numpy()
    place_by_com = g_place.set_index("code_insee_commune", drop=False)

    df = cand.merge(cent[["code_insee", "lat", "lon"]], on="code_insee", how="left")
    df = df.merge(acces[["code_insee", "acces_gare_duree_moy_min", "acces_gare_duree_min_min"]],
                  on="code_insee", how="left")
    df = df.rename(columns={"acces_gare_duree_moy_min": "acces_gare_proche_moy_min",
                            "acces_gare_duree_min_min": "acces_gare_proche_min_min"})

    rows = []
    for r in df.itertuples():
        dists = haversine_km(r.lat, r.lon, lat_u, lon_u)
        k = int(np.argmin(dists))
        gc = float(dists[k])
        ref = gu.iloc[k]
        acces_utile = round(max(ROAD_A + ROAD_B * gc, 1.0), 1)

        # la commune a sa propre gare (>=1 direct) mais non "utile" : on la garde si elle est
        # nettement plus proche que la gare utile la plus proche
        if r.code_insee in place_by_com.index:
            pl = place_by_com.loc[r.code_insee]
            acces_place = round(float(r.acces_gare_proche_min_min), 1) if pd.notna(r.acces_gare_proche_min_min) else 2.0
            if acces_place + 8 < acces_utile:
                ref, gc, acces_utile = pl, 0.0, acces_place

        # si la gare retenue est dans la commune, l'acces reel BPE prime sur l'estimation ;
        # sinon, le trajet route TomTom avec trafic prime sur la calibration a vol d'oiseau
        if r.code_insee == ref["code_insee_commune"] and pd.notna(r.acces_gare_proche_min_min):
            acces_utile = round(float(r.acces_gare_proche_min_min), 1)
        elif (r.code_insee, ref["uic"]) in tt_gare:
            acces_utile = round(float(tt_gare[(r.code_insee, ref["uic"])]), 1)

        rec = {
            "code_insee": r.code_insee, "commune": r.commune, "dep": r.dep,
            "PMUN": r.PMUN, "dans_MEL": r.dans_MEL,
            "acces_gare_proche_min_min": r.acces_gare_proche_min_min,
            "acces_gare_proche_moy_min": r.acces_gare_proche_moy_min,
            "gare_utile": ref["stop_name"],
            "gare_utile_uic": ref["uic"],
            "gare_utile_commune": ref["commune"],
            "gare_utile_sur_place": bool(r.code_insee == ref["code_insee_commune"]),
            "acces_gare_utile_min": acces_utile,
            "desserte_directe_faible": bool(ref["trains_directs_jour"] < SEUIL_DIRECTS),
        }
        for c in DESSERTE_COLS:
            rec[c] = ref[c]

        # temps de trajet consolide, comparable au trajet en TC urbain :
        #   acces gare + attente estimee (fonction de la frequence en pointe matin)
        #   + temps de train median + sortie a Lille (gare -> lieu de travail).
        tpm = ref["trains_pointe_matin"]
        attente = min(150.0 / max(float(tpm) if pd.notna(tpm) else 0, 1) / 2.0, 12.0)
        rec["attente_ter_min"] = round(attente, 1)
        rec["egress_lille_min"] = EGRESS_LILLE_MIN
        if pd.notna(ref["tps_trajet_median_min"]):
            rec["porte_a_porte_median_min"] = round(acces_utile + ref["tps_trajet_median_min"], 1)
            rec["trajet_ter_realiste_min"] = round(acces_utile + attente + ref["tps_trajet_median_min"]
                                                   + EGRESS_LILLE_MIN, 1)
        else:
            rec["porte_a_porte_median_min"] = None
            rec["trajet_ter_realiste_min"] = None
        rows.append(rec)

    res = pd.DataFrame(rows).sort_values(["dep", "commune"], ignore_index=True)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    # --- recap ---
    print(f"\ncommunes candidates : {len(res)}")
    print(f"  gare utile sur le territoire          : {int(res['gare_utile_sur_place'].sum())}")
    print(f"  acces gare utile <= 10 min            : {int((res['acces_gare_utile_min'] <= 10).sum())}")
    print(f"  acces gare utile 10-20 min            : {int(res['acces_gare_utile_min'].between(10, 20, inclusive='right').sum())}")
    print(f"  acces gare utile > 20 min             : {int((res['acces_gare_utile_min'] > 20).sum())}")
    print(f"  porte-a-porte median <= 45 min        : {int((res['porte_a_porte_median_min'] <= 45).sum())}")
    print(f"\n  ecart gare proche <-> gare utile (min d'acces) : "
          f"mediane +{(res['acces_gare_utile_min'] - res['acces_gare_proche_moy_min']).median():.1f} min")
    print("\n--- 15 meilleures communes hors MEL (porte-a-porte median) ---")
    top = res[~res["dans_MEL"]].nsmallest(15, "porte_a_porte_median_min")
    print(top[["commune", "gare_utile", "gare_utile_sur_place", "acces_gare_utile_min",
               "trains_directs_jour", "trains_arr_lille_matin", "tps_trajet_median_min",
               "porte_a_porte_median_min"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
