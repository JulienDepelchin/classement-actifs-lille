"""
Soumet un lot (batch) de requete Route Analysis a l'API TomTom Traffic Stats, attend le
resultat (job asynchrone) et telecharge les exports.

Usage : python scripts/submit_traffic_stats_job.py data/rt/traffic_stats_requests/batch1.json

Cle : env TRAFFICSTATS_KEY, sinon data/raw/traffic_stats_key.txt (jamais commite, cf .gitignore).

Rappel autorisation TomTom (Vincent Martinier, 2026-09-14) : usage editorial ok, source
mentionnee obligatoire, pas de calcul derive (extrapolation) a partir de ces donnees --
on affiche les chiffres Traffic Stats tels quels, a cote de nos autres sources.
"""
from __future__ import annotations
import os
import sys
import json
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.tomtom.com/traffic/trafficstats"
OUTDIR = ROOT / "data" / "raw" / "traffic_stats" / "results"

KEY = os.environ.get("TRAFFICSTATS_KEY", "").strip()
if not KEY:
    kf = ROOT / "data" / "raw" / "traffic_stats_key.txt"
    KEY = kf.read_text().strip() if kf.exists() else ""


def call(url: str, data: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def submit(payload_path: Path) -> str:
    payload = payload_path.read_bytes()
    resp = call(f"{BASE}/routeanalysis/1?key={KEY}", data=payload)
    print(f"soumis : {resp}")
    if resp.get("responseStatus") != "OK":
        sys.exit(f"echec de soumission : {resp}")
    return resp["jobId"]


def attendre(job_id: str, intervalle_s: int = 30, max_min: int = 30) -> dict:
    fin = time.monotonic() + max_min * 60
    while time.monotonic() < fin:
        resp = call(f"{BASE}/status/1/{job_id}?key={KEY}")
        etat = resp.get("jobState")
        print(f"  {etat}")
        if etat == "DONE":
            return resp
        if etat in ("ERROR", "FAILED"):
            sys.exit(f"job en echec : {resp}")
        time.sleep(intervalle_s)
    sys.exit(f"timeout apres {max_min} min, job toujours en cours (jobId={job_id})")


def telecharger(urls: list[str], nom_lot: str) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for u in urls:
        ext = u.split("?")[0].rsplit(".", 1)[-1]
        dest = OUTDIR / f"{nom_lot}.{ext}"
        urllib.request.urlretrieve(u, dest)
        print(f"  -> {dest}")


def main() -> None:
    if not KEY:
        sys.exit("TRAFFICSTATS_KEY manquant (env ou data/raw/traffic_stats_key.txt)")
    if len(sys.argv) < 2:
        sys.exit("usage : python submit_traffic_stats_job.py <fichier_requete.json>")
    payload_path = Path(sys.argv[1])
    nom_lot = payload_path.stem

    job_id = submit(payload_path)
    print(f"jobId={job_id} -- attente du resultat (peut prendre plusieurs minutes)...")
    resp = attendre(job_id)
    telecharger(resp["urls"], nom_lot)
    print(f"\n{nom_lot} termine.")


if __name__ == "__main__":
    main()
