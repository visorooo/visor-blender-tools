import bpy

bl_info = {
    "name": "Metal BSDF (Tailoff)",
    "author": "Victor Octavio",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "Shader Editor > Add > Metal BSDF (Tailoff)",
    "description": (
        "Principled BSDF variant streamlined for metal surfaces, with a "
        "collapsible Tailoff panel for blending extra roughness layers"
    ),
    "category": "Node",
}

GROUP_NAME = "Metal BSDF (Tailoff)"
TAILOFF_VERSION = 7  # bump whenever _build_node_group()'s structure changes so existing
                      # groups in already-open files get rebuilt in place, not just new ones.

EXCLUDE_PREFIXES = ("Diffuse", "Subsurface", "Transmission", "Sheen", "Emission")
TOP_BEFORE_ROUGHNESS = ["Base Color", "Metallic", "Roughness"]
TOP_AFTER_ROUGHNESS = ["IOR", "Alpha", "Normal"]
SPECULAR_NAMES = ["Specular IOR Level", "Specular Tint", "Anisotropic", "Anisotropic Rotation", "Tangent"]
COAT_NAMES = ["Coat Weight", "Coat Roughness", "Coat IOR", "Coat Tint", "Coat Normal"]
THIN_FILM_NAMES = ["Thin Film Thickness", "Thin Film IOR"]

TAILOFF_LAYER_COUNT = 2


def _socket(collection, name):
    # Some built-in nodes (Principled BSDF, Mix) expose hidden duplicate-named
    # sockets internally, which makes collection["Name"] key lookup unreliable.
    # Linear match on the visible .name is safe.
    for s in collection:
        if s.name == name:
            return s
    raise KeyError(name)


def _base_socket_type(principled_input):
    idname = principled_input.bl_idname
    if idname.startswith("NodeSocketFloat"):
        return "NodeSocketFloat"
    return idname


def _configure_float_socket(iface_socket, principled_input):
    # The raw node-level socket's .min_value/.max_value are always None for
    # compiled nodes like Principled BSDF -- the real UI range lives on the
    # underlying RNA float property as soft_min/soft_max (verified empirically;
    # e.g. Metallic/Roughness/Alpha report hard=soft=(0,1), IOR/Weight report
    # soft=(-10000,10000)). Copying the (always-None) min_value/max_value
    # silently failed and left FloatFactor sockets at Blender's generic
    # -10000..10000 fallback range, which is what corrupted Metallic/Roughness.
    idname = principled_input.bl_idname
    try:
        if idname == "NodeSocketFloatFactor":
            iface_socket.subtype = "FACTOR"
        elif idname == "NodeSocketFloatDistance":
            iface_socket.subtype = "DISTANCE"
        elif idname == "NodeSocketFloatWavelength":
            iface_socket.subtype = "WAVELENGTH"
    except (AttributeError, TypeError):
        pass

    prop = principled_input.bl_rna.properties["default_value"]
    iface_socket.min_value = prop.soft_min
    iface_socket.max_value = prop.soft_max
    iface_socket.default_value = principled_input.default_value


def _add_passthrough_socket(iface, principled_input, parent=None):
    socket_type = _base_socket_type(principled_input)
    iface_socket = iface.new_socket(
        name=principled_input.name, in_out='INPUT', socket_type=socket_type, parent=parent,
    )
    if socket_type == "NodeSocketFloat":
        _configure_float_socket(iface_socket, principled_input)
    elif socket_type in ("NodeSocketColor", "NodeSocketVector"):
        try:
            iface_socket.default_value = principled_input.default_value
        except (TypeError, ValueError):
            pass
    if hasattr(iface_socket, "hide_value") and hasattr(principled_input, "hide_value"):
        iface_socket.hide_value = principled_input.hide_value
    return iface_socket


def _new_factor_socket(iface, name, default, parent=None):
    socket = iface.new_socket(name=name, in_out='INPUT', socket_type='NodeSocketFloat', parent=parent)
    socket.subtype = 'FACTOR'
    socket.min_value = 0.0
    socket.max_value = 1.0
    socket.default_value = default
    return socket


def _new_normal_socket(iface, name, parent=None):
    socket = iface.new_socket(name=name, in_out='INPUT', socket_type='NodeSocketVector', parent=parent)
    socket.hide_value = True  # collapse to a single row instead of raw X/Y/Z fields
    return socket


def _build_node_group(existing=None):
    if existing is not None:
        ng = existing
        ng.nodes.clear()
        ng.interface.clear()
    else:
        ng = bpy.data.node_groups.new(GROUP_NAME, 'ShaderNodeTree')
    iface = ng.interface

    principled = ng.nodes.new('ShaderNodeBsdfPrincipled')
    principled.location = (300, 0)

    for name in TOP_BEFORE_ROUGHNESS:
        _add_passthrough_socket(iface, _socket(principled.inputs, name))

    tailoff_panel = iface.new_panel(
        name="Tailoff",
        description="Blend extra roughness layers into the base Roughness",
        default_closed=True,
    )
    use_tailoff = iface.new_socket(name="Use Tailoff", in_out='INPUT', socket_type='NodeSocketBool', parent=tailoff_panel)
    use_tailoff.default_value = False

    layer_names = []
    for i in range(1, TAILOFF_LAYER_COUNT + 1):
        _new_factor_socket(iface, f"Roughness {i}", 0.5, parent=tailoff_panel)
        _new_factor_socket(iface, f"Amount {i}", 0.0, parent=tailoff_panel)
        _new_factor_socket(iface, f"Anisotropy {i}", 0.0, parent=tailoff_panel)
        _new_factor_socket(iface, f"Rotation {i}", 0.0, parent=tailoff_panel)
        _new_normal_socket(iface, f"Normal {i}", parent=tailoff_panel)
        layer_names.append((f"Roughness {i}", f"Amount {i}", f"Anisotropy {i}", f"Rotation {i}", f"Normal {i}"))

    for name in TOP_AFTER_ROUGHNESS:
        _add_passthrough_socket(iface, _socket(principled.inputs, name))

    specular_panel = iface.new_panel(name="Specular", default_closed=True)
    for name in SPECULAR_NAMES:
        _add_passthrough_socket(iface, _socket(principled.inputs, name), parent=specular_panel)

    coat_panel = iface.new_panel(name="Coat", default_closed=True)
    for name in COAT_NAMES:
        _add_passthrough_socket(iface, _socket(principled.inputs, name), parent=coat_panel)

    thin_film_panel = iface.new_panel(name="Thin Film", default_closed=True)
    for name in THIN_FILM_NAMES:
        _add_passthrough_socket(iface, _socket(principled.inputs, name), parent=thin_film_panel)

    iface.new_socket(name="BSDF", in_out='OUTPUT', socket_type='NodeSocketShader')

    group_input = ng.nodes.new('NodeGroupInput')
    group_input.location = (-700, 0)
    group_output = ng.nodes.new('NodeGroupOutput')
    group_output.location = (900, 0)

    passthrough_names = (
        TOP_BEFORE_ROUGHNESS + TOP_AFTER_ROUGHNESS + SPECULAR_NAMES + COAT_NAMES + THIN_FILM_NAMES
    )
    for name in passthrough_names:
        ng.links.new(_socket(group_input.outputs, name), _socket(principled.inputs, name))

    # Tailoff is a stack of extra Glossy BSDF lobes mixed "over" the base Principled
    # result via Mix Shader, not a blend of the Roughness *number*. Each layer's
    # Amount is the Mix Shader factor -- how much of that rougher lobe shows through
    # on top of everything mixed in so far. This matches a classic multi-lobe
    # specular "tailoff" (sharp core + broader soft highlight), which a single
    # averaged roughness value can't reproduce.
    frame = ng.nodes.new('NodeFrame')
    frame.label = "Tailoff"

    def new_node(idname, x, y):
        node = ng.nodes.new(idname)
        node.location = (x, y)
        node.parent = frame
        return node

    current_shader = _socket(principled.outputs, "BSDF")
    for i, (r_name, a_name, aniso_name, rot_name, normal_name) in enumerate(layer_names):
        # 'ShaderNodeBsdfGlossy' is a backward-compat alias here; the created node's
        # real bl_idname is ShaderNodeBsdfAnisotropic (still labeled "Glossy BSDF").
        glossy = new_node('ShaderNodeBsdfGlossy', -400, 250 - i * 180)
        glossy.distribution = 'MULTI_GGX'
        ng.links.new(_socket(group_input.outputs, "Base Color"), glossy.inputs["Color"])
        ng.links.new(_socket(group_input.outputs, r_name), glossy.inputs["Roughness"])
        # Anisotropy/Rotation/Normal are independent per layer. Tangent is
        # intentionally left unconnected (native auto-tangent).
        ng.links.new(_socket(group_input.outputs, aniso_name), glossy.inputs["Anisotropy"])
        ng.links.new(_socket(group_input.outputs, rot_name), glossy.inputs["Rotation"])
        ng.links.new(_socket(group_input.outputs, normal_name), glossy.inputs["Normal"])

        mix_shader = new_node('ShaderNodeMixShader', -150 + i * 230, 250 - i * 180)
        ng.links.new(_socket(group_input.outputs, a_name), mix_shader.inputs[0])
        ng.links.new(current_shader, mix_shader.inputs[1])
        ng.links.new(glossy.outputs["BSDF"], mix_shader.inputs[2])
        current_shader = mix_shader.outputs[0]

    gate = new_node('ShaderNodeMixShader', 800, 0)
    ng.links.new(_socket(group_input.outputs, "Use Tailoff"), gate.inputs[0])
    ng.links.new(_socket(principled.outputs, "BSDF"), gate.inputs[1])  # off -> plain Principled
    ng.links.new(current_shader, gate.inputs[2])                       # on  -> full Tailoff stack

    ng.links.new(gate.outputs[0], _socket(group_output.inputs, "BSDF"))

    ng["tailoff_version"] = TAILOFF_VERSION
    return ng


def ensure_node_group():
    group = bpy.data.node_groups.get(GROUP_NAME)
    if group is None:
        group = _build_node_group()
    elif group.get("tailoff_version") != TAILOFF_VERSION:
        group = _build_node_group(existing=group)
    return group


class ShaderNodeMetalBSDFTailoff(bpy.types.ShaderNodeCustomGroup):
    """Native-looking wrapper around the shared Metal BSDF (Tailoff) node group.

    All instances share the one "Metal BSDF (Tailoff)" node tree (same as a plain
    node group) -- this class only changes how the node presents itself (no
    node-tree picker/user-count chrome; header color intentionally left at
    Blender's default shader-node green to match built-in BSDF nodes). Editing the
    shared tree still updates every placed instance at once, and
    ensure_node_group()'s version-upgrade-in-place still applies to all of them.
    """

    bl_idname = "ShaderNodeMetalBSDFTailoff"
    bl_label = "Metal BSDF (Tailoff)"
    bl_icon = 'SYSTEM'

    @classmethod
    def poll(cls, node_tree):
        return node_tree.bl_idname == 'ShaderNodeTree'

    def init(self, context):
        self.node_tree = ensure_node_group()
        self.width = 220


class NODE_OT_add_metal_bsdf_tailoff(bpy.types.Operator):
    bl_idname = "node.add_metal_bsdf_tailoff"
    bl_label = "Metal BSDF (Tailoff)"
    bl_description = (
        "Add a Principled-BSDF-based node streamlined for metal surfaces, "
        "with a multi-layer roughness Tailoff panel"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.tree_type == 'ShaderNodeTree'
            and space.edit_tree is not None
        )

    def execute(self, context):
        tree = context.space_data.edit_tree
        for n in tree.nodes:
            n.select = False

        node = tree.nodes.new(ShaderNodeMetalBSDFTailoff.bl_idname)
        node.select = True
        tree.nodes.active = node

        try:
            bpy.ops.node.translate_attach_remove_on_cancel('INVOKE_DEFAULT')
        except RuntimeError:
            pass

        return {'FINISHED'}


def _draw_menu(self, context):
    space = context.space_data
    if space and space.tree_type == 'ShaderNodeTree':
        self.layout.operator(NODE_OT_add_metal_bsdf_tailoff.bl_idname, icon='SYSTEM')


classes = (ShaderNodeMetalBSDFTailoff, NODE_OT_add_metal_bsdf_tailoff)


def _all_shader_node_trees():
    trees = list(bpy.data.node_groups)
    trees += [m.node_tree for m in bpy.data.materials if m.node_tree]
    trees += [w.node_tree for w in bpy.data.worlds if w.node_tree]
    return trees


def _reset_existing_node_styling():
    # init() only runs for newly-created nodes, so a node placed under an older
    # version of this add-on keeps whatever styling it was created with (e.g. an
    # earlier custom header color) until this runs it back to Blender's default.
    for tree in _all_shader_node_trees():
        for node in tree.nodes:
            if node.bl_idname == ShaderNodeMetalBSDFTailoff.bl_idname and node.use_custom_color:
                node.use_custom_color = False


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.NODE_MT_add.append(_draw_menu)

    # Upgrade an already-existing (e.g. previously broken) group in the
    # currently open file in place, so every node referencing it is fixed
    # without the user having to delete and re-add anything.
    existing = bpy.data.node_groups.get(GROUP_NAME)
    if existing is not None and existing.get("tailoff_version") != TAILOFF_VERSION:
        _build_node_group(existing=existing)

    _reset_existing_node_styling()


def unregister():
    bpy.types.NODE_MT_add.remove(_draw_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
