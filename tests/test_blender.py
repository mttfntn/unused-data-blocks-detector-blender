"""
Blender-side tests for the Unused Data Blocks add-on.

Run headless, from the repository root:
    blender --background --factory-startup --python tests/test_blender.py

The add-on is imported from the repository (not from an installed copy) and
enabled with addon_utils so its preferences exist. Exits with code 1 on failure.
"""

import os
import sys
import traceback

import addon_utils
import bpy

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.abspath(ROOT))
MODULE = "unused_data_blocks"


def mod():
    return sys.modules[MODULE]


def prefs():
    return bpy.context.preferences.addons[MODULE].preferences


def scan_names():
    m = mod()
    m.refresh(force=True)
    return {(it[0], it[1]) for it in m._state["result"].items}


def clean_file():
    """Start every test from the factory scene with nothing unused."""
    bpy.ops.wm.read_homefile(use_factory_startup=True)
    for attr, _l, _i in mod().CATEGORIES:
        coll = getattr(bpy.data, attr, None)
        if coll is None:
            continue
        for id_data in list(coll):
            if id_data.users == 0:
                coll.remove(id_data)
    p = prefs()
    p.paused = False
    p.include_recursive = True
    p.include_linked = False


# --------------------------------------------------------------------------
def test_registered():
    m = mod()
    assert hasattr(bpy.types, "UDB_PT_unused_data")
    for op in ("refresh", "purge", "remove_one", "keep", "show_in_outliner"):
        assert hasattr(bpy.ops.udb, op), op
    assert bpy.app.timers.is_registered(m._timer)
    assert m._on_change in bpy.app.handlers.depsgraph_update_post
    assert m._on_load in bpy.app.handlers.load_post
    assert m.draw_topbar in bpy.types.TOPBAR_HT_upper_bar._dyn_ui_initialize()


def test_pref_defaults():
    p = prefs()
    assert p.show_when_clean and not p.compact and p.show_pause_button
    assert p.include_recursive and not p.include_linked
    assert abs(p.alert_percent - 5.0) < 1e-6 and abs(p.alert_mb - 10.0) < 1e-6
    assert abs(p.scan_interval - 2.0) < 1e-6 and p.list_limit == 10


def test_clean_factory_file():
    clean_file()
    assert scan_names() == set()
    res = mod()._state["result"]
    assert res.unused_count == 0 and res.unused_size == 0 and res.total_size > 0
    assert res.percent == 0.0


def test_direct_and_recursive():
    clean_file()
    me = bpy.data.meshes.new("T_Mesh")
    mat = bpy.data.materials.new("T_Mat")
    me.materials.append(mat)
    found = scan_names()
    assert found == {("meshes", "T_Mesh"), ("materials", "T_Mat")}, found
    rec = {it[1]: it[4] for it in mod()._state["result"].items}
    assert rec == {"T_Mesh": False, "T_Mat": True}, rec
    prefs().include_recursive = False
    assert scan_names() == {("meshes", "T_Mesh")}


def test_recursive_chain():
    # collection -> object -> mesh -> material, nothing linked to the scene
    clean_file()
    me = bpy.data.meshes.new("C_Mesh")
    me.materials.append(bpy.data.materials.new("C_Mat"))
    ob = bpy.data.objects.new("C_Obj", me)
    col = bpy.data.collections.new("C_Col")
    col.objects.link(ob)
    assert scan_names() == {("collections", "C_Col"), ("objects", "C_Obj"),
                            ("meshes", "C_Mesh"), ("materials", "C_Mat")}


def test_fake_user_and_used_not_flagged():
    clean_file()
    keep = bpy.data.materials.new("Kept")
    keep.use_fake_user = True
    cube = bpy.data.objects["Cube"]
    cube.data.materials.append(bpy.data.materials.new("Used"))
    assert scan_names() == set()


def test_runtime_images_ignored():
    clean_file()
    bpy.data.images.new("Plain", 8, 8)
    names = scan_names()
    assert ("images", "Plain") in names
    assert not any(n in ("Render Result", "Viewer Node") for _a, n in names)


def test_sizes():
    clean_file()
    m = mod()
    img = bpy.data.images.new("S_Img", 64, 32)
    assert m.estimate_size("images", img) == 64 * 32 * 4
    fimg = bpy.data.images.new("S_Float", 16, 16, float_buffer=True)
    assert m.estimate_size("images", fimg) == 16 * 16 * 4 * 4
    me = bpy.data.meshes.new("S_Mesh")
    assert m.estimate_size("meshes", me) == m.BASE_ID_SIZE
    big = bpy.data.objects["Cube"].data
    assert m.estimate_size("meshes", big) > m.BASE_ID_SIZE
    act = bpy.data.actions.new("S_Act")
    assert m.estimate_size("actions", act) == m.BASE_ID_SIZE


def test_action_keyframes_counted():
    clean_file()
    cube = bpy.data.objects["Cube"]
    for f in (1, 10, 20):
        cube.location.x = f
        cube.keyframe_insert("location", frame=f)
    act = cube.animation_data.action
    assert mod()._action_keyframes(act) == 9  # 3 frames x 3 channels


def test_totals_and_percent():
    clean_file()
    bpy.data.images.new("P_Img", 256, 256)
    res = mod()._state["result"]
    mod().refresh(force=True)
    res = mod()._state["result"]
    assert res.unused_size == 256 * 256 * 4
    assert 0 < res.percent < 100
    assert res.by_category == {"images": [1, 256 * 256 * 4]}


def test_format_size():
    f = mod().format_size
    assert f(0) == "0 B" and f(1023) == "1023 B"
    assert f(1024) == "1.0 KB" and f(1536) == "1.5 KB"
    assert f(1024 ** 2) == "1.0 MB" and f(3 * 1024 ** 3) == "3.0 GB"
    assert f(5000 * 1024 ** 3) == "5000.0 GB"


def test_purge_all_and_category():
    clean_file()
    bpy.data.images.new("Q_Img", 8, 8)
    bpy.data.meshes.new("Q_Mesh")
    scan_names()
    assert bpy.ops.udb.purge('EXEC_DEFAULT', category="images") == {'FINISHED'}
    assert "Q_Img" not in bpy.data.images and "Q_Mesh" in bpy.data.meshes
    assert bpy.ops.udb.purge('EXEC_DEFAULT') == {'FINISHED'}
    assert "Q_Mesh" not in bpy.data.meshes
    assert mod()._state["result"].unused_count == 0


def test_purge_dialog_matches_deletion():
    # Regression: the confirm dialog used the cached scan, which is stale
    # while paused, so it could announce fewer items than were deleted.
    clean_file()
    scan_names()
    prefs().paused = True
    for i in range(3):
        bpy.data.images.new(f"PD{i}", 8, 8)
    count, size = mod().purge_summary()
    assert (count, size) == (3, 3 * 8 * 8 * 4), (count, size)
    assert mod().purge_summary("meshes") == (0, 0)
    bpy.ops.udb.purge('EXEC_DEFAULT')
    assert not any(f"PD{i}" in bpy.data.images for i in range(3))
    prefs().paused = False


def test_purge_many():
    # Purge looks items up through one session_uid map per collection.
    clean_file()
    for i in range(2000):
        bpy.data.meshes.new(f"F{i}")
        bpy.data.materials.new(f"FM{i}")
    bpy.ops.udb.purge('EXEC_DEFAULT')
    assert mod()._state["result"].unused_count == 0
    assert not any(m.name.startswith("F") for m in bpy.data.meshes)
    assert not any(m.name.startswith("FM") for m in bpy.data.materials)


def test_remove_one_and_keep():
    clean_file()
    bpy.data.meshes.new("R_Mesh")
    bpy.data.materials.new("R_Mat")
    scan_names()
    items = {it[1]: it for it in mod()._state["result"].items}
    a, n, uid = items["R_Mesh"][:3]
    assert bpy.ops.udb.remove_one(attr=a, uid=uid) == {'FINISHED'}
    assert "R_Mesh" not in bpy.data.meshes
    a, n, uid = items["R_Mat"][:3]
    assert bpy.ops.udb.keep(attr=a, uid=uid) == {'FINISHED'}
    assert bpy.data.materials["R_Mat"].use_fake_user
    assert mod()._state["result"].unused_count == 0


def test_pause_blocks_timer_scans():
    clean_file()
    m = mod()
    scan_names()
    prefs().paused = True
    bpy.data.images.new("Z_Img", 8, 8)
    m._state["dirty"] = True
    m._state["last_scan"] = 0.0
    m._timer()
    assert m._state["result"].unused_count == 0
    prefs().paused = False  # resuming rescans immediately
    assert m._state["result"].unused_count == 1


def test_timer_rescans_when_dirty():
    clean_file()
    m = mod()
    scan_names()
    bpy.data.images.new("D_Img", 8, 8)
    m._state["dirty"] = True
    m._state["last_scan"] = 0.0
    m._timer()
    assert m._state["result"].unused_count == 1 and not m._state["dirty"]


def test_alert_thresholds():
    m = mod()
    res = m.ScanResult()
    p = prefs()
    assert not m._is_alert(res, p)
    res.unused_count, res.unused_size, res.total_size = 1, 1024, 10 ** 9
    assert not m._is_alert(res, p)
    res.unused_size = int(11 * 1024 * 1024)
    assert m._is_alert(res, p)
    res.unused_size, res.total_size = 1024, 2048
    assert m._is_alert(res, p)


def test_load_resets_state():
    clean_file()
    m = mod()
    m._state["dirty"] = False
    bpy.ops.wm.read_homefile(use_empty=True)
    assert m._state["dirty"]


def test_unregister_clean():
    m = mod()
    addon_utils.disable(MODULE, default_set=True)
    assert not hasattr(bpy.types, "UDB_PT_unused_data")
    assert not bpy.app.timers.is_registered(m._timer)
    assert m._on_change not in bpy.app.handlers.depsgraph_update_post
    assert m.draw_topbar not in bpy.types.TOPBAR_HT_upper_bar._dyn_ui_initialize()
    addon_utils.enable(MODULE, default_set=True)


# --------------------------------------------------------------------------
def main():
    addon_utils.enable(MODULE, default_set=True)
    assert MODULE in bpy.context.preferences.addons, "add-on failed to enable"
    tests = [(n, f) for n, f in sorted(globals().items(), key=lambda kv: kv[1].__code__.co_firstlineno
                                        if callable(kv[1]) and hasattr(kv[1], "__code__") else 0)
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("PASS", name)
        except Exception:
            failed += 1
            print("FAIL", name)
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.stdout.flush()
    os._exit(1 if failed else 0)


main()
