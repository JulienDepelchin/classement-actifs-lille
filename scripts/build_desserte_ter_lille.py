"""
Desserte TER vers Lille depuis les gares Hauts-de-France - V1 (trajets DIRECTS, sans correspondance).

Source     : GTFS regional TER Hauts-de-France (producteur Region Hauts-de-France),
             transport.data.gouv.fr resource 83620.
Jour type  : mardi ordinaire hors vacances scolaires (parametrable, defaut 2026-09-15).
Perimetre  : toutes les gares du reseau regional TER HdF presentes dans le GTFS.
Directions : gare -> Lille (principal) + Lille -> gare (colonnes "retour_*", pour la pointe soir domicile).
Modes      : trains comptes separement des autocars TER de substitution (colonne "autocars_*").

Sorties :
  data/interim/trajets_directs_<date>.csv  : 1 ligne par (gare, circulation) - pour audit / verif-data
  data/output/desserte_ter_lille_<date>.csv : 1 ligne par gare, 1 colonne par indicateur

Definitions des fenetres (sur l'HEURE DE DEPART de la gare d'origine, resp. de Lille pour le retour) :
  pointe matin : 06:00:00 -> 09:30:00 inclus
  pointe soir  : 16:30:00 -> 20:00:00 inclus
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import gtfs_kit as gk

sys.stdout.reconfigure(encoding="utf-8")

# --------------------------------------------------------------------------- config
ROOT = Path(__file__).resolve().parents[1]
GTFS_ZIP = ROOT / "data" / "raw" / "ter_hdf_gtfs.zip"
OUT_DIR = ROOT / "data" / "output"
INTERIM_DIR = ROOT / "data" / "interim"

DATE = "20260915"                       # mardi hors vacances (zone B : Toussaint = 17/10 -> 02/11/2026)
LILLE_UIC = {"87286005": "Lille-Flandres", "87223263": "Lille-Europe"}  # gares d'arrivee retenues

# Gares exclues de la sortie (haltes intra-Lille : pas des communes "ou vivre" a part entiere)
EXCLUDE_GARES = {"87109306"}            # Lille Centre Hospitalier Regional

# Trajets rapides confirmes manuellement (SNCF Connect) : pas de flag "remarque"
GARES_TEMPS_VERIFIES = {
    "87281006",   # Dunkerque -> Lille-Europe 31 min (K90+) - verifie
    "87281071",   # Calais-Frethun -> Lille-Europe 28 min (K92+/K94+, LGV) - verifie
}

PEAK_AM = ("06:00:00", "09:30:00")            # fenetre sur l'heure de DEPART de la gare d'origine
PEAK_PM = ("16:30:00", "20:00:00")            # idem (retour : heure de depart de Lille)
ARR_LILLE_AM = ("05:30:00", "09:30:00")       # fenetre sur l'heure d'ARRIVEE a Lille (pour "etre au bureau le matin")
VIT_GC_SUSPECTE = 120.0                        # km/h grand-cercle : au-dela, temps de trajet a re-verifier
                                              # (normal pour les gares sur LGV : Calais-Frethun, Arras)

# --------------------------------------------------------------------------- helpers

def hms_to_sec(s: pd.Series) -> pd.Series:
    """'HH:MM:SS' -> secondes depuis minuit (gere HH >= 24)."""
    parts = s.str.split(":", expand=True).astype("Int64")
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def sec_to_hhmm(x) -> str:
    if pd.isna(x):
        return ""
    x = int(x)
    return f"{x // 3600:02d}:{(x % 3600) // 60:02d}"


def uic_of(stop_id: pd.Series) -> pd.Series:
    return stop_id.str.extract(r"(\d{7,8})", expand=False)


def haversine_km(lat, lon, lat0: float, lon0: float):
    """Distance grand-cercle (km) entre des points (lat, lon) et un point de reference."""
    lat, lon = np.radians(lat.astype(float)), np.radians(lon.astype(float))
    lat0, lon0 = np.radians(lat0), np.radians(lon0)
    d = np.sin((lat0 - lat) / 2) ** 2 + np.cos(lat) * np.cos(lat0) * np.sin((lon0 - lon) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(d))


def is_car(stop_id: pd.Series) -> pd.Series:
    return stop_id.str.contains("Car TER", na=False)


def _win(w):
    return hms_to_sec(pd.Series([w[0]]))[0], hms_to_sec(pd.Series([w[1]]))[0]


PEAK_AM_S = _win(PEAK_AM)
PEAK_PM_S = _win(PEAK_PM)
ARR_LILLE_AM_S = _win(ARR_LILLE_AM)


def count_in_window(sec_series: pd.Series, window) -> int:
    return int(sec_series.between(window[0], window[1]).sum())


# --------------------------------------------------------------------------- chargement

def load_day_stop_times(feed: gk.Feed, date: str) -> pd.DataFrame:
    """stop_times des circulations actives le <date>, enrichi (uic, mode, secondes, ligne)."""
    trips_day = feed.get_trips(date=date)[["trip_id", "route_id", "trip_headsign", "direction_id"]]
    routes = feed.routes[["route_id", "route_short_name", "route_long_name", "route_type"]]
    trips_day = trips_day.merge(routes, on="route_id", how="left")

    st = feed.stop_times.merge(trips_day, on="trip_id", how="inner").copy()
    st["uic"] = uic_of(st["stop_id"])
    st["is_car"] = is_car(st["stop_id"])
    st["dep_s"] = hms_to_sec(st["departure_time"])
    st["arr_s"] = hms_to_sec(st["arrival_time"])
    st["seq"] = st["stop_sequence"].astype("int64")
    st = st.sort_values(["trip_id", "seq"], ignore_index=True)
    return st


# --------------------------------------------------------------------------- trajets directs

def direct_legs(st: pd.DataFrame, sens: str) -> pd.DataFrame:
    """
    Retourne 1 ligne par (circulation, gare) correspondant a un trajet DIRECT.
      sens == "vers_lille" : gare (origine) -> premiere gare de Lille rencontree apres
      sens == "retour"     : derniere gare de Lille -> gare (situee apres dans la course)
    """
    rows = []
    for trip_id, g in st.groupby("trip_id", sort=False):
        g = g.reset_index(drop=True)
        lille_mask = g["uic"].isin(LILLE_UIC)
        if not lille_mask.any():
            continue
        lille_pos = np.where(lille_mask.to_numpy())[0]

        if sens == "vers_lille":
            l = lille_pos[0]                       # 1re gare de Lille de la course
            if l == 0:                             # Lille est l'origine : rien en amont
                continue
            lr = g.loc[l]
            if lr["drop_off_type"] == 1:           # descente interdite a Lille
                continue
            others = g.loc[: l - 1]
            others = others[~others["uic"].isin(LILLE_UIC) & (others["pickup_type"] != 1)]
            for _, o in others.iterrows():
                seg = g.loc[o.name : l]
                rows.append(dict(
                    trip_id=trip_id, route=g["route_short_name"].iloc[0],
                    num_train=g["trip_headsign"].iloc[0],
                    uic_gare=o["uic"], t_dep=o["dep_s"],
                    uic_lille=lr["uic"], lille=LILLE_UIC[lr["uic"]], t_arr=lr["arr_s"],
                    minutes=(lr["arr_s"] - o["dep_s"]) / 60.0,
                    autocar=bool(seg["is_car"].any()),
                ))
        else:  # retour : Lille -> gare
            l = lille_pos[-1]                      # derniere gare de Lille de la course
            if l == len(g) - 1:                    # Lille est le terminus : rien en aval
                continue
            lr = g.loc[l]
            if lr["pickup_type"] == 1:             # montee interdite a Lille
                continue
            others = g.loc[l + 1 :]
            others = others[~others["uic"].isin(LILLE_UIC) & (others["drop_off_type"] != 1)]
            for _, d in others.iterrows():
                seg = g.loc[l : d.name]
                rows.append(dict(
                    trip_id=trip_id, route=g["route_short_name"].iloc[0],
                    num_train=g["trip_headsign"].iloc[0],
                    uic_gare=d["uic"], t_dep=lr["dep_s"],
                    uic_lille=lr["uic"], lille=LILLE_UIC[lr["uic"]], t_arr=d["arr_s"],
                    minutes=(d["arr_s"] - lr["dep_s"]) / 60.0,
                    autocar=bool(seg["is_car"].any()),
                ))
    out = pd.DataFrame(rows)
    return out[(out["minutes"] > 0) & (out["minutes"] < 600)] if len(out) else out


# --------------------------------------------------------------------------- indicateurs

def aggregate(vers: pd.DataFrame, retour: pd.DataFrame, gares: pd.DataFrame) -> pd.DataFrame:
    v_train = vers[~vers["autocar"]]
    v_car = vers[vers["autocar"]]
    r_train = retour[~retour["autocar"]]

    recs = []
    for uic, gname in gares[["uic", "stop_name"]].itertuples(index=False):
        vt = v_train[v_train["uic_gare"] == uic]
        vc = v_car[v_car["uic_gare"] == uic]
        rt = r_train[r_train["uic_gare"] == uic]

        rec = {"uic": uic, "gare": gname}
        # --- direction gare -> Lille (trains directs) ---
        rec["trains_directs_jour"] = len(vt)
        rec["trains_pointe_matin"] = count_in_window(vt["t_dep"], PEAK_AM_S)      # depart gare 06:00-09:30
        rec["trains_arr_lille_matin"] = count_in_window(vt["t_arr"], ARR_LILLE_AM_S)  # arrivee Lille 05:30-09:30
        rec["trains_pointe_soir"] = count_in_window(vt["t_dep"], PEAK_PM_S)       # depart gare 16:30-20:00
        rec["tps_trajet_median_min"] = round(vt["minutes"].median(), 1) if len(vt) else np.nan
        rec["tps_trajet_min_min"] = round(vt["minutes"].min(), 1) if len(vt) else np.nan
        rec["premier_train"] = sec_to_hhmm(vt["t_dep"].min()) if len(vt) else ""
        rec["dernier_train"] = sec_to_hhmm(vt["t_dep"].max()) if len(vt) else ""
        rec["amplitude_h"] = (round((vt["t_dep"].max() - vt["t_dep"].min()) / 3600.0, 1)
                              if len(vt) else np.nan)
        rec["gares_lille_desservies"] = "+".join(sorted(vt["lille"].str.replace("Lille-", "").unique())) if len(vt) else ""
        rec["lignes"] = ", ".join(sorted(x for x in vt["route"].dropna().unique())) if len(vt) else ""
        # --- direction retour Lille -> gare (trains directs) ---
        rec["retour_trains_directs_jour"] = len(rt)
        rec["retour_pointe_soir"] = count_in_window(rt["t_dep"], PEAK_PM_S)       # depart Lille 16:30-20:00
        rec["retour_dernier_depart_lille"] = sec_to_hhmm(rt["t_dep"].max()) if len(rt) else ""
        # --- autocars TER de substitution (compte a part) ---
        rec["autocars_directs_jour"] = len(vc)
        # --- controle de plausibilite du temps le plus rapide ---
        if len(vt):
            fast = vt.loc[vt["minutes"].idxmin()]
            rec["vitesse_gc_rapide_kmh"] = round(fast["vit_gc"], 0)
            flag = fast["vit_gc"] > VIT_GC_SUSPECTE and uic not in GARES_TEMPS_VERIFIES
            rec["remarque"] = (f"tps mini a verifier (ligne {fast['route']}, "
                               f"{fast['vit_gc']:.0f} km/h a vol d'oiseau)" if flag else "")
        else:
            rec["vitesse_gc_rapide_kmh"] = np.nan
            rec["remarque"] = ""
        recs.append(rec)

    res = pd.DataFrame(recs).merge(
        gares[["uic", "stop_lat", "stop_lon"]], on="uic", how="left"
    )
    return res.sort_values("trains_directs_jour", ascending=False, ignore_index=True)


# --------------------------------------------------------------------------- main

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    feed = gk.read_feed(GTFS_ZIP, dist_units="km")
    print(f"GTFS regional TER HdF | validite {feed.feed_info.feed_start_date.iloc[0]} "
          f"-> {feed.feed_info.feed_end_date.iloc[0]}")
    print(f"Jour analyse : {DATE}")

    st = load_day_stop_times(feed, DATE)
    print(f"circulations actives ce jour : {st['trip_id'].nunique()} | arrets : {len(st)}")

    vers = direct_legs(st, "vers_lille")
    retour = direct_legs(st, "retour")
    print(f"trajets directs gare->Lille : {len(vers)}  (dont autocar : {int(vers['autocar'].sum())})")
    print(f"trajets directs Lille->gare : {len(retour)}")

    # liste des gares = tous les StopArea du reseau, hors gares de Lille et haltes exclues
    gares = feed.stops[feed.stops["location_type"] == 1].copy()
    gares["uic"] = uic_of(gares["stop_id"])
    gares = gares[~gares["uic"].isin(set(LILLE_UIC) | EXCLUDE_GARES)].dropna(subset=["uic"])
    gares = gares.drop_duplicates("uic")[["uic", "stop_name", "stop_lat", "stop_lon"]]

    # distance grand-cercle gare <-> Lille-Flandres + vitesse implicite (controle de plausibilite)
    lf = feed.stops.loc[feed.stops["stop_id"] == "StopArea:OCE87286005", ["stop_lat", "stop_lon"]].iloc[0]
    coords = gares.set_index("uic")[["stop_lat", "stop_lon"]].astype(float)
    for df in (vers, retour):
        if len(df):
            df["km_gc"] = haversine_km(df["uic_gare"].map(coords["stop_lat"]),
                                       df["uic_gare"].map(coords["stop_lon"]),
                                       float(lf["stop_lat"]), float(lf["stop_lon"]))
            df["vit_gc"] = df["km_gc"] / (df["minutes"] / 60.0)

    # audit : long format
    audit = pd.concat([vers.assign(sens="gare_vers_lille"),
                       retour.assign(sens="lille_vers_gare")], ignore_index=True)
    audit = audit.merge(gares[["uic", "stop_name"]].rename(columns={"uic": "uic_gare", "stop_name": "gare"}),
                        on="uic_gare", how="left")
    audit["dep"] = audit["t_dep"].map(sec_to_hhmm)
    audit["arr"] = audit["t_arr"].map(sec_to_hhmm)
    audit["km_gc"] = audit["km_gc"].round(1)
    audit["vit_gc_kmh"] = audit["vit_gc"].round(0)
    audit = audit[["sens", "uic_gare", "gare", "uic_lille", "lille", "route", "num_train",
                   "dep", "arr", "minutes", "km_gc", "vit_gc_kmh", "autocar", "trip_id"]].sort_values(["sens", "gare", "dep"])
    audit_path = INTERIM_DIR / f"trajets_directs_{DATE}.csv"
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")

    res = aggregate(vers, retour, gares)
    out_path = OUT_DIR / f"desserte_ter_lille_{DATE}.csv"
    res.to_csv(out_path, index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------------ recap
    served = res[res["trains_directs_jour"] > 0]
    print(f"\ngares avec >=1 train direct gare->Lille : {len(served)} / {len(res)}")
    print(f"total trains directs gare->Lille (jour) : {int(res['trains_directs_jour'].sum())}")
    print("\nTop 12 gares (trains directs / jour) :")
    print(served.head(12)[["gare", "trains_directs_jour", "trains_pointe_matin", "trains_arr_lille_matin",
                           "trains_pointe_soir", "tps_trajet_median_min", "tps_trajet_min_min",
                           "premier_train", "dernier_train", "amplitude_h"]].to_string(index=False))
    flagged = served[served["remarque"] != ""]
    if len(flagged):
        print(f"\n{len(flagged)} gare(s) avec temps mini a re-verifier :")
        print(flagged[["gare", "tps_trajet_min_min", "vitesse_gc_rapide_kmh", "lignes"]].to_string(index=False))
    print(f"\n-> {out_path}")
    print(f"-> {audit_path}")


if __name__ == "__main__":
    main()
