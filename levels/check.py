"""Compares a test-runner telemetry log against a level's expectations.json.

    python levels/check.py <level dir with expectations.json> <run dir with swr_test_telemetry.jsonl>

Every telemetry sample is placed on the level's centre line (nearest point), which gives the
station the pod was in. Per station it measures what the station asks for and checks the
predictions taken from the decomp. Prints a table, writes report.json into the run dir, and exits
1 when a prediction fails.
"""
import json
import math
import struct
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
        if "route" in station["measure"]:
            out["visited"] = False
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
        elif kind == "surface":
            # what the game read from the collision mesh under the pod (swrRace_UpdateSurfaceTag):
            # the middle of the station, away from the meshes either side
            n = len(samples)
            middle = samples[n // 5: n - n // 5] or samples
            out["surf"] = mode(s["surf"] for s in middle)
            out["spec"] = mode(s["spec"] for s in middle)
            out["f0_seen"] = or_all(s["f0"] for s in samples)
            out["f1_seen"] = or_all(s["f1"] for s in samples)
            out["bonus_max"] = round(max(s["bonus"] for s in samples), 1)
            out["sfac_min"] = round(min(s["sfac"] for s in samples), 3)
            out["grip_min"] = round(min(s["grip"] for s in samples), 3)
            out["heat_drop"] = round(samples[0]["heat"] - min(s["heat"] for s in samples), 1)
            out["speed_drop"] = round(samples[0]["spd"] - out["speed_min"], 1)
        elif kind == "lift":
            # the pod riding an animated platform: its height swing and the time between peaks
            zs = [(s["t"], s["pos"][2]) for s in samples]
            out["swing"] = round(max(z for _, z in zs) - min(z for _, z in zs), 1)
            # going down the platform outruns the pod's fall, so the pod leaves it; going up it
            # carries the pod: the longest steady climb is the platform's own speed
            rates = [((z1 - z0) / (t1 - t0)) for (t0, z0), (t1, z1) in zip(zs, zs[1:]) if t1 > t0]
            best, run = [], []
            for r in rates + [None]:
                if r is not None and r > 20 and (not run or abs(r - run[-1]) < 0.15 * abs(run[-1])):
                    run.append(r)
                else:
                    if len(run) > len(best):
                        best = run
                    run = [r] if r is not None and r > 20 else []
            out["rise_rate"] = round(sorted(best)[len(best) // 2], 1) if len(best) >= 4 else None
        elif kind == "route":
            out["visited"] = True
            laps = [s["lap"] for s in samples]
            # lap progress (swrObjJdge_GetRacerProgress) only grows within a station
            out["progress_back"] = round(max([0.0] + [a - b for a, b in zip(laps, laps[1:]) if a - b < 0.5]), 4)
        elif kind == "env":
            # the fog/light read from the mesh under the pod, and the camera's state (test runner
            # "env" lines): the middle of the station, the camera having had time to ease
            env = [e for e in events if e["ev"] == "env"]
            middle = env[len(env) // 3:] or env
            if middle:
                out["fog"] = list(mode(tuple(e["fog"]) for e in middle))
                lights = [e["light"] for e in middle]
                out["light_flags"] = mode(l[0] for l in lights)
                out["light_rgb"] = list(mode(tuple(l[1:7]) for l in lights))
                cam = middle[-1]["cam"]
                out["cam_flags"] = cam[0]
                f = [struct.unpack("<f", struct.pack("<I", w))[0] for w in cam[2:]]
                # +0x2c4 (fog_b in src) is the draw distance, +0x2c8 (fog_r_target) its target and
                # +0x2d0 (fog_b_target) the fog start target, all floats. A target goes back to -1
                # once the value has eased to it (swrObjcMan_UpdateFogAndViewport 0x4538d0), so
                # draw_set is the draw distance being set: the target while easing, else the value.
                out["draw_target"] = round(f[4], 1)
                out["draw_set"] = round(f[4] if f[4] >= 0 else f[3], 1)
                out["fog_start_target"] = round(f[6], 1)
    out["respawns"] = sum(1 for e in events if e["ev"] == "respawn")
    out["explodes"] = sum(1 for e in events if e["ev"] == "explode")
    out["triggers"] = [e["type"] for e in events if e["ev"] == "trigger"]
    out["fired"] = sorted(set(out["triggers"]))
    return out


def mode(values):
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=counts.get) if counts else None


def or_all(values):
    out = 0
    for v in values:
        out |= v
    return out


def holds(have, want):
    """want is a value (equal), or {"bits": m} (all of m set), {"no_bits": m} (none of m set),
    {"lt": v} / {"gt": v}; several keys must all hold."""
    if not isinstance(want, dict):
        return have == want
    if have is None:
        return False
    for op, v in want.items():
        if op == "bits" and have & v != v:
            return False
        if op == "no_bits" and have & v:
            return False
        if op == "lt" and not have < v:
            return False
        if op == "gt" and not have > v:
            return False
    return True


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
        where = e.get("pos") or e.get("center")    # a trigger event is placed by its trigger's centre
        if where is None:
            continue
        x, y, z = where
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

    # AI pods, from the all-pods lines: which AI pod (by index) was seen in which station
    ai_seen = {}
    for e in log:
        if e.get("ev") != "pods":
            continue
        for i, (x, y, z, local) in enumerate(e["p"]):
            if local:
                continue
            p = line.nearest(x, y, z)
            if p is not None:
                ai_seen.setdefault(p[4], set()).add(i)

    # cruising speed: the median on the flat closing straight (where the grid is)
    grid = sorted(e["spd"] for e in log if e.get("ev") == "s" and e.get("_station") == "grid" and e["t"] > 20)
    cruise = grid[len(grid) // 2] if grid else 600.0
    # crashes and respawns, with where they happened: one in an earlier station disturbs the next
    incidents = [(e["t"], e.get("_station")) for e in log if e.get("ev") in ("respawn", "explode")]
    report, failures = {"_cruise": cruise}, []
    for st in exp["stations"]:
        samples, events = per_station[st["name"]]
        events_t = [e["t"] for e in events]
        entered = min([samples[0]["t"]] + events_t) if samples else None
        disturbed = entered is not None and any(0 <= entered - t <= DISTURBED_S and where != st["name"]
                                                for t, where in incidents)
        zs = [p[3] for p in exp["centerline"] if p[4] == st["name"]]
        line_z = (zs[0], max(zs)) if zs else (0, 0)
        m = measure(st, samples, events, line_z, cruise)
        if "route" in st["measure"]:
            m["ai_pods"] = len(ai_seen.get(st["name"], ()))
        m["disturbed"] = disturbed
        verdicts = {}
        for key, want in ({} if disturbed else st["predict"]).items():
            have = m.get(key)
            if key == "respawns" and isinstance(want, bool):
                have = m["respawns"] > 0 if "respawns" in m else None
            ok = holds(have, want)
            verdicts[key] = {"want": want, "have": have, "ok": ok}
            if not ok:
                failures.append(f"{st['name']}: {key} predicted {want}, measured {have}")
        report[st["name"]] = {"measured": m, "predictions": verdicts, "source": st.get("source", "")}
    report["_route"] = visits
    if "grid" in exp:
        ok, detail = check_grid(exp["grid"], log)
        report["_grid"] = detail
        if not ok:
            failures.append(f"grid: {detail}")
    with open(os.path.join(run_dir, "report.json"), "w") as f:
        json.dump(report, f, indent=2)
    return report, failures


def predicted_grid(start, forward, racers):
    """swrObjJdge_GetSpawnTransform (0x465840): rows of 4 and 3 pods alternately, the first 100
    behind spline point 0 and each next 30 further back, pods 20 apart across the row."""
    fx, fy = forward
    lx, ly = -fy, fx
    out, row, left = [], 0, racers
    while left > 0:
        n = min(4 if row % 2 == 0 else 3, left)
        back = 100 + 30 * row
        for i in range(n):
            side = (i - (n - 1) / 2) * 20
            out.append((start[0] - fx * back + lx * side, start[1] - fy * back + ly * side))
        left -= n
        row += 1
    return out


def check_grid(grid, log):
    first = next((e for e in log if e.get("ev") == "pods"), None)
    if first is None:
        return False, "no pods line"
    have = [(p[0], p[1]) for p in first["p"]]
    want = predicted_grid(grid["start"], grid["forward"], grid["racers"])
    unmatched = list(have)
    for w in want:
        best = min(unmatched, key=lambda h: (h[0] - w[0]) ** 2 + (h[1] - w[1]) ** 2, default=None)
        if best is None or (best[0] - w[0]) ** 2 + (best[1] - w[1]) ** 2 > 3 ** 2:
            return False, f"no pod at {tuple(round(v) for v in w)}; pods {[tuple(round(v) for v in h) for h in have]}"
        unmatched.remove(best)
    return True, f"{len(want)} pods where predicted"


BASELINE_KEYS = ("climbs", "slows", "airborne", "respawns", "explodes", "hover", "wall_radius", "surf",
                 "spec", "fired", "fog", "light_flags", "light_rgb", "cam_flags", "draw_set",
                 "fog_start_target", "swing", "rise_rate")  # routes at forks are coin flips: not baselined


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
    if "_grid" in report:
        print("grid:", report["_grid"])
    for f in failures:
        print("FAIL", f)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
