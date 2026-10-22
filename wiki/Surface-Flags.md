The **Surface Flags** panel sets what a collision surface does to a pod while the pod is on it.

The section appears once a mesh is **Collidable** and has data added (see [Collision](Collision)). Tick any number of flags. Hover a flag for a short description. The reset arrow in its title row clears every flag on the selected meshes.

The game reads these flags from the mesh directly under the pod, every frame. Effects that "ease" move toward their target over time, so a short strip has a smaller effect than a long one.

Measured values come from the generated `museum_surfaces` level, on a fully upgraded pod that cruises at 614. Every flag bit set in Blender reaches the game exactly.

## Gameplay

| Name | Game code | Bit | What it does |
|---|---|---|---|
| **Fast** | `Fast` | 0x4 | Speed bonus that eases toward +200. Measured: +92 over the test strip. |
| **Slow** | `Slow` | 0x8 | Speed ×0.75. In zero-g it also cancels boost. |
| **Very Slow** | `Swst` | 0x10 | Speed eases toward ×0.1 and boost is cancelled. It is not a start-line marker. |
| **Slippery** | `Slip` | 0x20 | Grip ×0.2. |
| **Lava** | `Lava` | 0x2000 | Cools the engines: heat drops at 20 per second. Measured: −47 over the strip. |
| **Zero-g On** | `ZOn` | 0x1 | Turns zero-g on. It stays on after the pod leaves the surface. |
| **Zero-g Off** | `ZOff` | 0x2 | Ends zero-g. |
| **Fall** | `Fall` | 0x4000 | Respawns the pod once it is within 30 units of the surface and not airborne. |
| **No Respawn** | `NRsp` | 0x10000 | Not traced in the decomp. |

## Overrides
These are stored in a separate field of the collision data, not with the surface flags.

| Name | Bit | What it does |
|---|---|---|
| **Magnet** | 0x20 | Gravity follows the surface, so the pod sticks to walls, loops and ceilings. |
| **Full Raycast** | 0x10 | The pod's ground is tested against this mesh every frame. Normally it uses the track the game cached under the spline at load. **Needed for animated collision.** |
| **Spline Fork** | 0x8 | Marks a mesh shared between spline branches. Spline progress pauses on it. The game sets this bit itself at load, so you rarely need it. |

## Effects

| Name | Game code | Bit | What it does |
|---|---|---|---|
| **Dust** | `Dust` | 0x40 | Not traced in the decomp. |
| **Wet** | `Wet` | 0x100 | Not traced in the decomp. |
| **Swamp** | `Swmp` | 0x400 | Sets the pod's "on swamp" flag. What reads that flag is not traced. |
| **Snow** | `Snow` | 0x80 | Not traced in the decomp. |
| **No Snow** | `NSnw` | 0x800 | Not traced in the decomp. The camera code sets an internal flag while the pod is on it, but what that flag changes is not traced. |
| **Mirror** | `Mirr` | 0x1000 | The surface reflects the pod. Works only with reflections turned on in the game's video settings. |
| **Side** | `Side` | 0x20000000 | Sets the pod's "on side" flag. AI pods tilt fully onto their side while on it. |

## Feedback

| Name | Game code | Bit | What it does |
|---|---|---|---|
| **Rough** | `Ruff` | 0x200 | Not traced in the decomp. |
| **Soft** | `Soft` | 0x8000 | Sets the pod's "on soft" flag. What reads that flag is not traced. |
| **Flat (AI)** | `Flat` | 0x20000 | AI pods only. It never does anything on a human pod. |

## Limits and gotchas
- **Fall pads must be close.** Pods fall slowly, so a **Fall** pad 300 units down a pit gets flown straight over. Put it within reach of where the pod lands.
- **Zero-g needs both ends.** **Zero-g On** stays active until the pod touches a **Zero-g Off** surface.
- **Animated platforms need Full Raycast.** Without it the pod rides where the platform was when the track loaded. In the museum that was a 4-unit error on a 150-unit lift.
- The spline must sit above collision the pod can spawn on. See [Splines](Splines).
- Flags apply only while the pod is on the mesh. For one-off events (doors, explosions, resets) use [Triggers](Triggers).
