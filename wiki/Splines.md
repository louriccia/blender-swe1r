## Spline Editing
When importing a track, it should come with a spline object. This spline is from `out_splineblock.bin` and is the entity that the game uses to define the player's lap progression, start and finish line, spawn/respawn points, map display, guide arrow behavior, Zero-G mode (ZOn), and AI pathing. 
* The spline should only exist as a single spline object in Blender, in which there can be multiple paths.
* The "main spline" is the path where the start/finish line and player spawns (point 0). All other paths are considered alternate paths that branch from and rejoin the main spline.
* If the spline is not above any collidable and spawnable mesh (does not have the NRsp flag), the game will crash because there is nowhere for the player to spawn.
* If the spline is too high above any mesh (over 5000 in-game units), it may crash the game.

#### Cyclic Tracks
All tracks in the game are cyclic by default, meaning their last point connects back to their first point to create a loop.
* The main spline is considered to be the only closed loop spline. To create a closed loop spline, select a point on the spline and press Alt + C or check "Cyclic" under Object Data Properties -> Active Spline -> Cyclic.
* Start/Finish line and player will spawn at point 0.
* Race is finished once the player has completed the selected number of circuits.

#### Non-Cyclic Tracks (Rally)
The game also supports using a non-cyclic spline for a track. This allows us to easily create a point-to-point (rally) track.
* If no cyclic splines are found, the main spline with be the one with the most points.
* Player spawns at point 0 and the finish line spawns at the last point. 
* Race is finished once the player crosses the finish line. The race will always have 1 "lap" no matter how many laps the player has chosen.

#### Branching Paths
Some tracks feature branching paths. Blender does not support branching splines, so the first and last points of any alternate paths will be merged to the closest eligible points on any existing splines.  
To create an alternate path, create a new spline within the same curve object. This is easily done by selecting a spline point (in edit mode) and pressing Shift + D to duplicate an existing point, then pressing E to extrude. When ending the path, keep in mind that the last point you place will be replaced by the closest existing point (if it isn't already joining 4 paths).  

##### Limitations
* Splines must have 3-255 points.
* Splines cannot split more than 2 times on any point.
* Splines cannot join more than 4 times on any point.
* Splines cannot have paths that start before and end after the finish line on main spline.
* Splines cannot have paths that end at an earlier point on the main spline than the point where they begin.

#### The Spline panel
Select the spline to see the **Spline** panel in the sidebar:
* **Select spawn** selects point 0, where the start/finish line and starting grid are.
* **Set spawn** makes the selected point point 0. It needs a cyclic spline in Edit Mode.
* **Invert** reverses the spline, which reverses the direction pods race.
* **Cyclic** closes or opens the main loop. **Show direction** draws arrows along the curve.

#### Other Tips
* After selecting two points, press F ~~to pay respects~~ to join them.
