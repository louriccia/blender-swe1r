The **Tools** panel starts a new model from scratch and builds a Blender asset library of the game's materials. It also holds the [Display](Display) panel. It starts closed.

## New
Pick a model type in the dropdown, then click **+**. The add-on adds an empty model collection named "New *Type* Model" and makes it the active collection, so new objects go into it.

| Type | What New adds |
|---|---|
| Trak (track) | **Track** and **Skybox** collections, and a `spline` curve object |
| Podd (pod) | **Right Engine**, **Left Engine**, **Cockpit** and **Cable** collections |
| Modl, Part, Pupp, Scen | The collection only |

The new collection replaces the first game model of its type on export. A message names that model. Change it with **Replaces** in the [Export](Export) panel.

New also adds the scene's 24 view layers if they are missing. The game's load zones are stored in them; without them a mesh exports in no zone and is never drawn.

MAlt (the high detail pod) is not in the list: it is exported with its Podd.

### Limits
- The new spline has a single point. A track spline needs 3 to 255 points: see [Splines](Splines).
- Pods built from the template export without LODs or animations, and with an empty high detail MAlt model. Imported pods export in full.
- New adds no meshes or materials. Model them in Blender, or append them from another file.

## Export Asset Library
Reads every model in the game and saves each distinct material as a Blender material asset. You can then drag game materials onto your meshes from Blender's Asset Browser.

Before it will run:
1. Add an asset library in **Preferences > File Paths > Asset Libraries**. The add-on uses the first one.
2. Set the game folder in the [Import](Import) panel. It must contain `out_modelblock.bin` and `out_textureblock.bin`.
3. Save your file. The button is greyed out while the file is unsaved or has unsaved changes, because the export reopens it at the end.

Click **Export Asset Library** and confirm. It takes a few minutes. When it finishes, the asset library folder holds `swe1r_materials.blend`, and your file is reopened.

The materials are in the catalog **SWE1R/Materials**. Identical materials are saved once. Each asset is tagged with the model types, model ids and names that use it, its texture id, and "textured" or "untextured", so you can search for them.

Running it again replaces `swe1r_materials.blend`.
