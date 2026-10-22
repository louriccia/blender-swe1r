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

"""The wiki pages the sidebar's "?" buttons open. Each key is a page name: the file wiki/<name>.md
in this repo and the URL <URL_WIKI>/<name>. No bpy here, so tests/test_help_pages.py can check
that every page a panel links to exists."""

HELP_PAGES = {
    "Home": "Start here: what the add-on does and where to find each guide",
    "Getting-Started": "Install the add-on, find the game files, and import and export a first model",
    "Import": "Bring a model from the game's .bin files into Blender",
    "Export": "Write a model collection back into the game's .bin files",
    "Tools": "Create new models and export the material asset library",
    "Display": "Show, hide and select visual and collision meshes in the viewport",
    "Visuals": "How a mesh is drawn in game: visible meshes, vertex colors and materials",
    "Vertex-Colors": "Bake lighting into vertex colors",
    "Materials": "One material per mesh: texture, color, transparency, scroll, mirror and clip",
    "Collision": "What pods collide with, and the data a collision mesh carries",
    "Surface-Flags": "What each surface flag does to a pod",
    "Fog-and-Skybox": "Fog color, fog start, draw distance and the skybox",
    "Pod-Lighting": "The light and ambient color a pod gets on a surface",
    "Load-Zones": "Loading and unloading parts of the track as the pod moves",
    "Triggers": "Event triggers: types, flags, targets and the per-planet crash table",
    "Splines": "The racing line: start point, laps, point-to-point tracks and forks",
    "Lights": "Light streaks",
}


def help_url(base_url, page):
    return f"{base_url}/{page}"
