The **Vertex Colors** panel bakes the scene's Blender lights into the selected meshes' vertex colors.

Tracks have no lighting in game: flat white geometry stays flat white. The vertex colors are the shading. For a material the add-on makes, the game multiplies the texture by the vertex color, so baked shadows darken the texture.

It is a section under **Visible** in the **Selected** panel and only shows while **Visible** is on. Click its title to open it.

The section has two parts:
- **Selected meshes:** **Cast Shadows** and **Skip in Bake**, saved on each mesh.
- **Bake settings (whole scene):** Method, Samples or Falloff, Include Pod Lights and Ambient Light, shared by every bake, then the **Bake** button.

## Cast Shadows
Whether the selected meshes block light when baking. Turn it off for glass, decals, light beams, thin overlays and anything else that shouldn't throw a shadow. It is Blender's own **Object > Visibility > Shadow** setting, so both bake methods and Cycles renders use it.

These never cast shadows, whatever the setting:
- meshes that aren't **Visible** (collision-only meshes), since the game doesn't draw them;
- meshes in a **Skybox** collection, so a sky dome doesn't shadow the whole track. With only skybox meshes selected, the section shows this note instead of the two checkboxes.

## Skip in Bake (keep colors)
Bake leaves the selected meshes' vertex colors as they are, even when they are selected. Use it for meshes you painted by hand, glowing signs and lamps that should stay bright, or anything else you want to keep when you select the whole track and bake. The setting is saved with the mesh.

A skipped mesh still casts shadows unless **Cast Shadows** is off. The reset arrow (see **Reset**) still resets it.

## Method
- **Simple** (the default) is fast. It adds up point and sun lights by color, with hard shadows: each vertex is either lit or not by each light.
- **Cycles** ray traces the lighting with Blender's Cycles renderer. It is slower, but it gives:
  - soft shadows and bounce light;
  - every light type (point, sun, spot, area), using its **Power** or **Strength**;
  - light from glowing materials: a material with **Emission** set in the [Material](Materials#emission-cycles-bake) panel lights the surfaces around it in its own color;
  - light through transparent and cutout materials, by their alpha.

  Cycles bakes each face corner, so a vertex can be lighter on one face than another.

## Samples
**Cycles only.** How many rays each vertex color averages. More is smoother and slower. The default is 128. Raise it if the result looks speckled.

## Falloff
**Simple only.** How fast point lights fade with distance. A point light's contribution is divided by the distance to the light raised to this power. 0 means no fade; the default is 1.

Distance is measured in Blender units. The add-on imports at 0.01 Blender units per game unit, so a light 10 Blender units away is 1000 game units away.

Cycles uses real falloff (the inverse square of the distance) and the light's Power instead.

## Include Pod Lights
Off by default. The lights picked as [Pod Lighting](Pod-Lighting) on collision meshes (the `pod_lighting` lights an import makes) hold the direction of the light on the pod. They are not track lights, so Bake leaves them out unless this is on.

## Ambient Light
A color added to every vertex, so areas no light reaches are not black.

## Ambient Strength
Scales the ambient light: each vertex starts from **Ambient Light** × **Ambient Strength**. The default, 0.1, keeps unlit areas dark but not black.

## Bake
Computes a color for each vertex of the selected meshes and writes it to the mesh's active color attribute. It replaces any vertex colors already there.

With **Simple**, each vertex starts from Ambient Light and adds:
- **Point lights:** light color × the cosine of the angle between the vertex normal and the light, ÷ distance^Falloff.
- **Sun lights:** light color × the cosine of the angle between the vertex normal and the sun's direction. No distance fade.

A vertex gets nothing from a light that faces away from it, or when a mesh that casts shadows (see **Cast Shadows**) lies between it and the light.

With **Cycles**, each corner gets the light Cycles computes, plus Ambient Light. A Sun of **Strength** 1 shining straight onto a surface gives full white, like a white sun in Simple. Point, spot and area lights need a high **Power** at track scale (try thousands of Watts). The scene's World is left out; Ambient Light stands in for it. Lights disabled in renders (the camera icon in the Outliner) are left out.

## Stock sun
Importing a track recreates the sun its stock vertex colors were baked with, as a Sun light named `stock sun`, and sets **Ambient Light** and **Ambient Strength** to match. A **Simple** bake then comes close to the stock shading without any setup.

How it works:
- The stock bakes are sun shading without cast shadows: each vertex is brighter the more it faces the sun. On top of that the original artists adjusted whole meshes and painted vertices by hand, which no light can recreate.
- The sun's direction comes from the track's [pod lights](Pod-Lighting). Outdoor tracks light the pod from a point outside the track, and the direction to that point is the stock bake's sun (exactly on The Boonta Classic, within about 15° on the Boonta Training Course, Aquilaris and Ando Prime).
- The sun's color and the ambient light are fitted to the stock vertex colors.
- The sun's **Cast Shadows (bake)** is off, like the stock bake. Turn it on if you want your additions to cast shadows.
- A sun is only made when it explains at least 10% of the stock brightness variation. Tracks lit another way, such as Mon Gazza Speedway's tinted floodlights, get none (the import's console output says why).

How close it gets: a Simple bake with the stock sun explains about 20-50% of the stock brightness variation (The Boonta Training Course 51%, The Boonta Classic 36%, Ando Prime 21%, Aquilaris 20%), with the same average brightness. The rest is the hand work. Baking a stock area replaces that hand work, so bake only the meshes you changed or added.

Importing two tracks into one scene makes a sun for each, and every light counts in a bake: hide the other track's sun from renders (the camera icon in the Outliner) before baking.

## Reset
The reset arrow in the section's title row sets the selected meshes' vertex colors back to white.

## Limits
- **Simple** uses only point and sun lights, and only the light's color, not its power (Watts or Strength). Use the color's brightness and Falloff instead.
- Every light in the scene counts (except pod lights, see above), including [light streaks](Lights).
- With **Simple**, colors are per vertex: each vertex gets one color on all the faces that share it.
- Results brighter than white are clipped.
- Only Visible meshes are baked. Other selected objects are skipped.
- Meshes in a **Skybox** collection, and meshes with **Skip in Bake** on, are never baked, so you can select the whole track and bake without changing them.
- Meshes with **Lit by game** on (see [Materials](Materials#lit-by-game)) are lit by the game: their vertex colors hold normals, so Bake and Reset skip them.
- The original game's light setup isn't in the track data. The stock sun (above) recovers its main light, but not the hand adjustments, so a re-bake won't match the stock look exactly.

You can also paint vertex colors by hand in Blender's Vertex Paint mode; export uses the active color attribute either way.
