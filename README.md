# Blender Add-on for Star Wars Episode I: Racer
This is a Blender add-on that allows for importing and exporting from Star Wars Episode I: Racer's .bin files. 

## Status

🚧 **Work in Progress**

This project is currently under active development. While it may be functional for some use cases, please be aware that it is not yet feature-complete, and changes may be introduced frequently. Your feedback, suggestions, and contributions are welcome!

## Features
- Import SWE1R models directly from .bin files
- Edit mesh, collision, texture, vertex color, animation and spline data in blender
- Export SWE1R models directly to .bin files

## Requirements
[Blender 5.0](https://www.blender.org/download/) or newer

## Installation

This add-on ships as a Blender **extension**. Installing it from the extension repository is recommended, since that lets Blender update it for you automatically.

1. In Blender, go to **Edit → Preferences → Get Extensions**.
2. Click the **▼** dropdown in the top-right and choose **Add Remote Repository…**.
3. Paste this URL, tick **Check for Updates on Startup**, then click **Create**:
   ```
   https://louriccia.github.io/blender-swe1r/index.json
   ```
4. Find **SWE1R Import/Export** in the list and click **Install**.
5. Open the tools on the right side of the 3D view (press **N** if the sidebar is hidden) and click the **SWE1R Import/Export** tab.

### Updating

Once installed from the repository above, Blender detects new versions automatically. To update, go to **Edit → Preferences → Get Extensions**, click **Check for Updates**, then press **Update** next to the add-on.

### Manual install (no auto-updates)

Alternatively, [download the latest release .zip](https://github.com/louriccia/blender-swe1r/releases) and install it via **Get Extensions → ▼ → Install from Disk…** (or drag the .zip into Blender). Extensions installed this way must be updated manually.

## Known Issues

- Podd / MAlt import/export is not supported

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE - see the [LICENSE](https://github.com/louriccia/blender-swe1r/blob/main/LICENSE) file for details.

## Thanks
The following people have contributed to this project through feedback and insight. They're awesome!
* aphex0161
* Galeforce
* Leadphalanx
* tilman
* Tim707

## Related Projects
* [swe1r-assets](https://github.com/akopetsch/swe1r-assets) - A C#/.NET library for handling game assets of Star Wars Episode I: Racer
* [swe1r-assets-unity](https://github.com/akopetsch/swe1r-assets-unity) - A Unity package (WIP, currently just a sample project) that allows you to import, modify and re-export assets of the game Star Wars Episode I: Racer.
* [annodue](https://github.com/everalert/annodue) - A universal extension platform for STAR WARS Episode I Racer oriented toward speedrunning.

Support development by sending me some truguts</br>

[![ko-fi](https://www.ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/lightningpirate)