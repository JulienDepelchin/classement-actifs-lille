"""
Desserte Ilevia (metro / tram / bus MEL) vers le centre de Lille, un mardi type.

Pour chaque commune de la MEL : meilleurs trajets domicile -> Lille-centre en transport urbain,
en TRAJET DIRECT ou avec UNE correspondance prise dans le metro (schema hub classique du reseau).

Lille-centre = 4 poles metro : Gare Lille Flandres, Lille Europe, Rihour, Republique Beaux-Arts.
Jour analyse : mardi 2026-09-15 (meme date que la desserte TER).

Sortie : data/output/ilevia_lille_communes.csv  (1 ligne par commune MEL)

Indicateurs (sur l'heure d'ARRIVEE a Lille-centre) :
  tc_arr_lille_matin  : trajets arrivant 07:00-09:30
  tc_trajet_median_min / tc_trajet_min_min
  tc_premier_arr / tc_dernier_dep
  tc_mode_direct      : part des trajets directs (sans correspondance)
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
GTFS = ROOT / "data" / "raw" / "ilevia" / "sept"
STOPS_COM = ROOT / "data" / "interim" / "ilevia_stops_communes.csv"
OUT = ROOT / "data" / "output" / "ilevia_lille_communes.csv"

DATE = "20260915"
CENTRE_STOPAREAS = {"920", "7536", "942", "773"}   # Flandres, Europe, Rihour, Republique BA
METRO_ROUTES = {"ME1", "ME2"}
TRANSFER_BUFFER_S = 120       # temps mini de correspondance a une station de metro
PEAK_ARR = (7 * 3600, 9 * 3600 + 30 * 60)


def hms(s):
    p = s.str.split(":", expand=True).astype("int64")
    return p[0] * 3600 + p[1] * 60 + p[2]


def sec_hhmm(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    x = int(x)
    return f"{x // 3600:02d}:{x % 3600 // 60:02d}"


def main() -> None:
    stops = pd.read_csv(GTFS / "stops.txt", dtype=str)
    stops["sa"] = stops["parent_station"].fillna(stops["stop_id"])       # station = StopArea
    sa_of = dict(zip(stops["stop_id"], stops["sa"]))

    sc = pd.read_csv(STOPS_COM, dtype=str)
    sc["sa"] = sc["parent_station"].fillna(sc["stop_id"])
    com_of_sa = (sc.dropna(subset=["code_insee"]).groupby("sa")["code_insee"].first().to_dict())
    name_of_sa = stops.drop_duplicates("sa").set_index("sa")["stop_name"].to_dict()

    routes = pd.read_csv(GTFS / "routes.txt", dtype=str).set_index("route_id")
    trips = pd.read_csv(GTFS / "trips.txt", dtype=str)
    cd = pd.read_csv(GTFS / "calendar_dates.txt", dtype=str)
    active = set(cd[(cd["date"] == DATE) & (cd["exception_type"] == "1")]["service_id"])
    trips = trips[trips["service_id"].isin(active)].copy()
    trips["rtype"] = trips["route_id"].map(routes["route_type"])
    trips["is_metro"] = trips["route_id"].isin(METRO_ROUTES)
    print(f"services actifs {DATE} : {len(active)} | trips actifs : {len(trips)}")

    st = pd.read_csv(GTFS / "stop_times.txt", dtype=str,
                     usecols=["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"])
    st = st[st["trip_id"].isin(set(trips["trip_id"]))].copy()
    st["sa"] = st["stop_id"].map(sa_of)
    st["arr"] = hms(st["arrival_time"])
    st["dep"] = hms(st["departure_time"])
    st["seq"] = st["stop_sequence"].astype("int64")
    st = st.merge(trips[["trip_id", "route_id", "rtype", "is_metro"]], on="trip_id", how="left")
    st = st.sort_values(["trip_id", "seq"], ignore_index=True)

    # --- metro : pour chaque station, listes triees (dep, arr_centre, min) ---
    metro = st[st["is_metro"]]
    metro_centre_arr: dict[str, list[tuple[int, int]]] = {}
    for tid, g in metro.groupby("trip_id", sort=False):
        gv = g.to_dict("records")
        centre_after = []  # (index, arr)
        for i in range(len(gv) - 1, -1, -1):
            if gv[i]["sa"] in CENTRE_STOPAREAS:
                centre_after.append((gv[i]["arr"], gv[i]["sa"]))
        if not centre_after:
            continue
        for i, row in enumerate(gv):
            later = [(a, s) for (a, s) in centre_after if a > row["dep"]]
            if not later:
                continue
            a, cs = min(later)
            metro_centre_arr.setdefault(row["sa"], []).append((row["dep"], a))
    for k in metro_centre_arr:
        metro_centre_arr[k].sort()
    metro_stations = set(metro_centre_arr) | {s for s in st[st["is_metro"]]["sa"].unique()}
    print(f"stations de metro : {len(metro_stations)} | avec trajet vers un pole centre : {len(metro_centre_arr)}")

    def next_metro_to_centre(station: str, ready_at: int):
        arr_list = metro_centre_arr.get(station)
        if not arr_list:
            return None
        lo, hi = 0, len(arr_list)
        while lo < hi:
            m = (lo + hi) // 2
            if arr_list[m][0] < ready_at:
                lo = m + 1
            else:
                hi = m
        return arr_list[lo][1] if lo < len(arr_list) else None

    # --- parcours des trips : trajets directs vers centre + 1ere jambe vers une station metro ---
    direct = []          # (sa_origine, dep, arr_centre, rtype)
    firstleg = []        # (sa_origine, dep, sa_metro, arr_metro, rtype)
    for tid, g in st.groupby("trip_id", sort=False):
        gv = g.to_dict("records")
        n = len(gv)
        centre_idx = [i for i in range(n) if gv[i]["sa"] in CENTRE_STOPAREAS]
        metro_idx = [i for i in range(n) if gv[i]["sa"] in metro_stations and gv[i]["sa"] not in CENTRE_STOPAREAS]
        for i, row in enumerate(gv):
            o = row["sa"]
            if o in CENTRE_STOPAREAS or o not in com_of_sa:
                continue
            # direct
            for ci in centre_idx:
                if gv[ci]["arr"] > row["dep"]:
                    direct.append((o, row["dep"], gv[ci]["arr"], row["rtype"]))
                    break
            # 1ere jambe -> station metro
            for mi in metro_idx:
                if gv[mi]["arr"] > row["dep"]:
                    firstleg.append((o, row["dep"], gv[mi]["sa"], gv[mi]["arr"], row["rtype"]))
                    break

    dd = pd.DataFrame(direct, columns=["sa", "dep", "arr", "rtype"])
    dd["transfer"] = 0
    fl = pd.DataFrame(firstleg, columns=["sa", "dep", "sa_metro", "arr_metro", "rtype"])
    fl["arr"] = fl.apply(lambda r: next_metro_to_centre(r["sa_metro"], r["arr_metro"] + TRANSFER_BUFFER_S), axis=1)
    fl = fl.dropna(subset=["arr"])
    fl["arr"] = fl["arr"].astype(int)
    fl["transfer"] = 1
    legs = pd.concat([dd[["sa", "dep", "arr", "rtype", "transfer"]],
                      fl[["sa", "dep", "arr", "rtype", "transfer"]]], ignore_index=True)
    legs["commune"] = legs["sa"].map(com_of_sa)
    legs["minutes"] = (legs["arr"] - legs["dep"]) / 60.0
    legs = legs[(legs["minutes"] > 1) & (legs["minutes"] < 150)]

    # indicateur au niveau commune : pour chaque minute de depart, le MEILLEUR trajet possible
    # depuis n'importe quel arret de la commune ("qualite du lien TC de la commune vers Lille"),
    # puis on agrege sur la journee.
    legs = legs.sort_values("minutes").drop_duplicates(["commune", "dep"])

    # forfaits pour rendre le temps comparable a un trajet porte-a-porte
    TC_ACCES_ATTENTE_MIN = 7   # marche vers l'arret + attente du 1er vehicule
    TC_EGRESS_MIN = 6         # pole centre -> lieu de travail

    rows = []
    for code, g in legs.groupby("commune"):
        peak = g[g["arr"].between(*PEAK_ARR)]
        med = round(g["minutes"].median(), 1)
        rows.append({
            "code_insee": code,
            "tc_trajets_jour": len(g),
            "tc_arr_lille_matin": len(peak),
            "tc_trajet_median_min": med,
            "tc_trajet_min_min": round(g["minutes"].min(), 1),
            "tc_trajet_realiste_min": round(med + TC_ACCES_ATTENTE_MIN + TC_EGRESS_MIN, 1),
            "tc_premier_arr_lille": sec_hhmm(g["arr"].min()),
            "tc_dernier_dep": sec_hhmm(g["dep"].max()),
            "tc_part_direct": round((g["transfer"] == 0).mean(), 2),
            "tc_metro_sur_place": bool(len(set(g.loc[g["transfer"] == 0, "sa"]) & metro_stations) > 0),
        })
    res = pd.DataFrame(rows).sort_values("tc_trajet_median_min", ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")

    print(f"\ncommunes MEL avec desserte TC vers Lille-centre : {len(res)}")
    print(f"  trajet median <= 30 min : {(res['tc_trajet_median_min'] <= 30).sum()}")
    print(f"  >= 8 arrivees en pointe matin : {(res['tc_arr_lille_matin'] >= 8).sum()}")
    print("\n--- 12 mieux dotees ---")
    r = res.merge(pd.read_csv(ROOT / 'data/output/communes_candidates.csv', dtype={'code_insee': str})[['code_insee', 'commune']], on='code_insee', how='left')
    print(r.head(12)[["commune", "tc_trajets_jour", "tc_arr_lille_matin", "tc_trajet_median_min",
                      "tc_trajet_min_min", "tc_part_direct", "tc_metro_sur_place"]].to_string(index=False))
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
