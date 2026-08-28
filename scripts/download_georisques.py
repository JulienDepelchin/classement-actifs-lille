"""
Telecharge les risques naturels/miniers par commune candidate depuis l'API Georisques.

Deux endpoints fiables (filtrent bien par code_insee) :
  - gaspar/risques : liste des risques recenses (DDRM/GASPAR) -> flags inondation / remontee de
    nappe / minier / mouvement de terrain / techno
  - gaspar/catnat  : historique des arretes de catastrophe naturelle -> frequence inondation,
    frequence secheresse (= proxy retrait-gonflement des argiles), date du dernier arrete

(gaspar/pprn renvoie une liste non filtree par commune dans nos tests -> ecarte.)

Sortie : data/raw/georisques/georisques_communes.csv
"""
from __future__ import annotations
import sys
import time
import json
import urllib.request
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / "data" / "output" / "communes_candidates.csv"
OUT = ROOT / "data" / "raw" / "georisques" / "georisques_communes.csv"
API = "https://www.georisques.gouv.fr/api/v1"
PAUSE = 0.2

MINIER_LABELS = ("affaissement minier", "gaz de mine", "aléa minier", "risque minier")
TECHNO_LABELS = ("industriel", "nucléaire", "rupture de barrage", "rupture de digue")


def get(ep: str, **p) -> dict:
    q = "&".join(f"{k}={v}" for k, v in p.items())
    url = f"{API}/{ep}?{q}"
    for essai in (1, 2, 3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vdn-classement-lille/1.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            if essai == 3:
                raise
            time.sleep(4)
        except Exception:
            if essai == 3:
                raise
            time.sleep(4)


def commune_risques(insee: str) -> dict:
    d = get("gaspar/risques", code_insee=insee)
    rows = d.get("data") or []
    if not rows:
        return {}
    labels = [x["libelle_risque_long"].lower() for x in rows[0].get("risques_detail", [])]
    blob = " | ".join(labels)
    return {
        "georisques_libelle": rows[0].get("libelle_commune"),
        "risque_inondation": int("inondation" in blob),
        "risque_remontee_nappe": int("remont" in blob and "nappe" in blob),
        "risque_minier": int(any(m in blob for m in MINIER_LABELS)),
        "risque_mvt_terrain": int("mouvement de terrain" in blob),
        "risque_techno": int(any(t in blob for t in TECHNO_LABELS)),
    }


def commune_catnat(insee: str) -> dict:
    rows, page = [], 1
    while True:
        d = get("gaspar/catnat", code_insee=insee, page=page, page_size=100)
        rows += d.get("data") or []
        if page >= d.get("total_pages", 1) or not d:
            break
        page += 1
    if not rows:
        return {"catnat_total_n": 0, "catnat_inondation_n": 0, "catnat_secheresse_n": 0,
                "catnat_inondation_depuis_2010_n": 0, "catnat_derniere_annee": None}

    def annee(r):
        try:
            return int(r["date_publication_jo"][-4:])
        except Exception:
            return None

    lib = [(r["libelle_risque_jo"].lower(), annee(r)) for r in rows]
    inond = [a for l, a in lib if "inondation" in l]
    return {
        "catnat_total_n": len(rows),
        "catnat_inondation_n": len(inond),
        "catnat_secheresse_n": sum("écheresse" in l for l, _ in lib),
        "catnat_inondation_depuis_2010_n": sum(1 for a in inond if a and a >= 2010),
        "catnat_derniere_annee": max((a for _, a in lib if a), default=None),
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cand = pd.read_csv(CAND, dtype={"code_insee": str})[["code_insee", "commune"]]
    done = {}
    if OUT.exists():
        done = pd.read_csv(OUT, dtype={"code_insee": str}).set_index("code_insee").to_dict("index")

    rows, manques = [], []
    for i, r in enumerate(cand.itertuples(), 1):
        if r.code_insee in done and pd.notna(done[r.code_insee].get("georisques_libelle")):
            rows.append({"code_insee": r.code_insee, "commune": r.commune, **done[r.code_insee]})
            continue
        rq = commune_risques(r.code_insee)
        if not rq:
            manques.append(f"{r.code_insee} {r.commune}")
        cn = commune_catnat(r.code_insee)
        rows.append({"code_insee": r.code_insee, "commune": r.commune, **rq, **cn})
        time.sleep(PAUSE)
        if i % 40 == 0:
            pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8-sig")
            print(f"  {i}/{len(cand)}")

    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\n{len(df)} communes -> {OUT}")
    if manques:
        print(f"SANS reponse gaspar/risques ({len(manques)}) : {manques}")
    for c in ["risque_inondation", "risque_remontee_nappe", "risque_minier", "risque_mvt_terrain", "risque_techno"]:
        if c in df:
            print(f"  {c:24s}: {int(df[c].sum())} communes")
    print(df[["catnat_inondation_n", "catnat_secheresse_n", "catnat_inondation_depuis_2010_n"]].describe().round(1).to_string())


if __name__ == "__main__":
    main()
