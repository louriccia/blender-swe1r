An event trigger is a zone on a collision mesh. When a pod enters it, the game does something: breaks a rock, opens a door, shakes the camera, explodes the pod, and so on. In Blender a trigger is a cube empty parented to the collision mesh.

## Add a trigger
1. Select the collision mesh the pods drive on (usually the road under the spot).
2. In the **Selected** panel, make sure **Collidable** is on. See [Collision](Collision).
3. Click **Add event trigger** (under the **Event Triggers** section). If the mesh had no collision data yet, this adds it.

The new trigger is a cube empty named `trigger`, parented to the mesh, at the centre of the mesh's vertices. It is 200 × 200 game units across and 100 high. Select it to see its settings in the **Selected** panel.

**Event Triggers** lists the triggers on the selected meshes, with their types.

## Where a trigger works
**A trigger only works on the mesh it is parented to.** The game only tests the triggers of the collision mesh under the pod. If the trigger sits over a different mesh, it never fires.

- Parent it directly to that mesh. The panel shows **Parent this to a collidable mesh** if its parent isn't a mesh.
- The mesh needs its collision data. **Add event trigger** adds it; a trigger parented to a mesh without it some other way is not exported.
- Export splits a mesh with more than one material into one mesh per material. The trigger stays on only one of the pieces. Give the road under a trigger a single material, or put the trigger on its own one-material mesh.

## Size and rotation
The add-on writes the trigger from the empty's world transform. 1 Blender unit is 100 game units.

- **Width** is the empty's X scale × 2. Y scale is ignored.
- **Height** is the Z scale × 2. The zone runs from half the height below the centre to half above it. Pods ride about 5 units above the road, so let the box reach above the road surface.
- **Rotation:** the empty's local X axis is the trigger's direction. Its heading (rotation around Z) is what counts: the game's zone is always upright. Rolling the cube (around local X) changes nothing in game, and tilting it (around local Y) only narrows the zone a little (by the cosine of the tilt); the panel says so. For types 102 and 104, tilting it tilts the plane the pod crosses.

The game does not test the box you see. Seen from above, the zone is a strip with rounded ends: as deep as the cube along the empty's local X axis, and twice as long along its local Y axis. Vertically it matches the cube. *(Read from the decompiled game, not measured in game.)*

Types 102 and 104 are different: they fire when the pod crosses the vertical plane through the trigger's centre, facing along local X, within the cube's width and height.

## Type
**Type** is what the trigger does. Pick it from the dropdown, or type the number in the field beside it; a number not in the list shows as **Other**. Below them the panel says what the type does and warns about crashes, traps and a missing Target. Names come from the game's code and the test track that tried each type. "Every frame" means it fires on every frame the pod is inside; "once" means it fires, then disarms itself.

| Type | Name | What it does | Target | Fires |
|---|---|---|---|---|
| 0 | none | Nothing. | | every frame |
| 100 | Ice | Breaks the target. The game adds **>150 Speed** at load. | yes | once |
| 101 | Door | Plays the target's animation, reversing direction each time. | yes, animated | every frame |
| 102 | Asteroid | Breaks the target. Fires on crossing the plane, not on entering the box. | yes | once |
| 103 | Tent | Hides the target. | yes | once |
| 104 | Binder | **Explodes the pod.** Fires on crossing the plane. | | once |
| 105 | Glacier | Starts the target's animation and shakes the camera. The game adds **Ignore AI** at load. | yes, animated | once |
| 106 | Asteroids | Fire effects. | | every frame |
| 107 | Red carpet | Nothing. Handy for testing flags. | | every frame |
| 108 | Slalom | Spawns a slalom flag. | yes | once |
| 201 | Ice | Breaks the target (crash decel 25). | yes | once |
| 202 | Rocks | Breaks the target (crash decel 2.5). The game adds **>150 Speed** at load. | yes | once |
| 203 | Tuskens | Sound and fire effects. The game adds **Ignore AI** at load. | | every frame |
| 212 | Branches | Breaks the target. The game adds **>150 Speed** at load. | yes | once |
| 213 | Quake | Removes the target, earthquake, rock. Uses effect slot 3. **Never fires on lap 1** (see below). | yes | |
| 304 | Tram | Starts the target's animations. | yes, animated | once |
| 306 | Quake | Earthquake. Uses effect slot 1. **Never fires on lap 1.** | yes | |
| 307 | Door 2 | Loops the target's animation. | yes, animated | every frame |
| 312 | Pillar | Starts the target's animation and shakes the camera. The game adds **Ignore AI** at load. | yes, animated | once |
| 314 | Methane | Methane vapour effect at the target. Uses effect slot 0. The game adds **Ignore AI** at load. | yes | |
| 501 | Lava | Lava splash. Uses effect slot 5. **Crashes the game anywhere but Baroonda.** | yes | |
| 900 | Reset | Puts the pod back on the spline where it is, at speed 0. **Keep it out of bounds** (see Gotchas). | | every frame |

"Target" says whether the in-game test gave the trigger a target object. An empty "Fires" cell means not checked.

These types appear in the game's code but were not tested, and the game's trigger handler does nothing with them directly: 208 (ballooncraft spawner), 211 (flame spawner), 301 ("lake mystery"), 308 (Aquilaris fish), 310 (dozer spawner) and 503 (unknown). They may be handled elsewhere. Unconfirmed.

### Planets and effect models
Some types show an effect model, and each planet loads its own set of them into numbered slots. A trigger whose slot the track's planet doesn't load can crash the game. **501 crashes everywhere except Baroonda.**

| Planet | Effect slots loaded |
|---|---|
| 0 Tatooine | 0 rocksmall, 1 rockbig, 2 balloon |
| 1 Ando Prime | 0 shards, 1 rockbig, 2 flag tip, 3/4 flag wave |
| 2 Aquilaris | 0 big fish, 1 rockgiant |
| 3 Ord Ibanna | none |
| 4 Baroonda | 0 treesmash, 1 rockash, 2 flame, 3 rockgiant, 5 lava |
| 5 Mon Gazza | 0 dozer, 2 flame |
| 6 Oovo IV | 0 rockzero |
| 7 Malastare | 0 methane |

Known slots: 314 uses slot 0, 306 slot 1, 213 slot 3 and 501 slot 5.

**Every track loaded from a custom track folder is planet 1 (Ando Prime).** Effects on those tracks use Ando Prime's models, and 501 crashes.

## Flags
| Flag | Bit | Behaviour |
|---|---|---|
| **Disabled** | 0x1 | The trigger is disarmed and never fires. |
| **Ignore AI** | 0x20 | Only the local player's pod fires it. AI pods don't. |
| **>150 Speed** | 0x2 | Fires only when the pod's speed is 150 or more. |
| **Skip Lap 1** | 0x4 | Doesn't fire on lap 1. |
| **Skip Lap 2** | 0x8 | Doesn't fire on lap 2. |
| **Skip Lap 3** | 0x10 | Doesn't fire on lap 3. |

The game adds some flags when it loads a track, whatever you set:
- 100, 202 and 212 get **>150 Speed**.
- 105, 203, 312 and 314 get **Ignore AI**.
- 213 and 306 get **Skip Lap 1** and **Ignore AI**, so they never fire on lap 1.

## Settings
**Settings** holds the trigger's other flag bits (bits 6–15). They have no known effect. Leave it at 0 on new triggers; imported triggers keep their value.

## Target
**Target** is the object the trigger acts on: the rock it breaks, the door it opens, the model it animates. Pick an object in the same model collection; a target outside the exported model is written as no target. Types that play an animation need a target that has one.

## Gotchas
- **900 on the racing line traps the pod.** It resets the pod onto the spline at its own position every frame, and the pod can't move. Stock tracks put it out of bounds, where only a pod that has left the track reaches it.
- **104 explodes the pod**, even on the racing line.
- **213 and 306 never fire on lap 1**, even with no flags set.
- **Types that use an effect slot can crash the game** on a planet that doesn't load that slot. Check the table above before using 213, 306, 314 or 501.
- **A trigger over the wrong mesh never fires.** If the road under the trigger is a separate mesh from its parent, move the trigger or reparent it.
