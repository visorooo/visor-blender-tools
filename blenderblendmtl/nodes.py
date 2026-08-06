import bpy
from bpy.types import ShaderNodeCustomGroup, PropertyGroup
from bpy.props import CollectionProperty, EnumProperty

MAX_COATS = 9


def _on_mode_change(self, context):
    node = getattr(context, "node", None)
    if node is not None and node.bl_idname == "ShaderNodeBlenderBlendMtl":
        node.rebuild_internal_tree()


class BLENDERBLENDMTL_PG_Layer(PropertyGroup):
    mode: EnumProperty(
        name="Blend Mode",
        description="How this Coat layer combines with everything beneath it",
        items=[
            ('OVER', "Over", "Standard alpha-over blend: the Coat replaces the accumulated result below it according to Blend Amount"),
            ('ADDITIVE', "Additive", "The Coat's contribution is scaled by Blend Amount and added on top, without occluding what's beneath (e.g. clearcoat, decals)"),
        ],
        default='OVER',
        update=_on_mode_change,
    )


class ShaderNodeBlenderBlendMtl(ShaderNodeCustomGroup):
    """Layered Base + up to 9 Coat shader with per-layer masked Over/Additive blending"""
    bl_idname = 'ShaderNodeBlenderBlendMtl'
    bl_label = 'BlenderBlendMtl'
    bl_icon = 'SYSTEM'

    layers: CollectionProperty(type=BLENDERBLENDMTL_PG_Layer)

    def init(self, context):
        tree = bpy.data.node_groups.new(f".{self.bl_label}", 'ShaderNodeTree')
        tree.use_fake_user = True
        self.node_tree = tree

        tree.interface.new_socket("Shader", socket_type='NodeSocketShader', in_out='OUTPUT')
        tree.interface.new_socket("Base", socket_type='NodeSocketShader', in_out='INPUT')

        self.width = 220
        self.rebuild_internal_tree()

    def copy(self, node):
        self.node_tree = node.node_tree.copy()

    def free(self):
        bpy.data.node_groups.remove(self.node_tree, do_unlink=True)

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        for i, layer in enumerate(self.layers):
            box = col.box()
            row = box.row(align=True)
            row.label(text=f"Coat {i + 1}")
            row.prop(layer, "mode", text="")
            op = row.operator("node.blenderblendmtl_remove_layer", text="", icon='X')
            op.layer_index = i

        row = layout.row()
        row.enabled = len(self.layers) < MAX_COATS
        add_label = "Add Coat Layer" if len(self.layers) < MAX_COATS else f"Max {MAX_COATS} Coats Reached"
        row.operator("node.blenderblendmtl_add_layer", text=add_label, icon='ADD')

    def add_layer(self):
        idx = len(self.layers) + 1
        tree = self.node_tree
        tree.interface.new_socket(f"Coat {idx}", socket_type='NodeSocketShader', in_out='INPUT')
        amount_socket = tree.interface.new_socket(
            f"Blend Amount {idx}", socket_type='NodeSocketColor', in_out='INPUT'
        )
        amount_socket.default_value = (0.5, 0.5, 0.5, 1.0)

        layer = self.layers.add()
        layer.mode = 'OVER'
        self.rebuild_internal_tree()

    def remove_layer(self, layer_index):
        tree = self.node_tree

        for name in (f"Coat {layer_index + 1}", f"Blend Amount {layer_index + 1}"):
            item = tree.interface.items_tree.get(name)
            if item:
                tree.interface.remove(item)

        self.layers.remove(layer_index)

        # Renumber remaining sockets so labels stay contiguous. Renaming an
        # interface item keeps its identity (and existing links), it's a
        # cosmetic relabel only.
        for i in range(layer_index, len(self.layers)):
            old_coat = tree.interface.items_tree.get(f"Coat {i + 2}")
            old_amount = tree.interface.items_tree.get(f"Blend Amount {i + 2}")
            if old_coat:
                old_coat.name = f"Coat {i + 1}"
            if old_amount:
                old_amount.name = f"Blend Amount {i + 1}"

        self.rebuild_internal_tree()

    def rebuild_internal_tree(self):
        tree = self.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        group_in = nodes.new('NodeGroupInput')
        group_in.location = (-400, 0)
        group_out = nodes.new('NodeGroupOutput')

        accum_socket = group_in.outputs['Base']
        x = 0
        for i, layer in enumerate(self.layers):
            x += 400
            coat_name = f"Coat {i + 1}"
            amount_name = f"Blend Amount {i + 1}"

            rgb_to_bw = nodes.new('ShaderNodeRGBToBW')
            rgb_to_bw.location = (x - 200, -300)
            links.new(group_in.outputs[amount_name], rgb_to_bw.inputs['Color'])

            if layer.mode == 'OVER':
                mix = nodes.new('ShaderNodeMixShader')
                mix.location = (x, 0)
                links.new(rgb_to_bw.outputs['Val'], mix.inputs['Fac'])
                links.new(accum_socket, mix.inputs[1])
                links.new(group_in.outputs[coat_name], mix.inputs[2])
                accum_socket = mix.outputs['Shader']
            else:  # ADDITIVE
                transparent = nodes.new('ShaderNodeBsdfTransparent')
                transparent.location = (x - 200, 250)

                masked_coat = nodes.new('ShaderNodeMixShader')
                masked_coat.location = (x, 250)
                links.new(rgb_to_bw.outputs['Val'], masked_coat.inputs['Fac'])
                links.new(transparent.outputs['BSDF'], masked_coat.inputs[1])
                links.new(group_in.outputs[coat_name], masked_coat.inputs[2])

                add = nodes.new('ShaderNodeAddShader')
                add.location = (x, -50)
                links.new(accum_socket, add.inputs[0])
                links.new(masked_coat.outputs['Shader'], add.inputs[1])
                accum_socket = add.outputs['Shader']

        group_out.location = (x + 400, 0)
        links.new(accum_socket, group_out.inputs['Shader'])


classes = (
    BLENDERBLENDMTL_PG_Layer,
    ShaderNodeBlenderBlendMtl,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
