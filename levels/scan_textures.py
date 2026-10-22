"""Lists every stock texture the game's models use, with the size and format their materials give it.

    blender --background --factory-startup --python levels/scan_textures.py -- <out.json>

The textureblock holds only pixels; a texture's size and format live in the material that uses it
(SW_RACER_RE src/types.h swrModel_MaterialTexture), so this imports every model and reads its
images. The zoo uses the table to show stock textures by id without re-encoding them.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import build  # noqa: E402
import lib  # noqa: E402


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    addon = build.load_addon()
    imp = lib.addon_module(addon, "swr_import")
    models = lib.addon_module(addon, "swe1r.model_list").model_list
    # the importer reads data/lev01 as given; use a copy of the stock blocks (.bak preferred)
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp()
    for name, src in lib.stock_blocks().items():
        shutil.copy(src, os.path.join(tmp, name))
    folder = tmp + os.sep
    textures = {}
    for model in models:
        index = model["index"]
        if model.get("extension") in (None, "MAlt"):
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        try:
            imp.import_model(folder, [index], lambda *a, **k: None)
        except Exception as e:  # a model the importer can't read: skip it, note it
            print(f"[scan] model {index} failed: {e}")
            continue
        for image in bpy.data.images:
            if "id" not in image:
                continue
            tid = int(image["id"])
            entry = textures.setdefault(tid, {"size": list(image.size), "format": int(image.get("format", 0)),
                                              "models": []})
            if index not in entry["models"]:
                entry["models"].append(index)
        print(f"[scan] model {index}: {len(textures)} textures so far")
    with open(out, "w") as f:
        json.dump({str(k): v for k, v in sorted(textures.items())}, f, indent=1)
    print(f"[scan] {len(textures)} textures -> {out}")


if __name__ == "__main__":
    main()
