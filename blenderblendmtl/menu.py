import bpy

# Blender's Shader Editor "Add" menu (4.x/5.x) draws each category
# (Input/Output/Shader/.../Group/Layout) from a hardcoded per-category menu
# class, not from nodeitems_utils, for the built-in node tree types
# (ShaderNodeTree/GeometryNodeTree/CompositorNodeTree/TextureNodeTree).
# NODE_MT_shader_node_add_all is the *root* menu class for the Shader Editor
# (it draws Input/Output/Shader/.../Group/Layout in sequence) and, like any
# other bpy.types.Menu, still supports .append()/.remove() for third-party
# entries. Appending here (rather than to NODE_MT_group_add, the "Group"
# submenu) puts our node as its own flat top-level entry instead of nesting
# it inside "Group".


def draw_menu_item(self, context):
    space = context.space_data
    if space is None or getattr(space, "tree_type", None) != 'ShaderNodeTree':
        return
    layout = self.layout
    layout.separator()
    props = layout.operator("node.add_node", text="BlenderBlendMtl", icon='SYSTEM')
    props.type = "ShaderNodeBlenderBlendMtl"
    if hasattr(props, "use_transform"):
        props.use_transform = True


def register():
    bpy.types.NODE_MT_shader_node_add_all.append(draw_menu_item)


def unregister():
    bpy.types.NODE_MT_shader_node_add_all.remove(draw_menu_item)
