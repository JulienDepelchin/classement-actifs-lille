# Desserte TER vers Lille — pipeline V1

Critère « qualité de la desserte TER vers Lille » du classement *Où vivre quand on travaille à Lille*
(La Voix du Nord, parution septembre 2026).

## Ce que fait le pipeline

Pour **toutes les gares du réseau ferré régional TER Hauts-de-France**, calcule des indicateurs de
desserte **directe** (sans correspondance) vers **Lille-Flandres** et **Lille-Europe**, un mardi
ordinaire hors vacances scolaires.

## Source de données

| | |
|---|---|
| Jeu de données | **Horaires théoriques du réseau ferré régional TER Hauts-de-France** (GTFS) |
| Producteur | Région Hauts-de-France (via TER-SNCF Hauts-de-France) |
| Accès | [transport.data.gouv.fr — resource 83620](https://transport.data.gouv.fr/resources/83620/download) |
| Validité du fichier téléchargé | 25/08/2026 → 23/11/2026 |
| Format | GTFS avec `calendar.txt` (motifs hebdomadaires) + `calendar_dates.txt` (exceptions) |

> Le GTFS **national** SNCF (« Horaires SNCF ») a été écarté comme base : il ne comporte aucun champ
> opérateur/région permettant d'isoler le TER Hauts-de-France, et n'a pas de `calendar.txt`.
> Il est conservé (`data/raw/gtfs/`) uniquement pour contrôle croisé.

## Jour analysé

**Mardi 15 septembre 2026** — hors vacances scolaires (Toussaint zone B : 17/10 → 02/11/2026),
rentrée effectuée, service nominal (1 364 circulations actives). Paramétrable via `DATE` en tête de
`build_desserte_ter_lille.py`.

## Logique de filtrage

1. **Circulations actives le jour J** : `feed.get_trips(date)` de `gtfs_kit` (croise `calendar.txt`
   jour de semaine + plage de validité, puis applique les ajouts/retraits de `calendar_dates.txt`).
2. **Trajet direct gare → Lille** : dans une même circulation, on repère la **première** gare de Lille
   (`stop_id` de code UIC `87286005` ou `87223263`) ; toute gare desservie **avant** elle dans la
   séquence, où la montée est autorisée, ouvre un trajet direct vers Lille.
3. **Trajet direct Lille → gare** (colonnes `retour_*`) : symétrique, à partir de la **dernière**
   gare de Lille de la course.
4. **Train vs autocar** : le mode est encodé dans le `stop_id` (`OCETrain TER` vs `OCECar TER`).
   Les autocars TER de substitution sont comptés à part (`autocars_directs_jour`), jamais mélangés
   aux trains.
5. **Fenêtres horaires** (sur l'heure de **départ** de la gare d'origine, resp. de Lille au retour) :
   pointe matin 06:00–09:30, pointe soir 16:30–20:00. Les heures GTFS ≥ 24:00 (trains après minuit)
   sont gérées.

## Sorties

### `data/output/desserte_ter_lille_<date>.csv` — 1 ligne par gare

| colonne | définition |
|---|---|
| `uic` | code UIC 8 chiffres de la gare (clé de jointure) |
| `gare` | libellé |
| `trains_directs_jour` | nb de trains directs gare → Lille sur la journée |
| `trains_pointe_matin` | trains directs partant de la gare entre 06:00 et 09:30 |
| `trains_arr_lille_matin` | trains directs **arrivant à Lille** entre 05:30 et 09:30 |
| `trains_pointe_soir` | trains directs partant de la gare entre 16:30 et 20:00 |
| `tps_trajet_median_min` | temps de trajet médian gare → Lille (minutes), sur tous les directs du jour |
| `tps_trajet_min_min` | temps de trajet le plus rapide (minutes) |
| `premier_train` / `dernier_train` | heure de départ du 1er / dernier direct gare → Lille |
| `amplitude_h` | `dernier_train − premier_train` (heures) |
| `gares_lille_desservies` | `Flandres`, `Europe` ou `Europe+Flandres` |
| `lignes` | codes de ligne concernés (K60, C70…) |
| `retour_trains_directs_jour` | nb de trains directs Lille → gare sur la journée |
| `retour_pointe_soir` | trains directs partant de Lille entre 16:30 et 20:00 |
| `retour_dernier_depart_lille` | heure du dernier direct Lille → gare |
| `autocars_directs_jour` | trajets directs assurés par autocar TER de substitution (compté à part) |
| `vitesse_gc_rapide_kmh` | vitesse à vol d'oiseau du trajet le plus rapide (contrôle de plausibilité) |
| `remarque` | signalé si `vitesse_gc_rapide_kmh > 120` (à revérifier ; normal pour les gares sur LGV) |
| `stop_lat` / `stop_lon` | coordonnées (pour jointure avec la liste des communes candidates) |

Gares sans desservice directe : toutes colonnes de comptage à 0, temps à vide.

### `data/interim/trajets_directs_<date>.csv` — 1 ligne par (gare, circulation)

Détail de chaque trajet direct (sens, ligne, n° de train, départ, arrivée, minutes, km à vol
d'oiseau, vitesse, autocar O/N, `trip_id`). Sert à l'audit / vérification manuelle.

## Points de vigilance connus (V1)

- **Seules ~115 des 376 gares** du réseau ont une desserte directe vers Lille. Les autres nécessitent
  une correspondance — non traitée en V1 (à ajouter si des communes candidates sont concernées).
- **`Lille Centre Hospitalier Régional`** (UIC 87109306) : halte TER intra-muros lilloise, **exclue**
  de la sortie via `EXCLUDE_GARES`.
- **Gares belges** (Tournai, Mouscron, Courtrai) et de la frange Aisne/Oise : présentes car
  desservies par le réseau régional ; à filtrer via `stop_lat`/`stop_lon` selon le périmètre du
  classement.
- **Contrôle de plausibilité** (`remarque`) : signale les temps mini impliquant > 120 km/h à vol
  d'oiseau. Dunkerque (31 min, K90+) et Calais-Fréthun (28 min, LGV) ont été **vérifiés manuellement
  sur SNCF Connect** et sont exacts → whitelistés dans `GARES_TEMPS_VERIFIES`.
- Chiffres établis sur **un seul mardi**. Pour robustesse, envisager une moyenne sur 3–4 mardis
  types (V1.1).

---

# Périmètre — liste des communes candidates

`scripts/build_communes_candidates.py` → `data/output/communes_candidates.csv`

**Géographie de référence : communes au 1er janvier 2026** (COG 2026, 1 534 communes en 59+62).
Les données Insee sources (flux 2021, pop 2021) sont en géo 2024 → réagrégées vers la géo 2026
via `v_mvt_commune_2026.csv` (fusions 2025 : Bermeries → L'Orée de Mormal ; Huby-Saint-Leu /
Marconne / Sainte-Austreberthe → Hesdin-la-Forêt — aucune n'entre dans le périmètre).

Sélection en 3 filtres :

| filtre | règle | source |
|---|---|---|
| 1. Résidence | département **59 ou 62** | Insee, table d'appartenance géographique des communes, géo 01/01/2026 |
| 2. Lien avec Lille | navetteurs vers la **MEL** (EPCI 200093201) : **≥ 100** OU **part ≥ 5 %** des actifs occupés résidents | Insee, base des flux de mobilité domicile-lieu de travail, **millésime 2021**, géo 2024 → réagrégé géo 2026 (table agrégée commune-à-commune) |
| 3. Taille | **population municipale ≥ 1 000** hab | Insee, populations légales 2021 (géo 2024 → réagrégé géo 2026) |

Lille et la MEL conservées (elles passent trivialement le filtre 2).

**Résultat : 411 communes** (86 MEL + 325 hors MEL), population cumulée 3,04 M.

Note Insee : les flux < 200 sont des ordres de grandeur (sondage) → le seuil de 100 est un
garde-fou, pas une valeur exacte. La bascule 100 ↔ « part 5 % seule » ne change que **13 communes**
(sous-préfectures éloignées : Dunkerque, Calais, Boulogne, Maubeuge, Cambrai, Saint-Omer…).

Colonnes : `code_insee`, `commune`, `dep`, `PMUN`, `dans_MEL`, `navetteurs_MEL`,
`actifs_occ_residents`, `part_MEL` (%), `EPCI`, `ZE2020`, `AAV2020`, `BV2022`.

`code_insee` = clé de jointure avec tous les autres critères (dont la desserte TER, à filtrer sur
ce périmètre).

---

# Volet ferroviaire par commune

`scripts/build_transport_communes.py` → `data/output/transport_communes_candidates.csv`
(1 ligne par commune candidate).

## Accès à la gare (BPE)

Source : Insee, *« Données sur la localisation et l'accès de la population aux équipements »*
([data.gouv.fr](https://www.data.gouv.fr/datasets/donnees-sur-la-localisation-et-lacces-de-la-population-aux-equipements),
**millésime 2025**, BPE + distancier **Metric-OSRM**, réseau routier OSM 2022, trajet **voiture**).
Fichier parquet au carreau 200 m, région `reg = 32` (Hauts-de-France).
Gares = équipements **E107** (national), **E108** (régional), **E109** (local).

`scripts/` calcule via DuckDB, pour chaque commune du 59+62 :
`acces_gare_proche_moy_min` (temps routier moyen pondéré population vers la gare la plus proche,
tous types) et `acces_gare_proche_min_min` (temps mini).

## Gare de référence de la commune

La gare la plus proche n'est pas toujours celle qu'on utilise : ~120 communes ont pour gare la plus
proche une halte sans train direct vers Lille alors qu'une gare bien desservie est à quelques minutes.
On retient donc la **gare utile** = la plus proche parmi les **81 gares** offrant une desserte directe
régulière (`trains_directs_jour ≥ 5` **et** `trains_arr_lille_matin ≥ 2`), + la gare de la commune
elle-même si elle a ≥ 1 direct (cas Boulogne, `desserte_directe_faible = True`).

Temps d'accès à la gare utile (`acces_gare_utile_min`) :
- gare **dans la commune** (63 cas) : temps routier réel BPE/Metric-OSRM.
- gare **hors commune** (348 cas) : **itinéraire TomTom avec trafic**, `departAt` mardi 07:30
  (`scripts/route_gare_utile_tomtom.py` → `data/interim/acces_gare_utile_tomtom.csv`). Cohérent
  avec `voiture_min` (aussi TomTom). Médiane 12,8 min, p90 19,6, max 34,6 ; bouchons sur le
  rabattement faibles (médiane +1,6 min — trajet court, souvent à contre-flux).
- fallback si TomTom absent : `durée ≈ 2,02 + 1,32 × distance_vol_d'oiseau_km` (calibré BPE, R² 0,93).

## Colonnes de sortie

`code_insee`, `commune`, `dep`, `PMUN`, `dans_MEL` ·
`acces_gare_proche_min_min`, `acces_gare_proche_moy_min` (proximité ferroviaire brute) ·
`gare_utile`, `gare_utile_uic`, `gare_utile_commune`, `gare_utile_sur_place`,
`acces_gare_utile_min`, `desserte_directe_faible` ·
tous les indicateurs de desserte de la gare utile (`trains_directs_jour`, `trains_pointe_matin`,
`trains_arr_lille_matin`, `trains_pointe_soir`, `tps_trajet_median_min`, `tps_trajet_min_min`,
`premier_train`, `dernier_train`, `amplitude_h`, `gares_lille_desservies`, `lignes`,
`retour_*`, `autocars_directs_jour`) ·
`porte_a_porte_median_min` = `acces_gare_utile_min` + `tps_trajet_median_min`.

## Résultats (411 communes)

63 ont une gare utile sur leur territoire · 292 sont à ≤ 10 min d'une gare utile, 116 à 10-20 min,
3 au-delà · door-to-door médian ≤ 45 min pour 238 communes.

## Volet urbain — Ilévia (communes MEL)

`scripts/build_ilevia_lille.py` → `data/output/ilevia_lille_communes.csv` (communes MEL desservies).

Source : **GTFS Ilévia** (`media.ilevia.fr/opendata/gtfs_sept.zip`), réseau métro (M1/M2) + tram +
bus de la MEL. Jour analysé : mardi 2026-09-15 (même date que le TER).

Pour chaque commune MEL, meilleur trajet vers **Lille-centre** (4 pôles métro : Gare Lille
Flandres, Lille Europe, Rihour, République Beaux-Arts), en **direct** ou avec **1 correspondance
prise dans le métro** (schéma hub du réseau). Agrégation : pour chaque minute de départ, le
meilleur trajet possible depuis n'importe quel arrêt de la commune, puis médiane / percentiles sur
la journée. Indicateurs `tc_*` (trajets/jour, arrivées pointe matin, temps médian / mini, part de
trajets directs, métro sur le territoire).

## Temps consolidé vers Lille

Pour rendre TER et TC urbain comparables (le TER pur ignore l'attente et la sortie à Lille) :

| mode | `trajet_*_realiste_min` = |
|---|---|
| TER | `acces_gare_utile` + `attente_ter` (≈ ½ intervalle en pointe, plafond 12 min) + `tps_trajet_median` + **6 min** (gare de Lille → lieu de travail) |
| TC urbain | `tc_trajet_median` + **7 min** (marche + attente 1er véhicule) + **6 min** (pôle centre → lieu de travail) |

→ `meilleur_temps_vers_lille_min` = min des deux · `meilleur_mode_vers_lille` ∈ {`TER`, `TC urbain`, `TER ~ TC`} (écart ≤ 5 min).

**Résultats** : Lille 21 min, Mons-en-Barœul 21, La Madeleine 22, Seclin 24, Ronchin 25… ;
21 communes ≤ 30 min, 118 ≤ 45 min, 187 > 60 min. Pires : Cambrésis profond (~110 min),
littoral (~95-100 min).

## Coût du TER vers Lille

`scripts/build_prix_ter.py` → colonnes `ter_*` dans `transport_communes_candidates.csv`.

Source : **« Tarifs TER Hauts-de-France »** (SNCF, en vigueur au **28/02/2025**), matrice
origine-destination des prix 2ⁿᵈᵉ classe. Le dataset SNCF (`tarifs-ter-hdf`) a depuis été retiré ;
on utilise le **miroir parquet conservé par data.gouv.fr** (`hydra-parquet`, ressource
`2e006c20-cff1-4fa9-b3a5-7b3bf2c0599f`). Trois tarifs par O-D : Tarif Normal (billet), Mon Abo
Hebdo, **Mon Abo Mensuel**.

On retient l'**abonnement mensuel** (le vrai coût d'un pendulaire : ~−75 % vs 40 billets/mois),
prix mini Flandres/Europe confondus. Colonnes :

| colonne | |
|---|---|
| `ter_billet_normal_eur` | billet 2ⁿᵈᵉ classe à l'unité |
| `ter_abo_hebdo_eur` | Mon Abo TER HdF hebdomadaire |
| `ter_abo_mensuel_eur` | Mon Abo TER HdF **mensuel** (illimité sur le trajet) |
| `ter_abo_mensuel_estime` | `True` si reconstitué par ratio `9,9 × billet` (plancher 24 €) faute de ligne mensuelle dans la grille — 19 communes, surtout hops intra-MEL |
| `ter_abo_mensuel_reste_a_charge_eur` | après prise en charge employeur **50 %** (minimum légal) |

**Résultats** : abo mensuel médian **81 €** (min 24, max 269) · reste à charge médian **41 €/mois**
(Seclin 18, Douai 40, Béthune 47, Arras 61, Valenciennes 52, Dunkerque 84, Calais 95).
16 communes sans prix (gare utile = Hellemmes / Le Poirier Université, trajet purement urbain).

**Pour le scoring** : `ter_abo_mensuel_eur` est fortement corrélé au temps de trajet
(r ≈ 0,87 avec `tps_trajet_median_min`) — coût et durée ne sont **pas** indépendants, pondérer
les deux à plein double-compte la distance. `trains_directs_jour` reste, lui, indépendant
(r ≈ −0,14). Le « correspondance obligatoire » se dérive de
`gare_utile_sur_place == False` + `acces_gare_utile_min` élevé.

## Consolidation multimodale (`build_transport_multimodal.py`)

Met en concurrence **toutes les options** de trajet domicile → Lille et raisonne *par trajet*,
pas par mode.

| option | temps | coût net/mois | sans voiture ? |
|---|---|---|---|
| TER (+ accès **voiture** à la gare) | `trajet_ter_realiste_min` | `ter_abo_mensuel_reste_a_charge_eur` | seulement si gare sur le territoire |
| Ilévia métro/tram/bus (MEL) | `tc_trajet_realiste_min` | `ilevia_abo_reste_a_charge_eur` = 28,25 € (abo **permanent** 56,50 €/mois au 01/08/2025 − 50 %). V'Lille inclus dans l'abo depuis 08/2025. | oui |
| **Vélo pur** (≤ 12 km du centre) | `velo_min` (16 km/h, détour ×1,3) | 0 € | oui |
| **Vélo + TER** (gare ≤ 5 km) | `velo_ter_min` (rabattement vélo au lieu de voiture) | `ter_abo_mensuel_reste_a_charge_eur` | oui |
| Voiture | `voiture_min` = **itinéraire TomTom avec trafic** (`departAt` mardi 2026-09-15 08:00, modèle de trafic récurrent) **+ 8 min** (stationnement Lille) · `voiture_bouchons_min` = minutes perdues dans les bouchons (pointe − trafic fluide) · `voiture_km` = distance routière réelle · fallback OSRM×1,35 si TomTom absent (0 cas) | `voiture_cout_carburant_eur` = `voiture_km` × 0,21 €/km ×2×20j (**part dure**) · `voiture_cout_mensuel_est_eur` = + 100 €/mois parking (hypothèse basse) — **référence, hors score** | — |

**Colonnes produites :**

| colonne | |
|---|---|
| **`meilleur_temps_vers_lille_min` / `meilleur_mode_vers_lille`** | meilleur trajet **alternatif à la voiture intégrale** — TER (rabattement voiture à la gare = **park & ride**), Ilévia, vélo, vélo+TER. **0 NaN.** Ne compte pas « voiture tout le trajet ». |
| `cout_mensuel_meilleur_mode_eur` | coût net du mode le plus rapide (park & ride = abo TER seul, cf. limite) |
| **`ratio_alternatif_vs_voiture`** | `meilleur_temps_vers_lille_min / voiture_min` — dépendance : proche de 1 = le park & ride ne bat pas la voiture. **0 NaN.** Médiane **1,00** (parité, comparaison trafic ↔ trafic des deux côtés). |
| **`option_sans_voiture`** | binaire 0/1 — un trajet **100 % sans voiture** existe (**287/411**) |
| `temps_sans_voiture_min` / `mode_sans_voiture` / `cout_sans_voiture_eur` | le trajet 100 % sans voiture s'il existe (`NaN` sinon) — contexte / fiche commune |
| `surcout_temps_sans_voiture_min` | +minutes du 100 % car-free vs meilleur mode (médiane **+6 min**) |
| `cout_transit_min_eur` | titre payant le moins cher (abo TER ou Ilévia) |
| `ratio_sansvoiture_vs_voiture` | `temps_sans_voiture / voiture_min` (`NaN` pour les 124) — contexte |
| `voiture_bouchons_min` | minutes de bouchons à la pointe (indicateur à part) — méd. **18 min**, p90 22, max **25** (Noyelles-sous-Lens, axe A21/A26 Lens–Liévin–Béthune) |
| `gare_sur_territoire` | une gare TER dans la commune (même mal desservie) |

**Résultats** : **287 communes** ont un trajet sans voiture vers Lille (velo+TER 158, TER gare
sur place 91, vélo 24, Ilévia 14) ; **124 communes (382 000 hab) où il faut une voiture pour
rejoindre un train** — ex-bassin minier (Bruay, Auchel), vallée de l'Escaut (Vieux-Condé,
Escaudain), Flandre (Merville). Coût mensuel médian du meilleur mode : **41 € net** vs **≈ 350 € de carburant + usure** pour la
voiture (**≈ 450 €** avec un forfait parking).

**Avec les temps voiture routés (TomTom, trafic récurrent de pointe)** : pour les 287 communes qui
ont une option car-free, `ratio_sansvoiture_vs_voiture` **médian 1,05** — le trajet sans voiture est
**à parité** avec la voiture, et souvent plus rapide sur les corridors ferroviaires (Douai 0,57,
Béthune 0,66, Libercourt 0,70, Sin-le-Noble 0,65, Orchies 0,76). **Aucune commune** n'a de ratio
> 2. Le routage TomTom corrige l'ancien modèle dans les deux sens : il révèle ~22 min de bouchons
sur l'axe A1 Douai / A21-A26 bassin minier (que le facteur flat 1,35 masquait) et dégonfle
Dunkerque (86 → 75 min, autoroute fluide). Médiane bouchons : **18 min**.

## Coût voiture — hypothèses (référence, hors score)

Deux colonnes, volontairement séparées :

| colonne | formule | ce qu'elle représente |
|---|---|---|
| `voiture_cout_carburant_eur` | `voiture_km` × **2** (aller-retour) × **20** (jours ouvrés/mois) × **0,21 €/km** | **coût marginal** de rouler : carburant (**6,5 L/100 km × 2,00 €/L** SP95-E10 ≈ 0,13 €/km) + usure directe (pneus, révisions, freins, huile ≈ 0,08 €/km). **N'inclut PAS** l'amortissement du véhicule, l'assurance, la carte grise — on suppose que le ménage possède déjà la voiture. (prix moyens France au 26/08/2026). Le diesel est marginalement moins cher au carburant (~−15 %, consommation moindre) malgré un prix au litre désormais plus élevé (2,22 €/L). |
| `voiture_cout_mensuel_est_eur` | `+ 100 €/mois` de stationnement à Lille | hypothèse **basse** (place en ouvrage Euralille ≈ 150–250 €/mois ; nul si parking employeur). |

**Barème kilométrique fiscal (~0,55 €/km)** délibérément non retenu : il intègre la possession du
véhicule, ce qui gonflerait artificiellement le coût pour quelqu'un qui a déjà une voiture.

**Asymétrie assumée** vis-à-vis du coût transport : les colonnes TER/Ilévia sont **nettes** du
remboursement employeur 50 % (obligation légale) ; le coût voiture est **brut** (la « prime
transport » carburant existe mais est optionnelle et plafonnée). Le trajet en train est
réellement moins cher, en partie parce qu'il est subventionné — à dire tel quel dans l'angle
compagnon (« 41 € de train après remboursement employeur vs ~350 € de voiture, carburant et usure
seuls »).

## Limites connues

- **Forfaits `attente_ter`, egress (6 min), accès+attente TC (7 min), vélo 16 km/h** : ordres de
  grandeur, non mesurés commune par commune. Classement *relatif* robuste ; comparaisons
  *inter-modes* à ~±10 %.
- **Voiture** : temps routés **avec trafic** (TomTom, `scripts/route_voiture_tomtom.py` →
  `data/interim/voiture_lille_tomtom.csv`, `departAt` mardi 08:00, trafic récurrent ; 411/411 OK).
  Le facteur de pointe flat 1,35 (ancien modèle OSRM, conservé en fallback) est remplacé par le
  différentiel de congestion réel par itinéraire (`voiture_bouchons_min`). Restent des hypothèses :
  +8 min stationnement, 100 €/mois parking (coût). Trafic modélisé pour un mardi type, hors vacances.
- Les **124 « sans option car-free »** sont *sans option dans les modes modélisés* : un rabattement
  bus (Tadao Béthune-Lens, Transvilles, Évéole, DK'Bus) vers la gare en sauverait une partie.
  **Décision : non modélisé en V1** — ces communes alimentent l'angle compagnon « voiture
  indispensable » et se classent en bas, ce qui est légitime. V2 possible si besoin.
- `velo_ter_min` : rabattement vélo jusqu'à 5 km = « possible », pas « typique ».
- **Régularité / ponctualité TER** : la donnée SNCF `regularite-mensuelle-ter` n'existe qu'à
  l'échelle **régionale** (`scripts/download_regularite_ter.py` → `data/raw/sncf/regularite_ter_hdf.csv`,
  historique 2018→2026 : HdF ≈ **89 % de régularité, 2,5 % d'annulations** sur 12 mois, pire mois
  juin 2026 à 86 % / 5,2 %). Ne discrimine pas les communes → encadré méthodo + graphe compagnon.
  Le critère `trains_arr_lille_matin` capte partiellement la résilience (fréquence = tampon en cas
  d'annulation). **Mesure réelle par ligne/gare** : collecte GTFS-RT en cours — voir
  `data/rt/README.md`. `scripts/poll_ter_rt.py` interroge le flux GTFS-RT SNCF national (sans clé)
  et enregistre retards + annulations des TER vers Lille aux 75 gares suivies ;
  `.github/workflows/poll-ter-rt.yml` le lance toutes les 5 min sur les pointes (semaine), commit
  `data/rt/updates/`. Après 3-4 semaines → `build_regularite_reelle.py` (à écrire) → ponctualité
  par ligne, intégrable au thème transport (poids ~4) + angle compagnon.

---

# Critère TRANSPORT — bouclé (V1). Colonnes pour le scoring

Grille de scoring (`grille_ponderation_lille.xlsx`, thème transport, 8 critères, poids interne 33) :

| dimension | colonne | sens | poids |
|---|---|---|--:|
| **Meilleur trajet alternatif à la voiture** (pilier, park & ride inclus) | `meilleur_temps_vers_lille_min` | inverser | 7 |
| Dépendance voiture | `ratio_alternatif_vs_voiture` (0 NaN) | inverser | 4 |
| Option 100 % sans voiture | `option_sans_voiture` (binaire) | normal | 3 |
| Fréquence pointe matin | `trains_arr_lille_matin` | normal | 5 |
| Coût mensuel du meilleur mode | `cout_mensuel_meilleur_mode_eur` | inverser | 4 |
| Congestion | `indice_congestion` (fichier bouchons) | inverser | 4 |
| Accès physique à une gare | `acces_gare_proche_moy_min` | inverser | 3 |
| Réseau cyclable | `cyclable_util_km_1000hab` | normal | 3 |

Décision (2026-08-27) : le pilier n'est **plus** `temps_sans_voiture_min` (124 NaN à imputer) mais
`meilleur_temps_vers_lille_min`, qui **inclut le park & ride** (voiture jusqu'à la gare utile + TER).
Le rabattement voiture est un usage réel massif, bien plus fréquent que vélo+TER. Les 124 communes
« captives » restent pénalisées proprement (park & ride ~66 min médian, `ratio_alternatif` ≈ 1,
`option_sans_voiture` = 0) sans valeur inventée. Limite : `cout_mensuel_meilleur_mode` du park & ride
ne compte que l'abo TER, pas la possession + le rabattement voiture (~+30 €/mois).

Collinéarités connues : `temps_*` ↔ `cout_*` (r ≈ 0,85).
`trains_arr_lille_matin` et `ratio_alternatif_vs_voiture` sont les dimensions les plus indépendantes.
- `porte_a_porte_median_min` (accès + temps de train seul, sans attente/egress) conservé comme
  sous-composant.
- Accès gare = **voiture** : réel (BPE/Metric-OSRM) si gare sur place, sinon itinéraire TomTom
  avec trafic (`departAt` 07:30).
- **Correspondances TER non modélisées** (~120 communes routées en voiture vers une gare bien
  desservie ; un TER + 1 corresp. serait parfois mieux → V2).
- **Réseaux urbains hors MEL non traités** (Tadao Béthune-Lens, Transvilles Valenciennes, Évéole
  Douaisis, DK'Bus…) : pour les communes hors MEL, seul le TER + l'accès voiture à la gare compte
  en V1 (le rabattement bus vers la gare est une V2).
- Un seul mardi type.

## Aménagements cyclables — `scripts/build_cyclable_communes.py`

`data/output/cyclable_communes_candidates.csv` (13 col). Source : **Écolab / Tableau de bord des
mobilités durables**, indicateur *« Linéaire d'aménagements cyclables pour 1000 hab »* (fournisseur
**Geovelo**, [data.gouv.fr](https://www.data.gouv.fr/datasets/lineaire-damenagements-cyclables-pour-1000-hab)).
Millésimes **2022 → 2025** (`date_mesure` = 1ᵉʳ janvier). Fichier commune national, filtré 59/62,
remap géo 2026.

Format long : 1 ligne / commune × type (7 types). On sépare :
- **réseau utilitaire** (trajet domicile-travail) = pistes + bandes + double-sens + mixtes + voies bus ;
- **voies vertes** = loisir/nature, et gonfle artificiellement les villages traversés par une
  véloroute → sorties du pilier utilitaire (`voie_verte_km_1000hab`, pour info) ;
- **« autre »** (chemins non qualifiés) → ignoré.

| colonne | sens |
|---|---|
| `cyclable_util_km` | linéaire utilitaire **absolu** (2025) |
| `cyclable_util_km_1000hab` | indicateur natif Écolab restreint à l'utilitaire — **winsoriser p90** au scoring (véloroute ÷ village = valeur délirante) |
| `pistes_protegees_km_1000hab` | pistes en site propre seules (qualité) |
| `part_amenagements_proteges_pct` | pistes / réseau utilitaire (`NaN` si 0 km — 79 communes) |
| `cyclable_util_km_2022`, `cyclable_util_evol_km`, `cyclable_util_evol_pct` | **dynamique** 2022→2025 |

**Résultats** : médiane 0,68 km/1000 hab. Communes MEL **2× mieux dotées** (1,09 vs 0,53) et
progressent plus vite (+12 % vs +2 % sur 3 ans). L'**ex-bassin minier est le désert cyclable** :
Auchel 0,01 km/1000 hab (10 000 hab), Liévin 0,08, Harnes 0,19, Bruay-la-Buissière 0,47 — et
plusieurs **régressent** (Liévin −18 %, Harnes −31 %, Anzin −33 %). Recoupe presque exactement les
communes « double peine » de l'angle bouchons. Plus fortes constructions 2022→2025 : Tourcoing
(+17 km), Lille (+17), Roubaix (+15), Valenciennes (+9), Hazebrouck (+8).

**Limite** : l'évolution inter-millésimes reflète *en partie* l'amélioration de la donnée OSM/Geovelo
(reclassements, complétude), pas seulement des travaux réels — les **baisses** sont à lire avec
prudence. Utiliser surtout le niveau 2025 ; l'évolution comme signal directionnel faible.

## Navetteurs vers la MEL — `scripts/build_navetteurs_mel.py`

`data/output/navetteurs_mel_communes_candidates.csv` (12 col). Indicateur **inédit** répondant à
« des actifs comme moi font-ils déjà ce trajet ? ». Source : **Insee, base flux mobilité
domicile → lieu de travail 2021** (déjà téléchargée), remap géo 2026 origine + destination.
MEL = 95 communes (EPCI 200093201).

| colonne | sens |
|---|---|
| `actifs_occupes` | actifs occupés résidant dans la commune (base flux) |
| `navetteurs_mel_nb` / `navetteurs_lille_nb` | effectif travaillant dans la MEL / à Lille intra-muros |
| `part_actifs_vers_mel_pct` | **part** des actifs de la commune travaillant dans la MEL |
| `part_actifs_vers_lille_pct` | idem, Lille seule |
| `part_actifs_travail_sur_place_pct` | travaillent dans leur commune de résidence (auto-suffisance) |
| `part_actifs_navette_hors_mel_pct` | navette vers ailleurs (Douaisis, bassin minier, littoral…) |

**Résultats** : commune hors MEL médiane = 11 % de ses actifs vers la MEL. Mais la **Pévèle**
(Camphin-en-Pévèle 68 %, Gondecourt 67 %, Cysoing 63 %) et la **Lys** (Nieppe 65 %, Sailly-sur-la-Lys
58 %) sont déjà des banlieues de fait — 2 actifs sur 3. À l'inverse les villes lointaines sont
autonomes : Boulogne 1 %, Calais 2 %, Dunkerque 3,6 % — « travailler à Lille » n'y est pas un sujet.
Plus gros contingents bruts : Carvin (2 700), Bailleul (2 500), Hénin-Beaumont, Douai.

**Nature de l'indicateur** : préférence *révélée* — il intègre déjà tout ce que les gens ont pesé
(prix, transport, proximité). Part circulaire (commune bien reliée → part élevée) mais c'est
précisément ce qu'on veut mesurer : la viabilité éprouvée du choix. Note Insee : flux < 200 =
ordres de grandeur ; les **parts** restent fiables.

## Passoires thermiques / performance du parc — `scripts/download_dpe_ademe.py` + `build_dpe_communes.py`

`data/output/dpe_communes_candidates.csv` (13 col). Source : **ADEME, « DPE Logements existants
depuis juillet 2021 »**, agrégats par commune via l'API data-fair (`meg-83tjwtg8dyz4vv7h1dqe`),
cumul 07/2021 → 08/2026. **742 744 DPE** couvrant les 411 communes.

| colonne | sens |
|---|---|
| `dpe_n` | taille de l'échantillon (nb de DPE) — pondère la confiance |
| `part_passoires_pct` | **(F + G) / total** — logements soumis à l'interdiction progressive de louer |
| `part_dpe_g_pct` | G seuls (les pires) |
| `part_dpe_abc_pct` | parc performant |
| `dpe_conso_ep_m2` | conso moyenne énergie primaire kWh/m²/an |
| `dpe_cout_moyen_eur` | facture énergie annuelle moyenne (5 usages) — **confondu par la taille du logement**, à utiliser prudemment |
| `dpe_echantillon_faible` | `dpe_n < 50` (0 commune ici) |

**Résultats** : médiane 10 % de passoires, MEL 7,6 % vs hors MEL 10,9 %. Concentration dans
l'**ex-bassin minier** (Avion 17 %, Vieux-Condé 16 %, Fenain, Vendin-le-Vieil, Mazingarbe, Auchel
14 %) et les anciennes villes textiles / Cambrai — le parc de corons et de maisons 1930 est
thermiquement médiocre. Le mieux classé : communes péri-urbaines récentes (Lesquin, Roncq,
Lys-lez-Lannoy, Villeneuve-d'Ascq 4-5 %). **Convergence** avec bouchons + désert cyclable : le
bassin minier cumule.

**LIMITE MAJEURE** (encadré méthodo obligatoire) : ce n'est **pas le parc complet**, seulement les
logements passés au DPE depuis 07/2021 (ventes, mises en location, rénovations). Sur-représentation
des logements en transaction, biais possible vers le locatif dans les grandes villes. Proxy, pas
recensement — croiser avec `part_logts_vacants` et l'âge du parc (`cadre_urbain`).

## Risques naturels et miniers — `scripts/download_georisques.py` + `build_georisques_communes.py`

`data/output/georisques_communes_candidates.csv` (17 col). Source : **API Géorisques** (MTE) —
`gaspar/risques` (risques recensés au DDRM) + `gaspar/catnat` (historique des arrêtés de
catastrophe naturelle depuis 1982). Indicateur **inédit** pour un « où vivre », très régional.

| colonne | sens |
|---|---|
| `risque_minier` | aléa minier (affaissement, effondrement, gaz de mine) — **113 communes, 876 000 hab**, tout l'ex-bassin, **0 dans la MEL** |
| `risque_inondation`, `risque_remontee_nappe`, `risque_mvt_terrain`, `risque_techno` | flags DDRM |
| `nb_risques_naturels` | somme des 4 flags naturels |
| `catnat_inondation_n` | nb d'arrêtés CatNat inondation/coulée de boue (fréquence réelle) |
| `catnat_inondation_depuis_2010_n` | idem, récents |
| `catnat_secheresse_n` | arrêtés CatNat sécheresse = **proxy dégâts retrait-gonflement argiles** (fissures) |
| `catnat_total_n`, `catnat_derniere_annee` | volume total, dernier épisode |
| `catnat_inondation_par_decennie` | `catnat_inondation_n` / 4,3 |

**Résultats** : l'**aléa minier** dessine exactement l'ex-bassin (aucune commune MEL). L'**inondation**
frappe la vallée de la Lys et de l'Aa — Aire-sur-la-Lys et Saint-Omer 18 arrêtés (7 depuis 2010,
dernier **2024**), Hazebrouck, Merville, Bailleul, Robecq (dernier **2026**) : c'est le territoire
des **crues du Pas-de-Calais 2023-2024**. La **sécheresse/argiles** vise la Flandre intérieure
(Bailleul, Hondschoote, Wormhout, Esquelbecq…) et le Dunkerquois. Cumul de 4 risques : la frange
minière de Béthune-Bruay (Auchel, Bruay-la-Buissière, Calonne-Ricouart). **96 communes** sans aléa
minier ni inondation DDRM.

**Convergence** : le bassin minier cumule bouchons + désert cyclable + passoires + aléa minier ;
la Lys/Flandre cumule inondation + sécheresse.

**Limites** : un arrêté CatNat dépend en partie d'une demande de la mairie (léger biais de report) ;
événements pré-1982 non comptés ; « coulées de boue » agrégées avec les crues de rivière. Le flag
DDRM et l'historique CatNat peuvent diverger (ex. Lens : `risque_inondation=0` mais 7 arrêtés) →
privilégier les comptages CatNat comme signal principal.

## Retrait-gonflement des argiles (RGA) — `scripts/build_rga_communes.py`

`data/output/rga_communes_candidates.csv` (10 col). **1ᵉʳ poste de sinistralité CatNat en France**
depuis les sécheresses 2018-2022. Depuis la loi ELAN (2020), **étude de sol obligatoire avant de
construire en aléa moyen ou fort** (+ fondations renforcées, surcoût 2-5 k€).

Source : **DREAL Hauts-de-France / BRGM**, couche « Aléa retrait-gonflement des argiles »
(shapefile régional `n_alea_rga_s_r32`, 3 classes Faible/Moyen/Fort). **Overlay surfacique** avec
les contours communes IGN ADMIN-EXPRESS 2026 (Lambert-93).

| colonne | sens |
|---|---|
| `rga_pct_moyen_fort` | **part de la surface communale en aléa moyen + fort** (l'indicateur qui compte) — médiane 14 %, p90 **95 %** |
| `rga_pct_fort` / `rga_pct_moyen` / `rga_pct_faible` | détail par classe |
| `rga_alea_dominant` | classe majoritaire (nul 43 / faible 227 / moyen 127 / fort 14) |

**Résultats** : **131 communes (938 000 hab) majoritairement en aléa moyen+fort**. Foyers : le
**Bas-Pays / Weppes** (Bois-Grenier, Herlies, Fromelles, La Chapelle-d'Armentières à 100 % — mêmes
communes que les pires bouchons), la **Pévèle / Ostrevent** en aléa **fort** (Aniche 84 %,
Cappelle-en-Pévèle 77 %, Somain, Templeuve), le **Dunkerquois argileux** (Bourbourg,
Coudekerque-Branche). Discrimine bien (contrairement à l'air). Remplace `catnat_secheresse_n`
au scoring (celui-ci = historique de dégâts, gardé en contexte).

## Reste à vivre — `scripts/build_reste_a_vivre.py`

`data/output/reste_a_vivre_communes_candidates.csv` (15 col). Indicateur **inédit, composite** :
ce qui reste au ménage après **logement + trajet domicile-travail**. Synthèse de tout le pipeline.

Ménage de référence : **niveau de vie médian local, 1,5 UC** (couple sans enfant, convention Insee).
Montants **mensuels**. Sources : **Insee FiLoSoFi 2021** (`Q221` niveau de vie médian, `TP6021`
taux de pauvreté — dernier millésime, 2022 annulé) ; `cadre_urbain` (prix/loyers maison, avril
2026) ; `transport` (coût du trajet). Revenus 2021 rehaussés × **1,13** (croissance nominale
2021→2026) pour cohérence avec les prix 2026.

| colonne | hypothèse |
|---|---|
| `revenu_dispo_ref_mois_eur` | `Q221 × 1,13 × 1,5 / 12` |
| `cout_achat_maison_mois_eur` | maison **95 m²** (médiane NPDC), apport 10 %, prêt **25 ans à 3,6 %**, annuité constante |
| `cout_location_maison_mois_eur` | `loyers_maison_m2 × 95` |
| `cout_transport_mois_eur` | trajet **sans voiture** s'il existe (arbitrage budgétaire), sinon coût voiture estimé (`transport_contraint_voiture` = vrai) |
| `reste_a_vivre_achat_eur` / `_location_eur` | revenu − logement − transport |
| `taux_effort_achat_pct` / `_location_pct` | (logement + transport) / revenu |

**Résultat central** (contre-intuitif) : `prix_maison_m2` corrèle **positivement** avec
`reste_a_vivre_achat` (**r = +0,56**). Les communes chères laissent **plus** d'argent, pas moins :
le revenu local médian corrèle à +0,79 avec le prix, donc l'écart de revenu écrase l'écart de
prix. Acheter « pas cher » = souvent acheter là où on gagne peu.
- Meilleur reste à vivre : Pévèle + Artois périurbain aisé (Mérignies, Vaudricourt, Aix-en-Pévèle,
  Anzin-Saint-Aubin) — 2 800-3 400 €/mois, effort 22-33 %.
- Pire : Denaisis + frange minière + vallée de l'Escaut (Denain, Auchel, Bruay-la-Buissière,
  Condé-sur-l'Escaut) — 850-1 100 €/mois, effort 50-70 %, revenu bas **et** voiture obligatoire.
- Denain : maison la moins chère du panel (969 €/m²) mais reste à vivre ~1 000 €/mois.

**LIMITE MAJEURE** : construction à hypothèses (surface, taux, durée, UC, 100 €/mois parking hérité
du volet transport, facteur revenu). **Ordres de grandeur pour comparer les communes**, pas une
vérité sur un ménage donné. À présenter comme une simulation, jamais comme une mesure.

---

# Santé — accès aux soins de premier recours (APL)

`scripts/build_sante_communes.py` → `data/output/sante_communes_candidates.csv` (1 ligne / commune candidate).

Source : **DREES-Irdes, Accessibilité Potentielle Localisée (APL), millésime 2024** (méthodologie la
plus récente ; [data.gouv.fr](https://www.data.gouv.fr/datasets/accessibilite-potentielle-localisee-apl-aux-professionnels-de-sante)).
Indicateur **communal** d'adéquation offre/demande, tenant compte de l'offre des communes
environnantes (décroissance avec la distance), du niveau d'activité des professionnels et de la
structure par âge de la population.

| colonne | profession | unité |
|---|---|---|
| `apl_mg` | médecins généralistes | consultations/visites accessibles par habitant (standardisé) / an |
| `apl_mg_m65` | médecins généralistes **≤ 65 ans** (indicateur prospectif, hors proches retraite) | idem |
| `apl_inf` | infirmières | ETP pour 100 000 hab |
| `apl_kine` | masseurs-kinésithérapeutes | ETP / 100 000 hab |
| `apl_dent` | chirurgiens-dentistes | ETP / 100 000 hab |
| `apl_sf` | sages-femmes | ETP / 100 000 hab (pop. féminine) |
| `apl_mg_2022`, `apl_mg_evol_pct` | **trajectoire** APL généralistes 2022 → 2024 (même méthodo) | % — à lire en tendance (la standardisation ne corrige pas le vieillissement) |

`pop_std_sante`, `pop_totale_2022` fournis (pondération pour agrégation supra-communale).
Plus la valeur est élevée, meilleur l'accès. Géo 2024 → 2026 (mêmes fusions que le périmètre,
pondération pop standardisée).

## Accès aux établissements de santé (BPE)

Temps d'accès routier (voiture, Metric-OSRM, **millésime BPE 2025**, parquet `reg=32`), moyenne
pondérée population sur les carreaux de la commune + temps mini :

| colonnes | équipement BPE |
|---|---|
| `acces_urgences_moy_min` / `_min_min` | **D106** urgences (SAMU-SMUR + accueil) |
| `acces_maternite_moy_min` / `_min_min` | **D107** maternité (gynéco-obstétrique) |
| `acces_hopital_moy_min` / `_min_min` | **D101** établissement de santé court séjour (MCO) |
| `acces_pharmacie_moy_min` / `_min_min` | **D307** pharmacie d'officine |
| `acces_msp_moy_min` / `_min_min`, `msp_sur_place` | **D113** maison de santé pluridisciplinaire (signal anti-désertification) |

## Résultats

APL médecins généralistes 2024 : France 3,7 · candidats **4,6** · MEL 5,3 · hors MEL 4,2
(le bassin lillois est mieux doté que la moyenne nationale). 6 communes candidates sous 2,5
(proche du seuil de sous-dotation DREES) : Hardinghen, Féchain, Sailly-lez-Lannoy, Hondschoote,
Monchecourt, Watten.

**Trajectoire 2022 → 2024** : APL généralistes **en baisse dans 296 communes sur 411** (médiane
−3,5 %). Dégradations les plus fortes : Bucquoy −19 %, Quiévy −16 %, Cambrai −15 %, Denain −13 %.
(Part de la baisse imputable au vieillissement — présenter en tendance.)

Accès (médiane / max, communes > 20 min) : urgences 11 / 29 min, 35 communes · maternité
12 / 28 min, 37 communes · hôpital 9 / 25 min, 12 · **pharmacie 2 / 9 min, 0** et **MSP 6 / 17 min, 0**
— pharmacie et MSP ne discriminent quasiment pas : à garder pour la transparence, poids quasi nul.
**146 communes sur 411** ont une maison de santé pluridisciplinaire sur leur territoire.

## Notes pour le scoring (hors périmètre de ce script)

- Les 4 APL « ville » (`mg`, `kine`, `dent`, `sf`) sont fortement corrélées (r 0,77–0,92) → éviter
  de sommer 5 quasi-doublons ; `apl_inf` est plus indépendant (r ~0,55).
- Accès urgences / maternité / hôpital corrélés (r 0,81–0,93, souvent le même site hospitalier)
  → un composite « accès hospitalier », en gardant éventuellement la maternité à part (poids
  éditorial « familles »).
- APL vs temps d'accès : faiblement corrélés (r −0,2 à −0,5) → deux dimensions distinctes à
  conserver toutes les deux.

## Pistes santé non retenues en V1

- **Crèche / EAJE (BPE D502)** : très pertinent pour des actifs parents de jeunes enfants, mais
  relève plutôt d'un critère « famille / petite enfance » (avec école maternelle C101) → à traiter là.
- Pédiatre (D210), gynécologue (D214), laboratoire d'analyses (D302) : discrimination faible ou
  redondance avec l'APL → écartés.

## Critère SANTÉ — bouclé (V1). Colonnes pour le scoring

| dimension | colonne(s) | poids pressenti |
|---|---|---|
| Accès médecine de ville | `apl_mg` (+ `apl_mg_m65` prospectif) | fort |
| Accès soins infirmiers | `apl_inf` (dimension indépendante) | moyen |
| Kiné / dentiste / sage-femme | `apl_kine`, `apl_dent`, `apl_sf` (corrélées → 1 composite) | moyen |
| Trajectoire | `apl_mg_evol_pct` | faible (tendance) |
| Accès hospitalier | composite `acces_urgences` / `acces_hopital` + `acces_maternite` à part (familles) | fort |
| Pharmacie / MSP | `acces_pharmacie`, `msp_sur_place` | quasi nul (transparence) |

**Encadré méthodo** : APL = ambulatoire premier recours (pas de spécialistes, pas en open data) ·
évolution 2022→2024 biaisée par le vieillissement, à lire en tendance · temps d'accès = voiture.

---

# Commerces / services du quotidien

`scripts/build_commerces_communes.py` → `data/output/commerces_communes_candidates.csv` (20 col).

**Temps d'accès routier** (BPE **2025**, Metric-OSRM, moy. pondérée pop. + mini ; min par carreau
si plusieurs codes) : `acces_supermarche` (B104/B105), `acces_epicerie` (B201/B202),
`acces_boulangerie` (B207), `acces_boucherie` (B204), `acces_poste` (A206/A207/A208),
`acces_decheterie` (A133).
→ En zone dense, ces temps **discriminent peu** (médianes 2–3 min, aucun > 15 sauf déchetterie) :
à garder pour la transparence, poids faible — comme la pharmacie en santé.

**Stock** (BPE **2024**, `data/raw/bpe_stock/BPE24.parquet`) :
- **`commerces_essentiels_sur_place`** (0–7) — nb de catégories présentes physiquement dans la
  commune parmi : grande surface alim., boulangerie, épicerie, boucherie, pharmacie, poste,
  banque. **C'est le vrai indicateur discriminant** (médiane 5 ; 113 communes à 7 ; **82 communes
  à ≤ 2** — bourgs-dortoirs sans vie commerçante : Camphin-en-Pévèle, Ennevelin, Lompret,
  Prémesques…).
- `resto_pour_1000hab` (A504) — à **winsoriser p95** (artefact des zones commerciales :
  Lezennes 21/1000, Noyelles-Godault 7/1000).

*Millésime : temps d'accès en BPE 2025, densités en BPE 2024 (dernier stock publié).*

---

# Sécurité

`scripts/build_securite_communes.py` → `data/output/securite_communes_candidates.csv` (~19 col).

Source : **SSMSI, base statistique communale de la délinquance** (`ssmsi.parquet` du projet retraite,
clé `CODGEO_2025`). **Moyenne des taux 2022-2024** (robustesse) + colonnes `*_2024` (année de
l'atlas officiel « Géographie de la délinquance 2024 »).

| colonne | fait | unité SSMSI |
|---|---|---|
| `cambriolages_taux` | cambriolages de logement | pour 1 000 **logements** |
| `vols_sans_violence_taux` | vols sans violence contre des personnes | pour 1 000 hab |
| `vols_dans_vehicules_taux` | vols dans les véhicules (effractions) | pour 1 000 hab |
| `vols_de_vehicule_taux` | vols de véhicule | pour 1 000 hab |
| `degradations_taux` | destructions et dégradations volontaires | pour 1 000 hab |
| `violences_hors_famille_taux` | violences physiques hors cadre familial — **option, non retenue par le retraite** | pour 1 000 hab |

Tous *« moins c'est mieux »* → `Inverser`, **winsorisation p95** au scoring.
Cellules sous secret statistique (`ndiff`) : remplacées par l'estimation lissée SSMSI
(`complement_info_taux`). `securite_pct_estime` donne la part par commune.

**Limite majeure (encadré méthodo)** : **~45 % des cellules commune × indicateur sont sous secret
statistique** et donc estimées par modèle. Les écarts entre petites communes sont à prendre avec
prudence. La moyenne 3 ans + la winsorisation + le composite atténuent le bruit.

**Résultat** (contre-intuitif, à assumer) : les cambriolages frappent surtout les communes
**résidentielles aisées** (Bondues, Forest-sur-Marque, Avelin, Fleurbaix) — plus à voler, maisons
individuelles, absents en journée. Calais est « sûre » pour le cambriolage mais élevée sur les vols
sans violence et les dégradations → l'intérêt du composite multi-indicateurs.

---

# Éducation / petite enfance (thème nouveau vs le retraite)

`scripts/build_education_communes.py` → `data/output/education_communes_candidates.csv` (24 col).

| dimension | colonnes | source | discrimine ? |
|---|---|---|---|
| Accès crèche / maternelle / élémentaire / collège / lycée | `acces_*_moy_min` / `_min_min` | BPE 2025 (D502, C107/C108/C109, C201, C301/C302) | maternelle/élémentaire **non** (école partout, méd. 1,7 min) ; collège / lycée / crèche **oui** |
| Sur le territoire | `ecole_sur_place` (410/411), `college_sur_place` (159/411), `creche_sur_place` (179/411) | BPE 2024 stock | collège & crèche **oui** |
| Places de crèche collective | `places_creche`, `places_creche_col_pour_100_moins3` (estimé, **hors assistantes maternelles**) | BPE 2024 `CAPACITE` D502 + Insee 0-14 ans 2022 | oui |
| **Couverture petite enfance (tous modes)** | `couverture_petite_enfance_epci` (+ `_creche_epci`, `_assmat_epci`) | **CNAF Cafdata `txcouv_pe_epci` 2023** — échelle **EPCI** (le communal n'existe que > 10 000 hab) | oui |
| Contexte | `part_0_14ans` | Insee RP 2022 | descriptif |

**Résultat marquant** : la couverture petite enfance (places pour 100 enfants < 3 ans, tous modes)
va de **41-49 dans l'ex-bassin minier** (Lens-Liévin 48,5, Valenciennes 50,4, Béthune-Bruay /
Douaisis 55,6) à **74-80 dans la Pévèle et la Flandre rurale** (Pévèle-Carembault 76, Hauts de
Flandre 79,5), MEL au milieu (62,4). Les territoires qui en auraient le plus besoin en ont le moins.

**Limites** : couverture CNAF au niveau **EPCI** (toutes les communes d'un même EPCI ont la même
valeur) ; `places_creche` BPE = accueil **collectif** seulement (les assistantes maternelles,
mode dominant en périurbain, n'y sont pas — d'où l'apport du taux CNAF tous modes).

---

# Sport & nature

`scripts/build_sport_nature_communes.py` → `data/output/sport_nature_communes_candidates.csv` (17 col).

| dimension | colonnes | source |
|---|---|---|
| Accès piscine / fitness / randonnée / gymnase | `acces_*_moy_min` / `_min_min` | BPE 2025 (F101, F120, F203, F121) |
| Clubs sportifs licenciés | `nb_clubs_actifs`, `clubs_pour_1000hab` (méd. 1,8 · p95 3,3) | INJEP 2023 (`clubs-data-2023.csv`) |
| **Population à < 300 m d'un espace vert** | `part_pop_ev_300m` | carreaux 200 m Insee (`carreaux_59_62.gpkg`) + **espaces verts OSM ré-extraits sur tout le 59/62** (Geofabrik, `scripts/extract_espaces_verts_osm.py` → `data/raw/geo/espaces_verts_osm_5962.gpkg`, 85 000 polygones), buffer 300 m |
| **Surface d'espace vert par habitant (m²)** | `surf_ev_m2_par_hab` (méd. 312 · max 10 280) | idem × contour communal IGN Admin Express COG-CARTO 2026 |

**Note** : `part_pop_ev_300m` discrimine peu (méd. 98 %, q25 92 %) — presque partout on est près
d'un bois ou d'une prairie. La **queue basse est parlante** : ex-bassin minier (Grenay, Haillicourt,
Sains-en-Gohelle, Marquette-en-Ostrevant 30-56 %) — coron denses, peu de vert.
`surf_ev_m2_par_hab` discrimine bien mieux. Réserve OSM : la couverture dépend de la qualité de
cartographie locale.

**Espaces verts OSM** : Overpass API inaccessible depuis le réseau pro → extrait Geofabrik
`nord-pas-de-calais.osm.pbf` lu hors ligne via le pilote OSM de GDAL (couche `multipolygons`).

---

# Environnement

`scripts/build_environnement_communes.py` → `data/output/environnement_communes_candidates.csv` (13 col).

| dimension | colonnes | source |
|---|---|---|
| Qualité de l'air | `indice_atmo_moyen`, `air_pct_jours_bons` (≤ 2), `air_pct_jours_degrades` (≥ 3), `air_pct_jours_mauvais` (≥ 4), `air_nb_jours` | **Atmo Hauts-de-France**, indice ATMO communal journalier, **1ᵉʳ jan → 9 juil. 2026** (169 j) — `scripts/download_atmo.py`, FeatureServer ArcGIS |
| Artificialisation (flux) | `artif_pct_2009_2024` (méd. 1,7 % · p90 5,0 %) | CEREMA / Observatoire artificialisation, `conso2009-2024-resultats-com.csv` |
| Imperméabilisation (stock) | `imper_pct_2021` (méd. 13 % · p90 38 %), `imper_flux_2018_2021` | CEREMA, `imper_commune.csv` |

Tous *« moins c'est mieux »* → `Inverser`.

**Limites** :
- **L'indice ATMO discrimine très peu** (`indice_atmo_moyen` : p10 2,37 → p90 2,43) — la pollution
  de fond est régionale, la variation communale est marginale (industriel dunkerquois + corridor
  NE Roubaix-Tourcoing-VdA légèrement au-dessus). À garder au poids du template mais impact réel faible.
- Fenêtre air **jan → 9 juillet** (le service Atmo « année en cours » a du retard ; août manquant).
  Échantillon hiver-lourd → `pct_jours_mauvais` (12 %) sans doute un peu surévalué vs année pleine.
- **`imper_pct_2021` est corrélé à la densité urbaine** → il pénalise les communes denses de la MEL
  (Roubaix, La Madeleine 70-76 %) qui sont par ailleurs les mieux desservies. Tension éditoriale
  à assumer, pas à masquer.

---

# Cadre urbain / logement

`scripts/build_cadre_urbain_communes.py` → `data/output/cadre_urbain_communes_candidates.csv` (18 col).

| dimension | colonnes | source |
|---|---|---|
| Logement | `part_logts_vacants` (méd. 5,5 %), `part_maisons`, `part_proprietaires`, `part_hlm` | **Insee RP 2023** (base chiffres clés logement, **géo 01/01/2026** = notre périmètre) |
| **Motorisation des ménages** | `part_menages_sans_voiture` (méd. 9,6 %), `part_menages_2voit_plus` (méd. **45 %**, p90 59 %) | Insee RP 2023 — **révélateur de dépendance auto réelle** (Bondues 56 %, Gruson 65 %…) |
| Marché immobilier | `prix_maison_m2` (méd. 1 878), `prix_appart_m2`, `loyers_maison_m2`, `loyers_appart_m2`, `evol_prix_maison_1an_pct`, `delai_vente_jours` | SeLoger / MeilleursAgents IPI **avril 2026** (`prix_avril_2026.xlsx`) |
| Dynamique démographique | `evol_pop_2016_2022_pct` (méd. +0,3 %, p10 −4,1 %) | Insee, évol. et structure de la population 2022 |

**Note scoring** : `prix_maison_m2` — poids **volontairement faible** (comme le retraite, 0,8 %) :
les communes les moins chères (Denain, Lourches, Auchel à ~1 000 €/m²) ont aussi une **forte
vacance et une population en déclin** — la cheapness reflète un marché en détresse, pas une bonne
affaire. `part_logts_vacants` + `evol_pop` donnent le contexte.
`part_menages_2voit_plus` / `part_menages_sans_voiture` : classées ici mais **pourraient alimenter
le thème transport** (dépendance auto révélée, complément du `ratio_sansvoiture_vs_voiture` modélisé).

---

# ✅ Tous les critères construits (8 thèmes)

| thème | fichier | col | statut |
|---|---|--:|---|
| Périmètre | `communes_candidates.csv` | 12 | ✅ |
| Transport | `transport_communes_candidates.csv` | 64 | ✅ |
| Santé | `sante_communes_candidates.csv` | 26 | ✅ |
| Commerces | `commerces_communes_candidates.csv` | 20 | ✅ |
| Éducation / petite enfance | `education_communes_candidates.csv` | 24 | ✅ |
| Sécurité | `securite_communes_candidates.csv` | 19 | ✅ |
| Sport & nature | `sport_nature_communes_candidates.csv` | 17 | ✅ |
| Environnement | `environnement_communes_candidates.csv` | 13 | ✅ |
| Cadre urbain / logement | `cadre_urbain_communes_candidates.csv` | 18 | ✅ |

### Compléments transport + indicateurs inédits

| indicateur | fichier | col | statut |
|---|---|--:|---|
| Aménagements cyclables (Écolab/Geovelo) | `cyclable_communes_candidates.csv` | 13 | ✅ |
| Navetteurs MEL (préférence révélée) | `navetteurs_mel_communes_candidates.csv` | 12 | ✅ |
| Passoires thermiques (DPE ADEME) | `dpe_communes_candidates.csv` | 13 | ✅ |
| Risques naturels + aléa minier (Géorisques) | `georisques_communes_candidates.csv` | 17 | ✅ |
| Retrait-gonflement des argiles (DREAL/BRGM overlay) | `rga_communes_candidates.csv` | 10 | ✅ |
| Reste à vivre (FiLoSoFi − logement − trajet) | `reste_a_vivre_communes_candidates.csv` | 15 | ✅ |
| Bouchons (angle compagnon) | `bouchons_communes_lille.csv` | 20 | ✅ |

**Convergence géographique** (colonne vertébrale narrative) : l'ex-bassin minier (Denaisis + frange
Béthune-Bruay) cumule bouchons + désert cyclable + passoires + aléa minier + reste à vivre faible +
zéro alternative voiture. La Lys/Flandre cumule inondation + sécheresse-argiles. La Pévèle / l'Artois
périurbain aisé domine presque tous les axes.

# Scoring — architecture

`scripts/build_grille_ponderation.py` → **`data/output/grille_ponderation_lille.xlsx`** (+ `.csv`).
Modèle : classement retraite + système d'étoiles Lovable.

- **9 thèmes à étoiles** (le lecteur règle 1-5 ★ par thème sur `/personnaliser`) : transport,
  prix_immobilier, sante, education, securite, cadre_urbain, environnement, commerces, sport_nature.
  `vie_sociale` supprimé (pas de ciné/biblio/musée en data) ; `immobilier` redevient un thème à part
  (prix très concret pour le lecteur).
- **40 critères**, poids **fixes à l'intérieur** de chaque thème (les points ne comptent
  qu'intra-thème — chaque `score_thème` est ramené 0-20).
- Méthode (notebook 12 retraite) : merge sur `code_insee` → **imputation** (médiane, ou `0`, ou `p90`
  selon la colonne `imputation` de la grille) → **winsorisation** (colonne `winsor` : p95, p90,
  p5_p95) → **normalisation 0-20 min-max** (`normal` = haut meilleur ; `inverser` = bas meilleur).
- `score_thème = Σ(score_critère × poids) / Σ(poids)` → 0-20.
- `score_global` (preset par défaut) `= Σ(score_thème × ★_défaut) / Σ(★_défaut)`.
- **Preset ★ par défaut** : transport 5 · prix_immobilier 4 · sante 3 · education 3 · securite 3 ·
  cadre_urbain 3 · environnement 3 · commerces 2 · sport_nature 2. (Le recentrage transport vit dans
  le preset, pas dans une pondération figée.)
- **Hors scoring** (contexte / fiche commune / curseur budget / angles) : `reste_a_vivre_*`,
  `bouchons_*` (sauf `indice_congestion`), `navetteurs_mel_*`, motorisation des ménages.
- Air : gardé (thème environnement, poids 4) mais discrimine faiblement → **V1.1** : concentrations
  NO₂/PM₂.₅ modélisées par commune (cartographie Atmo).

Sorties visées : `scores_0_20.csv`, `classement_final.json` (score_thème + score_global),
`scores_detail.json` (40 critères) pour l'appli Lovable.

`scripts/build_scoring.py` → `scores_0_20.csv`, `classement_final.json`, `scores_detail.json`.
`score_global` rescalé min-max 0-20 pour la lisibilité (rangs inchangés ; `score_global_brut`
conservé, tassé ~7,4-13,2). **v1 (2026-08-27)** : preset transport ★5 domine (r = +0,70 avec le
global). Top : Gondecourt, Marquette-lez-Lille, Saint-André-lez-Lille, Lesquin, Hazebrouck,
Erquinghem-Lys, Pont-à-Marcq, Templeuve, Seclin, Ronchin — communes bien reliées en bordure de MEL
+ Pévèle avec TER. Tensions connues : `securite` (r = −0,28) pénalise toute vraie ville
(délinquance ∝ services) ; le bas du classement = petits villages ruraux sans gare (Cambrésis,
Lys) — légitime pour « travailler à Lille » mais peu spectaculaire ; des villages prisés mais
captifs de la voiture (Gruson, Camphin) se classent bas — assumé (le classement porte sur le
trajet domicile-travail).

# Prochaines étapes

1. Caler les poids en regardant top/flop (v1 faite).
2. `verif-data` avant publication.
3. Angle compagnon « sans voiture » + curseur interactif + export Lovable.
3. Éventuelles V2 : correspondances TER, réseaux urbains hors MEL.
4. `verif-data` avant publication.

---

## Reproduire

```bash
python scripts/download_gtfs.py            # + --national pour le contrôle croisé
python scripts/build_desserte_ter_lille.py
python scripts/build_communes_candidates.py
```

```bash
python scripts/build_transport_communes.py
python scripts/build_ilevia_lille.py
python scripts/build_transport_final.py     # fusionne TER + Ilevia dans transport_communes_candidates.csv
python scripts/build_prix_ter.py            # ajoute les colonnes ter_* (coût abonnement)
python scripts/route_voiture_osrm.py        # temps/distance voiture fluide (OSRM, fallback) — 1×, réseau requis
python scripts/route_voiture_tomtom.py      # temps voiture AVEC TRAFIC (TomTom, clé requise) — 1×, ~3 min
python scripts/route_gare_utile_tomtom.py   # rabattement voiture→gare utile avec trafic — 1×, ~3 min
                                            #   (lit gare_utile_uic ; re-lancer build_transport_communes ensuite)
python scripts/build_transport_communes.py  # 2e passe : intègre le rabattement TomTom
python scripts/build_transport_final.py
python scripts/build_prix_ter.py
python scripts/build_transport_multimodal.py # vélo + voiture + trajet sans voiture
python scripts/analyse_bouchons.py         # -> bouchons_communes_lille.csv (angle compagnon)
python scripts/build_cyclable_communes.py   # aménagements cyclables Écolab/Geovelo 2022-2025
python scripts/build_navetteurs_mel.py      # part des actifs travaillant déjà dans la MEL
python scripts/download_dpe_ademe.py        # agrégats DPE ADEME 59/62 (API) — 1×
python scripts/build_dpe_communes.py        # passoires thermiques / perf. énergétique du parc
python scripts/download_georisques.py       # API Géorisques 411 communes (~6 min) — 1×
python scripts/build_georisques_communes.py # risques naturels + aléa minier
python scripts/build_rga_communes.py        # retrait-gonflement des argiles (overlay DREAL/IGN)
python scripts/build_reste_a_vivre.py       # reste à vivre (revenu FiLoSoFi − logement − trajet)
python scripts/build_grille_ponderation.py  # grille de scoring (9 thèmes, 40 critères)
python scripts/build_scoring.py             # -> scores_0_20.csv + classement_final.json + scores_detail.json
python scripts/build_sante_communes.py      # APL DREES -> sante_communes_candidates.csv
```

Fichiers Insee dans `data/raw/insee/` (via `download_insee.py`) :
`base-flux-mobilite-domicile-lieu-travail-2021-csv.zip`,
`table-appartenance-geo-communes-2026.zip`, `pop_legales_2021` (`ensemble.zip`),
`v_mvt_commune_2026.csv`.

Autres fichiers (téléchargés manuellement, cf. URLs dans les scripts / historique) :
- `data/raw/bpe_acces/donnees_2025_reg32.parquet` (934 Mo — accès équipements HdF, data.gouv.fr)
- `data/raw/geo/communes-59.geojson`, `communes-62.geojson` (contours communes, github france-geojson)
- `data/raw/ilevia/gtfs_sept.zip` (GTFS Ilévia septembre, `media.ilevia.fr/opendata/gtfs_sept.zip`)

Étapes intermédiaires (générées) : `data/interim/acces_gare_communes_5962.parquet`,
`communes_centroids_5962.csv`, `gares_ter_communes.csv`.

Dépendances : `gtfs_kit`, `pandas`, `numpy`, `geopandas`, `duckdb`, `python-calamine`,
`openpyxl` (env conda base).
