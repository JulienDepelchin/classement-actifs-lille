# Collecte GTFS-RT — ponctualité réelle des TER vers Lille

Pallie l'absence de données SNCF de régularité à la maille ligne/gare.

## Fonctionnement

- **`scripts/poll_ter_rt.py`** interroge le flux GTFS-RT SNCF
  (`https://proxy.transport.data.gouv.fr/resource/sncf-gtfs-rt-trip-updates`, sans clé) et écrit,
  pour chaque TER desservant Lille, le retard / l'annulation constatés aux **75 gares suivies**
  (`gares_suivies.csv` = 2 gares de Lille + 73 gares utiles des communes candidates).
- **`.github/workflows/poll-ter-rt.yml`** lance ce poll toutes les 10 min, **toute la journée de
  service (≈ 05 h–23 h Paris), 7 j/7** (03–21 h UTC), et commit `data/rt/updates/`. Chaque run
  boucle ~8 min (poll toutes les 75 s). Journée complète = permet aussi l'angle « à quelle heure /
  quel jour le TER déraille le plus », la ponctualité hors pointe et le week-end.
- Chaque ligne de `updates/<date>.csv` = l'état connu d'un passage (train × gare) à l'instant du
  poll. L'agrégation prendra le **dernier état connu** par passage.

## Mise en route (à faire une fois)

1. `python scripts/gares_suivies_rt.py` — (re)génère la liste des gares
2. repo poussé sur GitHub, onglet **Actions** activé
3. le workflow tourne seul ; `workflow_dispatch` pour un test manuel

## Exploitation (après ~3-4 semaines)

`scripts/build_regularite_reelle.py` (à écrire) : `updates/*.csv` → ponctualité par gare et par
ligne — `% arrivées à Lille < 5 min`, `% annulations`, retard médian / p90, nb d'observations.
Restreindre aux trains de pointe en semaine ; signaler les jours de grève ; recouper avec le
mensuel régional (`data/raw/sncf/regularite_ter_hdf.csv`).
