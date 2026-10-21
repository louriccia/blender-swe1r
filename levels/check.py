"""Compares a test-runner telemetry log against a level's expectations.json.

    python levels/check.py <level dir with expectations.json> <run dir with swr_test_telemetry.jsonl>

Every telemetry sample is placed on the level's centre line (nearest point), which gives the
station the pod was in. Per station it measures what the station asks for and checks the
predictions taken from the decomp. Prints a table, writes report.json into the run dir, and exits
1 when a prediction fails.
"""
import json
import math
import os
import sys

DISTURBED_S = 4.0  # a station entered this soon after a crash or respawn isn't measured cleanly
AIR = 30.0        # SW_RACER_RE swrRace.c: the pod is airborne above 30 units off the ground
MISS = -9000.0    # groundZ is -10000 when the ground raycast misses


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


class Centerline:
    def __init__(self, points):
        self.points = points  # [s, x, y, z, station]
        self.cell = 400.0
        self.grid = {}
        for p in points:
            self.grid.setdefault(self.key(p[1], p[2]), []).append(p)

    def key(self, x, y):
        return int(math.floor(x / self.cell)), int(math.floor(y / self.cell))

    def nearest(self, x, y, z):
        kx, ky = self.key(x, y)
        best, best_d = None, float("inf")
        for r in range(0, 6):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    for p in self.grid.get((kx + dx, ky + dy), ()):
                        # height counts less than distance along the road (jumps, drops)
                        d = (p[1] - x) ** 2 + (p[2] - y) ** 2 + 0.25 * (p[3] - z) ** 2
                        if d < best_d:
                            best, best_d = p, d
            if best is not None and r >= 1:
                break
        return best


def measure(station, samples, events, line_z, cruise):
    out = {"samples": len(samples)}
    if not samples:
        return out
    t0, t1 = samples[0]["t"], samples[-1]["t"]
    out["time_s"] = round(t1 - t0, 2)
    speeds = [s["spd"] for s in samples]
    out["speed_min"], out["speed_max"] = round(min(speeds), 1), round(max(speeds), 1)
    out["speed_mean"] = round(sum(speeds) / len(speeds), 1)
    for kind in station["measure"]:
        if kind == "hover":
            moving = [s for s in samples if s["spd"] > 50 and s["gz"] > MISS]
            if moving:
                heights = sorted(s["pos"][2] - s["gz"] for s in moving)
                out["hover"] = round(heights[len(heights) // 2], 2)
        elif kind == "radius":
            radii = sorted(s["wr"] for s in samples if "wr" in s)
            if radii:
                out["wall_radius"] = round(radii[len(radii) // 2], 2)
        elif kind == "climb":
            zs = [s["pos"][2] for s in samples]
            out["z_min"], out["z_max"] = round(min(zs), 1), round(max(zs), 1)
            out["road_rise"] = round(line_z[1] - line_z[0], 1)
            # the pod hovers ~5 over the road; it climbed if it got to (near) the top
            out["climbs"] = out["z_max"] - line_z[0] >= 0.9 * out["road_rise"]
            # against the pod's flat-road cruising speed: the entry speed can be a downhill's
            out["slows"] = out["speed_min"] < 0.9 * cruise
        elif kind == "air":
            # height over the road under the centre line (the game's groundZ is cached and lags)
            # ...and a ground miss (over a gap) is in the air whatever the height
            above = [(s["t"], s["pos"][2] - s["_z"]) for s in samples]
            air = [s["t"] for s, (_, h) in zip(samples, above) if h > AIR or s["gz"] <= MISS]
            out["airborne"] = bool(air)
            out["air_s"] = round(max(air) - min(air), 2) if air else 0.0
            out["height_max"] = round(max(h for _, h in above), 1)
            out["ground_miss"] = any(s["gz"] <= MISS for s in samples)
        elif kind == "speed":
            out["slows"] = out["speed_min"] < 0.97 * cruise
    out["respawns"] = sum(1 for e in events if e["ev"] == "respawn")
    out["explodes"] = sum(1 for e in events if e["ev"] == "explode")
    out["triggers"] = [e["type"] for e in events if e["ev"] == "trigger"]
    return out


def check(level_dir, run_dir, race=None):
    with open(os.path.join(level_dir, "expectations.json")) as f:
        exp = json.load(f)
    log = load_jsonl(os.path.join(run_dir, "swr_test_telemetry.jsonl"))
    if race is not None:
        log = [e for e in log if e.get("race") == race]
    line = Centerline(exp["centerline"])
    station_of = {}
    for st in exp["stations"]:
        station_of[st["name"]] = st
    per_station = {st["name"]: ([], []) for st in exp["stations"]}
    visits = []
    done = set()    # stations already left once: only the first pass is measured
    current = None
    for e in log:
        if "pos" not in e:
            continue
        x, y, z = e["pos"]
        p = line.nearest(x, y, z)
        if p is None:
            continue
        e["_s"], e["_station"], e["_z"] = p[0], p[4], p[3]
        if e["ev"] == "s" and p[4] != current:
            if current is not None:
                done.add(current)
            current = p[4]
            visits.append(p[4])
        if p[4] in per_station and p[4] not in done:
            per_station[p[4]][0 if e["ev"] == "s" else 1].append(e)

    # cruising speed: the median on the flat closing straight (where the grid is)
    grid = sorted(e["spd"] for e in log if e.get("ev") == "s" and e.get("_station") == "grid" and e["t"] > 20)
    cruise = grid[len(grid) // 2] if grid else 600.0
    incidents = [e["t"] for e in log if e.get("ev") in ("respawn", "explode")]
    report, failures = {"_cruise": cruise}, []
    for st in exp["stations"]:
        samples, events = per_station[st["name"]]
        entered = samples[0]["t"] if samples else None
        disturbed = entered is not None and any(0 <= entered - t <= DISTURBED_S for t in incidents)
        zs = [p[3] for p in exp["centerline"] if p[4] == st["name"]]
        line_z = (zs[0], max(zs)) if zs else (0, 0)
        m = measure(st, samples, events, line_z, cruise)
        m["disturbed"] = disturbed
        verdicts = {}
        for key, want in ({} if disturbed else st["predict"]).items():
            have = m.get(key)
            if key == "respawns":
                have = m["respawns"] > 0 if "respawns" in m else None
            ok = have == want
            verdicts[key] = {"want": want, "have": have, "ok": ok}
            if not ok:
                failures.append(f"{st['name']}: {key} predicted {want}, measured {have}")
        report[st["name"]] = {"measured": m, "predictions": verdicts, "source": st.get("source", "")}
    report["_route"] = visits
    with open(os.path.join(run_dir, "report.json"), "w") as f:
        json.dump(report, f, indent=2)
    return report, failures


BASELINE_KEYS = ("climbs", "slows", "airborne", "respawns", "explodes", "hover", "wall_radius")


def baseline_of(report):
    """The outcomes a later run must reproduce: per station, the BASELINE_KEYS it measured."""
    return {name: {k: r["measured"][k] for k in BASELINE_KEYS if k in r["measured"]}
            for name, r in report.items() if not name.startswith("_") and not r["measured"].get("disturbed")}


def compare_baseline(report, baseline):
    diffs = []
    now = baseline_of(report)
    for station, want in baseline.items():
        have = now.get(station, {})
        if station not in now:
            continue    # disturbed this run: not comparable
        for k, v in want.items():
            h = have.get(k)
            if isinstance(v, bool) or isinstance(h, bool) or not isinstance(v, (int, float)):
                same = h == v
            else:
                same = h is not None and abs(h - v) <= max(0.5, 0.15 * abs(v))
            if not same:
                diffs.append(f"{station}: {k} was {v}, now {h}")
    return diffs


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("level_dir")
    parser.add_argument("run_dir")
    parser.add_argument("--baseline", help="compare against this blessed baseline")
    parser.add_argument("--bless", help="write this run's outcomes as the baseline here")
    parser.add_argument("--race", type=int, default=1, help="which race of the run (1-based)")
    args = parser.parse_args()
    report, failures = check(args.level_dir, args.run_dir, args.race)
    if args.bless:
        with open(args.bless, "w") as f:
            json.dump(baseline_of(report), f, indent=2, sort_keys=True)
        print(f"blessed {args.bless}")
    if args.baseline and os.path.exists(args.baseline):
        with open(args.baseline) as f:
            for d in compare_baseline(report, json.load(f)):
                failures.append(f"baseline {d}")
    for name, r in report.items():
        if name.startswith("_"):
            continue
        m = r["measured"]
        facts = ", ".join(f"{k}={v}" for k, v in m.items() if k not in ("samples",) and v not in ([], None))
        marks = " ".join(f"{k}:{'ok' if v['ok'] else 'FAIL'}" for k, v in r["predictions"].items())
        print(f"{name:<14} {marks:<24} {facts}")
    print("route:", " > ".join(report["_route"]))
    for f in failures:
        print("FAIL", f)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
