The **Material** panel sets the selected meshes' texture and how the game draws it: blend mode, color, culling, scrolling, mirroring and clipping.

It is a section under **Visible** in the **Selected** panel and only shows while **Visible** is on. Changes apply to the first material of every selected mesh.

## Before the settings
- **One material per mesh: export splits it.** A selected mesh has more than one material. Export will split it into one mesh per material. **Split mesh by material** does that now for the active mesh.
- **Add material.** A selected mesh has no material. This gives it a game material.

## Blend
How the game draws the material. Each choice is a whole setup copied from the game's own materials, so it is one the game's renderer accepts. Between them they cover 98% of the stock materials.

| Blend | Looks like | Color | Stock examples |
|---|---|---|---|
| **Opaque** | Solid: texture × vertex color (or the game's lighting on lit meshes) | not used | track surfaces, most props |
| **Tinted** | Solid, multiplied by **Color** | tints | pods, characters, scenery |
| **Cutout** | Hard-edged holes where the texture's alpha is under half | not used | fences, foliage |
| **Translucent** | Blends the texture's alpha with what is behind it | not used | ice, water |
| **Glow** | See-through and double-sided, tinted by **Color** | tints; its alpha is the opacity | energy binders, engine flames |
| **Flat Color** | **Color** × vertex color; the texture is ignored | is the color | |
| **Shadow** | **Color**, shown where the texture is transparent | is the shadow; its alpha is the darkness | pod shadows |
| **Custom** | An imported setup none of the above matches | depends | pod shadows, engine glow, overlays |

- New materials are **Opaque**. Imported materials show the blend their stored setup matches, or **Custom**.
- Picking a blend replaces the material's whole draw setup. A **Custom** material is never changed unless you pick something else, so imported materials export exactly as they came in.
- Choosing **Tinted**, **Glow** or **Flat Color** on a material whose Color is black sets it to white, so it doesn't vanish. **Glow** and **Shadow** also set Hide to **Off**, as stock glow and shadow materials have it.
- There is no additive blend: the game's renderer has no such mode.
- **Translucent** meshes are sorted back to front by the centre of their bounding box, so large or intersecting translucent meshes can sort wrongly. Split them up if they flicker.
- Meshes in a **Skybox** collection are always drawn as sky (no depth test, no fog), so the panel shows that instead of the dropdown.

## Color
The material's primitive color. It only matters for **Tinted**, **Glow**, **Flat Color**, **Shadow** and some **Custom** materials, so it is greyed out for the others. The viewport follows the material's color setup: if changing Color changes nothing in Material Preview, it changes nothing in game either.

## Hide (culling)
Which side of the faces the game doesn't draw:
- **Back Faces**: faces seen from behind (most stock meshes). Materials made by **Add material** start with it. Blender's viewport hides them too.
- **Front Faces**: faces seen from the front. Stock uses it on mirrored copies of meshes, whose faces are wound the other way. Blender can't hide front faces, so the viewport shows them double-sided.
- **Off**: both sides are drawn.

## Texture
The image the mesh is drawn with. Pick an image already in the file, or click the folder button to load one from disk.

On export (with **Texture** on in [Export](Export)):
- An image the importer made, still unchanged, is written as a reference to the game's own texture, not copied.
- A new or edited image is added as a new texture. Only about 52 new textures fit: the add-on stops at 1700 and the stock game has 1648.
- Images larger than 128×128 are scaled down to fit, keeping their shape. Each side is then resized, with filtering, up to a power of two, not padded: a 100×40 image becomes 128×64. The resize also changes the image in your Blender file.
- The add-on picks the game format from the image's content:

  | Image | Format |
  |---|---|
  | Greys only, opaque | I4 (16 levels) or I8 |
  | Any partly transparent pixel | RGBA32 |
  | Up to 16 colors | CI4 |
  | 17 to 255 colors | CI8 |
  | More than 255 colors | CI8, keeping the 255 most used colors |

  Palette (CI) colors are stored at 5 bits per channel with on/off alpha, so subtle gradients band.

The rest of the panel only shows once the mesh has a texture.

## Scroll
Animates the texture sliding across the mesh, per axis (**x**, **y**). The value is the seconds one full scroll takes. A negative value scrolls the other way; 0 is no scroll.

Export writes a scroll for each axis that is set. The viewport preview animates only **x** when both are set.

## Mirror
Repeats the texture mirrored, along **x** or **y**, instead of tiling it.

## Clip
Stops the texture repeating along **x** or **y**: beyond the edge of the texture, its edge pixels are stretched.

## Reset
The reset arrow in the section's title row sets the blend to **Opaque** and sets Hide to **Off** and resets Scroll, Mirror and Clip on the selected meshes. It leaves the texture and Color alone.

## Gotchas
- New textures may need a game restart to show.
- Mirror, Clip and Scroll work in UV space: x is the texture's horizontal (U) axis, y its vertical (V) axis.
