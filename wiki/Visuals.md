The **Visuals** panel sets whether the selected meshes are drawn in game, and holds the [Vertex Colors](Vertex-Colors) and [Materials](Materials) panels that control how they look.

It appears under **Mesh** when one or more meshes are selected. Every change applies to all selected meshes. A `*` after a label means the selected meshes have different values.

## Visible
The checkbox in the panel header. When it is on, the mesh is drawn in game. When it is off, the panel shows "Not drawn in game" and hides the Vertex Colors and Material panels.

A mesh can be visible, collidable, or both. Collision is set in the [Collision](Collision) panel. A mesh that is neither is not left out of the export:
- in a track (Trak), it exports as both visible and collidable;
- in any other model type, it exports as visible.

"Visible" here means drawn in the game. It has nothing to do with hiding objects in Blender's viewport; for that, see [Display](Display).

## How a visible mesh is coloured
For a material the add-on makes, the game draws each pixel as the **texture color times the vertex color**. With no texture, the mesh shows its vertex colors alone. Imported materials keep their own color combiner, which can also use the material's **Color**.

The viewport follows the same combiner, so what you see in Material Preview is a good guide to the game.

- [Vertex Colors](Vertex-Colors): bake Blender lights into the vertex colors. Tracks are not lit in game, so this is how a track gets shading.
- [Materials](Materials): texture, color, culling, transparency, scroll, mirror and clip.

## Reset
While a selected mesh's settings differ from the defaults, a reset arrow appears in the header. It sets the vertex colors back to white and resets the material settings (Backface Culling, Transparent, Scroll, Mirror and Clip). It leaves the texture and Color alone.

## Gotchas
- One material per mesh. A mesh with more than one material is split on export; the Material panel offers to split it now.
- Meshes whose material uses the game's normals vertex format (some imported models use it) are lit by the game, and their vertex colors are not used.
