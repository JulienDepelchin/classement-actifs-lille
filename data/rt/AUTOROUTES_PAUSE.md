# Collecte autoroutes en pause

**Cause identifiée (2026-09-14, export `analytics.csv` du dashboard TomTom) : quota
gratuit epuise, rien a voir avec le mail du 28/08 sur Traffic Stats.** La cle Routing
("My First API key", creee le 27/08) a un forfait GRATUIT de 20 000 transactions --
pas 2500/jour comme suppose au depart. A ~1653 appels/j (rythme du poller d'origine),
le forfait a tenu jusqu'au 11/09 (~996 erreurs 403 ce jour-la), puis 100% d'erreurs
403 les 12 et 13/09. Grille tarifaire au-dela : Tier 1 (20K-1M) 1,00 EUR/1000, Tier 2
0,80, Tier 3 0,65 -- pas de budget pour ca (contexte presse en crise), on reste gratuit.

Pas de date de reset trouvee sur le dashboard ; hypothese la plus probable = cycle
mensuel (forfait tenu ~11-15 jours a partir du 27/08 comme du 01/09), donc reset
probable au plus tard le 2026-10-01.

**Le script est recalibre** (2026-09-14) pour tenir sous 20 000/mois avec marge :
cadence pointe passee de ~10 min a 30 min (minutes 00/30 seulement), cadence epaule
de 30 min a 60 min (minute 00 seulement). Budget vise ~630 appels/j (~18 870/mois).

En attendant que le forfait reparte : `poll_autoroutes_tomtom.py` s'arrete
immediatement des le debut de `one_pass()` tant que ce fichier existe, sans appeler
TomTom ni faire echouer le run (pas d'alerte GitHub en boucle).

Pour relancer la collecte (des que le dashboard montre un quota reconstitue) :
supprimer ce fichier.
