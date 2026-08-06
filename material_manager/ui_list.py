import bpy


def material_passes_layer_filter(scene, mat):
    if scene.material_manager_filter_all:
        return True
    active_layer_names = {g.name for g in scene.material_manager_groups if g.active}
    return mat.matmgr_group in active_layer_names


class MATMGR_UL_materials(bpy.types.UIList):
    """Row layout for the scene-wide material list."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        mat = item

        row = layout.row(align=True)

        icon_id = 0
        if mat.preview:
            icon_id = mat.preview.icon_id

        checkbox_icon = 'CHECKBOX_HLT' if mat.matmgr_selected else 'CHECKBOX_DEHLT'
        op = row.operator("material_manager.select_material_row", text="", icon=checkbox_icon, emboss=False)
        op.material_name = mat.name

        if icon_id:
            row.label(text="", icon_value=icon_id)
        else:
            row.label(text="", icon='MATERIAL')

        row.prop(mat, "name", text="", emboss=False)

        trailing = row.row(align=True)
        trailing.alignment = 'RIGHT'

        if mat.matmgr_group:
            trailing.label(text=mat.matmgr_group, icon='OUTLINER_COLLECTION')

        trailing.prop(mat, "use_fake_user", text="", toggle=True, emboss=True)

        op = trailing.operator("material_manager.delete_material_confirm", text="", icon='TRASH', emboss=True)
        op.material_name = mat.name

    def filter_items(self, context, data, propname):
        materials = getattr(data, propname)
        helper = bpy.types.UI_UL_list

        if self.filter_name:
            flt_flags = helper.filter_items_by_name(
                self.filter_name, self.bitflag_filter_item, materials, "name",
            )
        else:
            flt_flags = [self.bitflag_filter_item] * len(materials)

        scene = context.scene
        for i, mat in enumerate(materials):
            if not (flt_flags[i] & self.bitflag_filter_item):
                continue
            if not material_passes_layer_filter(scene, mat):
                flt_flags[i] &= ~self.bitflag_filter_item

        if self.use_filter_sort_alpha:
            flt_neworder = helper.sort_items_by_name(materials, "name")
        else:
            flt_neworder = []

        return flt_flags, flt_neworder


classes = (
    MATMGR_UL_materials,
)
