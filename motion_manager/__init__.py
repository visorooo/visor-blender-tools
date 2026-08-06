# SPDX-License-Identifier: GPL-3.0-or-later
"""
Motion Manager for Blender  —  a Cinema 4D "Motion Manager" style easing tool.

Lives in the Graph Editor > N-panel > "Motion Mgr" tab.

v1.1 changes
  - Custom curve is now a single BEZIER SEGMENT (2 keyframes + handles), not an
    arbitrary compositor curve. Applying it writes the 2 handles onto the
    selected segment's endpoints -> SAME keyframe count, no baking.
  - Live preview drawn to look like the real F-curve / motion graph
    (blue curve, orange handles, keyframe dots) instead of the compositor widget.
  - Preset library shows real curve thumbnails.

Target: Blender 5.0+. Install via Preferences > Add-ons > Install from Disk.
"""

bl_info = {
    "name": "Vipz Motion Manager",
    "author": "Vipz",
    "version": (1, 1, 0),
    "blender": (5, 0, 0),
    "location": "Graph Editor > N-Panel > Motion Mgr",
    "description": "C4D Motion Manager style easing presets, ease copy/paste and custom curves.",
    "category": "Animation",
}

import bpy
import os
import json
import math

from bpy.props import (
    EnumProperty, FloatProperty, StringProperty, BoolProperty,
)
from bpy.types import Panel, Operator, PropertyGroup


# ===========================================================================
# Easing math (Penner) — used to draw the preset thumbnails.
# ===========================================================================
PI = math.pi


def _pow_in(t, n): return t ** n
def _pow_out(t, n): return 1.0 - (1.0 - t) ** n
def _pow_inout(t, n):
    return (2 ** (n - 1)) * (t ** n) if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** n) / 2.0


def _sine_in(t): return 1.0 - math.cos((t * PI) / 2.0)
def _sine_out(t): return math.sin((t * PI) / 2.0)
def _sine_inout(t): return -(math.cos(PI * t) - 1.0) / 2.0


def _expo_in(t): return 0.0 if t == 0.0 else 2 ** (10 * t - 10)
def _expo_out(t): return 1.0 if t == 1.0 else 1.0 - 2 ** (-10 * t)
def _expo_inout(t):
    if t == 0.0: return 0.0
    if t == 1.0: return 1.0
    return (2 ** (20 * t - 10)) / 2.0 if t < 0.5 else (2.0 - 2 ** (-20 * t + 10)) / 2.0


def _circ_in(t): return 1.0 - math.sqrt(max(0.0, 1.0 - t * t))
def _circ_out(t): return math.sqrt(max(0.0, 1.0 - (t - 1.0) ** 2))
def _circ_inout(t):
    if t < 0.5: return (1.0 - math.sqrt(max(0.0, 1.0 - (2 * t) ** 2))) / 2.0
    return (math.sqrt(max(0.0, 1.0 - (-2 * t + 2) ** 2)) + 1.0) / 2.0


_C1 = 1.70158
_C3 = _C1 + 1.0
_C2 = _C1 * 1.525
def _back_in(t): return _C3 * t ** 3 - _C1 * t ** 2
def _back_out(t): return 1.0 + _C3 * (t - 1) ** 3 + _C1 * (t - 1) ** 2
def _back_inout(t):
    if t < 0.5: return ((2 * t) ** 2 * ((_C2 + 1) * 2 * t - _C2)) / 2.0
    return ((2 * t - 2) ** 2 * ((_C2 + 1) * (2 * t - 2) + _C2) + 2.0) / 2.0


def _bounce_out(t):
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1: return n1 * t * t
    elif t < 2 / d1:
        t -= 1.5 / d1; return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1; return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1; return n1 * t * t + 0.984375
def _bounce_in(t): return 1.0 - _bounce_out(1.0 - t)
def _bounce_inout(t):
    return (1.0 - _bounce_out(1.0 - 2 * t)) / 2.0 if t < 0.5 else (1.0 + _bounce_out(2 * t - 1)) / 2.0


def _elastic_in(t):
    if t == 0.0: return 0.0
    if t == 1.0: return 1.0
    c4 = (2 * PI) / 3.0
    return -(2 ** (10 * t - 10)) * math.sin((t * 10 - 10.75) * c4)
def _elastic_out(t):
    if t == 0.0: return 0.0
    if t == 1.0: return 1.0
    c4 = (2 * PI) / 3.0
    return (2 ** (-10 * t)) * math.sin((t * 10 - 0.75) * c4) + 1.0
def _elastic_inout(t):
    if t == 0.0: return 0.0
    if t == 1.0: return 1.0
    c5 = (2 * PI) / 4.5
    if t < 0.5: return -(2 ** (20 * t - 10) * math.sin((20 * t - 11.125) * c5)) / 2.0
    return (2 ** (-20 * t + 10) * math.sin((20 * t - 11.125) * c5)) / 2.0 + 1.0


FAMILY_FUNCS = {
    'SINE': (_sine_in, _sine_out, _sine_inout),
    'QUAD': (lambda t: _pow_in(t, 2), lambda t: _pow_out(t, 2), lambda t: _pow_inout(t, 2)),
    'CUBIC': (lambda t: _pow_in(t, 3), lambda t: _pow_out(t, 3), lambda t: _pow_inout(t, 3)),
    'QUART': (lambda t: _pow_in(t, 4), lambda t: _pow_out(t, 4), lambda t: _pow_inout(t, 4)),
    'QUINT': (lambda t: _pow_in(t, 5), lambda t: _pow_out(t, 5), lambda t: _pow_inout(t, 5)),
    'EXPO': (_expo_in, _expo_out, _expo_inout),
    'CIRC': (_circ_in, _circ_out, _circ_inout),
    'BACK': (_back_in, _back_out, _back_inout),
    'BOUNCE': (_bounce_in, _bounce_out, _bounce_inout),
    'ELASTIC': (_elastic_in, _elastic_out, _elastic_inout),
}
FAMILY_LABEL = {
    'SINE': "Sine", 'QUAD': "Quad", 'CUBIC': "Cubic", 'QUART': "Quart",
    'QUINT': "Quint", 'EXPO': "Expo", 'CIRC': "Circ", 'BACK': "Back",
    'BOUNCE': "Bounce", 'ELASTIC': "Elastic",
}
EASE_FAMILIES = ['SINE', 'QUAD', 'CUBIC', 'QUART', 'QUINT', 'EXPO', 'CIRC', 'BACK']
BOUNCE_FAMILIES = ['BOUNCE']
ELASTIC_FAMILIES = ['ELASTIC']
# (label suffix, blender easing enum, func index)
DIRECTIONS = [
    ("In-Out", 'EASE_IN_OUT', 2),
    ("In", 'EASE_IN', 0),
    ("Out", 'EASE_OUT', 1),
]
NATIVE_EASE_TYPES = {'SINE', 'QUAD', 'CUBIC', 'QUART', 'QUINT', 'EXPO', 'CIRC', 'BACK',
                     'BOUNCE', 'ELASTIC'}
EASING_LABEL = {'EASE_IN': "In", 'EASE_OUT': "Out", 'EASE_IN_OUT': "In-Out", 'AUTO': "Auto"}


# ===========================================================================
# Pixel drawing helpers (bottom-up RGBA float buffers for preview icons)
# ===========================================================================
def _dot(px, w, h, x, y, color, r=0):
    for oy in range(-r, r + 1):
        yy = y + oy
        if yy < 0 or yy >= h:
            continue
        base = yy * w
        for ox in range(-r, r + 1):
            xx = x + ox
            if 0 <= xx < w:
                j = (base + xx) * 4
                px[j] = color[0]; px[j + 1] = color[1]; px[j + 2] = color[2]; px[j + 3] = 1.0


def _disc(px, w, h, cx, cy, r, color):
    r2 = r * r
    for oy in range(-r, r + 1):
        yy = cy + oy
        if yy < 0 or yy >= h:
            continue
        base = yy * w
        for ox in range(-r, r + 1):
            if ox * ox + oy * oy <= r2:
                xx = cx + ox
                if 0 <= xx < w:
                    j = (base + xx) * 4
                    px[j] = color[0]; px[j + 1] = color[1]; px[j + 2] = color[2]; px[j + 3] = 1.0


def _line(px, w, h, x0, y0, x1, y1, color, thick=0):
    dx = abs(x1 - x0); dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _dot(px, w, h, x0, y0, color, thick)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy; x0 += sx
        if e2 <= dx:
            err += dx; y0 += sy


# ---- preset thumbnail (small, F-curve styled) ----
def _raster_preset(fn, size=56):
    w = h = size
    bg = (0.145, 0.145, 0.155)
    grid = (0.22, 0.22, 0.24)
    curve = (0.24, 0.55, 0.85)
    px = [0.0] * (w * h * 4)
    for i in range(w * h):
        j = i * 4
        px[j] = bg[0]; px[j + 1] = bg[1]; px[j + 2] = bg[2]; px[j + 3] = 1.0
    for g in (h // 3, 2 * h // 3):
        for x in range(w):
            j = (g * w + x) * 4
            px[j] = grid[0]; px[j + 1] = grid[1]; px[j + 2] = grid[2]
    for g in (w // 3, 2 * w // 3):
        for y in range(h):
            j = (y * w + g) * 4
            px[j] = grid[0]; px[j + 1] = grid[1]; px[j + 2] = grid[2]
    pad = 6
    span = w - 1 - 2 * pad
    hspan = h - 1 - 2 * pad
    prev = None
    steps = w
    for s in range(steps + 1):
        t = s / steps
        v = min(1.3, max(-0.3, fn(t)))
        yf = (v + 0.3) / 1.6
        xi = int(pad + t * span)
        yi = int(pad + yf * hspan)
        if prev is not None:
            _line(px, w, h, prev[0], prev[1], xi, yi, curve, 0)
        prev = (xi, yi)
    return px


# ---- live custom-curve preview (large, motion-graph styled) ----
_LIVE_W = 220
_LIVE_H = 200
_bg_cache = {}


def _live_bg(w, h):
    key = (w, h)
    if key in _bg_cache:
        return _bg_cache[key]
    bg = (0.152, 0.152, 0.160)
    grid = (0.205, 0.205, 0.215)
    px = [0.0] * (w * h * 4)
    for i in range(w * h):
        j = i * 4
        px[j] = bg[0]; px[j + 1] = bg[1]; px[j + 2] = bg[2]; px[j + 3] = 1.0
    for k in range(0, 6):
        gx = int(k / 5 * (w - 1))
        for y in range(h):
            j = (y * w + gx) * 4
            px[j] = grid[0]; px[j + 1] = grid[1]; px[j + 2] = grid[2]
        gy = int(k / 5 * (h - 1))
        for x in range(w):
            j = (gy * w + x) * 4
            px[j] = grid[0]; px[j + 1] = grid[1]; px[j + 2] = grid[2]
    _bg_cache[key] = px
    return px


# template data range used when no real segment is selected
_T_XMIN, _T_XMAX = -0.20, 1.20
_T_YMIN, _T_YMAX = -0.45, 1.45


def _bezier(p0, p1, p2, p3, t):
    mt = 1.0 - t
    a = mt * mt * mt
    b = 3 * mt * mt * t
    c = 3 * mt * t * t
    d = t * t * t
    return (a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
            a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1])


def _frame_bounds(af, av, bf, bv, h1x, h1y, h2x, h2y):
    """Bounding box (with padding) around a real segment + its handles."""
    xs = (af, bf, h1x, h2x)
    ys = (av, bv, h1y, h2y)
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if xmax - xmin < 1e-6:
        xmin -= 0.5; xmax += 0.5
    if ymax - ymin < 1e-6:
        ymin -= 0.5; ymax += 0.5
    px = (xmax - xmin) * 0.14
    py = (ymax - ymin) * 0.20
    return (xmin - px, xmax + px, ymin - py, ymax + py)


def _frac_map(bounds):
    xmin, xmax, ymin, ymax = bounds
    dx = (xmax - xmin) or 1.0
    dy = (ymax - ymin) or 1.0
    return (lambda x: (x - xmin) / dx), (lambda y: (y - ymin) / dy)


def _ref_segment(context):
    """First selected segment: (fc, ia, ib, af, av, bf, bv, h1x, h1y, h2x, h2y) or None."""
    for fc in get_target_fcurves(context):
        kps = fc.keyframe_points
        for i, _ in selected_segments(fc):
            a, b = kps[i], kps[i + 1]
            return (fc, i, i + 1, a.co.x, a.co.y, b.co.x, b.co.y,
                    a.handle_right.x, a.handle_right.y, b.handle_left.x, b.handle_left.y)
    return None


def _compute_draw(context, props, bounds_override=None):
    """Return curve control points as box-fractions (0..1), matching the real
    selected segment when there is one, otherwise the abstract template."""
    ref = _ref_segment(context)
    if ref:
        _fc, _ia, _ib, af, av, bf, bv, h1x, h1y, h2x, h2y = ref
        bounds = bounds_override or _frame_bounds(af, av, bf, bv, h1x, h1y, h2x, h2y)
        fx, fy = _frac_map(bounds)
        cps = []
        for s in range(101):
            t = s / 100.0
            bp = _bezier((af, av), (h1x, h1y), (h2x, h2y), (bf, bv), t)
            cps.append((fx(bp[0]), fy(bp[1])))
        xmin, xmax, ymin, ymax = bounds
        return {
            'real': True, 'ref': ref, 'bounds': bounds,
            'p0': (fx(af), fy(av)), 'p3': (fx(bf), fy(bv)),
            'p1': (fx(h1x), fy(h1y)), 'p2': (fx(h2x), fy(h2y)),
            'cps': cps,
            'base': fy(0.0) if (ymin <= 0.0 <= ymax) else None,
        }
    bounds = bounds_override or (_T_XMIN, _T_XMAX, _T_YMIN, _T_YMAX)
    fx, fy = _frac_map(bounds)
    P0, P3 = (0.0, 0.0), (1.0, 1.0)
    P1 = (props.in_x, props.in_y)
    P2 = (1.0 + props.out_x, 1.0 + props.out_y)
    cps = []
    for s in range(101):
        t = s / 100.0
        bp = _bezier(P0, P1, P2, P3, t)
        cps.append((fx(bp[0]), fy(bp[1])))
    return {
        'real': False, 'ref': None, 'bounds': bounds,
        'p0': (fx(P0[0]), fy(P0[1])), 'p3': (fx(P3[0]), fy(P3[1])),
        'p1': (fx(P1[0]), fy(P1[1])), 'p2': (fx(P2[0]), fy(P2[1])),
        'cps': cps,
        'base': fy(0.0),
    }


def _raster_from_draw(d, w=_LIVE_W, h=_LIVE_H):
    px = list(_live_bg(w, h))
    curve_col = (0.24, 0.55, 0.85)
    handle_col = (0.90, 0.55, 0.16)
    kf_fill = (0.06, 0.06, 0.06)
    kf_ring = (0.82, 0.82, 0.82)
    green = (0.34, 0.55, 0.36)
    pad = 8
    ix0, ix1 = pad, w - 1 - pad
    iy0, iy1 = pad, h - 1 - pad

    def PX(fp):
        return (int(ix0 + fp[0] * (ix1 - ix0)), int(iy0 + fp[1] * (iy1 - iy0)))

    if d['base'] is not None:
        by = int(iy0 + d['base'] * (iy1 - iy0))
        _line(px, w, h, ix0, by, ix1, by, green, 0)

    a = PX(d['p0']); b = PX(d['p1']); c = PX(d['p3']); e = PX(d['p2'])
    _line(px, w, h, a[0], a[1], b[0], b[1], handle_col, 0)
    _line(px, w, h, c[0], c[1], e[0], e[1], handle_col, 0)

    prev = None
    for fp in d['cps']:
        q = PX(fp)
        if prev is not None:
            _line(px, w, h, prev[0], prev[1], q[0], q[1], curve_col, 1)
        prev = q

    _disc(px, w, h, b[0], b[1], 3, handle_col)
    _disc(px, w, h, e[0], e[1], 3, handle_col)
    for kx, ky in (a, c):
        _disc(px, w, h, kx, ky, 4, kf_ring)
        _disc(px, w, h, kx, ky, 2, kf_fill)
    return px


# ===========================================================================
# Previews collection
# ===========================================================================
_pcoll = None
_live_key = None


def _build_previews():
    global _pcoll
    try:
        import bpy.utils.previews
        _pcoll = bpy.utils.previews.new()
    except Exception:
        _pcoll = None
        return
    for fam, funcs in FAMILY_FUNCS.items():
        for name, idx in (("in", 0), ("out", 1), ("inout", 2)):
            try:
                p = _pcoll.new(f"{fam}_{name}")
                p.image_size = (56, 56)
                p.image_pixels_float = _raster_preset(funcs[idx])
            except Exception:
                pass
    try:
        live = _pcoll.new("mm_live")
        live.image_size = (_LIVE_W, _LIVE_H)
        _tmpl = {
            'real': False, 'ref': None, 'bounds': (_T_XMIN, _T_XMAX, _T_YMIN, _T_YMAX),
            'p0': (0.25, 0.30), 'p3': (0.79, 0.70),
            'p1': (0.45, 0.30), 'p2': (0.60, 0.70),
            'cps': [(0.25 + 0.54 * (s / 60.0), 0.30 + 0.40 * (0.5 - 0.5 * math.cos(math.pi * (s / 60.0))))
                    for s in range(61)],
            'base': None,
        }
        live.image_pixels_float = _raster_from_draw(_tmpl)
    except Exception:
        pass


def _preset_icon(fam, easing):
    if _pcoll is None:
        return 0
    name = {'EASE_IN': 'in', 'EASE_OUT': 'out', 'EASE_IN_OUT': 'inout'}.get(easing, 'inout')
    p = _pcoll.get(f"{fam}_{name}")
    return p.icon_id if p else 0


def _refresh_live(context, props):
    """Re-raster the big preview to match the real selected segment (or template)."""
    global _live_key
    if _pcoll is None or "mm_live" not in _pcoll:
        return 0
    override = _ed_bounds if _ed_bounds is not None else None
    d = _compute_draw(context, props, bounds_override=override)
    key = (d['real'],
           round(d['p0'][0], 3), round(d['p0'][1], 3),
           round(d['p1'][0], 3), round(d['p1'][1], 3),
           round(d['p2'][0], 3), round(d['p2'][1], 3),
           round(d['p3'][0], 3), round(d['p3'][1], 3),
           round(d['base'], 3) if d['base'] is not None else None)
    if key != _live_key:
        try:
            _pcoll["mm_live"].image_pixels_float = _raster_from_draw(d)
            _live_key = key
        except Exception:
            pass
    return _pcoll["mm_live"].icon_id


# ===========================================================================
# F-curve targeting (Track Filter)
# ===========================================================================
def get_target_fcurves(context):
    props = context.scene.motion_manager
    if props.filter_channels == 'SELECTED':
        fcurves = list(getattr(context, 'selected_visible_fcurves', None) or [])
    else:
        fcurves = list(getattr(context, 'visible_fcurves', None) or [])
    if not fcurves:
        obj = context.active_object
        if obj and obj.animation_data and obj.animation_data.action:
            try:
                fcurves = list(obj.animation_data.action.fcurves)
            except Exception:
                fcurves = []
    tf = props.filter_transform
    if tf != 'ALL':
        key = {'LOC': 'location', 'ROT': 'rotation', 'SCALE': 'scale'}[tf]
        fcurves = [fc for fc in fcurves if key in fc.data_path]
    return fcurves


def selected_segments(fc):
    kps = fc.keyframe_points
    for i in range(len(kps) - 1):
        if kps[i].select_control_point and kps[i + 1].select_control_point:
            yield i, i + 1


def apply_handles_to_selection(context):
    """Write the current In/Out handle values onto all selected segments (no baking)."""
    props = context.scene.motion_manager
    total = 0
    for fc in get_target_fcurves(context):
        kps = fc.keyframe_points
        segs = list(selected_segments(fc))
        for i, _ in segs:
            a, b = kps[i], kps[i + 1]
            seg_f = b.co.x - a.co.x
            seg_v = b.co.y - a.co.y
            vscale = abs(seg_v) if seg_v != 0 else abs(seg_f)
            a.interpolation = 'BEZIER'
            a.handle_right_type = 'FREE'
            b.handle_left_type = 'FREE'
            a.handle_right.x = a.co.x + props.in_x * props.handle_scale * seg_f
            a.handle_right.y = a.co.y + props.in_y * vscale
            b.handle_left.x = b.co.x + props.out_x * props.handle_scale * seg_f
            b.handle_left.y = b.co.y + props.out_y * vscale
            total += 1
        if segs:
            fc.update()
    return total


# ===========================================================================
# Saved handle presets (4 values) on disk
# ===========================================================================
def _presets_path(create=False):
    d = bpy.utils.user_resource('CONFIG', path="motion_manager", create=create)
    return os.path.join(d, "custom_eases.json")


def _load_saved():
    p = _presets_path()
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _write_saved(data):
    with open(_presets_path(create=True), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


_enum_cache = []


def _saved_items(self, context):
    global _enum_cache
    data = _load_saved()
    items = [(n, n, "") for n in sorted(data.keys())]
    if not items:
        items = [('__NONE__', "(no saved eases)", "")]
    _enum_cache = items
    return _enum_cache


# ===========================================================================
# Properties
# ===========================================================================
class MM_Props(PropertyGroup):
    mode: EnumProperty(name="Mode", default='EASE', items=[
        ('EASE', "Ease", "Standard easing families"),
        ('BOUNCE', "Bounce", "Bounce easing"),
        ('ELASTIC', "Elastic", "Elastic easing"),
    ])
    show_presets: BoolProperty(name="Show Presets", default=True)
    show_tools: BoolProperty(name="Show Tools", default=False)
    live_apply: BoolProperty(
        name="Live Apply", default=True,
        description="Apply to selected segments in real time while dragging handles")

    in_x: FloatProperty(name="In.X", default=0.5)
    in_y: FloatProperty(name="In.Y", default=0.0)
    out_x: FloatProperty(name="Out.X", default=-0.5)
    out_y: FloatProperty(name="Out.Y", default=0.0)
    handle_scale: FloatProperty(name="Handle Scale", default=1.0, min=0.0, max=2.0,
                                description="Multiplier on In.X / Out.X when applying")

    captured_mode: EnumProperty(default='NONE', items=[
        ('NONE', "None", ""), ('HANDLES', "Handles", ""), ('NATIVE', "Native", "")])
    captured_interp: StringProperty(default='BEZIER')
    captured_easing: StringProperty(default='EASE_IN_OUT')
    captured_label: StringProperty(default="nothing captured")

    filter_channels: EnumProperty(name="Channels", default='SELECTED', items=[
        ('SELECTED', "Selected", "Only selected channels"),
        ('VISIBLE', "Visible", "All visible channels")])
    filter_transform: EnumProperty(name="Transform", default='ALL', items=[
        ('ALL', "All", ""), ('LOC', "Loc", ""), ('ROT', "Rot", ""), ('SCALE', "Scale", "")])

    save_name: StringProperty(name="Name", default="MyEase")
    load_choice: EnumProperty(name="Saved", items=_saved_items)


# ===========================================================================
# Operators
# ===========================================================================
def _in_graph_editor(context):
    return context.area is not None and context.area.type == 'GRAPH_EDITOR'


class MM_OT_apply_preset(Operator):
    bl_idname = "mm.apply_preset"
    bl_label = "Apply Ease Preset"
    bl_description = "Apply this easing preset to selected keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    interpolation: StringProperty()
    easing: StringProperty()

    @classmethod
    def poll(cls, context):
        return _in_graph_editor(context)

    def execute(self, context):
        count = 0
        for fc in get_target_fcurves(context):
            touched = False
            for kf in fc.keyframe_points:
                if kf.select_control_point:
                    kf.interpolation = self.interpolation
                    try:
                        kf.easing = self.easing
                    except Exception:
                        pass
                    touched = True
                    count += 1
            if touched:
                fc.update()
        if count == 0:
            self.report({'WARNING'}, "No selected keyframes matched the track filter")
            return {'CANCELLED'}
        self.report({'INFO'}, f"{FAMILY_LABEL.get(self.interpolation, self.interpolation)} "
                              f"{EASING_LABEL.get(self.easing, '')} on {count} keys")
        return {'FINISHED'}


class MM_OT_get_ease(Operator):
    bl_idname = "mm.get_ease"
    bl_label = "Get Ease"
    bl_description = ("Capture the ease from the first selected segment (two adjacent keys). "
                     "Bezier segments fill the handle fields; native eases are stored as-is")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _in_graph_editor(context)

    def execute(self, context):
        props = context.scene.motion_manager
        for fc in get_target_fcurves(context):
            kps = fc.keyframe_points
            for i, _ in selected_segments(fc):
                a, b = kps[i], kps[i + 1]
                if a.interpolation in NATIVE_EASE_TYPES:
                    props.captured_mode = 'NATIVE'
                    props.captured_interp = a.interpolation
                    props.captured_easing = a.easing
                    props.captured_label = (f"{FAMILY_LABEL.get(a.interpolation, a.interpolation)} "
                                            f"{EASING_LABEL.get(a.easing, '')}")
                else:
                    seg_f = b.co.x - a.co.x
                    seg_v = b.co.y - a.co.y
                    if seg_f == 0:
                        continue
                    vscale = abs(seg_v) if seg_v != 0 else 1.0
                    props.in_x = (a.handle_right.x - a.co.x) / seg_f
                    props.in_y = (a.handle_right.y - a.co.y) / vscale
                    props.out_x = (b.handle_left.x - b.co.x) / seg_f
                    props.out_y = (b.handle_left.y - b.co.y) / vscale
                    props.captured_mode = 'HANDLES'
                    props.captured_label = "custom handles"
                self.report({'INFO'}, f"Captured: {props.captured_label}")
                return {'FINISHED'}
        self.report({'WARNING'}, "Select a segment (two adjacent keys) first")
        return {'CANCELLED'}


class MM_OT_set_ease(Operator):
    bl_idname = "mm.set_ease"
    bl_label = "Set Ease"
    bl_description = ("Apply the custom curve / captured ease to selected segments. "
                     "Writes the two endpoint handles only — keyframe count is unchanged")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _in_graph_editor(context)

    def execute(self, context):
        props = context.scene.motion_manager
        count = 0
        for fc in get_target_fcurves(context):
            kps = fc.keyframe_points
            segs = list(selected_segments(fc))
            for i, _ in segs:
                a, b = kps[i], kps[i + 1]
                if props.captured_mode == 'NATIVE':
                    a.interpolation = props.captured_interp
                    try:
                        a.easing = props.captured_easing
                    except Exception:
                        pass
                else:
                    seg_f = b.co.x - a.co.x
                    seg_v = b.co.y - a.co.y
                    vscale = abs(seg_v) if seg_v != 0 else abs(seg_f)
                    a.interpolation = 'BEZIER'
                    a.handle_right_type = 'FREE'
                    b.handle_left_type = 'FREE'
                    a.handle_right.x = a.co.x + props.in_x * props.handle_scale * seg_f
                    a.handle_right.y = a.co.y + props.in_y * vscale
                    b.handle_left.x = b.co.x + props.out_x * props.handle_scale * seg_f
                    b.handle_left.y = b.co.y + props.out_y * vscale
                count += 1
            if segs:
                fc.update()
        if count == 0:
            self.report({'WARNING'}, "Select segments (adjacent key pairs) first")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Set ease on {count} segments")
        return {'FINISHED'}


class MM_OT_reset_curve(Operator):
    bl_idname = "mm.reset_curve"
    bl_label = "Reset"
    bl_description = "Reset the custom curve handles to a symmetric ease"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.motion_manager
        props.in_x, props.in_y, props.out_x, props.out_y = 0.5, 0.0, -0.5, 0.0
        props.captured_mode = 'HANDLES'
        props.captured_label = "custom handles"
        return {'FINISHED'}


class MM_OT_save_curve(Operator):
    bl_idname = "mm.save_curve"
    bl_label = "Save Ease"
    bl_description = "Save the current custom curve handles under a name"

    def execute(self, context):
        props = context.scene.motion_manager
        name = props.save_name.strip()
        if not name:
            self.report({'WARNING'}, "Enter a name first")
            return {'CANCELLED'}
        data = _load_saved()
        data[name] = [props.in_x, props.in_y, props.out_x, props.out_y]
        _write_saved(data)
        self.report({'INFO'}, f"Saved '{name}'")
        return {'FINISHED'}


class MM_OT_load_curve(Operator):
    bl_idname = "mm.load_curve"
    bl_label = "Load Ease"
    bl_description = "Load the selected saved ease into the editor"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.motion_manager
        data = _load_saved()
        name = props.load_choice
        if name not in data:
            self.report({'WARNING'}, "No saved ease selected")
            return {'CANCELLED'}
        v = data[name]
        props.in_x, props.in_y, props.out_x, props.out_y = v[0], v[1], v[2], v[3]
        props.captured_mode = 'HANDLES'
        props.captured_label = f"loaded '{name}'"
        self.report({'INFO'}, f"Loaded '{name}'")
        return {'FINISHED'}


class MM_OT_delete_curve(Operator):
    bl_idname = "mm.delete_curve"
    bl_label = "Delete Ease"
    bl_description = "Delete the selected saved ease"

    def execute(self, context):
        props = context.scene.motion_manager
        data = _load_saved()
        if props.load_choice in data:
            del data[props.load_choice]
            _write_saved(data)
            self.report({'INFO'}, f"Deleted '{props.load_choice}'")
        return {'FINISHED'}


class MM_OT_tool(Operator):
    bl_idname = "mm.tool"
    bl_label = "Motion Tool"
    bl_description = "Run a quick ease utility on selected keys"
    bl_options = {'REGISTER', 'UNDO'}

    action: StringProperty()

    @classmethod
    def poll(cls, context):
        return _in_graph_editor(context)

    def execute(self, context):
        count = 0
        for fc in get_target_fcurves(context):
            kps = fc.keyframe_points
            changed = False
            if self.action in {'LINEAR', 'CONSTANT', 'SMOOTH'}:
                for kf in kps:
                    if not kf.select_control_point:
                        continue
                    if self.action == 'LINEAR':
                        kf.interpolation = 'LINEAR'
                    elif self.action == 'CONSTANT':
                        kf.interpolation = 'CONSTANT'
                    else:
                        kf.interpolation = 'BEZIER'
                        kf.handle_left_type = 'AUTO_CLAMPED'
                        kf.handle_right_type = 'AUTO_CLAMPED'
                    changed = True
                    count += 1
            elif self.action == 'REVERSE':
                for i, _ in selected_segments(fc):
                    a = kps[i]
                    if a.interpolation in NATIVE_EASE_TYPES:
                        a.easing = {'EASE_IN': 'EASE_OUT', 'EASE_OUT': 'EASE_IN'}.get(a.easing, a.easing)
                        changed = True
                        count += 1
            elif self.action == 'MIRROR':
                for i, _ in selected_segments(fc):
                    a, b = kps[i], kps[i + 1]
                    a.interpolation = 'BEZIER'
                    a.handle_right_type = 'FREE'
                    b.handle_left_type = 'FREE'
                    seg_f = b.co.x - a.co.x
                    la = a.co.x - a.handle_left.x
                    rb = b.handle_right.x - b.co.x
                    a.handle_right.x = a.co.x + (rb if rb > 0 else seg_f * 0.33)
                    b.handle_left.x = b.co.x - (la if la > 0 else seg_f * 0.33)
                    changed = True
                    count += 1
            if changed:
                fc.update()
        if count == 0:
            self.report({'WARNING'}, "Nothing to change (check selection / filter)")
            return {'CANCELLED'}
        self.report({'INFO'}, f"{self.action.title()} on {count} keys")
        return {'FINISHED'}


# ===========================================================================
# Interactive handle editor (modal operator + GPU overlay)
# ===========================================================================
_edit_handler = None
_ed_anchor = None
_ed_bounds = None

_ED_PAD = 26


def _ed_rect(region):
    bw = max(240, min(320, region.width - 36))
    bh = 270
    if _ed_anchor is not None:
        x0 = _ed_anchor[0] - bw * 0.5
        y0 = _ed_anchor[1] - bh - 24
    else:
        x0 = (region.width - bw) / 2.0
        y0 = region.height - bh - 70
    x0 = max(8, min(region.width - bw - 8, x0))
    y0 = max(8, min(region.height - bh - 8, y0))
    return (x0, y0, bw, bh)


def _ed_inner(rect):
    x0, y0, bw, bh = rect
    return (x0 + _ED_PAD, x0 + bw - _ED_PAD, y0 + _ED_PAD, y0 + bh - _ED_PAD)


def _ed_frac_px(fp, rect):
    ix0, ix1, iy0, iy1 = _ed_inner(rect)
    return (ix0 + fp[0] * (ix1 - ix0), iy0 + fp[1] * (iy1 - iy0))


def _ed_px_frac(mx, my, rect):
    ix0, ix1, iy0, iy1 = _ed_inner(rect)
    return ((mx - ix0) / (ix1 - ix0), (my - iy0) / (iy1 - iy0))


def _ed_near(mx, my, p, rad=13):
    return (mx - p[0]) ** 2 + (my - p[1]) ** 2 <= rad * rad


def _ed_inside(mx, my, rect):
    x0, y0, bw, bh = rect
    return x0 <= mx <= x0 + bw and y0 <= my <= y0 + bh


def _ed_draw():
    ctx = bpy.context
    region = ctx.region
    if region is None:
        return
    props = ctx.scene.motion_manager
    rect = _ed_rect(region)
    x0, y0, bw, bh = rect
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        import blf

        d = _compute_draw(ctx, props, bounds_override=_ed_bounds)

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        shader.bind()

        def tris(verts, col):
            b = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=[(0, 1, 2), (0, 2, 3)])
            shader.uniform_float("color", col)
            b.draw(shader)

        def lines(pts, col, width=1.0):
            gpu.state.line_width_set(width)
            b = batch_for_shader(shader, 'LINES', {"pos": pts})
            shader.uniform_float("color", col)
            b.draw(shader)

        def strip(pts, col, width=1.0):
            gpu.state.line_width_set(width)
            b = batch_for_shader(shader, 'LINE_STRIP', {"pos": pts})
            shader.uniform_float("color", col)
            b.draw(shader)

        def quad(cx, cy, r, col):
            tris([(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)], col)

        tris([(x0, y0), (x0 + bw, y0), (x0 + bw, y0 + bh), (x0, y0 + bh)], (0.10, 0.10, 0.115, 0.95))
        lines([(x0, y0), (x0 + bw, y0), (x0 + bw, y0), (x0 + bw, y0 + bh),
               (x0 + bw, y0 + bh), (x0, y0 + bh), (x0, y0 + bh), (x0, y0)],
              (0.32, 0.32, 0.34, 1.0), 1.0)

        ix0, ix1, iy0, iy1 = _ed_inner(rect)
        gl = []
        for k in range(5):
            gx = ix0 + (ix1 - ix0) * k / 4.0
            gl += [(gx, iy0), (gx, iy1)]
            gy = iy0 + (iy1 - iy0) * k / 4.0
            gl += [(ix0, gy), (ix1, gy)]
        lines(gl, (0.20, 0.20, 0.225, 1.0), 1.0)

        if d['base'] is not None:
            by = iy0 + d['base'] * (iy1 - iy0)
            lines([(ix0, by), (ix1, by)], (0.34, 0.55, 0.36, 1.0), 1.0)

        p0 = _ed_frac_px(d['p0'], rect)
        p3 = _ed_frac_px(d['p3'], rect)
        p1 = _ed_frac_px(d['p1'], rect)
        p2 = _ed_frac_px(d['p2'], rect)

        lines([p0, p1, p3, p2], (0.90, 0.55, 0.16, 1.0), 1.6)
        strip([_ed_frac_px(fp, rect) for fp in d['cps']], (0.24, 0.55, 0.85, 1.0), 2.5)

        for kp in (p0, p3):
            quad(kp[0], kp[1], 5, (0.85, 0.85, 0.85, 1.0))
            quad(kp[0], kp[1], 3, (0.06, 0.06, 0.06, 1.0))
        for hp in (p1, p2):
            quad(hp[0], hp[1], 5, (0.95, 0.60, 0.16, 1.0))

        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')

        fid = 0
        blf.size(fid, 12)
        blf.color(fid, 0.82, 0.82, 0.82, 1.0)
        blf.position(fid, x0 + 8, y0 + bh + 8, 0)
        blf.draw(fid, "Drag orange handles   |   Enter / click outside: apply   |   Esc: cancel")
        blf.size(fid, 11)
        blf.color(fid, 0.6, 0.6, 0.62, 1.0)
        blf.position(fid, x0 + 8, y0 - 16, 0)
        tag = "selected segment" if d['real'] else "template (nothing selected)"
        blf.draw(fid, f"{tag}    In {props.in_x:.2f},{props.in_y:.2f}  Out {props.out_x:.2f},{props.out_y:.2f}")
    except Exception:
        pass


class MM_OT_edit_curve(Operator):
    bl_idname = "mm.edit_curve"
    bl_label = "Drag Handles"
    bl_description = "Interactively drag the ease handles with the mouse in the graph area"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _in_graph_editor(context)

    def _end(self, context, status):
        global _edit_handler, _ed_bounds, _ed_anchor
        if _edit_handler is not None:
            try:
                bpy.types.SpaceGraphEditor.draw_handler_remove(_edit_handler, 'WINDOW')
            except Exception:
                pass
            _edit_handler = None
        _ed_bounds = None
        _ed_anchor = None
        if context.area:
            context.area.tag_redraw()
        return {status}

    def invoke(self, context, event):
        global _edit_handler, _ed_anchor, _ed_bounds
        props = context.scene.motion_manager
        self._init = (props.in_x, props.in_y, props.out_x, props.out_y)
        self._drag = None
        self._init_ref = None
        _ed_anchor = (event.mouse_region_x, event.mouse_region_y)
        # freeze the view box so it doesn't rescale while dragging
        ref = _ref_segment(context)
        if ref:
            _fc, _ia, _ib, af, av, bf, bv, h1x, h1y, h2x, h2y = ref
            _ed_bounds = _frame_bounds(af, av, bf, bv, h1x, h1y, h2x, h2y)
            self._init_ref = (af, av, bf, bv, h1x, h1y, h2x, h2y)
        else:
            _ed_bounds = (_T_XMIN, _T_XMAX, _T_YMIN, _T_YMAX)
        if _edit_handler is not None:
            try:
                bpy.types.SpaceGraphEditor.draw_handler_remove(_edit_handler, 'WINDOW')
            except Exception:
                pass
            _edit_handler = None
        _edit_handler = bpy.types.SpaceGraphEditor.draw_handler_add(
            _ed_draw, (), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _apply_drag(self, context, props, mx, my, rect):
        fx, fy = _ed_px_frac(mx, my, rect)
        xmin, xmax, ymin, ymax = _ed_bounds
        rx = xmin + fx * (xmax - xmin)
        ry = ymin + fy * (ymax - ymin)
        ref = _ref_segment(context)
        if ref:
            fc, ia, ib, af, av, bf, bv, _h1x, _h1y, _h2x, _h2y = ref
            kps = fc.keyframe_points
            a, b = kps[ia], kps[ib]
            seg_f = bf - af
            seg_v = bv - av
            vscale = abs(seg_v) if seg_v != 0 else abs(seg_f)
            if self._drag == 'IN':
                a.interpolation = 'BEZIER'
                a.handle_right_type = 'FREE'
                a.handle_right.x = rx
                a.handle_right.y = ry
                props.in_x = (rx - af) / seg_f if seg_f else 0.0
                props.in_y = (ry - av) / vscale
            else:
                b.handle_left_type = 'FREE'
                b.handle_left.x = rx
                b.handle_left.y = ry
                props.out_x = (rx - bf) / seg_f if seg_f else 0.0
                props.out_y = (ry - bv) / vscale
            fc.update()
            if props.live_apply:
                try:
                    apply_handles_to_selection(context)
                except Exception:
                    pass
        else:
            if self._drag == 'IN':
                props.in_x = max(-0.3, min(1.3, rx))
                props.in_y = max(-1.5, min(2.5, ry))
            else:
                props.out_x = max(-1.3, min(0.3, rx - 1.0))
                props.out_y = max(-1.5, min(2.5, ry - 1.0))
        props.captured_mode = 'HANDLES'
        props.captured_label = "custom handles"

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()
        props = context.scene.motion_manager
        region = context.region
        if region is None:
            return {'RUNNING_MODAL'}
        rect = _ed_rect(region)
        mx, my = event.mouse_region_x, event.mouse_region_y

        if event.type == 'MOUSEMOVE':
            if self._drag:
                self._apply_drag(context, props, mx, my, rect)
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                d = _compute_draw(context, props, bounds_override=_ed_bounds)
                p1 = _ed_frac_px(d['p1'], rect)
                p2 = _ed_frac_px(d['p2'], rect)
                if _ed_near(mx, my, p1):
                    self._drag = 'IN'
                    return {'RUNNING_MODAL'}
                if _ed_near(mx, my, p2):
                    self._drag = 'OUT'
                    return {'RUNNING_MODAL'}
                if not _ed_inside(mx, my, rect):
                    return self._end(context, 'FINISHED')
                return {'RUNNING_MODAL'}
            elif event.value == 'RELEASE':
                self._drag = None
                return {'RUNNING_MODAL'}

        if event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            return self._end(context, 'FINISHED')

        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            props.in_x, props.in_y, props.out_x, props.out_y = self._init
            # restore real handles if we edited a real segment
            if self._init_ref is not None:
                try:
                    apply_handles_to_selection(context)
                except Exception:
                    pass
            return self._end(context, 'CANCELLED')

        return {'RUNNING_MODAL'}


# ===========================================================================
# Panel
# ===========================================================================
class MM_PT_main(Panel):
    bl_label = "Vipz Motion Manager"
    bl_idname = "MM_PT_main"
    bl_space_type = 'GRAPH_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Vipz Motion Mgr"

    def draw(self, context):
        layout = self.layout
        props = context.scene.motion_manager

        # 1. Custom Curve (first)
        self.draw_custom(context, layout, props)
        # 2. Presets (collapsible)
        self.draw_presets(context, layout, props)
        # 3. Ease / Bounce / Elastic
        row = layout.row(align=True)
        row.scale_y = 1.05
        row.prop_enum(props, "mode", 'EASE')
        row.prop_enum(props, "mode", 'BOUNCE')
        row.prop_enum(props, "mode", 'ELASTIC')
        # 4. Track Filter + Save / Load
        self.draw_filter(layout, props)
        self.draw_saveload(layout, props)
        # Tools (collapsible, at the end)
        self.draw_tools(context, layout, props)

    # ---- Custom Curve ----
    def draw_custom(self, context, layout, props):
        have_icons = _pcoll is not None
        box = layout.box()
        box.label(text="Custom Curve", icon='FCURVE')
        if have_icons and "mm_live" in _pcoll:
            box.template_icon(icon_value=_refresh_live(context, props), scale=11.0)
        r = box.row(align=True)
        r.scale_y = 1.2
        r.operator("mm.edit_curve", text="Grab Handles (drag)", icon='IPO_BEZIER')
        r.prop(props, "live_apply", text="", icon='PLAY')

        grid = box.grid_flow(row_major=True, columns=2, align=True)
        grid.prop(props, "in_x")
        grid.prop(props, "out_x")
        grid.prop(props, "in_y")
        grid.prop(props, "out_y")
        r = box.row(align=True)
        r.prop(props, "handle_scale", slider=True)
        r.operator("mm.reset_curve", text="", icon='LOOP_BACK')
        box.label(text=f"Captured: {props.captured_label}", icon='COPYDOWN')
        r = box.row(align=True)
        r.scale_y = 1.2
        r.operator("mm.get_ease", icon='IMPORT')
        r.operator("mm.set_ease", icon='EXPORT')

    # ---- Presets (single button each, In-Out, collapsible) ----
    def draw_presets(self, context, layout, props):
        have_icons = _pcoll is not None
        box = layout.box()
        hdr = box.row(align=True)
        hdr.prop(props, "show_presets", text="",
                 icon='TRIA_DOWN' if props.show_presets else 'TRIA_RIGHT', emboss=False)
        hdr.label(text="Presets", icon='IPO_EASE_IN_OUT')
        if not props.show_presets:
            return
        families = {'EASE': EASE_FAMILIES, 'BOUNCE': BOUNCE_FAMILIES,
                    'ELASTIC': ELASTIC_FAMILIES}[props.mode]
        cols = 2 if len(families) > 1 else 1
        grid = box.grid_flow(row_major=True, columns=cols, align=True)
        grid.scale_y = 1.15
        for fam in families:
            op = grid.operator("mm.apply_preset", text=FAMILY_LABEL[fam],
                               icon_value=_preset_icon(fam, 'EASE_IN_OUT') if have_icons else 0)
            op.interpolation = fam
            op.easing = 'EASE_IN_OUT'

    # ---- Track Filter ----
    def draw_filter(self, layout, props):
        box = layout.box()
        box.label(text="Track Filter", icon='FILTER')
        box.row(align=True).prop(props, "filter_channels", expand=True)
        box.row(align=True).prop(props, "filter_transform", expand=True)

    # ---- Save / Load ----
    def draw_saveload(self, layout, props):
        box = layout.box()
        box.label(text="Save / Load", icon='FILE_TICK')
        r = box.row(align=True)
        r.prop(props, "save_name", text="")
        r.operator("mm.save_curve", text="", icon='ADD')
        r = box.row(align=True)
        r.prop(props, "load_choice", text="")
        r.operator("mm.load_curve", text="", icon='IMPORT')
        r.operator("mm.delete_curve", text="", icon='TRASH')

    # ---- Tools (collapsible) ----
    def draw_tools(self, context, layout, props):
        box = layout.box()
        hdr = box.row(align=True)
        hdr.prop(props, "show_tools", text="",
                 icon='TRIA_DOWN' if props.show_tools else 'TRIA_RIGHT', emboss=False)
        hdr.label(text="Tools", icon='TOOL_SETTINGS')
        if not props.show_tools:
            return
        box.operator("mm.tool", text="Reverse Ease", icon='ARROW_LEFTRIGHT').action = 'REVERSE'
        box.operator("mm.tool", text="Make Linear", icon='IPO_LINEAR').action = 'LINEAR'
        box.operator("mm.tool", text="Make Stepped", icon='IPO_CONSTANT').action = 'CONSTANT'
        box.operator("mm.tool", text="Smooth (Auto)", icon='SMOOTHCURVE').action = 'SMOOTH'
        box.operator("mm.tool", text="Mirror Handles", icon='MOD_MIRROR').action = 'MIRROR'


# ===========================================================================
# Registration
# ===========================================================================
classes = (
    MM_Props,
    MM_OT_apply_preset,
    MM_OT_get_ease,
    MM_OT_set_ease,
    MM_OT_reset_curve,
    MM_OT_edit_curve,
    MM_OT_save_curve,
    MM_OT_load_curve,
    MM_OT_delete_curve,
    MM_OT_tool,
    MM_PT_main,
)


def register():
    _build_previews()
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.motion_manager = bpy.props.PointerProperty(type=MM_Props)


def unregister():
    global _edit_handler
    if _edit_handler is not None:
        try:
            bpy.types.SpaceGraphEditor.draw_handler_remove(_edit_handler, 'WINDOW')
        except Exception:
            pass
        _edit_handler = None
    del bpy.types.Scene.motion_manager
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    global _pcoll, _live_key
    if _pcoll is not None:
        try:
            bpy.utils.previews.remove(_pcoll)
        except Exception:
            pass
        _pcoll = None
    _live_key = None


if __name__ == "__main__":
    register()
