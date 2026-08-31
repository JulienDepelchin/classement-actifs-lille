"""
Poller des perturbations du reseau ilevia (metro, tram, bus).

Source : OGC API Features de la MEL (Licence Ouverte, sans cle), rafraichi ~chaque minute,
NON historise -> on garde un instantane a chaque poll pour reconstituer, plus tard, la
frequence et la duree des incidents -- en priorite ceux du METRO (defaut de rame, ligne
interrompue entre deux stations...).

  cible : ME1 / ME2 = metro L1 / L2 | 71 = tramway | reste = bus / Liane / Corolle
  type_perturbation : "Perturbation" = incident en cours | "Information" = travaux, event...

Sortie : data/rt/ilevia_perturbations/<date>/<poll_utc>.csv.gz  (1 fichier par poll, immuable)
  poll_utc, id_perturbation, id_message, type, cible, mode, heure_fin_prevue,
  date_modification, message
"""
from __future__ import annotations
import csv
import gzip
import json
import sys
import datetime as dt
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "data" / "rt" / "ilevia_perturbations"
URL = ("https://data.lillemetropole.fr/geoserver/ogc/features/v1/collections/"
       "dsp_ilevia:perturbations/items?f=application/json&limit=1000")
COLS = ["poll_utc", "id_perturbation", "id_message", "type", "cible", "mode",
        "heure_fin_prevue", "date_modification", "message"]


def mode_of(cible: str) -> str:
    c = (cible or "").upper()
    if c in ("ME1", "ME2"):
        return "metro"
    if c in ("71", "R", "T", "TR", "TT"):
        return "tram"
    return "bus"


def main() -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": "vdn-classement-lille/1.0"})
    fc = json.loads(urllib.request.urlopen(req, timeout=90).read())
    poll_utc = dt.datetime.now(dt.timezone.utc)
    stamp = poll_utc.strftime("%Y%m%dT%H%M%SZ")
    day = poll_utc.strftime("%Y%m%d")

    rows = []
    for f in fc.get("features", []):
        p = f.get("properties", {})
        cible = (p.get("cible") or "").replace("ILEVIA:LineRef::", "").replace(":LOC", "")
        rows.append({
            "poll_utc": poll_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "id_perturbation": p.get("identifiant_perturbation", ""),
            "id_message": p.get("identifiant_message", ""),
            "type": p.get("type_perturbation", ""),
            "cible": cible,
            "mode": mode_of(cible),
            "heure_fin_prevue": p.get("heure_fin_prevue", ""),
            "date_modification": p.get("date_modification", ""),
            "message": " ".join((p.get("message") or "").split()),
        })

    d = OUTDIR / day
    d.mkdir(parents=True, exist_ok=True)
    with gzip.open(d / f"{stamp}.csv.gz", "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

    par_mode = {}
    for r in rows:
        par_mode[r["mode"]] = par_mode.get(r["mode"], 0) + 1
    incidents = [r for r in rows if r["type"] == "Perturbation"]
    print(f"{stamp} | {len(rows)} perturbations {par_mode} | "
          f"dont {len(incidents)} 'en cours'"
          + (" -> " + "; ".join(f"[{i['cible']}] {i['message'][:70]}" for i in incidents)
             if incidents else ""))


if __name__ == "__main__":
    main()
