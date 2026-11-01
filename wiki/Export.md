Exporting writes a model collection back into the game's `.bin` files, replacing one of the game's models.

1. Click the model's collection in the Outliner, or any object inside it. The panel shows which collection it will export.
2. Pick the export folder. It must already hold the game's `.bin` files: export replaces one model in them and leaves the rest alone.
3. **Replaces** is the game model the collection is written over. For a pod made with **New**, a **Pod Parts** checklist shows what each part will export and stops export when the pod has no engine or has meshes outside its part collections; see [Tools](Tools#pod-parts-checklist).
4. Choose what to write: **Model** (`out_modelblock.bin`), **Texture** (`out_textureblock.bin`) and **Spline** (`out_splineblock.bin`). Textures are only written together with the model, so **Texture** needs **Model** on. **Spline** needs the track's curve object directly in the collection and a track in **Replaces**; see [Splines](Splines). When something you turned on can't be written, the message at the end of the export says why.
5. Click **Export**.

The first time a `.bin` file is overwritten, the add-on saves the original next to it as `.bin.bak`.

## What export changes in your scene
To write the game's format, export splits meshes that have more than one material, applies scale and triangulates. Undo with **Ctrl+Z** if you want the scene back as it was.

## Extra files
- **Save copy to individual .bin file(s)**: also writes the exported model and spline to their own files. Textures are not saved separately.
- **Write model debug dump (.txt)**: a readable dump of the exported model, for troubleshooting.
