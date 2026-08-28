"""
Poller GTFS-RT SNCF : capture le retard/annulation des TER desservant Lille, aux gares suivies.

Flux : https://proxy.transport.data.gouv.fr/resource/sncf-gtfs-rt-trip-updates
  (protobuf GTFS-RT TripUpdates, national, sans cle, rafraichi ~toutes les 2 min).

Un appel = un instantane. A lancer regulierement (GitHub Actions, cron */5 sur les fenetres de
pointe). Chaque ligne ecrite = l'etat connu, a l'instant du poll, d'un passage (train x gare).
L'agregation (scripts/build_regularite_reelle.py, plus tard) prendra le DERNIER etat connu par
passage.

Sortie : data/rt/updates/<date_service>.csv   (append, entete cree au besoin)
  poll_utc, date_service, trip_id, start_time, uic, role, stop_seq,
  arr_delay_s, dep_delay_s, trip_annule, stop_saute
"""
from __future__ import annotations
import csv
import re
import sys
import time
import datetime as dt
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
try:
    from google.transit import gtfs_realtime_pb2
except ImportError:
    sys.exit("pip install gtfs-realtime-bindings")

ROOT = Path(__file__).resolve().parents[1]
GARES = ROOT / "data" / "rt" / "gares_suivies.csv"
OUTDIR = ROOT / "data" / "rt" / "updates"
FEED = "https://proxy.transport.data.gouv.fr/resource/sncf-gtfs-rt-trip-updates"
UIC_RE = re.compile(r"(\d{7,8})(?!.*\d)")   # dernier bloc de 7-8 chiffres du stop_id

CANCELED = 3          # trip.schedule_relationship
STU_SKIPPED = 1       # stop_time_update.schedule_relationship (SKIPPED)
COLS = ["poll_utc", "date_service", "trip_id", "start_time", "uic", "role", "stop_seq",
        "arr_delay_s", "dep_delay_s", "trip_annule", "stop_saute"]


def load_gares() -> dict[str, str]:
    out = {}
    with open(GARES, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out[r["uic"].zfill(8)] = r["role"]
    return out


def uic_of(stop_id: str) -> str | None:
    m = UIC_RE.search(stop_id or "")
    return m.group(1).zfill(8) if m else None


def fetch() -> gtfs_realtime_pb2.FeedMessage:
    req = urllib.request.Request(FEED, headers={"User-Agent": "vdn-classement-lille/1.0"})
    for essai in (1, 2, 3):
        try:
            raw = urllib.request.urlopen(req, timeout=60).read()
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(raw)
            return feed
        except Exception as e:
            if essai == 3:
                raise
            print(f"  retry ({e})")
            time.sleep(10)


def main() -> None:
    gares = load_gares()
    lille_uics = {u for u, r in gares.items() if r == "lille"}
    feed = fetch()
    poll_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    by_date: dict[str, list[dict]] = {}
    n_trips = 0
    for e in feed.entity:
        if not e.HasField("trip_update"):
            continue
        tu = e.trip_update
        stus = list(tu.stop_time_update)
        uics = [uic_of(s.stop_id) for s in stus]
        if not (lille_uics & set(u for u in uics if u)):
            continue                                   # ce train ne dessert pas Lille
        n_trips += 1
        trip_annule = int(tu.trip.schedule_relationship == CANCELED)
        d_service = tu.trip.start_date or dt.date.today().strftime("%Y%m%d")
        for s, u in zip(stus, uics):
            if u is None or u not in gares:
                continue
            arr = s.arrival.delay if s.HasField("arrival") and s.arrival.HasField("delay") else ""
            dep = s.departure.delay if s.HasField("departure") and s.departure.HasField("delay") else ""
            by_date.setdefault(d_service, []).append({
                "poll_utc": poll_utc, "date_service": d_service, "trip_id": tu.trip.trip_id,
                "start_time": tu.trip.start_time, "uic": u, "role": gares[u],
                "stop_seq": s.stop_sequence, "arr_delay_s": arr, "dep_delay_s": dep,
                "trip_annule": trip_annule,
                "stop_saute": int(s.schedule_relationship == STU_SKIPPED),
            })

    OUTDIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for d_service, rows in by_date.items():
        path = OUTDIR / f"{d_service}.csv"
        new = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            if new:
                w.writeheader()
            w.writerows(rows)
        total += len(rows)
    print(f"{poll_utc} | trains vers Lille : {n_trips} | lignes ecrites : {total} "
          f"| dates : {sorted(by_date)}")


def loop(minutes: float, every_s: float = 75.0) -> None:
    fin = time.monotonic() + minutes * 60
    n = 0
    while True:
        try:
            main()
        except Exception as e:
            print(f"  poll KO : {e}")
        n += 1
        if time.monotonic() >= fin:
            break
        time.sleep(every_s)
    print(f"loop terminee ({n} polls)")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--loop":
        loop(float(sys.argv[2]))
    else:
        main()
