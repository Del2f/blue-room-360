"""Paradise layout tools: a sidebar panel (N > 낙원 배치) for shaping the 360 scene by hand, with Claude.

Opened by open_layout.cmd, which runs:  blender paradise_layout.blend --python layout_tools.py
The .blend is made by:  pitch_frames.py ... --layout-blend <file>

- Every prop, tent, tree and turbine is one handle; clicking any part of it selects the whole thing.
  Moving it keeps it seated on the ground (G Z still lifts or sinks it on purpose).
- Dunes are arrow handles, tree clusters are sphere handles; the lake, the stage knoll, the camp sand and the
  sea are sliders (terrain.SLIDERS).
  지형 다시 만들기 / 나무 다시 심기 apply them.
- 배치 저장 writes layout.json, which the final render reads (only what differs from the code's
  defaults is kept per object). When Claude edits layout.json, it is pulled in automatically, or waits
  for a click if you have unsaved moves.
- 실시간 연결: runs command files Claude drops into blender/live/inbox and writes the result and a
  viewport capture to blender/live/outbox, so Claude can see what it changed.
"""
import bpy, importlib, io, json, math, os, sys, time, traceback
from contextlib import redirect_stdout
import numpy as np
from bpy.app.handlers import persistent
from mathutils import Euler, Vector

SCENE = "PARADISE"


def P():
    return bpy.data.scenes[SCENE]


sys.path.insert(0, P()["script_dir"])
import terrain as TR  # noqa: E402
importlib.reload(TR)

LIVE = os.path.join(P()["script_dir"], "live")
PLANT_LAYERS = (("grass", "풀"), ("bloom", "꽃"), ("edge", "초원 가장자리 관목"), ("shore", "물가 식물"), ("reeds", "갈대"),
                ("dunefoot", "사구 아래 관목"), ("dunetop", "사구 위 관목"))
STATE = {"T": None, "dirty": False, "terrain_dirty": False, "trees_dirty": False, "mtime": 0.0, "pending": False,
         "guard": False, "msg": "", "last_live": 0.0}


# ---------------------------------------------------------------- scene access
def handles():
    return [o for o in P().objects if o.get("layout")]


def dunes():
    return sorted([o for o in P().objects if o.get("dune")], key=lambda o: o.name)


def clusters(kind=None):
    cs = [o for o in P().objects if o.get("cluster") and (kind is None or o["kind"] == kind)]
    return sorted(cs, key=lambda o: (o["kind"], o["index"]))


def settings():
    return P().objects["terrain_settings"]


def viewpoint():
    return next(o for o in P().objects if o.get("viewpoint"))


def scatter_node(layer):
    """(modifier, density socket) of one plant layer; the density is the mask multiplier feeding the scatter."""
    m = P().objects["ground"].modifiers.get(layer)
    if m is None or m.node_group is None:
        return None, None
    n = m.node_group.nodes.get("density")
    if n is not None:
        return m, n.inputs[1]
    n = next((n for n in m.node_group.nodes if n.bl_idname == "GeometryNodeDistributePointsOnFaces"), None)
    return m, (n.inputs["Density"] if n is not None else None)


def scene_terrain():
    """Terrain values as the sliders and dune handles stand now."""
    ts = settings()
    over = {}
    for sec, key, _, _, _ in TR.SLIDERS:
        k = TR.slider_prop(sec, key)
        if k not in ts.keys():
            continue
        if key is None:
            over[sec] = float(ts[k])
        else:
            over.setdefault(sec, {})[key] = float(ts[k])
    over["barchans"] = [{"x": d.location.x, "y": d.location.y, "height": d["height"], "width": d["width"],
                         "dir": math.degrees(d.rotation_euler.z)} for d in dunes()]
    return TR.params(over)


def gz(x, y):
    return TR.ground_z(x, y, STATE["T"])


def say(msg):
    STATE["msg"] = msg
    print("[낙원 배치]", msg)
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == "VIEW_3D":
                a.tag_redraw()


def seat(o):
    """Put a handle back on the ground at its own height offset."""
    STATE["guard"] = True
    try:
        x, y = o.location.x, o.location.y
        o.location.z = gz(x, y) + o.get("dz", 0.0)
        o["_xy"] = (round(x, 4), round(y, 4))
    finally:
        STATE["guard"] = False


def remove_tree(o):
    for c in list(o.children_recursive) + [o]:
        bpy.data.objects.remove(c)


# ---------------------------------------------------------------- terrain rebuild
def make_ground_mesh(T):
    """New grid mesh for a new desert size; the ground object keeps its materials and plant modifiers."""
    g = TR.grid_spec(T)
    n = g["n"]
    X, Y = TR.grid(T)
    verts = np.stack([X.ravel(), Y.ravel(), np.zeros(X.size)], 1).astype(np.float32)
    idx = np.arange((n + 1) * (n + 1)).reshape(n + 1, n + 1)
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
    ground = P().objects["ground"]
    old = ground.data
    for m in old.materials:
        me.materials.append(m)
    ground.data = me
    bpy.data.meshes.remove(old)
    ground["grid"] = [g["x0"], g["x1"], g["y0"], g["y1"], g["n"]]


def make_lake_mesh(T):
    """The water sheet follows the lake's place and size; the lake object keeps its material."""
    verts, quads, depth = TR.lake_mesh_arrays(T)
    me = bpy.data.meshes.new("lake")
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(quads.size)
    me.loops.foreach_set("vertex_index", quads.ravel().astype(np.int32))
    me.polygons.add(len(quads))
    me.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4, dtype=np.int32))
    me.update(calc_edges=True)
    me.attributes.new("depth", "FLOAT", "POINT").data.foreach_set("value", depth)
    lake = P().objects["lake"]
    old = lake.data
    for m in old.materials:
        me.materials.append(m)
    lake.data = me
    bpy.data.meshes.remove(old)


def rebuild_terrain():
    t0 = time.time()
    T = scene_terrain()
    g = TR.grid_spec(T)
    ground = P().objects["ground"]
    if [round(v, 3) for v in ground.get("grid", [])] != [round(g[k], 3) for k in ("x0", "x1", "y0", "y1", "n")]:
        make_ground_mesh(T)
    X, Y = TR.grid(T)
    Z, DUNE, LAKE = TR.terrain(X, Y, T)
    M = TR.masks(X, Y, DUNE, LAKE, T)
    hold = {o.name: o.location for o in handles() if o.name in ("boat", "picnic")}
    vp = viewpoint().location
    TR.clear_masks(M, X, Y, TR.prop_clearings((vp.x, vp.y), *[(hold[k].x, hold[k].y) if k in hold else None for k in ("boat", "picnic")]))
    me = ground.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    co[:, 2] = Z.ravel()
    me.vertices.foreach_set("co", co.ravel())
    for k, v in M.items():
        if k not in me.attributes:
            me.attributes.new(k, "FLOAT", "POINT")
        me.attributes[k].data.foreach_set("value", v.ravel().astype(np.float32))
    me.update()
    make_lake_mesh(T)
    sea = P().objects["sea"]
    sea.location.x = T["sea"]["coast_x"] * T["desert_scale"] + 8000
    sea.location.z = T["sea_level"]
    TR.build_far_desert(bpy, P(), T)
    STATE["T"] = T
    for o in handles():
        seat(o)
    STATE["guard"] = True
    try:
        for d in dunes() + clusters():
            d.location.z = gz(d.location.x, d.location.y) + (3 if d.get("dune") else 2)
        vp = viewpoint()
        vp.location.z = gz(vp.location.x, vp.location.y) + 1.65
    finally:
        STATE["guard"] = False
    STATE["terrain_dirty"] = False
    say("지형을 다시 만들었습니다 (%.1f초)" % (time.time() - t0))


# ---------------------------------------------------------------- tree clusters
def cluster_dict(c):
    return {"x": round(c.location.x, 3), "y": round(c.location.y, 3), "n": int(c["n"]), "sx": round(float(c["sx"]), 3), "sy": round(float(c["sy"]), 3)}


def deep_copy(src, parent=None):
    c = src.copy()
    P().collection.objects.link(c)
    c.parent = parent
    if parent is not None:
        c.matrix_parent_inverse = src.matrix_parent_inverse.copy()
    c.hide_viewport = c.hide_render = False
    for ch in src.children:
        deep_copy(ch, c)
    return c


def plant_cluster(c):
    kind, ci = c["kind"], c["index"]
    prefix = TR.TREES[kind]["name"].split("%")[0] + "%d_" % (ci + 1)
    for o in [o for o in handles() if o.name.startswith(prefix)]:
        remove_tree(o)
    tpl = P().objects["template_" + kind]
    dens = float(settings()[kind + "_density"])
    STATE["guard"] = True
    try:
        for nm, x, y, rz, u in TR.cluster_trees(kind, ci, cluster_dict(c), dens, STATE["T"]):
            # same sizes as pitch_frames.py: golden bushes 2.2-3.8 m, casuarinas 8-14 m
            s = ((2.2 + 1.6 * u) if kind == "yellow" else (8 + 6 * u)) / tpl["model_h"]
            sink = 0.15 if kind == "yellow" else 0.3
            h = deep_copy(tpl)
            h.name = nm
            pv = Vector(tpl["pivot"]) * s
            pv.rotate(Euler((0, 0, rz)))
            h.location = Vector((x, y, gz(x, y) - sink)) - pv
            h.rotation_euler = (0, 0, rz)
            h.scale = (s, s, s)
            for k in ("pivot", "model_h"):
                if k in h.keys():
                    del h[k]
            h["layout"] = 1
            h["dz"] = h.location.z - gz(h.location.x, h.location.y)
            h["home"] = [h.location.x, h.location.y, h["dz"], math.degrees(rz), s]
            h["_xy"] = (round(h.location.x, 4), round(h.location.y, 4))
    finally:
        STATE["guard"] = False
    c["_planted"] = [c.location.x, c.location.y, c["n"], c["sx"], c["sy"], dens]


def replant(all_=False):
    t0 = time.time()
    n = 0
    for c in clusters():
        want = [c.location.x, c.location.y, c["n"], c["sx"], c["sy"], float(settings()[c["kind"] + "_density"])]
        if all_ or [round(v, 3) for v in c.get("_planted", [])] != [round(v, 3) for v in want]:
            plant_cluster(c)
            n += 1
    STATE["trees_dirty"] = False
    say("나무 군락 %d개를 다시 심었습니다 (%.1f초)" % (n, time.time() - t0))


def new_cluster(kind, x=0.0, y=40.0):
    idx = 1 + max([c["index"] for c in clusters(kind)] + [-1])
    e = bpy.data.objects.new("cluster_%s_%d" % (kind, idx + 1), None)
    P().collection.objects.link(e)
    e.location = (x, y, gz(x, y) + 2)
    e.empty_display_type, e.empty_display_size = "SPHERE", 6
    e.show_name = True
    e["cluster"], e["kind"], e["index"] = 1, kind, idx
    for k, v, lo, hi in (("n", 8, 0, 80), ("sx", 4.0 if kind == "yellow" else 9.0, 0.5, 60.0), ("sy", 2.5 if kind == "yellow" else 5.0, 0.5, 60.0)):
        e[k] = v
        e.id_properties_ui(k).update(min=lo, max=hi)
    return e


# ---------------------------------------------------------------- layout.json
def layout_path():
    return P()["layout_path"]


def layout_dict():
    T = STATE["T"]
    objs = {}
    for o in sorted(handles(), key=lambda o: o.name):
        x, y = o.location.x, o.location.y
        cur = [x, y, o.location.z - gz(x, y), math.degrees(o.rotation_euler.z), o.scale.x]
        home = list(o.get("home", []))
        tol = (0.005, 0.005, 0.005, 0.05, 0.0005)
        if len(home) == 5 and all(abs(a - b) <= t for a, b, t in zip(cur, home, tol)):
            continue   # still where the code puts it
        objs[o.name] = {"x": round(cur[0], 3), "y": round(cur[1], 3), "dz": round(cur[2], 3), "rz": round(cur[3], 2), "s": round(cur[4], 4)}
    plants = {}
    for layer, _ in PLANT_LAYERS:
        m, n = scatter_node(layer)
        if n is not None:
            plants[layer] = round(n.default_value, 4)
    vp = viewpoint()
    ter = {}
    for sec, key, _, _, _ in TR.SLIDERS:
        if key is None:
            ter[sec] = round(T[sec], 3)
        else:
            ter.setdefault(sec, {})[key] = round(T[sec][key], 3)
    ter["barchans"] = [{k: round(v, 3) for k, v in b.items()} for b in T["barchans"]]
    try:
        with open(layout_path(), encoding="utf-8") as f:
            old = json.load(f)
    except Exception:
        old = {}
    out = {
        "version": 3,
        "note": "Paradise layout. Edited in Blender (layout_tools.py) or by Claude; read by pitch_frames.py.",
        "viewpoint": [round(vp.location.x, 3), round(vp.location.y, 3)],
    }
    for k in ("sky", "sun_az", "haze"):   # look settings live only in the file; keep them
        if k in old:
            out[k] = old[k]
    out.update({
        "terrain": ter,
        "trees": {kind: {"density": round(float(settings()[kind + "_density"]), 3), "clusters": [cluster_dict(c) for c in clusters(kind)]}
                  for kind in ("yellow", "pine")},
        "plants": plants,
        "objects": objs,
    })
    return out


def save_layout():
    if STATE["terrain_dirty"]:
        rebuild_terrain()
    if STATE["trees_dirty"]:
        replant()
    path = layout_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(layout_dict(), f, ensure_ascii=False, indent=1)
    STATE["mtime"] = os.path.getmtime(path)
    STATE["dirty"] = STATE["pending"] = False
    say("배치를 저장했습니다: " + os.path.basename(path))


def load_layout():
    path = layout_path()
    if not os.path.exists(path):
        say("layout.json이 아직 없습니다. 배치 저장을 먼저 누르세요")
        return
    with open(path, encoding="utf-8") as f:
        L = json.load(f)
    STATE["guard"] = True
    try:
        ter = L.get("terrain", {})
        ts = settings()
        Tf = TR.params(ter)   # what the file says, over the code's defaults
        for sec, key, _, _, _ in TR.SLIDERS:
            ts[TR.slider_prop(sec, key)] = float(Tf[sec] if key is None else Tf[sec][key])
        if "barchans" in ter:
            ds = dunes()
            for i, b in enumerate(ter["barchans"]):
                d = ds[i] if i < len(ds) else new_dune("dune_%d" % (i + 1))
                d.location.x, d.location.y = b["x"], b["y"]
                d.rotation_euler.z = math.radians(b["dir"])
                d["height"], d["width"] = float(b["height"]), float(b["width"])
            for d in ds[len(ter["barchans"]):]:
                bpy.data.objects.remove(d)
        for kind, v in L.get("trees", {}).items():
            if kind + "_density" in ts.keys():
                ts[kind + "_density"] = float(v.get("density", ts[kind + "_density"]))
            if "clusters" in v:
                cs = clusters(kind)
                for i, cd in enumerate(v["clusters"]):
                    c = cs[i] if i < len(cs) else new_cluster(kind)
                    c.location.x, c.location.y = cd["x"], cd["y"]
                    c["n"], c["sx"], c["sy"] = int(cd["n"]), float(cd["sx"]), float(cd["sy"])
                for c in cs[len(v["clusters"]):]:
                    prefix = TR.TREES[kind]["name"].split("%")[0] + "%d_" % (c["index"] + 1)
                    for o in [o for o in handles() if o.name.startswith(prefix)]:
                        remove_tree(o)
                    bpy.data.objects.remove(c)
        for layer, dens in L.get("plants", {}).items():
            m, n = scatter_node(layer)
            if n is not None:
                n.default_value = float(dens)
        if "viewpoint" in L:
            vp = viewpoint()
            vp.location.x, vp.location.y = L["viewpoint"]
    finally:
        STATE["guard"] = False
    rebuild_terrain()
    replant()
    missing = []
    STATE["guard"] = True
    try:
        for o in handles():   # back to the code's defaults first, then what the file says
            home = o.get("home")
            if home and o.name not in L.get("objects", {}):
                o.location = (home[0], home[1], gz(home[0], home[1]) + home[2])
                o.rotation_euler.z = math.radians(home[3])
                o.scale = (home[4],) * 3
                o["dz"] = home[2]
                o["_xy"] = (round(home[0], 4), round(home[1], 4))
        for name, v in L.get("objects", {}).items():
            o = P().objects.get(name)
            if o is None or not o.get("layout"):
                missing.append(name)
                continue
            o.location = (v["x"], v["y"], gz(v["x"], v["y"]) + v.get("dz", 0.0))
            o.rotation_euler.z = math.radians(v.get("rz", math.degrees(o.rotation_euler.z)))
            if "s" in v:
                o.scale = (v["s"],) * 3
            o["dz"] = v.get("dz", 0.0)
            o["_xy"] = (round(v["x"], 4), round(v["y"], 4))
    finally:
        STATE["guard"] = False
    STATE["mtime"] = os.path.getmtime(path)
    STATE["dirty"] = STATE["pending"] = False
    say("layout.json을 불러왔습니다" + (" (없는 물건 %d개: 장면 다시 만들기 필요)" % len(missing) if missing else ""))


def new_dune(name, x=0.0, y=220.0):
    e = bpy.data.objects.new(name, None)
    P().collection.objects.link(e)
    e.location = (x, y, 0)
    e.rotation_euler = (0, 0, math.radians(-90))
    e.empty_display_type, e.empty_display_size = "ARROWS", 25
    e.show_name = True
    e["dune"] = 1
    e["height"], e["width"] = 30.0, 70.0
    e.id_properties_ui("height").update(min=2.0, max=120.0)
    e.id_properties_ui("width").update(min=10.0, max=300.0)
    return e


# ---------------------------------------------------------------- keep handles seated, selection on handles
@persistent
def on_depsgraph(scene, depsgraph):
    if STATE["guard"] or scene.name != SCENE:
        return
    for u in depsgraph.updates:
        if not u.is_updated_transform or not isinstance(u.id, bpy.types.Object):
            continue
        o = bpy.data.objects.get(u.id.name)
        if o is None:
            continue
        if o.get("layout"):
            key = (round(o.location.x, 4), round(o.location.y, 4))
            last = o.get("_xy")
            if last is None or (round(last[0], 4), round(last[1], 4)) != key:
                seat(o)   # moved sideways: follow the ground
            else:
                o["dz"] = o.location.z - gz(*key)   # moved up or down on purpose
            STATE["dirty"] = True
        elif o.get("viewpoint"):
            STATE["dirty"] = True


def same(a, b, nd=3):
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(same(a[k], b[k], nd) for k in a)
    if isinstance(a, (list, tuple)):
        return isinstance(b, (list, tuple)) and len(a) == len(b) and all(same(x, y, nd) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return round(a, nd) == round(b, nd)
    return a == b


def check_pending():
    """Terrain or tree settings that differ from what is built (sliders, handles, typed values)."""
    t_dirty = not same(scene_terrain(), STATE["T"])
    tr_dirty = False
    for c in clusters():
        want = [c.location.x, c.location.y, c["n"], c["sx"], c["sy"], float(settings()[c["kind"] + "_density"])]
        if not same(want, list(c.get("_planted", []))):
            tr_dirty = True
            break
    if t_dirty or tr_dirty:
        STATE["dirty"] = True
    STATE["terrain_dirty"], STATE["trees_dirty"] = t_dirty, tr_dirty


def fix_selection():
    """Clicking a tent pole or a tree leaf selects the whole tent or tree."""
    vl = P().view_layers[0]
    try:
        sel = bpy.context.selected_objects
    except Exception:
        return
    for o in sel:
        if o.get("layout") or o.get("dune") or o.get("cluster") or o.get("viewpoint") or o.parent is None:
            continue
        top = o
        while top.parent is not None and not top.get("layout"):
            top = top.parent
        if not top.get("layout"):
            continue
        o.select_set(False, view_layer=vl)
        top.select_set(True, view_layer=vl)
        if vl.objects.active == o:
            vl.objects.active = top


# ---------------------------------------------------------------- live link with Claude
def viewport_capture(path):
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == "VIEW_3D":
                reg = next(r for r in a.regions if r.type == "WINDOW")
                with bpy.context.temp_override(window=w, area=a, region=reg):
                    bpy.ops.screen.screenshot_area(filepath=path)
                return True
    return False


def set_view(location, rot_deg=(88, 0, 0), distance=0.02, lens=16, ortho=False):
    """Point the 3D view (used by live commands)."""
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == "VIEW_3D":
                sp = a.spaces.active
                r3d = sp.region_3d
                r3d.view_perspective = "ORTHO" if ortho else "PERSP"
                r3d.view_location = location
                r3d.view_distance = distance
                r3d.view_rotation = Euler([math.radians(v) for v in rot_deg]).to_quaternion()
                sp.lens, sp.clip_start, sp.clip_end = lens, 0.01, 12000
                a.tag_redraw()


def preview_render(path, width=2048, samples=32):
    """Blocking Cycles render of the 360 view to a file (used by live commands)."""
    sc = P()
    if STATE["terrain_dirty"]:
        rebuild_terrain()
    if STATE["trees_dirty"]:
        replant()
    keep = (sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples, sc.render.filepath)
    sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples = width, width // 2, samples
    sc.camera = viewpoint()
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples, sc.render.filepath = keep


def run_live():
    inbox = os.path.join(LIVE, "inbox")
    os.makedirs(inbox, exist_ok=True)
    os.makedirs(os.path.join(LIVE, "outbox"), exist_ok=True)
    cmds = sorted(f for f in os.listdir(inbox) if f.endswith(".py"))
    if not cmds:
        return
    name = cmds[0]
    src = os.path.join(inbox, name)
    out = os.path.join(LIVE, "outbox", name[:-3])
    code = open(src, encoding="utf-8").read()
    os.remove(src)
    buf = io.StringIO()
    ns = {"bpy": bpy, "P": P(), "TR": TR, "np": np, "math": math, "Vector": Vector, "gz": gz, "seat": seat, "handles": handles,
          "dunes": dunes, "clusters": clusters, "settings": settings, "viewpoint": viewpoint, "scatter_node": scatter_node,
          "rebuild_terrain": rebuild_terrain, "replant": replant, "save_layout": save_layout, "load_layout": load_layout,
          "new_dune": new_dune, "new_cluster": new_cluster, "preview_render": preview_render, "set_view": set_view,
          "STATE": STATE, "OUT": out}
    ok = True
    try:
        with redirect_stdout(buf):
            exec(compile(code, name, "exec"), ns)
    except Exception:
        ok = False
        buf.write(traceback.format_exc())
    bpy.context.view_layer.update()
    try:
        viewport_capture(out + ".png")
    except Exception as e:
        buf.write("\n(capture failed: %s)" % e)
    with open(out + ".txt", "w", encoding="utf-8") as f:
        f.write(("OK\n" if ok else "ERROR\n") + buf.getvalue())
    say("Claude 실시간 명령: " + name + ("" if ok else " (오류)"))


# ---------------------------------------------------------------- timer: selection, file watch, live link
def tick():
    try:
        fix_selection()
        check_pending()
        path = layout_path()
        if os.path.exists(path):
            m = os.path.getmtime(path)
            if m > STATE["mtime"] + 0.01:
                if STATE["dirty"]:
                    STATE["pending"] = True
                    STATE["mtime"] = m
                    say("Claude가 layout.json을 고쳤습니다. 내 변경을 저장하거나 'Claude 수정 불러오기'를 누르세요")
                elif bpy.context.window_manager.paradise_auto:
                    load_layout()
                    say("Claude가 고친 배치를 자동으로 불러왔습니다")
        if bpy.context.window_manager.paradise_live and time.time() - STATE["last_live"] > 0.5:
            STATE["last_live"] = time.time()
            run_live()
    except Exception:
        traceback.print_exc()
    return 0.4


# ---------------------------------------------------------------- operators
class PARADISE_OT_look(bpy.types.Operator):
    bl_idname = "paradise.look"
    bl_label = "360 시점에서 둘러보기"
    bl_description = "사이트의 360 카메라 자리에 시점을 둡니다. 가운데 마우스 버튼으로 끌면 그 자리에서 둘러봅니다"

    def execute(self, context):
        set_view(viewpoint().location)
        return {"FINISHED"}


class PARADISE_OT_top(bpy.types.Operator):
    bl_idname = "paradise.top"
    bl_label = "위에서 보기"
    bl_description = "사막 전체를 위에서 내려다봅니다"

    def execute(self, context):
        k = settings()["desert_scale"]
        vp = viewpoint().location
        set_view((vp.x + 40, vp.y - 40, 0), rot_deg=(0, 0, 0), distance=900 * k, ortho=True)
        return {"FINISHED"}


class PARADISE_OT_rebuild(bpy.types.Operator):
    bl_idname = "paradise.rebuild"
    bl_label = "지형 다시 만들기"
    bl_description = "사구 손잡이와 호수·언덕·캠프 모래·바다 값으로 땅을 다시 만들고 물건들을 새 땅에 앉힙니다"

    def execute(self, context):
        rebuild_terrain()
        if STATE["trees_dirty"]:
            replant()
        STATE["dirty"] = True
        return {"FINISHED"}


class PARADISE_OT_replant(bpy.types.Operator):
    bl_idname = "paradise.replant"
    bl_label = "나무 다시 심기"
    bl_description = "옮기거나 값을 바꾼 나무 군락을 새로 심습니다 (군락 안에서 하나씩 옮긴 나무는 새로 놓입니다)"

    def execute(self, context):
        replant()
        STATE["dirty"] = True
        return {"FINISHED"}


class PARADISE_OT_seat(bpy.types.Operator):
    bl_idname = "paradise.seat"
    bl_label = "선택한 물건 땅에 붙이기"
    bl_description = "띄우거나 묻은 높이를 없애고 땅 위에 바로 놓습니다"

    def execute(self, context):
        for o in context.selected_objects:
            if o.get("layout"):
                o["dz"] = 0.0
                seat(o)
        STATE["dirty"] = True
        return {"FINISHED"}


class PARADISE_OT_preview(bpy.types.Operator):
    bl_idname = "paradise.preview"
    bl_label = "미리보기 렌더 (약 30초)"
    bl_description = "사이트와 같은 360 시점으로 빠르게 렌더해 봅니다 (2K, 32샘플)"

    def execute(self, context):
        if STATE["terrain_dirty"]:
            rebuild_terrain()
        if STATE["trees_dirty"]:
            replant()
        sc = P()
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 2048, 1024, 100
        sc.cycles.samples = 32
        sc.camera = viewpoint()
        bpy.ops.render.render("INVOKE_DEFAULT")
        return {"FINISHED"}


class PARADISE_OT_save(bpy.types.Operator):
    bl_idname = "paradise.save"
    bl_label = "배치 저장"
    bl_description = "layout.json에 저장합니다. 최종 렌더는 이 파일을 읽습니다"

    def execute(self, context):
        save_layout()
        return {"FINISHED"}


class PARADISE_OT_load(bpy.types.Operator):
    bl_idname = "paradise.load"
    bl_label = "Claude 수정 불러오기"
    bl_description = "layout.json을 다시 읽습니다. 저장하지 않은 내 변경은 사라집니다"

    def execute(self, context):
        load_layout()
        return {"FINISHED"}


class PARADISE_OT_add(bpy.types.Operator):
    bl_idname = "paradise.add"
    bl_label = "추가"
    what: bpy.props.StringProperty()

    def execute(self, context):
        loc = context.scene.cursor.location
        if self.what == "dune":
            o = new_dune("dune_%d" % (len(dunes()) + 1), loc.x, loc.y)
            STATE["terrain_dirty"] = True
        else:
            o = new_cluster(self.what, loc.x, loc.y)
            STATE["trees_dirty"] = True
        STATE["dirty"] = True
        for s in context.selected_objects:
            s.select_set(False)
        o.select_set(True)
        context.view_layer.objects.active = o
        return {"FINISHED"}


class PARADISE_OT_remove(bpy.types.Operator):
    bl_idname = "paradise.remove"
    bl_label = "선택한 손잡이 지우기"

    def execute(self, context):
        for o in list(context.selected_objects):
            if o.get("dune"):
                bpy.data.objects.remove(o)
                STATE["terrain_dirty"] = True
            elif o.get("cluster"):
                prefix = TR.TREES[o["kind"]]["name"].split("%")[0] + "%d_" % (o["index"] + 1)
                for t in [t for t in handles() if t.name.startswith(prefix)]:
                    remove_tree(t)
                bpy.data.objects.remove(o)
        STATE["dirty"] = True
        return {"FINISHED"}


class PARADISE_OT_pick(bpy.types.Operator):
    bl_idname = "paradise.pick"
    bl_label = "선택"
    name: bpy.props.StringProperty()

    def execute(self, context):
        o = P().objects.get(self.name)
        if o:
            for s in context.selected_objects:
                s.select_set(False)
            o.select_set(True)
            context.view_layer.objects.active = o
        return {"FINISHED"}


# ---------------------------------------------------------------- panel
class PARADISE_PT_panel(bpy.types.Panel):
    bl_space_type, bl_region_type, bl_category, bl_label = "VIEW_3D", "UI", "낙원 배치", "소문의 낙원 배치"

    def draw(self, context):
        lay = self.layout
        wm = context.window_manager
        if STATE["msg"]:
            box = lay.box()
            for line in [STATE["msg"][i:i + 32] for i in range(0, len(STATE["msg"]), 32)]:
                box.label(text=line)
        row = lay.row(align=True)
        row.operator("paradise.look", icon="HIDE_OFF", text="360 시점")
        row.operator("paradise.top", icon="VIEW_ORTHO", text="위에서")
        col = lay.column(align=True)
        col.operator("paradise.preview", icon="RENDER_STILL")
        row = col.row(align=True)
        row.scale_y = 1.4
        row.operator("paradise.save", icon="FILE_TICK", text="배치 저장" + (" *" if STATE["dirty"] else ""))
        if STATE["pending"]:
            col.operator("paradise.load", icon="IMPORT")
        lay.prop(wm, "paradise_auto")
        lay.prop(wm, "paradise_live")

        ob = context.active_object
        box = lay.box()
        if ob is not None and ob.get("layout"):
            box.label(text="선택: " + ob.name, icon="OBJECT_DATA")
            box.prop(ob, "location", index=0, text="동서 (x)")
            box.prop(ob, "location", index=1, text="남북 (y)")
            box.prop(ob, "rotation_euler", index=2, text="방향")
            box.label(text="땅에서 높이: %.2f m" % ob.get("dz", 0.0))
            box.operator("paradise.seat", icon="SNAP_FACE")
        elif ob is not None and ob.get("dune"):
            box.label(text="사구: " + ob.name, icon="EMPTY_ARROWS")
            box.prop(ob, '["height"]', text="높이 (m)")
            box.prop(ob, '["width"]', text="폭 (m)")
            box.prop(ob, "rotation_euler", index=2, text="움푹한 면이 향하는 방향")
            box.operator("paradise.remove", icon="X")
        elif ob is not None and ob.get("cluster"):
            box.label(text="나무 군락: " + ob.name, icon="MESH_UVSPHERE")
            box.prop(ob, '["n"]', text="그루 수")
            box.prop(ob, '["sx"]', text="퍼짐 동서 (m)")
            box.prop(ob, '["sy"]', text="퍼짐 남북 (m)")
            box.operator("paradise.replant", icon="FILE_REFRESH")
            box.operator("paradise.remove", icon="X")
        else:
            box.label(text="물건, 사구 화살표, 나무 군락 구를 클릭하세요")

        ts = settings()
        box = lay.box()
        box.label(text="지형" + ("  (다시 만들기 필요)" if STATE["terrain_dirty"] else ""), icon="MOD_DISPLACE")
        sub = box.column(align=True)
        last = None
        for sec, key, label, _, _ in TR.SLIDERS:
            k = TR.slider_prop(sec, key)
            if k not in ts.keys():
                continue
            if last is not None and sec != last:
                sub = box.column(align=True)   # a small gap between groups (lake, island, knoll ...)
            sub.prop(ts, '["%s"]' % k, text=label)
            last = sec
        box.operator("paradise.rebuild", icon="FILE_REFRESH")
        row = box.row(align=True)
        row.operator("paradise.add", text="사구 추가", icon="ADD").what = "dune"
        sub = box.column(align=True)
        for d in dunes():
            sub.operator("paradise.pick", text="%s  높이 %.0f · 폭 %.0f" % (d.name, d["height"], d["width"])).name = d.name

        box = lay.box()
        box.label(text="나무" + ("  (다시 심기 필요)" if STATE["trees_dirty"] else ""), icon="PARTICLES")
        box.prop(ts, '["yellow_density"]', text="노란 나무 밀도 (배율)")
        box.prop(ts, '["pine_density"]', text="소나무 밀도 (배율)")
        row = box.row(align=True)
        row.operator("paradise.add", text="노란 나무 군락", icon="ADD").what = "yellow"
        row.operator("paradise.add", text="소나무 군락", icon="ADD").what = "pine"
        box.operator("paradise.replant", icon="FILE_REFRESH")

        box = lay.box()
        box.label(text="풀·꽃 밀도 (그루/㎡, 눈 아이콘 = 화면 표시)", icon="PARTICLES")
        for layer, label in PLANT_LAYERS:
            m, n = scatter_node(layer)
            if n is None:
                continue
            row = box.row(align=True)
            row.prop(n, "default_value", text=label)
            row.prop(m, "show_viewport", text="")


CLASSES = (PARADISE_OT_look, PARADISE_OT_top, PARADISE_OT_rebuild, PARADISE_OT_replant, PARADISE_OT_seat, PARADISE_OT_preview,
           PARADISE_OT_save, PARADISE_OT_load, PARADISE_OT_add, PARADISE_OT_remove, PARADISE_OT_pick, PARADISE_PT_panel)


def register():
    bpy.types.WindowManager.paradise_auto = bpy.props.BoolProperty(name="Claude 수정 자동 반영", default=True,
        description="Claude가 layout.json을 고치면 바로 불러옵니다 (저장 안 한 내 변경이 있으면 기다립니다)")
    bpy.types.WindowManager.paradise_live = bpy.props.BoolProperty(name="Claude 실시간 연결", default=True,
        description="Claude가 blender/live/inbox에 넣은 명령을 이 Blender에서 실행하고, 결과와 화면 캡처를 돌려줍니다")
    for c in CLASSES:
        bpy.utils.register_class(c)
    if on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(on_depsgraph)
    bpy.app.timers.register(tick, first_interval=1.0, persistent=True)


def start():
    STATE["T"] = scene_terrain()
    lp = layout_path()
    STATE["mtime"] = os.path.getmtime(lp) if os.path.exists(lp) else 0.0
    for o in handles():
        o["_xy"] = (round(o.location.x, 4), round(o.location.y, 4))
    win = bpy.context.window
    if win is not None:
        win.scene = P()
        for a in win.screen.areas:
            if a.type == "VIEW_3D":
                sp = a.spaces.active
                sp.shading.type = "SOLID"
                sp.shading.color_type = "TEXTURE"
                sp.overlay.show_relationship_lines = False
                sp.show_region_ui = True
    set_view(viewpoint().location)
    if not os.path.exists(lp):
        save_layout()
    os.makedirs(os.path.join(LIVE, "inbox"), exist_ok=True)
    os.makedirs(os.path.join(LIVE, "outbox"), exist_ok=True)
    with open(os.path.join(LIVE, "status.txt"), "w", encoding="utf-8") as f:
        f.write("ready %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    say("준비됐습니다. 물건을 클릭해 G(이동) R(회전)으로 옮기고 '배치 저장'을 누르세요")


if not globals().get("_HOT_RELOAD"):
    register()
    start()


def hot_reload():
    """Swap in an edited layout_tools.py inside a running Blender (used through the live link)."""
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass
    if on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph)
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
