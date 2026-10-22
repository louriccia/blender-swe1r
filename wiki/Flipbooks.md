A flipbook animates a material's texture: the game swaps it through a list of frames, like the stock lava, sparks, energy binders and the Baroonda beach.

The **Flipbook** panel is under **Mesh > Visuals > Material** and edits the active mesh's material. It starts closed.

## Frames
The list holds the frames in play order. Each frame is a Blender image.
- **Folder button**: pick one or more image files; they are added in file name order. If the material had no frames yet, its own texture becomes the first frame, so the mesh shows it before the flipbook starts.
- **+** / **−**: add an empty frame after the selected one (pick its image in the list), or remove the selected frame.
- **Arrows**: move the selected frame earlier or later.
- **X**: remove every frame. The material keeps its own texture, with no flipbook.

Frames are textures like any other: each new or edited image is added to the game's textures on export (see [Materials](Materials) for formats and sizes, and the limit of about 52 new textures in all). A frame repeated in the list is stored once.

## Frame Time and Loop
- **Frame Time**: how long each frame shows, in seconds. Stock flipbooks use 0.02 to 0.05.
- **Loop**: start over after the last frame. Off: play once and hold the last frame.

The panel shows how long one cycle takes.

## Imported flipbooks
Importing a model with a flipbook fills the list with its frames, read from the game's textures. While you leave the frames, Frame Time and Loop as they are, export writes the flipbook back exactly as it was, uneven timing included (the Baroonda beach holds some frames longer). Change any of them and export lays the frames out evenly, Frame Time apart.

## Gotchas
- Blender shows the material's own texture, not the animation.
- Only the mesh's first material is exported, so the flipbook belongs on that one.
- All frames should be the same size; the game uses each frame's own size.
