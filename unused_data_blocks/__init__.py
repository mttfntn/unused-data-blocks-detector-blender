# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unused Data Blocks Detector

Shows a small flag in the top bar when the file contains unused (orphan)
data-blocks, with how many there are and an estimate of how much memory /
file size they account for. Click the flag for a breakdown and cleanup tools.
"""

bl_info = {
    "name": "Unused Data Blocks Detector",
    "author": "Matteo Fontana",
    "version": (1, 1, 0),
    "blender": (4, 2, 0),
    "location": "Top Bar (right side)",
    "description": "Flags unused data-blocks in the top bar and estimates their weight",
    "category": "Interface",
}

import os
import time

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty

# --------------------------------------------------------------------------
# Data-block categories that are scanned (bpy.data attribute, label, icon).
# Scenes, screens, workspaces, window managers, libraries and texts are
# intentionally left out: they are never "garbage" in the usual sense.
# --------------------------------------------------------------------------
CATEGORIES = (
    ("meshes", "Meshes", 'MESH_DATA'),
    ("images", "Images", 'IMAGE_DATA'),
    ("materials", "Materials", 'MATERIAL'),
    ("node_groups", "Node Groups", 'NODETREE'),
    ("textures", "Textures", 'TEXTURE'),
    ("actions", "Actions", 'ACTION'),
    ("objects", "Objects", 'OBJECT_DATA'),
    ("collections", "Collections", 'OUTLINER_COLLECTION'),
    ("curves", "Curves", 'CURVE_DATA'),
    ("hair_curves", "Hair Curves", 'CURVES_DATA'),
    ("pointclouds", "Point Clouds", 'POINTCLOUD_DATA'),
    ("volumes", "Volumes", 'VOLUME_DATA'),
    ("grease_pencils", "Grease Pencil", 'OUTLINER_DATA_GREASEPENCIL'),
    ("annotations", "Annotations", 'OUTLINER_DATA_GREASEPENCIL'),
    ("armatures", "Armatures", 'ARMATURE_DATA'),
    ("lattices", "Lattices", 'LATTICE_DATA'),
    ("metaballs", "Metaballs", 'META_DATA'),
    ("lights", "Lights", 'LIGHT_DATA'),
    ("lightprobes", "Light Probes", 'OUTLINER_DATA_LIGHTPROBE'),
    ("cameras", "Cameras", 'CAMERA_DATA'),
    ("speakers", "Speakers", 'OUTLINER_DATA_SPEAKER'),
    ("worlds", "Worlds", 'WORLD'),
    ("fonts", "Fonts", 'FONT_DATA'),
    ("sounds", "Sounds", 'SOUND'),
    ("movieclips", "Movie Clips", 'TRACKER'),
    ("masks", "Masks", 'MOD_MASK'),
    ("cache_files", "Cache Files", 'FILE'),
    ("particles", "Particle Settings", 'PARTICLE_DATA'),
    ("linestyles", "Line Styles", 'LINE_DATA'),
    ("palettes", "Palettes", 'COLOR'),
    ("paint_curves", "Paint Curves", 'CURVE_BEZCURVE'),
    ("brushes", "Brushes", 'BRUSH_DATA'),
)
CATEGORY_INFO = {attr: (label, icon) for attr, label, icon in CATEGORIES}

# Bytes per element for attribute data types.
ATTR_SIZES = {
    'FLOAT': 4, 'INT': 4, 'FLOAT_VECTOR': 12, 'FLOAT_COLOR': 16,
    'BYTE_COLOR': 4, 'STRING': 8, 'BOOLEAN': 1, 'FLOAT2': 8, 'INT8': 1,
    'INT16_2D': 4, 'INT32_2D': 8, 'QUATERNION': 16, 'FLOAT4X4': 64,
}
BASE_ID_SIZE = 1024  # rough fixed overhead of any data-block


# --------------------------------------------------------------------------
# Size estimation
# --------------------------------------------------------------------------
_file_size_cache = {}


def _disk_size(id_data):
    """Packed size, otherwise size of the external file on disk."""
    packed = getattr(id_data, "packed_file", None)
    if packed is not None:
        return packed.size
    path = getattr(id_data, "filepath", "")
    if not path:
        return 0
    try:
        abspath = bpy.path.abspath(path, library=id_data.library)
    except Exception:
        return 0
    if abspath not in _file_size_cache:
        try:
            _file_size_cache[abspath] = os.path.getsize(abspath)
        except OSError:
            _file_size_cache[abspath] = 0
    return _file_size_cache[abspath]


def _attributes_size(attributes):
    total = 0
    for attr in attributes:
        try:
            total += len(attr.data) * ATTR_SIZES.get(attr.data_type, 4)
        except Exception:
            pass
    return total


def _action_keyframes(action):
    fcurves = getattr(action, "fcurves", None)  # legacy API (< 5.0)
    if fcurves is not None:
        return sum(len(fc.keyframe_points) for fc in fcurves)
    count = 0
    for layer in getattr(action, "layers", ()):  # layered actions (4.4+)
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", ()):
                for fc in bag.fcurves:
                    count += len(fc.keyframe_points)
    return count


def _tree_size(tree):
    return len(tree.nodes) * 1024 + len(tree.links) * 64 if tree else 0


def estimate_size(attr, id_data):
    """Approximate in-memory weight of a data-block, in bytes."""
    try:
        if attr == "meshes":
            # Attributes include positions, edges and corner topology.
            return BASE_ID_SIZE + _attributes_size(id_data.attributes) + len(id_data.polygons) * 4
        if attr == "images":
            if getattr(id_data, "packed_file", None) is not None:
                return id_data.packed_file.size
            if id_data.has_data:
                w, h = id_data.size
                return w * h * id_data.channels * (4 if id_data.is_float else 1)
            if id_data.source == 'GENERATED':
                return id_data.generated_width * id_data.generated_height * 4
            return _disk_size(id_data)
        if attr in {"sounds", "fonts", "movieclips", "volumes", "cache_files"}:
            return BASE_ID_SIZE + _disk_size(id_data)
        if attr == "hair_curves":
            return BASE_ID_SIZE + _attributes_size(id_data.attributes) + len(id_data.curves) * 4
        if attr == "pointclouds":
            return BASE_ID_SIZE + _attributes_size(id_data.attributes)
        if attr == "curves":
            pts = sum(len(s.points) + len(s.bezier_points) * 3 for s in id_data.splines)
            return BASE_ID_SIZE + pts * 32
        if attr == "actions":
            return BASE_ID_SIZE + _action_keyframes(id_data) * 64
        if attr in {"materials", "worlds", "textures", "lights", "linestyles"}:
            return BASE_ID_SIZE + _tree_size(getattr(id_data, "node_tree", None))
        if attr == "node_groups":
            return BASE_ID_SIZE + _tree_size(id_data)
        if attr == "armatures":
            return BASE_ID_SIZE + len(id_data.bones) * 512
        if attr == "lattices":
            return BASE_ID_SIZE + len(id_data.points) * 32
    except Exception:
        pass
    return BASE_ID_SIZE


def format_size(num):
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} GB"


# --------------------------------------------------------------------------
# Scanning
# --------------------------------------------------------------------------
class ScanResult:
    def __init__(self):
        self.items = []          # (attr, name, session_uid, size, recursive, linked)
        self.by_category = {}    # attr -> [count, size]
        self.unused_count = 0
        self.unused_size = 0
        self.total_size = 0
        self.scan_ms = 0.0

    @property
    def percent(self):
        return 100.0 * self.unused_size / self.total_size if self.total_size else 0.0


_state = {
    "result": ScanResult(),
    "dirty": True,
    "last_scan": 0.0,
}


def _prefs():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def _iter_ids():
    for attr, _label, _icon in CATEGORIES:
        coll = getattr(bpy.data, attr, None)
        if coll is None:
            continue
        for id_data in coll:
            # Render Result / Viewer Node images are runtime buffers, not real data.
            if attr == "images" and id_data.type in {'RENDER_RESULT', 'COMPOSITING'}:
                continue
            yield attr, id_data


def scan():
    t0 = time.perf_counter()
    prefs = _prefs()
    recursive = prefs.include_recursive if prefs else True
    include_linked = prefs.include_linked if prefs else False

    res = ScanResult()
    all_ids = []
    unused = set()
    for attr, id_data in _iter_ids():
        size = estimate_size(attr, id_data)
        res.total_size += size
        all_ids.append((attr, id_data, size))
        if id_data.users == 0 and (include_linked or id_data.library is None):
            unused.add(id_data)

    # Data only used by other unused data (e.g. a material on an orphan mesh)
    # would also be removed by a recursive purge.
    direct = set(unused)
    if recursive and unused:
        candidates = {
            id_data for _a, id_data, _s in all_ids
            if id_data not in unused and not id_data.use_fake_user
            and (include_linked or id_data.library is None)
        }
        if candidates:
            user_map = bpy.data.user_map(subset=candidates)
            changed = True
            while changed:
                changed = False
                for id_data in list(candidates):
                    users = user_map.get(id_data)
                    if users and users <= unused:
                        unused.add(id_data)
                        candidates.discard(id_data)
                        changed = True

    for attr, id_data, size in all_ids:
        if id_data not in unused:
            continue
        try:
            uid = id_data.session_uid
        except AttributeError:
            uid = 0
        res.items.append((attr, id_data.name, uid, size, id_data not in direct, id_data.library is not None))
        cat = res.by_category.setdefault(attr, [0, 0])
        cat[0] += 1
        cat[1] += size
        res.unused_size += size
    res.unused_count = len(res.items)
    res.items.sort(key=lambda it: it[3], reverse=True)
    res.scan_ms = (time.perf_counter() - t0) * 1000.0
    return res


def _redraw_ui():
    wm = bpy.context.window_manager
    if wm is None:
        return
    # The top bar is a global area that is not listed in screen.areas, so it
    # can't be tagged directly. Re-assigning a workspace property sends an
    # NC_WORKSPACE notifier, which the top bar header listens to.
    for window in wm.windows:
        try:
            ws = window.workspace
            ws.use_pin_scene = ws.use_pin_scene
        except Exception:
            pass
    for window in wm.windows:
        for area in window.screen.areas:
            area.tag_redraw()


def refresh(force=False):
    old = _state["result"]
    try:
        new = scan()
    except Exception as ex:  # never break the UI
        print("Unused Data Blocks:", ex)
        return
    _state["result"] = new
    _state["dirty"] = False
    _state["last_scan"] = time.monotonic()
    if force or (new.unused_count, new.unused_size, new.total_size) != (
        old.unused_count, old.unused_size, old.total_size
    ):
        _redraw_ui()


def _timer():
    prefs = _prefs()
    if prefs is not None and prefs.paused:
        return 1.0
    interval = prefs.scan_interval if prefs else 2.0
    now = time.monotonic()
    # Rescan when something changed, and periodically as a safety net
    # (user counts can change without a depsgraph update, e.g. Outliner edits).
    if _state["dirty"] or now - _state["last_scan"] > max(interval * 5, 10.0):
        if now - _state["last_scan"] >= interval:
            refresh()
    return 0.5


@persistent
def _on_change(*_args):
    _state["dirty"] = True


@persistent
def _on_load(*_args):
    _file_size_cache.clear()
    _state["dirty"] = True
    _state["last_scan"] = 0.0


# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------
def _find_id(attr, name, uid):
    coll = getattr(bpy.data, attr, None)
    if coll is None:
        return None
    for id_data in coll:
        try:
            if uid and id_data.session_uid == uid:
                return id_data
        except AttributeError:
            pass
        if not uid and id_data.name == name:
            return id_data
    return None


class UDB_OT_refresh(bpy.types.Operator):
    bl_idname = "udb.refresh"
    bl_label = "Rescan Unused Data"
    bl_description = "Scan the file again for unused data-blocks"

    def execute(self, context):
        refresh(force=True)
        return {'FINISHED'}


class UDB_OT_purge(bpy.types.Operator):
    bl_idname = "udb.purge"
    bl_label = "Purge Unused Data"
    bl_description = "Delete every unused data-block listed (can be undone with Ctrl+Z)"
    bl_options = {'REGISTER', 'UNDO'}

    category: StringProperty(default="", options={'SKIP_SAVE'})

    def invoke(self, context, event):
        res = _state["result"]
        items = [it for it in res.items if not self.category or it[0] == self.category]
        size = sum(it[3] for it in items)
        return context.window_manager.invoke_confirm(
            self, event, title="Purge Unused Data",
            message=f"Delete {len(items)} data-blocks (~{format_size(size)})?",
            confirm_text="Delete", icon='WARNING',
        )

    def execute(self, context):
        refresh()
        res = _state["result"]
        ids = []
        for attr, name, uid, _size, _rec, _linked in res.items:
            if self.category and attr != self.category:
                continue
            id_data = _find_id(attr, name, uid)
            if id_data is not None:
                ids.append(id_data)
        if ids:
            bpy.data.batch_remove(ids=ids)
        self.report({'INFO'}, f"Removed {len(ids)} unused data-blocks")
        refresh(force=True)
        return {'FINISHED'}


class UDB_OT_remove_one(bpy.types.Operator):
    bl_idname = "udb.remove_one"
    bl_label = "Delete Data-Block"
    bl_description = "Delete this unused data-block"
    bl_options = {'REGISTER', 'UNDO'}

    attr: StringProperty()
    name: StringProperty()
    uid: IntProperty()

    def execute(self, context):
        id_data = _find_id(self.attr, self.name, self.uid)
        if id_data is None:
            self.report({'WARNING'}, "Data-block not found")
        else:
            bpy.data.batch_remove(ids=[id_data])
        refresh(force=True)
        return {'FINISHED'}


class UDB_OT_keep(bpy.types.Operator):
    bl_idname = "udb.keep"
    bl_label = "Keep (Fake User)"
    bl_description = "Give this data-block a fake user so it is kept and no longer flagged"
    bl_options = {'REGISTER', 'UNDO'}

    attr: StringProperty()
    name: StringProperty()
    uid: IntProperty()

    def execute(self, context):
        id_data = _find_id(self.attr, self.name, self.uid)
        if id_data is not None:
            id_data.use_fake_user = True
        refresh(force=True)
        return {'FINISHED'}


class UDB_OT_show_in_outliner(bpy.types.Operator):
    bl_idname = "udb.show_in_outliner"
    bl_label = "Show in Outliner"
    bl_description = "Switch an Outliner to the Unused Data view"

    def execute(self, context):
        for area in context.screen.areas:
            if area.type == 'OUTLINER':
                area.spaces.active.display_mode = 'ORPHAN_DATA'
                area.tag_redraw()
                return {'FINISHED'}
        self.report({'WARNING'}, "No Outliner in this workspace")
        return {'CANCELLED'}


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
def _is_alert(res, prefs):
    if prefs is None:
        return res.unused_count > 0
    return res.unused_count > 0 and (
        res.percent >= prefs.alert_percent or res.unused_size >= prefs.alert_mb * 1024 * 1024
    )


class UDB_PT_unused_data(bpy.types.Panel):
    bl_idname = "UDB_PT_unused_data"
    bl_label = "Unused Data"
    bl_space_type = 'TOPBAR'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 18

    def draw(self, context):
        layout = self.layout
        res = _state["result"]
        prefs = _prefs()

        row = layout.row()
        row.label(text="Unused Data-Blocks", icon='ORPHAN_DATA')
        if prefs is not None:
            row.prop(prefs, "paused", text="", icon='PLAY' if prefs.paused else 'PAUSE', emboss=False)
        row.operator("udb.refresh", text="", icon='FILE_REFRESH', emboss=False)

        if prefs is not None and prefs.paused:
            layout.label(text="Auto-scan paused. Results are from the last scan.", icon='PAUSE')

        if not res.unused_count:
            layout.label(text="No unused data-blocks. All clean!", icon='CHECKMARK')
            layout.label(text=f"Estimated file data: ~{format_size(res.total_size)}")
            return

        col = layout.column(align=True)
        col.alert = _is_alert(res, prefs)
        col.label(text=f"{res.unused_count} unused  ·  ~{format_size(res.unused_size)}")
        col.alert = False
        col.label(text=f"{res.percent:.1f}% of ~{format_size(res.total_size)} estimated data")
        bar = layout.row()
        bar.enabled = False
        bar.prop(context.window_manager, "udb_percent", text="Share", slider=True)

        # Per category breakdown
        box = layout.box()
        box.label(text="By Type")
        for attr, (count, size) in sorted(res.by_category.items(), key=lambda kv: kv[1][1], reverse=True):
            label, icon = CATEGORY_INFO[attr]
            r = box.row(align=True)
            r.label(text=f"{label} ({count})", icon=icon)
            r.label(text=format_size(size))
            op = r.operator("udb.purge", text="", icon='TRASH', emboss=False)
            op.category = attr

        # Heaviest items
        limit = prefs.list_limit if prefs else 10
        box = layout.box()
        box.label(text="Heaviest")
        for attr, name, uid, size, recursive, linked in res.items[:limit]:
            _label, icon = CATEGORY_INFO[attr]
            r = box.row(align=True)
            text = name + ("  (via unused)" if recursive else "") + ("  [linked]" if linked else "")
            r.label(text=text, icon=icon)
            r.label(text=format_size(size))
            op = r.operator("udb.keep", text="", icon='FAKE_USER_OFF', emboss=False)
            op.attr, op.name, op.uid = attr, name, uid
            op = r.operator("udb.remove_one", text="", icon='X', emboss=False)
            op.attr, op.name, op.uid = attr, name, uid
        if res.unused_count > limit:
            box.label(text=f"… and {res.unused_count - limit} more")

        row = layout.row(align=True)
        row.operator("udb.show_in_outliner", icon='OUTLINER')
        sub = row.row(align=True)
        sub.alert = True
        sub.operator("udb.purge", text="Purge All", icon='TRASH').category = ""
        layout.label(text="Sizes are estimates. Purging can be undone (Ctrl+Z).", icon='INFO')


def draw_topbar(self, context):
    if context.region.alignment != 'RIGHT':
        return
    prefs = _prefs()
    res = _state["result"]
    paused = prefs is not None and prefs.paused
    row = self.layout.row(align=True)

    if paused:
        # Don't show stale numbers as if they were live.
        sub = row.row(align=True)
        sub.active = False
        sub.popover(panel=UDB_PT_unused_data.bl_idname, text="Paused", icon='ORPHAN_DATA')
    elif not res.unused_count:
        if prefs is None or prefs.show_when_clean:
            row.popover(panel=UDB_PT_unused_data.bl_idname, text="", icon='CHECKMARK')
    else:
        if prefs is not None and prefs.compact:
            text = str(res.unused_count)
        else:
            text = f"{res.unused_count} · {format_size(res.unused_size)} · {res.percent:.0f}%"
        sub = row.row(align=True)
        if _is_alert(res, prefs):
            # Popover buttons ignore `alert`, operator buttons turn red.
            sub.alert = True
            sub.operator("wm.call_panel", text=text, icon='ORPHAN_DATA').name = UDB_PT_unused_data.bl_idname
        else:
            sub.popover(panel=UDB_PT_unused_data.bl_idname, text=text, icon='ORPHAN_DATA')

    # Pause/resume toggle. Always shown while paused so you can resume;
    # otherwise only next to a visible flag.
    flag_visible = res.unused_count or prefs is None or prefs.show_when_clean
    if prefs is not None and (paused or (prefs.show_pause_button and flag_visible)):
        row.prop(prefs, "paused", text="", icon='PLAY' if paused else 'PAUSE')


# --------------------------------------------------------------------------
# Preferences
# --------------------------------------------------------------------------
def _prefs_update(self, context):
    _state["dirty"] = True
    _state["last_scan"] = 0.0


def _paused_update(self, context):
    if not self.paused:
        refresh(force=True)  # resume immediately with fresh numbers
    else:
        _redraw_ui()


class UDB_AP_preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    paused: BoolProperty(
        name="Pause Auto-Scan", default=False, update=_paused_update,
        description="Pause/resume automatic scanning for unused data-blocks",
    )
    show_pause_button: BoolProperty(
        name="Show Pause Button", default=True,
        description="Show a pause/resume button next to the top bar flag",
    )
    show_when_clean: BoolProperty(
        name="Show When Clean", default=True,
        description="Show a small check mark in the top bar when there is no unused data",
    )
    compact: BoolProperty(
        name="Compact", default=False,
        description="Only show the number of unused data-blocks in the top bar",
    )
    include_recursive: BoolProperty(
        name="Include Indirectly Unused", default=True, update=_prefs_update,
        description="Also count data that is only used by other unused data (like a recursive purge)",
    )
    include_linked: BoolProperty(
        name="Include Linked Data", default=False, update=_prefs_update,
        description="Also count unused data-blocks linked from other .blend files",
    )
    alert_percent: FloatProperty(
        name="Alert at %", default=5.0, min=0.0, max=100.0, subtype='PERCENTAGE',
        description="Turn the flag red when unused data exceeds this share of the file's data",
    )
    alert_mb: FloatProperty(
        name="Alert at MB", default=10.0, min=0.0,
        description="Turn the flag red when unused data exceeds this size",
    )
    scan_interval: FloatProperty(
        name="Min Scan Interval", default=2.0, min=0.5, max=60.0, subtype='TIME_ABSOLUTE', unit='TIME_ABSOLUTE',
        description="Minimum time between scans after something changed",
    )
    list_limit: IntProperty(name="Items Listed", default=10, min=1, max=100)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        col = layout.column(heading="Top Bar")
        col.prop(self, "show_when_clean")
        col.prop(self, "compact")
        col.prop(self, "show_pause_button")
        col = layout.column(heading="Detection")
        col.prop(self, "paused")
        col.prop(self, "include_recursive")
        col.prop(self, "include_linked")
        col = layout.column(heading="Alert")
        col.prop(self, "alert_percent")
        col.prop(self, "alert_mb")
        col = layout.column()
        col.prop(self, "scan_interval")
        col.prop(self, "list_limit")
        res = _state["result"]
        layout.label(text=f"Last scan took {res.scan_ms:.1f} ms", icon='TIME')


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------
classes = (
    UDB_AP_preferences,
    UDB_OT_refresh,
    UDB_OT_purge,
    UDB_OT_remove_one,
    UDB_OT_keep,
    UDB_OT_show_in_outliner,
    UDB_PT_unused_data,
)

HANDLERS = (
    (bpy.app.handlers.depsgraph_update_post, _on_change),
    (bpy.app.handlers.undo_post, _on_change),
    (bpy.app.handlers.redo_post, _on_change),
    (bpy.app.handlers.load_post, _on_load),
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.udb_percent = FloatProperty(
        subtype='PERCENTAGE', min=0.0, max=100.0, precision=1,
        get=lambda self: _state["result"].percent,
    )
    bpy.types.TOPBAR_HT_upper_bar.prepend(draw_topbar)
    for handler_list, fn in HANDLERS:
        if fn not in handler_list:
            handler_list.append(fn)
    _state["dirty"] = True
    _state["last_scan"] = 0.0
    if not bpy.app.timers.is_registered(_timer):
        bpy.app.timers.register(_timer, first_interval=0.5, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_timer):
        bpy.app.timers.unregister(_timer)
    for handler_list, fn in HANDLERS:
        if fn in handler_list:
            handler_list.remove(fn)
    bpy.types.TOPBAR_HT_upper_bar.remove(draw_topbar)
    del bpy.types.WindowManager.udb_percent
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
