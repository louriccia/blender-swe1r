# Blender Add-on for Star Wars Episode I: Racer
This is a Blender add-on that allows for importing and exporting from Star Wars Episode I: Racer's .bin files. 

## Status

🚧 **Work in Progress**

This project is currently under active development. While it may be functional for some use cases, please be aware that it is not yet feature-complete, and changes may be introduced frequently. Your feedback, suggestions, and contributions are welcome!

## Features
- Import SWE1R models directly from .bin files
- Edit mesh, collision, texture, vertex color, animation and spline data in blender
- Export SWE1R models directly to .bin files

## Requirements
[Blender 5.0](https://www.blender.org/download/) or newer

## Installation

This add-on ships as a Blender **extension**. Installing it from the extension repository is recommended, since that lets Blender update it for you automatically.

1. In Blender, go to **Edit → Preferences → Get Extensions**.
2. Inside the **Repositories** dropdown in the top-right, click the **+** button and choose **Add Remote Repository…**.
3. Paste this URL, tick **Check for Updates on Startup**, then click **Create**:
   ```
   https://louriccia.github.io/blender-swe1r/index.json
   ```
4. Find **SWE1R Import/Export** in the list and click **Install**.
5. Open the tools on the right side of the 3D view (press **N** if the sidebar is hidden) and click the **SWE1R Import/Export** tab.

### Updating

Once installed from the repository above, Blender detects new versions automatically. To update, go to **Edit → Preferences → Get Extensions**, click **Check for Updates**, then press **Update** next to the add-on.

### Manual install (no auto-updates)

Alternatively, [download the latest release .zip](https://github.com/louriccia/blender-swe1r/releases) and install it via **Get Extensions → ▼ → Install from Disk…** (or drag the .zip into Blender). Extensions installed this way must be updated manually.

## Known Issues

- In game, re-exported racer (pilot) models can still show missing or misplaced feet on the racer select screen, and Aldar Beedo can sink into the floor there; the cause hasn't been found yet (the exported pilot models match stock in everything checked so far).
- Pods built from the add-on's template (the Right Engine / Left Engine / Cockpit / Cable collections) export without LODs or animations and with an empty high detail MAlt model. Imported pods export in full, MAlt included.

## Development

The file parsing code can be tested without Blender:

```
pip install numpy
python -m unittest discover -s tests
```

Set `SWE1R_MODELBLOCK` to the path of the game's `out_modelblock.bin` to also check every pod against the real game data.

### Release check (Blender + game data)

Before tagging a release, run the round-trip suite. It needs Blender 5.x and a copy of the game:

```
python tests/blender/run.py          # smoke set, ~20s
python tests/blender/run.py --full   # every exportable model, ~2-3 min on 8 cores
python tests/blender/run.py --models 2,109
```

For each model it imports from the game's `data/lev01` files and exports into a temp copy; the game's own files are only read. It then checks that the re-import behaves the same in game, not that it has the same node layout:
- the same visual and collision triangles in world space, however they are grouped into meshes and nodes (within 2 game units), with the same texture size and material settings, or surface flags and triggers,
- animated geometry in the same places at sampled frames,
- the same header slots populated, with the nodes behind them in the same places (the game looks nodes up by slot),
- the same spline points,
- the export left every other model, texture and spline byte-identical, and the export settles: after one round-trip, exporting again gives the same size.

Small models share a Blender process (`--batch`, default 8; starting Blender takes longer than most models' round-trip), while tracks and known crashers get their own. If a shared process crashes, its models are run again one per process, so a Blender crash still fails only that model. `--jobs` sets how many processes run at once (default: half the CPU threads, at most 8). Logs go to `tests/blender/logs/`. Blender is found from `BLENDER` or the newest `Blender 5.x` under Program Files; the game data from `SWE1R_GAME_DATA` (default: the Steam install's `data/lev01`).

Failures that already exist are listed in `tests/blender/known_issues.json` and run as expected failures, so the suite fails only on regressions. When a fix makes one of them pass, the run fails with `unexpected success` (or `FIXED?` for a known crash) until its entry is removed.

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE - see the [LICENSE](https://github.com/louriccia/blender-swe1r/blob/main/LICENSE) file for details.

## Thanks
The following people have contributed to this project through feedback and insight. They're awesome!
* aphex0161
* Galeforce
* Leadphalanx
* tilman
* Tim707

## Related Projects
* [swe1r-assets](https://github.com/akopetsch/swe1r-assets) - A C#/.NET library for handling game assets of Star Wars Episode I: Racer
* [swe1r-assets-unity](https://github.com/akopetsch/swe1r-assets-unity) - A Unity package (WIP, currently just a sample project) that allows you to import, modify and re-export assets of the game Star Wars Episode I: Racer.
* [annodue](https://github.com/everalert/annodue) - A universal extension platform for STAR WARS Episode I Racer oriented toward speedrunning.

Support development by sending me some truguts</br>

[![ko-fi](https://www.ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/lightningpirate)
