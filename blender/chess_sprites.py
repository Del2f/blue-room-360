"""Board and piece images for the playable chess in the room, rendered from the same Poly Haven chess_set
the room shows.

blender -b --factory-startup -P chess_sprites.py -- <chess_set.gltf> <out dir>

Writes board.jpg (the 8x8 playing area seen from above, white at the bottom) and <w|b><k|q|r|b|n|p>.png
(each piece seen from the side, slightly from above, on a transparent background).
"""
import bpy, math, os, sys
from mathutils import Vector

src, out = sys.argv[sys.argv.index("--") + 1:][:2]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=src)
bpy.context.view_layer.update()
objs = {o.name: o for o in sc.objects if o.type == "MESH"}


def centre(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return sum(pts, Vector()) / 8, min(p.z for p in pts), max(p.z for p in pts)


# the board's grid from the rooks standing on the corners
ra, rb = centre(objs["piece_rook_white_01"])[0], centre(objs["piece_rook_white_02"])[0]
rc = centre(objs["piece_rook_black_01"])[0]
files_dir = (rb - ra).normalized()                 # along the white back rank
sq = (rb - ra).length / 7
toward_black = rc - ra
toward_black -= files_dir * toward_black.dot(files_dir)
ranks_dir = toward_black.normalized()
mid = ra + files_dir * 3.5 * sq + ranks_dir * 3.5 * sq
board_top = centre(objs["board"])[2]
print("SQUARE", round(sq, 4), "files", tuple(round(v, 3) for v in files_dir), "ranks", tuple(round(v, 3) for v in ranks_dir))

# light and render settings
w = bpy.data.worlds.new("w")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.92, 0.88, 0.8, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.55
for name, rot, energy, size in (("key", (math.radians(50), 0, math.radians(-35)), 260, 0.35), ("fill", (math.radians(65), 0, math.radians(140)), 90, 0.6)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.size = energy, size
    lo = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(lo)
    lo.rotation_euler = rot
    lo.location = mid + lo.rotation_euler.to_matrix() @ Vector((0, 0, 0.8))   # its -Z looks back at the board
sc.render.engine = "CYCLES"
sc.cycles.samples = 96
sc.cycles.use_denoising = True
try:
    sc.cycles.device = "GPU"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
except Exception:
    pass
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Base Contrast"
cd = bpy.data.cameras.new("cam")
cd.type = "ORTHO"
cam = bpy.data.objects.new("cam", cd)
sc.collection.objects.link(cam)
sc.camera = cam


def aim(loc, target, up=Vector((0, 0, 1))):
    cam.location = loc
    cam.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()


# 1. the board from above, white at the bottom, cropped to the 64 squares
for o in objs.values():
    o.hide_render = o.name != "board"
aim(mid + Vector((0, 0, 2.0)), mid)
# turn the camera so the files run left to right and white sits at the bottom of the image
up = ranks_dir
cam.rotation_euler = (Vector((0, 0, -1))).to_track_quat("-Z", "Y").to_euler()
right = files_dir
m = cam.rotation_euler.to_matrix()
ang = math.atan2(right.dot(m.col[1]), right.dot(m.col[0]))
cam.rotation_euler.rotate_axis("Z", ang)
cd.ortho_scale = 8 * sq
sc.render.resolution_x = sc.render.resolution_y = 1024
sc.render.film_transparent = False
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 90
sc.render.filepath = os.path.join(out, "board.jpg")
bpy.ops.render.render(write_still=True)

# 2. one sprite per piece, from the side and a little above, transparent background
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.render.resolution_x = sc.render.resolution_y = 256
sc.cycles.samples = 64
KIND = {"king": "k", "queen": "q", "rook": "r", "bishop": "b", "knight": "n", "pawn": "p"}
king_h = centre(objs["piece_king_white"])[2] - centre(objs["piece_king_white"])[1]
for colour in ("white", "black"):
    for kind, letter in KIND.items():
        name = next(n for n in objs if n.startswith("piece_%s_%s" % (kind, colour)))
        o = objs[name]
        for p in objs.values():
            p.hide_render = p is not o
        c, z0, z1 = centre(o)
        target = Vector((c.x, c.y, z0 + king_h * 0.5))
        # look along the ranks, from white's right-hand side, so the knights show their profile
        view = (-files_dir * math.cos(math.radians(14)) + Vector((0, 0, math.sin(math.radians(14))))).normalized()
        aim(target + view * 1.0, target)
        cd.ortho_scale = king_h * 1.12
        sc.render.filepath = os.path.join(out, ("w" if colour == "white" else "b") + letter + ".png")
        bpy.ops.render.render(write_still=True)
print("CHESS SPRITES DONE")
