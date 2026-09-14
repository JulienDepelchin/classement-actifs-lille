# Collecte autoroutes en pause

Clé TomTom Routing (`data/raw/tomtom_key.txt` / secret `TOMTOM_KEY`) en échec HTTP 403
depuis le 2026-09-11 ~18h. Mail envoyé au service presse TomTom le 2026-08-28 (usage
éditorial de Traffic Stats), sans réponse à ce jour -- lien de cause a effet avec ce 403
incertain (le mail portait sur un autre produit que la cle Routing qui a lache).

En attendant une reponse / une nouvelle cle : `poll_autoroutes_tomtom.py` s'arrete
immediatement des le debut de `one_pass()` tant que ce fichier existe, sans appeler
TomTom ni faire echouer le run (pas d'alerte GitHub en boucle).

Pour relancer la collecte : supprimer ce fichier.
