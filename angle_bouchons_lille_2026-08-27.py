"""
Analyse quantitative pour la note d'angle « bouchons vers Lille ».
Reproductibilite : voir angle_bouchons_lille_2026-08-27.md (identifiants ana_xx).

Source unique : data/output/bouchons_communes_lille.csv
  (issu de data/interim/voiture_lille_tomtom.csv — TomTom Routing API, calculateRoute,
   traffic=true, departAt=2026-09-15T08:00 mardi, computeTravelTimeFor=all ;
   historicTrafficTravelTimeInSeconds = pointe, noTrafficTravelTimeInSeconds = fluide).
Croisement immobilier : data/output/cadre_urbain_communes_candidates.csv (SeLoger/MeilleursAgents avril 2026).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent
B = pd.read_csv(ROOT / "data" / "output" / "bouchons_communes_lille.csv", dtype={"code_insee": str})
CU = pd.read_csv(ROOT / "data" / "output" / "cadre_urbain_communes_candidates.csv", dtype={"code_insee": str})

WEPPES_BASPAYS = ["Bois-Grenier", "Wavrin", "Illies", "Salomé", "Marquillies", "Fournes-en-Weppes",
                  "La Chapelle-d'Armentières", "Erquinghem-Lys", "Aubers", "Herlies", "Hantay",
                  "La Bassée", "Sainghin-en-Weppes", "Wicres", "Beaucamps-Ligny"]
MINIER_A1_A21 = ["Libercourt", "Carvin", "Courcelles-lès-Lens", "Noyelles-Godault", "Évin-Malmaison",
                 "Noyelles-sous-Lens", "Sallaumines", "Billy-Montigny", "Fouquières-lès-Lens",
                 "Hénin-Beaumont", "Montigny-en-Gohelle", "Rouvroy", "Avion", "Méricourt"]
ESCAUT = ["Vieux-Condé", "Condé-sur-l'Escaut", "Fresnes-sur-Escaut", "Hergnies", "Quarouble",
          "Escautpont", "Bruille-Saint-Amand", "Flines-lès-Mortagne", "Mortagne-du-Nord"]


def stat(s):
    return f"p10 {s.quantile(.1):.2f} | med {s.median():.2f} | p90 {s.quantile(.9):.2f} | max {s.max():.2f}"


def bloc(titre):
    print(f"\n{'='*70}\n{titre}\n{'='*70}")


bloc("STRUCTURE (ana_00)")
print(f"communes : {len(B)}  | colonnes : {list(B.columns)}")
print(f"valeurs manquantes voiture_pointe_min : {B['voiture_pointe_min'].isna().sum()}")

bloc("ana_01 — indice de congestion (pointe / fluide)")
print(stat(B["indice_congestion"]))
print(f"moyenne pondérée pop : {np.average(B['indice_congestion'], weights=B['PMUN']):.2f}")
print(f"communes indice >= 1.80 : {(B['indice_congestion']>=1.8).sum()}  "
      f"(pop {B.loc[B['indice_congestion']>=1.8,'PMUN'].sum():,})".replace(",", " "))
print(f"communes indice >= 1.90 : {(B['indice_congestion']>=1.9).sum()}")
print(f"communes indice >= 2.00 : {(B['indice_congestion']>=2.0).sum()}")
print("\ntop 12 indice :")
print(B.nlargest(12, "indice_congestion")[
    ["commune", "dep", "voiture_pointe_min", "voiture_libre_min", "bouchons_min",
     "indice_congestion", "part_trajet_bouchons_pct"]].to_string(index=False))

bloc("ana_02 — minutes perdues (absolu) + plateau")
print(stat(B["bouchons_min"]))
print(f"communes bouchons_min >= 23 : {(B['bouchons_min']>=23).sum()}  | >= 20 : {(B['bouchons_min']>=20).sum()}")
print("\ntop 12 minutes perdues :")
print(B.nlargest(12, "bouchons_min")[
    ["commune", "dep", "bouchons_min", "min_perdues_jour", "h_perdues_an", "indice_congestion", "PMUN"]].to_string(index=False))

bloc("ana_03 — corrélations distance / congestion")
print(f"corr indice_congestion ~ voiture_km    : {B['indice_congestion'].corr(B['voiture_km']):+.2f}")
print(f"corr bouchons_min ~ voiture_km         : {B['bouchons_min'].corr(B['voiture_km']):+.2f}")
print(f"corr indice_congestion ~ voiture_pointe_min : {B['indice_congestion'].corr(B['voiture_pointe_min']):+.2f}")
print("→ plus on est proche de Lille, plus le multiplicateur de pointe est fort ;")
print("  les minutes sèches perdues, elles, plafonnent (péage forfaitaire de l'approche).")

bloc("ana_04 — MEL vs hors MEL")
g = B.groupby(B["dans_MEL"].map({True: "MEL", False: "hors MEL"}))
print(g[["indice_congestion", "bouchons_min", "voiture_km", "h_perdues_an"]].median().to_string())

bloc("ana_05 — double peine : congestion ET aucune alternative sans voiture")
dp = B[B["sans_alternative"] & (B["bouchons_min"] >= B["bouchons_min"].median())]
print(f"{len(dp)} communes | {dp['PMUN'].sum():,} habitants".replace(",", " "))
print(f"indice médian de ce groupe : {dp['indice_congestion'].median():.2f} | "
      f"bouchons médian : {dp['bouchons_min'].median():.0f} min | h/an médian : {dp['h_perdues_an'].median():.0f}")
print("\n15 plus peuplées du groupe :")
print(dp.nlargest(15, "PMUN")[["commune", "dep", "PMUN", "bouchons_min", "indice_congestion", "h_perdues_an"]].to_string(index=False))

bloc("ana_06 — les plus épargnées (indice le plus bas)")
print(B.nsmallest(12, "indice_congestion")[
    ["commune", "dep", "voiture_pointe_min", "bouchons_min", "indice_congestion", "dans_MEL"]].to_string(index=False))

bloc("ana_07 — lecture par corridor (échantillons nommés)")
for nom, lst in [("Weppes / Bas-Pays (RN41 / A25)", WEPPES_BASPAYS),
                 ("Bassin minier A1 / A21", MINIER_A1_A21),
                 ("Vallée de l'Escaut (A2 / A23)", ESCAUT)]:
    sub = B[B["commune"].isin(lst)]
    print(f"\n{nom}  ({len(sub)}/{len(lst)} trouvées)")
    print(f"  indice médian {sub['indice_congestion'].median():.2f} | "
          f"bouchons médian {sub['bouchons_min'].median():.0f} min | "
          f"part trajet {sub['part_trajet_bouchons_pct'].median():.0f} %")

bloc("ana_08 — heures perdues par an, aller-retour, 220 j travaillés")
print(stat(B["h_perdues_an"]))
top = B.nlargest(1, "h_perdues_an").iloc[0]
print(f"record : {top['commune']} {top['h_perdues_an']:.0f} h/an ({top['min_perdues_jour']:.0f} min/j)")
print(f"communes >= 150 h/an : {(B['h_perdues_an']>=150).sum()}  "
      f"(pop {B.loc[B['h_perdues_an']>=150,'PMUN'].sum():,})".replace(",", " "))

bloc("ana_09 — tension immobilier : prix bas = bouchons hauts ?")
m = B.merge(CU[["code_insee", "prix_maison_m2", "part_menages_2voit_plus", "evol_pop_2016_2022_pct"]],
            on="code_insee", how="left")
m = m[m["prix_maison_m2"].notna()]
print(f"n = {len(m)}")
print(f"corr prix_maison_m2 ~ bouchons_min       : {m['prix_maison_m2'].corr(m['bouchons_min']):+.2f}")
print(f"corr prix_maison_m2 ~ indice_congestion  : {m['prix_maison_m2'].corr(m['indice_congestion']):+.2f}")
print(f"corr prix_maison_m2 ~ voiture_km         : {m['prix_maison_m2'].corr(m['voiture_km']):+.2f}")
q1 = m[m["prix_maison_m2"] <= m["prix_maison_m2"].quantile(.25)]
q4 = m[m["prix_maison_m2"] >= m["prix_maison_m2"].quantile(.75)]
print(f"\nquartile le - cher (méd. {q1['prix_maison_m2'].median():.0f} €/m²) : "
      f"bouchons méd {q1['bouchons_min'].median():.0f} min | indice {q1['indice_congestion'].median():.2f}")
print(f"quartile le + cher (méd. {q4['prix_maison_m2'].median():.0f} €/m²) : "
      f"bouchons méd {q4['bouchons_min'].median():.0f} min | indice {q4['indice_congestion'].median():.2f}")

bloc("ana_10 — repère externe TomTom officiel")
print("TomTom Traffic Index 2025 — agglo de Lille : 66 h perdues / an aux heures de pointe")
print("(base : trajet urbain type 10 km ; +2h33 vs 2024). Notre calcul = trajet réel")
print("commune → cœur de Lille, d'où des ordres de grandeur supérieurs pour les communes lointaines.")
