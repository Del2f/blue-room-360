"""Builds the two spaces of the '소문의 낙원' concept in Blender (Cycles).

    blender -b --factory-startup -P build_scenes.py -- --work <dir>

<dir> must contain assets/ (Poly Haven CC0 downloads) and fonts/. The script writes
<dir>/akmu.blend and <dir>/meta.json (camera + hotspot data for the web viewer).

Coordinates: Blender is Z-up. The web viewer is Y-up; three(x, y, z) == blender(x, -z, y).
"""
import bpy, bmesh, math, os, sys, json
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ARGS = {argv[i]: argv[i + 1] for i in range(0, len(argv) - 1, 2)}
WORK = ARGS["--work"]
ASSETS, FONTS, REN = (os.path.join(WORK, d) for d in ("assets", "fonts", "renders"))
os.makedirs(REN, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
LIB = bpy.context.scene
LIB.name = "LIB"
D = bpy.data.scenes.new("DUNES")
R = bpy.data.scenes.new("ROOM")
TAU = math.tau


# ---------------------------------------------------------------- helpers
def smooth_np(x, a, b):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def dune_h(x, y):
    """Same dune field as the realtime v2 (three z = -y)."""
    z = -np.asarray(y, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    d = np.hypot(x, z)
    eps = 0.0004 + 0.03 * smooth_np(d, 40, 220)  # soften knife-edge crests far away (no aliasing)
    crest = (1 - np.sqrt(np.sin(x * 0.026 + z * 0.011 + np.sin(z * 0.03) * 1.4) ** 2 + eps)) ** 2.4
    h = crest * 8 + np.sin(x * 0.035 + np.sin(z * 0.02) * 2.2) * 1.5 + np.sin((x * 0.6 + z) * 0.018 + 1.3) * 2.4 + 3
    h = h * smooth_np(d, 12, 60)
    h = h + 0.3 * np.sin(x * 0.23 + z * 0.1) * np.sin(z * 0.19) * smooth_np(d, 3, 14)
    sea = smooth_np(-x, 300, 520)
    return h * (1 - sea) - sea * 3


def ground(x, y):
    return float(dune_h(x, y))


def face_spawn(px, py):
    """Z rotation that turns a model's front (-Y) toward the dune spawn at the origin."""
    return math.atan2(-px, py)


def link(ob, scene, parent=None):
    scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def empty(name, scene, loc=(0, 0, 0), rz=0.0, parent=None):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    e.rotation_euler = (0, 0, rz)
    return link(e, scene, parent)


def tag(root, key):
    root["akey"] = key
    for o in root.children_recursive:
        o["akey"] = key


def node(nt, kind, **props):
    n = nt.nodes.new(kind)
    for k, v in props.items():
        setattr(n, k, v)
    return n


def load_img(path, non_color=False):
    im = bpy.data.images.load(path, check_existing=True)
    if non_color:
        im.colorspace_settings.name = "Non-Color"
    return im


def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree, m.node_tree.nodes["Principled BSDF"]


def setin(bsdf, name, value):
    if name in bsdf.inputs:
        bsdf.inputs[name].default_value = value


def mix_rgb(nt, blend, fac=1.0):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = blend
    n.inputs[0].default_value = fac
    ins = [s for s in n.inputs if s.type == "RGBA"]
    out = [s for s in n.outputs if s.type == "RGBA"][0]
    return ins[0], ins[1], out


def pbr(name, tdir, scale=1.0, box=False, tint=None, hsv=None, rough=1.0, nstr=1.0, coat=0.0, sheen=0.0):
    m, nt, b = new_mat(name)
    tc = node(nt, "ShaderNodeTexCoord")
    mp = node(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs["Object" if box else "UV"], mp.inputs["Vector"])

    def tex(f, nc):
        n = node(nt, "ShaderNodeTexImage")
        n.image = load_img(os.path.join(ASSETS, "t", tdir, f), nc)
        if box:
            n.projection = "BOX"
            n.projection_blend = 0.3
        nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
        return n

    dif, arm, nor = tex("diff.jpg", False), tex("arm.jpg", True), tex("nor.jpg", True)
    col = dif.outputs["Color"]
    if hsv:
        h = node(nt, "ShaderNodeHueSaturation")
        h.inputs["Hue"].default_value, h.inputs["Saturation"].default_value, h.inputs["Value"].default_value = hsv
        nt.links.new(col, h.inputs["Color"])
        col = h.outputs["Color"]
    if tint:
        a, bb, o = mix_rgb(nt, "MULTIPLY")
        nt.links.new(col, a)
        bb.default_value = (*tint, 1)
        col = o
    nt.links.new(col, b.inputs["Base Color"])
    sep = node(nt, "ShaderNodeSeparateColor")
    nt.links.new(arm.outputs["Color"], sep.inputs["Color"])
    mm = node(nt, "ShaderNodeMath", operation="MULTIPLY")
    mm.inputs[1].default_value = rough
    nt.links.new(sep.outputs[1], mm.inputs[0])
    nt.links.new(mm.outputs[0], b.inputs["Roughness"])
    nm = node(nt, "ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = nstr
    nt.links.new(nor.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    setin(b, "Coat Weight", coat)
    setin(b, "Sheen Weight", sheen)
    return m


def flat(name, color, rough=0.5, metal=0.0, coat=0.0, sheen=0.0, trans=0.0, ior=1.45, spec=0.5):
    m, nt, b = new_mat(name)
    setin(b, "Base Color", (*color, 1))
    setin(b, "Roughness", rough)
    setin(b, "Metallic", metal)
    setin(b, "Coat Weight", coat)
    setin(b, "Sheen Weight", sheen)
    setin(b, "Transmission Weight", trans)
    setin(b, "IOR", ior)
    setin(b, "Specular IOR Level", spec)
    return m


def emission_image(name, path, strength=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = node(nt, "ShaderNodeOutputMaterial")
    em = node(nt, "ShaderNodeEmission")
    tx = node(nt, "ShaderNodeTexImage")
    tx.image = load_img(path)
    tx.extension = "EXTEND"
    em.inputs["Strength"].default_value = strength
    nt.links.new(tx.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def placeholder_exr(path, w=64, h=64, color=(0.6, 0.45, 0.3)):
    if os.path.exists(path):
        return
    im = bpy.data.images.new("ph", w, h, alpha=False, float_buffer=True)
    px = np.tile(np.array([*color, 1.0], np.float32), w * h)
    im.pixels.foreach_set(px)
    im.filepath_raw = path
    im.file_format = "OPEN_EXR"
    im.save()
    bpy.data.images.remove(im)


def save_png(name, arr):
    """arr: HxWx3 float in 0..1 (sRGB). Rows are top-down."""
    h, w, _ = arr.shape
    im = bpy.data.images.new(name, w, h, alpha=False)
    rgba = np.concatenate([arr[::-1], np.ones((h, w, 1))], axis=2).astype(np.float32)
    im.pixels.foreach_set(rgba.ravel())
    path = os.path.join(REN, name + ".png")
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    return im


def mesh_obj(name, bm, mat, scene, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), bevel=0.0, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    if mat is not None:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.rotation_euler = rot
    link(ob, scene, parent)
    if bevel:
        md = ob.modifiers.new("bevel", "BEVEL")
        md.width = bevel
        md.segments = 3
        md.limit_method = "ANGLE"
    return ob


def bm_box(sx, sy, sz):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    return bm


def bm_cyl(r1, r2, depth, seg=40):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r1, radius2=r2, depth=depth, calc_uvs=True)
    return bm


def bm_sphere(r, u=40, v=20):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r, calc_uvs=True)
    return bm


def bm_plane(sx, sy, nx=1, ny=1):
    """Plane in XY with UVs; rotate X +90deg to make it face -Y (image upright)."""
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=nx, y_segments=ny, size=0.5, calc_uvs=True)
    bmesh.ops.scale(bm, vec=(sx, sy, 1), verts=bm.verts)
    return bm


def bm_torus(R, r, su=64, sv=12):
    bm = bmesh.new()
    ring = []
    for i in range(su):
        a = TAU * i / su
        row = []
        for j in range(sv):
            b = TAU * j / sv
            row.append(bm.verts.new(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b))))
        ring.append(row)
    for i in range(su):
        for j in range(sv):
            bm.faces.new((ring[i][j], ring[(i + 1) % su][j], ring[(i + 1) % su][(j + 1) % sv], ring[i][(j + 1) % sv]))
    return bm


def camera_only(ob):
    for p in ("visible_diffuse", "visible_glossy", "visible_shadow", "visible_transmission", "visible_volume_scatter"):
        setattr(ob, p, False)


FONT_KO = bpy.data.fonts.load(os.path.join(FONTS, "Pretendard-SemiBold.otf"))
FONT_KO_REG = bpy.data.fonts.load(os.path.join(FONTS, "Pretendard-Regular.otf"))
FONT_TYPE = bpy.data.fonts.load(os.path.join(FONTS, "SpecialElite-Regular.ttf"))


def text(scene, parent, body, size, loc, rot=(math.pi / 2, 0, 0), font=None, mat=None, align="LEFT", extrude=0.0004):
    cu = bpy.data.curves.new("txt", "FONT")
    cu.body = body
    cu.font = font or FONT_KO
    cu.size = size
    cu.align_x = align
    cu.extrude = extrude
    cu.space_line = 1.15
    ob = bpy.data.objects.new("txt", cu)
    if mat:
        cu.materials.append(mat)
    ob.location = loc
    ob.rotation_euler = rot
    return link(ob, scene, parent)


# ---------------------------------------------------------------- library models (Poly Haven glTF)
LIBM = {}


def import_model(mid):
    path = os.path.join(ASSETS, "m", mid, mid + ".gltf")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    LIBM[mid] = {"objs": new, "mn": mn, "mx": mx}


def spawn(mid, scene, parent=None, loc=(0, 0, 0), rz=0.0, s=1.0):
    """Places a copy (shared mesh data) with its bottom-centre at loc. Returns (holder, top_z)."""
    L = LIBM[mid]
    holder = empty(mid, scene, parent=parent)
    mapping = {o: o.copy() for o in L["objs"]}
    for o, c in mapping.items():
        scene.collection.objects.link(c)
        if o.parent in mapping:
            c.parent = mapping[o.parent]
        else:
            c.parent = holder
            c.matrix_parent_inverse = Matrix.Identity(4)
    mn, mx = L["mn"], L["mx"]
    pivot = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z)) * s
    pivot.rotate(Matrix.Rotation(rz, 3, "Z"))
    holder.location = Vector(loc) - pivot
    holder.rotation_euler = (0, 0, rz)
    holder.scale = (s, s, s)
    return holder, loc[2] + (mx.z - mn.z) * s


for mid in ["wooden_table_02", "painted_wooden_chair_01", "Television_01", "wooden_bookshelf_worn", "vintage_day_bed",
            "desk_lamp_arm_01", "potted_plant_02", "Rockingchair_01", "hanging_picture_frame_01", "vintage_cabinet_01",
            "wooden_crate_02", "tea_set_01", "round_wooden_table_01", "flower_gazania", "flower_ursinia",
            "wild_rooibos_bush", "book_encyclopedia_set_01"]:
    import_model(mid)

# the frame model's "glass" is an opaque textured layer; make it real clear glass so the artwork shows
gm = bpy.data.materials.get("hanging_picture_frame_01_glass")
if gm:
    gb = gm.node_tree.nodes["Principled BSDF"]
    for l in list(gb.inputs["Base Color"].links):
        gm.node_tree.links.remove(l)
    gb.inputs["Base Color"].default_value = (1, 1, 1, 1)
    gb.inputs["Transmission Weight"].default_value = 1.0
    gb.inputs["Roughness"].default_value = 0.03
    for l in list(gb.inputs["Roughness"].links):
        gm.node_tree.links.remove(l)


# ---------------------------------------------------------------- shared materials
M_WEATHERED = pbr("weathered", "weathered_planks", scale=1.2, box=True)
M_DOOR_BLUE = pbr("door_blue", "blue_painted_planks", scale=1.0, box=True, rough=1.0)
M_DOOR_MARIGOLD = pbr("door_marigold", "blue_painted_planks", scale=1.0, box=True, hsv=(0.62, 1.15, 1.05))
M_BRASS = flat("brass", (0.78, 0.6, 0.28), rough=0.28, metal=1.0)
M_INK = flat("ink", (0.03, 0.025, 0.02), rough=0.6)
M_PAPER = flat("paper", (0.93, 0.9, 0.82), rough=0.92, sheen=0.3)
M_LINEN = pbr("linen", "rough_linen", scale=2.0, box=True, tint=(0.95, 0.9, 0.8), sheen=0.4)
M_LINEN_WHITE = pbr("linen_white", "rough_linen", scale=2.5, box=True, tint=(1.0, 0.98, 0.94), sheen=0.5)
M_ROPE = flat("rope", (0.55, 0.45, 0.32), rough=0.9)


def stripe_mat(name, c1, c2, freq=6.0):
    m, nt, b = new_mat(name)
    tc = node(nt, "ShaderNodeTexCoord")
    wv = node(nt, "ShaderNodeTexWave")
    wv.wave_type = "BANDS"
    wv.bands_direction = "X"
    wv.inputs["Scale"].default_value = freq
    nt.links.new(tc.outputs["UV"], wv.inputs["Vector"])
    ramp = node(nt, "ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (*c2, 1)
    nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    setin(b, "Roughness", 0.85)
    setin(b, "Sheen Weight", 0.4)
    nor = node(nt, "ShaderNodeTexImage")
    nor.image = load_img(os.path.join(ASSETS, "t", "rough_linen", "nor.jpg"), True)
    mp = node(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (3, 3, 3)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], nor.inputs["Vector"])
    nm = node(nt, "ShaderNodeNormalMap")
    nt.links.new(nor.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return m


# ---------------------------------------------------------------- world / sun from the HDRI
HDR = os.path.join(ASSETS, "h", "sky_4k.hdr")
hdr_img = load_img(HDR)
w_, h_ = hdr_img.size
px = np.empty(w_ * h_ * 4, np.float32)
hdr_img.pixels.foreach_get(px)
px = px.reshape(h_, w_, 4)
lum = px[..., 0] * 0.2126 + px[..., 1] * 0.7152 + px[..., 2] * 0.0722
row, col = np.unravel_index(int(np.argmax(lum)), lum.shape)
u, v = (col + 0.5) / w_, (row + 0.5) / h_
phi, theta = (u - 0.5) * TAU, (v - 0.5) * math.pi
sun_img = Vector((-math.cos(theta) * math.cos(phi), math.cos(theta) * math.sin(phi), math.sin(theta)))
SUN_AZ_TARGET = math.atan2(0.66, -0.75)            # front-left, over the sea side
WORLD_ROT = math.atan2(sun_img.y, sun_img.x) - SUN_AZ_TARGET
elev = max(math.asin(max(min(sun_img.z, 1), -1)), math.radians(12))
SUN_DIR = Vector((math.cos(elev) * math.cos(SUN_AZ_TARGET), math.cos(elev) * math.sin(SUN_AZ_TARGET), math.sin(elev)))
print("SUN elevation deg", math.degrees(elev), "world rot", WORLD_ROT)


def make_world(name, strength):
    w = bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = node(nt, "ShaderNodeOutputWorld")
    bg = node(nt, "ShaderNodeBackground")
    env = node(nt, "ShaderNodeTexEnvironment")
    env.image = hdr_img
    tc = node(nt, "ShaderNodeTexCoord")
    mp = node(nt, "ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, WORLD_ROT)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    return w


def add_sun(scene, strength, angle_deg=0.6, color=(1.0, 0.86, 0.7)):
    ld = bpy.data.lights.new("sun", "SUN")
    ld.energy = strength
    ld.angle = math.radians(angle_deg)
    ld.color = color
    ob = bpy.data.objects.new("sun", ld)
    ob.rotation_euler = SUN_DIR.to_track_quat("Z", "Y").to_euler()
    return link(ob, scene)


# ================================================================== SPACE 1 — DUNES (Mũi Né)
D.world = make_world("dunes_world", 0.75)
add_sun(D, 3.4)

# terrain: dense near the spawn, coarse far away
N = 720
u_ = np.linspace(-1, 1, N + 1)
coord = 30 * u_ + 1470 * u_ ** 5
X, Y = np.meshgrid(coord, coord)
Z = dune_h(X, Y)
dist = np.hypot(X, Y)
wind = X * 0.8 + Y * 0.6
Z += np.sin(wind * TAU / 0.42 + np.sin(Y * 0.7) * 1.5 + np.sin(X * 0.5) * 1.2) * 0.02 * smooth_np(dist, 1.2, 4) * (1 - smooth_np(dist, 25, 45))
verts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1).astype(np.float32)
idx = np.arange((N + 1) * (N + 1)).reshape(N + 1, N + 1)
quads = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)
me = bpy.data.meshes.new("dunes")
me.vertices.add(len(verts))
me.vertices.foreach_set("co", verts.ravel())
me.loops.add(quads.size)
me.loops.foreach_set("vertex_index", quads.ravel().astype(np.int32))
me.polygons.add(len(quads))
me.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4, dtype=np.int32))
me.update(calc_edges=True)
me.shade_smooth()

# sand: red_sand texture graded toward Mũi Né orange, macro variation, wind-ripple bump
m_sand, nt, b = new_mat("sand")
tc = node(nt, "ShaderNodeTexCoord")
mp = node(nt, "ShaderNodeMapping")
mp.inputs["Scale"].default_value = (0.55, 0.55, 0.55)
nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
t_d, t_a, t_n = (node(nt, "ShaderNodeTexImage") for _ in range(3))
for t, f, nc in ((t_d, "diff.jpg", False), (t_a, "arm.jpg", True), (t_n, "nor.jpg", True)):
    t.image = load_img(os.path.join(ASSETS, "t", "red_sand", f), nc)
    nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
hs = node(nt, "ShaderNodeHueSaturation")
hs.inputs["Hue"].default_value = 0.53
hs.inputs["Saturation"].default_value = 0.92
hs.inputs["Value"].default_value = 1.25
nt.links.new(t_d.outputs["Color"], hs.inputs["Color"])
nz = node(nt, "ShaderNodeTexNoise")
nz.inputs["Scale"].default_value = 0.035
nz.inputs["Detail"].default_value = 3
nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
ramp = node(nt, "ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.35
ramp.color_ramp.elements[0].color = (0.93, 0.68, 0.52, 1)
ramp.color_ramp.elements[1].position = 0.7
ramp.color_ramp.elements[1].color = (1.08, 0.9, 0.74, 1)
nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
a_, b_, o_ = mix_rgb(nt, "MULTIPLY")
nt.links.new(hs.outputs["Color"], a_)
nt.links.new(ramp.outputs["Color"], b_)
nt.links.new(o_, b.inputs["Base Color"])
sep = node(nt, "ShaderNodeSeparateColor")
nt.links.new(t_a.outputs["Color"], sep.inputs["Color"])
nt.links.new(sep.outputs[1], b.inputs["Roughness"])
nm = node(nt, "ShaderNodeNormalMap")
nm.inputs["Strength"].default_value = 0.8
nt.links.new(t_n.outputs["Color"], nm.inputs["Color"])
rip_map = node(nt, "ShaderNodeMapping")
rip_map.inputs["Rotation"].default_value = (0, 0, math.atan2(0.6, 0.8))
nt.links.new(tc.outputs["Object"], rip_map.inputs["Vector"])
wv = node(nt, "ShaderNodeTexWave")
wv.wave_type = "BANDS"
wv.bands_direction = "X"
wv.inputs["Scale"].default_value = 1.6
wv.inputs["Distortion"].default_value = 5.0
wv.inputs["Detail"].default_value = 2.0
wv.inputs["Detail Scale"].default_value = 1.5
nt.links.new(rip_map.outputs["Vector"], wv.inputs["Vector"])
bump = node(nt, "ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.22
bump.inputs["Distance"].default_value = 0.02
nt.links.new(wv.outputs["Fac"], bump.inputs["Height"])
nt.links.new(nm.outputs["Normal"], bump.inputs["Normal"])
nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
setin(b, "Specular IOR Level", 0.35)
me.materials.append(m_sand)
terrain = link(bpy.data.objects.new("dunes", me), D)

# sea on the western horizon
sea_m = flat("sea", (0.05, 0.3, 0.33), rough=0.12, spec=0.6)
nt = sea_m.node_tree
bs = nt.nodes["Principled BSDF"]
nz2 = node(nt, "ShaderNodeTexNoise")
nz2.inputs["Scale"].default_value = 0.4
bp2 = node(nt, "ShaderNodeBump")
bp2.inputs["Strength"].default_value = 0.15
nt.links.new(nz2.outputs["Fac"], bp2.inputs["Height"])
nt.links.new(bp2.outputs["Normal"], bs.inputs["Normal"])
# (no sea plane: a shoreline seen between dunes read as a rendering artifact)


def ring_points(n, seed, rmin, rmax, avoid):
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < n:
        a = rng.uniform(0, TAU)
        d = rmin + rng.uniform(0, 1) ** 0.8 * (rmax - rmin)
        x, y = math.cos(a) * d, math.sin(a) * d
        if any(math.hypot(x - ax, y - ay) < ar for ax, ay, ar in avoid):
            continue
        out.append((x, y, rng.uniform(0, TAU), rng.uniform(0, 1), d))
    return out


DOOR = (-1.4, 7.6)
SIGN = (2.8, 6.4)
STALL = (-7.2, 3.6)
TENT = (10.0, 11.0)
BREAKFAST = (-4.6, -4.6)
BOAT = (6.6, -4.4)
AVOID = [(0, 0, 1.6), (*DOOR, 1.8), (*SIGN, 1.0), (*STALL, 2.4), (*TENT, 3.2), (*BREAKFAST, 1.8), (*BOAT, 1.8)]

for i, (x, y, r, k, d) in enumerate(ring_points(48, 7, 4, 48, AVOID)):
    spawn("wild_rooibos_bush", D, loc=(x, y, ground(x, y) - 0.03), rz=r, s=0.8 + k * 0.9)

FLOWERS = empty("flowers", D)
for i, (x, y, r, k, d) in enumerate(ring_points(90, 21, 1.8, 13, AVOID)):
    h, _ = spawn("flower_gazania" if i % 2 == 0 else "flower_ursinia", D, parent=FLOWERS, loc=(x, y, ground(x, y) - 0.02), rz=r, s=0.9 + k * 0.5)
    h["flower"] = 0.9 + k * 0.5
tag(FLOWERS, "flowers")


# --- door builder (front faces -Y; hinge on the left)
def make_door(scene, name, leaf_mat, view_path, loc, rz, view_strength=1.0):
    g = empty(name, scene, loc=loc, rz=rz)
    for x in (-0.565, 0.565):
        mesh_obj("post", bm_box(0.13, 0.16, 2.3), M_WEATHERED, scene, g, loc=(x, 0, 1.15), bevel=0.006)
    mesh_obj("lintel", bm_box(1.26, 0.18, 0.15), M_WEATHERED, scene, g, loc=(0, 0, 2.33), bevel=0.006)
    mesh_obj("sill", bm_box(1.3, 0.36, 0.06), M_WEATHERED, scene, g, loc=(0, 0, 0.03), bevel=0.006)
    placeholder_exr(view_path)
    view = mesh_obj("view", bm_plane(1.0, 2.22), emission_image(name + "_view", view_path, view_strength), scene, g, loc=(0, 0.03, 1.14), rot=(math.pi / 2, 0, 0))
    camera_only(view)
    hinge = empty("hinge", scene, loc=(-0.5, -0.05, 0), parent=g)
    mesh_obj("leaf", bm_box(1.0, 0.055, 2.18), leaf_mat, scene, hinge, loc=(0.5, 0, 1.13), bevel=0.008)
    for z, hh in ((1.55, 0.72), (0.6, 0.62)):
        mesh_obj("panel", bm_box(0.72, 0.016, hh), leaf_mat, scene, hinge, loc=(0.5, -0.033, z), bevel=0.006)
        mesh_obj("panel_b", bm_box(0.72, 0.016, hh), leaf_mat, scene, hinge, loc=(0.5, 0.033, z), bevel=0.006)
    mesh_obj("knob", bm_sphere(0.036), M_BRASS, scene, hinge, loc=(0.9, -0.075, 1.06), smooth=True)
    mesh_obj("knob_b", bm_sphere(0.036), M_BRASS, scene, hinge, loc=(0.9, 0.075, 1.06), smooth=True)
    mesh_obj("rose", bm_cyl(0.05, 0.05, 0.01), M_BRASS, scene, hinge, loc=(0.9, -0.03, 1.06), rot=(math.pi / 2, 0, 0))
    hinge.rotation_euler = (0, 0, -0.38)
    g["hinge"] = hinge.name
    return g, hinge


door_g, door_hinge = make_door(D, "door", M_DOOR_BLUE, os.path.join(REN, "pre_room_from_door.exr"), (DOOR[0], DOOR[1], ground(*DOOR) - 0.03), face_spawn(*DOOR), view_strength=1.8)
tag(door_g, "door")
spill = bpy.data.lights.new("door_spill", "AREA")
spill.shape = "RECTANGLE"
spill.size, spill.size_y = 0.9, 2.0
spill.energy = 70
spill.color = (1.0, 0.72, 0.45)
spill_ob = bpy.data.objects.new("door_spill", spill)
spill_ob.location = (0, 0.12, 1.15)
spill_ob.rotation_euler = (-math.pi / 2, 0, 0)
spill_ob.visible_camera = False
link(spill_ob, D, door_g)

# --- signpost (TOUR)
sign = empty("sign", D, loc=(SIGN[0], SIGN[1], ground(*SIGN) - 0.05), rz=face_spawn(*SIGN) - 0.3)
mesh_obj("pole", bm_cyl(0.06, 0.075, 2.7, 16), M_WEATHERED, D, sign, loc=(0, 0, 1.35))
M_SIGNPAINT = flat("sign_paint", (0.9, 0.86, 0.76), rough=0.8)
for txt, z, rz in (("CONCERT  소문의 낙원  →", 2.3, 0.22), ("이찬혁의 방  ←", 1.86, -0.25), ("바다까지  1.2 km", 1.42, 0.12)):
    arm = empty("arm", D, loc=(0, 0, z), rz=rz, parent=sign)
    mesh_obj("board", bm_box(1.32, 0.045, 0.3), M_WEATHERED, D, arm, loc=(0.52, 0, 0), bevel=0.006)
    mesh_obj("plate", bm_box(1.2, 0.006, 0.22), M_SIGNPAINT, D, arm, loc=(0.52, -0.024, 0), bevel=0.002)
    text(D, arm, txt, 0.1, (-0.04, -0.028, -0.035), mat=M_INK)
tag(sign, "tour")

# --- festival stall (SHOP) + bunting
stall = empty("stall", D, loc=(STALL[0], STALL[1], ground(*STALL) - 0.03), rz=face_spawn(*STALL))
_, crate_top = spawn("wooden_crate_02", D, stall, loc=(-0.45, 0, 0), rz=math.pi / 2)
spawn("wooden_crate_02", D, stall, loc=(0.65, 0, 0), rz=math.pi / 2)
spawn("wooden_crate_02", D, stall, loc=(0.65, 0.02, crate_top), rz=math.pi / 2 + 0.05, s=0.8)
for x in (-1.2, 1.2):
    for y in (-0.42, 0.5):
        mesh_obj("pole", bm_cyl(0.03, 0.035, 2.35, 12), M_WEATHERED, D, stall, loc=(x, y, 1.17))
bm = bm_plane(2.75, 1.3, 16, 8)
for vv in bm.verts:
    vv.co.z += math.sin(vv.co.x * 2.2) * 0.03 - abs(vv.co.y) * 0.06
aw = mesh_obj("awning", bm, stripe_mat("awning", (0.94, 0.9, 0.82), (0.7, 0.2, 0.12), 9.0), D, stall, loc=(0, 0.05, 2.28), rot=(-0.22, 0, 0), smooth=True)
aw.modifiers.new("solid", "SOLIDIFY").thickness = 0.006
for i, (x, c) in enumerate(((-0.78, (0.42, 0.48, 0.66)), (-0.38, (0.86, 0.66, 0.24)), (0.02, (0.7, 0.3, 0.2)), (-0.58, (0.85, 0.55, 0.37)))):
    mesh_obj("lp", bm_box(0.31, 0.012, 0.31), flat("lp%d" % i, c, rough=0.55), D, stall, loc=(x, -0.06 + i * 0.03, crate_top + 0.16), rot=(-0.28, 0, 0))
tag(stall, "shop")

flag_cols = [(0.86, 0.66, 0.24), (0.7, 0.3, 0.2), (0.93, 0.89, 0.8), (0.42, 0.48, 0.66), (0.45, 0.62, 0.6)]
bpy.context.view_layer.update()
D.view_layers[0].update()
pa = stall.matrix_world @ Vector((1.2, -0.42, 2.38))
door_w = door_g.matrix_world
pb = door_w @ Vector((-1.25, 0.25, 2.6))
mesh_obj("bunting_pole", bm_cyl(0.035, 0.04, 2.75, 10), M_WEATHERED, D, loc=(pb.x, pb.y, ground(pb.x, pb.y) + 1.37))
prev = None
for i in range(33):
    t = i / 32
    p = pa.lerp(pb, t)
    p.z -= math.sin(t * math.pi) * 0.45
    if prev is not None:
        seg = p - prev
        c = mesh_obj("string", bm_cyl(0.004, 0.004, seg.length, 6), M_ROPE, D, loc=(prev + p) / 2)
        c.rotation_euler = seg.to_track_quat("Z", "Y").to_euler()
    if i % 2 == 0 and 0 < i < 32:
        bm = bmesh.new()
        v1, v2, v3 = bm.verts.new((-0.12, 0, 0)), bm.verts.new((0.12, 0, 0)), bm.verts.new((0, 0, -0.28))
        bm.faces.new((v1, v2, v3))
        f = mesh_obj("flag", bm, flat("flag%d" % i, flag_cols[(i // 2) % 5], rough=0.85, sheen=0.4), D, loc=p)
        f.rotation_euler = (0, 0, math.atan2(pb.y - pa.y, pb.x - pa.x))
        f.modifiers.new("solid", "SOLIDIFY").thickness = 0.003
    prev = p

# --- canvas tent (Tent)
tent = empty("tent", D, loc=(TENT[0], TENT[1], ground(*TENT) - 0.05), rz=face_spawn(*TENT))
TW, TH, TL = 2.7, 1.95, 3.3
slope = math.hypot(TW / 2, TH)
for s in (-1, 1):
    bm = bm_plane(slope, TL, 8, 12)
    for vv in bm.verts:
        vv.co.z -= math.sin((vv.co.x / slope + 0.5) * math.pi) * 0.05 * (0.6 + 0.4 * math.cos(vv.co.y * 1.6))
    roof = mesh_obj("roof", bm, M_LINEN, D, tent, smooth=True)
    roof.location = (s * TW / 4, 0, TH / 2)
    roof.rotation_euler = (0, s * math.atan2(TH, TW / 2), 0)
    roof.rotation_mode = "XYZ"
    roof.modifiers.new("solid", "SOLIDIFY").thickness = 0.008
bm = bmesh.new()
vs = [bm.verts.new(c) for c in ((-TW / 2, TL / 2, 0), (TW / 2, TL / 2, 0), (0, TL / 2, TH))]
bm.faces.new(vs)
mesh_obj("back", bm, M_LINEN, D, tent).modifiers.new("solid", "SOLIDIFY").thickness = 0.008
mesh_obj("ridge", bm_cyl(0.03, 0.03, TL + 0.5, 10), M_WEATHERED, D, tent, loc=(0, 0, TH + 0.02), rot=(math.pi / 2, 0, 0))
for y in (-TL / 2 - 0.18, TL / 2 + 0.18):
    mesh_obj("tpole", bm_cyl(0.03, 0.03, TH + 0.12, 10), M_WEATHERED, D, tent, loc=(0, y, (TH + 0.12) / 2))
mesh_obj("trug", bm_plane(1.7, 2.3), stripe_mat("trug", (0.86, 0.66, 0.24), (0.55, 0.22, 0.14), 7), D, tent, loc=(0, 0.2, 0.012))
for s in (-1, 1):
    a = Vector((0, -TL / 2 - 0.18, TH + 0.1))
    bpos = Vector((s * 1.2, -TL / 2 - 1.3, 0.05))
    seg = bpos - a
    c = mesh_obj("guy", bm_cyl(0.006, 0.006, seg.length, 6), M_ROPE, D, tent, loc=(a + bpos) / 2)
    c.rotation_euler = seg.to_track_quat("Z", "Y").to_euler()
lan = bpy.data.lights.new("tent_lantern", "POINT")
lan.energy = 22
lan.color = (1.0, 0.62, 0.32)
lan.shadow_soft_size = 0.05
lan_ob = bpy.data.objects.new("tent_lantern", lan)
lan_ob.location = (0, 0.6, 0.55)
link(lan_ob, D, tent)
tag(tent, "tent")

# --- breakfast on the sand (우아한 아침 식사)
bf = empty("breakfast", D, loc=(BREAKFAST[0], BREAKFAST[1], ground(*BREAKFAST) - 0.03), rz=0.4)
_, top = spawn("round_wooden_table_01", D, bf, s=0.75)
skirt = bm_cyl(0.56, 0.6, 0.2, 64)
bmesh.ops.delete(skirt, geom=[f for f in skirt.faces if abs(f.normal.z) > 0.9], context="FACES")
for vv in skirt.verts:
    a = math.atan2(vv.co.y, vv.co.x)
    if vv.co.z < 0:
        vv.co.x += math.cos(a) * math.sin(a * 9) * 0.015
        vv.co.y += math.sin(a) * math.sin(a * 9) * 0.015
mesh_obj("cloth", skirt, M_LINEN_WHITE, D, bf, loc=(0, 0, top - 0.09), smooth=True).modifiers.new("solid", "SOLIDIFY").thickness = 0.004
mesh_obj("cloth_top", bm_cyl(0.56, 0.56, 0.006, 64), M_LINEN_WHITE, D, bf, loc=(0, 0, top + 0.003))
spawn("tea_set_01", D, bf, loc=(0.05, -0.05, top + 0.006), rz=0.6)
for s in (-1, 1):
    spawn("painted_wooden_chair_01", D, bf, loc=(s * 0.85, 0, 0), rz=s * math.pi / 2)
tag(bf, "breakfast")

# --- thúng chai, Mũi Né's round basket boat
m_weave, nt, b = new_mat("weave")
tc = node(nt, "ShaderNodeTexCoord")
w1, w2 = node(nt, "ShaderNodeTexWave"), node(nt, "ShaderNodeTexWave")
for w, rot in ((w1, 0.78), (w2, -0.78)):
    mpw = node(nt, "ShaderNodeMapping")
    mpw.inputs["Rotation"].default_value = (0, 0, rot)
    nt.links.new(tc.outputs["Object"], mpw.inputs["Vector"])
    w.wave_type = "BANDS"
    w.inputs["Scale"].default_value = 14
    w.inputs["Distortion"].default_value = 0.6
    nt.links.new(mpw.outputs["Vector"], w.inputs["Vector"])
mx_ = node(nt, "ShaderNodeMath", operation="MAXIMUM")
nt.links.new(w1.outputs["Fac"], mx_.inputs[0])
nt.links.new(w2.outputs["Fac"], mx_.inputs[1])
rr = node(nt, "ShaderNodeValToRGB")
rr.color_ramp.elements[0].color = (0.09, 0.07, 0.05, 1)
rr.color_ramp.elements[1].color = (0.32, 0.24, 0.15, 1)
nt.links.new(mx_.outputs[0], rr.inputs["Fac"])
nt.links.new(rr.outputs["Color"], b.inputs["Base Color"])
bpw = node(nt, "ShaderNodeBump")
bpw.inputs["Strength"].default_value = 0.6
nt.links.new(mx_.outputs[0], bpw.inputs["Height"])
nt.links.new(bpw.outputs["Normal"], b.inputs["Normal"])
setin(b, "Roughness", 0.55)
setin(b, "Coat Weight", 0.25)
boat = empty("boat", D, loc=(BOAT[0], BOAT[1], ground(*BOAT) - 0.12), rz=0.5)
hull = bm_sphere(1.0, 64, 32)
bmesh.ops.delete(hull, geom=[vv for vv in hull.verts if vv.co.z > 0.001], context="VERTS")
bmesh.ops.scale(hull, vec=(1, 1, 0.55), verts=hull.verts)
hob = mesh_obj("hull", hull, m_weave, D, boat, loc=(0, 0, 0.55), smooth=True)
hob.modifiers.new("solid", "SOLIDIFY").thickness = 0.025
mesh_obj("rim", bm_torus(1.0, 0.04), flat("bamboo", (0.62, 0.48, 0.3), rough=0.6), D, boat, loc=(0, 0, 0.55), smooth=True)
oar = empty("oar", D, loc=(0.25, 0.2, 0.5), parent=boat)
oar.rotation_euler = (0, 1.2, 0.3)
mesh_obj("shaft", bm_cyl(0.022, 0.022, 2.0, 12), M_WEATHERED, D, oar)
mesh_obj("blade", bm_box(0.16, 0.02, 0.5), M_WEATHERED, D, oar, loc=(0, 0, -1.15), bevel=0.01)
boat.rotation_euler = (0.1, -0.06, 0.5)
tag(boat, "boat")

# --- floating rumor slips
rumors = empty("rumors", D)
rng = np.random.default_rng(55)
for i in range(9):
    a = -1.3 + (i / 8) * 4.8 + rng.uniform(0, 0.3)
    d = 3.4 + rng.uniform(0, 4.6)
    x, y = math.sin(a) * d, math.cos(a) * d
    z = ground(x, y) + 1.6 + rng.uniform(0, 1.5)
    slip = empty("slip", D, loc=(x, y, z), parent=rumors)
    slip.rotation_euler = (rng.uniform(-0.2, 0.2), rng.uniform(-0.25, 0.25), face_spawn(x, y))
    bm = bm_plane(0.4, 0.26, 6, 4)
    for vv in bm.verts:
        vv.co.z += (vv.co.x ** 2) * 0.12
    mesh_obj("paper", bm, M_PAPER, D, slip, rot=(math.pi / 2, 0, 0), smooth=True)
    text(D, slip, "소문 #%02d" % (i + 1), 0.075, (-0.16, -0.014, 0.03), mat=M_INK)
    text(D, slip, "— 들었어?", 0.05, (-0.16, -0.014, -0.07), font=FONT_KO_REG, mat=M_INK)
tag(rumors, "rumor")


# ================================================================== SPACE 2 — ROOM (이찬혁의 방)
R.world = make_world("room_world", 0.9)
add_sun(R, 5.5, angle_deg=0.5)
RW, RD, RH, T = 6.4, 6.4, 2.8, 0.16
WIN = dict(x=-0.4, z=1.62, w=1.7, h=1.15)
BACKDOOR_X = 1.3

M_PLASTER = pbr("plaster", "painted_plaster_wall", scale=0.6, box=True, tint=(1.0, 0.93, 0.8))
M_WAINSCOT = pbr("wainscot", "weathered_planks", scale=1.1, box=True, hsv=(0.27, 0.7, 0.85), tint=(0.62, 0.68, 0.48))
M_TRIM = flat("trim", (0.86, 0.82, 0.72), rough=0.45)
M_FLOOR = pbr("floor", "old_wooden_floor_01", scale=0.42, box=True, rough=0.85)
M_BEAM = pbr("beam", "wood_planks", scale=0.8, box=True, tint=(0.55, 0.4, 0.3))


def boolean_cut(ob, cutter):
    md = ob.modifiers.new("cut", "BOOLEAN")
    md.operation = "DIFFERENCE"
    md.object = cutter
    md.solver = "EXACT"
    cutter.hide_render = True
    cutter.display_type = "WIRE"


walls = {
    "front": ((0, RD / 2 + T / 2, RH / 2), (RW + 2 * T, T, RH)),
    "back": ((0, -RD / 2 - T / 2, RH / 2), (RW + 2 * T, T, RH)),
    "left": ((-RW / 2 - T / 2, 0, RH / 2), (T, RD, RH)),
    "right": ((RW / 2 + T / 2, 0, RH / 2), (T, RD, RH)),
}
wall_obs = {}
for k, (loc, size) in walls.items():
    wall_obs[k] = mesh_obj("wall_" + k, bm_box(*size), M_PLASTER, R, loc=loc)
win_cut = mesh_obj("win_cut", bm_box(WIN["w"], 1.0, WIN["h"]), None, R, loc=(WIN["x"], RD / 2 + T / 2, WIN["z"]))
boolean_cut(wall_obs["front"], win_cut)
door_cut = mesh_obj("door_cut", bm_box(1.06, 1.0, 2.24), None, R, loc=(BACKDOOR_X, -RD / 2 - T / 2, 1.12))
boolean_cut(wall_obs["back"], door_cut)
mesh_obj("floor", bm_box(RW + 2 * T, RD + 2 * T, 0.1), M_FLOOR, R, loc=(0, 0, -0.05))
mesh_obj("ceiling", bm_box(RW + 2 * T, RD + 2 * T, 0.12), M_PLASTER, R, loc=(0, 0, RH + 0.06))
for y in (-2.2, -0.75, 0.75, 2.2):
    mesh_obj("beam", bm_box(RW, 0.14, 0.18), M_BEAM, R, loc=(0, y, RH - 0.09), bevel=0.01)
# wainscot + rail + skirting along every wall (with gaps for the window side and the back door)
for k, (loc, size) in walls.items():
    horiz = size[0] > size[1]
    length = RW if horiz else RD
    inner = (loc[0] - (T / 2 + 0.012) * (1 if loc[0] > 0 else -1) * (not horiz), loc[1] - (T / 2 + 0.012) * (1 if loc[1] > 0 else -1) * horiz, 0)
    pieces = [(-length / 2, length / 2)]
    if k == "back":
        pieces = [(-length / 2, BACKDOOR_X - 0.62), (BACKDOOR_X + 0.62, length / 2)]
    for a, bnd in pieces:
        c = (a + bnd) / 2
        L = bnd - a
        pos = (c, inner[1], 0) if horiz else (inner[0], c, 0)
        dims = (L, 0.024, 0.9) if horiz else (0.024, L, 0.9)
        mesh_obj("wainscot", bm_box(*dims), M_WAINSCOT, R, loc=(pos[0], pos[1], 0.45))
        rd = (L, 0.05, 0.05) if horiz else (0.05, L, 0.05)
        mesh_obj("rail", bm_box(*rd), M_TRIM, R, loc=(pos[0], pos[1], 0.92), bevel=0.008)
# window: frame, glass, sill, sheer curtains, outside view
wx, wz, ww, wh = WIN["x"], WIN["z"], WIN["w"], WIN["h"]
fy = RD / 2 + T / 2
for (x, z, sx, sz) in ((wx, wz + wh / 2 - 0.03, ww, 0.06), (wx, wz - wh / 2 + 0.03, ww, 0.06), (wx - ww / 2 + 0.03, wz, 0.06, wh), (wx + ww / 2 - 0.03, wz, 0.06, wh), (wx, wz, 0.045, wh), (wx, wz + 0.12, ww, 0.04)):
    mesh_obj("wframe", bm_box(sx, 0.07, sz), M_TRIM, R, loc=(x, fy, z), bevel=0.006)
mesh_obj("sill", bm_box(ww + 0.2, 0.26, 0.05), M_TRIM, R, loc=(wx, RD / 2 - 0.02, wz - wh / 2 - 0.02), bevel=0.008)
glass = mesh_obj("glass", bm_box(ww - 0.06, 0.008, wh - 0.06), flat("glass", (1, 1, 1), rough=0.0, trans=1.0, ior=1.5), R, loc=(wx, fy, wz))
glass.visible_shadow = False
for s in (-1, 1):
    bm = bm_plane(0.55, 1.55, 24, 8)
    for vv in bm.verts:
        vv.co.z += math.sin(vv.co.x * 38) * 0.025
    cur = mesh_obj("curtain", bm, flat("sheer", (0.97, 0.94, 0.88), rough=0.7, trans=0.55, sheen=0.5), R, loc=(wx + s * (ww / 2 + 0.22), RD / 2 - 0.06, wz + 0.1), rot=(math.pi / 2, 0, 0), smooth=True)
mesh_obj("rod", bm_cyl(0.012, 0.012, ww + 1.0, 12), M_BRASS, R, loc=(wx, RD / 2 - 0.06, wz + wh / 2 + 0.2), rot=(0, math.pi / 2, 0))
win_view_path = os.path.join(REN, "pre_window_view.exr")
placeholder_exr(win_view_path, color=(0.8, 0.6, 0.45))
wv_ob = mesh_obj("window_view", bm_plane(9.0, 5.0), emission_image("window_view", win_view_path, 1.0), R, loc=(wx, RD / 2 + 3.2, wz - 0.55), rot=(math.pi / 2, 0, 0))
camera_only(wv_ob)
# back door (to the dunes) + what is seen through it
back_door, back_hinge = make_door(R, "door_back", M_DOOR_MARIGOLD, os.path.join(REN, "pre_dunes_from_door.exr"), (BACKDOOR_X, -RD / 2 - T / 2, 0), math.pi, view_strength=0.75)
tag(back_door, "doorBack")
# volumetric haze so the low sun draws a beam through the window
vol = mesh_obj("haze", bm_box(RW - 0.05, RD - 0.05, RH - 0.05), None, R, loc=(0, 0, RH / 2))
vm = bpy.data.materials.new("haze")
vm.use_nodes = True
vnt = vm.node_tree
vnt.nodes.remove(vnt.nodes["Principled BSDF"])
pv = node(vnt, "ShaderNodeVolumePrincipled")
pv.inputs["Density"].default_value = 0.011
pv.inputs["Anisotropy"].default_value = 0.45
pv.inputs["Color"].default_value = (1.0, 0.93, 0.85, 1)
vnt.links.new(pv.outputs[0], vnt.nodes["Material Output"].inputs["Volume"])
vol.data.materials.append(vm)
vol["haze"] = 1

# light portal in the window so Cycles samples the sky through it (brighter, cleaner interior)
por = bpy.data.lights.new("window_portal", "AREA")
por.shape = "RECTANGLE"
por.size, por.size_y = WIN["w"], WIN["h"]
try:
    por.cycles.is_portal = True
except Exception:
    por.energy = 0
por_ob = bpy.data.objects.new("window_portal", por)
por_ob.location = (WIN["x"], RD / 2 + T + 0.02, WIN["z"])
por_ob.rotation_euler = (-math.pi / 2, 0, 0)
link(por_ob, R)
fill = bpy.data.lights.new("window_fill", "AREA")
fill.shape = "RECTANGLE"
fill.size, fill.size_y = WIN["w"] * 1.4, WIN["h"] * 1.4
fill.energy = 110
fill.color = (0.86, 0.9, 1.0)
fill_ob = bpy.data.objects.new("window_fill", fill)
fill_ob.location = (WIN["x"], RD / 2 - 0.15, WIN["z"])
fill_ob.rotation_euler = (-math.pi / 2, 0, 0)
fill_ob.visible_camera = False
link(fill_ob, R)
# furniture
desk, desk_top = spawn("wooden_table_02", R, loc=(WIN["x"], RD / 2 - 0.45, 0))
spawn("painted_wooden_chair_01", R, loc=(WIN["x"] + 0.05, RD / 2 - 1.05, 0), rz=math.pi + 0.15)
lamp, _ = spawn("desk_lamp_arm_01", R, loc=(WIN["x"] - 0.42, RD / 2 - 0.3, desk_top), rz=0.5)
for o in lamp.children_recursive:
    if o.type == "MESH":
        for ms in o.material_slots:
            if ms.material and "light" in ms.material.name.lower():
                ms.link = "OBJECT"
                lm, _, lb = new_mat("bulb")
                setin(lb, "Emission Color", (1.0, 0.78, 0.5, 1))
                setin(lb, "Emission Strength", 30)
                ms.material = lm
bulb = bpy.data.lights.new("desk_bulb", "POINT")
bulb.energy = 40
bulb.shadow_soft_size = 0.02
bulb.color = (1.0, 0.72, 0.45)
bulb_ob = bpy.data.objects.new("desk_bulb", bulb)
bulb_ob.location = (WIN["x"] - 0.28, RD / 2 - 0.45, desk_top + 0.42)
link(bulb_ob, R)
spawn("tea_set_01", R, loc=(WIN["x"] + 0.44, RD / 2 - 0.36, desk_top), rz=-0.4)

# typewriter (LETTER)
tw = empty("typewriter", R, loc=(WIN["x"] + 0.02, RD / 2 - 0.5, desk_top), rz=0.08)
M_ENAMEL = flat("enamel", (0.14, 0.2, 0.12), rough=0.3, coat=1.0)
M_CHROME = flat("chrome", (0.8, 0.78, 0.74), rough=0.18, metal=1.0)
M_RUBBER = flat("rubber", (0.02, 0.02, 0.02), rough=0.55)
M_KEY = flat("keycap", (0.9, 0.86, 0.76), rough=0.3, coat=0.6)
mesh_obj("tw_base", bm_box(0.42, 0.34, 0.09), M_ENAMEL, R, tw, loc=(0, 0, 0.045), bevel=0.018)
mesh_obj("tw_deck", bm_box(0.42, 0.17, 0.08), M_ENAMEL, R, tw, loc=(0, 0.075, 0.115), rot=(0.28, 0, 0), bevel=0.015)
mesh_obj("tw_roller", bm_cyl(0.035, 0.035, 0.52, 40), M_RUBBER, R, tw, loc=(0, 0.14, 0.19), rot=(0, math.pi / 2, 0))
for x in (-0.27, 0.27):
    mesh_obj("tw_knob", bm_cyl(0.03, 0.03, 0.014, 32), M_CHROME, R, tw, loc=(x, 0.14, 0.19), rot=(0, math.pi / 2, 0), bevel=0.003)
lever = mesh_obj("tw_lever", bm_cyl(0.006, 0.006, 0.17, 12), M_CHROME, R, tw, loc=(-0.31, 0.1, 0.24), rot=(0, 0.3, 1.2))
bm = bm_plane(0.28, 0.33, 4, 8)
for vv in bm.verts:
    vv.co.z += (vv.co.y + 0.165) ** 2 * 0.25
sheet = empty("sheet", R, loc=(0, 0.17, 0.35), parent=tw)
sheet.rotation_euler = (0.18, 0, 0)
mesh_obj("tw_paper", bm, M_PAPER, R, sheet, rot=(math.pi / 2, 0, 0), smooth=True)
text(R, sheet, "소문의 낙원\n\n모래 위에 문을\n하나 세워 두었다.", 0.022, (-0.12, -0.012, 0.11), font=FONT_KO_REG, mat=M_INK)
for rowi in range(4):
    for k in range(9 if rowi < 3 else 7):
        kx = -0.17 + k * 0.042 + rowi * 0.01
        ky = -0.135 + rowi * 0.038
        kz = 0.105 + rowi * 0.014
        mesh_obj("key_stem", bm_cyl(0.004, 0.004, 0.03, 8), M_CHROME, R, tw, loc=(kx, ky, kz - 0.015))
        mesh_obj("key", bm_cyl(0.016, 0.016, 0.01, 24), M_KEY, R, tw, loc=(kx, ky, kz), bevel=0.003)
        mesh_obj("key_ring", bm_cyl(0.0175, 0.0175, 0.006, 24), M_CHROME, R, tw, loc=(kx, ky, kz - 0.006))
mesh_obj("space", bm_box(0.2, 0.03, 0.012), M_KEY, R, tw, loc=(0, -0.168, 0.098), bevel=0.004)
text(R, tw, "ROYAL", 0.025, (-0.045, -0.172, 0.06), font=FONT_TYPE, mat=flat("gold", (0.85, 0.68, 0.32), rough=0.3, metal=1.0))
tag(tw, "contact")

# turntable on an apple crate (MUSIC)
music = empty("music", R, loc=(-RW / 2 + 0.36, 1.1, 0))
_, ct = spawn("wooden_crate_02", R, music)
M_WALNUT = pbr("walnut", "wood_planks", scale=2.5, box=True, tint=(0.42, 0.28, 0.2), coat=0.8, rough=0.6)
tt = empty("turntable", R, loc=(0, 0.2, ct), parent=music)
tt.rotation_euler = (0, 0, -math.pi / 2)
mesh_obj("plinth", bm_box(0.46, 0.36, 0.1), M_WALNUT, R, tt, loc=(0, 0, 0.05), bevel=0.012)
mesh_obj("platter", bm_cyl(0.155, 0.155, 0.02, 64), flat("alu", (0.75, 0.74, 0.72), rough=0.3, metal=1.0), R, tt, loc=(-0.05, 0, 0.11), bevel=0.003)
m_vinyl, nt, b = new_mat("vinyl")
setin(b, "Base Color", (0.012, 0.012, 0.012, 1))
setin(b, "Roughness", 0.28)
setin(b, "Coat Weight", 0.6)
tc = node(nt, "ShaderNodeTexCoord")
wv = node(nt, "ShaderNodeTexWave")
wv.wave_type = "RINGS"
wv.inputs["Scale"].default_value = 160
nt.links.new(tc.outputs["Object"], wv.inputs["Vector"])
bpv = node(nt, "ShaderNodeBump")
bpv.inputs["Strength"].default_value = 0.15
nt.links.new(wv.outputs["Fac"], bpv.inputs["Height"])
nt.links.new(bpv.outputs["Normal"], b.inputs["Normal"])
record = mesh_obj("record", bm_cyl(0.15, 0.15, 0.004, 96), m_vinyl, R, tt, loc=(-0.05, 0, 0.123))
mesh_obj("label", bm_cyl(0.05, 0.05, 0.0012, 48), flat("label", (0.86, 0.64, 0.24), rough=0.6), R, tt, loc=(-0.05, 0, 0.1257))
text(R, tt, "개화", 0.018, (-0.05, 0.004, 0.1265), rot=(0, 0, 0), mat=M_INK, align="CENTER")
text(R, tt, "AKMU", 0.011, (-0.05, -0.016, 0.1265), rot=(0, 0, 0), font=FONT_TYPE, mat=M_INK, align="CENTER")
mesh_obj("arm_base", bm_cyl(0.022, 0.026, 0.03, 24), M_CHROME, R, tt, loc=(0.16, 0.12, 0.115))
arm = mesh_obj("tonearm", bm_cyl(0.004, 0.004, 0.25, 12), M_CHROME, R, tt, loc=(0.12, 0.02, 0.135), rot=(math.pi / 2, 0, 0.35))
mesh_obj("headshell", bm_box(0.018, 0.035, 0.008), M_INK, R, tt, loc=(0.075, -0.09, 0.13), rot=(0, 0, 0.35))
for i, c in enumerate(((0.86, 0.66, 0.24), (0.7, 0.3, 0.2), (0.93, 0.89, 0.8), (0.42, 0.48, 0.66))):
    mesh_obj("sleeve", bm_box(0.012, 0.31, 0.31), flat("sleeve%d" % i, c, rough=0.6), R, music, loc=(-0.1 + i * 0.045, -0.25, ct + 0.15), rot=(0, -0.3 + i * 0.07, 0))
tag(music, "music")

# TV on a crate (VIDEO) with an emissive screen
video = empty("video", R, loc=(RW / 2 - 0.85, RD / 2 - 0.55, 0), rz=-0.55)
_, ct2 = spawn("wooden_crate_02", R, video, rz=math.pi / 2)
tvh, tv_top = spawn("Television_01", R, video, loc=(0, 0, ct2))
tvL = LIBM["Television_01"]
sz = tvL["mx"] - tvL["mn"]
bars = np.zeros((240, 320, 3))
cols = [(0.93, 0.9, 0.82), (0.86, 0.66, 0.24), (0.55, 0.72, 0.82), (0.5, 0.65, 0.35), (0.7, 0.3, 0.2), (0.42, 0.48, 0.66), (0.08, 0.07, 0.06)]
for i, c in enumerate(cols):
    bars[:170, i * 320 // 7:(i + 1) * 320 // 7 + 1] = c
bars[170:] = (0.06, 0.05, 0.05)
save_png("tv_bars", bars)
scr = mesh_obj("screen", bm_plane(sz.x * 0.62, sz.z * 0.56), emission_image("tv_screen", os.path.join(REN, "tv_bars.png"), 1.6), R, video,
               loc=(-sz.x * 0.08, -sz.y / 2 - 0.004, ct2 + sz.z * 0.5 + sz.z * 0.04), rot=(math.pi / 2, 0, 0))
scr["tv_screen"] = 1
tag(video, "video")

# other furniture
spawn("wooden_bookshelf_worn", R, loc=(-RW / 2 + 0.32, -1.15, 0), rz=math.pi / 2)
bk = LIBM["book_encyclopedia_set_01"]
bk_w = bk["mx"].x - bk["mn"].x
for i, (z, n) in enumerate(((0.05, 1), (0.55, 1), (1.05, 1), (1.53, 1))):
    spawn("book_encyclopedia_set_01", R, loc=(-RW / 2 + 0.3, -1.15 + (i % 2 - 0.5) * 0.25, z), rz=math.pi / 2, s=min(1.0, 0.33 / max(bk["mx"].z - bk["mn"].z, 0.01)))
spawn("vintage_day_bed", R, loc=(RW / 2 - 0.48, -1.35, 0), rz=-math.pi / 2)
mesh_obj("quilt", bm_box(0.7, 0.5, 0.08), pbr("quilt", "rough_linen", scale=3, box=True, tint=(0.9, 0.6, 0.25), sheen=0.6), R, loc=(RW / 2 - 0.5, -2.0, 0.62), rot=(0, 0, 0.1), bevel=0.03)
rock = empty("rock", R, loc=(1.15, 0.35, 0), rz=math.pi - 0.9)
spawn("Rockingchair_01", R, rock)
tag(rock, "rock")
spawn("potted_plant_02", R, loc=(-RW / 2 + 0.5, RD / 2 - 0.5, 0))
spawn("vintage_cabinet_01", R, loc=(-1.35, -RD / 2 + 0.36, 0), rz=math.pi, s=0.98)
spawn("hanging_picture_frame_01", R, loc=(RW / 2 - 0.02, -1.35, 1.28), rz=-math.pi / 2)
spawn("hanging_picture_frame_01", R, loc=(1.35, RD / 2 - 0.02, 1.3), rz=0.0)
for o in R.objects:
    if o.type == "MESH" and any(ms.material and "glass" in ms.material.name.lower() for ms in o.material_slots) and o.name != "glass" and len(o.material_slots) == 1:
        o.hide_render = True

# rug (kilim pattern generated here)
H_, W_ = 680, 1024
yy, xx = np.mgrid[0:H_, 0:W_]
rug = np.zeros((H_, W_, 3))
rug[:] = (0.55, 0.2, 0.12)
inner = (xx > 40) & (xx < W_ - 40) & (yy > 40) & (yy < H_ - 40)
rug[inner] = (0.9, 0.84, 0.7)
core = (xx > 70) & (xx < W_ - 70) & (yy > 70) & (yy < H_ - 70)
rug[core] = (0.62, 0.24, 0.14)
dia = (np.abs((xx % 170) - 85) + np.abs((yy % 136) - 68))
rug[core & (dia < 40) & (dia > 26)] = (0.86, 0.64, 0.24)
rug[core & (dia < 12)] = (0.15, 0.2, 0.33)
rug[(yy > 52) & (yy < 60) & inner] = (0.15, 0.2, 0.33)
rug[(yy > H_ - 60) & (yy < H_ - 52) & inner] = (0.15, 0.2, 0.33)
save_png("rug", rug)
m_rug, nt, b = new_mat("rug")
tx = node(nt, "ShaderNodeTexImage")
tx.image = load_img(os.path.join(REN, "rug.png"))
nt.links.new(tx.outputs["Color"], b.inputs["Base Color"])
nr = node(nt, "ShaderNodeTexImage")
nr.image = load_img(os.path.join(ASSETS, "t", "rough_linen", "nor.jpg"), True)
mpr = node(nt, "ShaderNodeMapping")
mpr.inputs["Scale"].default_value = (5, 4, 1)
nt.links.new(node(nt, "ShaderNodeTexCoord").outputs["UV"], mpr.inputs["Vector"])
nt.links.new(mpr.outputs["Vector"], nr.inputs["Vector"])
nmr = node(nt, "ShaderNodeNormalMap")
nt.links.new(nr.outputs["Color"], nmr.inputs["Color"])
nt.links.new(nmr.outputs["Normal"], b.inputs["Normal"])
setin(b, "Roughness", 0.95)
setin(b, "Sheen Weight", 0.8)
mesh_obj("rug", bm_box(2.5, 1.65, 0.012), m_rug, R, loc=(0.3, 0.15, 0.006), rot=(0, 0, 0.04))

# pinned notes (album facts)
notes = empty("notes", R)
for lines, x, z, rz in (("개화\nFLOWERING\n정규 4집\n2026.04.07", -2.05, 1.85, 0.06), ("01\n소문의 낙원\n3:38\n선공개 04.03", -1.62, 1.5, -0.08), ("04\n기쁨, 슬픔,\n아름다운 마음\nTITLE", -2.12, 1.25, 0.04)):
    n_ = empty("note", R, loc=(x, RD / 2 - 0.004, z), parent=notes)
    n_.rotation_euler = (0, rz, 0)
    mesh_obj("note_paper", bm_plane(0.28, 0.28), M_PAPER, R, n_, rot=(math.pi / 2, 0, 0))
    text(R, n_, lines, 0.03, (-0.115, -0.003, 0.085), mat=M_INK)
    mesh_obj("pin", bm_sphere(0.009), flat("pin", (0.75, 0.15, 0.1), rough=0.3, coat=1), R, n_, loc=(0, -0.008, 0.125), smooth=True)
tag(notes, "notes")


# ================================================================== render settings + metadata
def setup(scene):
    scene.render.engine = "CYCLES"
    c = scene.cycles
    c.device = "GPU"
    c.samples = 512
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.01
    c.use_denoising = True
    c.sample_clamp_indirect = 6
    c.max_bounces = 10
    c.volume_bounces = 1
    for attr, val in (("denoiser", "OPENIMAGEDENOISE"), ("denoising_use_gpu", True)):
        try:
            setattr(c, attr, val)
        except Exception:
            pass
    try:
        scene.view_settings.view_transform = "AgX"
    except Exception:
        pass
    scene.view_settings.exposure = 0.0
    scene.render.resolution_percentage = 100


setup(D)
setup(R)
R.view_settings.exposure = 0.85


def t3(v):
    return [round(v.x, 4), round(v.z, 4), round(-v.y, 4)]


meta = {"dunes": {"camera": t3(Vector((0, 0, 1.6))), "hot": {}}, "room": {"camera": t3(Vector((0.7, -1.0, 1.5))), "hot": {}}}
for sc, key in ((D, "dunes"), (R, "room")):
    sc.view_layers[0].update()
    groups = {}
    for o in sc.objects:
        k = o.get("akey")
        if k and o.type in ("MESH", "FONT"):
            for c in o.bound_box:
                groups.setdefault(k, []).append(o.matrix_world @ Vector(c))
    for k, pts in groups.items():
        mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        meta[key]["hot"][k] = {"center": t3((mn + mx) / 2)}
R.view_layers[0].update()
sw = scr.matrix_world
meta["room"]["tvScreen"] = [t3(sw @ Vector((sx * sz.x * 0.31, sy * sz.z * 0.28, 0))) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
meta["sun"] = t3(SUN_DIR)
meta["doors"] = {"dunes": {"pos": t3(door_g.matrix_world.translation), "rz": door_g.rotation_euler.z},
                 "room": {"pos": t3(back_door.matrix_world.translation), "rz": back_door.rotation_euler.z}}
with open(os.path.join(WORK, "meta.json"), "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=1)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "akmu.blend"))
print("BUILD OK", len(D.objects), "dune objects,", len(R.objects), "room objects")
