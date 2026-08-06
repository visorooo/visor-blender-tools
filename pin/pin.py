# SPDX-License-Identifier: MIT
"""
Pin - Blender port of a Cinema 4D tag plugin.

Constrains an object to follow a point, polygon, or surface location on
another (deforming/animated) mesh. Unlike a normal constraint, it reads the
*evaluated* (deformed) geometry, so the pinned object sticks to point-level
animation: shape keys, armatures, cloth/soft body, lattice, any deformer, etc.

Original C4D behaviour mapped to Blender:
  - C4D tag (per object)                -> per-object PropertyGroup + Object
                                           Properties panel.
  - Expression pass (runs each frame)   -> frame_change_post handler (+ a
                                           guarded depsgraph_update_post for
                                           live editing feedback).
  - GetDeformCache()                    -> obj.evaluated_get(depsgraph).to_mesh()
  - Pin / Unpin buttons                 -> operators.
  - Surface normal maps to +Y in C4D    -> mapped to the pinned object's local
                                           +Z here (Blender is Z-up).
"""

bl_info = {
    "name": "Pin",
    "author": "Ported from a Cinema 4D plugin",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "Properties > Object > Pin",
    "description": "Pin an object to a point/polygon/surface of a deforming mesh.",
    "category": "Object",
}

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatVectorProperty,
    IntProperty,
    IntVectorProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Object, Operator, Panel, PropertyGroup
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

# --------------------------------------------------------------------------- #
#  Geometry helpers
# --------------------------------------------------------------------------- #

def _frame_basis(normal):
    """Build an orthonormal 3x3 frame whose local +Z is the surface normal."""
    n = normal.normalized()
    if n.length_squared == 0.0:
        n = Vector((0.0, 0.0, 1.0))
    helper = Vector((1.0, 0.0, 0.0))
    if abs(helper.dot(n)) > 0.99:
        helper = Vector((0.0, 0.0, 1.0))
    x = helper.cross(n).normalized()      # tangent  -> local +X
    y = n.cross(x).normalized()           # bitangent -> local +Y
    # rows [x, y, n] transposed => columns x, y, n  (right-handed, Z = normal)
    return Matrix((x, y, n)).transposed()


def _frame_matrix(pos, basis):
    """4x4 transform: rotation = basis, translation = pos (no scale)."""
    return Matrix.Translation(pos) @ basis.to_4x4()


def _closest_point_on_triangle(p, a, b, c):
    """Return (u, v, w) barycentric coords of the closest point on tri (a,b,c)."""
    ab = b - a
    ac = c - a
    ap = p - a
    d1 = ab.dot(ap)
    d2 = ac.dot(ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return 1.0, 0.0, 0.0

    bp = p - b
    d3 = ab.dot(bp)
    d4 = ac.dot(bp)
    if d3 >= 0.0 and d4 <= d3:
        return 0.0, 1.0, 0.0

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return 1.0 - v, v, 0.0

    cp = p - c
    d5 = ab.dot(cp)
    d6 = ac.dot(cp)
    if d6 >= 0.0 and d5 <= d6:
        return 0.0, 0.0, 1.0

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return 1.0 - w, 0.0, w

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return 0.0, 1.0 - w, w

    denom = 1.0 / (va + vb + vc)
    v = vb * denom
    w = vc * denom
    return 1.0 - v - w, v, w


# --------------------------------------------------------------------------- #
#  Evaluated-mesh access (the "deform cache" equivalent)
# --------------------------------------------------------------------------- #

class _EvalMesh:
    """Reads the deformed source mesh and exposes targeted world-space queries.

    Use as a context manager so the temporary mesh is always freed.
    """

    def __init__(self, source, depsgraph):
        self.ok = False
        self.eval_obj = source.evaluated_get(depsgraph)
        self.me = self.eval_obj.to_mesh()
        if self.me is None or len(self.me.polygons) == 0:
            return
        self.mw = self.eval_obj.matrix_world.copy()
        self.nmat = self.mw.to_3x3().inverted_safe().transposed()
        self.ok = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        try:
            self.eval_obj.to_mesh_clear()
        except Exception:
            pass

    # -- queries -----------------------------------------------------------
    def vert_world(self, i):
        return self.mw @ self.me.vertices[i].co

    def n_verts(self):
        return len(self.me.vertices)

    def n_polys(self):
        return len(self.me.polygons)

    def point_frame(self, i):
        v = self.me.vertices[i]
        pos = self.mw @ v.co
        normal = (self.nmat @ v.normal).normalized()
        return pos, normal

    def polygon_frame(self, i):
        poly = self.me.polygons[i]
        pos = self.mw @ poly.center
        normal = (self.nmat @ poly.normal).normalized()
        return pos, normal

    def surface_frame(self, vi):
        """vi = (i0, i1, i2, w0, w1, w2). Position is the weighted point,
        normal comes from that triangle (so it follows deformation)."""
        i0, i1, i2, w0, w1, w2 = vi
        p0 = self.vert_world(i0)
        p1 = self.vert_world(i1)
        p2 = self.vert_world(i2)
        pos = p0 * w0 + p1 * w1 + p2 * w2
        normal = (p1 - p0).cross(p2 - p0).normalized()
        return pos, normal

    def nearest_surface(self, world_pos):
        """Find nearest triangle (fan-triangulated faces). Returns
        (face_index, (i0, i1, i2, w0, w1, w2)) or (None, None)."""
        best_d = None
        best_face = None
        best = None
        for face in self.me.polygons:
            verts = list(face.vertices)
            wp = [self.vert_world(v) for v in verts]
            a = wp[0]
            for k in range(1, len(verts) - 1):
                b = wp[k]
                c = wp[k + 1]
                u, v, w = _closest_point_on_triangle(world_pos, a, b, c)
                hit = a * u + b * v + c * w
                d = (world_pos - hit).length_squared
                if best_d is None or d < best_d:
                    best_d = d
                    best_face = face.index
                    best = (verts[0], verts[k], verts[k + 1], u, v, w)
        return best_face, best


# --------------------------------------------------------------------------- #
#  Apply transform to the pinned object
# --------------------------------------------------------------------------- #

def _mat_close(a, b, tol=1e-6):
    for i in range(4):
        for j in range(4):
            if abs(a[i][j] - b[i][j]) > tol:
                return False
    return True


def _apply(obj, pos, basis, use_orientation, offset):
    """Move (and optionally orient) obj. Writes only if something changed,
    which lets the depsgraph handler self-terminate."""
    frame = _frame_matrix(pos, basis)
    final_pos = frame @ Vector(offset)   # offset is (0,0,0) for point/polygon

    if use_orientation:
        _, _, scale = obj.matrix_world.decompose()
        intended = Matrix.LocRotScale(final_pos, basis.to_quaternion(), scale)
    else:
        intended = obj.matrix_world.copy()
        intended.translation = final_pos

    if not _mat_close(obj.matrix_world, intended):
        obj.matrix_world = intended


# --------------------------------------------------------------------------- #
#  Binding (the "Pin" action) and per-frame update
# --------------------------------------------------------------------------- #

def _bind(obj, ps, depsgraph):
    """Compute and store the binding for the current mode. Returns (ok, msg)."""
    source = ps.source
    if source is None:
        return False, "Source Object is missing"
    if source == obj:
        return False, "Source cannot be the object itself"

    with _EvalMesh(source, depsgraph) as em:
        if not em.ok:
            return False, "Source has no usable geometry"

        # default: no offset (object snaps to the target, like the original)
        ps.offset = (0.0, 0.0, 0.0)

        if ps.mode == 'POINT':
            if not (0 <= ps.point_index < em.n_verts()):
                return False, "Point index out of range"
            return True, "Object is pinned to point"

        if ps.mode == 'POLYGON':
            if not (0 <= ps.polygon_index < em.n_polys()):
                return False, "Polygon index out of range"
            return True, "Object is pinned to polygon"

        # SURFACE: find nearest point, store tri + weights + positional offset
        face, vi = em.nearest_surface(obj.matrix_world.translation)
        if face is None:
            return False, "Could not find surface"

        ps.face_index = face
        ps.bind_idx = (vi[0], vi[1], vi[2])
        ps.weight = (vi[3], vi[4], vi[5])

        pos, normal = em.surface_frame(vi)
        basis = _frame_basis(normal)
        m0 = _frame_matrix(pos, basis)
        ps.offset = m0.inverted_safe() @ obj.matrix_world.translation
        return True, "Object is pinned to surface"


def _update_object(obj, ps, em):
    """Apply one update for obj using an already-built _EvalMesh."""
    if ps.mode == 'POINT':
        if not (0 <= ps.point_index < em.n_verts()):
            return
        pos, normal = em.point_frame(ps.point_index)

    elif ps.mode == 'POLYGON':
        if not (0 <= ps.polygon_index < em.n_polys()):
            return
        pos, normal = em.polygon_frame(ps.polygon_index)

    else:  # SURFACE
        i0, i1, i2 = ps.bind_idx
        n = em.n_verts()
        if not (0 <= i0 < n and 0 <= i1 < n and 0 <= i2 < n):
            return
        w0, w1, w2 = ps.weight
        pos, normal = em.surface_frame((i0, i1, i2, w0, w1, w2))

    basis = _frame_basis(normal)
    _apply(obj, pos, basis, ps.use_orientation, ps.offset)


def _update_scene(scene, depsgraph):
    cache = {}
    try:
        for obj in scene.objects:
            ps = getattr(obj, "pin_settings", None)
            if ps is None or not ps.enabled or ps.source is None:
                continue
            src = ps.source
            em = cache.get(src)
            if em is None:
                em = _EvalMesh(src, depsgraph)
                cache[src] = em
            if not em.ok:
                continue
            _update_object(obj, ps, em)
    finally:
        for em in cache.values():
            if em is not None:
                em.__exit__()


# --------------------------------------------------------------------------- #
#  Handlers
# --------------------------------------------------------------------------- #

_UPDATING = False


def _run(scene, depsgraph):
    global _UPDATING
    if _UPDATING:
        return
    if scene is None:
        return
    if depsgraph is None:
        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
        except Exception:
            return
    _UPDATING = True
    try:
        _update_scene(scene, depsgraph)
    except Exception as exc:
        print("[Pin] update error:", exc)
    finally:
        _UPDATING = False


@persistent
def _on_frame(scene, depsgraph=None):
    _run(scene, depsgraph)


@persistent
def _on_depsgraph(scene, depsgraph=None):
    _run(scene, depsgraph)


# --------------------------------------------------------------------------- #
#  Properties
# --------------------------------------------------------------------------- #

def _source_poll(self, obj):
    return obj.type == 'MESH'


class PinSettings(PropertyGroup):
    enabled: BoolProperty(
        name="Pinned",
        default=False,
        description="Whether this object is currently following its source",
    )
    source: PointerProperty(
        name="Source Object",
        type=Object,
        poll=_source_poll,
        description="Mesh to pin to (its deformed geometry is followed)",
    )
    mode: EnumProperty(
        name="Mode",
        items=[
            ('POINT', "Point", "Follow a single vertex by index"),
            ('POLYGON', "Polygon", "Follow a face center by index"),
            ('SURFACE', "Surface", "Stick to the nearest point on the surface"),
        ],
        default='POINT',
    )
    point_index: IntProperty(name="Point Index", min=0, default=0)
    polygon_index: IntProperty(name="Polygon Index", min=0, default=0)
    use_orientation: BoolProperty(
        name="Use Orientation",
        default=False,
        description="Also align the object's local +Z to the surface normal",
    )

    # internal binding data
    bind_idx: IntVectorProperty(size=3, default=(0, 0, 0))
    weight: FloatVectorProperty(size=3, default=(1.0, 0.0, 0.0))
    offset: FloatVectorProperty(size=3, subtype='TRANSLATION', default=(0, 0, 0))
    face_index: IntProperty(default=-1)
    status: StringProperty(default="Object is unpinned")


# --------------------------------------------------------------------------- #
#  Operators
# --------------------------------------------------------------------------- #

class OBJECT_OT_pin_pin(Operator):
    bl_idname = "object.pin_pin"
    bl_label = "Pin"
    bl_description = "Pin this object to the source's current (deformed) geometry"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.pin_settings.source is not None \
            and not obj.pin_settings.enabled

    def execute(self, context):
        obj = context.object
        ps = obj.pin_settings
        depsgraph = context.evaluated_depsgraph_get()
        ok, msg = _bind(obj, ps, depsgraph)
        ps.status = msg
        if not ok:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        ps.enabled = True
        # apply once immediately
        with _EvalMesh(ps.source, depsgraph) as em:
            if em.ok:
                _update_object(obj, ps, em)
        return {'FINISHED'}


class OBJECT_OT_pin_unpin(Operator):
    bl_idname = "object.pin_unpin"
    bl_label = "Unpin"
    bl_description = "Stop following the source; leave the object where it is"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.pin_settings.enabled

    def execute(self, context):
        ps = context.object.pin_settings
        ps.enabled = False
        ps.status = "Object is unpinned"
        return {'FINISHED'}


# --------------------------------------------------------------------------- #
#  Panel
# --------------------------------------------------------------------------- #

class OBJECT_PT_pin(Panel):
    bl_label = "Pin"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'

    def draw(self, context):
        layout = self.layout
        obj = context.object
        if obj is None:
            return
        ps = obj.pin_settings

        col = layout.column()
        col.prop(ps, "source")
        col.prop(ps, "mode", expand=True)

        if ps.mode == 'POINT':
            col.prop(ps, "point_index")
        elif ps.mode == 'POLYGON':
            col.prop(ps, "polygon_index")

        col.prop(ps, "use_orientation")

        row = layout.row(align=True)
        row.operator("object.pin_pin", icon='PINNED')
        row.operator("object.pin_unpin", icon='UNPINNED')

        box = layout.box()
        box.label(text=ps.status, icon='PINNED' if ps.enabled else 'UNPINNED')


# --------------------------------------------------------------------------- #
#  Registration
# --------------------------------------------------------------------------- #

_classes = (
    PinSettings,
    OBJECT_OT_pin_pin,
    OBJECT_OT_pin_unpin,
    OBJECT_PT_pin,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    Object.pin_settings = PointerProperty(type=PinSettings)

    if _on_frame not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_on_frame)
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)


def unregister():
    if _on_frame in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_on_frame)
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)

    del Object.pin_settings
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
