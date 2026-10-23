"""Turns the raw renders into the v3 viewer's media folder.

    blender -b --factory-startup -P package.py -- --work <work> --dest <repo>/akmu-concept/v3/media

Cube faces become WebP at 4096 (desktop) and 2048 (phones); masks, door clips and
metadata are copied alongside.
"""
import bpy, os, sys, json, shutil

argv = sys.argv[sys.argv.index("--") + 1:]
A = {argv[i]: argv[i + 1] for i in range(0, len(argv) - 1, 2)}
WORK, DEST = A["--work"], A["--dest"]
OUT = os.path.join(WORK, "out")
QUALITY = int(A.get("--quality", 82))
scene = bpy.context.scene
s = scene.render.image_settings
s.file_format = "WEBP"
s.quality = QUALITY
s.color_mode = "RGB"

total = 0
for space in ("dunes", "dunes_bloom", "room"):
    src = os.path.join(OUT, "faces", space, "4096")
    if not os.path.isdir(src):
        continue
    names = [f for f in sorted(os.listdir(src)) if f.endswith(".jpg")]
    if A.get("--only") and space not in A["--only"].split(","):
        continue
    for f in names:
        if not f.endswith(".jpg"):
            continue
        name = f[:-4]
        im = bpy.data.images.load(os.path.join(src, f))
        for size in (4096, 2048):
            d = os.path.join(DEST, space, str(size))
            os.makedirs(d, exist_ok=True)
            if size != im.size[0]:
                im.scale(size, size)
            path = os.path.join(d, name + ".webp")
            im.save_render(path, scene=scene)
            total += os.path.getsize(path)
        bpy.data.images.remove(im)
        print("FACE", space, name)

ids = {}
for space in ("dunes", "room"):
    src = os.path.join(OUT, "masks", space)
    if not os.path.exists(os.path.join(src, "ids.json")):
        continue
    d = os.path.join(DEST, "masks", space)
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(src):
        if f.endswith(".png"):
            shutil.copy2(os.path.join(src, f), d)
    ids[space] = json.load(open(os.path.join(src, "ids.json")))

vd = os.path.join(DEST, "video")
os.makedirs(vd, exist_ok=True)
for f in (os.listdir(os.path.join(OUT, "video")) if os.path.isdir(os.path.join(OUT, "video")) else []):
    if f.endswith(".mp4"):
        shutil.copy2(os.path.join(OUT, "video", f), vd)

meta = json.load(open(os.path.join(WORK, "meta.json"), encoding="utf-8"))
cj = os.path.join(OUT, "video", "clips.json")
meta["clips"] = json.load(open(cj)) if os.path.exists(cj) else {}
meta["ids"] = ids
meta["ext"] = "webp"
bd = os.path.join(OUT, "faces", "dunes_bloom", "4096")
meta["bloomFaces"] = sorted(f[:-4] for f in os.listdir(bd) if f.endswith(".jpg")) if os.path.isdir(bd) else []
meta["available"] = [sp for sp in ("dunes", "room") if sp in ids and len([f for f in os.listdir(os.path.join(OUT, "faces", sp, "4096")) if f.endswith(".jpg")]) == 6]
with open(os.path.join(DEST, "meta.json"), "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=1)
print("PACKAGE DONE faces MB", round(total / 1048576, 1))
