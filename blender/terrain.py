"""The paradise as pure numpy, shared by the render script (pitch_frames.py) and the Blender layout tools
(layout_tools.py), so the land shaped in the layout file is the land that renders.

The look follows the MV and the Mui Ne reference photos: a lush meadow running down to a calm lake, the camp
on a sand patch behind the stage, a big smooth pale dune spilling to the lake on the west, rolling red
dunes dotted with casuarinas, round sage bushes and golden shrubs to the north and east, low scrubby hills
with wind turbines across the lake, and the sea beyond the dunes to the east.

All tunable values come from the "terrain" section of layout.json; DEFAULT holds the current look.
"""
import math
import numpy as np

GRID = dict(x0=-900.0, x1=900.0, y0=-800.0, y1=900.0, n=1400)   # about 1.3 m per vertex

DEFAULT = {
    "desert_scale": 1.0,
    # the lake south of the viewpoint (2, 4): centre, half lengths, rotation (deg), depth
    "lake": {"x": -40.0, "y": -122.0, "rx": 240.0, "ry": 78.0, "rot": -8.0, "depth": 2.6},
    "island": {"x": 110.0, "y": -152.0, "r": 20.0},
    # a small cove reaching up from the lake toward the stage knoll, where the boat is moored near the viewpoint
    "cove": {"x": -6.0, "y": -36.0, "rx": 9.0, "ry": 20.0, "rot": 15.0},
    "meadow_level": 0.8,       # meadow height above the water
    "hummocks": 9.0,           # how tall the vegetated dunes to the north and east grow
    "far_shore": 22.0,         # height of the low hills across the lake
    "camp": {"x": 17.0, "y": 28.0, "r": 8.0},    # the sand patch under the tents, behind the stage
    # the low rise the stage stands on, so the meadow falls gently away to the lake in front of the viewpoint
    "knoll": {"x": 5.0, "y": 10.0, "rx": 75.0, "ry": 48.0, "height": 2.2},
    "sea": {"coast_x": 560.0},
    "sea_level": -0.6,
    # big smooth dunes: centre, crest height, half width of the horns, direction the slip face opens (deg)
    "barchans": [
        {"x": -270.0, "y": 30.0, "height": 30.0, "width": 120.0, "dir": -40.0},
        {"x": 40.0, "y": 200.0, "height": 32.0, "width": 160.0, "dir": 80.0},    # the MV's big dune behind the stage
    ],
    # kept for older layout files
    "river": {"y": -122.0, "half_width": 78.0},
}


# The terrain values the Blender layout panel shows as sliders: (section, key or None, label, min, max).
# The slider for ("lake", "x") is the property "lake_x" on the terrain_settings object.
SLIDERS = [
    ("desert_scale", None, "사막 넓이 (배율)", 0.6, 2.0),
    ("lake", "x", "호수 중심 동서 (m)", -300.0, 300.0),
    ("lake", "y", "호수 중심 남북 (m)", -320.0, -60.0),
    ("lake", "rx", "호수 반길이 동서 (m)", 40.0, 420.0),
    ("lake", "ry", "호수 반길이 남북 (m)", 20.0, 200.0),
    ("lake", "rot", "호수 기울기 (도)", -90.0, 90.0),
    ("lake", "depth", "호수 깊이 (m)", 0.5, 8.0),
    ("island", "x", "섬 동서 (m)", -400.0, 400.0),
    ("island", "y", "섬 남북 (m)", -400.0, -20.0),
    ("island", "r", "섬 크기 (m, 0 = 없음)", 0.0, 60.0),
    ("cove", "x", "작은 만 동서 (m)", -120.0, 120.0),
    ("cove", "y", "작은 만 남북 (m)", -120.0, 0.0),
    ("cove", "rx", "작은 만 폭 (m, 0 = 없음)", 0.0, 40.0),
    ("cove", "ry", "작은 만 길이 (m)", 0.0, 60.0),
    ("cove", "rot", "작은 만 기울기 (도)", -90.0, 90.0),
    ("meadow_level", None, "초원 높이 (m)", 0.0, 3.0),
    ("knoll", "height", "무대 언덕 높이 (m)", 0.0, 8.0),
    ("knoll", "rx", "무대 언덕 폭 동서 (m)", 10.0, 200.0),
    ("knoll", "ry", "무대 언덕 폭 남북 (m)", 10.0, 200.0),
    ("camp", "x", "캠프 모래 동서 (m)", -100.0, 100.0),
    ("camp", "y", "캠프 모래 남북 (m)", -40.0, 120.0),
    ("camp", "r", "캠프 모래 크기 (m)", 0.0, 40.0),
    ("hummocks", None, "북동쪽 붉은 둔덕 높이 (m)", 0.0, 30.0),
    ("far_shore", None, "호수 건너 언덕 높이 (m)", 0.0, 60.0),
    ("sea", "coast_x", "해안선 동서 (m)", 250.0, 900.0),
    ("sea_level", None, "바다 높이 (m)", -5.0, 0.0),
]


def slider_prop(sec, key):
    return sec if key is None else sec + "_" + key


def params(over=None):
    T = {k: (dict(v) if isinstance(v, dict) else [dict(b) for b in v] if isinstance(v, list) else v) for k, v in DEFAULT.items()}
    for k, v in (over or {}).items():
        if k not in DEFAULT:
            continue   # settings from older terrain versions are ignored
        if isinstance(v, dict) and isinstance(T.get(k), dict):
            T[k].update(v)
        else:
            T[k] = v
    return T


def smooth(x, a, b):
    t = np.clip((np.asarray(x, dtype=np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- numpy gradient noise
def _hash(ix, iy, seed):
    h = (ix * 374761393 + iy * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return h ^ (h >> 16)


def _perlin(x, y, seed):
    ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - ix, y - iy
    u = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
    v = fy * fy * fy * (fy * (fy * 6 - 15) + 10)

    def g(dx, dy, ox, oy):
        a = (_hash(ix + ox, iy + oy, seed) & 1023) * (math.tau / 1024)
        return np.cos(a) * dx + np.sin(a) * dy

    n00, n10 = g(fx, fy, 0, 0), g(fx - 1, fy, 1, 0)
    n01, n11 = g(fx, fy - 1, 0, 1), g(fx - 1, fy - 1, 1, 1)
    a = n00 + (n10 - n00) * u
    b = n01 + (n11 - n01) * u
    return (a + (b - a) * v) * 1.41


def fbm(x, y, freq, octaves, seed, gain=0.5):
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    s, a, f, norm = np.zeros(np.broadcast(x, y).shape), 1.0, freq, 0.0
    for o in range(octaves):
        s = s + _perlin(x * f, y * f, seed + o * 101) * a
        norm += a
        f *= 2.03
        a *= gain
    return s / norm


# ---------------------------------------------------------------- shapes
def _ellipse_dist(x, y, E, wob):
    r = math.radians(E["rot"])
    dx, dy = x - E["x"], y - E["y"]
    u = dx * math.cos(r) + dy * math.sin(r)
    v = -dx * math.sin(r) + dy * math.cos(r)
    q = np.sqrt((u / E["rx"]) ** 2 + (v / E["ry"]) ** 2)
    return (q - 1 + wob) * min(E["rx"], E["ry"])


def lake_dist(x, y, T, parts=False):
    """Signed distance-like value to the lake shore: negative in the water, metres outside it.
    parts=True also returns the open lake's and the cove's own distances (their banks shelve differently)."""
    dl = _ellipse_dist(x, y, T["lake"], fbm(x, y, 1 / 90, 3, 71) * 0.12 + fbm(x, y, 1 / 25, 2, 72) * 0.03)
    C = T["cove"]
    d, dc = dl, np.full(np.shape(dl), 1e4)
    if C["rx"] > 0 and C["ry"] > 0:
        dc = _ellipse_dist(x, y, C, fbm(x, y, 1 / 12, 2, 74) * 0.08)
        k = 6.0   # smooth union, so the cove's banks run into the lake shore without a crease
        h = np.clip(k - np.abs(dl - dc), 0, None) / k
        d = np.minimum(dl, dc) - h * h * k / 4
    I = T["island"]
    di = np.hypot(x - I["x"], y - I["y"]) - I["r"] * (1 + 0.25 * fbm(x, y, 1 / 15, 2, 73))
    d = np.where(di < 0, np.maximum(d, -di), d)   # the island stands out of the water
    return (d, dl, dc) if parts else d


def river_y(x, T):
    """Older code asks for a river centre line; the lake's centre stands in."""
    return np.full(np.shape(x), T["lake"]["y"], dtype=np.float64)


def barchan(x, y, cx, cy, H, W, ang):
    """Crescent dune: gentle windward back, crest, concave slip face, horns pointing downwind."""
    dx, dy = x - cx, y - cy
    ux, uy = np.cos(ang), np.sin(ang)
    s = dx * ux + dy * uy
    t = -dx * uy + dy * ux + 0.06 * W * np.sin(s * 0.045 + cx)
    q = np.clip(np.abs(t) / W, 0, 1)
    ds = s - 0.9 * W * q ** 2
    Hc = H * (1 - q ** 2) ** 0.8
    up = np.maximum(-ds, 0)
    wind = Hc * np.exp(-up / (3.5 * H) - (up / (4.5 * H)) ** 2) * (1 - smooth(up, 3.0 * H, 5.0 * H))   # the long tail ends
    lee = Hc * np.clip(1 - np.maximum(ds, 0) / (2.6 * Hc + 1e-3), 0, 1) ** 1.6
    return np.where(ds < 0, wind, lee)


def barchans(x, y, T):
    if not T["barchans"]:
        return np.zeros(np.shape(x))
    return np.maximum.reduce([barchan(x, y, b["x"], b["y"], b["height"], b["width"], math.radians(b["dir"])) for b in T["barchans"]])


def _parts(x, y, T):
    k = T["desert_scale"]
    ld, ld_open, ld_cove = lake_dist(x, y, T, parts=True)
    C = T["camp"]
    camp_d = np.hypot((x - C["x"]) / 1.25, y - C["y"]) - C["r"]
    # vegetated hummocks to the north and east (and around the far edges), calm near the meadow and the lake
    away = smooth(np.hypot(x - 10, y + 10), 120 * k, 420 * k)
    north_east = np.clip(smooth(y, 20, 160) + smooth(x, 60, 260), 0, 1)
    hum_shape = 0.55 + 0.45 * fbm(x, y, 1 / 70, 4, 11) + 0.35 * np.abs(fbm(x, y, 1 / 30, 3, 12))
    hummocks = T["hummocks"] * np.clip(away * 0.6 + north_east * 0.7, 0, 1) * np.clip(hum_shape, 0, 1.6)
    hummocks = hummocks * smooth(ld, 25, 90)
    # across the lake: low hills with scrub, rising to a skyline for the turbines
    far = T["far_shore"] * smooth(-(y - T["lake"]["y"]), 110, 420) * (0.75 + 0.45 * fbm(x, y, 1 / 260, 4, 13))
    far = far * smooth(ld, 15, 80)
    dune = barchans(x, y, T)
    # the meadow: nearly level, a hair of relief, rising softly to the knoll under the stage
    K = T["knoll"]
    knoll = K["height"] * np.exp(-((x - K["x"]) / K["rx"]) ** 2 - ((y - K["y"]) / K["ry"]) ** 2)
    meadow = T["meadow_level"] + knoll + 0.12 * fbm(x, y, 1 / 18, 3, 14) + 0.25 * fbm(x, y, 1 / 90, 2, 15)
    h = meadow + np.maximum(np.maximum(hummocks, far), dune)
    # the camp: a low, softly rippled sand patch
    camp = 1 - smooth(camp_d, 0, 10)
    h = h + camp * (0.35 + 0.1 * np.sin(x * 0.7 + np.sin(y * 0.3)))
    # lake: shelving shore, flat bed, the island rising out of it
    shore = smooth(ld_open, 0, 22) * smooth(ld_cove, 0, 12)   # long shelving shore on the lake, shorter banks on the cove
    bed = -T["lake"]["depth"] * smooth(-ld, 0, 35)
    h = np.where(ld >= 0, T["meadow_level"] * 0.35 + (h - T["meadow_level"] * 0.35) * shore, bed)
    # the sea to the east: the land falls to a beach and the water
    coast = T["sea"]["coast_x"] * k + 60 * np.sin(y * 0.004) + 30 * fbm(x, y, 1 / 200, 2, 16)
    beach = smooth(x, coast - 140, coast)
    h = h * (1 - beach) + (T["sea_level"] - 3) * smooth(x, coast - 10, coast + 120) + 0.4 * beach * (1 - smooth(x, coast - 10, coast + 120))
    return h, dune, ld, camp, hummocks, far, meadow


def terrain(x, y, T):
    """Height, big-dune height and water mask at (x, y)."""
    h, dune, ld, camp, hum, far, base = _parts(np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64), T)
    water = (ld < 0) * 1.0
    return h, dune, water


def ground_z(x, y, T):
    return float(terrain(np.array(x, dtype=np.float64), np.array(y, dtype=np.float64), T)[0])


def grid_spec(T=None):
    k = (T or DEFAULT)["desert_scale"]
    g = GRID
    return dict(x0=g["x0"] * k, x1=g["x1"] * k, y0=g["y0"], y1=g["y1"] * k, n=int(min(2000, round(g["n"] * k))))


def grid(T=None):
    g = grid_spec(T)
    xs = np.linspace(g["x0"], g["x1"], g["n"] + 1)
    ys = np.linspace(g["y0"], g["y1"], g["n"] + 1)
    return np.meshgrid(xs, ys)


def masks(X, Y, DUNE, LAKE, T):
    """Per-vertex weights the ground shader and the plant scatter read."""
    h, dune, ld, camp, hum, far, base = _parts(X, Y, T)
    patch = 0.5 + 0.5 * fbm(X, Y, 1 / 35, 3, 31)
    big_patch = 0.5 + 0.5 * fbm(X, Y, 1 / 120, 3, 32)
    level = 1 - smooth(h - base, 0.9, 2.5)                          # low, level ground
    meadow = level * smooth(ld, 1.5, 6) * (1 - camp) * (1 - smooth(dune, 0.4, 2.0))
    meadow = meadow * (1 - smooth(np.hypot(X - 10, Y + 10), 220, 330) * (1 - smooth(-(Y - T["lake"]["y"]), 60, 160)))
    coast = T["sea"]["coast_x"] * T["desert_scale"] + 60 * np.sin(Y * 0.004)
    meadow = meadow * (1 - smooth(X, coast - 260, coast - 160))     # the beach stays sand
    meadow = np.clip(meadow * (0.85 + 0.3 * patch), 0, 1)
    red = np.clip(smooth(hum + far, 0.8, 3.5) * (1 - smooth(dune, 1, 4)) + (1 - meadow) * (1 - camp) * 0.5, 0, 1) * (1 - smooth(dune, 2, 6))
    white = smooth(dune, 0.5, 3.0)
    shore = smooth(ld, -1.5, 0.3) * (1 - smooth(ld, 3, 9))
    reeds = (smooth(ld, -12, -4) * (1 - smooth(ld, -1, 0.5))) * np.clip(patch * 1.6 - 0.35, 0, 1)
    I = T["island"]
    reeds = np.maximum(reeds, (1 - smooth(np.hypot(X - I["x"], Y - I["y"]), I["r"] * 0.6, I["r"] * 1.6)) * (ld > -6))
    ld_cove = lake_dist(X, Y, T, parts=True)[2]
    reeds = reeds * (1 - 0.8 * smooth(-ld_cove, 0.5, 3))    # the cove stays mostly open water, a few clumps on its edge
    scrub = np.clip(smooth(hum + far, 1.0, 4.0) * (0.25 + 0.9 * patch) * (0.4 + 0.8 * big_patch), 0, 1) * (1 - white * 0.8)
    out = {
        "meadow": meadow,
        "grass": meadow,      # where grass grows: the meadow, less the clearings around props (clear_masks)
        "red": red,
        "white": white,
        "shore": shore,
        "reeds": reeds,
        "wild": meadow * np.clip(patch * 1.5 - 0.6, 0, 1),
        "edge": np.clip(4 * meadow * (1 - meadow), 0, 1) * (1 - camp),
        "dunefoot": scrub,
        "dunetop": white * (patch > 0.72) * smooth(dune, 4, 10) * 0.6,
        "camp": camp,
    }
    return {k: np.clip(v, 0, 1) for k, v in out.items()}


CLEARED = ("grass", "wild", "edge", "reeds", "shore")


def clear_masks(M, X, Y, spots):
    """Plants cleared in soft circles (x, y, r) or along paths (x0, y0, x1, y1, r): trampled grass under a
    picnic blanket, a gap in the reeds where a boat is moored, a footpath down to it. The ground keeps its
    meadow colour; only the scattered plants go."""
    keep = np.ones(np.shape(X))
    for sp in spots:
        x0, y0, x1, y1, r = sp if len(sp) == 5 else (sp[0], sp[1], sp[0], sp[1], sp[2])
        dx, dy = x1 - x0, y1 - y0
        t = np.clip(((X - x0) * dx + (Y - y0) * dy) / max(dx * dx + dy * dy, 1e-9), 0, 1)
        keep = keep * smooth(np.hypot(X - x0 - t * dx, Y - y0 - t * dy), r, r * 1.6)
    for k in CLEARED:
        M[k] = M[k] * keep
    return M


def prop_clearings(view, boat=None, picnic=None):
    """Clearings that follow the props: the boat's gap in the reeds and a footpath down to it from the
    viewpoint, and trampled grass around the picnic blanket. Positions are (x, y) or None."""
    out = []
    if boat is not None:
        vx, vy = boat[0] - view[0], boat[1] - view[1]
        n = max(math.hypot(vx, vy), 1e-6)
        out += [(boat[0], boat[1], 5.0), (view[0] + vx / n * 5.0, view[1] + vy / n * 5.0, boat[0], boat[1], 1.4)]
    if picnic is not None:
        out.append((picnic[0], picnic[1], 3.5))
    return out


# ---------------------------------------------------------------- tree clusters
# Trees and big shrubs grow in clusters: a centre, how many, and how far they spread (east-west, north-south).
# density multiplies every cluster of that kind. Placement is seeded per cluster, so the Blender layout
# file and the render plant exactly the same trees.
TREES = {
    # golden flowering shrubs, the MV's yellow bushes: dense rounded masses at the meadow's edges
    "yellow": {"name": "golden_%d_%02d", "density": 1.0, "clusters": [
        {"x": -48, "y": 30, "n": 22, "sx": 11, "sy": 4}, {"x": -88, "y": 42, "n": 16, "sx": 9, "sy": 4},
        {"x": -20, "y": 52, "n": 12, "sx": 8, "sy": 3}, {"x": 46, "y": 48, "n": 12, "sx": 9, "sy": 4},
        {"x": 62, "y": 8, "n": 12, "sx": 6, "sy": 7}, {"x": 160, "y": 92, "n": 28, "sx": 26, "sy": 6},
        {"x": 230, "y": -4, "n": 22, "sx": 22, "sy": 6}, {"x": -175, "y": -42, "n": 14, "sx": 16, "sy": 4}]},
    # casuarinas (sea pines): groves on the dunes, a line along the far shore, a few on the island
    "pine": {"name": "pine_%d_%02d", "density": 1.0, "clusters": [
        {"x": 110, "y": -150, "n": 5, "sx": 6, "sy": 5}, {"x": -220, "y": -215, "n": 16, "sx": 45, "sy": 10},
        {"x": 30, "y": -230, "n": 18, "sx": 55, "sy": 10}, {"x": 250, "y": -205, "n": 14, "sx": 40, "sy": 12},
        {"x": 190, "y": 70, "n": 12, "sx": 16, "sy": 10}, {"x": 280, "y": 150, "n": 16, "sx": 22, "sy": 14},
        {"x": 215, "y": 230, "n": 12, "sx": 18, "sy": 10}, {"x": 175, "y": 125, "n": 9, "sx": 14, "sy": 8},
        {"x": -200, "y": -60, "n": 7, "sx": 10, "sy": 6}, {"x": 330, "y": 40, "n": 14, "sx": 20, "sy": 18}]},
}


def trees(over=None):
    """TREES with layout.json's "trees" section laid over it."""
    out = {k: {"name": v["name"], "density": v["density"], "clusters": [dict(c) for c in v["clusters"]]} for k, v in TREES.items()}
    for k, v in (over or {}).items():
        if k in out:
            out[k]["density"] = float(v.get("density", out[k]["density"]))
            if "clusters" in v:
                out[k]["clusters"] = [dict(c) for c in v["clusters"]]
    return out


def cluster_trees(kind, ci, c, density, T):
    """[(name, x, y, rz, u)] for one cluster; u in 0..1 picks the size. Trees that would land in water are skipped."""
    rng = np.random.default_rng(7919 * (ci + 1) + (11 if kind == "yellow" else 23))
    n = int(round(c["n"] * density))
    out = []
    fmt = TREES[kind]["name"]
    for i in range(n):
        x, y = c["x"] + rng.normal(0, c["sx"]), c["y"] + rng.normal(0, c["sy"])
        rz, u = rng.uniform(0, math.tau), rng.uniform()
        if float(terrain(np.array(x), np.array(y), T)[2]) > 0.02:
            continue
        out.append((fmt % (ci + 1, i + 1), float(x), float(y), float(rz), float(u)))
    return out


# ---------------------------------------------------------------- lake surface
def lake_mesh_arrays(T):
    """One sheet at water level over the basin, with the depth below each vertex (0..1 over 3 m) for the shader."""
    L = T["lake"]
    span = max(L["rx"], L["ry"])
    lx = np.linspace(L["x"] - span - 60, L["x"] + span + 60, 260)
    ly = np.linspace(L["y"] - span - 60, L["y"] + span + 60, 260)
    LX, LY = np.meshgrid(lx, ly)
    depth = np.clip(-terrain(LX, LY, T)[0], 0, 3) / 3
    verts = np.stack([LX.ravel(), LY.ravel(), np.zeros(LX.size)], 1).astype(np.float32)
    wi = np.arange(LX.size).reshape(LX.shape)
    quads = np.stack([wi[:-1, :-1], wi[:-1, 1:], wi[1:, 1:], wi[1:, :-1]], -1).reshape(-1, 4)
    return verts, quads, depth.ravel().astype(np.float32)


# ---------------------------------------------------------------- far land
# A coarse skirt around the detailed ground, out to about 12 km: rolling scrubby dunes, the sea to the east.
FAR = dict(x0=-12000.0, x1=12000.0, y0=-9000.0, y1=12000.0, nx=480, ny=420)


def far_desert(X, Y, T):
    g = grid_spec(T)
    cx, cy = np.clip(X, g["x0"], g["x1"]), np.clip(Y, g["y0"], g["y1"])
    edge = terrain(cx, cy, T)[0]
    d = np.hypot(X - cx, Y - cy)
    rolling = 6 + 6 * fbm(X, Y, 1 / 900, 3, 81) + smooth(d, 600, 6000) * (18 + 16 * fbm(X, Y, 1 / 2500, 3, 82))
    coast = T["sea"]["coast_x"] * T["desert_scale"] + 60 * np.sin(Y * 0.004)
    sea = smooth(X, coast, coast + 200)
    far = rolling * (1 - sea) + (T["sea_level"] - 6) * sea
    w = smooth(d, 0, 400)
    z = edge * (1 - w) + far * w
    return np.where(d < 1e-6, edge - 1.5, z)


def far_mesh_arrays(T):
    xs = np.linspace(FAR["x0"], FAR["x1"], FAR["nx"] + 1)
    ys = np.linspace(FAR["y0"], FAR["y1"], FAR["ny"] + 1)
    X, Y = np.meshgrid(xs, ys)
    Z = far_desert(X, Y, T)
    verts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1).astype(np.float32)
    nx, ny = FAR["nx"] + 1, FAR["ny"] + 1
    idx = np.arange(nx * ny).reshape(ny, nx)
    quads = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)
    return verts, quads


def build_far_desert(bpy, scene, T, name="far_desert"):
    """Create or refresh the far land in a Blender scene (bpy passed in, so this module stays importable
    outside Blender). Its scrubby sand fades into the haze with distance in the shader."""
    verts, quads = far_mesh_arrays(T)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(quads.size)
    me.loops.foreach_set("vertex_index", quads.ravel().astype(np.int32))
    me.polygons.add(len(quads))
    me.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4, dtype=np.int32))
    me.update(calc_edges=True)
    me.shade_smooth()
    ob = scene.objects.get(name)
    if ob is not None:
        old = ob.data
        for m in old.materials:
            me.materials.append(m)
        ob.data = me
        bpy.data.meshes.remove(old)
        return ob
    m = bpy.data.materials.new("far_sand")
    m.use_nodes = True
    nt = m.node_tree
    # find nodes by type: a Blender running in Korean names its default nodes in Korean
    b = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    b.inputs["Roughness"].default_value = 0.95
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.006
    nz.inputs["Detail"].default_value = 4
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    tone = nt.nodes.new("ShaderNodeMix")   # red sand and dark scrub, mottled
    tone.data_type = "RGBA"
    tone.inputs[6].default_value = (0.62, 0.42, 0.28, 1)
    tone.inputs[7].default_value = (0.24, 0.27, 0.16, 1)
    nt.links.new(nz.outputs["Fac"], tone.inputs[0])
    cam = nt.nodes.new("ShaderNodeCameraData")
    fog = nt.nodes.new("ShaderNodeMapRange")
    fog.interpolation_type = "SMOOTHSTEP"
    fog.inputs["From Min"].default_value, fog.inputs["From Max"].default_value = 800.0, 12000.0
    fog.inputs["To Min"].default_value, fog.inputs["To Max"].default_value = 0.15, 0.85
    nt.links.new(cam.outputs["View Distance"], fog.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[7].default_value = (0.8, 0.76, 0.7, 1)
    nt.links.new(fog.outputs["Result"], mix.inputs[0])
    nt.links.new(tone.outputs[2], mix.inputs[6])
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    b.inputs["Emission Color"].default_value = (0.8, 0.76, 0.7, 1)
    em = nt.nodes.new("ShaderNodeMath")
    em.operation = "MULTIPLY"
    em.inputs[1].default_value = 0.5
    nt.links.new(fog.outputs["Result"], em.inputs[0])
    nt.links.new(em.outputs[0], b.inputs["Emission Strength"])
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob
