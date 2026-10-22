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
| `museum_surfaces` | done | Every surface flag and special flag: exact bits reach the game, and their effect. |
| `museum_triggers` | done | Every trigger type and flag: what fires, when, and what it does. |
| `museum_environment` | done | Per-surface fog colour, fog start, draw distance and light flags: the bytes, and what the camera does. |
| `museum_splines` | done | An alternate path that splits off and joins (raced with AI pods). |
| `museum_p2p` | done | A point-to-point track: open spline, one lap, finish at the dead end, the grid. |
| `museum_animation` | done | A lift the pod rides (timing checked), plus rotation, scale and UV-scroll scenery. |
| museum: zones | waiting | Load/unload zones wait for planet-independent custom tracks (see below). |
| `zoo_textures_1..4` | done | All 1573 stock textures that models use, on tiles labelled with their ids. |
| `zoo_materials` | done | The texture format the add-on picks for each kind of image, and every material setting on one oriented texture. |
| `zoo_props_1..4` | done | Every stock Part, Scen and Modl model, copied into a track on a labelled pedestal. |

## Running

```
python levels/run_level.py gym             # build, race once, check against levels/baselines/gym.json
python levels/run_level.py gym --races 2   # race twice (the second run checks repeatability)
python levels/run_level.py gym --bless     # accept this run as the new baseline
python levels/run_level.py gym --screenshot-s 3
python levels/run_level.py all             # every level: about 30 minutes
```

The script runs these steps:

1. **Build.** `build.py` runs in headless Blender. It writes `levels/out/gym/`: the three block
   files, `gym.blend` (open it to see how the level is made) and `expectations.json`.
2. **Deploy.** It copies the blocks to `<game>/assets/levels_test/gym/`. The script owns that
   folder and empties it for each level, so keep your own tracks elsewhere.
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

## What the museum showed

**Surfaces** (`museum_surfaces`): all 23 surface and special flag bits set in Blender reach the game
exactly. Their effects, measured:

- **Fast:** +92 speed bonus over the strip (it eases toward +200 at 25/s).
- **Slow:** speed ×0.75.
- **Slip:** grip ×0.2.
- **Swst:** eases speed toward ×0.1 and cancels boost. It is not a start-line marker.
- **Lava:** engine heat drops by 47 over the strip.
- **Pod flags:**
  - **Swmp, Soft, Side, Mirr:** set the pod's matching `ON_*` flag (Mirr only with reflections on).
  - **Magnet, elevation:** set `MAGNET` and `FULL_RAYCAST`.
  - **ZOn:** sets zero-g.
  - **Flat:** never sets anything on a human pod (it is AI only).
- **Fall:** respawns only once the pod is within 30 of the surface. Pods fall slowly, so a Fall pad
  300 down a pit is flown straight over.

**Triggers** (`museum_triggers`):
- **Flags behave as the decomp says:**
  - **0x1** disarms the trigger.
  - **0x2** needs speed above 150.
  - **0x4 / 0x8 / 0x10** skip laps 1 / 2 / 3.
  - **0x20** fires for the local pod only.
- **A trigger only works on the mesh it is parented to.** The game tests only the triggers of the
  collision mesh under the pod.
- **Some triggers fire every frame the pod is inside them:** types without a handler (0, 107),
  101/307 doors, and 106/203 fire. The destructible, animation, 104 and 108 types fire once, then
  disarm themselves.
- **Loading a track changes some trigger flags.**
  - 100, 202 and 212 get 0x2.
  - 105, 203, 312 and 314 get 0x20.
  - **213 and 306 get 0x24, so they never fire on lap 1.**
- **104 explodes the pod.**
- **900 resets the pod onto the spline at its own progress, at speed 0.** Put on the racing line, it
  resets the pod into itself every frame, and the pod is stuck. Keep it out of bounds, as stock
  tracks do.
- **Trigger effects use per-planet models** (`swrObjTrig_LoadAndInitializeTriggerModels`). A trigger
  whose effect slot the track's planet doesn't load can crash the game. **501 (lava splash) crashes
  everywhere except Baroonda.**

  | Planet | Effect slots loaded |
  |---|---|
  | 0 Tatooine | 0 rocksmall, 1 rockbig, 2 balloon |
  | 1 Ando Prime | 0 shards, 1 rockbig, 2 flag tip, 3/4 flag wave |
  | 2 Aquilaris | 0 big fish, 1 rockgiant |
  | 3 Ord Ibanna | none |
  | 4 Baroonda | 0 treesmash, 1 rockash, 2 flame, 3 rockgiant, 5 lava |
  | 5 Mon Gazza | 0 dozer, 2 flame |
  | 6 Oovo IV | 0 rockzero |
  | 7 Malastare | 0 methane |

  314 uses slot 0, 501 slot 5, 213 slot 3 and 306 slot 1.

**Environment** (`museum_environment`): every fog and light byte set in Blender reaches the game.

- **`fog_color_update`:** turns fog on. The fog colour is also the background colour.
- **`fog_min` is not a distance.** The game uses it as an N64-style fog value and clamps it at 996
  (the literal 0x44790000). The add-on's 1–30000 range is misleading.
- **`fog_range_update`:** sets the draw distance from `fog_max`.
- **`fog_clear`:** the game only turns fog off through bit 0x1 with a start of 0 or less. The add-on
  used to write bit 0x2 for it, which cleared nothing on its own; it now writes 0x1 with start 0,
  and the exhibit checks Clear Fog alone turns fog off.
- **Lights:**
  - A light sets `light_flags` 0x3. Invert, flicker and persistent add 0x4, 0x8 and 0x10.
  - **The add-on calls 0x4 "invert", but the game reads it as "the light vector is a position".**
  - Track geometry with baked vertex colours isn't lit; the pod is.

**Splines** (`museum_splines`, `museum_p2p`):

- **Forks:** the add-on writes an alternate path as a split (`next_count` 2) and a join
  (`prev_count` 2). AI pods flip a coin at every fork (`swrRace.c:2382-2394`), and the autopilot
  pod does too.
- **Point-to-point:** a track whose spline point 0 has no previous point is one, no matter what lap
  count is set. Its finish is the dead end.
- **The grid is behind point 0** (`swrObjJdge_GetSpawnTransform`):
  - the first row is 100 back, and each further row 30 more;
  - rows alternate 4 and 3 pods, set 20 apart.

  **A point-to-point track needs road behind point 0.** Without it, every pod falls through the
  countdown.

**Animation** (`museum_animation`):

- Exported animations play with the authored timing: the lift rises at exactly 150 units/s as built.
- **Animated collision needs the "elevation" flag (full raycast).** Without it, the pod's ground ray
  uses the track mesh the game cached under the spline at load. The platform's visual moves, but the
  pod rides where the platform was at load: a 4-unit swing on a 150-unit lift.

## What the zoo showed

- **Stock textures are referenced, not copied.** A material can use a stock texture by id: give it
  an image the importer made (it carries the id, format, hashes and mip-chain notes) and export
  writes the stock index. The four texture-zoo parts add only their own 3 textures to the block.
  `scan_textures.py` writes each stock texture's size and format, which only the models record,
  to `data/stock_textures.json`.
- **Image formats the add-on picks** (`zoo_materials` re-imports its export to check them):

  | Image | Format |
  |---|---|
  | 16 greys | I4 |
  | 256 greys | I8 |
  | 4 colours | CI4 |
  | 200 or 1000 colours | CI8 |
  | partial alpha | RGBA32 |
  | 256×256 | 128×128 |

  **A 100×40 image is resized, with filtering, to 128×64, not padded**, so its 4 colours become
  many. It comes out CI8 and blurred.
- **Stock models re-export from inside a track.** Every Part, Scen and Modl model comes through
  with all its triangles, except ones the zoo's own scaling shrank below one game unit (those
  collapse when vertices round to whole units).

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
| `scan_textures.py` | Imports every stock model and lists each texture's size and format (for the zoo). |
| `level.verify()` | Optional Blender-side check of a level's export (re-imports it); `build.py` fails on a problem. |
| `baselines/*.json` | Blessed outcomes per station. Stations disturbed by a crash just before them aren't compared. |
