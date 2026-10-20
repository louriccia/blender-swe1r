"""Runs the headless Blender round-trip suite, a few models per Blender process.

    python tests/blender/run.py            # smoke set
    python tests/blender/run.py --full     # every exportable model
    python tests/blender/run.py --models 2,109 --jobs 2 --batch 1

Starting Blender takes a few seconds, more than most models' round-trip, so small models share a
process (--batch). Tracks and known crashers get their own, and when a shared process crashes
its models are run again one per process, so a hard Blender crash still fails only that model.
Blender is found from $BLENDER, then the newest "Blender 5.x" under Program Files, then PATH.
The game's data/lev01 folder comes from $SWE1R_GAME_DATA (default: the Steam install); it is only read.
Per-model logs are written to tests/blender/logs/.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(os.path.dirname(HERE))
SUITE = os.path.join(HERE, "roundtrip.py")
LOG_DIR = os.path.join(HERE, "logs")
KNOWN_ISSUES = os.path.join(HERE, "known_issues.json")
TIMEOUT_S = 900
# outcome lines of the verbose unittest output; it prints a test's docstring on the line after its
# name, before the outcome. The test class is named after the model (Model001_...).
TEST_LINE = re.compile(r"^(test_\w+) \(\w+\.Model(\d+)_.*?\)(?:\n.*?)? \.\.\. "
                       r"(ok|FAIL|ERROR|expected failure|unexpected success|skipped.*)$", re.M)


def find_blender():
    if os.environ.get("BLENDER"):
        return os.environ["BLENDER"]
    candidates = glob.glob(r"C:\Program Files\Blender Foundation\Blender 5.*\blender.exe")
    if candidates:
        return max(candidates, key=lambda p: [int(n) for n in re.findall(r"\d+", os.path.basename(os.path.dirname(p)))])
    return shutil.which("blender")


def suite_constants():
    """SMOKE_MODELS and the model list, read without importing bpy."""
    namespace = {}
    with open(os.path.join(ADDON_DIR, "swe1r", "model_list.py")) as f:
        exec(f.read(), namespace)
    with open(SUITE) as f:
        smoke = re.search(r"SMOKE_MODELS = \[(.*?)\]", f.read(), re.S).group(1)
    smoke_ids = [int(m) for m in re.findall(r"^\s*(\d+),", smoke, re.M)]
    return smoke_ids, namespace["model_list"]


def known_crashes():
    with open(KNOWN_ISSUES) as f:
        return {int(k): v["crash"] for k, v in json.load(f).items() if not k.startswith("_") and "crash" in v}


def record_known_issues(results):
    with open(KNOWN_ISSUES) as f:
        known = json.load(f)
    note = f"recorded {time.strftime('%Y-%m-%d')}, not yet triaged"
    for r in results:
        entry = known.setdefault(str(r["id"]), {})
        if r["status"] in ("CRASH", "TIMEOUT", "KNOWN"):
            entry.setdefault("crash", f"{r['status'].lower()} {note}")
            continue
        entry.pop("crash", None)
        for test, outcome in r["tests"]:
            if outcome in ("FAIL", "ERROR"):
                entry.setdefault(test, note)
            elif outcome in ("ok", "unexpected success"):
                entry.pop(test, None)
    meta = {k: v for k, v in known.items() if k.startswith("_")}
    models = {k: v for k, v in known.items() if not k.startswith("_") and v}
    with open(KNOWN_ISSUES, "w", newline="\n") as f:
        json.dump({**meta, **dict(sorted(models.items(), key=lambda kv: int(kv[0])))}, f, indent=2)
        f.write("\n")


def run_process(blender, model_ids, config_dir):
    """Runs the suite for model_ids in one Blender process; returns (output, exit code or None on timeout)."""
    # each process gets its own config dir: the add-on rewrites its settings file on every prop change
    process_config = os.path.join(config_dir, "_".join(map(str, model_ids)))
    process_temp = os.path.join(process_config, "tmp")
    os.makedirs(process_temp)
    # temp copies of the game data (~100MB a model) live under the run's dir, so they are
    # removed at the end even if Blender crashes before cleaning up
    env = dict(os.environ, BLENDER_USER_CONFIG=process_config, TEMP=process_temp, TMP=process_temp)
    cmd = [blender, "--background", "--factory-startup", "--python-exit-code", "1",
           "--python", SUITE, "--", "--models", ",".join(map(str, model_ids))]
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, errors="replace",
                              timeout=TIMEOUT_S * len(model_ids))
        return proc.stdout + proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        return "".join(s.decode(errors="replace") if isinstance(s, bytes) else s for s in (e.stdout, e.stderr) if s), None
    finally:
        shutil.rmtree(process_config, ignore_errors=True)


def crashed(output):
    return "EXCEPTION_ACCESS_VIOLATION" in output or "Segmentation fault" in output or not re.search(r"^Ran \d+ test", output, re.M)


def model_result(model_id, name, output, code, known_crash, seconds, log_path):
    tests = [(test, outcome) for test, mid, outcome in TEST_LINE.findall(output) if int(mid) == model_id]
    if code is None:
        status = "TIMEOUT"
    elif crashed(output):
        status = "KNOWN" if known_crash else "CRASH"
    elif known_crash:
        status = "FIXED?"  # listed as a known crash but ran to completion: update known_issues.json
    elif any(outcome in ("FAIL", "ERROR", "unexpected success") for _, outcome in tests):
        status = "FAIL"
    else:
        status = "PASS"
    return {"id": model_id, "name": name, "status": status, "tests": tests, "seconds": seconds, "log": log_path}


def run_batch(blender, model_ids, names, config_dir, crashes):
    """Results for model_ids, run in one process, or one process each if that one crashed."""
    start = time.time()
    output, code = run_process(blender, model_ids, config_dir)
    if len(model_ids) > 1 and (code is None or crashed(output)):
        # find out which model brought the process down
        return [r for mid in model_ids for r in run_batch(blender, [mid], names, config_dir, crashes)]
    elapsed = time.time() - start
    if len(model_ids) == 1:
        log_path = os.path.join(LOG_DIR, f"model_{model_ids[0]:03d}.log")
    else:
        log_path = os.path.join(LOG_DIR, f"models_{model_ids[0]:03d}-{model_ids[-1]:03d}.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(output)
    # roundtrip.py prints how long each model's round-trip took; the tests themselves are quick
    timings = {int(mid): float(t) for mid, t in re.findall(r"^SWE1R_MODEL_SECONDS (\d+) ([\d.]+)$", output, re.M)}
    return [model_result(mid, names.get(mid, "?"), output, code, crashes.get(mid),
                         timings.get(mid, elapsed / len(model_ids)), log_path) for mid in model_ids]


def batches(model_ids, model_list, crashes, size):
    """Tracks and known crashers alone (submitted first, as they are slowest), the rest in groups of size."""
    extensions = {m["index"]: m["extension"] for m in model_list}
    alone = [mid for mid in model_ids if extensions.get(mid) == "Trak" or mid in crashes or size <= 1]
    shared = [mid for mid in model_ids if mid not in alone]
    return [[mid] for mid in alone] + [shared[i:i + size] for i in range(0, len(shared), size)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="every exportable model instead of the smoke set")
    parser.add_argument("--models", help="comma-separated model ids")
    parser.add_argument("--jobs", type=int, default=max(1, min(8, (os.cpu_count() or 2) // 2)),
                        help="Blender processes to run at once")
    parser.add_argument("--batch", type=int, default=8, help="models per Blender process (tracks always run alone)")
    parser.add_argument("--record", action="store_true",
                        help="write this run's failures into known_issues.json and drop entries that now pass")
    args = parser.parse_args()

    blender = find_blender()
    if not blender or not os.path.exists(blender):
        sys.exit("Blender not found; set BLENDER to blender.exe")

    smoke_ids, model_list = suite_constants()
    names = {m["index"]: f'{m["extension"]} {m["name"]}' for m in model_list}
    if args.models:
        model_ids = [int(m) for m in args.models.split(",")]
    elif args.full:
        model_ids = [m["index"] for m in model_list if m["extension"] != "MAlt"]
    else:
        model_ids = smoke_ids

    free_gb = shutil.disk_usage(tempfile.gettempdir()).free / 1e9
    if free_gb < 2:
        # each running model holds ~100MB of game data copies; a full disk shows up as bogus failures
        sys.exit(f"only {free_gb:.1f} GB free in {tempfile.gettempdir()}; free some space first")

    shutil.rmtree(LOG_DIR, ignore_errors=True)  # stale logs from other models would mislead
    os.makedirs(LOG_DIR)
    # throwaway Blender configs and temp dirs, so the add-on's settings file never touches the
    # user's real one
    config_dir = tempfile.mkdtemp(prefix="swe1r_blender_cfg_")
    print(f"{blender}\n{len(model_ids)} models, {args.jobs} at a time\n")

    crashes = known_crashes()
    results = []
    start = time.time()
    try:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(run_batch, blender, batch, names, config_dir, crashes)
                       for batch in batches(model_ids, model_list, crashes, args.batch)]
            for r in (r for future in as_completed(futures) for r in future.result()):
                results.append(r)
                failed = [f"{t}: {outcome}" for t, outcome in r["tests"] if outcome in ("FAIL", "ERROR", "unexpected success")]
                known = sum(1 for _, outcome in r["tests"] if outcome == "expected failure")
                if r["status"] == "KNOWN":
                    detail = f"  (known crash: {crashes[r['id']]})"
                elif failed:
                    detail = f"  ({', '.join(failed)})"
                else:
                    detail = f"  ({known} known issues)" if known else ""
                print(f"{r['status']:8} {r['id']:3d} {r['name']:<40} {r['seconds']:5.0f}s{detail}", flush=True)
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)
    results.sort(key=lambda r: model_ids.index(r["id"]))

    if args.record:
        record_known_issues(results)
        print(f"\nRecorded current failures in {KNOWN_ISSUES}; review the diff before committing it")
        return

    bad = [r for r in results if r["status"] not in ("PASS", "KNOWN")]
    print(f"\n{len(results) - len(bad)}/{len(results)} models passed in {time.time() - start:.0f}s. Logs: {LOG_DIR}")
    for r in bad:
        print(f"  {r['status']} model {r['id']}: {r['log']}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
