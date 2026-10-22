The game builds every model from a tree of nodes. In Blender, empties are those nodes, and the **Node** panel sets what kind each one exports as. It shows for the active empty (trigger boxes and pod anchors have panels of their own).

## Type
- **Automatic** (the default for new empties): kept as a transform node when it is animated, a trigger's target or holds a header slot; otherwise merged into its parent, its transform baked into the meshes under it.
- **Group**: a plain node that draws all its children.
- **Transform**: a node with its own position, rotation and scale, kept even when nothing animates it.
- **Selector**: draws one chosen child, all of them or none (see below).
- **LOD Selector**: draws one child by distance from the camera (see below).
- **Camera-facing**: turns to face the camera, or follows the model's position.
- **Transform (no pivot)** and **Mesh Group** are imported node kinds, kept as they were.

Imported empties show the type they came in as.

## Children are ordered by name
For a Selector and an LOD Selector, which child is which matters. Export writes an empty's children in name order, and the panel lists them that way. Rename children (for example with a number prefix) to reorder them.

## Selector
**Draws child**: the number of the child to draw (0 is the first), **-1** to draw all of them, **-2** to draw none.

The game changes some stock selectors while racing (a pod's slot 0 switches between the pod and its far-away model). On a track, a selector keeps the child you set.

## LOD Selector
The first child is the most detailed. **Child 1 from**, **Child 2 from** … are where each child takes over, by distance from the camera; the first is always 0 and **-1** ends the list. A new LOD selector starts with the stock pod-part distances (0, 40, 60, 100, 1000000); stock track pieces use 0, 2000, 4000, 6000, 8000, 1000000.

**The replacement renderer always draws the first child**, so in practice the most detailed child is the one you see. Only the original renderer switches by distance.

## Camera-facing
- **Face Camera**: the node turns to face the camera (a billboard). 51 stock nodes do this.
- **Follow Model**: the node moves with the model's position. Stock sky domes and pod binders do this (28 stock nodes).

## Checked in game
On a test track, a selector set to draw child 1 showed only that child, an LOD selector showed its first child, and a camera-facing quad was drawn.
