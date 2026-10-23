"""Renders everything the web viewer needs from akmu.blend.

    blender -b <work>/akmu.blend -P render.py -- --work <work> --mode <mode> [options]

modes
  preview  quick perspective stills to judge the look           --space dunes|room --samples 64
  pre      door / window "portal" images (EXR) used in the scenes
  faces    6 cube faces of the 360° view                         --space --size 4096 --samples 512 [--bloom 1] [--only px,nx]
  masks    6 cube faces of flat hotspot IDs (for hover/click)    --space --size 1024
  video    door walk clips (MP4)                                 --clip d2r_a|d2r_b|r2d_a|r2d_b --samples 128
"""
import bpy, math, os, sys, json
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
A = {argv[i]: argv[i + 1] for i in range(0, len(argv) - 1, 2)}
WORK, MODE = A["--work"], A["--mode"]
REN = os.path.join(WORK, "renders")
OUT = os.path.join(WORK, "out")
os.makedirs(OUT, exist_ok=True)
SCN = {"dunes": bpy.data.scenes["DUNES"], "room": bpy.data.scenes["ROOM"]}
SPAWN = {"dunes": Vector((0, 0, 1.6)), "room": Vector((0.7, -1.0, 1.5))}
KEYS = {"dunes": ["door", "tour", "shop", "tent", "breakfast", "boat", "rumor", "flowers"],
        "room": ["doorBack", "music", "video", "contact", "rock", "notes"]}
# cube faces in the viewer's Y-up frame: forward, up
FACES = {"px": ((1, 0, 0), (0, 1, 0)), "nx": ((-1, 0, 0), (0, 1, 0)), "py": ((0, 1, 0), (0, 0, 1)),
         "ny": ((0, -1, 0), (0, 0, -1)), "pz": ((0, 0, 1), (0, 1, 0)), "nz": ((0, 0, -1), (0, 1, 0))}


def b3(v):  # viewer (x, y, z) -> blender (x, -z, y)
    return Vector((v[0], -v[2], v[1]))


def t3(v):
    return [round(v.x, 5), round(v.z, 5), round(-v.y, 5)]


def gpu():
    p = bpy.context.preferences.addons["cycles"].preferences
    p.compute_device_type = "OPTIX"
    p.get_devices()
    for d in p.devices:
        d.use = d.type == "OPTIX"


def reload_images():
    for im in bpy.data.images:
        if im.source == "FILE" and im.filepath:
            try:
                im.reload()
            except Exception:
                pass


def make_cam(scene, name, loc, fwd, up=Vector((0, 0, 1)), fov_deg=90.0, fit="AUTO"):
    cd = bpy.data.cameras.new(name)
    cd.clip_start, cd.clip_end = 0.03, 4000
    cd.sensor_fit = fit
    cd.angle = math.radians(fov_deg)
    ob = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(ob)
    set_cam(ob, loc, fwd, up)
    scene.camera = ob
    return ob


def set_cam(ob, loc, fwd, up=Vector((0, 0, 1))):
    f = Vector(fwd).normalized()
    r = f.cross(Vector(up)).normalized()
    u = r.cross(f)
    ob.matrix_world = Matrix.Translation(Vector(loc)) @ Matrix((r, u, -f)).transposed().to_4x4()


def out_settings(scene, fmt, w, h, quality=92):
    scene.render.resolution_x, scene.render.resolution_y = w, h
    s = scene.render.image_settings
    s.media_type = "IMAGE"
    s.file_format = fmt
    if fmt == "JPEG":
        s.quality = quality
        s.color_mode = "RGB"
    elif fmt == "PNG":
        s.color_mode = "RGB"
        s.color_depth = "8"
    elif fmt == "OPEN_EXR":
        s.color_mode = "RGB"
        s.color_depth = "16"


def render_to(scene, path):
    scene.render.filepath = path
    bpy.context.window_manager  # noqa: keeps context alive in background
    bpy.ops.render.render(write_still=True, scene=scene.name)
    print("WROTE", path)


def set_flowers(scene, bloom):
    for o in scene.objects:
        if "flower" in o.keys():
            s = o["flower"] * (1.0 if bloom else 0.22)
            o.scale = (s, s, s)


def door(scene):
    g = bpy.data.objects["door" if scene.name == "DUNES" else "door_back"]
    rz = g.rotation_euler.z
    f = Vector((math.sin(rz), -math.cos(rz), 0))
    return g, bpy.data.objects[g["hinge"]], f


gpu()
reload_images()
for _sc in SCN.values():  # objects in non-active scenes load with stale matrices in background mode
    _sc.view_layers[0].update()

if MODE == "preview":
    sp = A.get("--space", "dunes")
    sc = SCN[sp]
    sc.cycles.samples = int(A.get("--samples", 64))
    set_flowers(SCN["dunes"], False)
    out_settings(sc, "JPEG", int(A.get("--w", 1280)), int(A.get("--h", 720)))
    views = {"dunes": {"front": (0.0, -0.05), "left": (math.radians(70), -0.05), "right": (-math.radians(70), -0.08), "back": (math.pi, -0.08)},
             "room": {"front": (0.15, -0.12), "left": (math.radians(75), -0.12), "right": (-math.radians(60), -0.15), "back": (math.pi, -0.08)}}[sp]
    only = A.get("--views")
    cam = make_cam(sc, "pv", SPAWN[sp], Vector((0, 1, 0)), fov_deg=58, fit="VERTICAL")
    for name, (yaw, pitch) in views.items():
        if only and name not in only.split(","):
            continue
        fwd = Vector((-math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
        set_cam(cam, SPAWN[sp], fwd)
        render_to(sc, os.path.join(OUT, "preview", f"{sp}_{name}.jpg"))

elif MODE == "pre":
    d, r = SCN["dunes"], SCN["room"]
    set_flowers(d, False)
    for sc in (d, r):
        sc.cycles.samples = int(A.get("--samples", 384))
    # window view: dunes and the sea seen from a little rise
    gz = 0.0
    cam = make_cam(d, "pre_win", Vector((10, -25, 4.5)), Vector((-0.9, -0.45, -0.16)), fov_deg=72, fit="HORIZONTAL")
    out_settings(d, "OPEN_EXR", 2048, 1138)
    render_to(d, os.path.join(REN, "pre_window_view.exr"))
    # dunes as seen standing in the dune doorway (shown inside the room's back door)
    g, h, f = door(d)
    h.rotation_euler.z = -1.42  # fully open so the leaf is out of the way
    d.view_layers[0].update()
    p = g.matrix_world.translation + f * 0.25 + Vector((0, 0, 1.45))
    cam = make_cam(d, "pre_door", p, f, fov_deg=64, fit="VERTICAL")
    out_settings(d, "OPEN_EXR", 900, 2000)
    render_to(d, os.path.join(REN, "pre_dunes_from_door.exr"))
    # the room as seen from its own doorway (shown inside the dune door)
    g, h, f = door(r)
    h.rotation_euler.z = -1.42
    r.view_layers[0].update()
    p = g.matrix_world.translation + f * 0.3 + Vector((0, 0, 1.4))
    cam = make_cam(r, "pre_door", p, f, fov_deg=64, fit="VERTICAL")
    out_settings(r, "OPEN_EXR", 900, 2000)
    render_to(r, os.path.join(REN, "pre_room_from_door.exr"))

elif MODE == "faces":
    sp = A["--space"]
    sc = SCN[sp]
    bloom = A.get("--bloom") == "1"
    set_flowers(SCN["dunes"], bloom)
    sc.cycles.samples = int(A.get("--samples", 512))
    size = int(A.get("--size", 4096))
    out_settings(sc, "JPEG", size, size, quality=int(A.get("--quality", 90)))
    cam = make_cam(sc, "face", SPAWN[sp], Vector((0, 1, 0)), fov_deg=90)
    only = A.get("--only")
    folder = os.path.join(OUT, "faces", sp + ("_bloom" if bloom else ""), str(size))
    for name, (fw, up) in FACES.items():
        if only and name not in only.split(","):
            continue
        set_cam(cam, SPAWN[sp], b3(fw), b3(up))
        render_to(sc, os.path.join(folder, name + ".jpg"))

elif MODE == "masks":
    sp = A["--space"]
    sc = SCN[sp]
    set_flowers(SCN["dunes"], True)
    size = int(A.get("--size", 1024))
    ids = {k: i + 1 for i, k in enumerate(KEYS[sp])}

    def emit(name, rgb):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        e = nt.nodes.new("ShaderNodeEmission")
        e.inputs["Color"].default_value = (*rgb, 1)
        nt.links.new(e.outputs[0], o.inputs["Surface"])
        return m

    black = emit("mask_black", (0, 0, 0))
    mats = {k: emit("mask_" + k, (i / 16.0, 0, 0)) for k, i in ids.items()}
    for o in sc.objects:
        if o.get("haze"):
            o.hide_render = True
            continue
        if o.type not in ("MESH", "FONT", "CURVE"):
            continue
        m = mats.get(o.get("akey"), black)
        if len(o.material_slots) == 0:
            o.data.materials.append(None)
        for s in o.material_slots:
            s.link = "OBJECT"
            s.material = m
        for p in ("visible_diffuse", "visible_glossy", "visible_shadow", "visible_transmission", "visible_volume_scatter"):
            setattr(o, p, False)
        o.visible_camera = True
    w = bpy.data.worlds.new("mask_world")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    sc.world = w
    c = sc.cycles
    c.samples = 1
    c.use_adaptive_sampling = False
    c.use_denoising = False
    c.filter_width = 0.01
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0
    sc.view_settings.gamma = 1
    out_settings(sc, "PNG", size, size)
    cam = make_cam(sc, "mask", SPAWN[sp], Vector((0, 1, 0)), fov_deg=90)
    for name, (fw, up) in FACES.items():
        set_cam(cam, SPAWN[sp], b3(fw), b3(up))
        render_to(sc, os.path.join(OUT, "masks", sp, name + ".png"))
    srgb = lambda v: 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    with open(os.path.join(OUT, "masks", sp, "ids.json"), "w") as f:
        json.dump({k: round(255 * srgb(i / 16.0)) for k, i in ids.items()}, f)

elif MODE == "video":
    clip = A["--clip"]
    sp = "dunes" if clip in ("d2r_a", "r2d_b") else "room"
    sc = SCN[sp]
    # frame changes are evaluated on the active scene only, so make this clip's scene the only one
    for other in [s for s in bpy.data.scenes if s != sc]:
        bpy.data.scenes.remove(other)
    sc.view_layers[0].update()
    set_flowers(sc, False)
    sc.cycles.samples = int(A.get("--samples", 128))
    fps = 30
    g, hinge, f = door(sc)
    dpos = g.matrix_world.translation.copy()
    spawn = SPAWN[sp]
    if clip == "d2r_a":
        n = 78
        look_door = (dpos + Vector((0, 0, 1.15))) - spawn
        keys = [(1, spawn, look_door, 60), (n, dpos + f * 1.5 + Vector((0, 0, 1.25)), -f + Vector((0, 0, -0.02)), 50)]
        hk = [(8, -0.38), (40, -1.42)]
    elif clip == "d2r_b":
        n = 72
        start = dpos + f * 0.3 + Vector((0, 0, 1.5))
        keys = [(1, start, f, 44), (n, spawn, Vector((0.12, 1, -0.06)), 60)]
        hk = [(1, -1.42), (50, -0.38)]
    elif clip == "r2d_a":
        n = 78
        look_door = (dpos + Vector((0, 0, 1.15))) - spawn
        keys = [(1, spawn, look_door, 60), (n, dpos + f * 1.5 + Vector((0, 0, 1.25)), -f + Vector((0, 0, -0.02)), 50)]
        hk = [(8, -0.38), (40, -1.42)]
    else:  # r2d_b: out of the dune door and back to the spawn
        n = 96
        start = dpos + f * 0.3 + Vector((0, 0, 1.55))
        end_dir = Vector((f.x, f.y, -0.03))
        keys = [(1, start, f, 44), (n, spawn, end_dir, 60)]
        hk = [(1, -1.42), (60, -0.38)]
    cam = make_cam(sc, "vid", keys[0][1], keys[0][2], fov_deg=keys[0][3], fit="VERTICAL")
    prev = cam.rotation_euler.copy()
    for fr, loc, fwd, fov in keys:
        set_cam(cam, loc, fwd)
        cam.rotation_euler = cam.matrix_world.to_euler("XYZ", prev)  # avoid a 360° spin between keys
        prev = cam.rotation_euler.copy()
        cam.data.angle = math.radians(fov)
        cam.keyframe_insert("location", frame=fr)
        cam.keyframe_insert("rotation_euler", frame=fr)
        cam.data.keyframe_insert("lens", frame=fr)
    for fr, rz in hk:
        hinge.rotation_euler.z = rz
        hinge.keyframe_insert("rotation_euler", frame=fr)
    sc.frame_start, sc.frame_end = 1, n
    sc.render.fps = fps
    sc.render.resolution_x, sc.render.resolution_y = int(A.get("--w", 1920)), int(A.get("--h", 1080))
    if A.get("--stills"):  # quick framing check: first / middle / last frame as JPEG
        out_settings(sc, "JPEG", sc.render.resolution_x, sc.render.resolution_y)
        for fr in (1, n // 2, n):
            sc.frame_set(fr)
            render_to(sc, os.path.join(OUT, "stills", f"{clip}_{fr:03d}.jpg"))
        print("RENDER DONE stills")
        sys.exit(0)
    s = sc.render.image_settings
    s.media_type = "VIDEO"
    s.file_format = "FFMPEG"
    ff = sc.render.ffmpeg
    ff.format = "MPEG4"
    ff.codec = "H264"
    ff.constant_rate_factor = "HIGH"
    ff.ffmpeg_preset = "GOOD"
    ff.gopsize = 15
    ff.audio_codec = "NONE"
    path = os.path.join(OUT, "video", clip + ".mp4")
    sc.render.filepath = path
    bpy.ops.render.render(animation=True, scene=sc.name)
    # first / last view for the viewer so it can line up its own camera before and after the clip
    meta_path = os.path.join(OUT, "video", "clips.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    first, last = keys[0], keys[-1]
    meta[clip] = {"frames": n, "fps": fps, "start": {"dir": t3(Vector(first[2]).normalized()), "fov": first[3]},
                  "end": {"dir": t3(Vector(last[2]).normalized()), "fov": last[3]}}
    json.dump(meta, open(meta_path, "w"), indent=1)
    print("WROTE", path)

print("RENDER DONE", MODE)
