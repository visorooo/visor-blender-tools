import bpy


def _objects_using_material(context, material):
    found = []
    for obj in context.view_layer.objects:
        slots = getattr(obj, "material_slots", None)
        if not slots:
            continue
        for slot in slots:
            if slot.material == material:
                found.append(obj)
                break
    return found


def _assign_material_to_object(obj, material):
    if not hasattr(obj, "material_slots"):
        return False
    if len(obj.material_slots) == 0:
        if not hasattr(obj.data, "materials"):
            return False
        obj.data.materials.append(material)
    else:
        obj.active_material = material
    return True


class MATMGR_OT_select_material_row(bpy.types.Operator):
    bl_idname = "material_manager.select_material_row"
    bl_label = "Select Material"
    bl_description = "Click to select. Ctrl+Click to add/remove from selection. Shift+Click to select a range"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: bpy.props.StringProperty()

    def invoke(self, context, event):
        scene = context.scene
        materials = list(bpy.data.materials)

        try:
            clicked_index = next(i for i, m in enumerate(materials) if m.name == self.material_name)
        except StopIteration:
            return {'CANCELLED'}

        if event.shift:
            anchor = scene.material_manager_selection_anchor
            if anchor < 0 or anchor >= len(materials):
                anchor = clicked_index
            lo, hi = sorted((anchor, clicked_index))
            for i, mat in enumerate(materials):
                mat.matmgr_selected = lo <= i <= hi
        elif event.ctrl:
            materials[clicked_index].matmgr_selected = not materials[clicked_index].matmgr_selected
            scene.material_manager_selection_anchor = clicked_index
        else:
            was_sole_selection = (
                materials[clicked_index].matmgr_selected
                and sum(1 for m in materials if m.matmgr_selected) == 1
            )
            for mat in materials:
                mat.matmgr_selected = False
            if not was_sole_selection:
                materials[clicked_index].matmgr_selected = True
            scene.material_manager_selection_anchor = clicked_index

        scene.material_manager_index = clicked_index
        return {'FINISHED'}


class MATMGR_OT_select_users(bpy.types.Operator):
    bl_idname = "material_manager.select_users"
    bl_label = "Select Objects Using Material"
    bl_description = "Select every object in the scene that uses this material"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: bpy.props.StringProperty()

    def execute(self, context):
        mat = bpy.data.materials.get(self.material_name)
        if mat is None:
            self.report({'ERROR'}, f"Material '{self.material_name}' not found")
            return {'CANCELLED'}

        objs = _objects_using_material(context, mat)
        if not objs:
            self.report({'WARNING'}, f"No objects use '{mat.name}'")
            return {'CANCELLED'}

        for obj in context.view_layer.objects:
            obj.select_set(False)
        for obj in objs:
            obj.select_set(True)
        context.view_layer.objects.active = objs[0]

        self.report({'INFO'}, f"Selected {len(objs)} object(s) using '{mat.name}'")
        return {'FINISHED'}


class MATMGR_OT_assign_to_selected(bpy.types.Operator):
    bl_idname = "material_manager.assign_to_selected"
    bl_label = "Assign to Selected Objects"
    bl_description = "Assign this material to the active material slot of all selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def execute(self, context):
        mat = bpy.data.materials.get(self.material_name)
        if mat is None:
            self.report({'ERROR'}, f"Material '{self.material_name}' not found")
            return {'CANCELLED'}

        count = sum(1 for obj in context.selected_objects if _assign_material_to_object(obj, mat))

        if count == 0:
            self.report({'WARNING'}, "No selected objects can hold materials")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Assigned '{mat.name}' to {count} object(s)")
        return {'FINISHED'}


class MATMGR_OT_select_active_material_users(bpy.types.Operator):
    bl_idname = "material_manager.select_active_material_users"
    bl_label = "Select objects"
    bl_description = "Select every object in the scene that uses the highlighted material"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        idx = context.scene.material_manager_index
        return 0 <= idx < len(bpy.data.materials)

    def execute(self, context):
        mat = bpy.data.materials[context.scene.material_manager_index]
        return bpy.ops.material_manager.select_users(material_name=mat.name)


class MATMGR_OT_assign_active_material_to_selected(bpy.types.Operator):
    bl_idname = "material_manager.assign_active_material_to_selected"
    bl_label = "Assign to selected"
    bl_description = "Assign the highlighted material to the active slot of every selected object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        idx = context.scene.material_manager_index
        return 0 <= idx < len(bpy.data.materials) and len(context.selected_objects) > 0

    def execute(self, context):
        mat = bpy.data.materials[context.scene.material_manager_index]
        return bpy.ops.material_manager.assign_to_selected(material_name=mat.name)


class MATMGR_OT_delete_material(bpy.types.Operator):
    bl_idname = "material_manager.delete_material"
    bl_label = "Delete Material"
    bl_description = "Delete this material from the file and unlink it from every user"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: bpy.props.StringProperty()

    def execute(self, context):
        mat = bpy.data.materials.get(self.material_name)
        if mat is None:
            self.report({'ERROR'}, f"Material '{self.material_name}' not found")
            return {'CANCELLED'}

        name = mat.name
        bpy.data.materials.remove(mat, do_unlink=True)

        scene = context.scene
        if scene.material_manager_index >= len(bpy.data.materials):
            scene.material_manager_index = max(0, len(bpy.data.materials) - 1)

        self.report({'INFO'}, f"Deleted material '{name}'")
        return {'FINISHED'}


class MATMGR_OT_cancel_noop(bpy.types.Operator):
    bl_idname = "material_manager.cancel_noop"
    bl_label = "Cancel"
    bl_description = "Cancel"

    def execute(self, context):
        return {'CANCELLED'}


class MATMGR_OT_delete_material_confirm(bpy.types.Operator):
    bl_idname = "material_manager.delete_material_confirm"
    bl_label = "Delete Material?"
    bl_description = "Delete this material from the file (asks for confirmation)"
    bl_options = {'REGISTER'}

    material_name: bpy.props.StringProperty()

    def execute(self, context):
        return {'CANCELLED'}

    def invoke(self, context, event):
        material_name = self.material_name

        def draw(menu_self, menu_context):
            layout = menu_self.layout
            layout.label(text="Delete Material?", icon='ERROR')
            layout.separator()
            layout.operator_context = 'EXEC_DEFAULT'
            op = layout.operator("material_manager.delete_material", text="OK", icon='CHECKMARK')
            op.material_name = material_name
            layout.operator("material_manager.cancel_noop", text="Cancel", icon='X')

        context.window_manager.popup_menu(draw, title="")
        return {'FINISHED'}


class MATMGR_OT_new_material(bpy.types.Operator):
    bl_idname = "material_manager.new_material"
    bl_label = "New Material"
    bl_description = "Create a new material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mat = bpy.data.materials.new(name="Material")
        mat.use_nodes = True
        mat.preview_ensure()
        context.scene.material_manager_index = list(bpy.data.materials).index(mat)
        return {'FINISHED'}


class MATMGR_OT_purge_unused(bpy.types.Operator):
    bl_idname = "material_manager.purge_unused"
    bl_label = "Purge Unused Materials"
    bl_description = "Delete every material with zero users (fake-user materials are kept)"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        removed = 0
        for mat in list(bpy.data.materials):
            if mat.users == 0:
                bpy.data.materials.remove(mat)
                removed += 1

        if removed == 0:
            self.report({'INFO'}, "No unused materials found")
        else:
            context.scene.material_manager_index = 0
            self.report({'INFO'}, f"Purged {removed} unused material(s)")
        return {'FINISHED'}


class MATMGR_OT_delete_all(bpy.types.Operator):
    bl_idname = "material_manager.delete_all"
    bl_label = "Delete All Materials"
    bl_description = "Remove every material slot from every object and delete all materials from the file"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        for obj in bpy.data.objects:
            if hasattr(obj.data, "materials"):
                obj.data.materials.clear()
            for slot in obj.material_slots:
                slot.material = None

        removed = 0
        for mat in list(bpy.data.materials):
            bpy.data.materials.remove(mat, do_unlink=True)
            removed += 1

        context.scene.material_manager_index = 0
        self.report({'INFO'}, f"Deleted {removed} material(s) and cleared all slots")
        return {'FINISHED'}


classes = (
    MATMGR_OT_select_material_row,
    MATMGR_OT_select_users,
    MATMGR_OT_assign_to_selected,
    MATMGR_OT_select_active_material_users,
    MATMGR_OT_assign_active_material_to_selected,
    MATMGR_OT_delete_material,
    MATMGR_OT_cancel_noop,
    MATMGR_OT_delete_material_confirm,
    MATMGR_OT_new_material,
    MATMGR_OT_purge_unused,
    MATMGR_OT_delete_all,
)
