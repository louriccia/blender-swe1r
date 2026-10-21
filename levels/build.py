"""Builds a generated level and exports it as a custom track folder.

    blender --background --factory-startup --python levels/build.py -- --level hello --out <dir>

<dir> gets out_modelblock/splineblock/textureblock.bin (stock blocks with the level written over
Trak model 1 and its spline 10), expectations.json, and <level>.blend for designers to open.
Copy <dir> into the game's assets/custom_tracks/ (or point the test runner's custom_tracks_dir at
its parent) to race it.
"""
import argparse
import importlib
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(HERE)
PACKAGE = "swe1r_addon"
sys.path.insert(0, HERE)


def load_addon():
    if PACKAGE in sys.modules:
        return sys.modules[PACKAGE]
    spec = importlib.util.spec_from_file_location(
        PACKAGE, os.path.join(ADDON_DIR, "__init__.py"), submodule_search_locations=[ADDON_DIR])
    package = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = package
    spec.loader.exec_module(package)
    package.register()
    return package


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--no-blend", action="store_true")
    args = parser.parse_args(argv)

    import bpy
    import lib
    addon = load_addon()
    level = importlib.import_module(f"level_{args.level}")
    model, expectations = level.build(addon)
    out = os.path.abspath(args.out)
    if not args.no_blend:
        os.makedirs(out, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, f"{args.level}.blend"), compress=True)
    lib.export_level(addon, model, out, expectations)
    if not args.no_blend:
        # export bakes scale, splits and triangulates in place; keep the authoring file as built
        pass
    print(f"[levels] built {args.level} -> {out}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
