Importing brings a model from the game's `out_modelblock.bin` into Blender, along with its textures from `out_textureblock.bin` and, for tracks, its spline from `out_splineblock.bin`.

## Import folder
Pick the game's `data/lev01` folder, or any folder holding these files:
- `out_modelblock.bin`
- `out_splineblock.bin`
- `out_textureblock.bin`

Steam: `Steam\steamapps\common\Star Wars Episode I Racer\data\lev01`
GOG: `GOG Galaxy\Games\STAR WARS Racer\data\lev01`

## Type
Filters the Model list:
- **MAlt / Podd**: the pods (high and low detail)
- **Modl**: special effects
- **Part**: props and parts
- **Pupp**: animated characters (racers, Watto, pit droids…)
- **Scen**: cutscenes (unused on PC)
- **Trak**: tracks

## Model
The model to import. With a type chosen, **All** imports every model of that type.

## What you get
Each model becomes a collection named `model_<id>_<type>`. Export uses this collection, so keep the model's objects inside it.
