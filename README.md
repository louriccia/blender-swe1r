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

## Import a Model
1. Set the import folder by clicking the folder icon under "Import". If importing from your game files, this folder should be located at `Star Wars Episode I Racer > data > lev01`</br>This folder should contain the following files:
    * `out_modelblock.bin`
    * `out_splineblock.bin`
    * `out_spriteblock.bin`
    * `out_textureblock.bin`
  
1. Select a model from the Model dropdown. You may filter this list using the Type dropdown to filter the type of models to select from.
2. Click the Import button

## Spline Editing
* To declare the main spline, select a point on the spline and check "Cyclic U" under Object Data Properties -> Active Spline -> Cyclic
* To create an alternate path, create a new spline within the same curve object. The first and last points of the path will be merged to their closest relative points on the main spline.
* After selecting two points, press F ~~to pay respects~~ to join them.

#### Curve Tools
The Curve Tools add-on that comes with Blender (edit -> preferences -> add-ons) has two really useful buttons: 
'Set First Points' - can set the selected point as the first point in the spline and make it the start/finish line
'Switch Direction' - reverses the spline

#### Limitations
* Splines cannot split or join more than 2 times on any point.
* Splines cannot have paths that start before and end after the finish line on main spline.
* Splines cannot have paths that end at an earlier point on the main spline than the point where they begin.

## Export a Model
1. Coming soon

## Known Issues

- Nothing actually works yet

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE - see the [LICENSE.md]([link-to-license-file](https://github.com/louriccia/blender_swe1r/blob/main/LICENSE)) file for details.

Support the project by sending some truguts</br>

[![ko-fi](https://www.ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/lightningpirate)