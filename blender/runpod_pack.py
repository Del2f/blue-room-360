"""Makes a self-contained F1 file for cloud rendering from the saved pitch.blend.

    blender -b <work>/pitch.blend -P runpod_pack.py -- --out <dir>/f1_paradise.blend

Keeps only the PARADISE scene (plus LIB, whose objects the vegetation scatter instances),
sets the F1 camera, daytime sky and matching sun, removes unused data and packs every
external file so the .blend opens on Linux with no other files.
"""
import bpy, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[argv.index("--out") + 1]

P = bpy.data.scenes["PARADISE"]
if "ROOM" in bpy.data.scenes:
    bpy.data.scenes.remove(bpy.data.scenes["ROOM"])
day = bpy.data.worlds["day"]
P.world = day
sun = next(o for o in P.objects if o.type == "LIGHT" and o.data.type == "SUN")
sun.rotation_euler = Vector(day["sun_dir"]).to_track_quat("Z", "Y").to_euler()
sun.data.energy = 3.6
sun.data.color = (1.0, 0.95, 0.86)
P.camera = bpy.data.objects["F1"]
P.view_settings.exposure = 0.0
# LIB keeps only the originals the scatter layers instance; room furniture and the rest go
scatter_cols = {c for c in bpy.data.collections if c.name in ("grass", "bloom", "edge", "dunefoot", "shore")}
lib = bpy.data.scenes["LIB"]
for o in list(lib.objects):
    if not scatter_cols & set(o.users_collection) and P.objects.get(o.name) is None:
        bpy.data.objects.remove(o)
for w in list(bpy.data.worlds):
    if w != day:
        bpy.data.worlds.remove(w)
bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

missing = [im.name for im in bpy.data.images if im.source == "FILE" and not im.packed_file and not os.path.exists(bpy.path.abspath(im.filepath))]
print("MISSING", missing)
bpy.ops.file.pack_all()
unpacked = [im.name for im in bpy.data.images if im.source == "FILE" and not im.packed_file]
print("UNPACKED", unpacked)
print("IMAGES", len(bpy.data.images), "OBJECTS", len(bpy.data.objects), "SCENES", [s.name for s in bpy.data.scenes])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=True)
print("PACKED", OUT, os.path.getsize(OUT))
