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

## Fiabilité des autoroutes vers Lille (parallèle au TER)

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

`scripts/build_regularite_reelle.py` (à écrire) : `updates/*.csv` → ponctualité par gare et par
ligne — `% arrivées à Lille < 5 min`, `% annulations`, retard médian / p90, nb d'observations.
Restreindre aux trains de pointe en semaine ; signaler les jours de grève ; recouper avec le
mensuel régional (`data/raw/sncf/regularite_ter_hdf.csv`).
