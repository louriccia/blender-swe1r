"""Runs the headless Blender round-trip suite, one Blender process per model.

    python tests/blender/run.py            # smoke set
    python tests/blender/run.py --full     # every exportable model
    python tests/blender/run.py --models 2,109 --jobs 2

Each model gets its own process so a hard Blender crash fails that model instead of the whole run.
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
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(os.path.dirname(HERE))
SUITE = os.path.join(HERE, "roundtrip.py")
LOG_DIR = os.path.join(HERE, "logs")
KNOWN_ISSUES = os.path.join(HERE, "known_issues.json")
TIMEOUT_S = 900


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


def run_model(blender, model_id, name, config_dir, known_crash):
    log_path = os.path.join(LOG_DIR, f"model_{model_id:03d}.log")
    # each process gets its own config dir: the add-on rewrites its settings file on every prop change
    model_config = os.path.join(config_dir, str(model_id))
    os.makedirs(model_config)
    env = dict(os.environ, BLENDER_USER_CONFIG=model_config)
    cmd = [blender, "--background", "--factory-startup", "--python-exit-code", "1",
           "--python", SUITE, "--", "--models", str(model_id)]
    start = time.time()
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, errors="replace", timeout=TIMEOUT_S)
        output, code = proc.stdout + proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        output = "".join(s.decode(errors="replace") if isinstance(s, bytes) else s for s in (e.stdout, e.stderr) if s)
        code = None
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(output)

    # verbose unittest prints a test's docstring on the line after its name, before the outcome
    tests = re.findall(r"^(test_\w+) \(.*?\)(?:\n.*?)? \.\.\. (ok|FAIL|ERROR|expected failure|unexpected success|skipped.*)$",
                       output, re.M)
    if code is None:
        status = "TIMEOUT"
    elif "EXCEPTION_ACCESS_VIOLATION" in output or "Segmentation fault" in output or not re.search(r"^Ran \d+ test", output, re.M):
        status = "KNOWN" if known_crash else "CRASH"
    elif known_crash:
        status = "FIXED?"  # listed as a known crash but ran to completion: update known_issues.json
    elif code == 0:
        status = "PASS"
    else:
        status = "FAIL"
    return {"id": model_id, "name": name, "status": status, "tests": tests,
            "seconds": time.time() - start, "log": log_path}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="every exportable model instead of the smoke set")
    parser.add_argument("--models", help="comma-separated model ids")
    parser.add_argument("--jobs", type=int, default=4, help="Blender processes to run at once")
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

    shutil.rmtree(LOG_DIR, ignore_errors=True)  # stale logs from other models would mislead
    os.makedirs(LOG_DIR)
    # throwaway Blender configs so the add-on's settings file never touches the user's real one
    config_dir = tempfile.mkdtemp(prefix="swe1r_blender_cfg_")
    print(f"{blender}\n{len(model_ids)} models, {args.jobs} at a time\n")

    crashes = known_crashes()
    results = []
    try:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(run_model, blender, mid, names.get(mid, "?"), config_dir, crashes.get(mid))
                       for mid in model_ids]
            for future in futures:
                r = future.result()
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

    if args.record:
        record_known_issues(results)
        print(f"\nRecorded current failures in {KNOWN_ISSUES}; review the diff before committing it")
        return

    bad = [r for r in results if r["status"] not in ("PASS", "KNOWN")]
    print(f"\n{len(results) - len(bad)}/{len(results)} models passed. Logs: {LOG_DIR}")
    for r in bad:
        print(f"  {r['status']} model {r['id']}: {r['log']}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
