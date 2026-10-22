The **Vertex Colors** panel bakes the scene's Blender lights into the selected meshes' vertex colors.

Tracks have no lighting in game: flat white geometry stays flat white. The vertex colors are the shading. For a material the add-on makes, the game multiplies the texture by the vertex color, so baked shadows darken the texture.

It is a section under **Visible** in the **Selected** panel and only shows while **Visible** is on. Click its title to open it.

## Falloff
How fast point lights fade with distance. A point light's contribution is divided by the distance to the light raised to this power. 0 means no fade; the default is 1.

Distance is measured in Blender units. The add-on imports at 0.01 Blender units per game unit, so a light 10 Blender units away is 1000 game units away.

## Ambient Light
A color added to every vertex, so areas no light reaches are not black.

## Ambient Strength
Scales the ambient light: each vertex starts from **Ambient Light** × **Ambient Strength**. The default, 0.1, keeps unlit areas dark but not black.

## Bake
Computes a color for each vertex of the selected meshes and writes it to the mesh's active color attribute. It replaces any vertex colors already there.

For each vertex it starts from Ambient Light and adds:
- **Point lights:** light color × the cosine of the angle between the vertex normal and the light, ÷ distance^Falloff.
- **Sun lights:** light color × the cosine of the angle between the vertex normal and the sun's direction. No distance fade.

A vertex gets nothing from a light that faces away from it, or when a **Visible** mesh lies between it and the light (shadows). Collision-only meshes don't cast shadows, since the game doesn't draw them.

## Reset
The reset arrow in the section's title row sets the selected meshes' vertex colors back to white.

## Limits
- Only point and sun lights count. Spot and area lights are ignored.
- Only the light's color counts, not its power (Watts or Strength). Use the color's brightness and Falloff instead.
- Every point and sun light in the scene counts, including [light streaks](Lights) and [pod lighting](Pod-Lighting) lights.
- Colors are per vertex: each vertex gets one color on all the faces that share it.
- Results brighter than white are clipped.
- Only Visible meshes are baked. Other selected objects are skipped.
- Meshes whose material uses the game's normals vertex format are lit by the game, and their vertex colors are not used.

You can also paint vertex colors by hand in Blender's Vertex Paint mode; export uses the active color attribute either way.
