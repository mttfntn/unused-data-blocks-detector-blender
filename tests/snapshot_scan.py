"""
Behaviour snapshot used to prove that refactors don't change results.

Builds a broad, deterministic set of data (every scanned type, used, unused,
indirectly unused, fake users, packed/external/float images, layered actions,
linked library data) and records what the scan reports under every
combination of the detection settings, plus the size estimate of every
data-block. Writes JSON.

    blender --background --factory-startup --python tests/snapshot_scan.py -- <addon_parent_dir> <out.json>

Run it once on the old code and once on the new code and diff the two files.
"""

import json
import os
import sys
import tempfile

import addon_utils
import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, os.path.abspath(ARGS[0]))
OUT = ARGS[1]
MODULE = "unused_data_blocks"


def build_scene(tmp):
    D = bpy.data
    # Linked data: a library file with a material and a node group.
    lib_path = os.path.join(tmp, "lib.blend")
    m = D.materials.new("LibMat")
    ng = D.node_groups.new("LibGroup", 'ShaderNodeTree')
    m.use_fake_user = ng.use_fake_user = True
    D.libraries.write(lib_path, {m, ng})
    D.materials.remove(m); D.node_groups.remove(ng)
    with D.libraries.load(lib_path, link=True) as (src, dst):
        dst.materials = ["LibMat"]
        dst.node_groups = ["LibGroup"]

    # External image file on disk, loaded lazily (not in memory).
    ext = D.images.new("ExtSrc", 40, 30)
    ext.filepath_raw = os.path.join(tmp, "ext.png"); ext.file_format = 'PNG'; ext.save()
    D.images.remove(ext)
    D.images.load(os.path.join(tmp, "ext.png"))                 # unused, external

    D.images.new("GenImg", 128, 64)                             # unused, generated
    D.images.new("FloatImg", 32, 32, float_buffer=True)         # unused, float
    p = D.images.new("PackedImg", 16, 16); p.pack()             # unused, packed

    # Meshes: unused primitive with a material used only by it.
    import bmesh
    me = D.meshes.new("SphereMesh")
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1)
    bm.to_mesh(me); bm.free()
    mat = D.materials.new("OnlyOnOrphan")
    me.materials.append(mat)
    me.attributes.new("custom", 'FLOAT_COLOR', 'POINT')
    D.meshes.new("EmptyMesh")

    # A used mesh on the scene for the total.
    used = D.objects.new("UsedObj", me.copy())
    bpy.context.scene.collection.objects.link(used)

    # Chain: collection -> object -> curve, nothing linked to the scene.
    cu = D.curves.new("ChainCurve", 'CURVE')
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(4)
    sp2 = cu.splines.new('POLY'); sp2.points.add(7)
    ob = D.objects.new("ChainObj", cu)
    col = D.collections.new("ChainCol"); col.objects.link(ob)

    # Layered action with keys, unused.
    host = D.objects.new("AnimHost", None)
    bpy.context.scene.collection.objects.link(host)
    for f in (1, 5, 9, 13):
        host.location = (f, 0, 0); host.keyframe_insert("location", frame=f)
    act = host.animation_data.action
    host.animation_data.action = None
    act.name = "OrphanAction"

    # Other types, unused.
    D.hair_curves.new("Hair")
    D.pointclouds.new("Points")
    D.volumes.new("Vol")
    D.grease_pencils.new("GP")
    D.lattices.new("Lat")
    D.metaballs.new("Meta")
    D.lights.new("Lamp", 'POINT')
    D.cameras.new("Cam")
    D.speakers.new("Spk")
    D.worlds.new("Wrld")
    D.textures.new("Tex", 'CLOUDS')
    D.particles.new("Parts")
    D.palettes.new("Pal")
    D.linestyles.new("LS")
    D.masks.new("Msk")
    arm = D.armatures.new("Arm")
    tree = D.node_groups.new("Geo", 'GeometryNodeTree')
    for _ in range(3):
        tree.nodes.new('NodeFrame')

    # Kept: fake user, should never be flagged.
    keep = D.materials.new("FakeUserMat"); keep.use_fake_user = True
    return arm


def snapshot():
    mod = sys.modules[MODULE]
    prefs = bpy.context.preferences.addons[MODULE].preferences
    out = {"sizes": {}, "scans": {}}
    for attr, id_data in mod._iter_ids():
        key = f"{attr}:{id_data.name}:{id_data.library.name if id_data.library else ''}"
        out["sizes"][key] = mod.estimate_size(attr, id_data)
    for rec in (True, False):
        for linked in (False, True):
            prefs.include_recursive, prefs.include_linked = rec, linked
            res = mod.scan()
            out["scans"][f"recursive={rec},linked={linked}"] = {
                "items": sorted([it[0], it[1], it[3], it[4], it[5]] for it in res.items),
                "by_category": res.by_category,
                "unused_count": res.unused_count,
                "unused_size": res.unused_size,
                "total_size": res.total_size,
                "percent": round(res.percent, 9),
            }
    # Same scan with the module registered directly (no add-on preferences),
    # which takes the `prefs is None` defaults path.
    addon_utils.disable(MODULE, default_set=True)
    mod.register()
    assert mod._prefs() is None
    res = mod.scan()
    out["scans"]["no_prefs"] = {
        "items": sorted([it[0], it[1], it[3], it[4], it[5]] for it in res.items),
        "unused_count": res.unused_count, "unused_size": res.unused_size,
        "total_size": res.total_size, "alert": mod._is_alert(res, None),
    }
    mod.unregister()
    return out


addon_utils.enable(MODULE, default_set=True)
with tempfile.TemporaryDirectory() as tmp:
    build_scene(tmp)
    data = snapshot()
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1, sort_keys=True)
print("snapshot:", len(data["sizes"]), "data-blocks,", len(data["scans"]), "scans ->", OUT)
sys.stdout.flush()
os._exit(0)
