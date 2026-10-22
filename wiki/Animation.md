The **Animation** section of the **Selected** panel shows when the active object has location, rotation or scale keys. It sets how the game plays them.

## What gets exported
Keyframe an object's **location**, **rotation** or **scale** in Blender as usual. Export turns each into one of the game's animations on that object's node:
- Linear location, scale and quaternion curves are written key for key: the game interpolates them the same way.
- Anything else (eased or stepped keys, Euler or axis-angle rotation, curve modifiers other than Cycles) is sampled and written as extra keys, close enough that the game follows Blender's curve.
- An animation with a single key gets a second, identical one, which the game needs.

Material animations are set elsewhere: texture scrolling in [Materials](Materials), and frame-by-frame textures in [Flipbooks](Flipbooks).

## When it plays
- **Tracks** play their animations by themselves, from the start of the race, as authored (the test track's lift rises at exactly the speed it was keyed at).
- **Other models** play when the game starts them: a pod's parts, a character's moves, or a track object whose [trigger](Triggers) starts its animation (types 101, 105, 304, 307, 312).

## Loop
On: the animation starts over when it reaches its end. Off: it plays once and holds its last pose.

Loop is stored as Cycles modifiers on the object's curves: turning it on or off adds or removes them, so Blender's timeline plays the animation the way the game will. New keys start with Loop off; adding a Cycles modifier yourself turns it on.

## Smooth Wrap
With Loop on, blend back to the start instead of jumping to it. **Leave it off: set in a file, it freezes the animation at its first loop.** The blend's speed only comes from the game's own code (`swrModel_AnimationsSetSettings`, which turns the flag off when it has no speed). Loading a model sets the speed to 0, so the first wrap divides by zero. In the museum, a lift with Smooth Wrap stood still. No stock animation uses it; it's kept so imports round-trip.

## Loop Length
Seconds before the animation starts over. **0** means right after its last key, and a length shorter than the keys is raised to that. A longer length holds the last pose until then: stock characters give every limb the same length so they stay in step even when one limb's keys end early.

Blender's Cycles modifier loops at the last key, not at a Loop Length. So when the Loop Length runs past the keys, the add-on puts a key at the Loop Length that repeats the last pose: Blender then holds and loops the way the game does, and a puppet's limbs stay in step in the timeline too. The key moves when you change Loop Length, goes when you turn Loop off, and isn't exported. The panel's key range leaves it out.

## Imported animations
Import sets Loop, Smooth Wrap and Loop Length from the game's own values. Left as they are, the animation exports exactly as it came in.

## Gotchas
- **Moving collision needs Full Raycast.** A collidable mesh that moves must have the **Full Raycast** surface flag ([Surface Flags](Surface-Flags)), or the pod rides where the mesh was when the track loaded.
- **Don't drop a platform faster than a pod falls** (a pod falls about 230 units in its first 1.8 s off a lip). A platform dropping at 150/s left the pod in the air above it. When the platform turned and came back up, it passed the pod before the pod landed. The game finds the ground only below the pod, so the pod fell through. Slow the drop, or add keys that slow the platform before it turns.
- Imported pivots are kept as a pair of helper empties above and below the node. Keyframe the node itself, not the helpers: export stops with an error if a helper is animated.
