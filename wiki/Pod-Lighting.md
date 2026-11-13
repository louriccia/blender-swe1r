The **Pod Lighting** panel sets the light that shines on the pod while it is on the selected collision meshes.

The panel appears once a mesh is **Collidable** and has data added (see [Collision](Collision)). It lights the pod, not the track: track geometry with baked vertex colors isn't lit by the game. To shade the track, use [Vertex Colors](Vertex-Colors). Bake leaves the light picked here out unless its **Include Pod Lights** is on.

## Light
Pick a Blender light in the box at the top. Choosing a light is what switches the lighting on. Without one, the game ignores the mesh's lighting (unless one of the buttons below is on).

The light's type decides how the game uses it:
- **Sun:** the game lights the pod from a fixed direction, the way the sun shines (its arrow in the viewport). Its position doesn't matter.
- **Point** (or spot or area): the game lights the pod from the light's **world position**. Every frame it aims the light from that point toward the pod, so the light's side changes as the pod passes it. Picking one of these turns **Point** on.

On export the add-on takes the light's **color**, plus the sun's direction or the light's position. Nothing else is used: strength, radius and the spot or area shape are ignored.

Importing a track creates a light named `pod_lighting` for each light it finds: a point light for surfaces with the Point flag, a sun for the rest. One light is shared between meshes that use the same color and position or direction.

## Ambient Color
**Ambient Color** is the pod's ambient (fill) light while it is on the mesh. It is only used when the lighting is on (see **Light** above).

## Flicker, Point, Persist
These three toggles set light flag bits:
- **Point** (0x4): set from the light's type. With a sun the toggle is replaced by a greyed **Sun** label, and the flag is never written. With another light it is on when picked. If you turn it off, the game uses the light's position as a direction instead: the light travels from the world origin toward the light's position, so it comes from the opposite side.
- **Flicker** (0x8): the light's brightness pulses as the pod moves along the **Flicker Axis**: full, fading to off and back to full every 100 game units of the pod's position along the axis. Only the light color pulses, not the ambient color. The axis shows under the toggles while Flicker is on. The game normalizes it, so only its direction counts. Stock tracks use axes such as (0, 1, 0), (-1, 0, 0) and (1, -1, 0); new meshes start at (0, 1, 0).
- **Persist** (0x10): the light also becomes the game's base light. When the pod later moves onto a mesh without lighting data, the game returns to the last **Persist** light. A light without **Persist** applies only until the pod moves to another mesh.

The reset arrow in the section's title row clears the light, the ambient color and the three toggles on the selected meshes.

## Limits and gotchas
- The light settings change when the pod moves onto a mesh with different collision data. With a point light, the direction it comes from also follows the pod every frame.
- To keep a lighting change for a whole area, either tick **Persist**, or give every mesh in the area the same light.
