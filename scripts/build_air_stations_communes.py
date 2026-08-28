"""
Volet "qualite de l'air - concentrations" pour les communes candidates.

Remplace `air_pct_jours_degrades` (indice ATMO communal, qui ne discrimine rien) par les
CONCENTRATIONS annuelles reelles de NO2 et PM2.5, mesurees aux stations de FOND d'Atmo
Hauts-de-France (data/raw/atmo/stations_annuel_hdf.csv, 36 stations).

Methode : pour chaque commune, station de fond la plus proche (grand cercle), derniere valeur
annuelle valide (statut_valid = 't') du polluant. NO2 = meilleur marqueur trafic/urbain,
PM2.5 = marqueur sanitaire.

LIMITE a documenter : 36 stations pour 411 communes -> chaque commune herite de la station la
plus proche, parfois a >10 km. Indicateur DIRECTIONNEL (gradient urbain/industriel vs rural),
pas une mesure locale. Pas de modele de dispersion communal disponible en open data.

Sortie : data/output/air_stations_communes_candidates.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "atmo" / "stations_annuel_hdf.csv"
CENT = ROOT / "data" / "interim" / "communes_centroids_5962.csv"
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "output" / "air_stations_communes_candidates.csv"

POLL = {"Dioxyde d'azote": "no2", "Particules fines PM2.5": "pm25", "Particules PM10": "pm10"}


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    d = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(d))


def main() -> None:
    st = pd.read_csv(SRC)
    st = st[st["nom_poll"].isin(POLL) & (st["statut_valid"].astype(str).str.lower().isin(["t", "true"]))]
    st["valeur"] = pd.to_numeric(st["valeur"], errors="coerce")
    st = st.dropna(subset=["valeur", "x_wgs84", "y_wgs84"])
    # derniere annee valide par (station, polluant)
    st = st.sort_values("annee").groupby(["nom_station", "nom_poll"], as_index=False).last()
    st["poll"] = st["nom_poll"].map(POLL)

    cand = pd.read_csv(CAND, dtype={"code_insee": str})
    cent = pd.read_csv(CENT, dtype={"code_insee": str}).set_index("code_insee")[["lat", "lon"]]
    res = cand[["code_insee", "commune", "dep", "PMUN", "dans_MEL"]].copy()
    res = res.join(cent, on="code_insee")

    for poll in ("no2", "pm25", "pm10"):
        sp = st[st["poll"] == poll]
        if sp.empty:
            continue
        slat = sp["y_wgs84"].to_numpy()
        slon = sp["x_wgs84"].to_numpy()
        sval = sp["valeur"].to_numpy()
        sann = sp["annee"].to_numpy()
        sname = sp["nom_station"].to_numpy()
        vals, dists, names, anns = [], [], [], []
        for lat, lon in zip(res["lat"], res["lon"]):
            dk = haversine_km(lat, lon, slat, slon)
            k = int(np.argmin(dk))
            vals.append(sval[k]); dists.append(round(float(dk[k]), 1))
            names.append(sname[k]); anns.append(int(sann[k]))
        res[f"air_{poll}_ugm3"] = np.round(vals, 1)
        if poll == "no2":
            res["air_station_nom"] = names
            res["air_station_dist_km"] = dists
            res["air_station_annee"] = anns

    res = res.drop(columns=["lat", "lon"])
    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    print(f"communes : {len(res)} | stations fond utilisees : {st['nom_station'].nunique()}")
    for c in ["air_no2_ugm3", "air_pm25_ugm3", "air_pm10_ugm3", "air_station_dist_km"]:
        if c in res:
            v = res[c]
            print(f"  {c:20s}: med {v.median():6.1f} | p10 {v.quantile(.1):6.1f} | p90 {v.quantile(.9):6.1f} | max {v.max():6.1f}")
    print("\n--- NO2 le plus eleve / le plus bas (pop >= 5000) ---")
    b = res[res["PMUN"] >= 5000]
    print(b.nlargest(6, "air_no2_ugm3")[["commune", "dep", "air_no2_ugm3", "air_pm25_ugm3", "air_station_nom", "air_station_dist_km"]].to_string(index=False))
    print(b.nsmallest(6, "air_no2_ugm3")[["commune", "dep", "air_no2_ugm3", "air_pm25_ugm3", "air_station_nom", "air_station_dist_km"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
