"""
Telecharge les donnees immobilier "officielles" pour remplacer l'estimation SeLoger/MeilleursAgents :

- PRIX de vente : DVF geolocalisees (DGFiP via Etalab), transactions REELLES.
  files.data.gouv.fr/geo-dvf/latest/csv/<annee>/departements/{59,62}.csv.gz  (millesimes 2023-2025)
- LOYERS d'annonce : "Carte des loyers" 2025 (CGDD/ANIL/ministere), indicateur predit par commune.

Sorties : data/raw/dvf/{59,62}_{annee}.csv.gz + data/raw/loyers/pred-{mai,app}-2025.csv
"""
from __future__ import annotations
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
DVF_DIR = ROOT / "data" / "raw" / "dvf"
LOY_DIR = ROOT / "data" / "raw" / "loyers"

ANNEES = ["2023", "2024", "2025"]
DVF_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv/{an}/departements/{dep}.csv.gz"
LOYERS = {
    "pred-mai-2025.csv": "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145039/pred-mai-mef-dhup.csv",
    "pred-app-2025.csv": "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145010/pred-app-mef-dhup.csv",
}


def get(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "vdn-classement-lille/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        f.write(r.read())
    print(f"  {dest.name:22s} {dest.stat().st_size/1e6:7.1f} Mo")


def main() -> None:
    for an in ANNEES:
        for dep in ("59", "62"):
            get(DVF_URL.format(an=an, dep=dep), DVF_DIR / f"{dep}_{an}.csv.gz")
    for name, url in LOYERS.items():
        get(url, LOY_DIR / name)
    print("OK")


if __name__ == "__main__":
    main()
