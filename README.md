# Blender Layer
See Krita Artists [post](https://krita-artists.org/t/plugin-blender-layer-live-3d-view-in-krita/63394) for more info.

> This is a maintained fork of [Yuntokon/BlenderLayer](https://github.com/Yuntokon/BlenderLayer) that runs on **Krita 5.2, 5.3 and 6** from a single package and updates itself from GitHub releases.

## Installation
 - Download `blender_layer-<version>.zip` from the [latest release](https://github.com/SHoogstad/BlenderLayer/releases/latest) (the release zip, not the source code zip)
 - In Krita choose **Tools → Scripts → Import Python Plugin from File...** and select the zip
 - Restart Krita, then enable the docker under **Settings → Dockers → Blender Layer**

The same package works on Krita 5.2 and 5.3 (Qt 5) and Krita 6 (Qt 6). If you used the original Blender Layer, importing this package replaces it and keeps your settings.

### Updates
When Krita starts, the docker checks GitHub for a newer release and offers to install it. The download is verified against the checksum GitHub publishes for it, and the new version is active after restarting Krita. The check can be turned off, or run manually, in the docker settings under **Updates**.

This is intended for 2d artist who want to use 3d models as reference in krita. Some features for 3d artist, i.e. texture painting, might be added in the future (Proof of concept in dev branch)

## Getting Started
 - Install Blender
 - Make sure the 'Blender Layer' add-on is installed and enabled in Krita
 - Open a document
 - Connect to Blender:
   - **Drag and drop** a .blend File into Krita. This will start Blender, connect and directly open the .blend file.
(You might be asked to select the path to the blender executable. Under Windows and Blender 3.4 for example select 'C:\Program Files\Blender Foundation\Blender 3.4\blender.exe')
   - Or use the **'Start Blender'** button in the 'Blender Layer' Docker. This will start Blender with a fresh file and connect automatically.
   - (Advanced) Or manually install the **companion add-on** for Blender. Goto 'Preferences → Add-Ons → Install...' and select **'blenderLayerClient.py'** from the blender_layer folder of the add-on. (Under Windows installed Krita add-ons can be found in '%APPDATA%\krita\pykrita'). In Krita, start the server from the docker, then in Blender from the header of a 3D View choose 'View → Connect to Krita' make sure host and port match the settings in Krita and press ok.
## Usage
### Navigation
Using the navigation widget in the docker:
 - **Drag** to rotate
 - **Shift + Drag** to pan
 - **Ctrl + Drag** vertically to zoom
 
You can also change the view from outside the docker with **Alt + Middle Mouse Button**.
#### Assistants
In order to create painting assistants matching Blender's perspective use the **'Create Assistant Set'** button in the docker. You will be asked to save an xml file. Make sure the assistant tool is selected, then open the Tool Settings and press the **'Load Assistant Set'** Button (Folder icon) and select the file you have just created.
The colored axis can be disabled in settings.
#### Library
The docker allows you to append a selection of objects to the current scene. By default, this includes posable mannequin models 'Body-chan' and 'Body-kun'. (CC-0 License, created by [vinchau](https://blendswap.com/blend/23521)).
You can configure additional objects from the settings menu by providing a .blend file and the path to objects within the file e.g. Object/Cube. (See Blender's [append](https://docs.blender.org/manual/en/latest/files/linked_libraries/link_append.html) function for reference)

Blender Layer also supports Blender's asset based [Pose Library](https://docs.blender.org/manual/en/latest/animation/armatures/posing/editing/pose_library.html). If your Blender file contains pose assets, these will show up in the 'Library' section of the docker and can be directly applied from within Krita.

## Development
The plugin code imports Qt only through `blender_layer/qt.py`, which picks PyQt5 or PyQt6 to match Krita. Use fully scoped enums (`Qt.AlignmentFlag.AlignCenter`) and `exec()`; both work with either binding.

`tests/smoke_test.py` runs the plugin outside of Krita against a mock of Krita's API. It builds the docker, streams frames from a fake Blender through the real server, and installs an update from a fake GitHub API:
```
pip install PyQt6   # or PyQt5
BLENDER_LAYER_QT=6 QT_QPA_PLATFORM=offscreen python tests/smoke_test.py
```

### Releasing
1. Bump `__version__` in `blender_layer/version.py`
2. Push a tag `v<version>`, e.g. `git tag v1.0.1 && git push origin v1.0.1`

The release workflow builds the package with `scripts/package.py` and publishes it as a GitHub release. Installed plugins pick it up on their next start.
