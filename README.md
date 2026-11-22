# Unused Data Blocks Detector for Blender

[![Blender](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmttfntn%2Funused-data-blocks-detector-blender%2Fmain%2Funused_data_blocks%2Fblender_manifest.toml&query=%24.blender_version_min&label=Blender&color=E87D0D&logo=blender&logoColor=white)](https://www.blender.org/download/)
[![Release](https://img.shields.io/github/v/release/mttfntn/unused-data-blocks-detector-blender)](https://github.com/mttfntn/unused-data-blocks-detector-blender/releases/latest)
[![Tests](https://github.com/mttfntn/unused-data-blocks-detector-blender/actions/workflows/tests.yml/badge.svg)](https://github.com/mttfntn/unused-data-blocks-detector-blender/actions/workflows/tests.yml)
[![License](https://img.shields.io/github/license/mttfntn/unused-data-blocks-detector-blender)](LICENSE)
[![Language](https://img.shields.io/github/languages/top/mttfntn/unused-data-blocks-detector-blender)](https://github.com/mttfntn/unused-data-blocks-detector-blender)

A small flag in Blender's top bar that tells you when your file contains **unused data-blocks** (meshes, images, materials and so on that nothing uses), how many there are and roughly how much they weigh.

```
[♥ 3 · 18.0 MB · 97%] [⏸]   Scene   ViewLayer
```

- **Count · size · share**: number of unused data-blocks, their estimated size, and their share of all the file's data.
- **Red** when unused data passes 10 MB, or 5% of the file's data once it's at least 1 MB (all adjustable).
- **✓** when there's nothing unused (can be hidden).
- **⏸ / ▶** pauses and resumes automatic scanning. While paused, the flag says *Paused* and no scans run.

Click the flag for a panel with:
- a breakdown by type, with a button to delete everything of one type
- the heaviest unused items, each with **Keep** (adds a fake user) and **Delete**
- **Purge All** (asks first; Ctrl+Z undoes it) and **Show in Outliner** (Blender's Unused Data view)

It also counts data that is only used by other unused data, like a material only on an unused mesh, the same as Blender's recursive purge. This can be turned off.

**Requires Blender 5.3.** No other version is supported.

## Installation
1. Download `unused_data_blocks-<version>.zip` from the [latest release](https://github.com/mttfntn/unused-data-blocks-detector-blender/releases/latest).
2. In Blender, open **Edit › Preferences › Get Extensions**.
3. Open the **▾** menu at the top right, choose **Install from Disk…** and pick the zip.
4. The add-on is enabled automatically. If not, enable it under **Add-ons**.

To update, install the new zip the same way. It replaces the old version.

## Settings
In **Edit › Preferences › Add-ons › Unused Data Blocks Detector**:

| Setting | Default | What it does |
|---|---|---|
| Show When Clean | on | Show ✓ when nothing is unused |
| Compact | off | Show only the count in the top bar |
| Show Pause Button | on | Show ⏸ next to the flag (always shown while paused) |
| Pause Auto-Scan | off | Stop automatic scanning (kept across restarts) |
| Include Indirectly Unused | on | Count data used only by unused data |
| Include Linked Data | off | Count unused data linked from other .blend files |
| Alert at % / Alert at MB | 5% / 10 MB | When the flag turns red |
| Ignore % Below MB | 1 MB | The % rule only counts from this size, so a few KB in a nearly empty file stay neutral |
| Min Scan Interval | 2 s | Shortest time between scans after a change |
| Items Listed | 10 | How many items the panel lists |

## Good to know
- **Sizes are estimates**, from vertex/attribute counts, image resolution, packed or on-disk file size and keyframe counts. They are not the size of the saved .blend.
- **It doesn't add anything to your files.** Settings live in your Blender preferences.
- **Cost:** a scan takes about 1 ms with 1,000 data-blocks and about 20 ms with 10,000, and only runs after something changes (at most every 2 s), plus a check every 10 s.
- A new, empty scene already shows one unused item (not red): Blender creates a grease pencil material called *Dots Stroke* at startup that nothing uses.

## For developers
- [HANDOVER.md](HANDOVER.md): how the project works and how to change, test and release it.
- [AGENTS.md](AGENTS.md): the same, compact, for AI coding assistants.

## License
[GPL-3.0-or-later](LICENSE). © Matteo Fontana.
