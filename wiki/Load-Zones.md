The **Load Zones** panel loads and unloads parts of the track when the pod touches the selected collision meshes.

The panel appears once a mesh is **Collidable** and has data added (see [Collision](Collision)).

## Zones are view layers
A track is split into up to **24 zones**. In Blender each zone is a view layer, named `VisLayer_0` to `VisLayer_23` (the add-on creates them when it imports or creates a model). The first view layer in the scene is your working layer and is not a zone.

A mesh belongs to every zone whose view layer it is **not hidden** in. To move a mesh between zones, switch to that zone's view layer and hide or unhide the mesh there.

The game keeps a set of active zones for each pod. When the pod touches a mesh with load zone data, that mesh adds its "load" zones to the set and removes its "unload" zones.

## The zone list
The list shows the 24 zones. Click the icon next to a zone to cycle through three states:
- **dot**: unchanged. Touching the mesh leaves this zone as it is.
- **open eye**: load this zone when the pod touches the mesh.
- **closed eye**: unload this zone when the pod touches the mesh.

The click sets the state on every selected mesh. A `*` after a zone name means the selected meshes disagree on that zone.

The reset arrow in the panel header sets every zone back to unchanged on the selected meshes.

## Preview
Select a single mesh and click **Preview** to see the effect in the viewport. In the working view layer, the meshes in each zone this mesh loads are shown, and the meshes in each zone it unloads are hidden.

Preview changes what is hidden in your working layer and does not undo itself. Unhide everything (**Alt+H**) to go back.

## Limits and gotchas
- **Custom tracks loaded from a folder ignore these zones.** Every folder custom track runs as planet 1, sub-track 0. The game treats that slot specially and works out the zones from the pod's position on a grid instead. Load zones you author here do not apply there.
- Because of this, load zones have not been tested on the generated test levels yet. A track exported over a stock track in another slot should use the stored zones, but treat the details as unconfirmed.
- A mesh hidden in every zone view layer is in no zone, and the game never draws it.
- Zones change only when the pod touches a mesh that has load zone data. A mesh with every zone unchanged leaves the set alone.
