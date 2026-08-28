# Note d'angle — Les bouchons vers Lille, commune par commune

*Jeu de données : `data/output/bouchons_communes_lille.csv` (411 communes candidates du classement « Où vivre quand on travaille à Lille »). Temps voiture calculés via l'API TomTom Routing, départ mardi 15 septembre 2026 à 8 h, modèle de trafic récurrent. Code : `angle_bouchons_lille_2026-08-27.py`. Date : 27 août 2026.*

---

## 1. Contexte

### ctx_01 — Lille, 16ᵉ ville la plus embouteillée de France, et ça empire
TomTom Traffic Index 2025 : dans l'agglomération de Lille, un conducteur perd **66 heures par an** aux heures de pointe (référence : trajet urbain type de 10 km), soit **2 h 33 de plus qu'en 2024**. Lille se classe 16ᵉ au niveau national, derrière Marseille, Lyon ou Bordeaux mais devant Rennes ou Nantes.
*Source : TomTom Traffic Index 2025, tomtom.com/traffic-index, données 2024→2025.*

### ctx_02 — Le pire créneau, c'est le mardi matin
Article La Voix du Nord du 2 décembre 2024 (repris par Le Bonbon Lille le 3) sur le millésime TomTom 2023 : 47 heures perdues par an pour 10 km aux heures de pointe, et surtout **19 minutes 20 pour parcourir 10 km le mardi entre 8 h et 9 h**, contre 14 minutes 10 en moyenne. Surcoût carburant estimé : 104 € par an et par conducteur.
*Source : La Voix du Nord, 2 décembre 2024 ; TomTom Traffic Index 2023. → C'est exactement le créneau retenu pour notre calcul (mardi 8 h).*

### ctx_03 — La MEL paie déjà les gens pour éviter quatre axes saturés
Programme « Changer, ça rapporte » (Ecobonus) : 2 € par trajet en voiture évité aux heures de pointe, plafond 80 €/mois. Lancé en septembre 2023 sur l'**A1 et l'A23**, étendu en septembre 2024 à l'**A25 (Dunkerque–Lille) et la RN41 (La Bassée–Lille)**. Bilan communiqué : 2 376 participants, plus de 2 000 « effacements » de trajet par jour, objectif de −6 % de trafic déclaré atteint.
*Source : Métropole européenne de Lille, communiqués de presse 2023 et 2024.*

### ctx_04 — L'ouest lillois est identifié comme un point noir depuis des années
DREAL Hauts-de-France, études sur le contournement ouest de Lille : saturation reconnue de l'A1, de l'A25 et de l'itinéraire RN41/47, « diminution significative du niveau de service » aux heures de pointe. Projet de long terme : élargissement de l'A25 à 2×3 voies entre La Chapelle-d'Armentières et Englos, et dénivellation des nationales 41 et 47 (suppression des giratoires).
*Source : DREAL Hauts-de-France, synthèse « Amélioration du contournement Ouest de Lille ».*

### ctx_05 — 120 000 actifs entrent chaque jour dans la MEL, la moitié vient du bassin minier
Insee : 120 000 personnes rejoignent quotidiennement la MEL pour travailler depuis l'extérieur de la métropole ; la moitié de celles venant de l'extérieur de la MEL réside dans l'ex-bassin minier. Dans plusieurs communes (Hénin-Beaumont, Courcelles-lès-Lens, Béthune, Noyelles-Godault…), les trajets vers la métropole ont bondi de **68 % entre 2006 et 2014**. Distance médiane domicile-travail vers la MEL : **26 km** (+2,8 km en huit ans). Part de la voiture : 66,5 % dans la MEL, **80 à 86 % dans les intercommunalités périphériques**.
*Source : Insee Analyses Hauts-de-France n°81 et n°196 ; synthèse reprise en novembre 2024.*

### ctx_06 — On s'éloigne pour payer le logement moins cher
Le desserrement résidentiel vers le bassin minier et la Pévèle s'explique par des prix de l'immobilier « plus accessibles », la proximité géographique et les infrastructures (A1, A21, TER). La voiture reste « reine » : sur la période 2006-2014, sa part n'a reculé que de 2 points pour les actifs travaillant dans la MEL.
*Source : Insee ; Axe Culture Territoire, novembre 2024.*

---

## 2. Analyse

Tous les chiffres sont reproductibles via `angle_bouchons_lille_2026-08-27.py`. Trois indicateurs construits à partir du temps de pointe (`voiture_pointe_min`) et du temps fluide (`voiture_libre_min`) fournis par TomTom :

- **indice de congestion** = pointe ÷ fluide (1,00 = circulation libre ; 1,50 = trajet allongé de moitié) ;
- **minutes perdues** = pointe − fluide, pour un aller ;
- **part du trajet dans les bouchons** = minutes perdues ÷ temps de pointe.

### ana_00 — Structure
411 communes, aucune valeur manquante sur le temps voiture (routage TomTom 411/411). Champs mobilisés : `voiture_pointe_min`, `voiture_libre_min`, `bouchons_min`, `voiture_km`, `indice_congestion`, `part_trajet_bouchons_pct`, `h_perdues_an`, `sans_alternative` (aucun trajet sans voiture vers Lille), `PMUN` (population municipale).

### ana_01 — L'indice de congestion : +50 % en médiane, jusqu'à ×2
Distribution : p10 = 1,29 · **médiane = 1,49** · p90 = 1,79 · max = 2,02. Moyenne pondérée par la population : 1,48.
**40 communes** ont un indice ≥ 1,80 (trajet allongé d'au moins 80 %), représentant **240 000 habitants**. 14 communes ≥ 1,90. Deux communes ≥ 2,00 : **Bois-Grenier (2,02)** et **Wavrin (2,00)** — le trajet double.
Top 12 : Bois-Grenier, Wavrin, Noyelles-Godault, Évin-Malmaison, Libercourt, Illies, La Chapelle-d'Armentières, Salomé, Marquillies, Erquinghem-Lys, Fournes-en-Weppes, Noyelles-sous-Lens. Pour toutes, la part du trajet passée dans les bouchons approche ou dépasse **48 %**.

### ana_02 — Les minutes sèches perdues : un péage quasi forfaitaire
Distribution des minutes perdues (aller) : p10 = 6,9 · médiane = 17,7 · p90 = 22,2 · **max = 24,6** (Noyelles-sous-Lens). 18 communes plafonnent entre 23 et 24,6 minutes, toutes sur l'axe **Lens–Liévin–Béthune (A21)** : Angres, Vitry-en-Artois, Souchez, Sallaumines, Billy-Montigny, Liévin (30 000 hab), Fouquières-lès-Lens…
Le plafonnement autour de 24 minutes suggère que le modèle TomTom applique un retard borné sur le tronçon d'approche partagé de la métropole : au-delà d'une certaine distance, tout le monde subit la même file. → **L'indice relatif discrimine mieux que la minute absolue.**

### ana_03 — Contre-intuitif : ce n'est pas une question de distance
Corrélation indice de congestion / distance routière : **−0,37**. Plus on habite près de Lille, plus le multiplicateur de pointe est fort — on passe une part plus grande d'un trajet court dans la circulation de l'agglomération elle-même. À l'inverse, la corrélation minutes perdues / distance est positive mais faible (+0,36) et sature vite.

### ana_04 — MEL contre hors-MEL
| | indice médian | minutes perdues (méd.) | km (méd.) | heures perdues/an (méd.) |
|---|---|---|---|---|
| Communes MEL | 1,46 | 9,4 | 15,0 | 69 |
| Hors MEL | 1,50 | 18,5 | 46,9 | 136 |
Le multiplicateur est quasi identique ; c'est le volume de minutes qui explose à l'extérieur.

### ana_05 — La double peine : bouchons + aucune alternative
**68 communes, 210 000 habitants** cumulent des bouchons supérieurs à la médiane **et** l'absence de tout trajet sans voiture vers Lille (`sans_alternative = vrai`). Indice médian du groupe : 1,51 ; minutes perdues médianes : 20 ; **146 heures/an**.
Les plus peuplées : Bruay-la-Buissière (21 800 hab), Auchel, Merville, Mazingarbe, Barlin, Houdain, Grenay, Estaires, Hersin-Coupigny, Sains-en-Gohelle, La Gorgue, Lestrem, Laventie. Géographiquement : la **Gohelle à l'ouest de Lens** et la **couronne Béthune–Bruay**, plus la **Lys (Estaires, La Gorgue, Laventie, Merville)**.

### ana_06 — Les plus épargnées : la vallée de l'Escaut
Indice de congestion le plus bas : Escautpont (1,12), Quarouble (1,12), Nivelle, Flines-lès-Mortagne, Bruille-Saint-Amand, Hergnies, Vieux-Condé, Fresnes-sur-Escaut, Mortagne-du-Nord — toutes autour de **1,13-1,15**, avec 5 à 7 minutes perdues seulement. Ces communes sont pourtant à 45-60 minutes de Lille. Même Boulogne-sur-Mer et Hardinghen, très loin, roulent sur autoroute fluide.

### ana_07 — Lecture par corridor
| Corridor (échantillon nommé) | indice médian | minutes perdues (méd.) | part du trajet |
|---|---|---|---|
| **Weppes / Bas-Pays** (RN41, A25) — Bois-Grenier, Wavrin, Illies, Salomé, Marquillies, Fournes… | **1,92** | 20 min | 48 % |
| **Bassin minier A1 / A21** — Libercourt, Carvin, Courcelles-lès-Lens, Noyelles-Godault, Hénin-Beaumont… | **1,85** | 22 min | 46 % |
| **Vallée de l'Escaut** (A2, A23) — Vieux-Condé, Condé, Fresnes, Hergnies, Quarouble… | **1,13** | 6 min | 12 % |

### ana_08 — Le coût annuel
Heures perdues par an (aller-retour, 220 jours travaillés, retour supposé symétrique de l'aller) : p10 = 51 · médiane = 130 · p90 = 163 · **max = 180** (Noyelles-sous-Lens, 49 min/jour).
**128 communes dépassent 150 heures perdues par an**, soit **745 000 habitants**.

### ana_09 — Le calcul immobilier qui se retourne
Corrélation prix de la maison au m² / minutes perdues dans les bouchons : **−0,57**. Corrélation prix / distance routière : −0,61.
- Quartile des communes **les moins chères** (médiane 1 428 €/m²) : **20 minutes** perdues par trajet.
- Quartile des communes **les plus chères** (médiane 2 724 €/m²) : **10 minutes**.
L'indice de congestion, lui, est identique (1,46 des deux côtés) : les communes bon marché ne roulent pas « plus mal », elles sont simplement plus loin, donc paient le double de minutes. Le gain sur le prix d'achat se rembourse en temps de transport.
*Croisement : `data/output/cadre_urbain_communes_candidates.csv`, prix SeLoger/MeilleursAgents avril 2026.*

### ana_10 — Repère externe
Notre médiane (130 h/an) est supérieure au chiffre TomTom pour l'agglo (66 h/an, ctx_01) parce que nous mesurons le trajet réel commune → cœur de Lille, et non un trajet urbain normalisé de 10 km. Les ordres de grandeur sont cohérents : le mardi 8 h est bien le pic (ctx_02), et nos deux corridors noirs recoupent trois des quatre axes de l'Ecobonus (A1, A25, RN41 — ctx_03) et le point noir DREAL du contournement ouest (ctx_04).

### Limites (à intégrer à tout article — voir skill `verif-data`)
- **Donnée modélisée, pas mesurée.** TomTom fournit un temps de trajet fondé sur l'historique d'un mardi type à 8 h, pas une observation du 15 septembre 2026. Le « temps fluide » correspond aux vitesses légales sans autre véhicule.
- **Sens unique.** Seul le trajet domicile → Lille du matin est calculé. Le retour du soir est supposé symétrique pour l'estimation annuelle ; c'est une approximation (le soir sature aussi, souvent davantage en sortie d'agglo).
- **Plafond de retard.** 18 communes de l'axe A21 sont à égalité à ~23-24 min perdues : le modèle borne le retard sur le tronçon partagé. Utiliser l'indice de congestion pour classer, la minute absolue pour illustrer.
- **Point d'arrivée unique** : Lille-Flandres / Euralille (50.63658, 3.07103). Un emploi à Seclin, Roubaix ou Villeneuve-d'Ascq donnerait un autre résultat.
- Pas de mesure terrain commune par commune ; classement *relatif* robuste, valeurs à ±10-15 %.

---

## 3. Angle proposé

### Colonne vertébrale

**Affirmation centrale.** Pour rejoindre Lille en voiture le matin, ce ne sont pas les communes les plus éloignées qui souffrent le plus des bouchons, mais une couronne précise — Weppes, Bas-Pays, ex-bassin minier — où le trajet s'allonge de 80 à 100 % à l'heure de pointe, et où il n'existe le plus souvent aucune solution de rechange au volant.

**La tension.** On s'imagine que l'enfer des embouteillages se paie en kilomètres : Dunkerque, la côte, les confins. C'est faux. La vallée de l'Escaut, à 50 minutes de Lille, roule quasiment sans ralentir. Le vrai péage, c'est d'habiter à 30-45 minutes sur un axe qui se déverse dans l'entonnoir lillois sans porte de sortie ferroviaire.

**Ce que le lecteur doit comprendre autrement.** Le temps de trajet affiché par un GPS le dimanche est un mensonge. Un mardi à 8 h, il faut le multiplier par 1,5 en moyenne, par 2 sur les pires corridors. Et le raisonnement « je m'éloigne pour acheter moins cher » se retourne : le quart des communes les moins chères perd deux fois plus de minutes dans les bouchons que le quart le plus cher.

---

### Section 1 — Accroche
*Objectif : accroche. Sources : ana_01, ana_02.*

À Bois-Grenier, dans les Weppes, il faut compter dix-neuf minutes pour rejoindre Lille quand la route est libre. Un mardi à 8 heures, il en faut trente-huit. Le trajet a doublé.

Ce n'est pas un cas isolé. À Wavrin, même constat. À Libercourt, Évin-Malmaison, Noyelles-Godault, dans l'ancien bassin minier, le temps de route gonfle de 96 à 97 %. Sur ces trajets, près d'une minute sur deux se passe à l'arrêt ou au pas.

[SUGGESTION VISUELLE : carte choroplèthe des 411 communes, échelle de couleur sur l'indice de congestion (1,1 → 2,0), avec les autoroutes A1/A21/A22/A23/A25/RN41 en surimpression.]

---

### Section 2 — La géographie du pire
*Objectif : preuve. Sources : ana_01, ana_07, ana_03.*

En médiane, rejoindre Lille en voiture le matin prend 49 % de temps de plus qu'à vide. Mais la moyenne cache deux foyers noirs.

Le premier : les Weppes et le Bas-Pays, au sud-ouest, sur la RN41 et l'A25. Bois-Grenier, Wavrin, Illies, Salomé, Marquillies, Fournes-en-Weppes : indice de congestion médian de 1,92, aucune gare à proximité utile.

Le second : la diagonale de l'ancien bassin minier, entre Lens et Hénin-Beaumont, là où l'A21 et l'A1 se rejoignent pour foncer vers Lille. Libercourt, Carvin, Courcelles-lès-Lens, Noyelles-Godault : indice médian de 1,85.

Ces deux corridors recoupent presque exactement les axes que la Métropole européenne de Lille juge assez saturés pour payer les automobilistes qui les évitent — l'A1, l'A25 et la RN41 font partie du dispositif Ecobonus.

[SUGGESTION VISUELLE : deux zooms cartographiques côte à côte (Weppes / bassin minier) avec le nom des communes et leur indice.]

---

### Section 3 — Le paradoxe de la distance
*Objectif : bascule. Sources : ana_03, ana_06.*

On croit spontanément que les bouchons punissent les plus éloignés. Les données disent le contraire.

Plus une commune est proche de Lille, plus son trajet se dégrade en proportion à l'heure de pointe : la corrélation entre l'indice de congestion et la distance est négative. Logique — sur un trajet court, la part passée dans la circulation dense de l'agglomération pèse davantage.

La vallée de l'Escaut en est la démonstration inverse. Vieux-Condé, Condé-sur-l'Escaut, Fresnes-sur-Escaut, Hergnies : 45 à 60 minutes de Lille, mais un indice de 1,13, cinq à sept minutes perdues à peine. L'A23 et l'A2 les amènent aux portes de la métropole en roulant.

Habiter loin ne condamne pas aux bouchons. Habiter au mauvais endroit à mi-distance, si.

---

### Section 4 — La double peine
*Objectif : contexte + preuve. Sources : ana_05, ctx_03, ctx_04, ctx_05.*

Le pire n'est pas la durée, c'est l'absence de choix.

Soixante-huit communes, 210 000 habitants, cumulent des bouchons supérieurs à la médiane et aucune option pour rejoindre Lille autrement qu'en voiture : pas de gare bien desservie, pas de métro, trop loin pour le vélo. Pour eux, les vingt minutes perdues chaque matin ne sont pas négociables.

C'est la Gohelle à l'ouest de Lens — Angres, Souchez, Grenay, Aix-Noulette — et la couronne de Béthune et Bruay-la-Buissière, la plus peuplée de ce groupe avec près de 22 000 habitants. C'est aussi la Lys, autour d'Estaires et Merville.

Ces territoires sont ceux d'où partent, chaque matin, une part des 120 000 actifs qui entrent dans la métropole pour travailler. La moitié de ceux qui viennent de l'extérieur de la MEL habitent l'ancien bassin minier.

[SUGGESTION VISUELLE : carte des 68 communes « double peine », en aplat rouge, avec un encart chiffré (habitants, heures perdues/an médianes).]

---

### Section 5 — Le calcul qui se retourne
*Objectif : bascule. Sources : ana_09, ctx_06.*

On s'éloigne de Lille pour acheter moins cher. Les Weppes, la Pévèle, le bassin minier offrent la maison qu'on ne peut pas se payer à Lambersart ou La Madeleine.

Mais ce gain a une contrepartie mesurable. Dans le quart des communes les moins chères de notre panel — autour de 1 400 € le mètre carré —, un trajet vers Lille fait perdre vingt minutes dans les bouchons. Dans le quart le plus cher, deux fois moins.

Ces communes bon marché ne roulent pas « plus mal » : leur multiplicateur de congestion est identique. Elles sont simplement plus loin. Le prix payé en moins à l'achat se rembourse en minutes, tous les jours.

[SUGGESTION VISUELLE : nuage de points — prix maison €/m² en abscisse, minutes perdues dans les bouchons en ordonnée, une commune = un point, taille = population.]

---

### Section 6 — Combien ça coûte
*Objectif : preuve. Sources : ana_08, ana_02, ctx_01, ctx_02.*

Mises bout à bout, ces minutes font des journées entières.

À Noyelles-sous-Lens, la commune la plus touchée, les bouchons coûtent 49 minutes par jour, aller-retour — cent quatre-vingts heures par an, l'équivalent de plus de sept jours et sept nuits passés à l'arrêt sur le bitume.

Cent vingt-huit communes du panel dépassent cent cinquante heures perdues par an. Elles regroupent 745 000 habitants.

Pour mémoire, TomTom estime à soixante-six heures par an le temps perdu par un conducteur dans l'agglomération lilloise sur un trajet urbain type — un chiffre déjà en hausse de deux heures et demie en un an. Le trajet réel depuis la périphérie, lui, se compte en semaines.

[SUGGESTION VISUELLE : graphique en barres horizontales, top 15 des communes par heures perdues/an, couleur selon présence ou non d'une alternative sans voiture.]

---

### Section 7 — Ce que ça change pour « où vivre »
*Objectif : conclusion. Source : éditorial.*

Ce relevé n'est pas qu'un palmarès des points noirs. Il dit quelque chose du choix résidentiel lui-même.

Le temps domicile-travail qui compte n'est pas celui du GPS un dimanche, mais celui du mardi matin. À cette aune, deux communes à distance égale de Lille peuvent offrir des quotidiens radicalement différents selon l'axe qu'elles empruntent — et selon qu'il existe, ou non, un train pour doubler la voiture les jours où l'A1 est bloquée.

Dans le classement « Où vivre quand on travaille à Lille », c'est cette résilience-là — avoir une alternative — qui sépare les communes vraiment bien placées de celles qui ne tiennent qu'à une bretelle d'autoroute.

---

## Pistes de prolongement
- Croiser avec la desserte TER : combien des 68 communes « double peine » seraient sauvées par un rabattement bus vers une gare (réseaux Tadao, Transvilles) ?
- Trajet retour du soir (Lille → périphérie, 17 h-18 h) : le calculer pour confirmer ou corriger l'estimation annuelle.
- Comparer à un point d'arrivée secondaire (Villeneuve-d'Ascq, Seclin) pour les actifs qui ne travaillent pas dans l'hypercentre.
- Suivi Ecobonus : les communes des axes A1/A25/RN41 ont-elles vu leur trafic baisser depuis 2023 ? (demander le bilan détaillé à la MEL).
