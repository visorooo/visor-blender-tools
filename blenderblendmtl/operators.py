import bpy
from bpy.props import IntProperty

from .nodes import MAX_COATS


def _active_blenderblendmtl_node(context):
    node = getattr(context, "node", None)
    if node is not None and node.bl_idname == "ShaderNodeBlenderBlendMtl":
        return node
    return None


class NODE_OT_blenderblendmtl_add_layer(bpy.types.Operator):
    bl_idname = "node.blenderblendmtl_add_layer"
    bl_label = "Add Coat Layer"
    bl_description = "Add a new Coat layer (Shader + Blend Amount) to this BlenderBlendMtl node, up to 9 total"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        node = _active_blenderblendmtl_node(context)
        return node is not None and len(node.layers) < MAX_COATS

    def execute(self, context):
        node = _active_blenderblendmtl_node(context)
        if node is None:
            return {'CANCELLED'}
        node.add_layer()
        return {'FINISHED'}


class NODE_OT_blenderblendmtl_remove_layer(bpy.types.Operator):
    bl_idname = "node.blenderblendmtl_remove_layer"
    bl_label = "Remove Coat Layer"
    bl_description = "Remove this Coat layer from the BlenderBlendMtl node"
    bl_options = {'REGISTER', 'UNDO'}

    layer_index: IntProperty()

    @classmethod
    def poll(cls, context):
        node = _active_blenderblendmtl_node(context)
        return node is not None and len(node.layers) > 0

    def execute(self, context):
        node = _active_blenderblendmtl_node(context)
        if node is None:
            return {'CANCELLED'}
        node.remove_layer(self.layer_index)
        return {'FINISHED'}


classes = (
    NODE_OT_blenderblendmtl_add_layer,
    NODE_OT_blenderblendmtl_remove_layer,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
