The **Collidable** part of the **Selected** panel decides whether pods collide with the selected meshes, and whether those meshes carry extra data such as surface flags, fog and load zones.

## Visible and Collidable
Every mesh has two big switches in the **Selected** panel:
- **Visible** (see [Visuals](Visuals)): the mesh is drawn in game.
- **Collidable**: pods collide with the mesh.

A mesh can be either, both or neither. Imported tracks keep them apart: each node gets a `_visuals` mesh and a `_collision` mesh. A simple, invisible collision shell under detailed scenery is the usual way to build a track.

If a mesh is **neither**, export does not drop it:
- In a track (Trak) it is exported as both visible and collidable.
- In any other model type it is exported as visible only.

Export writes this choice back onto the mesh in your scene.

When it is unticked the panel says "Pods pass through it". Use [Display](Display) in the Tools panel to show, hide or select all collision meshes at once.

## Add surface flags, fog, etc.
A collidable mesh has no extra data by default. Click **Add surface flags, fog, etc.** to give it some. This shows four sections under **Collidable**; click a section's title to open or close it:
- [Surface Flags](Surface-Flags): what the surface does to a pod (speed, grip, zero-g, lava...).
- [Fog and Skybox](Fog-and-Skybox): fog, draw distance and the skybox, set when the pod touches the mesh.
- [Pod Lighting](Pod-Lighting): how the pod is lit while on the mesh.
- [Load Zones](Load-Zones): parts of the track loaded or unloaded when the pod touches the mesh.

The **Event Triggers** section lists the trigger boxes parented to the selected meshes, and **Add event trigger** below it adds one. See [Triggers](Triggers).

The reset arrow beside **Collidable** removes all of this data (surface flags, fog, lighting and load zones) from the selected meshes. The mesh stays collidable.

## How the pod meets collision
These were measured in the game on the generated gym level, on a fully upgraded pod:
- The pod rides **5 units** above the road.
- Against walls the pod is a **sphere of radius 5**. It fits through an 11-unit slot at full speed, and its body visibly clips through the walls.
- A surface steeper than about **45.6°** from the pod's "up" counts as a wall.
- Slopes up to 20° cost no speed. Steeper ramps still climb but lose speed (about 390 at 25°, 230 at 40°).
- A sudden 45° kink from flat road at cruising speed crashes the pod.
- The pod counts as airborne when it is more than **30 units** above the ground.

## Limits and gotchas
- **Triggers work only on the mesh they are parented to.** The game checks only the triggers of the collision mesh under the pod.
- **Moving collision needs Full Raycast.** The pod's ground ray normally uses the track as it was cached at load. Without **Full Raycast** (on the [Surface Flags](Surface-Flags) panel), an animated platform's visual moves, but the pod rides where the platform was at load.
- Vertices are stored as whole game units (int16). Keep geometry within ±32767 of its node.
- A collidable mesh with no faces is skipped on export.
