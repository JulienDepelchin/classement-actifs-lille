"""Telechargement des fichiers Insee necessaires a la construction du perimetre communal.

Usage : python scripts/download_insee.py
"""
from __future__ import annotations
import sys
import urllib.request
import zipfile
from pathlib import Path

INSEE = Path(__file__).resolve().parents[1] / "data" / "raw" / "insee"

FILES = {
    # flux domicile - lieu de travail, millesime 2021, geo 2024 (CSV = tous les flux)
    "flux_mobilite_2021.zip":
        "https://www.insee.fr/fr/statistiques/fichier/8201899/base-flux-mobilite-domicile-lieu-travail-2021-csv.zip",
    # table d'appartenance geographique des communes, geo 01/01/2026
    "table_appartenance_2026.zip":
        "https://www.insee.fr/fr/statistiques/fichier/7671844/table-appartenance-geo-communes-2026.zip",
    # populations legales 2021 (fichier d'ensemble)
    "pop_legales_2021.zip":
        "https://www.insee.fr/fr/statistiques/fichier/7739582/ensemble.zip",
    # COG 2026 : mouvements de communes (fusions / renommages)
    "v_mvt_commune_2026.csv":
        "https://www.insee.fr/fr/statistiques/fichier/8740222/v_mvt_commune_2026.csv",
}


def main() -> None:
    INSEE.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        dest = INSEE / name
        print(f"telechargement {name}")
        req = urllib.request.Request(url, headers={"User-Agent": "vdn-classement-lille/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
            f.write(r.read())
        print(f"  -> {dest} ({dest.stat().st_size / 1e6:.1f} Mo)")
        if dest.suffix == ".zip":
            with zipfile.ZipFile(dest) as z:
                z.extractall(INSEE / dest.stem)
            print(f"  -> extrait dans {INSEE / dest.stem}")


if __name__ == "__main__":
    sys.exit(main())
