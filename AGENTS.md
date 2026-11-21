# AGENTS.md: Unused Data Blocks Detector (Blender add-on)

Top bar flag showing unused data-blocks and their estimated weight, plus a popover to keep/delete them. Blender **5.3 only**. Extension format, one module. Python. GPL-3.0-or-later. Not a fork. Private repo `github.com/mttfntn/unused-data-blocks-detector-blender`, branch `main`. Human docs: `HANDOVER.md`.

## Commands
```
blender --background --factory-startup --python tests/test_blender.py                     # tests, exit 1 on failure
blender --background --factory-startup --python tests/snapshot_scan.py -- <parent_dir> out.json   # behaviour dump
python build.py                                                                             # -> dist/unused_data_blocks-<ver>.zip
blender --factory-startup --command extension validate dist/unused_data_blocks-<ver>.zip
```
Windows Blender: `C:\Program Files\Blender Foundation\Blender 5.3\blender.exe`.

**Isolation** (required): never test in the user's running Blender (it may be reachable through an MCP socket on port 9876; don't use that for tests) or their real profile. Set `BLENDER_USER_CONFIG`, `BLENDER_USER_SCRIPTS` and `BLENDER_USER_EXTENSIONS` to scratch dirs, and use `--factory-startup`.

## Architecture (`unused_data_blocks/__init__.py`)
- `CATEGORIES` `(bpy.data attr, label, icon)`: the scanned collections. All exist in 5.3; no `getattr` fallbacks.
- `estimate_size(attr, id)`: heuristic bytes. Images: packed size, else in-memory pixels, else generated size, else disk size. Disk sizes are cached in `_file_size_cache`, cleared on load.
- `scan() -> ScanResult`: `users == 0` gives direct; with `include_recursive`, `bpy.data.user_map(subset=candidates)` fixed-point loop gives indirect. Linked is skipped unless `include_linked`. Render Result/Viewer images are skipped. `items` = `(attr, name, session_uid, size, recursive, linked)`, sorted by size.
- `_state` = `{"result", "dirty", "last_scan"}`. Module-global; UI reads only this.
- **Data flow**: handlers (depsgraph/undo/redo set `dirty`; load clears the cache) → `_timer` every 0.5 s (skips when paused; scans when dirty or >10 s, rate-limited by `scan_interval`) → `refresh()` → `scan()` → `_state` → `_redraw_ui()` if changed.
- UI: `draw_topbar` prepended to `TOPBAR_HT_upper_bar`, only when `context.region.alignment == 'RIGHT'`. `UDB_PT_unused_data` popover (TOPBAR/HEADER). `UDB_AP_preferences` (`bl_idname = __package__`) holds every setting, including `paused`.
- Operators: `udb.refresh`, `udb.purge(category)`, `udb.remove_one(attr, uid)`, `udb.keep(attr, uid)`, `udb.show_in_outliner`. IDs are found by `session_uid`, never by name. `purge_summary()` rescans, then counts (used by the confirm dialog and tests).

## Rules and pitfalls
- No docstrings on Operator/Panel/AddonPreferences classes (they become tooltips). Use `#` comments.
- No fallbacks for old Blender. In 5.3: `Action.fcurves` is gone (use `layers → strips → channelbags → fcurves`), and every ID has `session_uid > 0`.
- The top bar is not in `screen.areas`. Redraw it by re-assigning `workspace.use_pin_scene` (sends NC_WORKSPACE). WM ID-props and `wm.redraw_timer` don't work (tested). It doesn't set `is_dirty` (tested).
- `layout.alert` doesn't color popovers. Use an operator button (`wm.call_panel`) for the red state.
- Drawing must never scan. Handlers must only set flags.
- Headless: `invoke_confirm` executes directly, and `bpy.ops` calls don't push undo unless you pass `True` after the context, e.g. `('EXEC_DEFAULT', True)`.
- The GUI factory startup has an unused material "Dots Stroke" (~26% of a new file). `_is_alert`: red if `size >= alert_mb`, or `percent >= alert_percent` **and** `size >= alert_min_mb` (1 MB), so new files aren't red (tested). Tests remove all orphans in `clean_file()` first.
- Manifest `tagline` max 64 chars (validation fails otherwise).
- The version lives only in `blender_manifest.toml`. `bl_info` was removed on purpose.

## How changes were verified (handover pass, Nov 2026)
- Tests: 18/18 on the original code before any change. After the cleanup: 20/20 (2 regression tests added; both fail on the original code).
- `tests/snapshot_scan.py`: 46 data-blocks of every type (packed/external/float images, layered action, linked library data, recursive chain, fake users), 4 setting combinations plus the no-preferences path. **Identical** between the original commit (`7dcb2f5`) and the cleaned code, and identical between two runs of each.
- The `except` blocks were instrumented across the tests, the snapshot and a 10,000-item stress run; none fired.
- Purge benchmark (10k items): 1631 ms → 97 ms.
- Isolated GUI Blender 5.3 (scratch profile): the zip installs and enables; flag clean/red/paused/resumed checked by screenshot; purge then undo restores, redo deletes again.

## Release checklist
1. Bump `version` in `unused_data_blocks/blender_manifest.toml` **and** the static release badge in `README.md` (private repo, so badges are static, except GitHub's Tests badge).
2. Run the tests locally. Commit and push to `main`. Confirm Tests is green (`gh run list`).
3. `git tag -a vX.Y.Z -m "<notes>"`, then `git push origin vX.Y.Z`.
4. Watch Release (`gh run watch`). Check `gh release view vX.Y.Z` has the zip.

## Git and CI
- Single branch `main`, remote `origin`. Small commits, clear messages. `.gitattributes` forces LF.
- `tests.yml`: push to main, PRs, manual, and `workflow_call`. Blender 5.3.0 is fetched by `.github/scripts/get-blender.sh` (official server + 3 mirrors, curl retries, SHA-256 check); only the tarball is cached. Tests use scratch `BLENDER_USER_*` dirs. Build + `extension validate`. **No workflow artifacts** (keeps account storage free; the zip ships only as a release asset).
- `release.yml`: on tag `v*.*.*` → reuses tests → fetches the tag object explicitly (checkout only gets the commit) → tag must equal the manifest version and be annotated → notes from the tag message → `gh release create --verify-tag` with the zip.
- `dist/` and `*.zip` are gitignored.
