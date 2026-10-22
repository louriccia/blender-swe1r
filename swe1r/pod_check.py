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

"""What a pod template (Tools > New > Podd) will export, checked before export: the Export panel
lists it part by part and Model.unmake refuses to write a pod with an error, so a pod built wrong
fails up front with a reason instead of exporting with parts missing.

A template's parts are its child collections by collection_type (Model.unmake writes each into
its header slots). Meshes anywhere else are not written, and a missing engine is made by mirroring
the other one (the game draws the left engine at the right one's anchor with x negated,
pod_visual.py)."""

import mathutils

from .pod_visual import pod_anchor_positions

# collection_type: (name, anchor its meshes are sorted to)
POD_PARTS = {
    '2': ("Right Engine", 'engine_r'),
    '3': ("Left Engine", 'engine_l'),
    '4': ("Cockpit", 'cockpit'),
    '5': ("Cable", None),
    '6': ("Jet Trails", None),
    '7': ("Shadows", None),
    '8': ("Engine Glow", None),
}

# Blender's x mirror: the left engine's anchor is the right one's with x negated
MIRROR_X = mathutils.Matrix.Scale(-1, 4, (1, 0, 0))


def all_objects(collection):
    objects = set(collection.objects)
    for child in collection.children:
        objects.update(all_objects(child))
    return objects


def part_collection(collection, collection_type):
    return next((c for c in collection.children if c.collection_type == collection_type), None)


def part_meshes(collection):
    """{collection_type: [meshes]} for each part collection there is."""
    return {child.collection_type: [obj for obj in all_objects(child) if obj.type == 'MESH']
            for child in collection.children if child.collection_type in POD_PARTS}


def loose_meshes(collection):
    """Meshes in the template that are in no part collection, so would not be exported."""
    inside = set()
    for child in collection.children:
        if child.collection_type in POD_PARTS:
            inside.update(all_objects(child))
    return sorted((obj for obj in all_objects(collection) if obj.type == 'MESH' and obj not in inside), key = lambda obj: obj.name)


def mirrored_engine(parts):
    """'engine_l' when Left Engine has no meshes and is made from Right Engine's, 'engine_r' the
    other way round, else None."""
    right, left = len(parts.get('2', [])), len(parts.get('3', []))
    if right and not left:
        return 'engine_l'
    if left and not right:
        return 'engine_r'
    return None


def is_pod_template(collection):
    """A Podd collection export writes from its part collections (not an imported pod's node tree)."""
    if collection is None or collection.export_type != '4':
        return False
    from .modelblock import get_imported_podd_root
    return get_imported_podd_root(collection) is None


def pod_report(collection):
    """[(status, part, text)] for a pod template, status one of 'OK', 'INFO', 'WARNING', 'ERROR'.
    Export refuses while there is an 'ERROR'."""
    parts = part_meshes(collection)
    mirror = mirrored_engine(parts)
    rows = []

    def count(n):
        return f"{n} mesh" + ("" if n == 1 else "es")

    for collection_type in ('2', '3'):
        name, key = POD_PARTS[collection_type]
        n = len(parts.get(collection_type, []))
        if n:
            rows.append(('OK', name, count(n)))
        elif mirror == key:
            other = POD_PARTS['3' if collection_type == '2' else '2'][0]
            rows.append(('INFO', name, f"mirrors {other}"))
        else:
            rows.append(('ERROR', name, "empty"))
    n = len(parts.get('4', []))
    rows.append(('OK', "Cockpit", count(n)) if n else ('WARNING', "Cockpit", "empty: none drawn"))
    for collection_type, missing in (('5', "none"), ('8', "none")):
        name = POD_PARTS[collection_type][0]
        if collection_type not in parts:
            rows.append(('INFO', name, missing))
        else:
            rows.append(('INFO', name, "stock shape"))
    for collection_type in ('6', '7'):
        name = POD_PARTS[collection_type][0]
        n = len(parts.get(collection_type, []))
        if n:
            rows.append(('OK', name, count(n)))
    loose = loose_meshes(collection)
    if loose:
        rows.append(('ERROR', "Not in a part", count(len(loose))))
    if pod_anchor_positions(collection.export_model) is None:
        rows.append(('WARNING', "Positions", "unknown for this pod"))
    return rows


def pod_errors(collection):
    """Why export would write this pod template wrong, or [] when it is fine."""
    errors = []
    rows = pod_report(collection)
    if any(status == 'ERROR' and part in ("Right Engine", "Left Engine") for status, part, _ in rows):
        errors.append("The pod has no engine: put the engine meshes in the Right Engine (or Left Engine) collection; the other side is mirrored from it.")
    loose = loose_meshes(collection)
    if loose:
        names = ", ".join(obj.name for obj in loose[:3]) + (", ..." if len(loose) > 3 else "")
        errors.append(f"{len(loose)} mesh(es) ({names}) are in no part collection and would not be exported: click Sort Loose Meshes in the Export panel, or move them into Right Engine, Left Engine or Cockpit.")
    return errors


def nearest_part(obj, anchors):
    """'2', '3' or '4': the engine or cockpit whose anchor is nearest the mesh's middle (seen from
    above). Without anchors, by which side of the pod it is on."""
    corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    centre = sum(corners, mathutils.Vector()) / 8
    if not anchors:
        return '2' if centre.x > 0.01 else '3' if centre.x < -0.01 else '4'
    keys = {'2': 'engine_r', '3': 'engine_l', '4': 'cockpit'}
    return min(keys, key = lambda t: (mathutils.Vector(anchors[keys[t]]).xy - centre.xy).length)
