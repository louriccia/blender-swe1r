"""Build a level, race it in the game with the SW_RACER_RE test runner, and check the telemetry.

    python levels/run_level.py gym [museum_surfaces ...] [--races 2] [--bless] [--no-build]
    python levels/run_level.py all

Needs Blender 5.x (found like tests/blender/run.py), the game, and a dinput.dll built from
SW_RACER_RE's feat/level-telemetry branch (test runner with telemetry_hz / fixed_dt_hz /
screenshot_s). The game's own data/lev01 blocks must be stock: the hook tells a custom track from
stock tracks by comparing against them.

Environment:
    SWE1R_GAME_DIR   the game folder (default: the Steam install)
    SWR_RACER_RE     an SW_RACER_RE checkout with scripts/run_tests.py (default: ../SWR_wt_levels)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tests", "blender"))
from run import find_blender  # noqa: E402

GAME_DIR = os.environ.get("SWE1R_GAME_DIR",
                          r"C:\Program Files (x86)\Steam\steamapps\common\Star Wars Episode I Racer")
RACER_RE = os.environ.get("SWR_RACER_RE", os.path.join(os.path.dirname(REPO), "SWR_wt_levels"))
LEVELS_IN_GAME = "assets/levels"     # custom_tracks_dir, relative to the game folder
FIXED_HZ = 60


LEVELS = ["hello", "gym", "museum_surfaces", "museum_triggers", "museum_environment", "museum_splines",
          "museum_p2p", "museum_animation", "zoo_materials", "zoo_textures_1", "zoo_textures_2",
          "zoo_textures_3", "zoo_textures_4", "zoo_props_1", "zoo_props_2", "zoo_props_3", "zoo_props_4"]


def run_one(level, args):
    """Build, race and check one level; True when every check passed."""
    level_dir = os.path.join(args.out, level)
    run_dir = os.path.join(args.out, level + "-run")
    if not args.no_build:
        built = subprocess.run([find_blender(), "--background", "--factory-startup", "--python-exit-code", "1",
                                "--python", os.path.join(HERE, "build.py"), "--", "--level", level,
                                "--out", level_dir])
        if built.returncode != 0:
            print(f"[{level}] build failed")
            return False

    # the runner races every folder under custom_tracks_dir: give it only this level
    target_root = os.path.join(GAME_DIR, *LEVELS_IN_GAME.split("/"))
    shutil.rmtree(target_root, ignore_errors=True)
    os.makedirs(os.path.join(target_root, level))
    for block in ("out_modelblock.bin", "out_splineblock.bin", "out_textureblock.bin"):
        shutil.copy(os.path.join(level_dir, block), os.path.join(target_root, level, block))

    with open(os.path.join(level_dir, "expectations.json")) as f:
        racers = json.load(f).get("racers", 1)   # a level that needs AI pods (forks) asks for them
    shutil.rmtree(run_dir, ignore_errors=True)
    cmd = [sys.executable, os.path.join(RACER_RE, "scripts", "run_tests.py"), "--game-dir", GAME_DIR,
           "--tracks", ",".join(["custom"] * args.races), "--finish-tracks", "custom", "--laps", "1",
           "--racers", str(racers), "--race-timeout", "400", "--custom-tracks-dir", "./" + LEVELS_IN_GAME,
           "--telemetry-hz", "20", "--fixed-dt-hz", str(FIXED_HZ), "--out", run_dir]
    if args.screenshot_s:
        cmd += ["--screenshot-s", str(args.screenshot_s)]
    ok = subprocess.run(cmd).returncode == 0

    baseline = os.path.join(HERE, "baselines", level + ".json")
    for race in range(1, args.races + 1):
        check = [sys.executable, os.path.join(HERE, "check.py"), level_dir, run_dir, "--race", str(race)]
        if args.bless and race == 1:
            check += ["--bless", baseline]
        else:
            check += ["--baseline", baseline]
        print(f"--- {level} race {race}")
        ok &= subprocess.run(check).returncode == 0
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("levels", nargs="+", help="level names, or 'all'")
    parser.add_argument("--out", default=os.path.join(HERE, "out"))
    parser.add_argument("--races", type=int, default=1)
    parser.add_argument("--screenshot-s", type=int, default=0)
    parser.add_argument("--bless", action="store_true", help="write race 1's outcomes as the baseline")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    levels = LEVELS if args.levels == ["all"] else args.levels
    results = {level: run_one(level, args) for level in levels}
    if len(levels) > 1:
        print()
        for level, ok in results.items():
            print(f"{'ok  ' if ok else 'FAIL'} {level}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
