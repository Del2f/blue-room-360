"""Single-frame Cycles benchmark of the packed F1 paradise scene.

    blender -b f1_paradise.blend -P render_f1.py -- [--out out/F1.png] [--samples 256] [--w 1920 --h 1080] [--device OPTIX|CUDA|CPU]

Prints the GPU devices found, then render time. The file is self-contained (all images packed).
"""
import bpy, os, sys, time

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
A = {argv[i]: argv[i + 1] for i in range(0, len(argv) - 1, 2)}
out = os.path.abspath(A.get("--out", "out/F1_paradise.png"))
os.makedirs(os.path.dirname(out), exist_ok=True)

scene = bpy.data.scenes["PARADISE"]
want = A.get("--device", "OPTIX")
prefs = bpy.context.preferences.addons["cycles"].preferences
device = "CPU"
for kind in ([want] if want != "CPU" else []) + ["OPTIX", "CUDA"]:
    try:
        prefs.compute_device_type = kind
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == kind]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == kind
            device = kind
            print("DEVICES", kind, [d.name for d in gpus])
            break
    except Exception as e:
        print("DEVICE", kind, "unavailable:", e)
c = scene.cycles
c.device = "GPU" if device != "CPU" else "CPU"
c.samples = int(A.get("--samples", 256))
scene.render.resolution_x = int(A.get("--w", 1920))
scene.render.resolution_y = int(A.get("--h", 1080))
scene.render.resolution_percentage = 100
s = scene.render.image_settings
s.file_format = "PNG"
s.color_depth = "16"
scene.render.filepath = out
print("RENDER", device, scene.render.resolution_x, "x", scene.render.resolution_y, "samples", c.samples, "blender", bpy.app.version_string)
t0 = time.time()
bpy.ops.render.render(write_still=True, scene=scene.name)
print("RENDER_SECONDS %.1f" % (time.time() - t0), out)
