# Blender Add-on for Star Wars Episode I: Racer
This is a Blender add-on that allows for importing and exporting from Star Wars Episode I:Racer's .bin files. 

## Status

🚧 **Work in Progress**

This project is currently under active development. While it may be functional for some use cases, please be aware that it is not yet feature-complete, and changes may be introduced frequently. Your feedback, suggestions, and contributions are welcome!

## Features
- Import SWE1R models directly from .bin files
- Edit mesh, collision, texture, vertex color, and spline data in blender
- Export SWE1R models directly to .bin files

## Requirements
[Blender 4.0](https://www.blender.org/download/releases/4-0/)

## Installation
0. [Download the latest release](https://github.com/louriccia/blender_swe1r/releases) OR make a zip file of this repo 
1. In Blender, go to Edit -> Preferences -> Add-Ons -> Install... and select the .zip file
2. Enable the add-on by clicking the checkbox.
3. Open the tools on the right side of the 3D view (probably hidden by a small left arrow) and click the SWE1R Import/Export tab

## Importing
1. Set the import folder by clicking the folder icon under "Import". If importing from your game files, this folder should be located at `Star Wars Episode I Racer > data > lev01`</br>This folder should contain the following files:
    * `out_modelblock.bin`
    * `out_splineblock.bin`
    * `out_spriteblock.bin`
    * `out_textureblock.bin`
  
1. Select a model from the Model dropdown. You may filter this list using the Type dropdown to filter the type of models to select from.
2. Click "Import".

## Exporting
1. Set the export folder by clicking the folder icon under "Export". This folder should contain existing `.bin` files for each block. 
2. Select a collection or object within a collection. All objects within the active collection are considered for export.
3. Select which assets to export. You may select to affect the `out_modelblock.bin`, `out_textureblock.bin` or `out_splineblock.bin` by toggling the Model, Texture, and Spline buttons respectively.
4. Click "Export".

## Spline Editing
When importing a track, it should come with a spline object. This spline is from `out_splineblock.bin` and is the entity that the game uses to define the player's lap progression, start and finish line, spawn/respawn points, map display, guide arrow behavior, Zero-G mode (ZOn), and AI pathing. 
* The spline should only exist as a single spline object in Blender, in which there can be multiple paths.
* The "main spline" is the path where the start/finish line and player spawns (point 0). All other paths are considered alternate paths that branch from and rejoin the main spline.

#### Cyclic Tracks
All tracks in the game are cyclic by default, meaning their last point connects back to their first point to create a loop.
* The main spline is considered to be the only closed loop spline. To create a closed loop spline, select a point on the spline and press Alt + C or check "Cylic" under Object Data Properties -> Active Spline -> Cyclic.
* Start/Finish line and player will spawn at point 0.
* Race is finished once the player has completed the selected number of circuits.

#### Non-Cyclic Tracks (Rally)
The game also supports using a non-cyclic spline for a track. This allows us to easily create a point-to-point (rally) track.
* If no cyclic splines are found, the main spline with be the one with the most points.
* Player spawns at point 0 and the finish line spawns at the last point. 
* Race is finished once the player crosses the finish line. The race will always have 1 "lap" no matter how many laps the player has chosen.

#### Branching Paths
Some tracks feature branching paths. Blender does not support branching splines, so the first and last points of any alternate paths will be merged to the closest eligible points on any existing splines.  
To create an alternate path, create a new spline within the same curve object. This is easily done by selecting a spline point (in edit mode) and pressing Shift + D to duplicate an existing point, then pressing E to extrude. When ending the path, keep in mind that the last point you place will be replaced by the closest existing point (if it isn't already joining 4 paths).  

##### Limitations
* Splines cannot split more than 2 times on any point.
* Splines cannot join more than 4 times on any point.
* Splines cannot have paths that start before and end after the finish line on main spline.
* Splines cannot have paths that end at an earlier point on the main spline than the point where they begin.

#### Other Tips
* After selecting two points, press F ~~to pay respects~~ to join them.
* You can reverse a spline by right clicking on a point and selecting "Switch Direction"
* The Curve Tools add-on that comes with Blender (edit -> preferences -> add-ons) has two really useful buttons. 
'Set First Points' - can set the selected point as the first point in the spline and make it the start/finish line.
'Switch Direction' - reverses the spline

## Known Issues

- Nothing actually works yet

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE - see the [LICENSE.md]([link-to-license-file](https://github.com/louriccia/blender_swe1r/blob/main/LICENSE)) file for details.

Support the project by sending some truguts</br>

[![ko-fi](https://www.ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/lightningpirate)