# Encadré méthodo — « Où vivre quand on travaille à Lille »

*Brouillon à retravailler façon VDN. Chiffres à revérifier via `verif-data` avant publication.*

---

## Ce que mesure ce classement

Il compare **411 communes** du Nord et du Pas-de-Calais sur un critère précis : **leur adéquation au quotidien d'un actif qui travaille dans la métropole lilloise**. Ce n'est pas un palmarès des « plus belles communes où vivre » dans l'absolu — c'est un outil pour qui cherche où s'installer en gardant son emploi à Lille.

Le périmètre : les communes de plus de 1 000 habitants du 59 et du 62 qui ont déjà un lien domicile-travail marqué avec la Métropole européenne de Lille (au moins 100 navetteurs ou 5 % des actifs, source Insee).

## Comment il est construit

**40 indicateurs**, regroupés en **10 thèmes** : transport vers Lille, santé, éducation et petite enfance, cadre urbain et logement, environnement et risques, sécurité, commerces et services, sport et nature, dynamique résidentielle, coût du logement.

Chaque indicateur est converti en une **note sur 20** à partir des valeurs minimale et maximale observées. Quand quelques communes ont des valeurs très au-dessus des autres (nombre de restaurants, mètres carrés d'espaces verts…), une transformation logarithmique limite leur influence avant la mise à l'échelle.

La note de chaque thème est la moyenne pondérée de ses indicateurs. Elle est ajustée à la marge par des **bonus et malus** (par exemple : malus si aucun trajet vers Lille n'est possible sans voiture, bonus si un collège est présent dans la commune).

La **note globale** combine les dix thèmes selon une pondération par défaut : le transport pèse le plus (l'enjeu central du sujet), puis la santé, l'école, le cadre de vie. **Cette pondération n'est pas une vérité.** Elle reflète les priorités que nous prêtons à quelqu'un qui déménage pour travailler à Lille. Dans la version interactive, le lecteur règle lui-même l'importance de chaque thème et obtient son propre classement.

## Un rang, une fourchette, une tranche

Chaque commune a un **rang** (de 1 à 411) et une **tranche** (de « très favorable » à « défavorable »). Les tranches sont fixées par des **seuils de note** — « très favorable » à partir de 14 sur 20, « favorable » à partir de 12, etc. — et non par une découpe en parts égales : elles sont donc de tailles inégales (59 communes en tête, 101 dans la tranche « moyen », qui est de loin la plus fournie — la plupart des communes sont, précisément, moyennes).

Mais le rang ne se lit pas de la même façon partout. Nous avons recalculé le classement **1 000 fois** en faisant varier les pondérations : dans le **haut du tableau, l'ordre tient** (le top 15 reste le top 15, une commune « très favorable » le reste dans 9 cas sur 10) ; dans le **milieu, deux communes séparées de trente ou quarante places sont en pratique à égalité**. Chaque commune affiche donc sa **fourchette** de rang (« 3ᵉ, entre la 1ʳᵉ et la 8ᵉ place ») et une position **solide** ou **à nuancer**.

En clair : le podium et le bas de tableau sont des affirmations solides ; le classement précis du peloton, non.

## Ce que le classement ne dit pas

- Il suppose un **trajet quotidien** vers Lille : ni télétravail majoritaire, ni navette d'entreprise, ni covoiturage.
- Le point d'arrivée de référence est **le centre de Lille** (gare de Lille-Flandres). Un emploi à Villeneuve-d'Ascq, Seclin ou Roubaix change la donne.
- Il raisonne pour un **ménage qui achète une maison**. Un célibataire locataire ou une famille nombreuse ont d'autres contraintes.
- Un **village agréable mais sans gare** figure dans la moyenne basse : non parce qu'il est désagréable, mais parce qu'y vivre en travaillant à Lille impose la voiture pour presque tous les déplacements. Le classement mesure une adéquation, pas un charme.

## Ce que valent les données

- **Sécurité** : les statistiques communales de la délinquance (ministère de l'Intérieur) sont largement estimées. Pour la commune médiane, **la moitié des faits comptabilisés sont des estimations lissées** (le secret statistique interdit de publier les petits nombres), et **59 communes n'ont aucune donnée directe**. À lire comme une tendance, pas un chiffre exact. C'est pourquoi ce thème ne pèse que deux étoiles sur cinq par défaut, sur deux indicateurs seulement (cambriolages, dégradations).
- **Air** : faute de modèle de pollution disponible commune par commune en accès libre, la concentration de dioxyde d'azote retenue est celle mesurée à la **station de surveillance de fond la plus proche** (millésimes 2023 à 2025, années COVID écartées) — parfois à plus de dix kilomètres. C'est un indicateur de gradient (cœur urbain contre campagne : de 6 à 18 µg/m³), pas une mesure du niveau réel dans chaque commune.
- **Train** : le classement s'appuie sur l'offre **théorique** — les horaires. La régularité réelle du réseau TER Hauts-de-France (environ 89 % des trains à l'heure et 2,5 % d'annulations sur les douze derniers mois) n'est pas ventilée commune par commune dans les données publiques. Une mesure de la ponctualité ligne par ligne est en cours de collecte pour une prochaine mise à jour.
- **Millésimes** : les données ne datent pas toutes de la même année (revenus 2021, logement 2023, prix des ventes 2023-2025, population 2016-2022, carte des argiles 2017…). Chacune est la plus récente disponible à l'échelle communale.

## Sources principales

Insee (recensement, flux domicile-travail, populations légales, revenus FiLoSoFi, structure de la population) · SNCF / transport.data.gouv.fr (horaires GTFS TER Hauts-de-France, GTFS Ilévia) · TomTom (temps de trajet routier avec trafic) · Insee, base permanente des équipements et distancier Metric-OSRM (temps d'accès aux services) · DREES-Irdes (accessibilité aux professionnels de santé, APL) · CNAF (couverture petite enfance) · ministère de l'Intérieur – SSMSI (délinquance) · INJEP (clubs sportifs) · CEREMA (artificialisation, imperméabilisation) · Atmo Hauts-de-France (qualité de l'air) · DREAL Hauts-de-France / BRGM (aléa retrait-gonflement des argiles) · Géorisques (aléa minier, inondations) · ADEME (diagnostics de performance énergétique) · DVF / DGFiP (prix des ventes immobilières, taxe foncière) · CGDD / ANIL (carte des loyers) · Écolab – Tableau de bord des mobilités durables (aménagements cyclables, parts modales).
