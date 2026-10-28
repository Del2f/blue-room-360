"""Packs everything the 360 world render needs into one zip for a Linux GPU server (RunPod).

    python pack_world_job.py <work dir> <refs/official dir> <out zip>

The scene script and its helpers (terrain.py, layout.json) come from this folder; only the asset
folders/HDRIs they name are taken from <work dir>/assets. Inside the zip:
akb/scripts/{pitch_frames.py,terrain.py,layout.json}, akb/assets/..., akb/fonts/..., akb/refs/*, run_world.sh
"""
import os, re, sys, zipfile

WORK, REFS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
here = os.path.dirname(os.path.abspath(__file__))
scripts = [os.path.join(here, f) for f in ("pitch_frames.py", "terrain.py", "layout.json")]
src = "".join(open(f, encoding="utf-8").read() for f in scripts)
names = set(re.findall(r'"([A-Za-z0-9_]+)"', src))
hdrs = set(re.findall(r'"([A-Za-z0-9_]+\.hdr)"', src))
A = os.path.join(WORK, "assets")
files = []
for kind in ("m", "t"):
    for d in sorted(os.listdir(os.path.join(A, kind))):
        if d in names:
            for root, _, fs in os.walk(os.path.join(A, kind, d)):
                files += [os.path.join(root, f) for f in fs if not f.endswith(".part")]
for h in sorted(os.listdir(os.path.join(A, "h"))):
    if h in hdrs:
        files.append(os.path.join(A, "h", h))
files += [os.path.join(WORK, "fonts", f) for f in os.listdir(os.path.join(WORK, "fonts"))]
missing = sorted(hdrs - set(os.listdir(os.path.join(A, "h"))))
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_STORED) as z:
    for f in scripts:
        z.write(f, "akb/scripts/" + os.path.basename(f))
    z.write(os.path.join(here, "run_world.sh"), "run_world.sh")
    for f in files:
        z.write(f, "akb/" + os.path.relpath(f, WORK).replace(os.sep, "/"))
    for f in os.listdir(REFS):
        z.write(os.path.join(REFS, f), "akb/refs/" + f)
print("PACKED", OUT, len(files), "asset files", round(os.path.getsize(OUT) / 2 ** 20), "MB", "| HDRIs not found:", missing)
