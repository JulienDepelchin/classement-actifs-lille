# Collecte GTFS-RT — ponctualité réelle des TER vers Lille

Pallie l'absence de données SNCF de régularité à la maille ligne/gare.

## Fonctionnement

- **`scripts/poll_ter_rt.py`** interroge le flux GTFS-RT SNCF
  (`https://proxy.transport.data.gouv.fr/resource/sncf-gtfs-rt-trip-updates`, sans clé) et écrit,
  pour chaque TER desservant Lille, le retard / l'annulation constatés aux **75 gares suivies**
  (`gares_suivies.csv` = 2 gares de Lille + 73 gares utiles des communes candidates).
- **`.github/workflows/poll-ter-rt.yml`** fait le poll (loop ~8 min, une requête toutes les 75 s)
  puis commit `data/rt/updates/`. Il n'a **que le trigger `workflow_dispatch`** — le planificateur
  natif de GitHub est trop peu fiable (premier run retardé de plusieurs heures, runs silencieusement
  sautés). Le déclenchement vient d'un **cron externe** (cron-job.org), toutes les 10 min.
- Collecte visée : toute la journée de service, 7 j/7 → permet aussi l'angle « à quelle heure / quel
  jour le TER déraille », la ponctualité hors pointe, le week-end.

## Cron externe (cron-job.org) — à configurer une fois

1. **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token**
   - Repository access : *Only select repositories* → `classement-actifs-lille`
   - Permissions → Repository → **Actions : Read and write**
   - Expiration : 90 jours
   - copier le token `github_pat_…`
2. **cron-job.org → Create cronjob**
   - Title : `poll-ter-rt`
   - URL : `https://api.github.com/repos/JulienDepelchin/classement-actifs-lille/actions/workflows/poll-ter-rt.yml/dispatches`
   - Schedule : *Every 10 minutes* (ou une plage horaire 05 h–23 h)
   - Advanced → Request method : **POST**
   - Advanced → Headers :
     - `Authorization: Bearer github_pat_…`
     - `Accept: application/vnd.github+json`
     - `X-GitHub-Api-Version: 2022-11-28`
   - Advanced → Request body : `{"ref":"main"}`
   - réponse attendue : **HTTP 204** (No Content) = accepté
3. Vérifier : onglet Actions du dépôt → des runs `poll-ter-rt` toutes les 10 min, commits `rt: …`.
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
