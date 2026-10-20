"""Loads the add-on's file parsing code outside of Blender by stubbing the Blender modules."""
import importlib
import os
import sys
import types
from unittest import mock

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = "swe1r_addon"


def load_modelblock():
    for name in ["bpy", "bpy_extras", "bpy_extras.anim_utils", "bmesh", "mathutils"]:
        sys.modules.setdefault(name, mock.MagicMock())

    if PACKAGE not in sys.modules:
        # register the add-on folder as a package without running its __init__ (which registers Blender classes)
        package = types.ModuleType(PACKAGE)
        package.__path__ = [ADDON_DIR]
        sys.modules[PACKAGE] = package

    return importlib.import_module(f"{PACKAGE}.swe1r.modelblock")
