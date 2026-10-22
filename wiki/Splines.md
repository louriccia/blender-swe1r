The spline is the track's racing line. The game uses it for lap progress, the start/finish line and starting grid, and the AI's path. Trigger type 900 also uses it to put pods back on the track (see [Triggers](Triggers)). The old wiki also listed respawn points, the map and the wrong-way arrow; those haven't been re-checked.

Importing a track brings its spline from `out_splineblock.bin`. Export writes it back when **Spline** is on in [Export](Export).

## One curve object
- A track has exactly **one curve object**, placed directly in the model collection (not in **Track** or **Skybox**). With none, or more than one, the spline isn't exported. A curve in a child collection isn't used either; export says so.
- That object can hold several paths (Blender splines). Only Bézier paths with 2 or more points are used.
- Which game spline it replaces follows **Replaces** in the Export panel, so it only works when **Replaces** is a track.
- The object's location, rotation and scale are applied. Point positions and handles are exported; tilt and radius are not.
- **No more than 255 points in all.** The main path counts all its points; each alternate path counts all but its first and last.

## The main path
The main path is the one with the start/finish line. **Point 0**, its first point, is where the line is.
- If any path is **Cyclic**, the first cyclic path is the main path. Other cyclic paths are ignored.
- If no path is cyclic, the main path is the one with the most points.

### The starting grid
The grid is built behind point 0, against the racing direction: the first row is 100 game units back, each further row 30 more, with rows of 4 and 3 pods set 20 apart. **There must be road behind point 0**, or the pods fall through the track during the countdown.

## Loop tracks
Make the main path cyclic: tick **Cyclic** in the Spline panel, or press **Alt+C** in Edit Mode. The race lasts the number of laps chosen in the game.

## Point-to-point tracks
If the main path isn't cyclic, point 0 has no previous point and the track is point-to-point, whatever lap count is chosen. The finish is the dead end at the main path's last point. The Spline panel shows **Not cyclic: point-to-point track**.

## Alternate paths
An alternate path is a fork: it leaves one point and rejoins another.
1. In Edit Mode, select a point near where the fork should leave and press **Shift+D** to duplicate it as a new path.
2. Press **E** to extrude new points along the alternate route.
3. End near the point where it should rejoin.

On export, the alternate path's **first and last points are dropped and replaced by the nearest existing points**: the one it leaves from and the one it rejoins. There is no distance limit, so end each path close to the point you mean. An alternate path can leave from or rejoin another alternate path. A path of just 2 points is a direct link between two existing points.

You don't have to draw an alternate path in the racing direction: export reverses it if it would run backwards.

AI pods, and your own pod on autopilot, pick a branch at random at every fork.

### Limits
- **A point can lead to at most 2 paths**, so only one fork can leave each point.
- **At most 4 paths can arrive at a point.**
- Breaking either limit stops the export with an error.
- **An alternate path can't cross the start/finish line.** Export doesn't stop you: it sees the path as running backwards and reverses it, so pods would take it the wrong way.

## The Spline panel
Select the curve object to see the **Spline** panel in the sidebar. Its buttons act on the active path (the one you last clicked in Edit Mode).
- **Select spawn** enters Edit Mode and selects point 0: the main path's first point (the main path is the first cyclic path, else the longest).
- **Set spawn** makes the selected point on the main path its first point, moving the start/finish line and grid there. The path keeps its shape, handle types included. It needs a cyclic main path, in Edit Mode.
- **Invert** reverses every path in the curve, which reverses the racing direction. The old last point becomes point 0; use **Set spawn** to put the line back where you want it.
- **Cyclic** opens or closes the active path. **Show direction** draws the curve's normals, so you can see which way it runs.
