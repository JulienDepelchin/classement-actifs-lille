"""
Consolidation multimodale du trajet domicile -> Lille, par commune candidate.

Met en concurrence, pour chaque commune, TOUTES les options :
  - TER (+ acces voiture a la gare)          -> deja calcule (trajet_ter_realiste_min)
  - Ilevia metro/tram/bus (MEL)              -> deja calcule (tc_trajet_realiste_min) + prix abo ajoute ici
  - Velo pur (communes <= VELO_KM_MAX du centre de Lille)
  - Velo + TER (rabattement a velo vers la gare utile si <= VELO_GARE_KM_MAX)
  - Voiture                                  -> REFERENCE (mesure de la dependance a la voiture)

Sorties (colonnes ajoutees a data/output/transport_communes_candidates.csv) :
  velo_min, velo_ter_min, voiture_min, voiture_cout_mensuel_est_eur,
  ilevia_abo_mensuel_eur, ilevia_abo_reste_a_charge_eur,
  meilleur_temps_vers_lille_min, meilleur_mode_vers_lille,
  cout_mensuel_meilleur_mode_eur, cout_mensuel_min_eur,
  option_sans_voiture, voiture_min_ref, ratio_temps_vs_voiture

Le lecteur verra "meilleur temps" + "cout mensuel" separement ; le composite reste pour le scoring.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
TRANSPORT = ROOT / "data" / "output" / "transport_communes_candidates.csv"
CENTROIDS = ROOT / "data" / "interim" / "communes_centroids_5962.csv"
GARES = ROOT / "data" / "interim" / "gares_ter_communes.csv"

LILLE_FLANDRES = (50.63658, 3.07103)          # point de reference "centre / Euralille"

# --- velo ---
VELO_KMH, VELO_DETOUR = 16.0, 1.30
VELO_KM_MAX = 12.0                            # au-dela, le velo pur n'est pas un trajet domicile-travail
VELO_GARE_KM_MAX = 5.0                        # rabattement velo -> gare envisageable

# --- voiture (reference, hors score) ---
#   temps = itineraire TomTom AVEC TRAFIC (departAt mardi 08:00, trafic recurrent) + stationnement.
#   fallback : OSRM (fluide) x facteur de pointe si TomTom absent.
VOIT_PEAK_FACTOR = 1.35                       # fallback uniquement
VOIT_PARK_LILLE_MIN = 8.0                     # recherche de place + marche, centre de Lille
VOIT_FIXE_MIN = 5.0                           # (fallback uniquement)
#   cout : COUT MARGINAL de rouler (le menage possede deja la voiture).
#   N'inclut PAS amortissement / assurance / carte grise (bareme fiscal ~0,55 EUR/km ecarte).
VOIT_PRIX_CARBURANT = 2.00                    # SP95-E10, prix moyen France au 26/08/2026 (gazole ~2,22)
VOIT_CONSO_L_100 = 6.5                        # L/100 km, trajet mixte autoroute + approche MEL congestionnee
VOIT_USURE_KM = 0.08                          # pneus, revisions, freins, huile (EUR/km)
VOIT_COUT_KM = VOIT_PRIX_CARBURANT * VOIT_CONSO_L_100 / 100 + VOIT_USURE_KM  # ~= 0,21 EUR/km
VOIT_PARK_MENSUEL = 100.0                     # hypothese BASSE stationnement Lille (ouvrage ~150-250)
VOIT_JOURS = 20                               # jours ouvres / mois

# --- Ilevia ---
# Tarifs au 01/08/2025 : mensuel tout public 65 EUR ; abonnement PERMANENT (prelevement, engagement
# 1 an) 56,50 EUR/mois -> c'est le tarif du pendulaire. V'Lille (velos en libre-service) desormais
# INCLUS dans tous les abonnements longue duree (renforce l'option velo pour les communes MEL).
ILEVIA_ABO_MENSUEL = 56.5
PART_EMPLOYEUR = 0.50

# --- dependance voiture ---
RATIO_OK, RATIO_MAX = 1.3, 2.5               # ratio temps(meilleur TC/velo)/temps(voiture)


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    d = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(d))


def velo_min(gc_km, fixe=2.0):
    return fixe + gc_km * VELO_DETOUR / VELO_KMH * 60.0


def voiture_min_fallback(gc_km):
    # utilise seulement si l'itineraire OSRM manque
    f = np.where(np.asarray(gc_km) < 8, 1.55, 1.05)
    return VOIT_FIXE_MIN + np.asarray(gc_km) * f + VOIT_PARK_LILLE_MIN


def main() -> None:
    tr = pd.read_csv(TRANSPORT, dtype={"code_insee": str, "gare_utile_uic": str})
    cent = pd.read_csv(CENTROIDS, dtype={"code_insee": str})[["code_insee", "lat", "lon"]]
    gares = pd.read_csv(GARES, dtype={"uic": str}).dropna(subset=["stop_lat"])
    gare_xy = gares.drop_duplicates("uic").set_index("uic")[["stop_lat", "stop_lon"]].astype(float)

    tr = tr.drop(columns=[c for c in tr.columns if c in {
        "velo_min", "velo_ter_min", "voiture_min", "voiture_bouchons_min",
        "voiture_km", "voiture_cout_carburant_eur", "voiture_cout_mensuel_est_eur",
        "ilevia_abo_mensuel_eur", "ilevia_abo_reste_a_charge_eur", "cout_mensuel_meilleur_mode_eur",
        "cout_transit_min_eur", "gare_sur_territoire", "temps_sans_voiture_min",
        "mode_sans_voiture", "cout_sans_voiture_eur", "surcout_temps_sans_voiture_min",
        "ratio_sansvoiture_vs_voiture", "ratio_alternatif_vs_voiture",
        "ratio_temps_vs_voiture", "option_sans_voiture", "cout_mensuel_min_eur"}], errors="ignore")
    tr = tr.merge(cent, on="code_insee", how="left")

    gc_lille = haversine_km(tr["lat"], tr["lon"], *LILLE_FLANDRES)
    tr["_gc_lille_km"] = gc_lille.round(1)

    # gc commune -> gare utile
    gu_lat = tr["gare_utile_uic"].map(gare_xy["stop_lat"])
    gu_lon = tr["gare_utile_uic"].map(gare_xy["stop_lon"])
    gc_gare = haversine_km(tr["lat"], tr["lon"], gu_lat, gu_lon)

    # --- velo ---
    tr["velo_min"] = np.where(gc_lille <= VELO_KM_MAX, velo_min(gc_lille).round(0), np.nan)

    # --- velo + TER : on remplace l'acces voiture a la gare par un acces velo ---
    acces_velo_gare = velo_min(gc_gare, fixe=1.0)
    base_ter_hors_acces = tr["trajet_ter_realiste_min"] - tr["acces_gare_utile_min"]
    tr["velo_ter_min"] = np.where(
        (gc_gare <= VELO_GARE_KM_MAX) & tr["trajet_ter_realiste_min"].notna(),
        (base_ter_hors_acces + acces_velo_gare).round(0), np.nan)

    # --- voiture (reference) : itineraire TomTom AVEC TRAFIC (pointe mardi 08:00) ---
    tt = pd.read_csv(ROOT / "data" / "interim" / "voiture_lille_tomtom.csv", dtype={"code_insee": str})
    osrm = pd.read_csv(ROOT / "data" / "interim" / "voiture_lille_osrm.csv", dtype={"code_insee": str})
    tr = tr.merge(tt, on="code_insee", how="left").merge(osrm, on="code_insee", how="left")

    v_tt = tr["tt_voiture_min"] + VOIT_PARK_LILLE_MIN
    v_osrm = tr["osrm_voiture_min"] * VOIT_PEAK_FACTOR + VOIT_PARK_LILLE_MIN
    v_fallback = pd.Series(voiture_min_fallback(gc_lille), index=tr.index)
    tr["voiture_min"] = v_tt.fillna(v_osrm).fillna(v_fallback).round(0)
    tr["voiture_bouchons_min"] = tr["tt_bouchons_min"].round(0)               # minutes perdues dans les bouchons
    tr["voiture_km"] = tr["tt_voiture_km"].fillna(tr["osrm_voiture_km"]).round(1)
    km = tr["voiture_km"].fillna(gc_lille * 1.3)
    tr["voiture_cout_carburant_eur"] = (km * 2 * VOIT_JOURS * VOIT_COUT_KM).round(0)     # + usure, part dure
    tr["voiture_cout_mensuel_est_eur"] = (tr["voiture_cout_carburant_eur"] + VOIT_PARK_MENSUEL).round(0)  # + hypothese parking Lille
    tr = tr.drop(columns=["tt_voiture_min", "tt_voiture_libre_min", "tt_bouchons_min",
                          "tt_voiture_km", "osrm_voiture_min", "osrm_voiture_km"])

    # --- Ilevia (MEL) ---
    tr["ilevia_abo_mensuel_eur"] = np.where(tr["dans_MEL"], ILEVIA_ABO_MENSUEL, np.nan)
    tr["ilevia_abo_reste_a_charge_eur"] = np.where(
        tr["dans_MEL"], round(ILEVIA_ABO_MENSUEL * (1 - PART_EMPLOYEUR), 2), np.nan)

    # --- une gare TER sur le territoire communal (meme mal desservie) ? ---
    a_gare = set(pd.read_csv(GARES, dtype={"code_insee_commune": str})
                 .dropna(subset=["code_insee_commune"])["code_insee_commune"])
    tr["gare_sur_territoire"] = tr["code_insee"].isin(a_gare)
    ter_sans_voiture = tr["gare_utile_sur_place"].fillna(False) | tr["gare_sur_territoire"]

    # --- assemblage des options (temps, cout net mensuel, dependance voiture) ---
    #   "TER" ici = TER avec acces voiture a la gare ; les options SANS voiture sont marquees.
    ter_net = tr["ter_abo_mensuel_reste_a_charge_eur"]
    opts = {
        # mode          temps                        cout net             sans voiture ?
        "TER":       (tr["trajet_ter_realiste_min"], ter_net,                     ter_sans_voiture),
        "TC urbain": (tr["tc_trajet_realiste_min"],  tr["ilevia_abo_reste_a_charge_eur"], tr["dans_MEL"]),
        "velo":      (tr["velo_min"],                pd.Series(0.0, index=tr.index),      pd.Series(True, index=tr.index)),
        "velo+TER":  (tr["velo_ter_min"],            ter_net,                     pd.Series(True, index=tr.index)),
    }
    times = pd.DataFrame({k: v[0] for k, v in opts.items()})
    costs = pd.DataFrame({k: v[1].astype(float) for k, v in opts.items()})
    carfree = pd.DataFrame({k: v[2].fillna(False).astype(bool) for k, v in opts.items()})

    def safe_idxmin(df):
        ok = df.notna().any(axis=1)
        out = pd.Series(np.nan, index=df.index, dtype=object)
        out[ok] = df[ok].idxmin(axis=1)
        return out

    tbest = times.min(axis=1)
    best_mode = safe_idxmin(times)
    times_cf = times.where(carfree)                       # temps des seules options sans voiture
    tbest_cf = times_cf.min(axis=1)
    best_cf = safe_idxmin(times_cf)

    def label(bm, row):
        if pd.isna(bm):
            return None
        others = row.drop(bm).dropna()
        close = others[others - row[bm] <= 5]
        return f"{bm} ~ {close.idxmin()}" if len(close) else bm

    tr["meilleur_temps_vers_lille_min"] = tbest
    tr["meilleur_mode_vers_lille"] = [label(m, times.loc[i]) for i, m in best_mode.items()]
    tr["cout_mensuel_meilleur_mode_eur"] = [
        costs.at[i, m] if isinstance(m, str) else np.nan for i, m in best_mode.items()]

    tr["temps_sans_voiture_min"] = tbest_cf
    tr["mode_sans_voiture"] = [label(m, times_cf.loc[i]) for i, m in best_cf.items()]
    tr["cout_sans_voiture_eur"] = [
        costs.at[i, m] if isinstance(m, str) else np.nan for i, m in best_cf.items()]
    tr["surcout_temps_sans_voiture_min"] = (tbest_cf - tbest).round(0)

    # --- pilier "alternative a la voiture integrale" (park & ride TER inclus) ---
    #   tbest = meilleur trajet hors voiture-tout-le-trajet (le TER inclut l'acces voiture a la gare).
    #   Pas de NaN : toute commune a au moins un rabattement voiture vers une gare utile.
    tr["ratio_alternatif_vs_voiture"] = (tbest / tr["voiture_min"]).round(2)
    tr["option_sans_voiture"] = tbest_cf.notna().astype(int)   # 1 = trajet 100% sans voiture possible

    # titre de transport payant le moins cher (TER abo ou Ilevia abo)
    tr["cout_transit_min_eur"] = pd.concat(
        [ter_net, tr["ilevia_abo_reste_a_charge_eur"]], axis=1).min(axis=1)

    # --- dependance a la voiture : temps du meilleur trajet SANS voiture / temps voiture ---
    tr["ratio_sansvoiture_vs_voiture"] = (tbest_cf / tr["voiture_min"]).round(2)

    tr = tr.drop(columns=["lat", "lon", "_gc_lille_km"])
    tr.to_csv(TRANSPORT, index=False, encoding="utf-8-sig")

    # ---------------------------------------------------------------- recap
    cf = tr["temps_sans_voiture_min"].notna()
    print(f"communes : {len(tr)}")
    print(f"  option velo pur (<= {VELO_KM_MAX} km)          : {tr['velo_min'].notna().sum()}")
    print(f"  option velo+TER (gare <= {VELO_GARE_KM_MAX} km)     : {tr['velo_ter_min'].notna().sum()}")
    print(f"  AU MOINS UN trajet sans voiture vers Lille : {int(cf.sum())}  "
          f"(=> {int((~cf).sum())} communes ou il FAUT une voiture pour rejoindre un train)")
    print(f"\n  meilleur mode (tous modes) :")
    print(tr["meilleur_mode_vers_lille"].str.split(" ~ ").str[0].value_counts().to_string())
    print(f"  mode sans voiture :")
    print(tr["mode_sans_voiture"].str.split(" ~ ").str[0].value_counts(dropna=False).to_string())
    print(f"\n  meilleur temps (min)          : med {tr['meilleur_temps_vers_lille_min'].median():.0f}")
    print(f"  temps sans voiture (min)      : med {tr.loc[cf,'temps_sans_voiture_min'].median():.0f} "
          f"| surcout median vs meilleur : +{tr.loc[cf,'surcout_temps_sans_voiture_min'].median():.0f} min")
    print(f"  cout mensuel meilleur mode    : med {tr['cout_mensuel_meilleur_mode_eur'].median():.0f} EUR net")
    print(f"  cout titre transit le -cher   : med {tr['cout_transit_min_eur'].median():.0f} EUR net")
    print(f"  voiture cout mensuel estime   : med {tr['voiture_cout_mensuel_est_eur'].median():.0f} EUR")
    print(f"  voiture bouchons (min pointe) : med {tr['voiture_bouchons_min'].median():.0f} "
          f"| p90 {tr['voiture_bouchons_min'].quantile(.9):.0f} | max {tr['voiture_bouchons_min'].max():.0f}")
    print(f"  ratio sans-voiture / voiture  : med {tr['ratio_sansvoiture_vs_voiture'].median():.2f} "
          f"| > 2 (peu competitif) : {int((tr['ratio_sansvoiture_vs_voiture']>2).sum())}")
    print(f"  ratio ALTERNATIF / voiture    : med {tr['ratio_alternatif_vs_voiture'].median():.2f} "
          f"| NaN {tr['ratio_alternatif_vs_voiture'].isna().sum()} "
          f"| option 100% sans voiture : {int(tr['option_sans_voiture'].sum())}/{len(tr)}")
    print("\n--- 12 communes hors MEL les mieux placees (temps sans voiture) ---")
    top = tr[~tr["dans_MEL"] & cf].nsmallest(12, "temps_sans_voiture_min")
    print(top[["commune", "mode_sans_voiture", "temps_sans_voiture_min", "cout_sans_voiture_eur",
               "voiture_min", "voiture_cout_mensuel_est_eur", "ratio_sansvoiture_vs_voiture"]].to_string(index=False))
    print("\n--- communes MEL ou le velo est le meilleur mode ---")
    v = tr[tr["meilleur_mode_vers_lille"].fillna("").str.startswith("velo")]
    print(v[["commune", "meilleur_mode_vers_lille", "meilleur_temps_vers_lille_min", "velo_min",
             "trajet_ter_realiste_min", "tc_trajet_realiste_min"]].head(18).to_string(index=False))
    print(f"\n-> {TRANSPORT}")


if __name__ == "__main__":
    main()
