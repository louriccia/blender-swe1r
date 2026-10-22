The **Material** panel sets the selected meshes' texture and how the game draws it: color, culling, transparency, scrolling, mirroring and clipping.

It is under **Mesh > Visuals** and only shows while **Visible** is on. Changes apply to the first material of every selected mesh.

## Before the settings
- **One material per mesh: export splits it.** A selected mesh has more than one material. Export will split it into one mesh per material. **Split mesh by material** does that now for the active mesh.
- **Add material.** A selected mesh has no material. This gives it a game material.

## Color
The material's primitive color. It only has an effect when the material's color combiner uses it:
- **Materials the add-on makes** (Add material, or a mesh with no imported material) draw texture × vertex color, so Color does nothing.
- **Imported materials** keep their combiner. Some use the primitive color, some don't.

The viewport follows the combiner. If changing Color changes nothing in Material Preview, it changes nothing in game either.

## Backface Culling
On: faces seen from behind are not drawn. Off: faces are drawn from both sides. Materials made by **Add material** start with it on.

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

## Transparent
On: the mesh is blended with what is behind it, using its alpha. For a material the add-on makes, the alpha is the texture's alpha × the vertex color alpha.

Off: alpha is ignored and the mesh is opaque. Imported cutout materials are the exception: they still drop pixels under half alpha with Transparent off.

## Scroll
Animates the texture sliding across the mesh, per axis (**x**, **y**). The value is the seconds one full scroll takes. A negative value scrolls the other way; 0 is no scroll.

Export writes a scroll for each axis that is set. The viewport preview animates only **x** when both are set.

## Mirror
Repeats the texture mirrored, along **x** or **y**, instead of tiling it.

## Clip
Stops the texture repeating along **x** or **y**: beyond the edge of the texture, its edge pixels are stretched.

## Reset
The arrow in the panel header resets Backface Culling, Transparent, Scroll, Mirror and Clip on the selected meshes. It leaves the texture and Color alone, and turns Backface Culling off.

## Gotchas
- New textures may need a game restart to show.
- Mirror, Clip and Scroll work in UV space: x is the texture's horizontal (U) axis, y its vertical (V) axis.
