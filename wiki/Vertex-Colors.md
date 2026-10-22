The **Vertex Colors** panel bakes the scene's Blender lights into the selected meshes' vertex colors.

Tracks have no lighting in game: flat white geometry stays flat white. The vertex colors are the shading. For a material the add-on makes, the game multiplies the texture by the vertex color, so baked shadows darken the texture.

The panel is under **Mesh > Visuals** and only shows while **Visible** is on. It starts closed.

## Falloff
How fast point lights fade with distance. A point light's contribution is divided by the distance to the light raised to this power. 0 means no fade; the default is 1.

Distance is measured in Blender units. The add-on imports at 0.01 Blender units per game unit, so a light 10 Blender units away is 1000 game units away.

## Ambient Light
A color added to every vertex, so areas no light reaches are not black.

## Ambient Strength
Meant to scale the ambient light. **It currently has no effect**: the Ambient Light color is added at full strength. Ambient Light defaults to white, which bakes every vertex fully white. Set Ambient Light to a dark color before baking.

## Bake
Computes a color for each vertex of the selected meshes and writes it to the mesh's active color attribute. It replaces any vertex colors already there.

For each vertex it starts from Ambient Light and adds:
- **Point lights:** light color × the cosine of the angle between the vertex normal and the light, ÷ distance^Falloff.
- **Sun lights:** light color × the cosine of the angle between the vertex normal and the sun's direction. No distance fade.

A vertex gets nothing from a light that faces away from it, or when any geometry in the scene lies between it and the light (shadows).

## Reset
The arrow in the panel header sets the selected meshes' vertex colors back to white.

## Limits
- Only point and sun lights count. Spot and area lights are ignored.
- Only the light's color counts, not its power (Watts or Strength). Use the color's brightness and Falloff instead.
- Every point and sun light in the scene counts, including [light streaks](Lights) and [pod lighting](Pod-Lighting) lights.
- Colors are per vertex: each vertex gets one color on all the faces that share it.
- Results brighter than white are clipped.
- Select only Visible meshes before baking. A light, or a mesh that is not Visible, in the selection can stop the bake with an error.
- Meshes whose material uses the game's normals vertex format are lit by the game, and their vertex colors are not used.

You can also paint vertex colors by hand in Blender's Vertex Paint mode; export uses the active color attribute either way.
