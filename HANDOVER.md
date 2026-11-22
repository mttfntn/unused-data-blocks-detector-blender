# Handover: Unused Data Blocks Detector

## What it is
A Blender add-on (extension format) that puts a flag in the top bar showing how many unused data-blocks the open file has and roughly how much they weigh, with a panel to inspect, keep or delete them. User-facing description: [README.md](README.md).

- Language: Python, one module.
- Supported: **Blender 5.3 only** (manifest `blender_version_min = 5.3.0`, `blender_version_max = 5.4.0`). Code written for older Blender versions was removed on purpose.
- License: GPL-3.0-or-later. Not a fork.
- Repository: `github.com/mttfntn/unused-data-blocks-detector-blender` (public), branch `main`.

## What you need
- Blender 5.3. On this machine: `C:\Program Files\Blender Foundation\Blender 5.3\blender.exe`.
- Python 3 (any recent version) for `build.py`.
- `git` and the GitHub CLI `gh`, logged in, for releases.

## Files

| Path | What it is |
|---|---|
| `unused_data_blocks/__init__.py` | The whole add-on: scanning, size estimates, operators, top bar flag, panel, preferences, registration |
| `unused_data_blocks/blender_manifest.toml` | Extension manifest. **The only place the version number lives** |
| `tests/test_blender.py` | Blender-side tests (run headless) |
| `tests/snapshot_scan.py` | Behaviour snapshot: dumps scan results and size estimates to JSON, to compare two versions of the code |
| `build.py` | Builds `dist/unused_data_blocks-<version>.zip` (manifest + module + LICENSE) |
| `.github/workflows/tests.yml` | CI: tests on Blender 5.3.0, build and validate the package |
| `.github/workflows/release.yml` | Release: on a `vX.Y.Z` tag, test, build, publish a GitHub release |
| `.github/scripts/get-blender.sh` | Downloads Blender 5.3.0 for CI with retries, mirrors and a checksum |
| `LICENSE` | GPL-3.0 text (also shipped in the zip) |
| `README.md`, `HANDOVER.md`, `AGENTS.md` | Docs. Not shipped in the zip |

## How it works
1. **Change detection.** Handlers on depsgraph updates, undo, redo and file load only set a `dirty` flag. They never scan.
2. **Timer.** `_timer` runs every 0.5 s. When `dirty` (or 10 s have passed, as a safety net for changes Blender doesn't announce, like deleting in the Outliner) and at least `scan_interval` (2 s) has passed since the last scan, it calls `refresh()`. While paused, it does nothing.
3. **Scan.** `scan()` walks every collection in `CATEGORIES` (meshes, images, materials, …; scenes, screens, workspaces and texts are left out on purpose). For each data-block it estimates a size (`estimate_size`) and adds it to the total. Data-blocks with zero users are *directly unused* (a fake user counts as a user). With *Include Indirectly Unused* on, it uses `bpy.data.user_map` to add data-blocks whose only users are unused, repeating until nothing changes. This is what a recursive purge would delete. Linked data is skipped unless *Include Linked Data* is on. Render Result and Viewer Node images are skipped.
4. **Result.** `refresh()` stores a `ScanResult` in `_state`. If it changed, `_redraw_ui()` makes the top bar redraw (see "Things to know") and tags Preferences editors.
5. **Drawing.** `draw_topbar` (prepended to `TOPBAR_HT_upper_bar`, right side only) and the popover panel `UDB_PT_unused_data` only read `_state`. They never scan, so drawing is free.
6. **Actions.** Operators `udb.purge`, `udb.remove_one`, `udb.keep`, `udb.refresh` and `udb.show_in_outliner`. Items are identified by `session_uid` (unique per session), never by name. Purge rescans first, deletes with `bpy.data.batch_remove`, and can be undone.

## How to make a change
1. Edit `unused_data_blocks/__init__.py`.
2. Run the tests (below). Add a test for any behaviour you change or bug you fix.
3. If the change should not alter results, run the behaviour snapshot on the old and new code and compare (below).
4. To try it by hand, build the zip and install it in a **scratch profile**, never your everyday one (below).
5. Commit small, clear steps and push to `main`. CI must be green.

## How to run the tests
Always isolated: a scratch profile and `--factory-startup`, never a running Blender or your real profile.

```bash
export BLENDER_USER_CONFIG=/tmp/udb/config BLENDER_USER_SCRIPTS=/tmp/udb/scripts BLENDER_USER_EXTENSIONS=/tmp/udb/extensions
blender --background --factory-startup --python tests/test_blender.py
```
This prints `PASS`/`FAIL` per test, then `N/N passed`. The exit code is 1 on any failure.

Behaviour comparison between two versions:
```bash
git archive <old-commit> unused_data_blocks | tar -x -C /tmp/old
blender --background --factory-startup --python tests/snapshot_scan.py -- /tmp/old old.json
blender --background --factory-startup --python tests/snapshot_scan.py -- .        new.json
```
Then compare the two files: identical means no change. The snapshot is deterministic (two runs of the same code are identical).

Trying the built package by hand, in a throwaway profile:
```bash
python build.py
blender --factory-startup --command extension validate dist/unused_data_blocks-<version>.zip
```
Then start Blender with the same `BLENDER_USER_*` variables and install the zip from **Preferences › Get Extensions › Install from Disk**.

## How to make a release
1. Bump `version` in `unused_data_blocks/blender_manifest.toml`.
2. Nothing to change in `README.md`: its release, license and language badges read GitHub, and the Blender badge reads the manifest.
3. Run the tests locally. Commit and push to `main`. Wait for the Tests workflow to pass (`gh run list`).
4. Create an **annotated** tag whose message is the release notes, and push it:
   ```bash
   git tag -a vX.Y.Z -m "What changed"
   git push origin vX.Y.Z
   ```
5. The Release workflow tests again, checks that the tag matches the manifest version, builds the zip and publishes the release with the tag message as notes. Check with `gh release view vX.Y.Z`.

## Bringing in updates from the original project
Not applicable: this project is not a fork.

## Things to know
- **The top bar can't be redrawn directly.** It's a global area that Python can't reach through `screen.areas`, and `area.tag_redraw()` there does nothing for it. Setting a WindowManager property or running `wm.redraw_timer` did not refresh it (tested). `_redraw_ui` re-assigns `workspace.use_pin_scene` to its own value, which sends a workspace notifier the top bar listens to. This does not mark the file as modified (tested).
- **Popover buttons ignore `layout.alert`.** The red flag is therefore an operator button (`wm.call_panel`) when alerting, and a popover otherwise.
- **Don't give operator, panel or preferences classes docstrings.** Blender shows them as tooltips. Use `#` comments.
- **Operators called from Python don't record undo steps by default.** Pass `True` after the execution context (`bpy.ops.udb.purge('EXEC_DEFAULT', True)`) when testing undo.
- **Headless Blender skips confirmation dialogs** (`invoke_confirm` runs `execute` straight away). That is why the dialog's numbers come from `purge_summary()`, which the tests call directly.
- `bl_info` was removed on purpose: extensions ignore it and read the manifest.
- The add-on's settings, including *Paused*, live in Blender's user preferences, not in .blend files.

## Known limits
- **Sizes are heuristics**, not measured memory: per-attribute bytes for geometry, pixels × channels for loaded images, file size for external or packed files, fixed amounts per keyframe, node and bone, and 1 KB for everything else. Grease pencil, objects, collections and most small types are counted as 1 KB.
- **New files show one unused item.** Blender's GUI creates the *Dots Stroke* grease pencil material at startup with no users. It's about 26% of a new file's data, so the % alert only applies from *Ignore % Below MB* (1 MB) up; otherwise every new file would be red (that was the case up to 1.1.0).
- **Changes Blender doesn't announce**, like deleting in the Outliner, are picked up within about 10 s instead of 2 s.
- Not tested: whether an already-open popover refreshes by itself when a scan finishes while it's open.
- **Recursive detection relies on `bpy.data.user_map`.** A reference that `user_map` doesn't report would make an item look indirectly unused when it isn't. Blender's own recursive purge works the same way.
- The top bar flag and popover were checked visually in Blender 5.3 on Windows only. CI runs headless on Linux, so it can't test drawing.
