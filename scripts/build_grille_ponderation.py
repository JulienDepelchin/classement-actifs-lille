"""
Genere la grille de ponderation du classement "Ou vivre quand on travaille a Lille",
sur le modele de D:/Classement_retraite/analyse/methodologie_criteres.xlsx.

Architecture (identique au classement retraite + systeme d'etoiles Lovable) :
  - 9 THEMES a etoiles (le lecteur regle 1-5 etoiles par theme sur /personnaliser)
  - a l'interieur d'un theme : poids FIXES par critere (colonne "poids")
  - score_theme = somme(score_critere x poids) / somme(poids)      -> 0-20
  - score_global (preset par defaut) = somme(score_theme x etoiles_defaut) / somme(etoiles_defaut)
  - normalisation : imputation (voir colonne "imputation") -> winsorisation (colonne "winsor")
    -> min-max 0-20 (sens "normal" = haut meilleur ; "inverser" = bas meilleur)

Sorties : data/output/grille_ponderation_lille.csv  (+ .xlsx si openpyxl dispo)
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output" / "grille_ponderation_lille"

# thème -> (étoiles par défaut, libellé)
THEMES = {
    "transport":       (5, "Transport vers Lille"),
    "prix_immobilier": (1, "Prix de l'immobilier"),   # poids tres faible (cf. retraite) : le prix
    #   en "moins cher = mieux" enterre les communes desirables et remonte les communes en declin.
    #   Reste un theme a etoiles : le lecteur qui priorise le budget le monte.
    "sante":           (3, "Santé"),
    "education":       (3, "Éducation & petite enfance"),
    "securite":        (2, "Sécurité"),   # baisse (etait 3) : la delinquance suit mecaniquement
    #   les services/flux -> ce theme penalisait toute vraie ville (Lille, Seclin, Roubaix).
    "cadre_urbain":    (3, "Cadre urbain & logement"),
    "environnement":   (3, "Environnement & risques"),
    "commerces":       (2, "Commerces & services"),
    "sport_nature":    (2, "Sport & nature"),
}

# (theme, colonne_source, libelle, fichier, sens, poids, winsor, imputation, note)
C = [
 ("transport", "meilleur_temps_vers_lille_min", "Meilleur trajet alternatif a la voiture integrale",
  "transport", "inverser", 7, None, "mediane",
  "porte-a-porte du meilleur mode hors voiture-tout-le-trajet ; le TER inclut le rabattement voiture (park & ride) -> 0 NaN"),
 ("transport", "ratio_alternatif_vs_voiture", "Dependance a la voiture",
  "transport", "inverser", 4, "p95", "mediane",
  "meilleur trajet alternatif / temps voiture pure ; proche de 1 = le park & ride ne bat pas la voiture -> captif ; 0 NaN"),
 ("transport", "option_sans_voiture", "Existe-t-il une option 100% sans voiture ?",
  "transport", "normal", 3, None, "0", "binaire 0/1 ; 287/411 communes ont un trajet sans voiture du tout"),
 ("transport", "trains_arr_lille_matin", "Trains directs arrivant a Lille le matin",
  "transport", "normal", 5, "p95", "0", "frequence a la pointe (05h30-09h30)"),
 ("transport", "cout_mensuel_meilleur_mode_eur", "Cout mensuel du meilleur mode",
  "transport", "inverser", 4, "p95", "mediane",
  "abo TER/Ilevia net du remboursement 50% ; NOTE : pour le park & ride ne compte pas la possession + le rabattement voiture (~+30 EUR/mois)"),
 ("transport", "indice_congestion", "Congestion aux heures de pointe",
  "bouchons_lille", "inverser", 4, "p95", "mediane",
  "temps pointe / temps fluide (TomTom) ; pese aussi sur le rabattement voiture vers la gare ; fichier bouchons_communes_lille.csv"),
 ("transport", "acces_gare_proche_moy_min", "Acces a une gare TER",
  "transport", "inverser", 3, "p95", "mediane", "temps routier moyen vers la gare la plus proche (BPE)"),
 ("transport", "cyclable_util_km_1000hab", "Reseau cyclable utilitaire",
  "cyclable", "normal", 3, "p90", "0", "km d'amenagements cyclables utilitaires / 1000 hab (Ecolab/Geovelo 2025)"),

 ("prix_immobilier", "prix_maison_m2", "Prix des maisons au m2",
  "immobilier", "inverser", 6, "p5_p95", "mediane",
  "DVF transactions reelles 2023-2025 (mediane communale) ; winsor DEUX queues : les prix planchers (marche en detresse) ne scorent pas 20/20"),
 ("prix_immobilier", "loyers_maison_m2", "Loyers des maisons au m2",
  "immobilier", "inverser", 3, "p5_p95", "mediane", "Carte des loyers 2025 (indicateur d'annonce predit, CGDD/ANIL)"),
 ("prix_immobilier", "loyers_appart_m2", "Loyers des appartements au m2",
  "immobilier", "inverser", 2, "p5_p95", "mediane", "Carte des loyers 2025 ; pertinent surtout pour les communes MEL (locatif)"),

 ("sante", "apl_mg_m65", "Acces aux medecins generalistes (<= 65 ans)",
  "sante", "normal", 7, None, "mediane", "APL DREES 2024, indicateur prospectif"),
 ("sante", "apl_dent", "Acces aux chirurgiens-dentistes",
  "sante", "normal", 4, None, "mediane", "APL DREES 2024 (profession la plus tendue)"),
 ("sante", "acces_urgences_moy_min", "Temps d'acces aux urgences",
  "sante", "inverser", 5, "p95", "mediane", "BPE 2025, temps routier moyen pondere pop"),
 ("sante", "acces_maternite_moy_min", "Temps d'acces a une maternite",
  "sante", "inverser", 3, "p95", "mediane", "BPE 2025"),
 ("sante", "apl_mg_evol_pct", "Trajectoire des generalistes 2022->2024",
  "sante", "normal", 2, "p5_p95", "mediane", "en baisse dans 296/411 communes ; a lire en tendance"),

 ("education", "couverture_petite_enfance_epci", "Couverture petite enfance",
  "education", "normal", 6, None, "mediane", "CNAF 2023, tous modes de garde, niveau EPCI"),
 ("education", "acces_college_moy_min", "Temps d'acces a un college",
  "education", "inverser", 5, "p95", "mediane", "BPE 2025"),
 ("education", "acces_lycee_moy_min", "Temps d'acces a un lycee",
  "education", "inverser", 4, "p95", "mediane", "BPE 2025"),
 ("education", "college_sur_place", "College dans la commune",
  "education", "normal", 2, None, "0", "0/1"),

 ("commerces", "commerces_essentiels_sur_place", "Panier de commerces essentiels sur place",
  "commerces", "normal", 6, None, "0", "0-7 : boulangerie, boucherie, epicerie/superette, pharmacie, poste, ecole, medecin"),
 ("commerces", "acces_supermarche_moy_min", "Temps d'acces a un supermarche",
  "commerces", "inverser", 4, "p95", "mediane", "BPE 2025"),
 ("commerces", "resto_pour_1000hab", "Restaurants pour 1000 habitants",
  "commerces", "normal", 2, "p95", "0", "BPE stock 2024, winsorise (artefact zones commerciales)"),

 ("sport_nature", "surf_ev_m2_par_hab", "Espaces verts (m2 par habitant)",
  "sport_nature", "normal", 5, "p95", "mediane", "parcs/jardins/bois OSM x population"),
 ("sport_nature", "clubs_pour_1000hab", "Clubs sportifs pour 1000 habitants",
  "sport_nature", "normal", 4, "p95", "mediane", "INJEP 2023"),
 ("sport_nature", "acces_piscine_moy_min", "Temps d'acces a une piscine",
  "sport_nature", "inverser", 3, "p95", "mediane", "BPE 2025"),
 ("sport_nature", "acces_randonnee_moy_min", "Temps d'acces a un sentier de randonnee",
  "sport_nature", "inverser", 3, "p95", "mediane", "BPE 2025"),

 ("securite", "cambriolages_taux", "Taux de cambriolages",
  "securite", "inverser", 5, "p95", "mediane", "SSMSI, moyenne 2022-2024, pour 1000 logements ; ~45% des cellules estimees"),
 ("securite", "degradations_taux", "Taux de degradations volontaires",
  "securite", "inverser", 4, "p95", "mediane", "SSMSI moy. 2022-2024"),
 ("securite", "vols_sans_violence_taux", "Taux de vols sans violence",
  "securite", "inverser", 4, "p95", "mediane", "SSMSI moy. 2022-2024"),
 ("securite", "vols_vehicules_taux", "Taux de vols lies aux vehicules",
  "securite", "inverser", 3, "p95", "mediane", "fusion vols_de_vehicule + vols_dans_vehicules (SSMSI) ; pertinent pour qui se gare a la gare"),

 ("environnement", "air_pct_jours_degrades", "Qualite de l'air : jours degrades",
  "environnement", "inverser", 1, None, "mediane", "% de jours indice ATMO >= 3 (jan-juil 2026, 169j) ; discrimine tres peu -> poids 1 en attendant les concentrations NO2/PM modelisees (V1.1)"),
 ("environnement", "artif_pct_2009_2024", "Rythme d'artificialisation des sols",
  "environnement", "inverser", 3, "p95", "mediane", "CEREMA, flux 2009-2024"),
 ("environnement", "imper_pct_2021", "Impermeabilisation des sols",
  "environnement", "inverser", 2, "p95", "mediane", "CEREMA 2021 ; correle a la densite urbaine (tension editoriale)"),
 ("environnement", "risque_minier", "Alea minier",
  "georisques", "inverser", 3, None, "0", "0/1 ; affaissement, effondrement, gaz de mine (113 communes)"),
 ("environnement", "catnat_inondation_depuis_2010_n", "Inondations recentes",
  "georisques", "inverser", 3, "p95", "0", "nb d'arretes CatNat inondation depuis 2010"),
 ("environnement", "rga_pct_moyen_fort", "Retrait-gonflement des argiles (exposition)",
  "rga", "inverser", 3, None, "0",
  "part de la surface communale en alea moyen+fort (DREAL HdF / BRGM) ; etude de sol obligatoire avant construction depuis la loi ELAN ; 131 communes majoritairement exposees"),

 ("cadre_urbain", "part_logts_vacants", "Part de logements vacants",
  "cadre_urbain", "inverser", 4, "p95", "mediane", "INSEE RP 2023 ; proxy de vitalite du tissu urbain"),
 ("cadre_urbain", "part_passoires_pct", "Part de passoires thermiques (DPE F-G)",
  "dpe", "inverser", 4, "p95", "mediane", "ADEME DPE 07/2021-08/2026 ; echantillon de transactions, pas le parc complet"),
 ("cadre_urbain", "evol_pop_2016_2022_pct", "Dynamique demographique 2016-2022",
  "cadre_urbain", "normal", 3, "p5_p95", "mediane", "INSEE"),
]

DEFAUT_ETOILES = {k: v[0] for k, v in THEMES.items()}


def main() -> None:
    rows = []
    for theme, col, lib, fich, sens, poids, winsor, imput, note in C:
        rows.append({
            "theme": theme,
            "theme_libelle": THEMES[theme][1],
            "etoiles_defaut": DEFAUT_ETOILES[theme],
            "critere_colonne": col,
            "critere_libelle": lib,
            "fichier_source": ("bouchons_communes_lille.csv" if fich == "bouchons_lille"
                               else f"{fich}_communes_candidates.csv"),
            "sens": sens,
            "poids": poids,
            "winsor": winsor or "",
            "imputation": imput,
            "note": note or "",
        })
    df = pd.DataFrame(rows)

    # recap poids par theme
    rec = df.groupby("theme_libelle").agg(
        n_criteres=("critere_colonne", "count"), poids_total=("poids", "sum"),
        etoiles=("etoiles_defaut", "first")).reset_index()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    try:
        with pd.ExcelWriter(OUT.with_suffix(".xlsx"), engine="openpyxl") as w:
            df.to_excel(w, sheet_name="Criteres & ponderation", index=False)
            rec.to_excel(w, sheet_name="Recap themes", index=False)
            pd.DataFrame([{"theme": k, "libelle": v[1], "etoiles_defaut": v[0]}
                         for k, v in THEMES.items()]).to_excel(w, sheet_name="Preset defaut", index=False)
        print(f"-> {OUT.with_suffix('.xlsx')}")
    except Exception as e:
        print(f"(xlsx non genere : {e})")
    print(f"-> {OUT.with_suffix('.csv')}")

    print(f"\n{len(df)} criteres | {len(THEMES)} themes\n")
    print(rec.to_string(index=False))
    print("\nPreset par defaut (score_global) :")
    print("  " + " · ".join(f"{k} {'★'*v[0]}" for k, v in THEMES.items()))


if __name__ == "__main__":
    main()
