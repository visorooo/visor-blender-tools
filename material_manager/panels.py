import bpy

from . import ui_list


class MATMGR_PT_panel(bpy.types.Panel):
    bl_idname = "MATMGR_PT_panel"
    bl_label = "Material Manager"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'material'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        view_row = layout.row(align=True)
        view_row.alignment = 'RIGHT'
        view_icon = 'IMGDISPLAY' if not scene.material_manager_grid_view else 'SHORTDISPLAY'
        view_row.prop(scene, "material_manager_grid_view", text="", icon=view_icon, toggle=True)

        row = layout.row()
        if scene.material_manager_grid_view:
            self._draw_grid_body(row, scene)
        else:
            self._draw_list_body(row, scene)

        col = row.column(align=True)
        col.operator("material_manager.new_material", icon='ADD', text="")
        col.separator()
        col.operator("material_manager.purge_unused", icon='RESTRICT_INSTANCED_ON', text="")
        col.operator("material_manager.delete_all", icon='TRASH', text="")

        active_group = next((g for g in scene.material_manager_groups if g.active), None)
        current_label = "All" if scene.material_manager_filter_all or active_group is None else active_group.name

        grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        grid.operator("material_manager.select_active_material_users", text="Select objects")
        grid.operator("material_manager.assign_active_material_to_selected", text="Assign to selected")
        grid.operator("material_manager.move_selected_to_layer_menu", text="Move to Layer")
        grid.operator("material_manager.layer_filter_menu", text=current_label, icon='OUTLINER_COLLECTION')

    def _draw_list_body(self, row, scene):
        row.template_list(
            "MATMGR_UL_materials", "",
            bpy.data, "materials",
            scene, "material_manager_index",
            rows=12,
        )

    def _draw_grid_body(self, row, scene):
        materials = [m for m in bpy.data.materials if ui_list.material_passes_layer_filter(scene, m)]

        box = row.box()
        if not materials:
            box.label(text="No materials to show", icon='INFO')
            return

        flow = box.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=True, align=True)
        for mat in materials:
            tile = flow.column(align=True)
            icon_id = mat.preview.icon_id if mat.preview else 0
            if icon_id:
                tile.template_icon(icon_value=icon_id, scale=1.0)
            else:
                tile.label(text="", icon='MATERIAL')
            op = tile.operator(
                "material_manager.select_material_row", text=mat.name,
                depress=mat.matmgr_selected,
            )
            op.material_name = mat.name


classes = (
    MATMGR_PT_panel,
)
