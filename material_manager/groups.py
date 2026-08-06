import bpy


def _unique_group_name(scene, base="Layer"):
    existing = {g.name for g in scene.material_manager_groups}
    if base not in existing:
        return base
    i = 1
    while f"{base}.{i:03d}" in existing:
        i += 1
    return f"{base}.{i:03d}"


def _ensure_filter_fallback(scene):
    """If nothing ends up active, fall back to 'All' so the list isn't empty by accident."""
    if not scene.material_manager_filter_all and not any(g.active for g in scene.material_manager_groups):
        scene.material_manager_filter_all = True


def _set_single_active_group(scene, index):
    for i, g in enumerate(scene.material_manager_groups):
        g.active = (i == index)
    scene.material_manager_filter_all = False
    scene.material_manager_group_index = index


class MATMGR_MaterialGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Layer Name", default="Layer")
    active: bpy.props.BoolProperty(name="Filter Active", default=False)


class MATMGR_OT_add_group(bpy.types.Operator):
    bl_idname = "material_manager.add_group"
    bl_label = "New Layer"
    bl_description = "Create a new material layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        name = _unique_group_name(scene)
        group = scene.material_manager_groups.add()
        group.name = name
        _set_single_active_group(scene, len(scene.material_manager_groups) - 1)
        return {'FINISHED'}


class MATMGR_OT_remove_group(bpy.types.Operator):
    bl_idname = "material_manager.remove_group"
    bl_label = "Remove Layer"
    bl_description = "Delete the current layer and unassign it from every material"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return 0 <= scene.material_manager_group_index < len(scene.material_manager_groups)

    def execute(self, context):
        scene = context.scene
        idx = scene.material_manager_group_index
        name = scene.material_manager_groups[idx].name

        for mat in bpy.data.materials:
            if mat.matmgr_group == name:
                mat.matmgr_group = ""

        scene.material_manager_groups.remove(idx)
        scene.material_manager_group_index = max(0, min(idx, len(scene.material_manager_groups) - 1))

        _ensure_filter_fallback(scene)
        self.report({'INFO'}, f"Removed layer '{name}'")
        return {'FINISHED'}


class MATMGR_OT_rename_group(bpy.types.Operator):
    bl_idname = "material_manager.rename_group"
    bl_label = "Rename Layer"
    bl_description = "Rename the current layer"
    bl_options = {'REGISTER', 'UNDO'}

    new_name: bpy.props.StringProperty(name="Name")

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return 0 <= scene.material_manager_group_index < len(scene.material_manager_groups)

    def invoke(self, context, event):
        scene = context.scene
        self.new_name = scene.material_manager_groups[scene.material_manager_group_index].name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        scene = context.scene
        group = scene.material_manager_groups[scene.material_manager_group_index]
        old_name = group.name
        new_name = self.new_name.strip()

        if not new_name:
            self.report({'ERROR'}, "Name cannot be empty")
            return {'CANCELLED'}

        group.name = new_name
        for mat in bpy.data.materials:
            if mat.matmgr_group == old_name:
                mat.matmgr_group = new_name

        return {'FINISHED'}


class MATMGR_OT_set_filter_all(bpy.types.Operator):
    bl_idname = "material_manager.set_filter_all"
    bl_label = "All"
    bl_description = "Show every material, regardless of layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        scene.material_manager_filter_all = True
        for g in scene.material_manager_groups:
            g.active = False
        return {'FINISHED'}


class MATMGR_OT_set_filter_layer(bpy.types.Operator):
    bl_idname = "material_manager.set_filter_layer"
    bl_label = "Filter by This Layer"
    bl_description = "Show only materials on this layer"
    bl_options = {'REGISTER', 'UNDO'}

    group_index: bpy.props.IntProperty()

    def execute(self, context):
        scene = context.scene
        if not (0 <= self.group_index < len(scene.material_manager_groups)):
            return {'CANCELLED'}
        _set_single_active_group(scene, self.group_index)
        return {'FINISHED'}


class MATMGR_OT_layer_filter_menu(bpy.types.Operator):
    bl_idname = "material_manager.layer_filter_menu"
    bl_label = "Filter by Layer"
    bl_description = "Choose which layer to view"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return {'CANCELLED'}

    def invoke(self, context, event):
        def draw(menu_self, menu_context):
            layout = menu_self.layout
            layout.operator("material_manager.set_filter_all", text="All", icon='MATERIAL')
            groups = menu_context.scene.material_manager_groups
            if groups:
                layout.separator()
                for i, g in enumerate(groups):
                    op = layout.operator("material_manager.set_filter_layer", text=g.name, icon='OUTLINER_COLLECTION')
                    op.group_index = i

            layout.separator()
            layout.operator("material_manager.add_group", text="New Layer", icon='ADD')
            if groups:
                layout.operator("material_manager.rename_group", text="Rename Current Layer", icon='GREASEPENCIL')
                layout.operator("material_manager.remove_group", text="Remove Current Layer", icon='REMOVE')

        context.window_manager.popup_menu(draw, title="Filter by Layer")
        return {'FINISHED'}


class MATMGR_OT_assign_selected_to_group(bpy.types.Operator):
    bl_idname = "material_manager.assign_selected_to_group"
    bl_label = "Move to Layer"
    bl_description = "Assign every selected material to this layer"
    bl_options = {'REGISTER', 'UNDO'}

    group_index: bpy.props.IntProperty()

    def execute(self, context):
        scene = context.scene
        if not (0 <= self.group_index < len(scene.material_manager_groups)):
            return {'CANCELLED'}
        group = scene.material_manager_groups[self.group_index]

        count = 0
        for mat in bpy.data.materials:
            if mat.matmgr_selected:
                mat.matmgr_group = group.name
                count += 1

        if count == 0:
            self.report({'WARNING'}, "No materials selected")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Moved {count} material(s) to '{group.name}'")
        return {'FINISHED'}


class MATMGR_OT_add_group_and_assign_selected(bpy.types.Operator):
    bl_idname = "material_manager.add_group_and_assign_selected"
    bl_label = "New Layer"
    bl_description = "Create a new layer and move every selected material into it"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        name = _unique_group_name(scene)
        group = scene.material_manager_groups.add()
        group.name = name
        _set_single_active_group(scene, len(scene.material_manager_groups) - 1)

        count = 0
        for mat in bpy.data.materials:
            if mat.matmgr_selected:
                mat.matmgr_group = name
                count += 1

        self.report({'INFO'}, f"Created '{name}' and moved {count} material(s) into it")
        return {'FINISHED'}


class MATMGR_OT_clear_group_from_selected(bpy.types.Operator):
    bl_idname = "material_manager.clear_group_from_selected"
    bl_label = "No Layer"
    bl_description = "Remove the layer assignment from every selected material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        count = 0
        for mat in bpy.data.materials:
            if mat.matmgr_selected and mat.matmgr_group:
                mat.matmgr_group = ""
                count += 1

        if count == 0:
            self.report({'WARNING'}, "No layered materials selected")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Cleared layer from {count} material(s)")
        return {'FINISHED'}


class MATMGR_OT_move_selected_to_layer_menu(bpy.types.Operator):
    bl_idname = "material_manager.move_selected_to_layer_menu"
    bl_label = "Move to Layer"
    bl_description = "Assign every selected material to a layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return {'CANCELLED'}

    def invoke(self, context, event):
        if not any(mat.matmgr_selected for mat in bpy.data.materials):
            self.report({'WARNING'}, "No materials selected")
            return {'CANCELLED'}

        def draw(menu_self, menu_context):
            layout = menu_self.layout
            layout.operator("material_manager.clear_group_from_selected", text="No Layer", icon='X')
            groups = menu_context.scene.material_manager_groups
            if groups:
                layout.separator()
                for i, g in enumerate(groups):
                    op = layout.operator(
                        "material_manager.assign_selected_to_group", text=g.name, icon='OUTLINER_COLLECTION',
                    )
                    op.group_index = i
            layout.separator()
            layout.operator("material_manager.add_group_and_assign_selected", text="New Layer...", icon='ADD')

        context.window_manager.popup_menu(draw, title="Move to Layer")
        return {'FINISHED'}


classes = (
    MATMGR_MaterialGroup,
    MATMGR_OT_add_group,
    MATMGR_OT_remove_group,
    MATMGR_OT_rename_group,
    MATMGR_OT_set_filter_all,
    MATMGR_OT_set_filter_layer,
    MATMGR_OT_layer_filter_menu,
    MATMGR_OT_assign_selected_to_group,
    MATMGR_OT_add_group_and_assign_selected,
    MATMGR_OT_clear_group_from_selected,
    MATMGR_OT_move_selected_to_layer_menu,
)
