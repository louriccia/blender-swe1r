# Copyright (C) 2021-2024
# lightningpirate@gmail.com

# Created by LightningPirate

# This file is part of SWE1R Import/Export.

#     SWE1R Import/Export is free software; you can redistribute it and/or
#     modify it under the terms of the GNU General Public License
#     as published by the Free Software Foundation; either version 3
#     of the License, or (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program; if not, see <https://www.gnu.org
# /licenses>.

import os
import tomllib

# As an extension, add-on metadata lives in blender_manifest.toml rather than a
# bl_info dict. Read name/version from there so there is a single source of truth
# for the values the Info panel displays.
def _load_manifest():
    path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
    with open(path, "rb") as f:
        return tomllib.load(f)

_manifest = _load_manifest()
NAME = _manifest["name"]
VERSION = _manifest["version"]

if "bpy" in locals():
    import importlib
    importlib.reload(panels)
    importlib.reload(operators)
    importlib.reload(props)
else:
    from . import panels
    from . import operators
    from . import props

def register():
    props.register()
    operators.register()
    panels.register()
    
def unregister():
    panels.unregister()
    operators.unregister()
    props.unregister()

if __name__ == "__main__":
    register()
