The **Tools** panel starts a new model from scratch and builds a Blender asset library of the game's materials. It also holds the [Display](Display) box.

## New
Pick a model type in the dropdown, then click **+**. The add-on adds an empty model collection named "New *Type* Model" and makes it the active collection, so new objects go into it.

| Type | What New adds |
|---|---|
| Trak (track) | **Track** and **Skybox** collections, and a `spline` curve object |
| Podd (pod) | **Right Engine**, **Left Engine**, **Cockpit**, **Cable**, **Jet Trails**, **Shadows** and **Engine Glow** collections, and anchors (see below) |
| Modl, Part, Pupp, Scen | The collection only |

The new collection replaces the first game model of its type on export. A message names that model. Change it with **Replaces** in the [Export](Export) panel.

New also adds the scene's 24 view layers if they are missing. The game's load zones are stored in them; without them a mesh exports in no zone and is never drawn.

MAlt (the high detail pod) is not in the list: it is exported with its Podd.

### Pod anchors
The game places a pod's engines, cockpit, cable, binder, exhausts and shadows itself, every frame, from a table in its executable with one row per racer. Where those parts sit in your model makes no difference: a pod that replaces Anakin's always has Anakin's engine spacing.

So a new pod gets locked empties showing where the game will draw the pod it replaces: **Anchor Engine R**, **Anchor Engine L**, **Anchor Cockpit**, arrows at **Anchor Exhaust R** and **Anchor Exhaust L** where the jet trails start, **Anchor Binder R** and **L** where the energy binder's beam ends, and **Anchor Cable Cockpit R/L** and **Anchor Cable Engine R/L** where each cable starts and ends. They move when you change **Replaces**. The binder and cable points move with their engine or cockpit in game (engine tilt, cockpit lag), so shape the engines and cockpit to meet them.

Model each part around its anchor. Export writes each part's meshes relative to their anchor, keeping their position, rotation and parenting, so what you see in Blender is what the game shows. One Blender unit in a pod is 1.6 game units.

### Jet trails and shadows
- **Jet Trails**: each mesh trails from the nearer exhaust arrow. Model a short tube pointing back (−Y) from the arrow, about half a Blender unit long, like the stock ones: the game stretches it with speed, scrolls its texture and may set its color.
- **Cable** and **Engine Glow**: the game reshapes both every frame (it stretches the cable from the cockpit to each engine and, up close, draws its own tube; it scales the glow by the pod's glow size and speed and sets its color from engine heat), so only their material is yours to choose. Put any mesh in the collection to give the cable or glow that mesh's material; leave the collection empty for the stock black cable or the stock glow; delete the collection for no cable or no glow. The glow is faint in normal driving, as on stock pods.
- **Shadows**: each mesh goes on the ground under the nearest engine or cockpit anchor; only its outline matters (it is laid flat on the ground). Give it the **Shadow** blend (see [Materials](Materials)): it draws Color where the texture is transparent, so a texture with a soft transparent blob gives the stock look. The right engine's shadow also sets how wide the pod is for collisions with other pods.

### Limits
- The new spline has a single point. A track spline needs 3 to 255 points: see [Splines](Splines).
- Pods built from the template export without LODs, animations or a far-away model, and with an empty high detail MAlt model. Imported pods export in full.
- AI racers don't draw the pod model: they use a separate low detail model (a Part), so a new pod only shows on your own racer.
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
