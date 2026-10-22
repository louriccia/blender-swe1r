The **Pod Lighting** panel sets the light that shines on the pod while it is on the selected collision meshes.

The panel appears once a mesh is **Collidable** and has data added (see [Collision](Collision)). It lights the pod, not the track: track geometry with baked vertex colors isn't lit by the game. To shade the track, use [Vertex Colors](Vertex-Colors).

## Light
Pick a Blender light in the box at the top. On export the add-on takes two things from it:
- its **color**, as the light color;
- its **world position**, as the light vector.

Nothing else is used: the light type, strength and rotation are ignored. Choosing a light is what switches the lighting on. Without one, the game ignores the mesh's lighting (unless one of the buttons below is on).

By default the game reads the light vector as a **direction**: it normalizes the light's location, so only the direction from the origin to the light counts, not the distance.

Importing a track creates a point light named `pod_lighting` for each light it finds, and shares one light between meshes that use the same color and position.

## Ambient Color
**Ambient Color** is the pod's ambient (fill) light while it is on the mesh. It is only used when the lighting is on (see **Light** above).

## Flicker, Point, Persist
These three toggles set light flag bits:
- **Point** (0x4): the game reads the light vector as a **position** (a point light) instead of a direction.
- **Flicker** (0x8): the game copies this bit into its lighting state. What it changes on screen is not traced in the decomp.
- **Persist** (0x10): the light also becomes the game's base light. When the pod later moves onto a mesh without lighting data, the game returns to the last **Persist** light. A light without **Persist** applies only until the pod moves to another mesh.

The reset arrow in the panel header clears the light, the ambient color and the three toggles on the selected meshes.

## Limits and gotchas
- Lighting changes when the pod moves onto a mesh with different collision data, not every frame.
- To keep a lighting change for a whole area, either tick **Persist**, or give every mesh in the area the same light.
