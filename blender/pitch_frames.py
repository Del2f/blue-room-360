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


for mid in ["grass_medium_01", "grass_medium_02", "tree_small_02", "island_tree_01", "Sofa_01", "ArmChair_01", "Chandelier_02",
            "GothicBed_01", "ClassicNightstand_01", "painted_wooden_cabinet", "fancy_picture_frame_01", "fancy_picture_frame_02",
            "vintage_grandfather_clock_01", "vintage_oil_lamp", "wooden_table_02", "painted_wooden_chair_01"]:
    import_model(mid)

# yellow bloom like the shrubs in the MV
for mid in ("tree_small_02", "island_tree_01"):
    recolor(mid, lambda n: "leaf" in n or "leaves" in n or "foliage" in n, hsv=(0.38, 1.6, 1.25))

# ---------------------------------------------------------------- shared materials
M_LINEN = pbr("canvas", "rough_linen", scale=2.0, tint=(0.97, 0.95, 0.9), sheen=0.4)
M_WOOD = pbr("weathered", "weathered_planks", scale=1.2)
M_DOOR = pbr("door_blue", "blue_painted_planks", scale=1.0)
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
W_DAY = world_from_hdr("day", os.path.join(ASSETS, "h", "kloofendal_48d_partly_cloudy_puresky_4k.hdr"), 0.9, sun_az_deg=-125)
W_GOLD = world_from_hdr("golden", os.path.join(ASSETS, "h", "kloofendal_48d_partly_cloudy_puresky_4k.hdr"), 0.85, sun_az_deg=160, tint=(1.0, 0.85, 0.68))
# late-afternoon sun: keep the azimuth, force a low elevation (the sky disc itself stays out of frame)
W_GOLD["sun_dir"] = [math.cos(math.radians(14)) * math.cos(math.radians(160)), math.cos(math.radians(14)) * math.sin(math.radians(160)), math.sin(math.radians(14))]
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
MEADOW = smooth(0.9 - DUNE, 0.0, 0.6) * (1 - smooth(LAKE, 0.02, 0.15)) * (1 - smooth(Y, 34, 46)) * (1 - smooth(dist, 75, 115))
MEADOW = np.clip(MEADOW * (0.55 + 0.6 * patch), 0, 1)
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

# ground shader: pale Bàu Trắng sand with wind ripples, grassy ground where "meadow" is set
m_g, nt, b = new_mat("ground")
tc = node(nt, "ShaderNodeTexCoord")
mp = node(nt, "ShaderNodeMapping")
mp.inputs["Scale"].default_value = (0.5, 0.5, 0.5)
nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])


def tex3(folder):
    ts = []
    for f, nc in (("diff.jpg", False), ("arm.jpg", True), ("nor.jpg", True)):
        t = node(nt, "ShaderNodeTexImage")
        t.image = load_img(os.path.join(ASSETS, "t", folder, f), nc)
        nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
        ts.append(t)
    return ts


sd, sa, sn = tex3("sand_01")
gd, ga, gn = tex3("sparse_grass")
hs = node(nt, "ShaderNodeHueSaturation")
hs.inputs["Saturation"].default_value = 0.35
hs.inputs["Value"].default_value = 1.75
nt.links.new(sd.outputs["Color"], hs.inputs["Color"])
_, A_, B_, sand_col = mix_rgb(nt, "MULTIPLY")
nt.links.new(hs.outputs["Color"], A_)
B_.default_value = (1.0, 0.94, 0.84, 1)
attrn = node(nt, "ShaderNodeAttribute")
attrn.attribute_type = "GEOMETRY"
attrn.attribute_name = "meadow"
mixc, A2, B2, col = mix_rgb(nt, "MIX")
nt.links.new(attrn.outputs["Fac"], mixc.inputs[0])
nt.links.new(sand_col, A2)
gh = node(nt, "ShaderNodeHueSaturation")
gh.inputs["Hue"].default_value = 0.56
gh.inputs["Saturation"].default_value = 1.6
nt.links.new(gd.outputs["Color"], gh.inputs["Color"])
nt.links.new(gh.outputs["Color"], B2)
nt.links.new(col, b.inputs["Base Color"])
setin(b, "Roughness", 0.92)
nms = node(nt, "ShaderNodeNormalMap")
nt.links.new(sn.outputs["Color"], nms.inputs["Color"])
rip_map = node(nt, "ShaderNodeMapping")
rip_map.inputs["Rotation"].default_value = (0, 0, 0.6)
nt.links.new(tc.outputs["Object"], rip_map.inputs["Vector"])
wv = node(nt, "ShaderNodeTexWave")
wv.bands_direction = "X"
wv.inputs["Scale"].default_value = 1.8
wv.inputs["Distortion"].default_value = 2
wv.inputs["Detail"].default_value = 2
nt.links.new(rip_map.outputs["Vector"], wv.inputs["Vector"])
bmp = node(nt, "ShaderNodeBump")
bmp.inputs["Strength"].default_value = 0.07
nt.links.new(wv.outputs["Fac"], bmp.inputs["Height"])
nt.links.new(nms.outputs["Normal"], bmp.inputs["Normal"])
nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
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

# grass: Geometry Nodes scatter of the Poly Haven tufts where "meadow" is high
grass_col = bpy.data.collections.new("GRASS")
for mid in ("grass_medium_01", "grass_medium_02"):
    for o in LIBM[mid]["objs"]:
        if o.type == "MESH":
            grass_col.objects.link(o)
ng = bpy.data.node_groups.new("scatter_grass", "GeometryNodeTree")
ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
gi, go = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
dist_n = ng.nodes.new("GeometryNodeDistributePointsOnFaces")
dist_n.inputs["Density"].default_value = 12.0
na = ng.nodes.new("GeometryNodeInputNamedAttribute")
na.data_type = "FLOAT"
na.inputs["Name"].default_value = "meadow"
rnd_sel = ng.nodes.new("FunctionNodeRandomValue")
rnd_sel.data_type = "FLOAT"
cmp = ng.nodes.new("FunctionNodeCompare")
cmp.data_type = "FLOAT"
cmp.operation = "LESS_THAN"
ng.links.new(rnd_sel.outputs[0], cmp.inputs[0])
ng.links.new(na.outputs["Attribute"], cmp.inputs[1])
ci = ng.nodes.new("GeometryNodeCollectionInfo")
ci.inputs["Collection"].default_value = grass_col
ci.inputs["Separate Children"].default_value = True
ci.inputs["Reset Children"].default_value = True
iop = ng.nodes.new("GeometryNodeInstanceOnPoints")
iop.inputs["Pick Instance"].default_value = True
rv = ng.nodes.new("FunctionNodeRandomValue")
rv.data_type = "FLOAT_VECTOR"
[s for s in rv.inputs if s.name == "Max" and s.type == "VECTOR"][0].default_value = (0.15, 0.15, TAU)
[s for s in rv.inputs if s.name == "Min" and s.type == "VECTOR"][0].default_value = (-0.15, -0.15, 0)
rs = ng.nodes.new("FunctionNodeRandomValue")
rs.data_type = "FLOAT"
[s for s in rs.inputs if s.name == "Min" and s.type == "VALUE"][0].default_value = 0.55
[s for s in rs.inputs if s.name == "Max" and s.type == "VALUE"][0].default_value = 1.3
join = ng.nodes.new("GeometryNodeJoinGeometry")
ng.links.new(gi.outputs[0], dist_n.inputs["Mesh"])
ng.links.new(cmp.outputs["Result"], dist_n.inputs["Selection"])
ng.links.new(dist_n.outputs["Points"], iop.inputs["Points"])
ng.links.new(ci.outputs[0], iop.inputs["Instance"])
ng.links.new([s for s in rv.outputs if s.type == "VECTOR"][0], iop.inputs["Rotation"])
ng.links.new([s for s in rs.outputs if s.type == "VALUE"][0], iop.inputs["Scale"])
ng.links.new(gi.outputs[0], join.inputs[0])
ng.links.new(iop.outputs[0], join.inputs[0])
ng.links.new(join.outputs[0], go.inputs[0])
ground.modifiers.new("grass", "NODES").node_group = ng

# yellow-blooming shrubs along the dune foot and around the camp
rng = np.random.default_rng(3)
for i in range(46):
    x = rng.uniform(-60, 55)
    y = rng.uniform(27, 40) if i < 34 else rng.uniform(4, 26)
    if i >= 34 and (abs(x - 8) < 13 and 6 < y < 24):
        continue
    z = float(terrain(np.array(x), np.array(y))[0])
    if float(terrain(np.array(x), np.array(y))[2]) > 0.05:
        continue
    spawn("tree_small_02" if i % 3 else "island_tree_01", P, loc=(x, y, z - 0.1), rz=rng.uniform(0, TAU), s=(0.42 if i % 3 else 0.28) * rng.uniform(0.75, 1.25))

# --- festival camp ---------------------------------------------------------------
def ground_z(x, y):
    return float(terrain(np.array(x), np.array(y))[0])


# painted sun-arch stage (like the MV)
def painted_panel():
    H_, W_ = 512, 1024
    yy, xx = np.mgrid[0:H_, 0:W_]
    img = np.zeros((H_, W_, 3))
    img[:] = (0.12, 0.42, 0.45)
    cx, cy = W_ / 2, H_ * 0.95
    r = np.hypot(xx - cx, yy - cy)
    ang = np.arctan2(cy - yy, xx - cx)
    rays = (np.sin(ang * 22) > 0.2) & (r < H_ * 0.85) & (r > H_ * 0.42)
    img[rays] = (0.95, 0.72, 0.18)
    img[r < H_ * 0.4] = (0.97, 0.82, 0.25)
    img[(r < H_ * 0.4) & (r > H_ * 0.36)] = (0.85, 0.3, 0.16)
    img[(r > H_ * 0.88) & (r < H_ * 0.93)] = (0.85, 0.3, 0.16)
    noise = np.random.default_rng(1).normal(0, 0.03, img.shape)
    return save_png("sun_panel", np.clip(img + noise, 0, 1))


def leaf_panel():
    H_, W_ = 1024, 256
    yy, xx = np.mgrid[0:H_, 0:W_]
    img = np.zeros((H_, W_, 3))
    img[:] = (0.18, 0.5, 0.32)
    dots = ((xx % 64 - 32) ** 2 + (yy % 80 - 40) ** 2) < 110
    img[dots] = (0.95, 0.88, 0.7)
    img[(xx < 14) | (xx > W_ - 14)] = (0.82, 0.25, 0.16)
    return save_png("leaf_panel", img)


stage = empty("stage", P, loc=(7, 17, ground_z(7, 17) - 0.05), rz=0.12)
mesh_obj("deck", bm_box(6.0, 3.2, 0.5), M_WOOD, P, stage, loc=(0, 0, 0.25), bevel=0.02)
m_sun = image_mat("sun_panel", painted_panel(), rough=0.7)
m_leaf = image_mat("leaf_panel", leaf_panel(), rough=0.7)
M_TRIM_RED = flat("trim_red", (0.75, 0.22, 0.14), rough=0.55)
for sx in (-1, 1):
    mesh_obj("pillar", bm_box(0.7, 0.3, 3.6), m_leaf, P, stage, loc=(sx * 2.45, 0.9, 2.3), bevel=0.02)
arch = mesh_obj("arch", bm_torus(2.45, 0.16, 48, 12, math.pi), M_TRIM_RED, P, stage, loc=(0, 0.9, 4.1), rot=(math.pi / 2, 0, 0), smooth_shade=True)
bm = bmesh.new()
cverts = [bm.verts.new((0, 0, 0))] + [bm.verts.new((2.3 * math.cos(math.pi * i / 48), 2.3 * math.sin(math.pi * i / 48), 0)) for i in range(49)]
uvl = bm.loops.layers.uv.new()
for i in range(48):
    f = bm.faces.new((cverts[0], cverts[i + 1], cverts[i + 2]))
    for lp in f.loops:
        lp[uvl].uv = (0.5 + lp.vert.co.x / 4.6, lp.vert.co.y / 2.3 * 0.95)
mesh_obj("sun", bm, m_sun, P, stage, loc=(0, 1.0, 4.1), rot=(math.pi / 2, 0, 0))
mesh_obj("back_cloth", bm_plane(4.6, 3.4, 20, 6), M_LINEN, P, stage, loc=(0, 1.05, 2.35), rot=(math.pi / 2, 0, 0))
for i, c in enumerate(((0.12, 0.6, 0.7), (0.95, 0.75, 0.2), (0.8, 0.25, 0.18), (0.25, 0.55, 0.3))):
    x = -2.2 + i * 1.45
    mesh_obj("fpole", bm_cyl(0.03, 0.03, 3.2, 10), M_WOOD, P, stage, loc=(x, -1.4, 1.6))
    fb = bm_plane(0.9, 0.55, 12, 4)
    for vv in fb.verts:
        vv.co.z += math.sin((vv.co.x + 0.45) * 7) * 0.05 * (vv.co.x + 0.45)
    mesh_obj("flag", fb, flat("flag%d" % i, c, rough=0.8, sheen=0.4), P, stage, loc=(x + 0.46, -1.4, 2.9), rot=(math.pi / 2, 0, 0.2), smooth_shade=True).modifiers.new("s", "SOLIDIFY").thickness = 0.004


def dome_tent(name, loc, r=1.3, h=1.25, rz=0.0):
    g = empty(name, P, loc=(loc[0], loc[1], ground_z(*loc) - 0.05), rz=rz)
    bm = bm_sphere(r, 48, 24)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.001], context="VERTS")
    bmesh.ops.scale(bm, vec=(1, 1, h / r), verts=bm.verts)
    for v in bm.verts:
        a = math.atan2(v.co.y, v.co.x)
        v.co.x *= 1 - 0.03 * (math.cos(a * 8) ** 2) * (1 - v.co.z / h)
        v.co.y *= 1 - 0.03 * (math.cos(a * 8) ** 2) * (1 - v.co.z / h)
    t = mesh_obj("dome", bm, M_LINEN, P, g, smooth_shade=True)
    t.modifiers.new("s", "SOLIDIFY").thickness = 0.01
    mesh_obj("door", bm_box(0.7, 0.05, 0.95), flat("tentdoor", (0.18, 0.14, 0.1), rough=0.9), P, g, loc=(0, -r + 0.06, 0.48))
    return g


def bell_tent(name, loc, r=2.2, wall=0.7, h=2.8, rz=0.0):
    g = empty(name, P, loc=(loc[0], loc[1], ground_z(*loc) - 0.05), rz=rz)
    prof = [(r, 0.0), (r, wall), (r * 0.97, wall + 0.08)] + [(r * (1 - t) ** 1.15 + 0.05, wall + 0.08 + (h - wall - 0.08) * t) for t in np.linspace(0.05, 1, 12)]
    t = mesh_obj("bell", bm_lathe(prof, 64, lambda a, z: 0.012 * math.sin(a * 12) * (z < 0.8)), M_LINEN, P, g, smooth_shade=True)
    t.modifiers.new("s", "SOLIDIFY").thickness = 0.01
    mesh_obj("pole", bm_cyl(0.04, 0.04, h + 0.4, 10), M_WOOD, P, g, loc=(0, 0, (h + 0.4) / 2))
    mesh_obj("bdoor", bm_box(0.9, 0.05, 1.3), flat("belldoor", (0.2, 0.15, 0.1), rough=0.9), P, g, loc=(0, -r + 0.02, 0.62))
    return g


def teepee(name, loc, r=1.7, h=4.0, rz=0.0):
    g = empty(name, P, loc=(loc[0], loc[1], ground_z(*loc) - 0.05), rz=rz)
    prof = [(r * (1 - t) + 0.02, h * 0.85 * t) for t in np.linspace(0, 1, 10)]
    t = mesh_obj("cone", bm_lathe(prof, 48, lambda a, z: 0.02 * math.sin(a * 9)), M_LINEN, P, g, smooth_shade=True)
    t.modifiers.new("s", "SOLIDIFY").thickness = 0.01
    for i in range(9):
        a = TAU * i / 9
        p0 = Vector((math.cos(a) * r * 1.02, math.sin(a) * r * 1.02, 0))
        p1 = Vector((-math.cos(a) * 0.35, -math.sin(a) * 0.35, h))
        seg = p1 - p0
        c = mesh_obj("tpole", bm_cyl(0.03, 0.025, seg.length, 8), M_WOOD, P, g, loc=(p0 + p1) / 2)
        c.rotation_euler = seg.to_track_quat("Z", "Y").to_euler()
    mesh_obj("band", bm_cyl(r * 0.58, r * 0.53, 0.25, 48), flat("band", (0.75, 0.25, 0.16), rough=0.8), P, g, loc=(0, 0, h * 0.85 * 0.43))
    return g


dome_tent("tent1", (15.5, 10.5), rz=0.5)
dome_tent("tent2", (18.5, 15.0), r=1.1, h=1.05, rz=0.3)
dome_tent("tent3", (-4.5, 18.5), r=1.0, h=0.95, rz=-0.4)
bell_tent("bell", (-1.0, 11.5), rz=-0.2)
teepee("teepee", (13.0, 22.5))
# bunting across the camp
flag_cols = [(0.12, 0.6, 0.7), (0.95, 0.75, 0.2), (0.8, 0.25, 0.18), (0.95, 0.92, 0.85), (0.25, 0.55, 0.3)]
for (ax, ay, bx, by) in ((-1.0, 11.5, 7.0, 15.4), (9.5, 15.0, 15.5, 10.5)):
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
hv.inputs["Density"].default_value = 0.0012
hv.inputs["Color"].default_value = (0.86, 0.92, 1.0, 1)
hnt.links.new(hv.outputs[0], hnt.nodes["Material Output"].inputs["Volume"])
haze.data.materials.append(hm)


# ================================================================== ROOM (이찬혁의 방)
R.world = world_from_hdr("room_out", os.path.join(ASSETS, "h", "kloofendal_48d_partly_cloudy_4k.hdr"), 1.0, sun_az_deg=125, min_elev=22)
RW, RD, RH, T = 6.4, 6.4, 3.0, 0.16
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
chess = mesh_obj("chess", bm_box(0.42, 0.42, 0.03), None, R, loc=(WIN["x"] + 0.25, RD / 2 - 0.55, desk_top + 0.015), rot=(0, 0, 0.2), bevel=0.004)
cm, cnt, cbsdf = new_mat("chess")
ck = node(cnt, "ShaderNodeTexChecker")
ck.inputs["Scale"].default_value = 8
ck.inputs["Color1"].default_value = (0.8, 0.68, 0.48, 1)
ck.inputs["Color2"].default_value = (0.24, 0.12, 0.07, 1)
cnt.links.new(ck.outputs["Color"], cbsdf.inputs["Base Color"])
setin(cbsdf, "Coat Weight", 0.8)
chess.data.materials.append(cm)
spawn("painted_wooden_chair_01", R, loc=(WIN["x"] + 0.05, RD / 2 - 1.05, 0), rz=math.pi + 0.15)
spawn("Sofa_01", R, loc=(-RW / 2 + 0.48, 0.1, 0), rz=math.pi / 2)
spawn("ArmChair_01", R, loc=(-0.75, -1.15, 0), rz=-math.pi / 2 - 0.45)
spawn("painted_wooden_cabinet", R, loc=(RW / 2 - 0.32, 1.25, 0), rz=-math.pi / 2)
spawn("GothicBed_01", R, loc=(RW / 2 - 1.05, -RD / 2 + 1.15, 0), rz=math.pi)
spawn("ClassicNightstand_01", R, loc=(0.75, -RD / 2 + 0.3, 0), rz=math.pi)
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
    "F6_bed": (R, "room", cam(R, "F6", (0.4, -0.7, 1.15), (2.6, -2.55, 0.85), 30, dof=(2.9, 3.5))),
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
P.view_settings.exposure = 0.15
R.view_settings.exposure = 0.85

if ARGS.get("--save"):
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "pitch.blend"))
want = ARGS.get("--frames")


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
    scene.camera = camob
    scene.view_layers[0].update()
    scene.render.filepath = os.path.join(OUTDIR, name + ".jpg")
    bpy.ops.render.render(write_still=True, scene=scene.name)
    print("WROTE", scene.render.filepath)
print("FRAMES DONE")
