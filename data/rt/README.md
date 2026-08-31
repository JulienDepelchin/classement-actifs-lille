# Collecte GTFS-RT — ponctualité réelle des TER du Nord / Pas-de-Calais

Pallie l'absence de données SNCF de régularité à la maille ligne/gare. Sert deux livrables :
la **fiabilité ligne par ligne** (article « les lignes TER les plus fiables du NPDC ») et,
par filtre, la **régularité vers Lille** pour le classement « à moins d'une heure de Lille ».

## Fonctionnement

- **`scripts/poll_ter_rt.py`** interroge le flux GTFS-RT SNCF
  (`https://proxy.transport.data.gouv.fr/resource/sncf-gtfs-rt-trip-updates`, sans clé) et écrit,
  pour **tout TER touchant au moins une gare du 59/62**, le retard / l'annulation constatés à
  **toutes les gares du 59/62** (`gares_npdc.csv` = 190 gares, dont Lille-Flandres / Lille-Europe
  tagguées `role=lille`). Généré par `scripts/gares_npdc_rt.py`.
- Sortie : **un fichier gzip par poll**, immuable —
  `data/rt/ter_npdc/<date_service>/<poll_utc>.csv.gz`
  (colonnes : `poll_utc, date_service, trip_id, start_time, uic, role, stop_seq, arr_delay_s,
  dep_delay_s, trip_annule, stop_saute`). Chaque ligne = l'état connu d'un passage (train × gare)
  à l'instant du poll ; l'agrégation prendra le **dernier état connu** par passage.
- L'ancienne collecte restreinte à Lille (`data/rt/updates/*.csv`, 75 gares, 28-31 août 2026)
  reste dans le dépôt comme historique — elle n'est plus alimentée.
- **`.github/workflows/poll-ter-rt.yml`** fait le poll (loop ~8 min, une requête toutes les 75 s)
  puis commit `data/rt/ter_npdc/`. Il n'a **que le trigger `workflow_dispatch`** — le planificateur
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

1. `python scripts/gares_npdc_rt.py` — (re)génère `gares_npdc.csv` (190 gares 59/62)
2. repo poussé sur GitHub, onglet **Actions** activé
3. le workflow tourne seul ; `workflow_dispatch` pour un test manuel

## Autoroutes — capteurs DIR Nord (open data, source principale)

- **`scripts/poll_dir_nord.py`** lit le flux national « Circulation temps réel – réseau non
  concédé » (transport.data.gouv.fr, DATEX II, **Licence Ouverte**) et extrait **vitesse moyenne +
  débit des 168 stations DIR Nord** (toutes autour de Lille : A25 ×46, A22 ×26+, A1 ×23, A27, A23,
  N41, N356, N227…). Aucune clé, aucun quota.
- Référentiel : `scripts/dir_nord_referentiel.py` → `data/rt/dir_nord_stations.csv` (code_pme →
  route, décodé du code : `A0025…` = A25, `A22TC…` = contournement, etc. — le référentiel national
  ne donne ni coords ni PR pour les stations DIRN, on reste à la maille **axe**).
- **`.github/workflows/poll-dir-nord.yml`** (`workflow_dispatch`), déclenché par le Worker Cloudflare.
- Sortie `data/rt/dir_nord/<date>.csv` : `poll_utc, feed_time, code_pme, route, vitesse_kmh, debit_vh`.
- **Publiable sans réserve** (données de l'État). Exploitation : par axe, vitesse par tranche
  horaire / jour de semaine, % de temps en congestion (< 50 km/h), point noir persistant, débit.

## Départementales — poller TomTom (complément, Weppes / Pévèle / Mélantois)

- **`scripts/poll_autoroutes_tomtom.py`** interroge TomTom en **trafic live** :
  - **26 points d'entrée** (`points_routes.csv`) → Lille : 12 corridors autoroutiers + 14 points
    sur les axes **départementaux** (Weppes, Pévèle, Mélantois, rocade NO / M652, Ferrain, Lys).
  - **9 de ces points** aussi en **retour** (Lille → point) le soir — l'angle « sortir de Lille ».
  - **5 sondes de tronçon** (`troncons_routes.csv`) aux points noirs : échangeur d'Englos (A25),
    rocade Lomme (M652), approche A1 Fretin-Ronchin, Croix-Wasquehal (A22), Haubourdin-Loos (RN41).
  - **Échantillonnage adapté à l'heure** (quota gratuit ~1 700 appels/j) : tous les points +
    tronçons à chaque run pendant les pointes (04:45-07:15 et 14:15-17:15 UTC), sinon aux minutes
    00 / 30 seulement, rien la nuit.
  - Sortie `data/rt/autoroutes/<date>.csv` : `poll_utc, categorie (point/troncon), libelle,
    zone_axe, type, sens (vers_lille/depuis_lille), temps_live_min, temps_libre_min, retard_min,
    distance_km`.
- **`.github/workflows/poll-autoroutes.yml`** (`workflow_dispatch` seul), déclenché par le **même
  Worker Cloudflare** que le TER.
- Clé TomTom = **secret GitHub Actions** `TOMTOM_KEY` (Settings → Secrets and variables → Actions).

### Mise en route (une fois)

1. **GitHub → Settings → Secrets and variables → Actions → New repository secret** :
   `TOMTOM_KEY` = la clé (contenu de `data/raw/tomtom_key.txt`)
2. **Cloudflare Worker `poll-ter`** → Edit code → ajouter, à la fin du handler `scheduled`,
   juste avant la fin de la fonction :
   ```javascript
   const r2 = await fetch(
     "https://api.github.com/repos/JulienDepelchin/classement-actifs-lille/actions/workflows/poll-autoroutes.yml/dispatches",
     { method: "POST", headers: {
         "Authorization": "Bearer " + env.GH_TOKEN,
         "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28",
         "User-Agent": "cf-worker-ter"
       }, body: JSON.stringify({ ref: "main" }) }
   );
   console.log("autoroutes dispatch:", r2.status);
   ```
   → **Deploy**. Le Worker déclenche alors les deux collectes à chaque tir du cron.

### Exploitation

`scripts/build_regularite_autoroutes.py` (à écrire) : `autoroutes/*.csv` → par point / tronçon /
sens : temps médian, **temps tampon** (p95 − médiane), pire jour, % de « jours galère »
(> 1,5× la médiane), courbe horaire, écart matin/soir.

## Exploitation TER (après ~3-4 semaines)

`scripts/build_regularite_reelle.py` (à écrire) : `ter_npdc/*/*.csv.gz` → dernier état connu par
passage (trip × gare), puis :
- **par ligne** (reconstruire l'appartenance ligne + l'ordre des arrêts depuis le GTFS statique,
  `stop_sequence` étant peu fiable dans le flux) : `% arrivées < 5 min`, `% annulations`, retard
  médian / p90 → classement des lignes NPDC.
- **par gare** : même chose, pour la carte.
- **filtre Lille** (`role=lille` + gares utiles) : le critère `ter_ponctualite` du classement.
Restreindre aux trains de pointe en semaine ; signaler les jours de grève ; recouper avec le
mensuel régional (`data/raw/sncf/regularite_ter_hdf.csv`).
