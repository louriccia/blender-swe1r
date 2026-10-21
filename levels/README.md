# Generated levels: gym, museum, zoo

Tracks built by script, so they can be rebuilt after every add-on change and raced by the game's
test runner. Each one serves two purposes:

- **Documentation you can drive.** The level has signs, and its stations show a limit or a feature
  as it actually behaves in the game.
- **A parity check.** The add-on exports the level, the game races it, and `check.py` compares
  what the pod did against predictions from the SW_RACER_RE decomp and a blessed baseline.

The idea comes from Robin-Yann Storm's talk *Gyms, Zoos, and Museums: Your documentation should
be in-game* (GodotFest 2025):

- a **gym** measures movement;
- a **zoo** shows every asset;
- a **museum** demonstrates every feature.

| Level | Status | What it is |
|---|---|---|
| `hello` | done | The smallest track that races: a flat loop. Proves the from-scratch export path. |
| `gym` | done | The pod's physical limits: slopes, jumps, drops, gate widths, turns. |
| `museum` | planned | Every surface flag, trigger type, zone, fog/light setting, animation and spline feature. |
| `zoo` | planned | Every stock texture and material setting, and stock props, labelled by id. |

## Running

```
python levels/run_level.py gym             # build, race once, check against levels/baselines/gym.json
python levels/run_level.py gym --races 2   # race twice (the second run checks repeatability)
python levels/run_level.py gym --bless     # accept this run as the new baseline
python levels/run_level.py gym --screenshot-s 3
```

The script runs these steps:

1. **Build.** `build.py` runs in headless Blender. It writes `levels/out/gym/`: the three block
   files, `gym.blend` (open it to see how the level is made) and `expectations.json`.
2. **Deploy.** It copies the blocks to `<game>/assets/levels/gym/`.
3. **Race.** It runs SW_RACER_RE's `scripts/run_tests.py` on them:
   - the autopilot drives one lap;
   - the simulation step is fixed at 1/60 s, so runs repeat;
   - telemetry is recorded at 20 Hz.
4. **Check.** It runs `check.py`.

What it needs:

- **The game**, with its `data/lev01` blocks stock. The hook decides which tracks in a folder are
  custom by comparing them against those blocks.
- **A `dinput.dll` from SW_RACER_RE branch `feat/level-telemetry`.** That branch adds these test
  runner options: `telemetry_hz`, `screenshot_s` and `fixed_dt_hz`.
- **Blender 5.x.**

To race a level by hand, copy `levels/out/<level>/out_*.bin` into a folder under
`<game>/assets/custom_tracks/`.

## What the gym measured

Measured on the fully upgraded test pod, which cruises at 614 on flat road. Every value here
comes from the game, not from reading code.

| Station | Result |
|---|---|
| Hover | The pod rides 5.0 units above the road. |
| Wall collision | The pod is a sphere of radius 5.0 for walls: it slides through an 11-unit slot at full speed, and its body visibly clips through the walls. |
| Slopes 5–20° (500 long) | Climbed with no speed loss. |
| Slopes 25–40° (150 high) | Climbed, but speed falls to 390 (25°), 380 (30°), 305 (35°) and 230 (40°). The decomp clamps vertical speed above about 20.3° (`swrRace.c:4509`). It costs speed; it doesn't stop the climb. |
| Slope 45° (150 high) | A sudden kink from flat road at cruising speed **crashes the pod** (explodes, then respawns). |
| Gaps (10° kicker, landing level with the lip) | 200 and 400 are cleared. 600 and 800 are not: the pod falls, and after about 3 s with no ground below it respawns. |
| Drops 100 / 300 / 600 | No respawn and no crash. Up to about 1 s in the air. |
| Turns R2500 | Flat: dips to 576. Banked 20°: speeds up to 640. |

**Physics notes** (from the decomp, as checked by the gym):
- A surface steeper than about 45.6° from the pod's "up" counts as a wall
  (`swrRace_ApplyWallCollision`).
- The pod is airborne more than 30 units above the ground.
- It crashes when its speed is above 325 and drops by more than 140 in one frame
  (`swrRace_DeathSpeedMin` / `swrRace_DeathSpeedDrop`).

## Facts every custom track runs into

- **Vertex coordinates are int16 game units.** Keep geometry within ±32767 of its node; the gym
  centres its loop on the origin for this reason.
- **Only about 52 new textures fit.** The add-on stops at 1700 and the stock block has 1648. The gym
  uses 3. Signs share one 128×128 glyph atlas, and vertex colours tint it.
- **Tracks have no lighting by default.** Bake shading into the vertex colours (`lib.shade`), or
  flat white geometry won't read in 3D.
- **Every folder custom track is planet 1, sub-track 0** (`dinput_hook/custom_tracks.cpp`). The game
  treats that slot specially: `swrObjJdge_InitTrack` (0x466BD0) derives the collision zones from the
  pod's position on an XY grid. Load/unload zones authored in Blender therefore don't apply on these
  tracks. Dust colours and trigger effect models are planet 1's too.

## Files

| File | What it does |
|---|---|
| `lib.py` | Scene setup, meshes, materials, vertex shading, the spline, and export to a custom-track folder. |
| `course.py` | Lays a track out as segments: straights, ramps, banked arcs, gaps and cliffs. Closes the loop and gives every station's extent. |
| `signs.py` | In-world text from the glyph atlas. |
| `level_*.py` | One per level. `build(addon)` returns the model collection and the expectations. |
| `check.py` | Telemetry → per-station measurements, then predictions and the baseline. |
| `baselines/*.json` | Blessed outcomes per station. Stations disturbed by a crash just before them aren't compared. |
