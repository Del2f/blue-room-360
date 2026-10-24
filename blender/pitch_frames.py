"""Style frames for the '소문의 낙원' pitch: the Mũi Né paradise and Lee Chan-hyuk's room.

    blender -b --factory-startup -P pitch_frames.py -- --work <dir> --cover <cover.jpg> --out <frames dir>
        [--frames F1,F2,...] [--samples 256] [--w 1920 --h 1080] [--save 1]

<dir>/assets holds the Poly Haven CC0 downloads. Builds both scenes, then renders the
requested frames as JPEG. Blender is Z-up; the dune wall lies to +Y, the lake to -X.
"""
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ARGS = {argv[i]: argv[i + 1] for i in range(0, len(argv) - 1, 2)}
WORK = ARGS["--work"]
ASSETS = os.path.join(WORK, "assets")
COVER = ARGS["--cover"]
OUTDIR = ARGS["--out"]
os.makedirs(OUTDIR, exist_ok=True)
TAU = math.tau

bpy.ops.wm.read_factory_settings(use_empty=True)
LIB = bpy.context.scene
LIB.name = "LIB"
P = bpy.data.scenes.new("PARADISE")
R = bpy.data.scenes.new("ROOM")


# ---------------------------------------------------------------- generic helpers
def smooth(x, a, b):
    t = np.clip((np.asarray(x, dtype=np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


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


def setin(b, name, v):
    if name in b.inputs:
        b.inputs[name].default_value = v


def mix_rgb(nt, blend, fac=1.0):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = blend
    n.inputs[0].default_value = fac
    ins = [s for s in n.inputs if s.type == "RGBA"]
    return n, ins[0], ins[1], [s for s in n.outputs if s.type == "RGBA"][0]


def pbr(name, tdir, scale=1.0, box=True, tint=None, hsv=None, rough=1.0, nstr=1.0, coat=0.0, sheen=0.0):
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

    d, a, nn = tex("diff.jpg", False), tex("arm.jpg", True), tex("nor.jpg", True)
    col = d.outputs["Color"]
    if hsv:
        h = node(nt, "ShaderNodeHueSaturation")
        h.inputs["Hue"].default_value, h.inputs["Saturation"].default_value, h.inputs["Value"].default_value = hsv
        nt.links.new(col, h.inputs["Color"])
        col = h.outputs["Color"]
    if tint:
        _, A, B, O = mix_rgb(nt, "MULTIPLY")
        nt.links.new(col, A)
        B.default_value = (*tint, 1)
        col = O
    nt.links.new(col, b.inputs["Base Color"])
    sep = node(nt, "ShaderNodeSeparateColor")
    nt.links.new(a.outputs["Color"], sep.inputs["Color"])
    mm = node(nt, "ShaderNodeMath", operation="MULTIPLY")
    mm.inputs[1].default_value = rough
    nt.links.new(sep.outputs[1], mm.inputs[0])
    nt.links.new(mm.outputs[0], b.inputs["Roughness"])
    nm = node(nt, "ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = nstr
    nt.links.new(nn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    setin(b, "Coat Weight", coat)
    setin(b, "Sheen Weight", sheen)
    return m


def flat(name, color, rough=0.5, metal=0.0, coat=0.0, sheen=0.0, trans=0.0, ior=1.45, emit=None, estr=0.0):
    m, nt, b = new_mat(name)
    setin(b, "Base Color", (*color, 1))
    setin(b, "Roughness", rough)
    setin(b, "Metallic", metal)
    setin(b, "Coat Weight", coat)
    setin(b, "Sheen Weight", sheen)
    setin(b, "Transmission Weight", trans)
    setin(b, "IOR", ior)
    if emit:
        setin(b, "Emission Color", (*emit, 1))
        setin(b, "Emission Strength", estr)
    return m


def image_mat(name, path, rough=0.6, sheen=0.0, emit=0.0):
    m, nt, b = new_mat(name)
    tx = node(nt, "ShaderNodeTexImage")
    tx.image = load_img(path)
    tx.extension = "EXTEND"
    nt.links.new(tx.outputs["Color"], b.inputs["Base Color"])
    if emit:
        nt.links.new(tx.outputs["Color"], b.inputs["Emission Color"])
        setin(b, "Emission Strength", emit)
    setin(b, "Roughness", rough)
    setin(b, "Sheen Weight", sheen)
    return m


def save_png(name, arr):
    h, w, _ = arr.shape
    im = bpy.data.images.new(name, w, h, alpha=False)
    im.pixels.foreach_set(np.concatenate([arr[::-1], np.ones((h, w, 1))], 2).astype(np.float32).ravel())
    path = os.path.join(WORK, "renders", name + ".png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    return path


def mesh_obj(name, bm, mat, scene, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), bevel=0.0, smooth_shade=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth_shade:
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
    bm.loops.layers.uv.new()
    bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    return bm


def bm_cyl(r1, r2, depth, seg=40):
    bm = bmesh.new()
    bm.loops.layers.uv.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r1, radius2=r2, depth=depth, calc_uvs=True)
    return bm


def bm_sphere(r, u=40, v=20):
    bm = bmesh.new()
    bm.loops.layers.uv.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r, calc_uvs=True)
    return bm


def bm_plane(sx, sy, nx=1, ny=1):
    bm = bmesh.new()
    bm.loops.layers.uv.new()
    bmesh.ops.create_grid(bm, x_segments=nx, y_segments=ny, size=0.5, calc_uvs=True)
    bmesh.ops.scale(bm, vec=(sx, sy, 1), verts=bm.verts)
    return bm


def bm_lathe(profile, seg=64, wobble=None):
    """profile: list of (radius, z). Revolve around Z."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        ring = []
        for i in range(seg):
            a = TAU * i / seg
            rr = r * (1 + (wobble(a, z) if wobble else 0))
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z)))
        rings.append(ring)
    for k in range(len(rings) - 1):
        for i in range(seg):
            bm.faces.new((rings[k][i], rings[k][(i + 1) % seg], rings[k + 1][(i + 1) % seg], rings[k + 1][i]))
    return bm


def bm_torus(R_, r, su=64, sv=12, arc=TAU):
    bm = bmesh.new()
    n = su + (0 if arc >= TAU - 1e-6 else 1)
    rings = []
    for i in range(n):
        a = arc * i / su
        rings.append([bm.verts.new(((R_ + r * math.cos(b)) * math.cos(a), 0 * a + (R_ + r * math.cos(b)) * math.sin(a), r * math.sin(b))) for b in (TAU * j / sv for j in range(sv))])
    for i in range(su):
        i2 = (i + 1) % n if arc >= TAU - 1e-6 else i + 1
        for j in range(sv):
            bm.faces.new((rings[i][j], rings[i2][j], rings[i2][(j + 1) % sv], rings[i][(j + 1) % sv]))
    return bm


def camera_only(ob):
    for p in ("visible_diffuse", "visible_glossy", "visible_shadow", "visible_transmission", "visible_volume_scatter"):
        setattr(ob, p, False)


def light(scene, kind, name, energy, color, loc, rot=(0, 0, 0), size=0.1, parent=None, cam=False):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    elif kind in ("POINT", "SPOT"):
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.rotation_euler = rot
    ob.visible_camera = cam
    return link(ob, scene, parent)


# ---------------------------------------------------------------- library models
LIBM = {}


def import_model(mid):
    folder = os.path.join(ASSETS, "m", mid)
    path = os.path.join(folder, next(f for f in sorted(os.listdir(folder)) if f.endswith(".gltf")))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    LIBM[mid] = {"objs": new, "mn": mn, "mx": mx}


def spawn(mid, scene, parent=None, loc=(0, 0, 0), rz=0.0, s=1.0):
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


def recolor(mid, test, hsv=None, tint=None):
    """Insert a hue/saturation and/or tint step on the base colour of matching materials."""
    mats = {ms.material for o in LIBM[mid]["objs"] if o.type == "MESH" for ms in o.material_slots if ms.material}
    for m in mats:
        if not test(m.name.lower()):
            continue
        nt = m.node_tree
        b = nt.nodes.get("Principled BSDF")
        if not b:
            continue
        src = b.inputs["Base Color"].links[0].from_socket if b.inputs["Base Color"].is_linked else None
        out = src
        if hsv and src is not None:
            h = node(nt, "ShaderNodeHueSaturation")
            h.inputs["Hue"].default_value, h.inputs["Saturation"].default_value, h.inputs["Value"].default_value = hsv
            nt.links.new(out, h.inputs["Color"])
            out = h.outputs["Color"]
        if tint:
            _, A, B, O = mix_rgb(nt, "MIX", tint[3] if len(tint) > 3 else 0.6)
            if out is not None:
                nt.links.new(out, A)
            else:
                A.default_value = b.inputs["Base Color"].default_value
            B.default_value = (*tint[:3], 1)
            out = O
        if out is not None:
            nt.links.new(out, b.inputs["Base Color"])


PLANTS = {
    "grass": ["grass_medium_01", "grass_medium_02", "grass_bermuda_01"],
    "bloom": ["didelta_spinosa", "flower_gazania", "flower_ursinia", "shrub_01", "shrub_04"],
    "edge": ["crystalline_iceplant", "sand_rocks_small_01", "namaqualand_stones_01", "dry_branches_medium_01"],
    "dunefoot": ["searsia_lucida", "shrub_02", "wild_rooibos_bush", "didelta_spinosa"],
    "shore": ["rock_moss_set_02", "sand_rocks_small_01", "grass_medium_02"],
}
GREEN_GRASS = True
ROOM_PROPS = ["Ukulele_01", "chess_set", "throw_pillows_01", "brass_candleholders", "standing_picture_frame_01",
              "book_encyclopedia_set_01", "potted_plant_02"]
for mid in sorted({m for v in PLANTS.values() for m in v}) + ["Sofa_01", "ArmChair_01", "Chandelier_02",
            "GothicBed_01", "ClassicNightstand_01", "painted_wooden_cabinet", "fancy_picture_frame_01", "fancy_picture_frame_02",
            "vintage_grandfather_clock_01", "vintage_oil_lamp", "wooden_table_02", "painted_wooden_chair_01"] + ROOM_PROPS:
    import_model(mid)
for mid in PLANTS["grass"]:
    recolor(mid, lambda n: True, hsv=(0.56, 1.6, 1.35), tint=(0.3, 0.55, 0.12, 0.35))
import_model("tree_small_02")
recolor("tree_small_02", lambda n: "leaf" in n or "leaves" in n or "foliage" in n, tint=(0.95, 0.7, 0.12, 0.75))

# ---------------------------------------------------------------- shared materials
M_LINEN = pbr("canvas", "rough_linen", scale=2.0, tint=(0.97, 0.95, 0.9), sheen=0.4)
M_WOOD = pbr("weathered", "weathered_peeling_timber", scale=1.0, hsv=(0.5, 0.8, 0.95))
M_DOOR = pbr("door_paint", "wood_peeling_paint_weathered", scale=1.8, hsv=(0.5, 1.0, 1.6))
M_BRASS = flat("brass", (0.78, 0.6, 0.28), rough=0.25, metal=1.0)
M_ROPE = flat("rope", (0.6, 0.5, 0.36), rough=0.9)
M_WHITE = flat("white_paint", (0.92, 0.92, 0.9), rough=0.4)


# ---------------------------------------------------------------- world helpers
def world_from_hdr(name, hdr_path, strength, sun_az_deg, min_elev=8, tint=None):
    img = load_img(hdr_path)
    w_, h_ = img.size
    px = np.empty(w_ * h_ * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h_, w_, 4)
    lum = px[..., 0] * 0.2126 + px[..., 1] * 0.7152 + px[..., 2] * 0.0722
    row, col = np.unravel_index(int(np.argmax(lum)), lum.shape)
    u, v = (col + 0.5) / w_, (row + 0.5) / h_
    phi, theta = (u - 0.5) * TAU, (v - 0.5) * math.pi
    s = Vector((-math.cos(theta) * math.cos(phi), math.cos(theta) * math.sin(phi), math.sin(theta)))
    target = math.radians(sun_az_deg)
    rot = math.atan2(s.y, s.x) - target
    elev = max(math.asin(max(min(s.z, 1), -1)), math.radians(min_elev))
    sun_dir = Vector((math.cos(elev) * math.cos(target), math.cos(elev) * math.sin(target), math.sin(elev)))
    w = bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = node(nt, "ShaderNodeOutputWorld")
    bg = node(nt, "ShaderNodeBackground")
    env = node(nt, "ShaderNodeTexEnvironment")
    env.image = img
    tc = node(nt, "ShaderNodeTexCoord")
    mp = node(nt, "ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, rot)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    if tint:
        mx, ta, tb, tout = mix_rgb(nt, "MULTIPLY")
        mx.inputs[0].default_value = 1.0
        nt.links.new(env.outputs["Color"], ta)
        tb.default_value = (*tint, 1)
        nt.links.new(tout, bg.inputs["Color"])
    else:
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    w["sun_dir"] = list(sun_dir)
    print("WORLD", name, "sun elev", round(math.degrees(elev), 1))
    return w


# ================================================================== PARADISE (Bàu Trắng, Mũi Né)
W_DAY = world_from_hdr("day", os.path.join(ASSETS, "h", "qwantani_late_afternoon_puresky_8k.hdr"), 1.0, sun_az_deg=-125, tint=(0.9, 0.98, 1.12))
W_GOLD = world_from_hdr("golden", os.path.join(ASSETS, "h", "qwantani_sunset_puresky_8k.hdr"), 1.1, sun_az_deg=160, min_elev=10)
P.world = W_DAY
SUN_P = light(P, "SUN", "sun", 3.6, (1.0, 0.95, 0.86), (0, 0, 50))
SUN_P.data.angle = math.radians(0.8)


def terrain(x, y):
    h = 0.12 * np.sin(x * 0.21 + np.sin(y * 0.13)) * np.cos(y * 0.17) + 0.05 * np.sin(x * 0.7 + y * 0.5)
    lake = np.clip(1 - (((x + 24) / 18) ** 2 + ((y - 9) / 10) ** 2), 0, 1)
    h = h - 1.0 * lake ** 0.55
    yc = 62 + 7 * np.sin(x * 0.035) + 3 * np.sin(x * 0.09 + 1)
    H = 17 + 5 * np.sin(x * 0.028 + 1.0)
    d = y - yc
    prof = np.where(d < 0, np.exp(-(d / 22) ** 2), np.exp(-(d / 8) ** 2))
    dune = H * prof
    back = smooth(y, 95, 170) * (12 + 7 * np.sin(x * 0.02 + 0.4) + 4 * np.sin(x * 0.051))
    return h + dune + back, dune, lake


N = 700
xs = np.linspace(-170, 170, N + 1)
ys = np.linspace(-70, 270, N + 1)
X, Y = np.meshgrid(xs, ys)
Z, DUNE, LAKE = terrain(X, Y)
dist = np.hypot(X - 4, Y + 10)
patch = 0.5 + 0.5 * np.sin(X * 0.17 + np.sin(Y * 0.11) * 2.0) * np.cos(Y * 0.13 + X * 0.05)
MEADOW = smooth(0.9 - DUNE, 0.0, 0.6) * (1 - smooth(LAKE, 0.02, 0.15)) * (1 - smooth(Y, 20, 27)) * (1 - smooth(dist, 75, 115))
MEADOW = np.clip(MEADOW * (0.9 + 0.3 * patch), 0, 1)
verts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1).astype(np.float32)
idx = np.arange((N + 1) * (N + 1)).reshape(N + 1, N + 1)
quads = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)
me = bpy.data.meshes.new("ground")
me.vertices.add(len(verts))
me.vertices.foreach_set("co", verts.ravel())
me.loops.add(quads.size)
me.loops.foreach_set("vertex_index", quads.ravel().astype(np.int32))
me.polygons.add(len(quads))
me.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4, dtype=np.int32))
me.update(calc_edges=True)
me.shade_smooth()
attr = me.attributes.new("meadow", "FLOAT", "POINT")
attr.data.foreach_set("value", MEADOW.ravel().astype(np.float32))
E = ((X + 24) / 18) ** 2 + ((Y - 9) / 10) ** 2
SHORE = smooth(E, 0.72, 0.86) * (1 - smooth(E, 1.1, 1.5))
DUNEFOOT = smooth(DUNE, 0.25, 0.9) * (1 - smooth(DUNE, 2.5, 5.5)) * (Y < 60)
CAMP = 1 - smooth(np.hypot((X - 6) / 1.3, Y - 15.5), 8, 12)
EDGE = np.clip(4 * MEADOW * (1 - MEADOW), 0, 1) * (1 - CAMP)
for nm, arr in (("shore", SHORE), ("dunefoot", DUNEFOOT), ("edge", EDGE), ("wild", MEADOW * (1 - CAMP) * (1 - SHORE))):
    me.attributes.new(nm, "FLOAT", "POINT").data.foreach_set("value", np.clip(arr, 0, 1).ravel().astype(np.float32))

# ground shader: photo-scanned Poly Haven sand, bleached toward the white sand of Bau Trang;
# 30 m wind ripples from aerial_beach_01, damp sand at the lake, grass and mud where "meadow" is set
m_g, nt, b = new_mat("ground")
tc = node(nt, "ShaderNodeTexCoord")


def gmap(scale, rot=0.0):
    mp = node(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    mp.inputs["Rotation"].default_value = (0, 0, rot)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    return mp


def tex3(folder, mp, files=("diff.jpg", "arm.jpg", "nor.jpg")):
    out = []
    for f in files:
        t = node(nt, "ShaderNodeTexImage")
        t.image = load_img(os.path.join(ASSETS, "t", folder, f), f != "diff.jpg")
        nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
        out.append(t)
    return out


def gattr(name):
    a = node(nt, "ShaderNodeAttribute")
    a.attribute_type = "GEOMETRY"
    a.attribute_name = name
    return a.outputs["Fac"]


def mixc(fac, a, b_, blend="MIX"):
    n, A, B, O = mix_rgb(nt, blend)
    if isinstance(fac, float):
        n.inputs[0].default_value = fac
    else:
        nt.links.new(fac, n.inputs[0])
    for sock, v in ((A, a), (B, b_)):
        if isinstance(v, tuple):
            sock.default_value = v
        else:
            nt.links.new(v, sock)
    return O


big_d, big_a, big_n = tex3("aerial_beach_01", gmap(1 / 30, 0.6))
fine_d, fine_a, fine_n = tex3("coast_sand_01", gmap(0.5))
damp_d, damp_a, damp_n = tex3("damp_beach_sand", gmap(0.5, 1.1))
grs_d, grs_a, grs_n = tex3("sparse_grass", gmap(0.5, 0.3))
mud_d, mud_a, mud_n = tex3("brown_mud_02", gmap(0.7, 2.0))
sand = mixc(0.55, big_d.outputs["Color"], fine_d.outputs["Color"])
hs = node(nt, "ShaderNodeHueSaturation")
hs.inputs["Saturation"].default_value = 0.3
hs.inputs["Value"].default_value = 1.7
nt.links.new(sand, hs.inputs["Color"])
sand = mixc(1.0, hs.outputs["Color"], (1.0, 0.93, 0.8, 1), "MULTIPLY")
# large-scale tone variation so the white sand is never one flat colour
vn = node(nt, "ShaderNodeTexNoise")
vn.inputs["Scale"].default_value = 0.035
nt.links.new(tc.outputs["Object"], vn.inputs["Vector"])
vr = node(nt, "ShaderNodeMapRange")
vr.inputs["To Min"].default_value, vr.inputs["To Max"].default_value = 0.86, 1.06
nt.links.new(vn.outputs["Fac"], vr.inputs["Value"])
vc = node(nt, "ShaderNodeCombineColor")
for k in ("Red", "Green", "Blue"):
    nt.links.new(vr.outputs["Result"], vc.inputs[k])
sand = mixc(1.0, sand, vc.outputs["Color"], "MULTIPLY")
gh = node(nt, "ShaderNodeHueSaturation")
gh.inputs["Hue"].default_value = 0.58
gh.inputs["Saturation"].default_value = 1.7
gh.inputs["Value"].default_value = 1.4
nt.links.new(grs_d.outputs["Color"], gh.inputs["Color"])
meadow_col = mixc(0.12, gh.outputs["Color"], mud_d.outputs["Color"])
col = mixc(gattr("shore"), sand, damp_d.outputs["Color"])
col = mixc(gattr("meadow"), col, meadow_col)
nt.links.new(col, b.inputs["Base Color"])
rough = mixc(gattr("shore"), (0.93, 0.93, 0.93, 1), (0.55, 0.55, 0.55, 1))
nt.links.new(rough, b.inputs["Roughness"])
nrm = mixc(0.5, big_n.outputs["Color"], fine_n.outputs["Color"])
nrm = mixc(gattr("shore"), nrm, damp_n.outputs["Color"])
nrm = mixc(gattr("meadow"), nrm, mixc(0.5, grs_n.outputs["Color"], mud_n.outputs["Color"]))
nms = node(nt, "ShaderNodeNormalMap")
nms.inputs["Strength"].default_value = 1.4
nt.links.new(nrm, nms.inputs["Color"])
nt.links.new(nms.outputs["Normal"], b.inputs["Normal"])
me.materials.append(m_g)
ground = link(bpy.data.objects.new("ground", me), P)

# lake (Bàu Trắng is a pair of lakes at the foot of the white dunes)
water, nt, wb = new_mat("water")
setin(wb, "Base Color", (0.06, 0.16, 0.17, 1))
setin(wb, "Roughness", 0.04)
setin(wb, "IOR", 1.33)
nzw = node(nt, "ShaderNodeTexNoise")
nzw.inputs["Scale"].default_value = 3.5
bw = node(nt, "ShaderNodeBump")
bw.inputs["Strength"].default_value = 0.06
nt.links.new(nzw.outputs["Fac"], bw.inputs["Height"])
nt.links.new(bw.outputs["Normal"], wb.inputs["Normal"])
mesh_obj("lake", bm_plane(60, 34), water, P, loc=(-24, 9, -0.32))

# vegetation: Geometry Nodes scatter layers. Each picks Poly Haven scans where its mask attribute
# is high, thinned by a noise field so plants grow in clumps and gaps instead of an even carpet.
def scatter(name, mids, density, mask, smin, smax, clump=0.0, seed=0, tilt=0.12, crange=(0.45, 0.62)):
    col = bpy.data.collections.new(name)
    for mid in mids:
        for o in LIBM[mid]["objs"]:
            if o.type == "MESH" and o.name not in col.objects:
                col.objects.link(o)
    ng = bpy.data.node_groups.new("scatter_" + name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N = ng.nodes.new
    gi, go = N("NodeGroupInput"), N("NodeGroupOutput")
    dist_n = N("GeometryNodeDistributePointsOnFaces")
    dist_n.inputs["Density"].default_value = density
    dist_n.inputs["Seed"].default_value = seed
    na = N("GeometryNodeInputNamedAttribute")
    na.data_type = "FLOAT"
    na.inputs["Name"].default_value = mask
    prob = na.outputs["Attribute"]
    if clump:
        nz = N("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = clump
        nz.inputs["Detail"].default_value = 3
        mr = N("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = crange
        ng.links.new(nz.outputs["Fac"], mr.inputs["Value"])
        mul = N("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        ng.links.new(prob, mul.inputs[0])
        ng.links.new(mr.outputs["Result"], mul.inputs[1])
        prob = mul.outputs[0]
    rnd = N("FunctionNodeRandomValue")
    rnd.data_type = "FLOAT"
    [x for x in rnd.inputs if x.name == "Seed"][0].default_value = seed + 7
    cmp = N("FunctionNodeCompare")
    cmp.data_type = "FLOAT"
    cmp.operation = "LESS_THAN"
    ng.links.new(rnd.outputs[0], cmp.inputs[0])
    ng.links.new(prob, cmp.inputs[1])
    ci = N("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = col
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    iop = N("GeometryNodeInstanceOnPoints")
    iop.inputs["Pick Instance"].default_value = True
    rv = N("FunctionNodeRandomValue")
    rv.data_type = "FLOAT_VECTOR"
    [x for x in rv.inputs if x.name == "Max" and x.type == "VECTOR"][0].default_value = (tilt, tilt, TAU)
    [x for x in rv.inputs if x.name == "Min" and x.type == "VECTOR"][0].default_value = (-tilt, -tilt, 0)
    [x for x in rv.inputs if x.name == "Seed"][0].default_value = seed + 11
    rs = N("FunctionNodeRandomValue")
    rs.data_type = "FLOAT"
    [x for x in rs.inputs if x.name == "Min" and x.type == "VALUE"][0].default_value = smin
    [x for x in rs.inputs if x.name == "Max" and x.type == "VALUE"][0].default_value = smax
    [x for x in rs.inputs if x.name == "Seed"][0].default_value = seed + 13
    join = N("GeometryNodeJoinGeometry")
    L = ng.links.new
    L(gi.outputs[0], dist_n.inputs["Mesh"])
    L(cmp.outputs["Result"], dist_n.inputs["Selection"])
    L(dist_n.outputs["Points"], iop.inputs["Points"])
    L(ci.outputs[0], iop.inputs["Instance"])
    L([x for x in rv.outputs if x.type == "VECTOR"][0], iop.inputs["Rotation"])
    L([x for x in rs.outputs if x.type == "VALUE"][0], iop.inputs["Scale"])
    L(gi.outputs[0], join.inputs[0])
    L(iop.outputs[0], join.inputs[0])
    L(join.outputs[0], go.inputs[0])
    ground.modifiers.new(name, "NODES").node_group = ng


scatter("grass", PLANTS["grass"], 45.0, "meadow", 0.45, 0.95, clump=0.18, seed=1, crange=(0.15, 0.35))
scatter("bloom", PLANTS["bloom"], 0.25, "wild", 0.45, 0.9, clump=0.07, seed=2)
scatter("edge", PLANTS["edge"], 0.5, "edge", 0.6, 1.4, clump=0.12, seed=3, tilt=0.3)
scatter("dunefoot", PLANTS["dunefoot"], 0.03, "dunefoot", 0.8, 1.6, clump=0.05, seed=4)
scatter("shore", PLANTS["shore"], 0.4, "shore", 0.6, 1.5, clump=0.1, seed=5, tilt=0.3)

rng = np.random.default_rng(8)
for cx, cy, n in ((-18, 27, 15), (-31, 23, 10), (24, 27, 12), (14, 33, 8)):
    for i in range(n):
        x, y = cx + rng.normal(0, 3.6), cy + rng.normal(0, 2.0)
        t = terrain(np.array(x), np.array(y))
        if float(t[2]) > 0.02:
            continue
        spawn("tree_small_02", P, loc=(x, y, float(t[0]) - 0.1), rz=rng.uniform(0, TAU), s=rng.uniform(0.95, 1.35))

# --- festival camp ---------------------------------------------------------------
def ground_z(x, y):
    return float(terrain(np.array(x), np.array(y))[0])


# the stage wagon from the MV: green wagon with lilac steps, wooden corner posts with knobs, dark-green
# side panels with white climbing roses, a teal front with an arched opening outlined in pink (the dunes
# show through it), blue curtains drawn aside, and a teal arch painted with a spiky gold sun
def save_rgba(name, arr):
    h, w, _ = arr.shape
    im = bpy.data.images.new(name, w, h, alpha=True)
    im.pixels.foreach_set(np.clip(arr[::-1], 0, 1).astype(np.float32).ravel())
    path = os.path.join(WORK, "renders", name + ".png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    return path


def alpha_mat(name, path, rough=0.7):
    m, nt, b = new_mat(name)
    tx = node(nt, "ShaderNodeTexImage")
    tx.image = load_img(path)
    tx.extension = "CLIP"
    nt.links.new(tx.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(tx.outputs["Alpha"], b.inputs["Alpha"])
    setin(b, "Roughness", rough)
    return m


PX = 400  # texture pixels per metre
TEAL, TEAL_D, GREEN_D, PINK = (0.13, 0.42, 0.6), (0.08, 0.3, 0.45), (0.07, 0.25, 0.15), (0.86, 0.36, 0.42)
rngp = np.random.default_rng(4)


def disc(img, fx, fy, r, col):
    y0, y1 = int(max(fy - r, 0)), int(min(fy + r + 1, img.shape[0]))
    x0, x1 = int(max(fx - r, 0)), int(min(fx + r + 1, img.shape[1]))
    yy, xx = np.mgrid[y0:y1, x0:x1]
    m = (xx - fx) ** 2 + (yy - fy) ** 2 < r * r
    img[y0:y1, x0:x1, :3][m] = col


def roses(img, x0, x1, y0, y1, n, vines=2):
    """White climbing roses: wavy vines with blossoms along them."""
    yy = np.arange(y0, y1)
    for k in range(vines):
        cx = x0 + (x1 - x0) * (0.3 + 0.4 * k / max(vines - 1, 1))
        vx = cx + (x1 - x0) * 0.16 * np.sin(yy / 55.0 + k * 2)
        for yv, xv in zip(yy[::2], vx[::2]):
            disc(img, xv, yv, 3, (0.2, 0.42, 0.22))
    for _ in range(n):
        fx, fy = rngp.uniform(x0 + 12, x1 - 12), rngp.uniform(y0 + 12, y1 - 12)
        r = rngp.uniform(8, 14)
        disc(img, fx, fy, r, (0.96, 0.94, 0.9) if rngp.random() > 0.2 else (0.95, 0.72, 0.78))
        disc(img, fx, fy, r * 0.35, (0.92, 0.78, 0.45))


def front_panel():
    h_, w_ = int(3.1 * PX), int(4.6 * PX)
    img = np.ones((h_, w_, 4))
    img[..., :3] = TEAL
    side, band = int(0.95 * PX), int(0.35 * PX)
    img[:, :side, :3] = GREEN_D
    img[:, w_ - side:, :3] = GREEN_D
    img[:band, side:w_ - side, :3] = TEAL_D
    roses(img, 0, side, 0, h_, 80)
    roses(img, w_ - side, w_, 0, h_, 80)
    roses(img, side, w_ - side, int(band * 0.2), int(band * 0.9), 45, vines=1)
    yy, xx = np.mgrid[0:h_, 0:w_]
    cx, ow, top_y = w_ / 2, 0.95 * PX, h_ - 1.55 * PX

    def arch(o):
        return ((np.abs(xx - cx) < ow + o) & (yy > top_y)) | ((xx - cx) ** 2 + (yy - top_y) ** 2 < (ow + o) ** 2)
    inner = arch(0)
    img[arch(0.07 * PX) & ~inner, :3] = PINK
    img[..., :3] += rngp.normal(0, 0.02, (h_, w_, 1))
    img[inner, 3] = 0
    return save_rgba("stage_front", img)


def sun_arch():
    h_, w_ = int(1.5 * PX), int(3.0 * PX)
    img = np.zeros((h_, w_, 4))
    yy, xx = np.mgrid[0:h_, 0:w_]
    cx, cy, R0 = w_ / 2, h_, 1.5 * PX
    r = np.hypot(xx - cx, yy - cy)
    img[..., :3] = TEAL
    img[..., 3] = r < R0
    img[(r > R0 - 0.13 * PX) & (r < R0), :3] = TEAL_D
    for k in range(25):
        a = math.pi * (k + 0.5) / 25
        disc(img, cx + math.cos(a) * (R0 - 0.065 * PX), cy - math.sin(a) * (R0 - 0.065 * PX), 0.035 * PX, (0.97, 0.95, 0.9))
    sy = cy - 0.62 * PX
    rr, a = np.hypot(xx - cx, yy - sy), np.arctan2(yy - sy, xx - cx)
    f = a / TAU * 18
    tri = 1 - np.abs((f % 1) - 0.5) * 2
    long = np.where(np.floor(f) % 2 == 0, 1.0, 0.6)
    img[rr < 0.2 * PX + 0.36 * PX * tri ** 2 * long, :3] = (0.96, 0.76, 0.2)
    img[rr < 0.2 * PX, :3] = (0.98, 0.83, 0.32)
    img[..., :3] += rngp.normal(0, 0.02, (h_, w_, 1))
    return save_rgba("stage_sun", img)


stage = empty("stage", P, loc=(7, 17, ground_z(7, 17) - 0.05), rz=0.12)
M_POST = flat("post_wood", (0.24, 0.15, 0.09), rough=0.6)
mesh_obj("deck", bm_box(6.0, 3.2, 0.5), flat("wagon_green", (0.07, 0.36, 0.26), rough=0.55, coat=0.2), P, stage, loc=(0, 0, 0.25), bevel=0.02)
M_LILAC = flat("lilac", (0.66, 0.58, 0.82), rough=0.6)
for hgt, yo in ((0.38, -1.78), (0.25, -2.12), (0.12, -2.46)):
    mesh_obj("step", bm_box(1.3, 0.34, hgt), M_LILAC, P, stage, loc=(-2.0, yo, hgt / 2), bevel=0.01)
FY, BY, X2 = -0.3, 1.1, 2.38
mesh_obj("front", bm_plane(4.6, 3.1), alpha_mat("stage_front", front_panel()), P, stage, loc=(0, FY, 0.5 + 1.55), rot=(math.pi / 2, 0, 0))
mesh_obj("sun_arch", bm_plane(3.0, 1.5), alpha_mat("stage_sun", sun_arch()), P, stage, loc=(0, FY, 0.5 + 3.1 + 0.75), rot=(math.pi / 2, 0, 0))
M_SIDE = flat("side_green", GREEN_D, rough=0.7)
for sx in (-1, 1):
    mesh_obj("side", bm_box(0.04, BY - FY, 3.1), M_SIDE, P, stage, loc=(sx * X2, (FY + BY) / 2, 0.5 + 1.55))
    for yv in (FY - 0.03, BY):
        mesh_obj("post", bm_cyl(0.05, 0.05, 4.3, 12), M_POST, P, stage, loc=(sx * X2, yv, 0.5 + 2.15))
        mesh_obj("knob", bm_sphere(0.085, 16, 8), M_POST, P, stage, loc=(sx * X2, yv, 0.5 + 4.38), smooth_shade=True)
    mesh_obj("rail", bm_box(0.06, BY - FY, 0.06), M_POST, P, stage, loc=(sx * X2, (FY + BY) / 2, 0.5 + 3.1))
M_STAGE_CURTAIN = pbr("stage_curtain", "velour_velvet", scale=3, hsv=(0.5, 0.0, 1.8), tint=(0.12, 0.34, 0.66), sheen=0.8)
for sx in (-1, 1):
    cb = bm_plane(0.6, 2.5, 24, 8)
    for vv in cb.verts:
        vv.co.z += math.sin(vv.co.x * 40) * 0.035
        vv.co.x *= 1 - 0.35 * max(0.0, -vv.co.y / 1.25)  # gathered toward the bottom
    mesh_obj("drape", cb, M_STAGE_CURTAIN, P, stage, loc=(sx * 0.68, FY + 0.12, 0.5 + 1.25), rot=(math.pi / 2, 0, 0), smooth_shade=True).modifiers.new("s", "SOLIDIFY").thickness = 0.01
# ribbon pole beside the stage
mesh_obj("rpole", bm_cyl(0.03, 0.03, 4.2, 10), M_POST, P, stage, loc=(-3.4, -1.3, 2.1))
for k, c in enumerate(((0.95, 0.75, 0.8), (0.7, 0.85, 0.95), (0.98, 0.9, 0.6), (0.75, 0.9, 0.75), (0.85, 0.75, 0.95), (0.97, 0.97, 0.95))):
    mesh_obj("ribbon", bm_plane(0.12, 2.0), flat("ribbon%d" % k, c, rough=0.7, sheen=0.5), P, stage,
             loc=(-3.4 + 0.08 * math.cos(k), -1.3 + 0.08 * math.sin(k), 4.2 - 1.2), rot=(math.pi / 2, 0.08 * (k - 2.5), k * 1.05))


TENT_MINT = pbr("tent_mint", "rough_linen", scale=2.0, hsv=(0.5, 0.0, 1.6), tint=(0.6, 0.86, 0.8), sheen=0.4)
TENT_PINK = pbr("tent_pink", "rough_linen", scale=2.0, hsv=(0.5, 0.0, 1.6), tint=(0.94, 0.7, 0.72), sheen=0.4)
TENT_SKY = pbr("tent_sky", "rough_linen", scale=2.0, hsv=(0.5, 0.0, 1.6), tint=(0.78, 0.88, 0.95), sheen=0.4)
M_FLAP = flat("tentdoor", (0.2, 0.16, 0.12), rough=0.9)


def dome_tent(name, loc, r=1.3, h=1.25, rz=0.0, mat=M_LINEN):
    g = empty(name, P, loc=(loc[0], loc[1], ground_z(*loc) - 0.05), rz=rz)
    bm = bm_sphere(r, 48, 24)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.001], context="VERTS")
    bmesh.ops.scale(bm, vec=(1, 1, h / r), verts=bm.verts)
    for v in bm.verts:
        a = math.atan2(v.co.y, v.co.x)
        v.co.x *= 1 - 0.04 * (math.cos(a * 8) ** 2) * (1 - v.co.z / h)
        v.co.y *= 1 - 0.04 * (math.cos(a * 8) ** 2) * (1 - v.co.z / h)
    t = mesh_obj("dome", bm, mat, P, g, smooth_shade=True)
    t.modifiers.new("s", "SOLIDIFY").thickness = 0.01
    mesh_obj("door", bm_box(0.7, 0.05, 0.95), M_FLAP, P, g, loc=(0, -r + 0.06, 0.48))
    return g


def cabin_tent(name, loc, w, d, wall, ridge, mat, rz=0.0, awning=0.0):
    """Canvas cabin tent: short walls, a sagging ridge roof running front to back, optional front awning."""
    g = empty(name, P, loc=(loc[0], loc[1], ground_z(*loc) - 0.05), rz=rz)
    bm = bmesh.new()
    hw, hd = w / 2, d / 2
    V = bm.verts.new
    a0, a1, a2, a3 = V((-hw, -hd, 0)), V((hw, -hd, 0)), V((hw, hd, 0)), V((-hw, hd, 0))
    b0, b1, b2, b3 = V((-hw, -hd, wall)), V((hw, -hd, wall)), V((hw, hd, wall)), V((-hw, hd, wall))
    r0, r1 = V((0, -hd, ridge)), V((0, hd, ridge))
    for f in ((a0, a1, b1, r0, b0), (a2, a3, b3, r1, b2), (a1, a2, b2, b1), (a3, a0, b0, b3), (b0, r0, r1, b3), (r0, b1, b2, r1)):
        bm.faces.new(f)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) == 5])
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=6, use_grid_fill=True)
    for v in bm.verts:
        u = (v.co.y + hd) / d
        if v.co.z > wall * 0.95:
            v.co.z -= 0.07 * math.sin(math.pi * u) * (1 - abs(v.co.x) / hw * 0.5)
        else:
            v.co.x *= 1 + 0.015 * math.sin(v.co.z * 7 + v.co.y * 3)
    t = mesh_obj("cabin", bm, mat, P, g, smooth_shade=True)
    t.modifiers.new("s", "SOLIDIFY").thickness = 0.01
    mesh_obj("flap", bm_plane(0.8, 1.35), M_FLAP, P, g, loc=(0, -hd - 0.015, 0.68), rot=(math.pi / 2, 0, 0))
    if awning:
        tilt = 0.28
        mesh_obj("awning", bm_plane(w * 0.85, awning, 8, 4), mat, P, g, loc=(0, -hd - awning / 2 * math.cos(tilt), wall + 0.1 - awning / 2 * math.sin(tilt)), rot=(tilt, 0, 0)).modifiers.new("s", "SOLIDIFY").thickness = 0.01
        for sx in (-1, 1):
            hz = wall + 0.1 - awning * math.sin(tilt)
            mesh_obj("apole", bm_cyl(0.025, 0.025, hz, 8), M_POST, P, g, loc=(sx * w * 0.4, -hd - awning * math.cos(tilt), hz / 2))
    return g


def teepee(name, loc, r=1.7, h=4.0, rz=0.0, mat=M_LINEN):
    g = empty(name, P, loc=(loc[0], loc[1], ground_z(*loc) - 0.05), rz=rz)
    prof = [(r * (1 - t) + 0.02, h * 0.85 * t) for t in np.linspace(0, 1, 10)]
    t = mesh_obj("cone", bm_lathe(prof, 48, lambda a, z: 0.02 * math.sin(a * 9)), mat, P, g, smooth_shade=True)
    t.modifiers.new("s", "SOLIDIFY").thickness = 0.01
    for i in range(9):
        a = TAU * i / 9
        p0 = Vector((math.cos(a) * r * 1.02, math.sin(a) * r * 1.02, 0))
        p1 = Vector((-math.cos(a) * 0.35, -math.sin(a) * 0.35, h))
        seg = p1 - p0
        c = mesh_obj("tpole", bm_cyl(0.03, 0.025, seg.length, 8), M_POST, P, g, loc=(p0 + p1) / 2)
        c.rotation_euler = seg.to_track_quat("Z", "Y").to_euler()
    return g


# pastel camp on the sand behind the meadow, as in the MV
cabin_tent("tent_mint", (-3.0, 25.0), 3.4, 2.8, 1.1, 2.3, TENT_MINT, rz=0.25, awning=1.4)
cabin_tent("tent_pink", (1.8, 28.0), 3.0, 2.6, 1.0, 2.1, TENT_PINK, rz=-0.15)
cabin_tent("tent_pink2", (5.8, 29.5), 2.4, 2.2, 0.9, 1.8, TENT_PINK, rz=0.35)
dome_tent("dome_white", (-7.5, 27.0), r=1.6, h=1.4, rz=0.3)
dome_tent("dome_sky", (10.5, 27.5), r=1.3, h=1.2, rz=-0.4, mat=TENT_SKY)
teepee("teepee", (2.0, 20.5), r=1.5, h=3.6, mat=TENT_SKY)
# bunting strung over the camp
flag_cols = [(0.12, 0.6, 0.7), (0.95, 0.75, 0.2), (0.8, 0.25, 0.18), (0.95, 0.92, 0.85), (0.25, 0.55, 0.3)]
for (ax, ay, bx, by) in ((-3.0, 25.0, 1.8, 28.0), (1.8, 28.0, 5.8, 29.5), (4.6, 16.7, 2.0, 20.5)):
    pa = Vector((ax, ay, ground_z(ax, ay) + 3.0))
    pb = Vector((bx, by, ground_z(bx, by) + 3.4))
    prev = None
    for i in range(25):
        t = i / 24
        p = pa.lerp(pb, t)
        p.z -= math.sin(t * math.pi) * 0.5
        if prev is not None:
            seg = p - prev
            c = mesh_obj("string", bm_cyl(0.005, 0.005, seg.length, 6), M_ROPE, P, loc=(prev + p) / 2)
            c.rotation_euler = seg.to_track_quat("Z", "Y").to_euler()
        if 0 < i < 24 and i % 2 == 0:
            bmf = bmesh.new()
            v1, v2, v3 = bmf.verts.new((-0.15, 0, 0)), bmf.verts.new((0.15, 0, 0)), bmf.verts.new((0, 0, -0.34))
            bmf.faces.new((v1, v2, v3))
            f = mesh_obj("pennant", bmf, flat("pen%d" % i, flag_cols[(i // 2) % 5], rough=0.8, sheen=0.4), P, loc=p)
            f.rotation_euler = (0, 0, math.atan2(pb.y - pa.y, pb.x - pa.x))
            f.modifiers.new("s", "SOLIDIFY").thickness = 0.003
        prev = p

# the door standing on the dune slope
def make_door(scene, loc, rz, leaf_mat, glow=True):
    g = empty("door", scene, loc=loc, rz=rz)
    for x in (-0.565, 0.565):
        mesh_obj("post", bm_box(0.13, 0.16, 2.3), M_WOOD, scene, g, loc=(x, 0, 1.15), bevel=0.006)
    mesh_obj("lintel", bm_box(1.26, 0.18, 0.15), M_WOOD, scene, g, loc=(0, 0, 2.33), bevel=0.006)
    mesh_obj("sill", bm_box(1.3, 0.36, 0.06), M_WOOD, scene, g, loc=(0, 0, 0.03), bevel=0.006)
    if glow:
        inner = mesh_obj("inner", bm_plane(1.0, 2.22), flat("doorlight", (0, 0, 0), emit=(1.0, 0.62, 0.32), estr=2.5), scene, g, loc=(0, 0.04, 1.14), rot=(math.pi / 2, 0, 0))
        camera_only(inner)
        light(scene, "AREA", "spill", 120, (1.0, 0.75, 0.5), (0, 0.15, 1.15), rot=(-math.pi / 2, 0, 0), size=0.9, parent=g)
    hinge = empty("hinge", scene, loc=(-0.5, -0.05, 0), parent=g)
    mesh_obj("leaf", bm_box(1.0, 0.055, 2.18), leaf_mat, scene, hinge, loc=(0.5, 0, 1.13), bevel=0.008)
    for z, hh in ((1.55, 0.72), (0.6, 0.62)):
        mesh_obj("panel", bm_box(0.72, 0.016, hh), leaf_mat, scene, hinge, loc=(0.5, -0.033, z), bevel=0.006)
    mesh_obj("knob", bm_sphere(0.036), M_BRASS, scene, hinge, loc=(0.9, -0.075, 1.06), smooth_shade=True)
    hinge.rotation_euler = (0, 0, -0.62)
    return g


DOOR = (-4.0, 40.0)
door = make_door(P, (DOOR[0], DOOR[1], ground_z(*DOOR) - 0.25), 0.0, M_DOOR)
door.rotation_euler = (math.radians(-3), 0, 0.05)

# wind turbines on the far horizon (as in the reference photo)
for i, (x, y) in enumerate(((-150, 175), (-128, 205), (-104, 232), (-176, 150))):
    g = empty("turbine", P, loc=(x, y, ground_z(x, y) - 1), rz=0.9)
    mesh_obj("tower", bm_cyl(1.1, 0.6, 60, 16), M_WHITE, P, g, loc=(0, 0, 30))
    mesh_obj("nacelle", bm_box(2.0, 4.0, 2.0), M_WHITE, P, g, loc=(0, 0, 61))
    for k in range(3):
        bl = mesh_obj("blade", bm_box(0.9, 0.25, 26), M_WHITE, P, g, loc=(0, -2.2, 61))
        bl.rotation_euler = (0, TAU * k / 3 + i, 0)
        bl.location = (math.sin(TAU * k / 3 + i) * 13, -2.2, 61 + math.cos(TAU * k / 3 + i) * 13)

# gentle aerial haze
haze = mesh_obj("haze", bm_box(900, 900, 160), None, P, loc=(0, 100, 75))
hm = bpy.data.materials.new("haze")
hm.use_nodes = True
hnt = hm.node_tree
hnt.nodes.remove(hnt.nodes["Principled BSDF"])
hv = node(hnt, "ShaderNodeVolumePrincipled")
hv.inputs["Density"].default_value = 0.00025
hv.inputs["Color"].default_value = (0.86, 0.92, 1.0, 1)
hnt.links.new(hv.outputs[0], hnt.nodes["Material Output"].inputs["Volume"])
haze.data.materials.append(hm)


# ================================================================== ROOM (이찬혁의 방)
R.world = world_from_hdr("room_out", os.path.join(ASSETS, "h", "rustig_koppie_puresky_8k.hdr"), 1.0, sun_az_deg=125, min_elev=22)
RW, RD, RH, T = 6.4, 6.4, 3.0, 0.16
# keep the room's sun low enough to throw window patches across the floor
R.world["sun_dir"] = [math.cos(math.radians(28)) * math.cos(math.radians(125)), math.cos(math.radians(28)) * math.sin(math.radians(125)), math.sin(math.radians(28))]
WIN = dict(x=0.4, z=1.55, w=1.6, h=1.75)
M_WALL = pbr("wallpaper", "quatrefoil_jacquard_fabric", scale=1.6, tint=(1.0, 0.93, 0.78), hsv=(0.5, 0.22, 2.0), rough=1.0, nstr=0.35)
M_TRIMC = flat("trim_cream", (0.88, 0.84, 0.74), rough=0.4)
M_FLOOR = pbr("parquet", "herringbone_parquet", scale=0.55, rough=0.7, coat=0.3)
M_CURTAIN = pbr("curtain", "velour_velvet", scale=3, tint=(0.62, 0.26, 0.13), hsv=(0.5, 0.3, 1.0), sheen=0.8)
M_GLASS = flat("glass", (1, 1, 1), rough=0.0, trans=1.0, ior=1.5)


def boolean_cut(ob, cutter):
    md = ob.modifiers.new("cut", "BOOLEAN")
    md.operation = "DIFFERENCE"
    md.object = cutter
    md.solver = "EXACT"
    cutter.hide_render = True
    cutter.display_type = "WIRE"


walls = {"front": ((0, RD / 2 + T / 2, RH / 2), (RW + 2 * T, T, RH)), "back": ((0, -RD / 2 - T / 2, RH / 2), (RW + 2 * T, T, RH)),
         "left": ((-RW / 2 - T / 2, 0, RH / 2), (T, RD, RH)), "right": ((RW / 2 + T / 2, 0, RH / 2), (T, RD, RH))}
wobs = {k: mesh_obj("wall_" + k, bm_box(*s), M_WALL, R, loc=l) for k, (l, s) in walls.items()}
boolean_cut(wobs["front"], mesh_obj("cut", bm_box(WIN["w"], 1.0, WIN["h"]), None, R, loc=(WIN["x"], RD / 2 + T / 2, WIN["z"])))
mesh_obj("floor", bm_box(RW + 2 * T, RD + 2 * T, 0.1), M_FLOOR, R, loc=(0, 0, -0.05))
mesh_obj("ceiling", bm_box(RW + 2 * T, RD + 2 * T, 0.12), flat("ceil", (0.93, 0.9, 0.84), rough=0.9), R, loc=(0, 0, RH + 0.06))
for k, (l, s) in walls.items():
    horiz = s[0] > s[1]
    off = Vector(((0 if horiz else -math.copysign(T / 2 + 0.015, l[0])), (-math.copysign(T / 2 + 0.015, l[1]) if horiz else 0), 0))
    L = RW if horiz else RD
    for z, hgt, dep in ((0.07, 0.14, 0.03), (RH - 0.08, 0.16, 0.08)):
        mesh_obj("trim", bm_box(L if horiz else dep, dep if horiz else L, hgt), M_TRIMC, R, loc=(l[0] + off.x, l[1] + off.y, z), bevel=0.01)
# window
wx, wz, ww, wh = WIN["x"], WIN["z"], WIN["w"], WIN["h"]
fy = RD / 2 + T / 2
M_WFRAME = flat("wframe", (0.42, 0.26, 0.14), rough=0.5, coat=0.3)
for (x, z, sx, sz) in ((wx, wz + wh / 2 - 0.035, ww, 0.07), (wx, wz - wh / 2 + 0.035, ww, 0.07), (wx - ww / 2 + 0.035, wz, 0.07, wh), (wx + ww / 2 - 0.035, wz, 0.07, wh), (wx, wz, 0.05, wh), (wx, wz + 0.25, ww, 0.045)):
    mesh_obj("wf", bm_box(sx, 0.08, sz), M_WFRAME, R, loc=(x, fy, z), bevel=0.006)
mesh_obj("sill", bm_box(ww + 0.24, 0.28, 0.05), M_WFRAME, R, loc=(wx, RD / 2 - 0.02, wz - wh / 2 - 0.02), bevel=0.008)
g = mesh_obj("glass", bm_box(ww - 0.07, 0.006, wh - 0.07), M_GLASS, R, loc=(wx, fy, wz))
g.visible_shadow = False
for s in (-1, 1):
    cb = bm_plane(0.62, 2.55, 30, 10)
    for vv in cb.verts:
        vv.co.z += math.sin(vv.co.x * 32 + s) * 0.035 + 0.02 * math.sin(vv.co.y * 3)
    mesh_obj("curtain", cb, M_CURTAIN, R, loc=(wx + s * (ww / 2 + 0.3), RD / 2 - 0.09, 1.55), rot=(math.pi / 2, 0, 0), smooth_shade=True).modifiers.new("s", "SOLIDIFY").thickness = 0.01
mesh_obj("rod", bm_cyl(0.014, 0.014, ww + 1.4, 16), M_BRASS, R, loc=(wx, RD / 2 - 0.09, 2.86), rot=(0, math.pi / 2, 0))
por = light(R, "AREA", "portal", 0, (1, 1, 1), (wx, RD / 2 + T + 0.02, wz), rot=(-math.pi / 2, 0, 0))
por.data.shape = "RECTANGLE"
por.data.size, por.data.size_y = ww, wh
try:
    por.data.cycles.is_portal = True
except Exception:
    pass
SUN_R = light(R, "SUN", "sun", 4.5, (1.0, 0.87, 0.7), (0, 0, 30))
SUN_R.rotation_euler = Vector(R.world["sun_dir"]).to_track_quat("Z", "Y").to_euler()
SUN_R.data.angle = math.radians(0.6)
WINDOW_VIEW = mesh_obj("window_view", bm_plane(40, 22.5), None, R, loc=(-4, RD / 2 + 14, -2.5), rot=(math.pi / 2, 0, 0))
for prop in ("visible_diffuse", "visible_shadow", "visible_volume_scatter"):
    setattr(WINDOW_VIEW, prop, False)
vol = mesh_obj("roomhaze", bm_box(RW - 0.05, RD - 0.05, RH - 0.05), None, R, loc=(0, 0, RH / 2))
vm = bpy.data.materials.new("roomhaze")
vm.use_nodes = True
vnt = vm.node_tree
vnt.nodes.remove(vnt.nodes["Principled BSDF"])
pv = node(vnt, "ShaderNodeVolumePrincipled")
pv.inputs["Density"].default_value = 0.006
pv.inputs["Anisotropy"].default_value = 0.45
vnt.links.new(pv.outputs[0], vnt.nodes["Material Output"].inputs["Volume"])
vol.data.materials.append(vm)

# re-skin the library furniture to match the references
recolor("Sofa_01", lambda n: True, tint=(0.33, 0.36, 0.12, 0.85))          # olive velvet
for o in LIBM["Sofa_01"]["objs"]:
    for ms in getattr(o, "material_slots", []):
        if ms.material and "Principled BSDF" in ms.material.node_tree.nodes:
            setin(ms.material.node_tree.nodes["Principled BSDF"], "Sheen Weight", 0.9)
recolor("GothicBed_01", lambda n: True, tint=(0.88, 0.83, 0.72, 0.8))     # cream painted bed
recolor("ClassicNightstand_01", lambda n: True, tint=(0.88, 0.83, 0.72, 0.8))
recolor("ArmChair_01", lambda n: "fabric" in n or "cloth" in n or "seat" in n, tint=(0.86, 0.74, 0.62, 0.5))

# layout (front wall = window, +Y)
spawn("wooden_table_02", R, loc=(WIN["x"], RD / 2 - 0.45, 0))
desk_top = LIBM["wooden_table_02"]["mx"].z - LIBM["wooden_table_02"]["mn"].z
spawn("vintage_oil_lamp", R, loc=(WIN["x"] - 0.4, RD / 2 - 0.38, desk_top), rz=0.3)
light(R, "POINT", "oil_lamp", 14, (1.0, 0.68, 0.38), (WIN["x"] - 0.4, RD / 2 - 0.38, desk_top + 0.42), size=0.04)
spawn("chess_set", R, loc=(WIN["x"] + 0.28, RD / 2 - 0.55, desk_top), rz=0.25)
spawn("book_encyclopedia_set_01", R, loc=(WIN["x"] - 0.05, RD / 2 - 0.3, desk_top), rz=0.0)
spawn("Ukulele_01", R, loc=(-1.35, RD / 2 - 0.14, 0), rz=0.15)
spawn("potted_plant_02", R, loc=(1.6, RD / 2 - 0.35, 0), rz=0.4)
spawn("throw_pillows_01", R, loc=(-RW / 2 + 0.55, 0.1, 0.42), rz=math.pi / 2)
spawn("painted_wooden_chair_01", R, loc=(WIN["x"] + 0.05, RD / 2 - 1.05, 0), rz=math.pi + 0.15)
spawn("Sofa_01", R, loc=(-RW / 2 + 0.48, 0.1, 0), rz=math.pi / 2)
spawn("ArmChair_01", R, loc=(-0.75, -1.15, 0), rz=-math.pi / 2 - 0.45)
spawn("painted_wooden_cabinet", R, loc=(RW / 2 - 0.32, 1.25, 0), rz=-math.pi / 2)
spawn("GothicBed_01", R, loc=(RW / 2 - 1.05, -RD / 2 + 1.15, 0), rz=math.pi)
_, ns_top = spawn("ClassicNightstand_01", R, loc=(0.75, -RD / 2 + 0.3, 0), rz=math.pi)
spawn("brass_candleholders", R, loc=(0.7, -RD / 2 + 0.3, ns_top), rz=0.0, s=0.45)
spawn("standing_picture_frame_01", R, loc=(0.95, -RD / 2 + 0.36, ns_top), rz=math.pi - 0.3, s=0.8)
spawn("vintage_grandfather_clock_01", R, loc=(-RW / 2 + 0.3, -RD / 2 + 0.35, 0), rz=3 * math.pi / 4)
spawn("Chandelier_02", R, loc=(0, 0, RH - (LIBM["Chandelier_02"]["mx"].z - LIBM["Chandelier_02"]["mn"].z)))
for i, (x, y) in enumerate(((-0.35, 0.28), (0.35, 0.28), (0, -0.4))):
    light(R, "POINT", "chand%d" % i, 4, (1.0, 0.75, 0.45), (x, y, RH - 0.75), size=0.03)
spawn("fancy_picture_frame_01", R, loc=(-RW / 2 + 0.03, -0.35, 1.25), rz=math.pi / 2, s=0.85)
spawn("fancy_picture_frame_02", R, loc=(-RW / 2 + 0.03, 0.75, 1.45), rz=math.pi / 2, s=0.65)
spawn("fancy_picture_frame_02", R, loc=(RW / 2 - 0.03, 1.25, 1.6), rz=-math.pi / 2, s=0.75)

# green fringed floor lamp next to the sofa (reference: green shade with a bead fringe)
fl = empty("floorlamp", R, loc=(-RW / 2 + 0.4, 1.6, 0))
mesh_obj("lbase", bm_cyl(0.16, 0.18, 0.03, 32), M_BRASS, R, fl, loc=(0, 0, 0.015))
mesh_obj("lpole", bm_cyl(0.012, 0.012, 1.45, 12), M_BRASS, R, fl, loc=(0, 0, 0.75))
M_SHADE = flat("shade", (0.16, 0.32, 0.18), rough=0.7, sheen=0.6, trans=0.25)
mesh_obj("lshade", bm_cyl(0.3, 0.13, 0.26, 40), M_SHADE, R, fl, loc=(0, 0, 1.55)).modifiers.new("s", "SOLIDIFY").thickness = 0.006
for k in range(60):
    a = TAU * k / 60
    mesh_obj("fringe", bm_cyl(0.005, 0.005, 0.1, 4), M_SHADE, R, fl, loc=(math.cos(a) * 0.3, math.sin(a) * 0.3, 1.37))
light(R, "POINT", "floorlamp_l", 60, (1.0, 0.72, 0.42), (0, 0, 1.5), size=0.05, parent=fl)

# striped kilim rug (reference: cream with black stripes)
H_, W_ = 1024, 1536
yy, xx = np.mgrid[0:H_, 0:W_]
rug = np.ones((H_, W_, 3)) * np.array([0.88, 0.85, 0.78])
band = np.sin(xx / W_ * 70 * (1 + 0.6 * (xx / W_) ** 2)) > 0.86 - 0.5 * np.abs(xx / W_ - 0.5)
rug[band] = (0.1, 0.09, 0.08)
rug += np.random.default_rng(2).normal(0, 0.02, rug.shape)
mr = image_mat("rug", save_png("kilim", np.clip(rug, 0, 1)), rough=0.95, sheen=0.7)
mesh_obj("rug", bm_plane(2.6, 1.8, 1, 1), mr, R, loc=(-0.9, 0.0, 0.008), rot=(0, 0, math.pi / 2 + 0.03))

# gramophone cabinet with the 개화 record
gram = empty("gramophone", R, loc=(-RW / 2 + 0.45, RD / 2 - 0.55, 0), rz=0.7)
M_WALNUT = pbr("walnut", "wood_planks", scale=2.5, tint=(0.45, 0.28, 0.18), coat=0.9, rough=0.5)
mesh_obj("cab", bm_box(0.55, 0.48, 0.92), M_WALNUT, R, gram, loc=(0, 0, 0.46), bevel=0.02)
for z in (0.28, 0.6):
    mesh_obj("drawer", bm_box(0.46, 0.02, 0.22), M_WALNUT, R, gram, loc=(0, -0.245, z), bevel=0.008)
    mesh_obj("pull", bm_sphere(0.018), M_BRASS, R, gram, loc=(0, -0.265, z), smooth_shade=True)
for sx in (-1, 1):
    for sy in (-1, 1):
        mesh_obj("foot", bm_cyl(0.03, 0.02, 0.06, 12), M_WALNUT, R, gram, loc=(sx * 0.24, sy * 0.2, 0.03))
mesh_obj("platter", bm_cyl(0.16, 0.16, 0.02, 64), flat("felt", (0.35, 0.05, 0.06), rough=0.9), R, gram, loc=(0.03, 0.02, 0.935))
mv, mvt, mvb = new_mat("vinyl")
setin(mvb, "Base Color", (0.01, 0.01, 0.01, 1))
setin(mvb, "Roughness", 0.25)
setin(mvb, "Coat Weight", 0.7)
wvv = node(mvt, "ShaderNodeTexWave")
wvv.wave_type = "RINGS"
wvv.inputs["Scale"].default_value = 160
mvt.links.new(node(mvt, "ShaderNodeTexCoord").outputs["Object"], wvv.inputs["Vector"])
bpv = node(mvt, "ShaderNodeBump")
bpv.inputs["Strength"].default_value = 0.12
mvt.links.new(wvv.outputs["Fac"], bpv.inputs["Height"])
mvt.links.new(bpv.outputs["Normal"], mvb.inputs["Normal"])
mesh_obj("record", bm_cyl(0.15, 0.15, 0.004, 96), mv, R, gram, loc=(0.03, 0.02, 0.948))
mesh_obj("label", bm_cyl(0.05, 0.05, 0.001, 64), image_mat("label", COVER, rough=0.6), R, gram, loc=(0.03, 0.02, 0.9505))
mesh_obj("armbase", bm_cyl(0.025, 0.03, 0.04, 24), M_BRASS, R, gram, loc=(0.2, 0.17, 0.95))
arm = mesh_obj("tonearm", bm_cyl(0.006, 0.006, 0.24, 12), M_BRASS, R, gram, loc=(0.15, 0.06, 0.975), rot=(math.pi / 2, 0, 0.45))
# brass horn: revolved bell with a scalloped rim, tilted up and forward
horn_prof = [(0.03 + 0.24 * t ** 3.0, 0.48 * t) for t in np.linspace(0, 1, 30)]
horn = mesh_obj("horn", bm_lathe(horn_prof, 72, lambda a, z: 0.035 * math.sin(a * 8) * (z / 0.48) ** 6), M_BRASS, R, gram, loc=(0.18, 0.14, 1.0), rot=(math.radians(55), 0, math.radians(15)), smooth_shade=True)
horn.modifiers.new("s", "SOLIDIFY").thickness = 0.004
mesh_obj("neck", bm_cyl(0.025, 0.03, 0.18, 24), M_BRASS, R, gram, loc=(0.19, 0.15, 0.99), rot=(math.radians(20), 0, 0))
for i in range(3):
    sl = mesh_obj("sleeve", bm_box(0.31, 0.31, 0.006), image_mat("cover%d" % i, COVER, rough=0.7) if i == 0 else flat("sleeve%d" % i, ((0.86, 0.66, 0.24), (0.42, 0.48, 0.66), (0.7, 0.3, 0.2))[i], rough=0.6), R, gram,
                  loc=(-0.05 + i * 0.012, -0.36 - i * 0.02, 0.17), rot=(math.radians(78 - i * 4), 0, 0))
# Edison wall sconce by the bed (reference: bare bulb on a wooden block with a pull chain)
sc = empty("sconce", R, loc=(0.75, -RD / 2 + 0.02, 1.45), rz=math.pi)
mesh_obj("block", bm_box(0.22, 0.06, 0.14), M_WALNUT, R, sc, loc=(0, -0.03, 0), bevel=0.01)
mesh_obj("bulb", bm_sphere(0.06), flat("bulb", (1, 0.9, 0.7), emit=(1.0, 0.62, 0.3), estr=40), R, sc, loc=(0, -0.13, 0), smooth_shade=True)
light(R, "POINT", "sconce_l", 45, (1.0, 0.62, 0.3), (0, -0.14, 0), size=0.03, parent=sc)


# ================================================================== cameras + render
def cam(scene, name, loc, target, lens=28, dof=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start, cd.clip_end = 0.03, 5000
    if dof:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = dof[1]
        cd.dof.focus_distance = dof[0]
    ob = bpy.data.objects.new(name, cd)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return link(ob, scene)


gz = ground_z
dz = ground_z(*DOOR)
FRAMES = {
    "F1_paradise": (P, "day", cam(P, "F1", (9, -15, gz(9, -15) + 1.7), (-8, 30, 6.0), 24)),
    "F2_door": (P, "golden", cam(P, "F2", (-1.6, 33.6, gz(-1.6, 33.6) + 1.45), (-4.0, 40.0, dz + 2.1), 32, dof=(6.8, 5.6))),
    "F3_stage": (P, "day", cam(P, "F3", (3.2, 4.0, gz(3.2, 4) + 1.45), (7.5, 17, 2.6), 30, dof=(13, 8))),
    "F4_room": (R, "room", cam(R, "F4", (2.75, -0.55, 1.6), (-1.8, 2.0, 1.05), 17)),
    "F5_gramophone": (R, "room", cam(R, "F5", (-0.9, 1.6, 1.35), (-2.75, 2.6, 1.1), 38, dof=(1.95, 4.0))),
    "F6_bed": (R, "room", cam(R, "F6", (2.6, -0.45, 1.35), (1.0, -2.8, 0.85), 28, dof=(2.6, 4.0))),
}


def setup(scene, samples):
    scene.render.engine = "CYCLES"
    c = scene.cycles
    c.device = "GPU"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.015
    c.use_denoising = True
    c.sample_clamp_indirect = 6
    c.volume_bounces = 1
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces, c.transmission_bounces, c.transparent_max_bounces = 8, 3, 3, 6, 8
    for a, v in (("denoiser", "OPENIMAGEDENOISE"), ("denoising_use_gpu", True)):
        try:
            setattr(c, a, v)
        except Exception:
            pass
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Base Contrast"
    except Exception:
        pass
    scene.render.resolution_x = int(ARGS.get("--w", 1920))
    scene.render.resolution_y = int(ARGS.get("--h", 1080))
    s = scene.render.image_settings
    s.file_format = "JPEG"
    s.quality = 92


prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "OPTIX"
samples = int(ARGS.get("--samples", 256))
setup(P, samples)
setup(R, int(samples * 1.5))
P.view_settings.exposure = 0.0
try:
    P.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
R.view_settings.exposure = 0.85

if ARGS.get("--save"):
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "pitch.blend"))
want = ARGS.get("--frames")


def box_blur(a, r):
    for ax in (0, 1):
        c = np.cumsum(np.pad(a, [(r + 1, r) if i == ax else (0, 0) for i in range(a.ndim)], mode="edge"), axis=ax)
        a = (np.take(c, range(2 * r + 1, c.shape[ax]), axis=ax) - np.take(c, range(0, c.shape[ax] - 2 * r - 1), axis=ax)) / (2 * r + 1)
    return a


def film_post(path):
    """Halation, slight lens fringing, lifted blacks, vignette and grain on the display-referred JPEG."""
    im = bpy.data.images.load(path)
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    a = px.reshape(h, w, 4)[..., :3].astype(np.float32)
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    k = 8
    hw, hh = w // k, h // k
    hi = (np.clip((lum - 0.85) / 0.15, 0, 1)[..., None] * a)[: hh * k, : hw * k].reshape(hh, k, hw, k, 3).mean((1, 3))
    for _ in range(3):
        hi = box_blur(hi, max(2, hw // 90))
    small = bpy.data.images.new("glow", hw, hh, float_buffer=True)
    small.pixels.foreach_set(np.dstack([hi, np.ones((hh, hw, 1), np.float32)]).ravel())
    small.scale(w, h)
    g = np.empty(w * h * 4, np.float32)
    small.pixels.foreach_get(g)
    a += g.reshape(h, w, 4)[..., :3] * np.array([0.35, 0.22, 0.14], np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    for ch, f in ((0, 1.0009), (2, 0.9991)):
        sx = np.clip(np.rint(cx + (xx - cx) / f), 0, w - 1).astype(int)
        sy = np.clip(np.rint(cy + (yy - cy) / f), 0, h - 1).astype(int)
        a[..., ch] = a[sy, sx, ch]
    r2 = ((xx - cx) / cx) ** 2 * 0.62 + ((yy - cy) / cy) ** 2 * 0.38
    a = 0.012 + a * 0.98
    a *= (1 - 0.2 * r2 ** 1.4)[..., None]
    grain = np.random.default_rng(5).normal(0, 1, (h, w, 1)).astype(np.float32)
    a += grain * (0.007 + 0.008 * (1 - np.clip(lum, 0, 1)))[..., None]
    out = bpy.data.images.new("post", w, h)
    out.pixels.foreach_set(np.dstack([np.clip(a, 0, 1), np.ones((h, w, 1), np.float32)]).ravel())
    out.filepath_raw = path
    out.file_format = "JPEG"
    out.save(quality=92)
    for x in (im, small, out):
        bpy.data.images.remove(x)


def render_window_plate():
    """Linear EXR of the dunes from the paradise scene, shown through the room window at true brightness."""
    path = os.path.join(WORK, "renders", "_window_plate.exr")
    if not os.path.exists(path):
        P.world = W_DAY
        SUN_P.rotation_euler = Vector(W_DAY["sun_dir"]).to_track_quat("Z", "Y").to_euler()
        P.camera = cam(P, "PLATE", (-18, 22, gz(-18, 22) + 5), (-12, 62, 20), 24)
        r, st = P.render, P.render.image_settings
        keep = (r.resolution_x, r.resolution_y, P.cycles.samples, st.file_format)
        r.resolution_x, r.resolution_y, P.cycles.samples = 1600, 900, 96
        st.file_format = "OPEN_EXR"
        r.filepath = path
        P.view_layers[0].update()
        bpy.ops.render.render(write_still=True, scene=P.name)
        r.resolution_x, r.resolution_y, P.cycles.samples, st.file_format = keep
    m, nt, b = new_mat("window_view")
    setin(b, "Base Color", (0, 0, 0, 1))
    tx = node(nt, "ShaderNodeTexImage")
    tx.image = bpy.data.images.load(path)
    tx.extension = "EXTEND"
    nt.links.new(tx.outputs["Color"], b.inputs["Emission Color"])
    setin(b, "Emission Strength", 1.0)
    WINDOW_VIEW.data.materials.append(m)
    print("WINDOW PLATE", path)


if not want or any(f.split("_")[0] in want.split(",") for f in FRAMES if FRAMES[f][0] == R):
    render_window_plate()


def door_view(path):
    """Shows the rendered room inside the desert door frame (cropped to the opening's aspect)."""
    m, nt, b = new_mat("doorview")
    setin(b, "Base Color", (0, 0, 0, 1))
    tx = node(nt, "ShaderNodeTexImage")
    tx.image = bpy.data.images.load(path)
    tx.extension = "EXTEND"
    mp = node(nt, "ShaderNodeMapping")
    a = (1.0 / 2.22) / (16 / 9)
    mp.inputs["Location"].default_value = (0.66 - a / 2, 0, 0)
    mp.inputs["Scale"].default_value = (a, 1, 1)
    nt.links.new(node(nt, "ShaderNodeTexCoord").outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tx.inputs["Vector"])
    nt.links.new(tx.outputs["Color"], b.inputs["Emission Color"])
    setin(b, "Emission Strength", 3.0)
    for o in door.children_recursive:
        if o.name.startswith("inner"):
            o.data.materials.clear()
            o.data.materials.append(m)


order = sorted(FRAMES, key=lambda n: FRAMES[n][0] != R)
for name in order:
    scene, mode, camob = FRAMES[name]
    if want and name.split("_")[0] not in want.split(","):
        continue
    room_img = os.path.join(OUTDIR, "F4_room.jpg")
    if name == "F2_door" and os.path.exists(room_img):
        door_view(room_img)
    if scene == P:
        w = W_GOLD if mode == "golden" else W_DAY
        P.world = w
        SUN_P.rotation_euler = Vector(w["sun_dir"]).to_track_quat("Z", "Y").to_euler()
        SUN_P.data.energy = 3.0 if mode == "golden" else 3.6
        SUN_P.data.color = (1.0, 0.78, 0.55) if mode == "golden" else (1.0, 0.95, 0.86)
        P.view_settings.exposure = 0.4 if mode == "golden" else 0.0
    scene.camera = camob
    scene.view_layers[0].update()
    scene.render.filepath = os.path.join(OUTDIR, name + ".jpg")
    bpy.ops.render.render(write_still=True, scene=scene.name)
    if ARGS.get("--post", "1") == "1":
        film_post(scene.render.filepath)
    print("WROTE", scene.render.filepath)
print("FRAMES DONE")
