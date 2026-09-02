"""
Poller "vitesse et debit sur les autoroutes vers Lille" -- capteurs DIR Nord (open data).

Source : flux national "Circulation temps reel - reseau non concede" (transport.data.gouv.fr),
DATEX II, refraichi ~toutes les 6 min. Licence Ouverte. On extrait vitesse moyenne + debit des
~168 stations DIR Nord (source DIRN), toutes autour de Lille.

Aucune cle, aucun quota. A lancer regulierement (Cloudflare Worker -> workflow_dispatch, ~10 min).

Entree  : data/rt/dir_nord_stations.csv  (code_pme -> route)
Sortie  : data/rt/dir_nord/<date>.csv    (append)
  poll_utc, feed_time, code_pme, route, vitesse_kmh, debit_vh
"""
from __future__ import annotations
import re
import sys
import csv
import time
import datetime as dt
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
STATIONS = ROOT / "data" / "rt" / "dir_nord_stations.csv"
OUTDIR = ROOT / "data" / "rt" / "dir_nord"
FEED = "https://transport.data.gouv.fr/resources/79165/download"
COLS = ["poll_utc", "feed_time", "code_pme", "route", "vitesse_kmh", "debit_vh"]
SENTINELLES = {9999999.0, 999999.0, 99999.0, -1.0}


def load_routes() -> dict[str, str]:
    with open(STATIONS, encoding="utf-8-sig") as f:
        return {r["code_pme"]: r["route"] for r in csv.DictReader(f)}


def num(x: str) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v in SENTINELLES else v


def fetch(url: str) -> str:
    for essai in (1, 2, 3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vdn-classement-lille/1.0"})
            return urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "ignore")
        except Exception as e:
            if essai == 3:
                raise
            print(f"  retry ({e})")
            time.sleep(10)


def main() -> None:
    routes = load_routes()
    raw = fetch(FEED)
    poll_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = []
    for b in re.findall(r"<siteMeasurements>.*?</siteMeasurements>", raw, re.S):
        mid = re.search(r'id="([^"]+)"', b)
        if not mid or mid.group(1) not in routes:
            continue
        code = mid.group(1)
        ft = re.search(r"<measurementTimeDefault>([^<]+)</", b)
        speeds = [num(s) for s in re.findall(r"<speed>([^<]+)</speed>", b)]
        flows = [num(s) for s in re.findall(r"<vehicleFlowRate>([^<]+)</vehicleFlowRate>", b)]
        speeds = [s for s in speeds if s is not None]
        flows = [s for s in flows if s is not None]
        rows.append({
            "poll_utc": poll_utc,
            "feed_time": ft.group(1) if ft else "",
            "code_pme": code, "route": routes[code],
            "vitesse_kmh": round(sum(speeds) / len(speeds), 1) if speeds else "",
            "debit_vh": int(sum(flows)) if flows else "",
        })

    OUTDIR.mkdir(parents=True, exist_ok=True)
    path = OUTDIR / f"{dt.date.today():%Y%m%d}.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerows(rows)

    import collections
    v = collections.defaultdict(list)
    for r in rows:
        if r["vitesse_kmh"] != "":
            v[r["route"]].append(r["vitesse_kmh"])
    ft = rows[0]["feed_time"] if rows else "?"
    print(f"{poll_utc} | feed {ft} | {len(rows)} stations")
    for rte, sp in sorted(v.items(), key=lambda x: -len(x[1]))[:6]:
        sp.sort()
        print(f"  {rte:16s} n={len(sp):3d}  vitesse min {sp[0]:.0f} | med {sp[len(sp)//2]:.0f}")


if __name__ == "__main__":
    # une source open data indisponible = un poll saute, pas un echec de workflow
    # (evite les mails d'alerte GitHub pour un alea reseau passager).
    try:
        main()
    except Exception as e:
        print(f"poll saute -- source indisponible : {e}")
        sys.exit(0)
