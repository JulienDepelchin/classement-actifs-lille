"""
Extraction des espaces verts OSM sur le Nord + Pas-de-Calais, a partir de l'extrait Geofabrik
(hors ligne — Overpass est inaccessible depuis le reseau pro).

Source : data/raw/geo/nord-pas-de-calais.osm.pbf  (download.geofabrik.de, ~238 Mo)
Le pilote OSM de GDAL expose la couche `multipolygons` avec les colonnes leisure / landuse /
natural ; l'assemblage des relations en multipolygones est fait par GDAL.

Memes tags que le retraite (notebook 02) : leisure park/garden/nature_reserve/common ;
landuse forest/grass/meadow/recreation_ground ; natural wood/heath. Exclusions : access
private/no, farmland/farmyard/commercial/industrial.

Sortie : data/raw/geo/espaces_verts_osm_5962.gpkg
"""
from __future__ import annotations
import sys
import warnings
from pathlib import Path
import geopandas as gpd

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
PBF = ROOT / "data" / "raw" / "geo" / "nord-pas-de-calais.osm.pbf"
OUT = ROOT / "data" / "raw" / "geo" / "espaces_verts_osm_5962.gpkg"

WHERE = (
    "leisure IN ('park','garden','nature_reserve','common') "
    "OR landuse IN ('forest','grass','meadow','recreation_ground') "
    "OR natural IN ('wood','heath')"
)


def main() -> None:
    print("lecture de la couche multipolygons (pbf)...")
    ev = gpd.read_file(PBF, layer="multipolygons", where=WHERE, engine="pyogrio",
                       columns=["osm_id", "leisure", "landuse", "natural", "other_tags"])
    print(f"  {len(ev):,} entites brutes")

    ot = ev["other_tags"].fillna("")
    ev = ev[~ot.str.contains('"access"=>"(private|no)"', regex=True)]
    ev = ev[ev.geometry.notna() & ev.geometry.is_valid
            & ev.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    ev = ev.to_crs(2154)

    out = gpd.GeoDataFrame(geometry=ev.geometry.values, crs=2154)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(OUT, driver="GPKG", layer="espaces_verts")

    print(f"\nespaces verts retenus : {len(out):,}")
    print(f"surface totale        : {ev.geometry.area.sum() / 1e6:,.0f} km2")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
