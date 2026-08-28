"""
Grille de ponderation v2 du classement "Ou vivre quand on travaille a Lille".

Modele : classement retraite + systeme d'etoiles Lovable + reprises de la methodo Le Figaro
(transformation log pour les distributions asymetriques ; systeme bonus/malus pour les faits
binaires ; phrase d'humilite).

  - 10 THEMES a etoiles (le lecteur regle 1-5 etoiles par theme sur /personnaliser)
  - poids FIXES par critere a l'interieur d'un theme
  - score_theme = somme(score_critere x poids) / somme(poids)  -> 0-20
    ... ajuste par des BONUS / MALUS (+-0,2 a 0,4 pt) pour des faits qualitatifs, puis borne [0;20]
  - score_global (preset defaut) = somme(score_theme x etoiles_defaut) / somme(etoiles)
  - normalisation d'un critere : imputation -> transformation (log / winsor / aucune) -> min-max 0-20

Sorties : data/output/grille_ponderation_lille.csv / .xlsx
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output" / "grille_ponderation_lille"

# theme -> (etoiles par defaut, libelle)
THEMES = {
    "transport":     (5, "Transport vers Lille"),
    "sante":         (3, "Santé"),
    "education":     (3, "Éducation & petite enfance"),
    "cadre_urbain":  (3, "Cadre urbain & logement"),
    "environnement": (3, "Environnement & risques"),
    "securite":      (2, "Sécurité"),
    "commerces":     (2, "Commerces & services"),
    "sport_nature":  (2, "Sport & nature"),
    "dynamique":     (2, "Dynamique résidentielle"),
    "cout_logement": (1, "Coût du logement"),
}

FICH = {
    "transport": "transport_communes_candidates.csv",
    "bouchons": "bouchons_communes_lille.csv",
    "cyclable": "cyclable_communes_candidates.csv",
    "sante": "sante_communes_candidates.csv",
    "education": "education_communes_candidates.csv",
    "commerces": "commerces_communes_candidates.csv",
    "sport_nature": "sport_nature_communes_candidates.csv",
    "securite": "securite_communes_candidates.csv",
    "environnement": "environnement_communes_candidates.csv",
    "air": "air_stations_communes_candidates.csv",
    "georisques": "georisques_communes_candidates.csv",
    "rga": "rga_communes_candidates.csv",
    "cadre_urbain": "cadre_urbain_communes_candidates.csv",
    "dpe": "dpe_communes_candidates.csv",
    "immobilier": "immobilier_communes_candidates.csv",
    "fiscalite": "fiscalite_communes_candidates.csv",
    "dynamiques": "dynamiques_communes_candidates.csv",
}

# (theme, colonne, libelle, fichier, sens, poids, transform, imputation, note)
#   transform : "log" | "winsor_p95" | "winsor_p90" | "winsor_p5_p95" | "aucune"
C = [
 # ---------------- TRANSPORT ----------------
 ("transport", "meilleur_temps_vers_lille_min", "Meilleur trajet alternatif a la voiture integrale",
  "transport", "inverser", 7, "aucune", "mediane", "park & ride TER inclus ; 0 NaN"),
 ("transport", "ratio_alternatif_vs_voiture", "Dependance a la voiture",
  "transport", "inverser", 4, "winsor_p95", "mediane", "meilleur trajet alternatif / temps voiture"),
 ("transport", "part_actifs_tc_pct_2022", "Part des actifs qui prennent deja le TC",
  "dynamiques", "normal", 4, "log", "0", "RP 2022 (mesure, pas modele) ; valide le pilier (r=0,53 avec le score)"),
 ("transport", "trains_arr_lille_matin", "Trains directs arrivant a Lille le matin",
  "transport", "normal", 5, "winsor_p95", "0", "frequence a la pointe (05h30-09h30)"),
 ("transport", "cout_mensuel_meilleur_mode_eur", "Cout mensuel du meilleur mode",
  "transport", "inverser", 3, "winsor_p95", "mediane", "abo TER/Ilevia net du remboursement 50%"),
 ("transport", "indice_congestion", "Congestion aux heures de pointe",
  "bouchons", "inverser", 4, "winsor_p95", "mediane", "pointe / fluide (TomTom)"),
 ("transport", "acces_gare_proche_moy_min", "Acces a une gare TER",
  "transport", "inverser", 3, "winsor_p95", "mediane", "temps routier moyen (BPE)"),
 ("transport", "cyclable_util_km_1000hab", "Reseau cyclable utilitaire",
  "cyclable", "normal", 3, "log", "0", "km / 1000 hab (Ecolab/Geovelo 2025)"),

 # ---------------- SANTE ----------------
 ("sante", "apl_mg_m65", "Acces aux medecins generalistes (<= 65 ans)",
  "sante", "normal", 7, "aucune", "mediane", "APL DREES 2024"),
 ("sante", "apl_dent", "Acces aux chirurgiens-dentistes",
  "sante", "normal", 4, "aucune", "mediane", "APL DREES 2024 (profession la plus tendue)"),
 ("sante", "acces_urgences_moy_min", "Temps d'acces aux urgences",
  "sante", "inverser", 5, "winsor_p95", "mediane", "BPE 2025"),
 ("sante", "acces_maternite_moy_min", "Temps d'acces a une maternite",
  "sante", "inverser", 3, "winsor_p95", "mediane", "BPE 2025"),

 # ---------------- EDUCATION ----------------
 ("education", "couverture_petite_enfance_epci", "Couverture petite enfance",
  "education", "normal", 6, "aucune", "mediane", "CNAF 2023, tous modes, niveau EPCI"),
 ("education", "acces_college_moy_min", "Temps d'acces a un college",
  "education", "inverser", 5, "winsor_p95", "mediane", "BPE 2025"),
 ("education", "acces_lycee_moy_min", "Temps d'acces a un lycee",
  "education", "inverser", 4, "winsor_p95", "mediane", "BPE 2025"),

 # ---------------- CADRE URBAIN ----------------
 ("cadre_urbain", "part_logts_vacants", "Part de logements vacants",
  "cadre_urbain", "inverser", 4, "winsor_p95", "mediane", "INSEE RP 2023 ; proxy vitalite du tissu"),
 ("cadre_urbain", "part_passoires_pct", "Part de passoires thermiques (DPE F-G)",
  "dpe", "inverser", 4, "winsor_p95", "mediane", "ADEME DPE (echantillon transactions)"),

 # ---------------- ENVIRONNEMENT & RISQUES ----------------
 ("environnement", "air_no2_ugm3", "Qualite de l'air : NO2",
  "air", "inverser", 3, "aucune", "mediane", "concentration annuelle a la station de fond la plus proche (~8 km med) ; indicateur directionnel"),
 ("environnement", "artif_pct_2009_2024", "Rythme d'artificialisation des sols",
  "environnement", "inverser", 3, "winsor_p95", "mediane", "CEREMA 2009-2024"),
 ("environnement", "imper_pct_2021", "Impermeabilisation des sols",
  "environnement", "inverser", 2, "winsor_p95", "mediane", "CEREMA 2021 ; correle densite urbaine"),
 ("environnement", "catnat_inondation_depuis_2010_n", "Inondations recentes",
  "georisques", "inverser", 3, "winsor_p95", "0", "arretes CatNat inondation depuis 2010"),
 ("environnement", "rga_pct_moyen_fort", "Retrait-gonflement des argiles (exposition)",
  "rga", "inverser", 3, "aucune", "0", "part surface communale en alea moyen+fort (DREAL/BRGM)"),

 # ---------------- SECURITE ----------------
 ("securite", "cambriolages_taux", "Taux de cambriolages",
  "securite", "inverser", 5, "winsor_p95", "mediane", "SSMSI moy. 2022-2024 ; ~45% des cellules estimees"),
 ("securite", "degradations_taux", "Taux de degradations volontaires",
  "securite", "inverser", 4, "winsor_p95", "mediane", "SSMSI moy. 2022-2024"),

 # ---------------- COMMERCES ----------------
 ("commerces", "commerces_essentiels_sur_place", "Panier de commerces essentiels sur place",
  "commerces", "normal", 4, "aucune", "0", "0-7 : boulangerie, boucherie, epicerie, pharmacie, poste, ecole, medecin"),
 ("commerces", "acces_supermarche_moy_min", "Temps d'acces a un supermarche",
  "commerces", "inverser", 4, "winsor_p95", "mediane", "BPE 2025"),
 ("commerces", "acces_boulangerie_moy_min", "Temps d'acces a une boulangerie",
  "commerces", "inverser", 2, "winsor_p95", "mediane", "BPE 2025"),
 ("commerces", "resto_pour_1000hab", "Restaurants pour 1000 habitants",
  "commerces", "normal", 2, "winsor_p95", "0", "BPE stock 2024 (winsor : artefact zones commerciales)"),

 # ---------------- SPORT & NATURE ----------------
 ("sport_nature", "surf_ev_m2_par_hab", "Espaces verts (m2 par habitant)",
  "sport_nature", "normal", 5, "log", "mediane", "parcs/jardins/bois OSM x population"),
 ("sport_nature", "clubs_pour_1000hab", "Clubs sportifs pour 1000 habitants",
  "sport_nature", "normal", 4, "log", "mediane", "INJEP 2023"),
 ("sport_nature", "acces_piscine_moy_min", "Temps d'acces a une piscine",
  "sport_nature", "inverser", 3, "winsor_p95", "mediane", "BPE 2025"),
 ("sport_nature", "acces_randonnee_moy_min", "Temps d'acces a un sentier de randonnee",
  "sport_nature", "inverser", 3, "winsor_p95", "mediane", "BPE 2025"),

 # ---------------- DYNAMIQUE RESIDENTIELLE (nouveau) ----------------
 ("dynamique", "taux_var_pop_16_22_pct_an", "Croissance de la population 2016-2022",
  "dynamiques", "normal", 5, "winsor_p5_p95", "mediane", "taux annuel moyen (Insee RP)"),
 ("dynamique", "accel_pop_pts", "Acceleration demographique",
  "dynamiques", "normal", 3, "winsor_p5_p95", "mediane", "var. 16-22 moins var. 11-16 (pts)"),
 ("dynamique", "arrivants_actifs_pour_1000hab", "Arrivee d'actifs (25-54 ans)",
  "dynamiques", "normal", 3, "log", "mediane", "residaient dans une autre commune 1 an avant (IRAN)"),
 ("dynamique", "indice_vieillissement_2022", "Vieillissement de la population",
  "dynamiques", "inverser", 3, "winsor_p95", "mediane", "65+ pour 100 jeunes de -20 ans"),

 # ---------------- COUT DU LOGEMENT (ex prix_immobilier + fiscalite) ----------------
 ("cout_logement", "prix_maison_m2", "Prix des maisons au m2",
  "immobilier", "inverser", 5, "winsor_p5_p95", "mediane", "DVF transactions reelles 2023-2025"),
 ("cout_logement", "loyers_maison_m2", "Loyers des maisons au m2",
  "immobilier", "inverser", 3, "winsor_p5_p95", "mediane", "Carte des loyers 2025 (annonce predite)"),
 ("cout_logement", "loyers_appart_m2", "Loyers des appartements au m2",
  "immobilier", "inverser", 2, "winsor_p5_p95", "mediane", "Carte des loyers 2025"),
 ("cout_logement", "taux_taxe_fonciere_bati", "Taux de taxe fonciere",
  "fiscalite", "inverser", 3, "winsor_p95", "mediane", "DGFiP 2025, taux global sur le bati"),
]

# BONUS / MALUS : (theme, colonne, condition, delta, libelle)
#   condition = ("==", v) | (">", v) | ("<", v) | ("truthy",) | ("falsy",)
BM = [
 ("transport", "desserte_directe_faible", ("truthy",), -0.30, "gare de rabattement mal desservie"),
 ("transport", "option_sans_voiture",     ("==", 0),   -0.40, "aucun trajet 100% sans voiture possible"),
 ("transport", "gare_sur_territoire",     ("truthy",), +0.20, "une gare TER dans la commune"),
 ("sante",     "msp_sur_place",           ("truthy",), +0.20, "maison de sante pluriprofessionnelle sur place"),
 ("sante",     "acces_urgences_moy_min",  (">", 20),   -0.30, "urgences a plus de 20 min"),
 ("education", "college_sur_place",       ("==", 1),   +0.25, "un college dans la commune"),
 ("environnement", "risque_minier",       ("==", 1),   -0.30, "alea minier (affaissement, gaz de mine)"),
]
BM_FICH = {"transport": "transport", "sante": "sante", "education": "education",
           "environnement": "georisques"}

DEFAUT = {k: v[0] for k, v in THEMES.items()}


def main() -> None:
    rows = []
    for theme, col, lib, fk, sens, poids, transf, imput, note in C:
        rows.append({
            "theme": theme, "theme_libelle": THEMES[theme][1], "etoiles_defaut": DEFAUT[theme],
            "critere_colonne": col, "critere_libelle": lib, "fichier_source": FICH[fk],
            "sens": sens, "poids": poids, "transform": transf, "imputation": imput, "note": note or "",
        })
    df = pd.DataFrame(rows)

    bm = pd.DataFrame([{
        "theme": t, "colonne": c, "condition": f"{cond[0]} {cond[1] if len(cond) > 1 else ''}".strip(),
        "delta": d, "fichier_source": FICH[BM_FICH[t]], "libelle": lib,
    } for t, c, cond, d, lib in BM])

    rec = df.groupby("theme_libelle").agg(
        n_criteres=("critere_colonne", "count"), poids_total=("poids", "sum"),
        etoiles=("etoiles_defaut", "first")).reset_index()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    bm.to_csv(OUT.parent / "grille_bonus_malus_lille.csv", index=False, encoding="utf-8-sig")
    try:
        with pd.ExcelWriter(OUT.with_suffix(".xlsx"), engine="openpyxl") as w:
            df.to_excel(w, sheet_name="Criteres", index=False)
            bm.to_excel(w, sheet_name="Bonus-malus", index=False)
            rec.to_excel(w, sheet_name="Recap themes", index=False)
            pd.DataFrame([{"theme": k, "libelle": v[1], "etoiles_defaut": v[0]}
                          for k, v in THEMES.items()]).to_excel(w, sheet_name="Preset defaut", index=False)
        print(f"-> {OUT.with_suffix('.xlsx')}")
    except Exception as e:
        print(f"(xlsx non genere : {e})")

    print(f"{len(df)} criteres | {len(bm)} bonus/malus | {len(THEMES)} themes\n")
    print(rec.to_string(index=False))
    print("\nPreset par defaut :")
    print("  " + " · ".join(f"{k} {'★'*v[0]}" for k, v in THEMES.items()))


if __name__ == "__main__":
    main()
