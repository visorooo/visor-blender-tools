import bpy

from . import ui_list
from . import operators
from . import groups
from . import panels

classes = (
    *ui_list.classes,
    *operators.classes,
    *groups.classes,
    *panels.classes,
)


def _redraw_material_panels(scene, depsgraph):
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'PROPERTIES':
                area.tag_redraw()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.material_manager_index = bpy.props.IntProperty(
        name="Active Material Index",
        default=0,
    )
    bpy.types.Scene.material_manager_groups = bpy.props.CollectionProperty(
        type=groups.MATMGR_MaterialGroup,
    )
    bpy.types.Scene.material_manager_group_index = bpy.props.IntProperty(
        name="Active Group Index",
        default=0,
    )
    bpy.types.Scene.material_manager_filter_all = bpy.props.BoolProperty(
        name="Show All Materials",
        default=True,
    )
    bpy.types.Scene.material_manager_selection_anchor = bpy.props.IntProperty(
        name="Selection Range Anchor",
        default=-1,
    )
    bpy.types.Scene.material_manager_grid_view = bpy.props.BoolProperty(
        name="Grid View",
        default=False,
    )

    bpy.types.Material.matmgr_selected = bpy.props.BoolProperty(
        name="Selected",
        default=False,
    )
    bpy.types.Material.matmgr_group = bpy.props.StringProperty(
        name="Group",
        default="",
    )

    bpy.app.handlers.depsgraph_update_post.append(_redraw_material_panels)


def unregister():
    bpy.app.handlers.depsgraph_update_post.remove(_redraw_material_panels)

    del bpy.types.Material.matmgr_group
    del bpy.types.Material.matmgr_selected

    del bpy.types.Scene.material_manager_grid_view
    del bpy.types.Scene.material_manager_selection_anchor
    del bpy.types.Scene.material_manager_filter_all
    del bpy.types.Scene.material_manager_group_index
    del bpy.types.Scene.material_manager_groups
    del bpy.types.Scene.material_manager_index

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
