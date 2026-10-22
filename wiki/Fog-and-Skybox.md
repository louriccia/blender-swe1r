The **Fog & Skybox** panel changes the fog, the draw distance and the skybox when the pod touches the selected collision meshes.

The panel appears once a mesh is **Collidable** and has data added (see [Collision](Collision)). Changes are not tied to the mesh: they take effect when the pod moves onto it and last until another mesh changes them. A mesh with no fog settings leaves the current fog alone. The camera eases toward the new values rather than switching at once.

## Set fog
Tick **Set fog**, then pick the fog **color** and **Start**. When the pod touches the mesh, fog turns on with them.
- The fog color is also the background color, the "sky" behind everything the game draws.
- **Start** is where the fog begins. **It is not a distance**: the game uses it as an N64-style fog value and clamps it at 996, so values above 996 all look the same.

## Set draw
Tick **Set draw** and set **Distance**: the far clip. Nothing beyond it is drawn. The game sets the draw distance to this value when the pod touches the mesh. It is independent of the fog.

## Clear Fog
**Clear Fog** turns fog off when the pod touches the mesh. It writes the fog with a Start of 0, which is how the game turns fog off, so the fog color and Start are greyed out while it is ticked. It doesn't change the draw distance; use **Set draw** for that.

## Show Skybox / Hide Skybox
**Show Skybox** and **Hide Skybox** show or hide the skybox when the pod touches the mesh. Tick only one: if both are ticked, Show wins.

The reset arrow in the panel header clears all of these settings on the selected meshes.

## Limits and gotchas
- **Start is clamped at 996.** Treat it as "how much fog", not "how far away".
- In the game's data, **Set fog** is flag 0x1 (color and Start; a Start of 0 or less turns fog off) and **Set draw** is flag 0x2 (draw distance).
- Changes happen when the pod moves onto a mesh with different collision data. They do not switch back when the pod leaves, so put a mesh that restores the old fog wherever the pod exits the area.
- The slider limits (1 to 30000) are the add-on's, not the game's.
