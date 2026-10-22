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

"""Event trigger types: what each does in game. Names follow SW_RACER_RE src/types_enums.h
(swrModel_TriggerType); behaviour is as the museum_triggers level measured it (levels/README.md)
unless marked untested. No bpy, so tests can read it."""

# Planets that load each trigger effect slot (swrObjTrig_LoadAndInitializeTriggerModels 0x47ddc0).
# A type that shows an effect crashes on a planet that doesn't load its slot.
EFFECT_SLOT_PLANETS = {
    0: ["Tatooine", "Ando Prime", "Aquilaris", "Baroonda", "Mon Gazza", "Oovo IV", "Malastare"],
    1: ["Tatooine", "Ando Prime", "Aquilaris", "Baroonda"],
    3: ["Ando Prime", "Baroonda"],
    5: ["Baroonda"],
}

# id: (name, what it does, needs a target, effect slot or None, fires: "once" / "every frame" / None)
TRIGGER_TYPES = {
    0: ("None", "Does nothing", False, None, "every frame"),
    100: ("Ice", "Breaks the target. The game adds >150 Speed at load", True, None, "once"),
    101: ("Door", "Plays the target's animation, reversing direction each time", True, None, "every frame"),
    102: ("Asteroid", "Breaks the target. Fires on crossing the trigger's plane, not on entering the box", True, None, "once"),
    103: ("Tent", "Hides the target", True, None, "once"),
    104: ("Binder", "Explodes the pod. Fires on crossing the trigger's plane", False, None, "once"),
    105: ("Glacier", "Starts the target's animation and shakes the camera. The game adds Ignore AI at load", True, None, "once"),
    106: ("Asteroids", "Fire effects and asteroid sounds", False, None, "every frame"),
    107: ("Red Carpet", "Does nothing (handy for testing flags)", False, None, "every frame"),
    108: ("Slalom", "Spawns a slalom flag", True, None, "once"),
    201: ("Ice 2", "Breaks the target (crash deceleration 25)", True, None, "once"),
    202: ("Rocks", "Breaks the target (crash deceleration 2.5). The game adds >150 Speed at load", True, None, "once"),
    203: ("Tuskens", "Tusken sounds and fire effects. The game adds Ignore AI at load", False, None, "every frame"),
    208: ("Balloon Spawner", "Spawns a ballooncraft (untested)", False, None, None),
    211: ("Flame Spawner", "Spawns a flame (untested)", False, None, None),
    212: ("Branches", "Breaks the target. The game adds >150 Speed at load", True, None, "once"),
    213: ("Quake Shortcut", "Removes the target, earthquake and rock. Never fires on lap 1 (the game adds Skip Lap 1 and Ignore AI at load)", True, 3, None),
    301: ("Lake Mystery", "Untested", False, None, None),
    304: ("Tram", "Starts the target's animations", True, None, "once"),
    306: ("Quake", "Earthquake. Never fires on lap 1 (the game adds Skip Lap 1 and Ignore AI at load)", True, 1, None),
    307: ("Door 2", "Loops the target's animation", True, None, "every frame"),
    308: ("Fish Spawner", "Spawns an Aquilaris fish (untested)", False, None, None),
    310: ("Dozer Spawner", "Spawns a dozer (untested)", False, None, None),
    312: ("Pillar", "Starts the target's animation and shakes the camera. The game adds Ignore AI at load", True, None, "once"),
    314: ("Methane", "Methane vapour effect at the target. The game adds Ignore AI at load", True, 0, None),
    501: ("Lava", "Lava splash", True, 5, None),
    503: ("Unknown 503", "Untested", False, None, None),
    900: ("Reset", "Puts the pod back on the spline where it is, at speed 0", False, None, "every frame"),
}

CUSTOM = -1  # the dropdown's "Other" entry: a type number not in the table


def type_label(type_id):
    entry = TRIGGER_TYPES.get(type_id)
    return f"{type_id} {entry[0]}" if entry else str(type_id)


def type_warnings(type_id):
    """Short warnings for the panel: crashes, traps, and what the type needs."""
    entry = TRIGGER_TYPES.get(type_id)
    if entry is None:
        return ["Not a known trigger type"]
    name, _, needs_target, slot, fires = entry
    out = []
    if slot is not None:
        # 501 is the one measured; for the others the museum couldn't test off-planet
        verb = "Crashes" if type_id == 501 else "Can crash"
        loaded = EFFECT_SLOT_PLANETS[slot]
        missing = [p for p in ALL_PLANETS if p not in loaded]
        out.append(f"{verb} off {' or '.join(loaded)}" if len(loaded) <= 2 else f"{verb} on {', '.join(missing)}")
        if "Ando Prime" in missing:
            out.append("Custom-folder tracks count as Ando Prime")
    if type_id == 900:
        out.append("Keep out of bounds: on the racing line it traps the pod")
    if type_id == 104:
        out.append("Explodes the pod")
    if needs_target:
        out.append("Needs a Target")
    if fires == "every frame":
        out.append("Fires every frame the pod is inside")
    return out


ALL_PLANETS = ["Tatooine", "Ando Prime", "Aquilaris", "Ord Ibanna", "Baroonda", "Mon Gazza", "Oovo IV", "Malastare"]
