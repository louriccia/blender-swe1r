## Install
You need [Blender 5.0](https://www.blender.org/download/) or newer.

1. In Blender, go to **Edit → Preferences → Get Extensions**.
2. In the **Repositories** dropdown at the top right, click **+** and choose **Add Remote Repository…**.
3. Paste this URL, tick **Check for Updates on Startup**, then click **Create**:
   ```
   https://louriccia.github.io/blender-swe1r/index.json
   ```
4. Find **SWE1R Import/Export** in the list and click **Install**.

Blender then offers updates on its own. You can also [download a release .zip](https://github.com/louriccia/blender-swe1r/releases) and install it with **Get Extensions → ▼ → Install from Disk…**, but then you have to update it by hand.

## Open the add-on
Open the sidebar on the right of the 3D viewport (press **N**) and click the **SWE1R Import/Export** tab.

## Find the game files
The add-on reads and writes the game's `.bin` files in its `data/lev01` folder:
- Steam: `Steam\steamapps\common\Star Wars Episode I Racer\data\lev01`
- GOG: `GOG Galaxy\Games\STAR WARS Racer\data\lev01`

The first time the add-on overwrites a `.bin` file it saves the original next to it as `.bin.bak`. Keep your own copy of the folder too.

## First import and export
1. In **Import**, pick the `lev01` folder, a type and a model, then click **Import**. See [Import](Import).
2. Edit it.
3. Click the model's collection in the Outliner, or one of its objects. In **Export**, pick the folder to write to, then click **Export**. See [Export](Export).
4. Start the game and race it.
