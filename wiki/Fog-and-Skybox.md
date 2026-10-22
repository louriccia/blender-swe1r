The **Fog & Skybox** panel changes the fog, the draw distance and the skybox when the pod touches the selected collision meshes.

The panel appears once a mesh is **Collidable** and has data added (see [Collision](Collision)). Changes are not tied to the mesh: they take effect when the pod moves onto it and last until another mesh changes them. A mesh with no fog settings leaves the current fog alone. The camera eases toward the new values rather than switching at once.

## Set color
Tick **Set color** and pick a color. When the pod touches the mesh, fog turns on with this color.
- The fog color is also the background color, the "sky" behind everything the game draws.
- **Set color** also applies the fog **Start** value (see below). A Start of 0 or less turns fog off instead.
- The panel greys out **Start** unless **Set range** is ticked, but the value is exported either way. To change it for **Set color** alone, tick **Set range**, edit **Start**, then untick it.

## Set range
**Set range** shows two values:
- **Start**: where the fog begins. **This is not a distance.** The game uses it as an N64-style fog value and clamps it at 996, so values above 996 all look the same. The game applies Start through **Set color**, not **Set range**.
- **Draw distance**: the far clip; nothing beyond it is drawn. Ticking **Set range** makes the game set the draw distance to this value.

## Clear Fog
**Clear Fog** writes a fog Start of 0, which turns fog off.
- It also sets the draw-distance bit, so clearing fog also resets the draw distance to the **Draw distance** value (30000 by default).
- In the decomp, the game only reads Start when the color bit is set. The tested case had **Set color** ticked as well. To be safe, tick **Set color** together with **Clear Fog**.

## Show Skybox / Hide Skybox
**Show Skybox** and **Hide Skybox** show or hide the skybox when the pod touches the mesh. Tick only one: if both are ticked, Show wins.

The reset arrow in the panel header clears all of these settings on the selected meshes.

## Limits and gotchas
- **Start is clamped at 996.** Treat it as "how much fog", not "how far away".
- Changes happen when the pod moves onto a mesh with different collision data. They do not switch back when the pod leaves, so put a mesh that restores the old fog wherever the pod exits the area.
- The slider limits (1 to 30000) are the add-on's, not the game's.
