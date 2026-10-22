The **Display** panel shows, hides and selects all visual meshes or all collision meshes at once, so you can work on one without the other in the way.

It is inside the [Tools](Tools) panel. It has a row for **Visuals** (meshes that are [Visible](Visuals)) and a row for **Collision** (meshes that are [Collidable](Collision)).

## The buttons on each row
- **Arrow (selectable):** makes every mesh of that kind selectable or unselectable in the viewport.
- **Eye (show/hide):** shows or hides every mesh of that kind in the viewport.
- **Select:** deselects everything, makes that kind selectable, then selects every mesh of that kind in the scene.

## What it does not change
These are viewing aids only. They don't change what is drawn or collided with in game, and they don't change the export.

The game's load zones are stored as Blender view layers, which export reads. The Display buttons only touch the first view layer, your working layer, which export skips. Export shows the meshes it needs while it runs, then puts your Display settings back.

## Gotchas
- A mesh that is both visible and collidable follows the **Visuals** row. Hiding Collision does not hide it.
- **Select** works on the whole scene, including other model collections, not only the model you are editing.
- The buttons work on meshes only. Splines, lights and triggers are not affected.
- "Visible" and "Collidable" are game settings, set in the [Visuals](Visuals) and [Collision](Collision) panels. The eye here is just Blender's viewport visibility.
