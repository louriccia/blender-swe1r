The **Light** panel sets a Blender light's color and whether it exports as a light streak. It appears when the active object is a light.

## Color
The light's color, the same setting as in Blender's Light properties. It is used in two places:
- **[Bake](Vertex-Colors)** adds point and sun lights to the vertex colors in this color.
- A light chosen in **[Pod Lighting](Pod-Lighting)** is exported with this color, as the light that lights the pod on that surface.

A light that is used for neither does nothing in game, except as a light streak.

## Light Streak
On: the light's position is exported as a light streak (an `LStr` entry in the track's data). The game draws a light streak sprite on screen at each of these points.

Only the position is exported. The light's color, type and power are ignored for streaks.

Ticking it on one light applies it to every selected light.

Importing a track with light streaks adds one point light named `lightstreak` for each, with Light Streak on.

## Limits
- Tracks only. Light streaks in any other model type are not exported.
- The game's light streak table holds 40 positions; more than 40 is untested.
- A light streak light is still a point light in Blender, so [Bake](Vertex-Colors) counts it. If you don't want it in the vertex colors, bake before adding it, or make it a spot or area light: Bake ignores those, and the streak only uses the position.

Pod lights are set on the collision mesh, not here: see **Mesh > Collision > [Pod Lighting](Pod-Lighting)**.
