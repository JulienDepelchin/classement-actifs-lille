# Encadré méthodo — « Où vivre quand on travaille à Lille »

*Brouillon à retravailler façon VDN. Chiffres à revérifier via `verif-data` avant publication.*

---

## Ce que mesure ce classement

Il compare **227 communes** du Nord et du Pas-de-Calais sur un critère précis : **leur adéquation au quotidien d'un actif qui travaille dans la métropole lilloise**. Ce n'est pas un palmarès des « plus belles communes où vivre » dans l'absolu — c'est un outil pour qui cherche où s'installer en gardant son emploi à Lille.

Le périmètre part des communes de plus de 1 000 habitants du 59 et du 62 ayant déjà un lien domicile-travail marqué avec la Métropole européenne de Lille (au moins 100 navetteurs ou 5 % des actifs, source Insee). On leur applique ensuite un **filtre de distance-temps** : seules restent celles à **moins d'une heure porte-à-porte du centre de Lille**, en retenant le meilleur du TER (horaires réels, rabattement voiture jusqu'à la gare inclus) ou de la voiture aux heures de pointe. 197 communes passent sous les 60 minutes ; 30 sont entre 60 et 63 minutes et figurent au classement avec la mention **« à la limite »** ; 184 sont écartées au-delà (les couronnes de Lens, Béthune, Douai lointain, Valenciennes et Arras). Au-delà d'une heure, on considère qu'on ne « vit plus à côté de Lille ».

## Comment il est construit

**40 indicateurs**, regroupés en **10 thèmes** : transport vers Lille, santé, éducation et petite enfance, cadre urbain et logement, environnement et risques, sécurité, commerces et services, sport et nature, dynamique résidentielle, coût du logement.

Chaque indicateur est converti en une **note sur 20** à partir des valeurs minimale et maximale observées. Quand quelques communes ont des valeurs très au-dessus des autres (nombre de restaurants, mètres carrés d'espaces verts…), une transformation logarithmique limite leur influence avant la mise à l'échelle.

La note de chaque thème est la moyenne pondérée de ses indicateurs. Elle est ajustée à la marge par des **bonus et malus** (par exemple : malus si aucun trajet vers Lille n'est possible sans voiture, bonus si un collège est présent dans la commune).

La **note globale** est la moyenne des dix notes thématiques, pondérée par une grille par défaut : le transport pèse le plus (l'enjeu central du sujet), puis la santé, l'école, le cadre de vie et l'environnement, le reste ensuite, le coût du logement en dernier. Elle n'est pas re-étalée : une commune obtient rarement plus de 13 ou moins de 8 sur 20, parce qu'aucune n'est bonne — ni mauvaise — sur tous les thèmes à la fois. **Cette pondération n'est pas une vérité.** Elle reflète les priorités que nous prêtons à quelqu'un qui déménage pour travailler à Lille. Dans la version interactive, le lecteur règle lui-même l'importance de chaque thème et obtient son propre classement.

## Un rang, une fourchette, une tranche

Chaque commune a un **rang** (de 1 à 227) et une **tranche**. Les tranches sont fixées par des **seuils de note** — « très favorable » à partir de 11,5 sur 20, « favorable » à partir de 10,5, « moyen » à partir de 9,7, « peu favorable » à partir de 9, « peu adapté » en dessous — et non par une découpe en parts égales : elles sont de tailles inégales (27 communes en tête, 64 dans la tranche « moyen », la plus fournie). La dernière s'appelle **« peu adapté »**, pas « défavorable » : toutes ces communes sont à moins d'une heure de Lille, aucune n'est un mauvais endroit — elles sont seulement peu taillées pour ce projet précis (souvent : pas de gare, population vieillissante, ou marché immobilier tendu).

Mais le rang ne se lit pas de la même façon partout. Nous avons recalculé le classement **1 000 fois** en faisant varier les pondérations : dans le **haut du tableau, l'ordre tient** (les 15 premières restent groupées, une commune « très favorable » le reste dans près de 9 cas sur 10) ; dans le **milieu, deux communes séparées de quarante ou soixante places sont en pratique à égalité**. Chaque commune affiche donc sa **fourchette** de rang (« 3ᵉ, entre la 1ʳᵉ et la 6ᵉ place ») et une position **solide** ou **à nuancer**.

En clair : le podium et le bas de tableau sont des affirmations solides ; le classement précis du peloton, non.

## Ce que le classement ne dit pas

- Il suppose un **trajet quotidien** vers Lille : ni télétravail majoritaire, ni navette d'entreprise, ni covoiturage.
- Le point d'arrivée de référence est **le centre de Lille** (gare de Lille-Flandres). Un emploi à Villeneuve-d'Ascq, Seclin ou Roubaix change la donne.
- Il raisonne pour un **ménage qui achète une maison**. Un célibataire locataire ou une famille nombreuse ont d'autres contraintes.
- Un **village agréable mais sans gare** figure dans la moyenne basse : non parce qu'il est désagréable, mais parce qu'y vivre en travaillant à Lille impose la voiture pour presque tous les déplacements. Le classement mesure une adéquation, pas un charme.
- La **barre d'une heure est un choix, pas une frontière naturelle**. Une commune à 61 minutes est écartée du calcul principal quand sa voisine à 59 minutes y figure : à ce niveau de précision, l'estimation de temps de trajet vaut à quelques minutes près. C'est pourquoi les communes de 60 à 63 minutes restent affichées, signalées « à la limite ».

## Ce que valent les données

- **Sécurité** : les statistiques communales de la délinquance (ministère de l'Intérieur) sont largement estimées. Pour la commune médiane, **la moitié des faits comptabilisés sont des estimations lissées** (le secret statistique interdit de publier les petits nombres), et **59 communes n'ont aucune donnée directe**. À lire comme une tendance, pas un chiffre exact. C'est pourquoi ce thème ne pèse que deux étoiles sur cinq par défaut, sur deux indicateurs seulement (cambriolages, dégradations).
- **Air** : faute de modèle de pollution disponible commune par commune en accès libre, la concentration de dioxyde d'azote retenue est celle mesurée à la **station de surveillance de fond la plus proche** (millésimes 2023 à 2025, années COVID écartées) — parfois à plus de dix kilomètres. C'est un indicateur de gradient (cœur urbain contre campagne : de 6 à 18 µg/m³), pas une mesure du niveau réel dans chaque commune.
- **Train** : le classement s'appuie sur l'offre **théorique** — les horaires. La régularité réelle du réseau TER Hauts-de-France (environ 89 % des trains à l'heure et 2,5 % d'annulations sur les douze derniers mois) n'est pas ventilée commune par commune dans les données publiques. Une mesure de la ponctualité ligne par ligne est en cours de collecte pour une prochaine mise à jour.
- **Millésimes** : les données ne datent pas toutes de la même année (revenus 2021, logement 2023, prix des ventes 2023-2025, population 2016-2022, carte des argiles 2017…). Chacune est la plus récente disponible à l'échelle communale.

## Sources principales

Insee (recensement, flux domicile-travail, populations légales, revenus FiLoSoFi, structure de la population) · SNCF / transport.data.gouv.fr (horaires GTFS TER Hauts-de-France, GTFS Ilévia) · TomTom (temps de trajet routier avec trafic) · Insee, base permanente des équipements et distancier Metric-OSRM (temps d'accès aux services) · DREES-Irdes (accessibilité aux professionnels de santé, APL) · CNAF (couverture petite enfance) · ministère de l'Intérieur – SSMSI (délinquance) · INJEP (clubs sportifs) · CEREMA (artificialisation, imperméabilisation) · Atmo Hauts-de-France (qualité de l'air) · DREAL Hauts-de-France / BRGM (aléa retrait-gonflement des argiles) · Géorisques (aléa minier, inondations) · ADEME (diagnostics de performance énergétique) · DVF / DGFiP (prix des ventes immobilières, taxe foncière) · CGDD / ANIL (carte des loyers) · Écolab – Tableau de bord des mobilités durables (aménagements cyclables, parts modales).
