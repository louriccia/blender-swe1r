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

bl_info = {
    "name": "SWE1R Import/Export",
    "author": "LightningPirate",
    "blender": (4, 0, 0),
    "version": (0, 9, 0),
    "location": "View3D > Tool Shelf > SWE1R Import/Export",
    "warning": "",
    "category": "Generic",
}

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
