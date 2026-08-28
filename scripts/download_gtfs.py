"""Telechargement des GTFS necessaires au calcul de la desserte TER vers Lille.

- GTFS regional TER Hauts-de-France (base de calcul) : transport.data.gouv.fr, resource 83620
- GTFS national SNCF (controle croise, optionnel)     : eu.ftp.opendatasoft.com / transport.data.gouv.fr

Usage : python scripts/download_gtfs.py [--national]
"""
from __future__ import annotations
import argparse
import sys
import urllib.request
import zipfile
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

SOURCES = {
    "ter_hdf": (
        "https://transport.data.gouv.fr/resources/83620/download",
        RAW / "ter_hdf_gtfs.zip",
        RAW / "ter_hdf",
    ),
    "national": (
        "https://eu.ftp.opendatasoft.com/sncf/plandata/Export_OpenData_SNCF_GTFS_NewTripId.zip",
        RAW / "sncf_gtfs.zip",
        RAW / "gtfs",
    ),
}


def fetch(url: str, zip_path: Path, extract_dir: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"telechargement {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "vdn-classement-lille/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(zip_path, "wb") as f:
        f.write(r.read())
    print(f"  -> {zip_path} ({zip_path.stat().st_size / 1e6:.1f} Mo)")
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(extract_dir)
    print(f"  -> extrait dans {extract_dir} : {sorted(p.name for p in extract_dir.glob('*.txt'))}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--national", action="store_true", help="telecharger aussi le GTFS national SNCF")
    args = ap.parse_args()

    fetch(*SOURCES["ter_hdf"])
    if args.national:
        fetch(*SOURCES["national"])


if __name__ == "__main__":
    sys.exit(main())
