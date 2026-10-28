"""Style frames for the '소문의 낙원' pitch: the Mũi Né paradise and Lee Chan-hyuk's room.

    blender -b --factory-startup -P pitch_frames.py -- --work <dir> --cover <cover.jpg> --out <frames dir>
        [--frames F1,F2,...] [--samples 256] [--w 1920 --h 1080] [--save 1]
        [--layout layout.json] [--layout-blend <file.blend>]

Object positions in the paradise and the terrain shape come from layout.json (next to this script by
default), which the Blender layout file edits; --layout-blend builds that file instead of rendering.

<dir>/assets holds the Poly Haven CC0 downloads. Builds both scenes, then renders the
requested frames as JPEG. Blender is Z-up; the dune wall lies to +Y, the lake to -X.
"""
import bpy, bmesh, json, math, os, sys
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
SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[sys.argv.index("-P") + 1] if "-P" in sys.argv else __file__))
sys.path.insert(0, SCRIPT_DIR)
import terrain as TR  # noqa: E402
LAYOUT_PATH = os.path.abspath(ARGS.get("--layout", os.path.join(SCRIPT_DIR, "layout.json")))
LAYOUT = json.load(open(LAYOUT_PATH, encoding="utf-8")) if os.path.exists(LAYOUT_PATH) else {}
TER = TR.params(LAYOUT.get("terrain"))
print("LAYOUT", LAYOUT_PATH if LAYOUT else "(none, defaults)")

bpy.ops.wm.read_factory_settings(use_empty=True)
LIB = bpy.context.scene
LIB.name = "LIB"
P = bpy.data.scenes.new("PARADISE")
R = bpy.data.scenes.new("ROOM")


# ---------------------------------------------------------------- generic helpers
def ram(label):
    """Print this Blender process's RAM now and at peak (Windows), to keep an eye on scene weight."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] +                        [(k, ctypes.c_size_t) for k in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                                       "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                                       "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(pmc)
        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        gpmi = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        gpmi.argtypes = (wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD)
        gpmi(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        print("RAM %-22s now %.1f GB, peak %.1f GB" % (label, pmc.WorkingSetSize / 2 ** 30, pmc.PeakWorkingSetSize / 2 ** 30))
    except Exception as e:
        print("RAM unknown:", e)


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


def import_model(mid, rz=0.0, scale=1.0, key=None):
    """rz/scale correct a source model's own heading and units (Sketchfab files vary). key stores a second,
    separately coloured copy of a model (its own materials) under another name."""
    folder = os.path.join(ASSETS, "m", mid)
    path = os.path.join(folder, next(f for f in sorted(os.listdir(folder)) if f.endswith(".gltf")))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    if rz or scale != 1.0:
        fix = Matrix.Rotation(rz, 4, "Z") @ Matrix.Scale(scale, 4)
        for o in new:
            if o.parent is None:
                o.matrix_world = fix @ o.matrix_world
        bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    LIBM[key or mid] = {"objs": new, "mn": mn, "mx": mx}


def spawn(mid, scene, parent=None, loc=(0, 0, 0), rz=0.0, s=1.0, name=None):
    L = LIBM[mid]
    holder = empty(name or mid, scene, parent=parent)
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
    "bloom": ["flower_empodium", "flower_stinkkruid", "flower_gazania", "didelta_spinosa"],
    "edge": ["crystalline_iceplant", "dry_branches_medium_01", "flower_ursinia"],
    "dunefoot": ["shrub_04", "shrub_01", "searsia_burchellii", "wild_rooibos_bush", "searsia_lucida"],
    "shore": ["rock_moss_set_02", "grass_medium_02"],
}
GREEN_GRASS = True
ROOM_PROPS = ["Ukulele_01", "chess_set", "throw_pillows_01", "brass_candleholders", "standing_picture_frame_01",
              "book_encyclopedia_set_01", "potted_plant_02"]
for mid in sorted({m for v in PLANTS.values() for m in v}) + ["Sofa_01", "ArmChair_01", "Chandelier_02",
            "GothicBed_01", "ClassicNightstand_01", "painted_wooden_cabinet", "fancy_picture_frame_01", "fancy_picture_frame_02",
            "vintage_grandfather_clock_01", "vintage_oil_lamp", "wooden_table_02", "painted_wooden_chair_01"] + ROOM_PROPS:
    import_model(mid)
ram("assets imported")
for mid in PLANTS["grass"]:
    recolor(mid, lambda n: True, hsv=(0.56, 1.35, 1.15), tint=(0.28, 0.52, 0.2, 0.3))   # the MV's cool, deep meadow green
# round sage bushes on the red dunes (Mui Ne photo): dusty grey-green
for mid in ("shrub_04", "shrub_01", "searsia_burchellii"):
    recolor(mid, lambda n: not any(k in n for k in ("bark", "trunk", "branch", "stem", "wood")), tint=(0.46, 0.53, 0.4, 0.55))
# the MV's golden flowering shrubs: dense, rounded searsia clumps (a second copy, so the sage ones keep their colour)
import_model("searsia_burchellii", key="golden_bush")
recolor("golden_bush", lambda n: not any(k in n for k in ("bark", "trunk", "branch", "stem", "wood")), hsv=(0.5, 0.7, 1.35), tint=(1.0, 0.7, 0.06, 0.85))


def make_patches(key, mids, n_var=4, size=1.6, per_m2=30.0, smin=0.5, smax=1.05, tilt=0.12):
    """Pre-merged turf patches: per_m2 tufts of mids on a size x size square, realized into one mesh, n_var
    variants. Scattering patches instead of single tufts cuts the instance count ~per_m2*size^2 times; each
    Cycles instance costs ~10 KB of RAM, so this is what keeps a lush meadow light."""
    col = bpy.data.collections.new(key + "_src")
    for mid in mids:
        for o in LIBM[mid]["objs"]:
            if o.type == "MESH":
                col.objects.link(o)
    objs = []
    for v in range(n_var):
        ng = bpy.data.node_groups.new("patch_%s_%d" % (key, v), "GeometryNodeTree")
        ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        N, L = ng.nodes.new, ng.links.new
        go = N("NodeGroupOutput")
        grid = N("GeometryNodeMeshGrid")
        grid.inputs["Size X"].default_value = grid.inputs["Size Y"].default_value = size
        dist = N("GeometryNodeDistributePointsOnFaces")
        dist.inputs["Density"].default_value = per_m2
        dist.inputs["Seed"].default_value = 101 + v
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
        [x for x in rv.inputs if x.name == "Seed"][0].default_value = 211 + v
        rs = N("FunctionNodeRandomValue")
        rs.data_type = "FLOAT"
        [x for x in rs.inputs if x.name == "Min" and x.type == "VALUE"][0].default_value = smin
        [x for x in rs.inputs if x.name == "Max" and x.type == "VALUE"][0].default_value = smax
        [x for x in rs.inputs if x.name == "Seed"][0].default_value = 307 + v
        real = N("GeometryNodeRealizeInstances")
        L(grid.outputs["Mesh"], dist.inputs["Mesh"])
        L(dist.outputs["Points"], iop.inputs["Points"])
        L(ci.outputs[0], iop.inputs["Instance"])
        L([x for x in rv.outputs if x.type == "VECTOR"][0], iop.inputs["Rotation"])
        L([x for x in rs.outputs if x.type == "VALUE"][0], iop.inputs["Scale"])
        L(iop.outputs[0], real.inputs[0])
        L(real.outputs[0], go.inputs[0])
        helper = bpy.data.objects.new("patch_helper", bpy.data.meshes.new("patch_helper"))
        LIB.collection.objects.link(helper)
        helper.modifiers.new("patch", "NODES").node_group = ng
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(helper.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        me.name = "%s_%d" % (key, v)
        bpy.data.objects.remove(helper)
        bpy.data.node_groups.remove(ng)
        objs.append(bpy.data.objects.new(me.name, me))
    bpy.data.collections.remove(col)
    LIBM[key] = {"objs": objs, "mn": Vector((-size / 2, -size / 2, 0)), "mx": Vector((size / 2, size / 2, smax))}
    print("PATCHES", key, n_var, "x", len(objs[0].data.polygons), "faces")


GRASS_PATCH = 1.6 * 1.6 * 30.0   # tufts per patch
make_patches("grass_patch", PLANTS["grass"])

# ---------------------------------------------------------------- shared materials
M_LINEN = pbr("canvas", "rough_linen", scale=2.0, tint=(0.97, 0.95, 0.9), sheen=0.4)
M_WOOD = pbr("weathered", "weathered_peeling_timber", scale=1.0, hsv=(0.5, 0.8, 0.95))
M_DOOR = pbr("door_paint", "wood_peeling_paint_weathered", scale=1.8, hsv=(0.5, 1.0, 1.6))
M_BRASS = flat("brass", (0.78, 0.6, 0.28), rough=0.25, metal=1.0)
M_ROPE = flat("rope", (0.6, 0.5, 0.36), rough=0.9)
M_WHITE = flat("white_paint", (0.92, 0.92, 0.9), rough=0.4)


# ---------------------------------------------------------------- world helpers
def world_from_hdr(name, hdr_path, strength, sun_az_deg, min_elev=8, tint=None, camera_grade=None):
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
    sky = env.outputs["Color"]
    if tint:
        mx, ta, tb, tout = mix_rgb(nt, "MULTIPLY")
        mx.inputs[0].default_value = 1.0
        nt.links.new(sky, ta)
        tb.default_value = (*tint, 1)
        sky = tout
    nt.links.new(sky, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    if camera_grade:
        # what the camera sees of the sky gets the MV's clear cyan; the light the sky casts stays as photographed
        hs = node(nt, "ShaderNodeHueSaturation")
        hs.inputs["Saturation"].default_value = camera_grade.get("sat", 1.6)
        nt.links.new(sky, hs.inputs["Color"])
        gm, ga, gb, gout = mix_rgb(nt, "MULTIPLY")
        gm.inputs[0].default_value = 1.0
        nt.links.new(hs.outputs["Color"], ga)
        gb.default_value = (*camera_grade.get("tint", (0.86, 1.0, 1.06)), 1)
        gain = node(nt, "ShaderNodeVectorMath", operation="SCALE")
        nt.links.new(gout, gain.inputs[0])
        gain.inputs["Scale"].default_value = camera_grade.get("gain", 1.0)
        # the sun and its bright halo keep their photographed level, or the halation swallows a quarter of the sky
        bw = node(nt, "ShaderNodeRGBToBW")
        nt.links.new(sky, bw.inputs[0])
        hot = node(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        nt.links.new(bw.outputs[0], hot.inputs["Value"])
        hot.inputs["From Min"].default_value, hot.inputs["From Max"].default_value = 1.2, 4.0   # ~10 deg and ~4 deg from the sun
        km, ka, kb, kout = mix_rgb(nt, "MIX")
        nt.links.new(hot.outputs["Result"], km.inputs[0])
        nt.links.new(gain.outputs["Vector"], ka)
        nt.links.new(sky, kb)
        bgc = node(nt, "ShaderNodeBackground")
        nt.links.new(kout, bgc.inputs["Color"])
        bgc.inputs["Strength"].default_value = strength
        # camera rays only: graded glossy rays would also brighten the sheen on every grass blade
        lp = node(nt, "ShaderNodeLightPath")
        ms = node(nt, "ShaderNodeMixShader")
        nt.links.new(lp.outputs["Is Camera Ray"], ms.inputs[0])
        nt.links.new(bg.outputs[0], ms.inputs[1])
        nt.links.new(bgc.outputs[0], ms.inputs[2])
        nt.links.new(ms.outputs[0], out.inputs["Surface"])
    else:
        nt.links.new(bg.outputs[0], out.inputs["Surface"])
    w["sun_dir"] = list(sun_dir)
    print("WORLD", name, "sun elev", round(math.degrees(elev), 1))
    return w


# ================================================================== PARADISE (Bàu Trắng, Mũi Né)
SKY = LAYOUT.get("sky", "syferfontein_18d_clear_puresky_8k.hdr")
W_DAY = world_from_hdr("day", os.path.join(ASSETS, "h", SKY), 1.0, sun_az_deg=LAYOUT.get("sun_az", 20), tint=(1.0, 0.96, 0.9),
                       camera_grade=LAYOUT.get("sky_grade", {"sat": 1.15, "tint": (0.88, 1.0, 0.86), "gain": 3.0}))
W_DAY["sun_dir"] = [-W_DAY["sun_dir"][0], -W_DAY["sun_dir"][1], W_DAY["sun_dir"][2]]
_GOLD = []


def w_gold():
    """The sunset world for the old golden style frames, loaded only when one is rendered (an 8K sky is ~0.5 GB in memory)."""
    if not _GOLD:
        _GOLD.append(world_from_hdr("golden", os.path.join(ASSETS, "h", "qwantani_sunset_puresky_8k.hdr"), 1.1, sun_az_deg=160, min_elev=10))
    return _GOLD[0]
P.world = W_DAY
SUN_P = light(P, "SUN", "sun", 4.6, (1.0, 0.8, 0.58), (0, 0, 50))
SUN_P.data.angle = math.radians(0.6)


def river_y(x):
    return TR.river_y(x, TER)


def barchans(x, y):
    return TR.barchans(x, y, TER)


def terrain(x, y):
    return TR.terrain(x, y, TER)


GSPEC = TR.grid_spec(TER)
N = GSPEC["n"]
X, Y = TR.grid(TER)
Z, DUNE, LAKE = terrain(X, Y)
MASKS = TR.masks(X, Y, DUNE, LAKE, TER)
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
for nm, arr in MASKS.items():
    me.attributes.new(nm, "FLOAT", "POINT").data.foreach_set("value", arr.ravel().astype(np.float32))

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
hs.inputs["Value"].default_value = 1.45
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
gh.inputs["Hue"].default_value = 0.6
gh.inputs["Saturation"].default_value = 1.9
gh.inputs["Value"].default_value = 1.15
nt.links.new(grs_d.outputs["Color"], gh.inputs["Color"])
meadow_col = mixc(1.0, mixc(0.1, gh.outputs["Color"], mud_d.outputs["Color"]), (0.55, 0.8, 0.32, 1), "MULTIPLY")
# Mui Ne red sand: the same scans, warmed toward orange
redn = node(nt, "ShaderNodeHueSaturation")
redn.inputs["Saturation"].default_value = 1.25
redn.inputs["Value"].default_value = 0.95
nt.links.new(sand, redn.inputs["Color"])
sand_red = mixc(1.0, redn.outputs["Color"], (1.0, 0.62, 0.4, 1), "MULTIPLY")
sand_white = mixc(1.0, sand, (1.0, 0.95, 0.86, 1), "MULTIPLY")
col = mixc(gattr("red"), sand_white, sand_red)
col = mixc(gattr("white"), col, sand_white)
col = mixc(gattr("camp"), col, mixc(1.0, sand, (0.98, 0.9, 0.78, 1), "MULTIPLY"))
col = mixc(gattr("shore"), col, damp_d.outputs["Color"])
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
# open desert beyond the detailed ground, out to the horizon
TR.build_far_desert(bpy, P, TER)

# the lake: one sheet at water level over the basin; each vertex knows the depth below it, so the shallows
# read olive-sand and the middle dark teal, the way the MV and the Bau Trang photos show it
water, nt, wb = new_mat("water")
setin(wb, "Roughness", 0.03)
setin(wb, "IOR", 1.33)
setin(wb, "Specular IOR Level", 0.5)
wv, wq, depth = TR.lake_mesh_arrays(TER)
wme = bpy.data.meshes.new("lake")
wme.vertices.add(len(wv))
wme.vertices.foreach_set("co", wv.ravel())
wme.loops.add(wq.size)
wme.loops.foreach_set("vertex_index", wq.ravel().astype(np.int32))
wme.polygons.add(len(wq))
wme.polygons.foreach_set("loop_start", np.arange(0, wq.size, 4, dtype=np.int32))
wme.update(calc_edges=True)
wme.attributes.new("depth", "FLOAT", "POINT").data.foreach_set("value", depth)
da = node(nt, "ShaderNodeAttribute")
da.attribute_type = "GEOMETRY"
da.attribute_name = "depth"
wmix, wA, wB, wO = mix_rgb(nt, "MIX")
nt.links.new(da.outputs["Fac"], wmix.inputs[0])
wA.default_value = (0.36, 0.36, 0.25, 1)    # shallow olive-sand
wB.default_value = (0.03, 0.09, 0.1, 1)     # deep teal
nt.links.new(wO, wb.inputs["Base Color"])
wtc = node(nt, "ShaderNodeTexCoord")
wn1 = node(nt, "ShaderNodeTexNoise")
wn1.inputs["Scale"].default_value = 0.35
wn1.inputs["Detail"].default_value = 5
nt.links.new(wtc.outputs["Object"], wn1.inputs["Vector"])
wn2 = node(nt, "ShaderNodeTexNoise")
wn2.inputs["Scale"].default_value = 9
nt.links.new(wtc.outputs["Object"], wn2.inputs["Vector"])
wb1 = node(nt, "ShaderNodeBump")
wb1.inputs["Strength"].default_value = 0.06
nt.links.new(wn1.outputs["Fac"], wb1.inputs["Height"])
wb2 = node(nt, "ShaderNodeBump")
wb2.inputs["Strength"].default_value = 0.02
nt.links.new(wn2.outputs["Fac"], wb2.inputs["Height"])
nt.links.new(wb1.outputs["Normal"], wb2.inputs["Normal"])
nt.links.new(wb2.outputs["Normal"], wb.inputs["Normal"])
wme.materials.append(water)
link(bpy.data.objects.new("lake", wme), P)

# the open sea to the east, beyond the dunes
sea, nt, sb = new_mat("sea")
# deep blue body with soft, weak reflections, so it reads as sea rather than a mirror of the pale horizon
setin(sb, "Base Color", (0.005, 0.045, 0.11, 1))
setin(sb, "Roughness", 0.22)
setin(sb, "IOR", 1.33)
setin(sb, "Specular IOR Level", 0.22)
stc = node(nt, "ShaderNodeTexCoord")
smp = node(nt, "ShaderNodeMapping")
smp.inputs["Scale"].default_value = (0.04, 0.12, 1.0)
nt.links.new(stc.outputs["Object"], smp.inputs["Vector"])
snz = node(nt, "ShaderNodeTexNoise")
snz.inputs["Scale"].default_value = 6.0
snz.inputs["Detail"].default_value = 6
nt.links.new(smp.outputs["Vector"], snz.inputs["Vector"])
sbu = node(nt, "ShaderNodeBump")
sbu.inputs["Strength"].default_value = 0.25
nt.links.new(snz.outputs["Fac"], sbu.inputs["Height"])
nt.links.new(sbu.outputs["Normal"], sb.inputs["Normal"])
mesh_obj("sea", bm_plane(16000, 40000), sea, P, loc=(TER["sea"]["coast_x"] * TER["desert_scale"] + 8000, 0, TER["sea_level"]))

# vegetation: Geometry Nodes scatter layers. Each picks Poly Haven scans where its mask attribute
# is high, thinned by a noise field so plants grow in clumps and gaps instead of an even carpet.
VIEW_XY = tuple(LAYOUT.get("viewpoint", (2.0, 4.0)))


def scatter(name, mids, density, mask, smin, smax, clump=0.0, seed=0, tilt=0.12, crange=(0.45, 0.62), near=0.0, far=0.0, floor=1.0,
            grow=1.0, per_instance=1.0):
    """grow > 1: plants thinned out with distance are scaled up by 1/sqrt(thinning), at most grow times, so the
    ground stays as covered with a fraction of the instances (the game-LOD trick for scattered foliage).
    per_instance: plants each instance carries (turf patches); density stays in plants per m2."""
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
    if far > near:
        # distance falloff: full density within `near` metres of the viewpoint, down to `floor` by `far`
        pos = N("GeometryNodeInputPosition")
        sep = N("ShaderNodeSeparateXYZ")
        ng.links.new(pos.outputs[0], sep.inputs[0])
        cmb = N("ShaderNodeCombineXYZ")
        ng.links.new(sep.outputs["X"], cmb.inputs["X"])
        ng.links.new(sep.outputs["Y"], cmb.inputs["Y"])
        dist = N("ShaderNodeVectorMath")
        dist.operation = "DISTANCE"
        ng.links.new(cmb.outputs[0], dist.inputs[0])
        dist.inputs[1].default_value = (VIEW_XY[0], VIEW_XY[1], 0)
        fall = N("ShaderNodeMapRange")
        fall.interpolation_type = "SMOOTHSTEP"
        fall.inputs["From Min"].default_value, fall.inputs["From Max"].default_value = near, far
        fall.inputs["To Min"].default_value, fall.inputs["To Max"].default_value = 1.0, floor
        ng.links.new(dist.outputs["Value"], fall.inputs["Value"])
        mul2 = N("ShaderNodeMath")
        mul2.operation = "MULTIPLY"
        ng.links.new(prob, mul2.inputs[0])
        ng.links.new(fall.outputs["Result"], mul2.inputs[1])
        prob = mul2.outputs[0]
        fall_out = fall.outputs["Result"]
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
    scale = [x for x in rs.outputs if x.type == "VALUE"][0]
    if grow > 1.0 and far > near:
        boost = N("ShaderNodeMath")
        boost.operation = "POWER"
        L(fall_out, boost.inputs[0])
        boost.inputs[1].default_value = -0.5
        cap = N("ShaderNodeMath")
        cap.operation = "MINIMUM"
        L(boost.outputs[0], cap.inputs[0])
        cap.inputs[1].default_value = grow
        smul = N("ShaderNodeMath")
        smul.operation = "MULTIPLY"
        L(scale, smul.inputs[0])
        L(cap.outputs[0], smul.inputs[1])
        scale = smul.outputs[0]
    if per_instance != 1.0:
        pin = N("ShaderNodeMath")
        pin.operation = "MULTIPLY"
        L(prob, pin.inputs[0])
        pin.inputs[1].default_value = 1.0 / per_instance
        prob = pin.outputs[0]
    dmul = N("ShaderNodeMath")   # random mode takes density as a field: points only where the mask allows
    dmul.name = "density"        # the layout panel's density slider is this node's second input
    dmul.operation = "MULTIPLY"
    dmul.inputs[1].default_value = density
    L(prob, dmul.inputs[0])
    L(dmul.outputs[0], dist_n.inputs["Density"])
    L(dist_n.outputs["Points"], iop.inputs["Points"])
    L(ci.outputs[0], iop.inputs["Instance"])
    L([x for x in rv.outputs if x.type == "VECTOR"][0], iop.inputs["Rotation"])
    L(scale, iop.inputs["Scale"])
    L(gi.outputs[0], join.inputs[0])
    L(iop.outputs[0], join.inputs[0])
    L(join.outputs[0], go.inputs[0])
    ground.modifiers.new(name, "NODES").node_group = ng


PLANT_D = LAYOUT.get("plants", {})
ram("before scatter")
scatter("grass", ["grass_patch"], PLANT_D.get("grass", 90.0), "grass", 0.85, 1.15, clump=0.12, seed=1, tilt=0.04, crange=(0.1, 0.32),
        near=10, far=80, floor=0.025, grow=1.8, per_instance=GRASS_PATCH)
scatter("bloom", PLANTS["bloom"], PLANT_D.get("bloom", 0.6), "wild", 0.5, 1.0, clump=0.06, seed=2, near=20, far=220, floor=0.15)
scatter("edge", PLANTS["edge"], PLANT_D.get("edge", 0.4), "edge", 0.6, 1.4, clump=0.12, seed=3, tilt=0.3, near=30, far=260, floor=0.25)
scatter("dunefoot", PLANTS["dunefoot"], PLANT_D.get("dunefoot", 0.09), "dunefoot", 1.2, 2.6, clump=0.04, seed=4, near=60, far=750, floor=0.18)
scatter("shore", PLANTS["shore"], PLANT_D.get("shore", 0.5), "shore", 0.6, 1.5, clump=0.1, seed=5, tilt=0.3, near=30, far=320, floor=0.3)
scatter("reeds", ["grass_medium_01"], PLANT_D.get("reeds", 9.0), "reeds", 1.9, 3.1, clump=0.15, seed=6, tilt=0.15, near=40, far=420, floor=0.3)
scatter("dunetop", PLANTS["dunefoot"], PLANT_D.get("dunetop", 0.02), "dunetop", 1.0, 1.8, clump=0.06, seed=7)

# golden tree clusters (centres, counts and spread from layout.json "trees")
TREES = TR.trees(LAYOUT.get("trees"))
GOLD_H = LIBM["golden_bush"]["mx"].z - LIBM["golden_bush"]["mn"].z
for ci, c in enumerate(TREES["yellow"]["clusters"]):
    for nm, x, y, rz, u in TR.cluster_trees("yellow", ci, c, TREES["yellow"]["density"], TER):
        spawn("golden_bush", P, loc=(x, y, float(terrain(np.array(x), np.array(y))[0]) - 0.15), rz=rz, s=(2.2 + 1.6 * u) / GOLD_H, name=nm)

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
cabin_tent("tent_mint", (12.0, 24.0), 3.4, 2.8, 1.1, 2.3, TENT_MINT, rz=-0.3, awning=1.4)
cabin_tent("tent_pink", (16.5, 27.0), 3.0, 2.6, 1.0, 2.1, TENT_PINK, rz=-0.45)
cabin_tent("tent_pink2", (20.5, 28.5), 2.4, 2.2, 0.9, 1.8, TENT_PINK, rz=-0.1)
dome_tent("dome_white", (25.0, 24.0), r=1.6, h=1.4, rz=-0.6)
dome_tent("dome_sky", (8.5, 28.5), r=1.3, h=1.2, rz=-0.2, mat=TENT_SKY)
teepee("teepee", (13.5, 19.5), r=1.5, h=3.6, mat=TENT_SKY)
# bunting strung over the camp
flag_cols = [(0.12, 0.6, 0.7), (0.95, 0.75, 0.2), (0.8, 0.25, 0.18), (0.95, 0.92, 0.85), (0.25, 0.55, 0.3)]
BUNT = Vector((14.5, 23.0, ground_z(14.5, 23.0)))
bunting = empty("bunting", P, loc=BUNT)
for (ax, ay, bx, by) in ((12.0, 24.0, 16.5, 27.0), (16.5, 27.0, 20.5, 28.5), (9.4, 16.9, 13.5, 19.5)):
    pa = Vector((ax, ay, ground_z(ax, ay) + 3.0))
    pb = Vector((bx, by, ground_z(bx, by) + 3.4))
    prev = None
    for i in range(25):
        t = i / 24
        p = pa.lerp(pb, t)
        p.z -= math.sin(t * math.pi) * 0.5
        if prev is not None:
            seg = p - prev
            c = mesh_obj("string", bm_cyl(0.005, 0.005, seg.length, 6), M_ROPE, P, bunting, loc=(prev + p) / 2 - BUNT)
            c.rotation_euler = seg.to_track_quat("Z", "Y").to_euler()
        if 0 < i < 24 and i % 2 == 0:
            bmf = bmesh.new()
            v1, v2, v3 = bmf.verts.new((-0.15, 0, 0)), bmf.verts.new((0.15, 0, 0)), bmf.verts.new((0, 0, -0.34))
            bmf.faces.new((v1, v2, v3))
            f = mesh_obj("pennant", bmf, flat("pen%d" % i, flag_cols[(i // 2) % 5], rough=0.8, sheen=0.4), P, bunting, loc=p - BUNT)
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

# wind turbines on the far hills across the lake, small on the horizon as in the Mui Ne photos
# (beyond the detailed ground, so they stand on the far land's surface)
for i, (x, y) in enumerate(((-900, -1020), (-640, -960), (-390, -1060), (-130, -990), (130, -1050), (390, -970), (-1150, -930))):
    g = empty("turbine_%d" % (i + 1), P, loc=(x, y, float(TR.far_desert(np.array(float(x)), np.array(float(y)), TER)) - 1), rz=0.9)
    mesh_obj("tower", bm_cyl(1.1, 0.6, 60, 16), M_WHITE, P, g, loc=(0, 0, 30))
    mesh_obj("nacelle", bm_box(2.0, 4.0, 2.0), M_WHITE, P, g, loc=(0, 0, 61))
    for k in range(3):
        bl = mesh_obj("blade", bm_box(0.9, 0.25, 26), M_WHITE, P, g, loc=(0, -2.2, 61))
        bl.rotation_euler = (0, TAU * k / 3 + i, 0)
        bl.location = (math.sin(TAU * k / 3 + i) * 13, -2.2, 61 + math.cos(TAU * k / 3 + i) * 13)

# ================================================================== AKMU content in the desert
# Objects tagged with "hot" become clickable regions in the site (ID masks); children inherit the tag.
REFS = os.path.dirname(COVER)
FONTS = os.path.join(WORK, "fonts")
F_TYPE = bpy.data.fonts.load(os.path.join(FONTS, "SpecialElite-Regular.ttf"))
F_KR = bpy.data.fonts.load(os.path.join(FONTS, "Pretendard-SemiBold.otf"))
M_INK = flat("ink", (0.08, 0.06, 0.05), rough=0.8)
M_CREAM = flat("cream_paint", (0.9, 0.85, 0.74), rough=0.7)
M_TVWOOD = pbr("tv_wood", "wood_planks", scale=3, tint=(0.5, 0.32, 0.2), coat=0.6, rough=0.5)


def tag(ob, group):
    ob["hot"] = group
    return ob


def text_obj(scene, body, size, parent=None, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), mat=None, font=None, extrude=0.003):
    cu = bpy.data.curves.new("txt", "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.font = font or F_TYPE
    cu.materials.append(mat or M_INK)
    ob = bpy.data.objects.new("txt", cu)
    ob.location, ob.rotation_euler = loc, rot
    return link(ob, scene, parent)


def retro_tv(scene, name, loc, rz, img, parent=None, s=1.0):
    g = empty(name, scene, loc=loc, rz=rz, parent=parent)
    g.scale = (s, s, s)
    mesh_obj("tvbody", bm_box(0.78, 0.55, 0.58), M_TVWOOD, scene, g, loc=(0, 0, 0.29), bevel=0.04)
    mesh_obj("bezel", bm_box(0.56, 0.02, 0.44), flat("bezel", (0.1, 0.09, 0.08), rough=0.4), scene, g, loc=(-0.07, -0.28, 0.31), bevel=0.02)
    mesh_obj("screen", bm_plane(0.5, 0.375), image_mat("tvscreen_" + name, img, rough=0.15, emit=1.6), scene, g, loc=(-0.07, -0.292, 0.31), rot=(math.pi / 2, 0, 0))
    for z in (0.42, 0.24):
        mesh_obj("knob", bm_cyl(0.025, 0.025, 0.03, 16), M_BRASS, scene, g, loc=(0.29, -0.285, z), rot=(math.pi / 2, 0, 0))
    for a in (-0.5, 0.5):
        mesh_obj("antenna", bm_cyl(0.004, 0.004, 0.45, 6), M_BRASS, scene, g, loc=(0.1 + a * 0.2, 0, 0.58 + 0.2), rot=(0, a, 0))
    return g


def sleeves(scene, parent, n, front_img, loc=(0, 0, 0), w=0.31):
    for i in range(n):
        m = flat("sl%d" % i, ((0.86, 0.66, 0.24), (0.42, 0.48, 0.66), (0.7, 0.3, 0.2), (0.25, 0.45, 0.35), (0.9, 0.86, 0.78))[i % 5], rough=0.6)
        sl = mesh_obj("sleeve", bm_box(w, 0.006, w), m, scene, parent, loc=(loc[0], loc[1] + 0.04 * (n - 1 - i), loc[2] + w / 2), rot=(-0.12, 0, 0))
        if i == n - 1:  # the album faces out at the front of the crate
            mesh_obj("sleeve_img", bm_plane(w, w), image_mat("sleeve_front", front_img, rough=0.6), scene, sl, loc=(0, -0.0035, 0), rot=(math.pi / 2, 0, 0))


DESERT_HOT = {}
gz = ground_z
C360 = tuple(LAYOUT.get("viewpoint", (2.0, 4.0)))


def face(x, y):
    """rz that turns an object's front (-Y) toward the desert viewpoint."""
    return math.atan2(C360[0] - x, -(C360[1] - y))
# signpost
sp = tag(empty("signpost", P, loc=(-4.5, 1, gz(-4.5, 1) - 0.05), rz=face(-4.5, 1) - 0.4), "sign")
mesh_obj("spost", bm_cyl(0.06, 0.06, 3.0, 12), M_POST, P, sp, loc=(0, 0, 1.5))
for k, (txt, ang, z) in enumerate((("PARADISE", 0.5, 2.6), ("THE ROOM", -0.35, 2.2), ("TOUR", 0.15, 1.8), ("소문", -0.6, 1.4))):
    arm = empty("arm", P, loc=(0, 0, z), rz=ang, parent=sp)
    mesh_obj("board", bm_box(1.15, 0.05, 0.24), M_CREAM, P, arm, loc=(0.6, 0, 0), bevel=0.01)
    text_obj(P, txt, 0.14, arm, loc=(0.6, -0.03, 0), font=F_KR if txt == "소문" else F_TYPE)
DESERT_HOT["sign"] = sp
# record stall: table, LP crate, the album cover on an easel
rs = tag(empty("records", P, loc=(-4, 9.5, gz(-4, 9.5) - 0.05), rz=face(-4, 9.5)), "records")
mesh_obj("rtop", bm_box(2.0, 0.85, 0.05), M_WOOD, P, rs, loc=(0, 0, 0.78), bevel=0.01)
for sx in (-0.9, 0.9):
    for sy in (-0.35, 0.35):
        mesh_obj("rleg", bm_box(0.05, 0.05, 0.78), M_WOOD, P, rs, loc=(sx, sy, 0.39))
crate = empty("lpcrate", P, loc=(-0.5, 0.05, 0.805), parent=rs)
for (bx, by, bz, sx_, sy_) in ((0, -0.22, 0.12, 0.38, 0.02), (0, 0.22, 0.12, 0.38, 0.02), (-0.18, 0, 0.12, 0.02, 0.46), (0.18, 0, 0.12, 0.02, 0.46), (0, 0, 0.005, 0.38, 0.46)):
    mesh_obj("crate", bm_box(sx_, sy_, bz * 2 if bz > 0.01 else 0.01), M_WOOD, P, crate, loc=(bx, by, bz))
sleeves(P, crate, 7, COVER, loc=(0, -0.16, 0.0))
easel = empty("easel", P, loc=(0.45, 0, 0.805), rz=0.15, parent=rs)
mesh_obj("cover_back", bm_box(0.62, 0.012, 0.62), M_CREAM, P, easel, loc=(0, 0.05, 0.36), rot=(-0.2, 0, 0))
mesh_obj("cover_big", bm_plane(0.62, 0.62), image_mat("cover_big", COVER, rough=0.6), P, easel, loc=(0, 0.05 - 0.0075, 0.36), rot=(math.pi / 2 - 0.2, 0, 0))
mesh_obj("easel_leg", bm_box(0.03, 0.03, 0.75), M_POST, P, easel, loc=(0, 0.16, 0.35), rot=(0.25, 0, 0))
mesh_obj("rsignpole", bm_cyl(0.025, 0.025, 1.4, 8), M_POST, P, rs, loc=(-0.95, 0.38, 1.5))
mesh_obj("rsign", bm_box(0.9, 0.03, 0.28), M_CREAM, P, rs, loc=(-0.95, 0.38, 2.15), bevel=0.01)
text_obj(P, "RECORDS", 0.15, rs, loc=(-0.95, 0.36, 2.15))
DESERT_HOT["records"] = rs
# TV tower playing the MV
tvs = tag(empty("tvtower", P, loc=(7.5, 7.5, gz(7.5, 7.5) - 0.05), rz=face(7.5, 7.5)), "tv")
mesh_obj("tvcrate", bm_box(1.0, 0.7, 0.55), M_WOOD, P, tvs, loc=(0, 0, 0.275), bevel=0.01)
retro_tv(P, "tv1", (-0.22, 0, 0.55), 0.05, os.path.join(REFS, "mv_paradise_01.jpg"), tvs)
retro_tv(P, "tv2", (0.3, 0.02, 0.55), -0.12, os.path.join(REFS, "mv_paradise_02.jpg"), tvs, s=0.8)
retro_tv(P, "tv3", (0.02, 0.05, 1.13), 0.1, os.path.join(REFS, "concert_01.jpg"), tvs, s=0.9)
text_obj(P, "M/V", 0.16, tvs, loc=(0, -0.36, 0.3), mat=M_CREAM)
DESERT_HOT["tv"] = tvs
# merch rack beside the camp
mr = tag(empty("merch", P, loc=(11, 10, gz(11, 10) - 0.05), rz=face(11, 10)), "merch")
for sx in (-0.85, 0.85):
    mesh_obj("rpost", bm_cyl(0.025, 0.025, 1.7, 10), M_POST, P, mr, loc=(sx, 0, 0.85))
    mesh_obj("rfoot", bm_box(0.06, 0.6, 0.04), M_POST, P, mr, loc=(sx, 0, 0.02))
mesh_obj("rbar", bm_cyl(0.018, 0.018, 1.75, 10), M_BRASS, P, mr, loc=(0, 0, 1.68), rot=(0, math.pi / 2, 0))
TEE = [(-0.25, 0), (0.25, 0), (0.25, 0.45), (0.4, 0.38), (0.47, 0.5), (0.25, 0.62), (0.1, 0.62), (0, 0.58), (-0.1, 0.62), (-0.25, 0.62), (-0.47, 0.5), (-0.4, 0.38), (-0.25, 0.45)]
for k, c in enumerate(((0.95, 0.93, 0.88), (0.62, 0.82, 0.76), (0.94, 0.72, 0.72), (0.96, 0.82, 0.42))):
    bm = bmesh.new()
    vs = [bm.verts.new((x * 0.85, 0, z * 0.85)) for x, z in TEE]
    bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    t = mesh_obj("tee", bm, flat("tee%d" % k, c, rough=0.85, sheen=0.5), P, mr, loc=(-0.6 + k * 0.4, 0.02 * k, 1.08), rot=(0, 0, 0.12 * (k - 1.5)))
    t.modifiers.new("s", "SOLIDIFY").thickness = 0.01
    mesh_obj("hanger", bm_cyl(0.006, 0.006, 0.12, 6), M_BRASS, P, mr, loc=(-0.6 + k * 0.4, 0.02 * k, 1.62))
mesh_obj("msign", bm_box(0.7, 0.03, 0.22), M_CREAM, P, mr, loc=(0, 0, 1.92), bevel=0.01)
text_obj(P, "MERCH", 0.14, mr, loc=(0, -0.02, 1.92))
DESERT_HOT["merch"] = mr
# basket boat moored in the cove below the knoll, with a bottle letter
bt = tag(empty("boat", P, loc=(-5, -25, -0.25), rz=0.6), "boat")
bt.scale = (1.2,) * 3   # a 2.4 m thung chai, big enough to read from the viewpoint
prof = [(1.0 * math.sin(t * math.pi / 2) + 0.02, -0.45 * math.cos(t * math.pi / 2) + 0.45) for t in np.linspace(0, 1, 14)]
mesh_obj("basket", bm_lathe(prof, 48, lambda a, z: 0.01 * math.sin(a * 40)), pbr("basket", "weathered_peeling_timber", scale=4, tint=(0.62, 0.48, 0.32)), P, bt, smooth_shade=True).modifiers.new("s", "SOLIDIFY").thickness = 0.03
mesh_obj("rim", bm_torus(1.0, 0.035, 48, 8), M_POST, P, bt, loc=(0, 0, 0.45), smooth_shade=True)
mesh_obj("paddle", bm_box(0.06, 1.7, 0.02), M_POST, P, bt, loc=(0.3, 0.1, 0.5), rot=(0.15, 0.1, 0.6))
mesh_obj("bottle", bm_cyl(0.05, 0.035, 0.26, 16), flat("bottle_glass", (0.75, 0.9, 0.85), rough=0.05, trans=1.0, ior=1.45), P, bt, loc=(-0.25, -0.2, 0.2), rot=(1.2, 0, 0.3))
mesh_obj("letter", bm_box(0.03, 0.16, 0.03), M_CREAM, P, bt, loc=(-0.25, -0.2, 0.2), rot=(1.2, 0, 0.3))
DESERT_HOT["boat"] = bt
# dark trees on the near bank (MV, left of frame)
import_model("island_tree_01")
for k, (x, y, s_) in enumerate(((-96, -36, 1.0), (-112, -44, 0.9), (58, -40, 0.8), (-150, -30, 1.2), (140, -55, 1.1))):
    spawn("island_tree_01", P, loc=(x, y, gz(x, y) - 0.2), rz=x * 0.37, s=s_, name="dark_tree_%d" % (k + 1))
# a belt of dark pines along the far bank, in clumps, leaving the middle open to the sea
import_model("pine_tree_lod")
PINE_H = LIBM["pine_tree_lod"]["mx"].z - LIBM["pine_tree_lod"]["mn"].z
# casuarinas: a duller, greyer green than a European pine
recolor("pine_tree_lod", lambda n: "twig" in n or "needle" in n or "leaf" in n, tint=(0.33, 0.4, 0.28, 0.5))
for ci, c in enumerate(TREES["pine"]["clusters"]):
    for nm, x, y, rz, u in TR.cluster_trees("pine", ci, c, TREES["pine"]["density"], TER):
        spawn("pine_tree_lod", P, loc=(x, y, gz(x, y) - 0.3), rz=rz, s=(8 + 6 * u) / PINE_H, name=nm)
# picnic on the knoll above the cove: gingham blanket, boombox (playlist) and a wicker basket
import_model("boombox")
import_model("wicker_basket_01")
gy, gx = np.mgrid[0:256, 0:256]
ging = np.ones((256, 256, 3)) * np.array([0.93, 0.9, 0.84])
band = ((gx // 32) % 2 == 0).astype(float) * 0.5 + ((gy // 32) % 2 == 0).astype(float) * 0.5
ging = ging * (1 - band[..., None]) + band[..., None] * np.array([0.78, 0.22, 0.2])
pc = tag(empty("picnic", P, loc=(3.5, -7, gz(3.5, -7) + 0.01), rz=face(3.5, -7)), "picnic")
bl = bm_plane(2.2, 1.7, 22, 16)
for vv in bl.verts:
    vv.co.z += 0.015 * math.sin(vv.co.x * 9) * math.sin(vv.co.y * 7)
mesh_obj("blanket", bl, image_mat("gingham", save_png("gingham", np.clip(ging, 0, 1)), rough=0.9, sheen=0.5), P, pc, loc=(0, 0, 0.02), smooth_shade=True)
spawn("boombox", P, parent=pc, loc=(-0.45, 0.15, 0.03), rz=0.15)
spawn("wicker_basket_01", P, parent=pc, loc=(0.6, 0.35, 0.03), rz=-0.4)
for k in range(3):
    mesh_obj("cassette", bm_box(0.1, 0.064, 0.012), flat("cass%d" % k, ((0.95, 0.9, 0.8), (0.3, 0.5, 0.7), (0.9, 0.55, 0.3))[k], rough=0.5), P, pc, loc=(0.0 + 0.12 * k, -0.35, 0.03 + 0.012 * k), rot=(0, 0, 0.3 * k))
DESERT_HOT["picnic"] = pc

# band gear left out for the show, no players (Sketchfab, CC BY 4.0, see CREDITS.md)
# drum kit: modelled about 1.6x life size (97 cm bass drum), scaled to a real kit
import_model("sf_drum_kit", scale=0.6)
import_model("sf_mic_stand")
import_model("sf_acoustic_guitar")
# 1970 pickup: the file is about half scale and turned 43 degrees; straightened so its front is +X
import_model("sf_pickup_1970", rz=-math.radians(42.8), scale=2.2)
ST_RZ = 0.12


def on_stage(lx, ly):
    """World position of a point in the stage wagon's own frame."""
    sx, sy = stage.location.x, stage.location.y
    return (sx + lx * math.cos(ST_RZ) - ly * math.sin(ST_RZ), sy + lx * math.sin(ST_RZ) + ly * math.cos(ST_RZ))


for mid, nm, lx, ly in (("sf_mic_stand", "mic_stands", -0.35, -1.0), ("sf_acoustic_guitar", "guitar", -1.2, -0.95)):
    wx, wy = on_stage(lx, ly)
    spawn(mid, P, parent=stage, loc=(lx, ly, 0.5), rz=face(wx, wy) - ST_RZ, name=nm)
wx, wy = on_stage(4.4, -0.2)
tag(spawn("sf_drum_kit", P, loc=(wx, wy, gz(wx, wy)), rz=face(wx, wy), name="drum_kit")[0], "stage")
# the pickup parked between the merch rack and the tents, nose toward the river
spawn("sf_pickup_1970", P, loc=(19.0, 9.0, gz(19.0, 9.0)), rz=math.radians(-113), name="pickup_truck")
DESERT_HOT["stage"] = tag(stage, "stage")
DESERT_HOT["door"] = tag(door, "door")


# ---------------------------------------------------------------- layout overrides
# Every top-level holder in the paradise (stage, tents, props, trees ...) can be moved in layout.json.
# Heights are stored relative to the ground (dz), so things stay seated when the dunes are reshaped.
def layout_holders(scene):
    return [o for o in scene.objects if o.parent is None and o.type == "EMPTY"]


n_moved = 0
for o in layout_holders(P):
    o["home"] = [o.location.x, o.location.y, o.location.z - gz(o.location.x, o.location.y), math.degrees(o.rotation_euler.z), o.scale.x]
    v = LAYOUT.get("objects", {}).get(o.name)
    if not v:
        continue
    o.location = (v["x"], v["y"], gz(v["x"], v["y"]) + v.get("dz", 0.0))
    o.rotation_euler.z = math.radians(v.get("rz", math.degrees(o.rotation_euler.z)))
    if "s" in v:
        o.scale = (v["s"],) * 3
    n_moved += 1
print("LAYOUT objects", n_moved, "of", len(layout_holders(P)))
# no grass through the picnic blanket, a gap in the reeds at the boat and a footpath down to it (after the
# layout.json moves, so the clearings follow the props)
_b, _p = DESERT_HOT["boat"].location, DESERT_HOT["picnic"].location
TR.clear_masks(MASKS, *TR.grid(TER), TR.prop_clearings(VIEW_XY, (_b.x, _b.y), (_p.x, _p.y)))
for nm in TR.CLEARED:
    ground.data.attributes[nm].data.foreach_set("value", MASKS[nm].ravel().astype(np.float32))
# the blanket drapes over the slope it lies on instead of letting the ground poke through
P.view_layers[0].update()
for o in DESERT_HOT["picnic"].children:
    if o.name.startswith("blanket"):
        mw = o.matrix_world
        for v in o.data.vertices:
            w_ = mw @ v.co
            v.co.z += gz(w_.x, w_.y) + 0.035 - w_.z
        o.data.update()

# gentle aerial haze: a low, homogeneous slab (cheap to sample) that softens the distance but leaves the sky above clear
haze = mesh_obj("haze", bm_box(8000, 8000, 170), None, P, loc=(0, 0, 65))
hm = bpy.data.materials.new("haze")
hm.use_nodes = True
hnt = hm.node_tree
hnt.nodes.remove(hnt.nodes["Principled BSDF"])
hv = node(hnt, "ShaderNodeVolumePrincipled")
hv.inputs["Color"].default_value = (1.0, 0.95, 0.88, 1)
hv.inputs["Anisotropy"].default_value = 0.55
# density falls off with height: thick near the ground, clear above ~30 m
hsep = node(hnt, "ShaderNodeSeparateXYZ")
hnt.links.new(node(hnt, "ShaderNodeNewGeometry").outputs["Position"], hsep.inputs[0])
hzc = node(hnt, "ShaderNodeMath", operation="MAXIMUM")
hnt.links.new(hsep.outputs["Z"], hzc.inputs[0])
hzc.inputs[1].default_value = 0.0
hexp = node(hnt, "ShaderNodeMath", operation="MULTIPLY")
hnt.links.new(hzc.outputs[0], hexp.inputs[0])
hexp.inputs[1].default_value = -1 / 11.0
hpow = node(hnt, "ShaderNodeMath", operation="EXPONENT")
hnt.links.new(hexp.outputs[0], hpow.inputs[0])
hden = node(hnt, "ShaderNodeMath", operation="MULTIPLY")
hnt.links.new(hpow.outputs[0], hden.inputs[0])
hden.inputs[1].default_value = 0.0013
hnt.links.new(hden.outputs[0], hv.inputs["Density"])
hnt.links.new(hv.outputs[0], hnt.nodes["Material Output"].inputs["Volume"])
haze.data.materials.append(hm)
# --haze 0 renders without the volume (to compare cost, or to add the haze afterwards from the depth pass)
for l_ in list(hv.inputs["Density"].links):
    hnt.links.remove(l_)
hv.inputs["Density"].default_value = float(LAYOUT.get("haze", 0.00014))
hv.inputs["Color"].default_value = (1.0, 0.93, 0.83, 1)
hv.inputs["Anisotropy"].default_value = 0.35
haze.hide_render = ARGS.get("--haze", "1") == "0"


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
pv.inputs["Density"].default_value = 0.012
pv.inputs["Anisotropy"].default_value = 0.6
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
DESK = tag(spawn("wooden_table_02", R, loc=(WIN["x"], RD / 2 - 0.45, 0))[0], "desk")
desk_top = LIBM["wooden_table_02"]["mx"].z - LIBM["wooden_table_02"]["mn"].z
spawn("vintage_oil_lamp", R, loc=(WIN["x"] - 0.4, RD / 2 - 0.38, desk_top), rz=0.3)
light(R, "POINT", "oil_lamp", 14, (1.0, 0.68, 0.38), (WIN["x"] - 0.4, RD / 2 - 0.38, desk_top + 0.42), size=0.04)
CHESS = tag(spawn("chess_set", R, loc=(WIN["x"] + 0.28, RD / 2 - 0.55, desk_top), rz=0.25)[0], "chess")   # playable on the site
spawn("book_encyclopedia_set_01", R, loc=(WIN["x"] - 0.05, RD / 2 - 0.3, desk_top), rz=0.0)
UKE = tag(spawn("Ukulele_01", R, loc=(-RW / 2 + 0.22, -1.75, 0), rz=-math.pi / 2)[0], "ukulele")
spawn("potted_plant_02", R, loc=(1.6, RD / 2 - 0.35, 0), rz=0.4)
spawn("throw_pillows_01", R, loc=(-RW / 2 + 0.55, 0.1, 0.42), rz=math.pi / 2)
spawn("painted_wooden_chair_01", R, loc=(WIN["x"] + 0.05, RD / 2 - 1.05, 0), rz=math.pi + 0.15)
spawn("Sofa_01", R, loc=(-RW / 2 + 0.48, 0.1, 0), rz=math.pi / 2)
spawn("ArmChair_01", R, loc=(-0.75, -1.15, 0), rz=-math.pi / 2 - 0.45)
spawn("painted_wooden_cabinet", R, loc=(RW / 2 - 0.32, 1.25, 0), rz=-math.pi / 2)
BED = tag(spawn("GothicBed_01", R, loc=(RW / 2 - 1.05, -RD / 2 + 1.15, 0), rz=math.pi)[0], "bed")
_, ns_top = spawn("ClassicNightstand_01", R, loc=(0.75, -RD / 2 + 0.3, 0), rz=math.pi)
spawn("brass_candleholders", R, loc=(0.7, -RD / 2 + 0.3, ns_top), rz=0.0, s=0.45)
spawn("standing_picture_frame_01", R, loc=(0.95, -RD / 2 + 0.36, ns_top), rz=math.pi - 0.3, s=0.8)
CLOCK = tag(spawn("vintage_grandfather_clock_01", R, loc=(-RW / 2 + 0.3, -RD / 2 + 0.35, 0), rz=3 * math.pi / 4)[0], "clock")
spawn("Chandelier_02", R, loc=(0, 0, RH - (LIBM["Chandelier_02"]["mx"].z - LIBM["Chandelier_02"]["mn"].z)))
for i, (x, y) in enumerate(((-0.35, 0.28), (0.35, 0.28), (0, -0.4))):
    light(R, "POINT", "chand%d" % i, 4, (1.0, 0.75, 0.45), (x, y, RH - 0.75), size=0.03)
FR1 = tag(spawn("fancy_picture_frame_01", R, loc=(-RW / 2 + 0.03, -0.35, 1.25), rz=math.pi / 2, s=0.85)[0], "frames")
FR2 = tag(spawn("fancy_picture_frame_02", R, loc=(-RW / 2 + 0.03, 0.75, 1.45), rz=math.pi / 2, s=0.65)[0], "frames")
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


# ================================================================== AKMU content in the room
tag(gram, "gramophone")
tag(next(o for o in R.objects if o.name.startswith("glass")), "window")
ROOM_HOT = {"gramophone": gram, "ukulele": UKE, "desk": DESK, "bed": BED, "clock": CLOCK}
# TV on a low walnut cabinet against the front wall, playing the MV
tvc = tag(empty("tvcab", R, loc=(-1.45, RD / 2 - 0.3, 0), rz=0.0), "tv")
mesh_obj("tvcabinet", bm_box(0.95, 0.45, 0.5), M_WALNUT, R, tvc, loc=(0, 0, 0.25), bevel=0.015)
retro_tv(R, "room_tv", (0, -0.02, 0.5), 0.12, os.path.join(REFS, "mv_paradise_01.jpg"), tvc, s=0.85)
ROOM_HOT["tv"] = tvc
# gilt photo frames with concert and MV photos on the left wall
pf = tag(empty("photoframes", R, loc=(-RW / 2 + 0.02, -1.5, 0), rz=math.pi / 2), "photos")
M_GILT = flat("gilt", (0.75, 0.58, 0.28), rough=0.3, metal=1.0)
for (img, x, z, w_, h_) in (("concert_01.jpg", 0.0, 1.75, 0.64, 0.42), ("mv_paradise_02.jpg", -0.08, 1.18, 0.5, 0.33), ("concert_03.jpg", 0.42, 1.2, 0.3, 0.38)):
    mesh_obj("pframe", bm_box(w_ + 0.08, 0.03, h_ + 0.08), M_GILT, R, pf, loc=(x, -0.015, z), bevel=0.01)
    mesh_obj("photo", bm_plane(w_, h_), image_mat("photo_" + img, os.path.join(REFS, img), rough=0.4), R, pf, loc=(x, -0.032, z), rot=(math.pi / 2, 0, 0))
ROOM_HOT["photos"] = pf
tag(FR1, "photos")
tag(FR2, "photos")
# concert poster beside the window
pst = tag(empty("poster", R, loc=(2.35, RD / 2 - 0.01, 1.55), rz=0.0), "poster")
mesh_obj("pposter", bm_plane(0.6, 0.85), image_mat("poster_img", os.path.join(REFS, "concert_02.png"), rough=0.6), R, pst, loc=(0, -0.005, 0), rot=(math.pi / 2, 0, 0))
for (x, z) in ((-0.27, 0.4), (0.27, 0.4)):
    mesh_obj("pin", bm_sphere(0.012, 8, 4), M_BRASS, R, pst, loc=(x, -0.012, z))
ROOM_HOT["poster"] = pst
# LP crate by the sofa with the album at the front
lpc = tag(empty("lpcrate_room", R, loc=(-2.1, -1.3, 0), rz=-0.6), "records")
for (bx, by, bz, sx_, sy_) in ((0, -0.22, 0.17, 0.42, 0.02), (0, 0.22, 0.17, 0.42, 0.02), (-0.2, 0, 0.17, 0.02, 0.46), (0.2, 0, 0.17, 0.02, 0.46), (0, 0, 0.01, 0.42, 0.46)):
    mesh_obj("crate", bm_box(sx_, sy_, bz * 2 if bz > 0.02 else 0.02), M_WALNUT, R, lpc, loc=(bx, by, bz))
sleeves(R, lpc, 8, COVER, loc=(0, -0.17, 0.02))
ROOM_HOT["records"] = lpc
ROOM_HOT["chess"] = CHESS
# lyric notes on the desk
paper = tag(empty("notes", R, loc=(WIN["x"] - 0.22, RD / 2 - 0.66, desk_top + 0.002), rz=0.25), "desk")
mesh_obj("paper", bm_box(0.21, 0.297, 0.002), flat("paper", (0.95, 0.93, 0.88), rough=0.9), R, paper)
text_obj(R, "소문의 낙원", 0.022, paper, loc=(0, 0.09, 0.003), rot=(0, 0, 0), font=F_KR, extrude=0.0003)
for k in range(8):
    mesh_obj("line", bm_box(0.15 - 0.02 * (k % 3), 0.003, 0.0005), M_INK, R, paper, loc=(-0.01 * (k % 2), 0.05 - 0.022 * k, 0.003))

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
    # light tree for the many small lights, and GPU OIDN fed with albedo and normal passes
    for a, v in (("denoiser", "OPENIMAGEDENOISE"), ("denoising_use_gpu", True), ("use_light_tree", True),
                 ("denoising_input_passes", "RGB_ALBEDO_NORMAL"), ("denoising_prefilter", "ACCURATE")):
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
for _kind in ("OPTIX", "CUDA", "HIP", "METAL"):
    try:
        prefs.compute_device_type = _kind
        prefs.get_devices()
        if any(d.type == _kind for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == _kind
            print("DEVICE", _kind, [d.name for d in prefs.devices if d.use])
            break
    except Exception:
        pass
samples = int(ARGS.get("--samples", 256))
setup(P, samples)
setup(R, int(samples * 1.5))
P.view_settings.exposure = float(LAYOUT.get("exposure", -0.3))
try:
    P.view_settings.look = "AgX - Base Contrast"
except Exception:
    pass
R.view_settings.exposure = 0.85

if ARGS.get("--save"):
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "pitch.blend"))
want = ARGS.get("--frames")

# ================================================================== NIGHT (--time night)
NIGHT = ARGS.get("--time") == "night"
MOON_DIR = Vector((math.cos(math.radians(28)) * math.cos(math.radians(70)), math.cos(math.radians(28)) * math.sin(math.radians(70)), math.sin(math.radians(28))))


def night_world(name, hdr_path, strength, rot=0.0):
    """Moonlit sky: the photographed sky, dimmed, greyed and tinted blue, lights the scene; camera rays
    see a deep blue gradient with stars and a small moon instead."""
    w = bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = node(nt, "ShaderNodeOutputWorld")
    tc = node(nt, "ShaderNodeTexCoord")
    mp = node(nt, "ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, rot)
    env = node(nt, "ShaderNodeTexEnvironment")
    env.image = load_img(hdr_path)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    hs = node(nt, "ShaderNodeHueSaturation")
    hs.inputs["Saturation"].default_value = 0.25
    nt.links.new(env.outputs["Color"], hs.inputs["Color"])
    mx, ta, tb, tout = mix_rgb(nt, "MULTIPLY")
    nt.links.new(hs.outputs["Color"], ta)
    tb.default_value = (0.45, 0.6, 1.0, 1)
    bg = node(nt, "ShaderNodeBackground")
    nt.links.new(tout, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    # what the camera sees: horizon glow fading to a deep zenith
    sep = node(nt, "ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = node(nt, "ShaderNodeValToRGB")
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.05, 0.07, 0.13, 1)
    cr.elements[1].position, cr.elements[1].color = 0.55, (0.006, 0.011, 0.032, 1)
    cr.elements.new(0.12).color = (0.022, 0.034, 0.075, 1)
    # stars: a few random Voronoi cells, each lit only at its very centre, none below the horizon
    vo = node(nt, "ShaderNodeTexVoronoi")
    vo.inputs["Scale"].default_value = 260
    nt.links.new(tc.outputs["Generated"], vo.inputs["Vector"])
    pick = node(nt, "ShaderNodeSeparateColor")
    nt.links.new(vo.outputs["Color"], pick.inputs["Color"])
    bright = node(nt, "ShaderNodeMapRange", clamp=True)
    nt.links.new(pick.outputs[0], bright.inputs["Value"])
    bright.inputs["From Min"].default_value, bright.inputs["From Max"].default_value = 0.955, 1.0
    bright.inputs["To Max"].default_value = 4.0
    core = node(nt, "ShaderNodeMapRange", clamp=True)
    nt.links.new(vo.outputs["Distance"], core.inputs["Value"])
    core.inputs["From Min"].default_value, core.inputs["From Max"].default_value = 0.0, 0.22
    core.inputs["To Min"].default_value, core.inputs["To Max"].default_value = 1.0, 0.0
    above = node(nt, "ShaderNodeMapRange", clamp=True)
    nt.links.new(sep.outputs["Z"], above.inputs["Value"])
    above.inputs["From Min"].default_value, above.inputs["From Max"].default_value = 0.02, 0.15
    s1 = node(nt, "ShaderNodeMath", operation="MULTIPLY")
    nt.links.new(bright.outputs["Result"], s1.inputs[0])
    nt.links.new(core.outputs["Result"], s1.inputs[1])
    s2 = node(nt, "ShaderNodeMath", operation="MULTIPLY")
    nt.links.new(s1.outputs[0], s2.inputs[0])
    nt.links.new(above.outputs["Result"], s2.inputs[1])
    # the moon: a small bright disc with a soft halo, where the moonlight comes from
    dot = node(nt, "ShaderNodeVectorMath", operation="DOT_PRODUCT")
    nt.links.new(tc.outputs["Generated"], dot.inputs[0])
    dot.inputs[1].default_value = tuple(MOON_DIR)
    disc = node(nt, "ShaderNodeMapRange", clamp=True, interpolation_type="SMOOTHSTEP")
    nt.links.new(dot.outputs["Value"], disc.inputs["Value"])
    disc.inputs["From Min"].default_value, disc.inputs["From Max"].default_value = 0.99984, 0.99988
    disc.inputs["To Max"].default_value = 6.0
    halo = node(nt, "ShaderNodeMapRange", clamp=True)
    nt.links.new(dot.outputs["Value"], halo.inputs["Value"])
    halo.inputs["From Min"].default_value, halo.inputs["From Max"].default_value = 0.985, 1.0
    halo.inputs["To Max"].default_value = 0.12
    hp = node(nt, "ShaderNodeMath", operation="POWER")
    nt.links.new(halo.outputs["Result"], hp.inputs[0])
    hp.inputs[1].default_value = 3.0
    lit = node(nt, "ShaderNodeMath", operation="ADD")
    nt.links.new(s2.outputs[0], lit.inputs[0])
    nt.links.new(disc.outputs["Result"], lit.inputs[1])
    lit2 = node(nt, "ShaderNodeMath", operation="ADD")
    nt.links.new(lit.outputs[0], lit2.inputs[0])
    nt.links.new(hp.outputs[0], lit2.inputs[1])
    add = node(nt, "ShaderNodeVectorMath", operation="ADD")
    nt.links.new(ramp.outputs["Color"], add.inputs[0])
    tint = node(nt, "ShaderNodeVectorMath", operation="SCALE")
    tint.inputs[0].default_value = (0.9, 0.94, 1.0)
    nt.links.new(lit2.outputs[0], tint.inputs["Scale"])
    nt.links.new(tint.outputs["Vector"], add.inputs[1])
    bgc = node(nt, "ShaderNodeBackground")
    nt.links.new(add.outputs["Vector"], bgc.inputs["Color"])
    lp = node(nt, "ShaderNodeLightPath")
    ms = node(nt, "ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], ms.inputs[0])
    nt.links.new(bg.outputs[0], ms.inputs[1])
    nt.links.new(bgc.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], out.inputs["Surface"])
    return w


def set_sky(scene):
    """Day sky and sun, or the night sky and the moon, for the paradise (the room keeps its own world)."""
    if NIGHT:
        P.world = W_NIGHT
        SUN_P.rotation_euler = MOON_DIR.to_track_quat("Z", "Y").to_euler()
    else:
        P.world = W_DAY
        SUN_P.rotation_euler = Vector(W_DAY["sun_dir"]).to_track_quat("Z", "Y").to_euler()


def bulb(scene, parent, loc, energy, r=0.045, col=(1.0, 0.7, 0.36)):
    """A glowing bulb the camera sees, and a small point light that does the actual lighting."""
    camera_only(mesh_obj("bulb", bm_sphere(r, 12, 6), M_NBULB, scene, parent, loc=loc, smooth_shade=True))
    light(scene, "POINT", "bulbl", energy, col, loc, size=r, parent=parent)


def bulb_string(scene, a, b, n, sag, energy):
    a, b = Vector(a), Vector(b)
    for i in range(n):
        t = (i + 0.5) / n
        p = a.lerp(b, t)
        p.z -= sag * 4 * t * (1 - t)
        bulb(scene, None, tuple(p), energy)


if NIGHT:
    W_NIGHT = night_world("night", os.path.join(ASSETS, "h", SKY), 0.035)
    SUN_P.data.energy, SUN_P.data.color, SUN_P.data.angle = 0.32, (0.62, 0.72, 1.0), math.radians(0.5)
    P.view_settings.exposure = float(LAYOUT.get("exposure", -0.3)) + float(ARGS.get("--night-ev", 1.6))
    M_NBULB = flat("night_bulb", (1, 0.9, 0.7), emit=(1.0, 0.68, 0.32), estr=30)
    # festoon of bulbs across the stage front and out to the teepee and the merch rack
    sm = stage.matrix_world
    pl, pr = sm @ Vector((-X2, FY - 0.03, 0.5 + 4.25)), sm @ Vector((X2, FY - 0.03, 0.5 + 4.25))
    bulb_string(P, pl, pr, 14, 0.55, 3.0)
    bulb_string(P, pr, (13.5, 19.5, gz(13.5, 19.5) + 3.3), 10, 0.8, 3.0)
    bulb_string(P, pl, (-3.4 + 7, -1.3 + 17, gz(3.6, 15.7) + 4.0), 6, 0.4, 3.0)
    bulb_string(P, (7.5, 7.5, gz(7.5, 7.5) + 2.2), (11, 10, gz(11, 10) + 2.1), 8, 0.35, 2.5)
    # a lantern in front of each tent, on the side facing the viewpoint
    for tx, ty in ((12.0, 24.0), (16.5, 27.0), (20.5, 28.5), (25.0, 24.0), (8.5, 28.5), (13.5, 19.5)):
        d = (Vector((C360[0], C360[1])) - Vector((tx, ty))).normalized() * 2.1
        lx, ly = tx + d.x, ty + d.y
        mesh_obj("lantern_post", bm_cyl(0.02, 0.02, 1.1, 8), M_POST, P, None, loc=(lx, ly, gz(lx, ly) + 0.55))
        bulb(P, None, (lx, ly, gz(lx, ly) + 1.18), 18, r=0.07)
    # campfire beside the picnic: a ring of stones, crossed logs, flames and embers
    FX, FY_ = 5.2, -4.8
    fz = gz(FX, FY_)
    fire = empty("campfire", P, loc=(FX, FY_, fz))
    rngf = np.random.default_rng(11)
    M_STONE = flat("fire_stone", (0.09, 0.085, 0.08), rough=0.9)
    for k in range(10):
        a_ = k / 10 * TAU + rngf.uniform(-0.1, 0.1)
        st_ = mesh_obj("stone", bm_sphere(0.12, 12, 6), M_STONE, P, fire, loc=(0.5 * math.cos(a_), 0.5 * math.sin(a_), 0.03), rot=(0, 0, a_), smooth_shade=True)
        st_.scale = (rngf.uniform(1.0, 1.4), rngf.uniform(0.7, 0.95), rngf.uniform(0.4, 0.55))
    # charred logs leaning into a cone; only their tips glow, as embers
    M_LOG, nt, b = new_mat("fire_log")
    setin(b, "Base Color", (0.07, 0.045, 0.03, 1))
    setin(b, "Roughness", 0.9)
    tcl, sepl = node(nt, "ShaderNodeTexCoord"), node(nt, "ShaderNodeSeparateXYZ")
    nt.links.new(tcl.outputs["Generated"], sepl.inputs[0])
    tip = node(nt, "ShaderNodeMapRange", clamp=True)
    nt.links.new(sepl.outputs["Z"], tip.inputs["Value"])
    tip.inputs["From Min"].default_value, tip.inputs["From Max"].default_value = 0.82, 1.0
    tip.inputs["To Max"].default_value = 0.5
    setin(b, "Emission Color", (1.0, 0.4, 0.05, 1))
    nt.links.new(tip.outputs["Result"], b.inputs["Emission Strength"])
    for k in range(5):
        a_ = k / 5 * TAU + 0.3
        mesh_obj("log", bm_cyl(0.05, 0.04, 0.62, 10), M_LOG, P, fire, loc=(0.24 * math.cos(a_), 0.24 * math.sin(a_), 0.12),
                 rot=(0.0, -math.radians(64), a_), smooth_shade=True)
    # glowing ember bed in the middle
    M_EMBER = flat("ember", (0.05, 0.02, 0.01), rough=0.8, emit=(1.0, 0.42, 0.06), estr=1.0)
    for k in range(14):
        r_, a_ = 0.16 * math.sqrt(rngf.uniform()), rngf.uniform(0, TAU)
        mesh_obj("ember", bm_sphere(rngf.uniform(0.015, 0.028), 8, 4), M_EMBER, P, fire, loc=(r_ * math.cos(a_), r_ * math.sin(a_), 0.02), smooth_shade=True)

    def flame_mat(name, bottom, top, strength):
        """Emission that runs from a hot base to a deep red tip and thins out to nothing at the top and edges."""
        m, nt, _ = new_mat(name)
        nt.nodes.remove(nt.nodes["Principled BSDF"])
        tc, sp = node(nt, "ShaderNodeTexCoord"), node(nt, "ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Generated"], sp.inputs[0])
        ramp = node(nt, "ShaderNodeValToRGB")
        nt.links.new(sp.outputs["Z"], ramp.inputs["Fac"])
        ramp.color_ramp.elements[0].color, ramp.color_ramp.elements[1].color = (*bottom, 1), (*top, 1)
        ramp.color_ramp.elements[1].position = 0.85
        em = node(nt, "ShaderNodeEmission")
        nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
        em.inputs["Strength"].default_value = strength
        fade = node(nt, "ShaderNodeMapRange", clamp=True, interpolation_type="SMOOTHSTEP")
        nt.links.new(sp.outputs["Z"], fade.inputs["Value"])
        fade.inputs["From Min"].default_value, fade.inputs["From Max"].default_value = 0.08, 0.85
        fade.inputs["To Min"].default_value, fade.inputs["To Max"].default_value = 1.0, 0.0
        lw = node(nt, "ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.55
        edge = node(nt, "ShaderNodeMath", operation="SUBTRACT")
        edge.inputs[0].default_value = 1.0
        nt.links.new(lw.outputs["Facing"], edge.inputs[1])
        alpha = node(nt, "ShaderNodeMath", operation="MULTIPLY", use_clamp=True)
        nt.links.new(fade.outputs["Result"], alpha.inputs[0])
        nt.links.new(edge.outputs[0], alpha.inputs[1])
        mix = node(nt, "ShaderNodeMixShader")
        nt.links.new(alpha.outputs[0], mix.inputs[0])
        nt.links.new(node(nt, "ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
        return m

    M_FLAME = flame_mat("flame", (1.0, 0.62, 0.14), (1.0, 0.24, 0.02), 0.8)
    M_FLAME2 = flame_mat("flame_core", (1.0, 0.8, 0.4), (1.0, 0.5, 0.08), 1.1)
    # licking tongues: thin, twisted, leaning a little, of different heights around a short bright core;
    # spread apart, since every layer a ray passes through adds its glow
    for k in range(6):
        a_ = k / 6 * TAU + rngf.uniform(-0.3, 0.3)
        r_ = 0.0 if k == 0 else rngf.uniform(0.08, 0.15)
        h_ = (0.95 if k == 0 else rngf.uniform(0.5, 0.8))
        ph = rngf.uniform(0, TAU)
        prof = [(0.0, 0.0), (0.09, 0.06), (0.085, 0.22), (0.055, 0.5), (0.02, 0.82), (0.0, 1.0)]
        fl_ = mesh_obj("flame", bm_lathe(prof, seg=14, wobble=lambda a, z, ph=ph: 0.35 * math.sin(3 * a + ph + 9 * z) * z), M_FLAME, P, fire,
                       loc=(r_ * math.cos(a_), r_ * math.sin(a_), 0.06), rot=(rngf.uniform(-0.18, 0.18), rngf.uniform(-0.18, 0.18), ph), smooth_shade=True)
        fl_.scale = (1.0, 1.0, h_)
        camera_only(fl_)
    for k in range(1):
        a_ = 0.0
        fl_ = mesh_obj("flame", bm_lathe([(0.0, 0.0), (0.12, 0.08), (0.08, 0.45), (0.0, 1.0)], seg=12), M_FLAME2, P, fire,
                       loc=(0.0, 0.0, 0.04), rot=(0, 0, a_), smooth_shade=True)
        fl_.scale = (1.0, 1.0, 0.4)
        camera_only(fl_)
    light(P, "POINT", "fire_l", 22, (1.0, 0.66, 0.3), (FX, FY_, fz + 0.3), size=0.15)
    light(P, "POINT", "fire_low", 5, (1.0, 0.55, 0.2), (FX, FY_, fz + 0.1), size=0.15)

    # room: the outside goes dark and blue, the lamps carry the room
    R.world = night_world("room_night", os.path.join(ASSETS, "h", "rustig_koppie_puresky_8k.hdr"), 0.03)
    SUN_R.data.energy, SUN_R.data.color = 0.22, (0.62, 0.72, 1.0)
    SUN_R.rotation_euler = Vector((MOON_DIR.x, MOON_DIR.y, 0.6)).normalized().to_track_quat("Z", "Y").to_euler()
    R.view_settings.exposure = 0.85 + float(ARGS.get("--room-ev", -0.6))
    for o in R.objects:
        if o.type == "LIGHT" and o.data.type == "POINT":
            o.data.energy *= 1.3
    print("NIGHT on")


def box_blur(a, r):
    for ax in (0, 1):
        c = np.cumsum(np.pad(a, [(r + 1, r) if i == ax else (0, 0) for i in range(a.ndim)], mode="edge"), axis=ax)
        a = (np.take(c, range(2 * r + 1, c.shape[ax]), axis=ax) - np.take(c, range(0, c.shape[ax] - 2 * r - 1), axis=ax)) / (2 * r + 1)
    return a


def film_post(path, pano=False):
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
    a += g.reshape(h, w, 4)[..., :3] * np.array([0.5, 0.36, 0.24], np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    for ch, f in (() if pano else ((0, 1.0009), (2, 0.9991))):
        sx = np.clip(np.rint(cx + (xx - cx) / f), 0, w - 1).astype(int)
        sy = np.clip(np.rint(cy + (yy - cy) / f), 0, h - 1).astype(int)
        a[..., ch] = a[sy, sx, ch]
    r2 = ((xx - cx) / cx) ** 2 * 0.62 + ((yy - cy) / cy) ** 2 * 0.38
    # MV-like haze: warm veil, lifted blacks, a little less saturation
    l2 = (a @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None]
    a = l2 + (a - l2) * 0.94
    # at night only a faint blue lift, or the dark turns to grey
    a = a * 0.96 + np.array([0.01, 0.013, 0.024], np.float32) if NIGHT else a * 0.9 + np.array([0.1, 0.095, 0.08], np.float32)
    if not pano:
        a *= (1 - 0.18 * r2 ** 1.4)[..., None]
    grain = np.random.default_rng(5).normal(0, 1, (h, w, 1)).astype(np.float32)
    if not pano:
        a += grain * (0.006 + 0.006 * (1 - np.clip(lum, 0, 1)))[..., None]
    out = bpy.data.images.new("post", w, h)
    out.pixels.foreach_set(np.dstack([np.clip(a, 0, 1), np.ones((h, w, 1), np.float32)]).ravel())
    out.filepath_raw = path
    out.file_format = "JPEG"
    out.save(quality=92)
    for x in (im, small, out):
        bpy.data.images.remove(x)


def render_window_plate():
    """Linear EXR of the dunes from the paradise scene, shown through the room window at true brightness."""
    path = os.path.join(WORK, "renders", "_window_plate_night.exr" if NIGHT else "_window_plate.exr")
    if not os.path.exists(path):
        set_sky(P)
        # from the meadow north-west of the stage, level, toward the golden bushes and the big dune. The window
        # shows only part of the 40 x 22.5 m plane behind it: seen from R0, eye level falls 68% up the plate and
        # straight ahead 61% across, so the lens is shifted to put the horizon there
        eye = gz(-18, 22) + 3.5
        P.camera = cam(P, "PLATE", (-18, 22, eye), (20, 150, eye), 20)
        P.camera.data.shift_x, P.camera.data.shift_y = -0.1075, -0.101
        r, st = P.render, P.render.image_settings
        keep = (r.resolution_x, r.resolution_y, P.cycles.samples, st.file_format)
        r.resolution_x, r.resolution_y, P.cycles.samples = 1600, 900, 96
        st.file_format = "OPEN_EXR"
        r.filepath = path
        P.view_layers[0].update()
        bpy.ops.render.render(write_still=True, scene=P.name)
        r.resolution_x, r.resolution_y, P.cycles.samples, st.file_format = keep
        prev = bpy.data.images.load(path)   # a JPEG next to it, to check the framing without an EXR viewer
        prev.save_render(path[:-4] + "_preview.jpg", scene=P)
        bpy.data.images.remove(prev)
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


def hot_group(o):
    while o is not None:
        if "hot" in o.keys():
            return o["hot"]
        o = o.parent
    return None


def closeup_cam(scene, name, root, from_pos, lens=35, margin=1.35, room=False, lift=0.35):
    scene.view_layers[0].update()
    objs = [o for o in scene.objects if hot_group(o) == root["hot"]] if "hot" in root.keys() else [root] + list(root.children_recursive)
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type in ("MESH", "FONT") for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2
    size = max((hi - lo).length * 0.5, 0.25)
    d = Vector(from_pos) - c
    d.z = 0
    d.normalize()
    dist = size * margin / math.tan(math.atan(18 / lens))
    pos = c + d * dist + Vector((0, 0, size * lift))
    if room:
        pos.x = max(min(pos.x, RW / 2 - 0.2), -RW / 2 + 0.2)
        pos.y = max(min(pos.y, RD / 2 - 0.2), -RD / 2 + 0.2)
        pos.z = max(min(pos.z, RH - 0.25), 0.4)
    else:
        pos.z = max(pos.z, ground_z(pos.x, pos.y) + 0.8)
    return cam(scene, name, tuple(pos), tuple(c), lens)


def srgb(v):
    return round(255 * (12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055))


ID_COLS = [(1, 0.2, 0), (0, 1, 0.2), (0.2, 0, 1), (1, 1, 0), (0, 1, 1), (1, 0, 1), (1, 0.2, 1), (0.2, 1, 1), (1, 1, 0.2), (0.2, 0.2, 1),
           (0.6, 0.6, 0)]


def render_mask(scene, camob, path, groups):
    m = bpy.data.materials.new("idmask")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out, em, oi = nt.nodes.new("ShaderNodeOutputMaterial"), nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeObjectInfo")
    nt.links.new(oi.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    ids = {}
    for o in bpy.data.objects:
        o.color = (0, 0, 0, 1)
    for o in scene.objects:
        if o.name.startswith("haze") or o.name.startswith("roomhaze"):
            o.hide_render = True
        grp = hot_group(o)
        if grp in groups:
            col = ID_COLS[groups.index(grp)]
            o.color = (*col, 1)
            ids[grp] = [srgb(v) for v in col]
    scene.view_layers[0].material_override = m
    w = bpy.data.worlds.new("black")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0
    scene.world = w
    vs = scene.view_settings
    vs.view_transform, vs.exposure = "Standard", 0.0
    try:
        vs.look = "None"
    except Exception:
        pass
    c = scene.cycles
    c.samples, c.use_denoising, c.use_adaptive_sampling = 1, False, False
    c.filter_width = 0.01
    r = scene.render
    keep = (r.resolution_x, r.resolution_y)
    r.resolution_x, r.resolution_y = keep[0] // 2, keep[1] // 2
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    scene.camera = camob
    r.filepath = path
    scene.view_layers[0].update()
    bpy.ops.render.render(write_still=True, scene=scene.name)
    print("MASK", path)
    return ids


def render_depth(scene, camob, path, far=600.0):
    """Log-encoded distance (white = near, black = sky/far) for the viewer's 2.5D parallax."""
    m = bpy.data.materials.new("depthpass")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out, em, cd = nt.nodes.new("ShaderNodeOutputMaterial"), nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeCameraData")
    a = nt.nodes.new("ShaderNodeMath"); a.operation = "ADD"; a.inputs[1].default_value = 1.0
    lg = nt.nodes.new("ShaderNodeMath"); lg.operation = "LOGARITHM"; lg.inputs[1].default_value = math.e
    dv = nt.nodes.new("ShaderNodeMath"); dv.operation = "DIVIDE"; dv.inputs[1].default_value = math.log(1 + far)
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0; inv.use_clamp = True
    nt.links.new(cd.outputs["View Distance"], a.inputs[0])
    nt.links.new(a.outputs[0], lg.inputs[0])
    nt.links.new(lg.outputs[0], dv.inputs[0])
    nt.links.new(dv.outputs[0], inv.inputs[1])
    nt.links.new(inv.outputs[0], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    scene.view_layers[0].material_override = m
    c = scene.cycles
    c.samples, c.use_denoising, c.use_adaptive_sampling = 4, False, False
    r = scene.render
    r.resolution_x, r.resolution_y = 2048, 1024
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "BW"
    r.image_settings.color_depth = "16"
    scene.camera = camob
    r.filepath = path
    scene.view_layers[0].update()
    bpy.ops.render.render(write_still=True, scene=scene.name)
    print("DEPTH", path)


# ---------------------------------------------------------------- layout file for hand-editing in Blender
# Saves the built paradise as a .blend: every top-level holder is a handle (its height kept relative to
# the ground), each crescent dune gets a handle, and layout_tools.py adds the panel that saves layout.json.
if ARGS.get("--layout-blend"):
    out_blend = os.path.abspath(ARGS["--layout-blend"])
    cd = bpy.data.cameras.new("D0")
    cd.type = "PANO"
    try:
        cd.panorama_type = "EQUIRECTANGULAR"
    except Exception:
        cd.cycles.panorama_type = "EQUIRECTANGULAR"
    cd.clip_start, cd.clip_end = 0.03, 5000
    D0 = link(bpy.data.objects.new("D0", cd), P)
    D0.location = (C360[0], C360[1], gz(*C360) + 1.65)
    D0.rotation_euler = (math.pi / 2, 0, 0)
    D0["viewpoint"] = 1
    P.camera = D0
    for o in layout_holders(P):
        o["layout"] = 1
        o["dz"] = o.location.z - gz(o.location.x, o.location.y)
        o.empty_display_type, o.empty_display_size = "PLAIN_AXES", 1.2
    for i, b in enumerate(TER["barchans"]):
        e = empty("dune_%d" % (i + 1), P, loc=(b["x"], b["y"], gz(b["x"], b["y"]) + 3), rz=math.radians(b["dir"]))
        e.empty_display_type, e.empty_display_size = "ARROWS", 25
        e["dune"] = 1
        e["height"], e["width"] = float(b["height"]), float(b["width"])
        e.id_properties_ui("height").update(min=2.0, max=120.0, description="crest height (m)")
        e.id_properties_ui("width").update(min=10.0, max=300.0, description="half width of the horns (m)")
        e.show_name = True
    ts = empty("terrain_settings", P, loc=(0, 0, -50))
    ts.hide_viewport = True
    for sec, key, label, lo, hi in TR.SLIDERS:
        k = TR.slider_prop(sec, key)
        ts[k] = float(TER[sec] if key is None else TER[sec][key])
        ts.id_properties_ui(k).update(min=lo, max=hi, description=label)
    for kind in ("yellow", "pine"):
        ts[kind + "_density"] = float(TREES[kind]["density"])
        ts.id_properties_ui(kind + "_density").update(min=0.0, max=5.0)
    # tree clusters: a sphere handle per cluster (centre, count, spread) and a hidden template tree to plant from
    for kind, mid in (("yellow", "golden_bush"), ("pine", "pine_tree_lod")):
        for ci, c in enumerate(TREES[kind]["clusters"]):
            e = empty("cluster_%s_%d" % (kind, ci + 1), P, loc=(c["x"], c["y"], gz(c["x"], c["y"]) + 2))
            e.empty_display_type, e.empty_display_size = "SPHERE", max(c["sx"], c["sy"])
            e.show_name = True
            e["cluster"], e["kind"], e["index"] = 1, kind, ci
            for k, v, lo, hi in (("n", c["n"], 0, 80), ("sx", c["sx"], 0.5, 60.0), ("sy", c["sy"], 0.5, 60.0)):
                e[k] = int(v) if k == "n" else float(v)
                e.id_properties_ui(k).update(min=lo, max=hi)
            e["_planted"] = [e.location.x, e.location.y, e["n"], e["sx"], e["sy"], TREES[kind]["density"]]
        tpl = spawn(mid, P, loc=(0, 0, -400), name="template_" + kind)[0]
        L_ = LIBM[mid]
        tpl["pivot"] = [(L_["mn"].x + L_["mx"].x) / 2, (L_["mn"].y + L_["mx"].y) / 2, L_["mn"].z]
        tpl["model_h"] = L_["mx"].z - L_["mn"].z
        for o in [tpl] + list(tpl.children_recursive):
            o.hide_viewport = o.hide_render = True
    ground["grid"] = [GSPEC["x0"], GSPEC["x1"], GSPEC["y0"], GSPEC["y1"], GSPEC["n"]]
    # keep the viewport light: dense grass and reeds render but are not drawn while you arrange things
    for m in ground.modifiers:
        if m.name in ("grass", "bloom", "edge", "shore", "reeds"):
            m.show_viewport = False
    P.objects["haze"].hide_viewport = True
    P["layout_path"], P["script_dir"], P["work"] = LAYOUT_PATH, SCRIPT_DIR, WORK
    # images made in memory would be lost on save; pack just those
    for im in bpy.data.images:
        if im.source == "GENERATED" or (not im.filepath and im.has_data):
            try:
                im.pack()
            except Exception:
                pass
    for w in bpy.data.window_managers[0].windows if bpy.data.window_managers else []:
        w.scene = P
    os.makedirs(os.path.dirname(out_blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=False)
    print("LAYOUT BLEND", out_blend)
    sys.exit(0)

if ARGS.get("--world"):
    import json as _json
    WD = os.path.join(OUTDIR, "world")
    os.makedirs(WD, exist_ok=True)
    only = ARGS.get("--views")
    def pano_cam(scene, name, loc):
        cd = bpy.data.cameras.new(name)
        cd.type = "PANO"
        try:
            cd.panorama_type = "EQUIRECTANGULAR"
        except Exception:
            cd.cycles.panorama_type = "EQUIRECTANGULAR"
        cd.clip_start, cd.clip_end = 0.03, 5000
        ob = bpy.data.objects.new(name, cd)
        ob.location = loc
        ob.rotation_euler = (math.pi / 2, 0, 0)  # image centre looks north (+Y)
        return link(ob, scene)

    ram("scene built")
    D0 = pano_cam(P, "D0", (C360[0], C360[1], gz(*C360) + 1.65))
    R0 = pano_cam(R, "R0", (0.3, -0.2, 1.55))
    PANO_W = int(ARGS.get("--pano", 6144))
    shots = [("R0", R, R0)]
    for k, root in ROOM_HOT.items():
        # the chess set sits low behind the desk chair: look down on it from above the backrest
        shots.append(("R_" + k, R, closeup_cam(R, "R_" + k, root, R0.location, lens=32, room=True, lift=2.2 if k == "chess" else 0.35)))
    shots.append(("D0", P, D0))
    # the TV tower stands between the viewpoint and the merch rack, so that close-up is framed from a little further south
    CLOSE_FROM = {"merch": Vector((7.0, -2.0, D0.location.z))}
    for k, root in DESERT_HOT.items():
        shots.append(("D_" + k, P, closeup_cam(P, "D_" + k, root, CLOSE_FROM.get(k, D0.location), lens=35 if k != "stage" else 28)))
    if NIGHT:
        # a look at the campfire from the viewpoint side, only rendered when asked for (--views D_fire)
        shots.append(("D_fire", P, cam(P, "D_fire", (FX - 1.6, FY_ + 2.4, fz + 1.5), (FX, FY_, fz + 0.3), 45)))
    render_window_plate()
    set_sky(P)
    for name, scene, camob in shots:
        if only and name not in only.split(","):
            continue
        if name == "D_door" and os.path.exists(os.path.join(WD, "R0.jpg")):
            door_view(os.path.join(WD, "R0.jpg"))
        scene.camera = camob
        pano = camob.data.type == "PANO"
        r_ = scene.render
        r_.resolution_x, r_.resolution_y = (PANO_W, PANO_W // 2) if pano else (int(ARGS.get("--w", 1920)), int(ARGS.get("--h", 1080)))
        scene.view_layers[0].update()
        r_.filepath = os.path.join(WD, name + ".jpg")
        bpy.ops.render.render(write_still=True, scene=scene.name)
        if ARGS.get("--post", "1") == "1":
            film_post(r_.filepath, pano=pano)
        print("WROTE", scene.render.filepath)
    if not ARGS.get("--nomask"):
        for sc_ in (P, R):
            sc_.render.resolution_x, sc_.render.resolution_y = PANO_W, PANO_W // 2
        P.objects["lake"]["hot"] = "water"
        ids = {"D0": render_mask(P, D0, os.path.join(WD, "D0_mask.png"), list(DESERT_HOT) + ["water"]),
               "R0": render_mask(R, R0, os.path.join(WD, "R0_mask.png"), list(dict.fromkeys(list(ROOM_HOT) + ["photos", "poster", "window"])))}
        with open(os.path.join(WD, "ids.json"), "w") as f:
            _json.dump(ids, f)
        render_depth(P, D0, os.path.join(WD, "D0_depth.png"))
        render_depth(R, R0, os.path.join(WD, "R0_depth.png"))
    ram("end")
    print("WORLD DONE")
    sys.exit(0)

order = sorted(FRAMES, key=lambda n: FRAMES[n][0] != R)
for name in order:
    scene, mode, camob = FRAMES[name]
    if want and name.split("_")[0] not in want.split(","):
        continue
    room_img = os.path.join(OUTDIR, "F4_room.jpg")
    if name == "F2_door" and os.path.exists(room_img):
        door_view(room_img)
    if scene == P:
        w = w_gold() if mode == "golden" else W_DAY
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
