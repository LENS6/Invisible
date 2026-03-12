bl_info = {
    "name": "Invisible",
    "author": "Lenslance",
    "version": (1, 0, 0),
    "blender": (4, 2, 6),
    "location": "View3D > Sidebar > Invisible",
    "description": "对象重命名和材质分配工具（Object renaming and material assignment tool）",
    "category": "Object",
}

import bpy
import re
import random
import colorsys
import json
import os
from bpy.props import (StringProperty, IntProperty, BoolProperty, FloatProperty,
                       EnumProperty, CollectionProperty, PointerProperty)
from bpy.types import Panel, Operator, PropertyGroup, UIList
from bpy_extras.io_utils import ExportHelper, ImportHelper

# ==================== 多语言字典 ====================

LANG = {
    # 主面板
    'panel_label': ("Invisible 工具", "Invisible Tools"),
    'renamer_box': ("对象重命名器", "Object Renamer"),
    'delimiter_label': ("分隔符:", "Delimiter:"),
    'name_parts_label': ("名称部分 (勾选=忽略分隔符):", "Name Parts (check=ignore delimiter):"),
    'add_part': ("添加部分", "Add Part"),
    'suffix_label': ("后缀:", "Suffix:"),
    'high_btn': ("High", "High"),
    'low_btn': ("Low", "Low"),
    'only_rename_special': ("仅重命名包含特殊字符的对象", "Rename Only Special"),
    'sync_mesh': ("同步数据名称", "Sync Data Name"),
    'sync_material': ("同步材质名称", "Sync Material Name"),
    'auto_detect': ("自动检测编号", "Auto-detect Number"),
    'start_number': ("起始编号:", "Start Number:"),
    'digits': ("数字位数:", "Digits:"),
    'apply_rename': ("应用重命名", "Apply Rename"),
    'reset_defaults': ("恢复默认设置", "Reset Defaults"),
    
    # 历史记录子面板
    'history_label': ("历史记录", "History"),
    'load_btn': ("加载", "Load"),
    'delete_btn': ("删除", "Delete"),
    'clear_history': ("清除所有历史", "Clear All History"),
    'clear_history_confirm': ("确定清除所有历史记录？", "Clear all history records?"),
    
    # 模板子面板
    'templates_label': ("模板", "Templates"),
    'save_template': ("保存模板", "Save Template"),
    'load_btn': ("加载", "Load"),
    'delete_btn': ("删除", "Delete"),
    'clear_templates': ("清除所有模板", "Clear All Templates"),
    'clear_templates_confirm': ("确定清除所有模板？", "Clear all templates?"),
    'export_templates': ("导出模板", "Export Templates"),
    'import_templates': ("导入模板", "Import Templates"),
    
    # 材质分配器子面板
    'material_label': ("材质分配器", "Material Assigner"),
    'assign_material': ("分配材质", "Assign Materials"),
    
    # 材质分配器对话框
    'random_colors': ("随机颜色", "Random Colors"),
    'color_mode': ("颜色模式", "Color Mode"),
    'golden': ("黄金比例", "Golden Ratio"),
    'hsv': ("HSV 区分", "HSV Distinct"),
    'rgb': ("RGB 随机", "RGB Random"),
    'saturation': ("饱和度", "Saturation"),
    'value': ("亮度", "Value"),
    'force_new': ("强制创建新材质", "Force New"),
    
    # 操作符消息
    'no_objects': ("没有选中的对象", "No objects selected"),
    'no_mesh': ("没有选中的网格对象", "No mesh objects selected"),
    'no_name_parts': ("没有指定名称部分", "No name parts specified"),
    'synced_data': ("已同步 {} 个数据名称", "Synced {} data names"),
    'renamed': ("已重命名 {} 个对象", "Renamed {} objects"),
    'assigned': ("已为 {} 个对象分配材质", "Assigned materials to {} objects"),
    'template_name_empty': ("模板名称不能为空", "Template name cannot be empty"),
    'history_cleared': ("已清除所有历史记录", "Cleared all history"),
    'templates_cleared': ("已清除所有模板", "Cleared all templates"),
    'templates_exported': ("已导出 {} 个模板", "Exported {} templates"),
    'templates_imported': ("已导入 {} 个模板", "Imported {} templates"),
    'file_not_selected': ("未选择文件", "No file selected"),
    'invalid_file': ("无效的模板文件", "Invalid template file"),
    'bones_cleaned': ("已清理骨骼名称中的 .001 后缀", "Cleaned .001 suffix from bone names"),
}

# ==================== 语言检测函数 ====================

def is_chinese():
    locale = bpy.app.translations.locale
    return locale.startswith('zh')

def get_text(msg_id):
    text_tuple = LANG.get(msg_id, (msg_id, msg_id))
    return text_tuple[0] if is_chinese() else text_tuple[1]

# ==================== 辅助函数 ====================

def get_current_blend_name():
    filepath = bpy.data.filepath
    if filepath:
        return bpy.path.basename(filepath).rsplit('.', 1)[0]
    return "Untitled"

def copy_name_parts(src_parts, dst_parts):
    dst_parts.clear()
    for part in src_parts:
        new_part = dst_parts.add()
        new_part.name_part = part.name_part
        new_part.ignore_delimiter_after = part.ignore_delimiter_after

def get_name_pattern(props):
    name_parts_info = [(item.name_part, item.ignore_delimiter_after)
                       for item in props.name_parts if item.name_part]
    if not name_parts_info:
        return None, None

    delimiter = props.delimiter
    suffix = props.suffix
    ignore_delimiter_before_suffix = props.ignore_delimiter_before_suffix

    prefix_parts = []
    for i, (name_part, ignore_delimiter) in enumerate(name_parts_info):
        prefix_parts.append(name_part)
        if i < len(name_parts_info) - 1 and not ignore_delimiter:
            prefix_parts.append(delimiter)
    if name_parts_info and not name_parts_info[-1][1]:
        prefix_parts.append(delimiter)
    prefix = "".join(prefix_parts)

    suffix_parts = []
    if suffix:
        if not ignore_delimiter_before_suffix:
            suffix_parts.append(delimiter)
        suffix_parts.append(suffix)
    suffix_str = "".join(suffix_parts)

    prefix_esc = re.escape(prefix)
    suffix_esc = re.escape(suffix_str)
    return prefix_esc, suffix_esc

def clean_bone_names(armature_obj):
    """清理骨架对象中所有骨骼名称的 .001 后缀，确保名称唯一且无 .001"""
    if not armature_obj or armature_obj.type != 'ARMATURE':
        return
    bones = armature_obj.data.bones
    renamed_count = 0
    # 先收集所有现有骨骼名
    existing_names = set(b.name for b in bones)
    for bone in bones:
        # 匹配末尾的 .001, .002 等
        m = re.search(r'\.\d{3}$', bone.name)
        if m:
            base = bone.name[:m.start()]
            new_name = base
            # 如果 base 已存在，则需要添加其他标识（这里简单添加 _01 等）
            if new_name in existing_names:
                # 寻找不重复的名称
                suffix = 1
                while f"{base}_{suffix:02d}" in existing_names:
                    suffix += 1
                new_name = f"{base}_{suffix:02d}"
            # 重命名
            if new_name != bone.name:
                bone.name = new_name
                existing_names.add(new_name)
                existing_names.discard(bone.name)  # 移除旧名
                renamed_count += 1
    return renamed_count

# ==================== 属性组 ====================

class NamePartProperty(PropertyGroup):
    name_part: StringProperty(
        name="Name Part",
        description="名称的一部分",
        default=""
    )
    ignore_delimiter_after: BoolProperty(
        name="Ignore Delimiter",
        description="勾选后忽略此部分后的分隔符",
        default=False
    )

class HistoryItem(PropertyGroup):
    name: StringProperty(name="Record Name", default="未命名")
    delimiter: StringProperty(default="_")
    suffix: StringProperty(default="")
    ignore_delimiter_before_suffix: BoolProperty(default=False)
    only_rename_special: BoolProperty(default=False)
    sync_mesh_name: BoolProperty(default=True)
    sync_material_name: BoolProperty(default=False)
    start_number: IntProperty(default=1)
    digits: IntProperty(default=2)
    auto_detect_number: BoolProperty(default=True)
    name_parts: CollectionProperty(type=NamePartProperty)

class TemplateItem(PropertyGroup):
    name: StringProperty(name="Template Name", default="模板")
    delimiter: StringProperty(default="_")
    suffix: StringProperty(default="")
    ignore_delimiter_before_suffix: BoolProperty(default=False)
    only_rename_special: BoolProperty(default=False)
    sync_mesh_name: BoolProperty(default=True)
    sync_material_name: BoolProperty(default=False)
    start_number: IntProperty(default=1)
    digits: IntProperty(default=2)
    auto_detect_number: BoolProperty(default=True)
    name_parts: CollectionProperty(type=NamePartProperty)

class MYNAME_Properties(PropertyGroup):
    delimiter: StringProperty(
        name="Delimiter",
        description="名称部分之间的分隔符",
        default="_"
    )
    suffix: StringProperty(
        name="Suffix",
        description="对象名称后缀",
        default=""
    )
    ignore_delimiter_before_suffix: BoolProperty(
        name="Ignore Delimiter before Suffix",
        description="勾选后忽略后缀前的分隔符",
        default=False
    )
    only_rename_special: BoolProperty(
        name="Rename Only Special",
        description="如果启用，只重命名包含中文或特殊字符的对象",
        default=False
    )
    sync_mesh_name: BoolProperty(
        name="Sync Data Name",
        description="同时更新对象的数据名称（网格、曲线、相机、骨架等）",
        default=True
    )
    sync_material_name: BoolProperty(
        name="Sync Material Name",
        description="将选中物体的材质名称改为物体名称",
        default=False
    )
    start_number: IntProperty(
        name="Start Number",
        description="编号的起始数字（当未启用自动检测时使用）",
        default=1,
        min=0
    )
    digits: IntProperty(
        name="Digits",
        description="编号的数字位数（如2表示01,02,...）",
        default=2,
        min=1,
        max=4
    )
    auto_detect_number: BoolProperty(
        name="Auto-detect Number",
        description="自动查找场景中最大编号并递增",
        default=True
    )

    name_parts: CollectionProperty(type=NamePartProperty)
    active_name_part_index: IntProperty(default=0)

    history: CollectionProperty(type=HistoryItem)
    templates: CollectionProperty(type=TemplateItem)
    active_history_index: IntProperty(default=0)
    active_template_index: IntProperty(default=0)

# ==================== 重命名功能 ====================

def contains_chinese(text):
    return any('\u4e00' <= char <= '\u9fff' for char in text)

def contains_special_chars(text):
    return bool(re.search(r'[^a-zA-Z0-9_\-\.]', text))

class MYNAME_OT_add_name_part(Operator):
    bl_idname = "myname.add_name_part"
    bl_label = "Add Name Part"
    
    def execute(self, context):
        context.scene.myname_tools.name_parts.add()
        return {'FINISHED'}

class MYNAME_OT_remove_name_part(Operator):
    bl_idname = "myname.remove_name_part"
    bl_label = "Remove"
    
    index: IntProperty(default=-1)
    
    def execute(self, context):
        props = context.scene.myname_tools
        idx = self.index if self.index != -1 else props.active_name_part_index
        if props.name_parts and 0 <= idx < len(props.name_parts):
            props.name_parts.remove(idx)
            props.active_name_part_index = min(idx, len(props.name_parts)-1) if props.name_parts else 0
        return {'FINISHED'}

class MYNAME_OT_move_name_part(Operator):
    bl_idname = "myname.move_name_part"
    bl_label = "Move"
    
    direction: EnumProperty(items=[('UP', 'Up', ''), ('DOWN', 'Down', '')])
    index: IntProperty()
    
    def execute(self, context):
        props = context.scene.myname_tools
        if not props.name_parts:
            return {'CANCELLED'}
        idx = self.index
        if self.direction == 'UP' and idx > 0:
            props.name_parts.move(idx, idx-1)
            props.active_name_part_index = idx-1
        elif self.direction == 'DOWN' and idx < len(props.name_parts)-1:
            props.name_parts.move(idx, idx+1)
            props.active_name_part_index = idx+1
        return {'FINISHED'}

class MYNAME_OT_set_suffix_high(Operator):
    bl_idname = "myname.set_suffix_high"
    bl_label = "High"
    
    def execute(self, context):
        context.scene.myname_tools.suffix = "high"
        return {'FINISHED'}

class MYNAME_OT_set_suffix_low(Operator):
    bl_idname = "myname.set_suffix_low"
    bl_label = "Low"
    
    def execute(self, context):
        context.scene.myname_tools.suffix = "low"
        return {'FINISHED'}

class MYNAME_OT_rename_objects(Operator):
    bl_idname = "object.myname_rename_objects"
    bl_label = "Rename Objects"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        props = scene.myname_tools
        
        name_parts_info = [(item.name_part, item.ignore_delimiter_after)
                           for item in props.name_parts if item.name_part]
        
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'WARNING'}, get_text('no_objects'))
            return {'CANCELLED'}
        
        if not name_parts_info:
            if props.sync_mesh_name:
                synced = 0
                for obj in selected_objects:
                    if hasattr(obj, 'data') and obj.data and hasattr(obj.data, 'name'):
                        obj.data.name = obj.name
                        synced += 1
                self.report({'INFO'}, get_text('synced_data').format(synced))
                return {'FINISHED'}
            else:
                self.report({'WARNING'}, get_text('no_name_parts'))
                return {'CANCELLED'}
        
        start_num = props.start_number
        if props.auto_detect_number:
            prefix_esc, suffix_esc = get_name_pattern(props)
            if prefix_esc is not None:
                pattern = prefix_esc + r'(\d+)' + suffix_esc
                max_num = 0
                for obj in bpy.data.objects:
                    match = re.fullmatch(pattern, obj.name)
                    if match:
                        try:
                            num = int(match.group(1))
                            if num > max_num:
                                max_num = num
                        except:
                            pass
                start_num = max_num + 1
            else:
                start_num = 1
        
        counter = start_num
        renamed_count = 0
        data_synced_count = 0
        for obj in selected_objects:
            original_name = obj.name
            
            if props.only_rename_special:
                has_chinese = contains_chinese(original_name)
                has_special = contains_special_chars(original_name)
                if not (has_chinese or has_special):
                    continue
            
            new_parts = []
            for i, (name_part, ignore_delimiter) in enumerate(name_parts_info):
                new_parts.append(name_part)
                if i < len(name_parts_info)-1 and not ignore_delimiter:
                    new_parts.append(props.delimiter)
            if name_parts_info and not name_parts_info[-1][1]:
                new_parts.append(props.delimiter)
            number_str = f"{counter:0{props.digits}d}"
            new_parts.append(number_str)
            if props.suffix:
                if not props.ignore_delimiter_before_suffix:
                    new_parts.append(props.delimiter)
                new_parts.append(props.suffix)
            new_name = "".join(new_parts)
            
            # 重命名对象
            obj.name = new_name
            
            # 同步数据名称（所有类型）
            if props.sync_mesh_name and hasattr(obj, 'data') and obj.data and hasattr(obj.data, 'name'):
                try:
                    obj.data.name = new_name
                    data_synced_count += 1
                except:
                    pass  # 某些数据可能不可写
            
            # 同步材质名称
            if props.sync_material_name and obj.type == 'MESH' and obj.data.materials:
                for mat_slot in obj.material_slots:
                    if mat_slot.material:
                        try:
                            mat_slot.material.name = obj.name
                        except:
                            pass
            
            # 特殊处理骨架：清理骨骼名称中的 .001 后缀
            if obj.type == 'ARMATURE' and props.sync_mesh_name:
                cleaned = clean_bone_names(obj)
                if cleaned:
                    self.report({'INFO'}, get_text('bones_cleaned'))
            
            renamed_count += 1
            counter += 1
        
        if renamed_count > 0:
            self.save_history(context, props)
        
        self.report({'INFO'}, get_text('renamed').format(renamed_count))
        return {'FINISHED'}
    
    def save_history(self, context, props):
        history = props.history
        item = history.add()
        from datetime import datetime
        blend_name = get_current_blend_name()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item.name = f"{blend_name} - {timestamp}"
        item.delimiter = props.delimiter
        item.suffix = props.suffix
        item.ignore_delimiter_before_suffix = props.ignore_delimiter_before_suffix
        item.only_rename_special = props.only_rename_special
        item.sync_mesh_name = props.sync_mesh_name
        item.sync_material_name = props.sync_material_name
        item.start_number = props.start_number
        item.digits = props.digits
        item.auto_detect_number = props.auto_detect_number
        copy_name_parts(props.name_parts, item.name_parts)
        
        if len(history) > 20:
            history.remove(0)

# ==================== 历史记录与模板操作 ====================

class MYNAME_OT_load_history(Operator):
    bl_idname = "myname.load_history"
    bl_label = "Load History"
    
    index: IntProperty()
    
    def execute(self, context):
        props = context.scene.myname_tools
        if self.index < 0 or self.index >= len(props.history):
            return {'CANCELLED'}
        hist = props.history[self.index]
        props.delimiter = hist.delimiter
        props.suffix = hist.suffix
        props.ignore_delimiter_before_suffix = hist.ignore_delimiter_before_suffix
        props.only_rename_special = hist.only_rename_special
        props.sync_mesh_name = hist.sync_mesh_name
        props.sync_material_name = hist.sync_material_name
        props.start_number = hist.start_number
        props.digits = hist.digits
        props.auto_detect_number = hist.auto_detect_number
        copy_name_parts(hist.name_parts, props.name_parts)
        return {'FINISHED'}

class MYNAME_OT_delete_history(Operator):
    bl_idname = "myname.delete_history"
    bl_label = "Delete History"
    
    index: IntProperty()
    
    def execute(self, context):
        props = context.scene.myname_tools
        if 0 <= self.index < len(props.history):
            props.history.remove(self.index)
        return {'FINISHED'}

class MYNAME_OT_clear_history(Operator):
    bl_idname = "myname.clear_history"
    bl_label = "Clear History"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def description(cls, context, properties):
        return get_text('clear_history')
    
    def execute(self, context):
        props = context.scene.myname_tools
        props.history.clear()
        self.report({'INFO'}, get_text('history_cleared'))
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

class MYNAME_OT_save_template(Operator):
    bl_idname = "myname.save_template"
    bl_label = "Save Template"
    bl_options = {'REGISTER', 'UNDO'}
    
    template_name: StringProperty(name="Template Name", default="New Template")
    
    def execute(self, context):
        props = context.scene.myname_tools
        if not self.template_name.strip():
            self.report({'WARNING'}, get_text('template_name_empty'))
            return {'CANCELLED'}
        templ = props.templates.add()
        templ.name = self.template_name
        templ.delimiter = props.delimiter
        templ.suffix = props.suffix
        templ.ignore_delimiter_before_suffix = props.ignore_delimiter_before_suffix
        templ.only_rename_special = props.only_rename_special
        templ.sync_mesh_name = props.sync_mesh_name
        templ.sync_material_name = props.sync_material_name
        templ.start_number = props.start_number
        templ.digits = props.digits
        templ.auto_detect_number = props.auto_detect_number
        copy_name_parts(props.name_parts, templ.name_parts)
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class MYNAME_OT_load_template(Operator):
    bl_idname = "myname.load_template"
    bl_label = "Load Template"
    
    index: IntProperty()
    
    def execute(self, context):
        props = context.scene.myname_tools
        if self.index < 0 or self.index >= len(props.templates):
            return {'CANCELLED'}
        templ = props.templates[self.index]
        props.delimiter = templ.delimiter
        props.suffix = templ.suffix
        props.ignore_delimiter_before_suffix = templ.ignore_delimiter_before_suffix
        props.only_rename_special = templ.only_rename_special
        props.sync_mesh_name = templ.sync_mesh_name
        props.sync_material_name = templ.sync_material_name
        props.start_number = templ.start_number
        props.digits = templ.digits
        props.auto_detect_number = templ.auto_detect_number
        copy_name_parts(templ.name_parts, props.name_parts)
        return {'FINISHED'}

class MYNAME_OT_delete_template(Operator):
    bl_idname = "myname.delete_template"
    bl_label = "Delete Template"
    
    index: IntProperty()
    
    def execute(self, context):
        props = context.scene.myname_tools
        if 0 <= self.index < len(props.templates):
            props.templates.remove(self.index)
        return {'FINISHED'}

class MYNAME_OT_clear_templates(Operator):
    bl_idname = "myname.clear_templates"
    bl_label = "Clear Templates"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def description(cls, context, properties):
        return get_text('clear_templates')
    
    def execute(self, context):
        props = context.scene.myname_tools
        props.templates.clear()
        self.report({'INFO'}, get_text('templates_cleared'))
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

class MYNAME_OT_export_templates(Operator, ExportHelper):
    bl_idname = "myname.export_templates"
    bl_label = "Export Templates"  # 修复：添加 bl_label
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    
    def execute(self, context):
        props = context.scene.myname_tools
        templates = []
        for templ in props.templates:
            t = {
                "name": templ.name,
                "delimiter": templ.delimiter,
                "suffix": templ.suffix,
                "ignore_delimiter_before_suffix": templ.ignore_delimiter_before_suffix,
                "only_rename_special": templ.only_rename_special,
                "sync_mesh_name": templ.sync_mesh_name,
                "sync_material_name": templ.sync_material_name,
                "start_number": templ.start_number,
                "digits": templ.digits,
                "auto_detect_number": templ.auto_detect_number,
                "name_parts": [(p.name_part, p.ignore_delimiter_after) for p in templ.name_parts]
            }
            templates.append(t)
        
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(templates, f, ensure_ascii=False, indent=2)
            self.report({'INFO'}, get_text('templates_exported').format(len(templates)))
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}

class MYNAME_OT_import_templates(Operator, ImportHelper):
    bl_idname = "myname.import_templates"
    bl_label = "Import Templates"  # 修复：添加 bl_label
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    
    def execute(self, context):
        props = context.scene.myname_tools
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, get_text('invalid_file') + ": " + str(e))
            return {'CANCELLED'}
        
        if not isinstance(data, list):
            self.report({'ERROR'}, get_text('invalid_file'))
            return {'CANCELLED'}
        
        imported = 0
        for item in data:
            templ = props.templates.add()
            templ.name = item.get("name", "Imported")
            templ.delimiter = item.get("delimiter", "_")
            templ.suffix = item.get("suffix", "")
            templ.ignore_delimiter_before_suffix = item.get("ignore_delimiter_before_suffix", False)
            templ.only_rename_special = item.get("only_rename_special", False)
            templ.sync_mesh_name = item.get("sync_mesh_name", True)
            templ.sync_material_name = item.get("sync_material_name", False)
            templ.start_number = item.get("start_number", 1)
            templ.digits = item.get("digits", 2)
            templ.auto_detect_number = item.get("auto_detect_number", True)
            for part_data in item.get("name_parts", []):
                if isinstance(part_data, (list, tuple)) and len(part_data) == 2:
                    p = templ.name_parts.add()
                    p.name_part = part_data[0]
                    p.ignore_delimiter_after = part_data[1]
            imported += 1
        
        self.report({'INFO'}, get_text('templates_imported').format(imported))
        return {'FINISHED'}

class MYNAME_OT_reset_defaults(Operator):
    bl_idname = "myname.reset_defaults"
    bl_label = "Reset Defaults"
    
    def execute(self, context):
        props = context.scene.myname_tools
        props.delimiter = "_"
        props.suffix = ""
        props.ignore_delimiter_before_suffix = False
        props.only_rename_special = False
        props.sync_mesh_name = True
        props.sync_material_name = False
        props.start_number = 1
        props.digits = 2
        props.auto_detect_number = True
        props.name_parts.clear()
        return {'FINISHED'}

# ==================== 材质分配功能 ====================

class MYNAME_OT_assign_materials(Operator):
    bl_idname = "object.myname_assign_materials"
    bl_label = "Assign Materials"
    bl_options = {'REGISTER', 'UNDO'}

    saturation: FloatProperty(name="Saturation", min=0.5, max=1.5, default=1.5)
    value: FloatProperty(name="Value", min=0.5, max=1.5, default=1.5)
    force_new: BoolProperty(name="Force New", default=False)
    random_colors: BoolProperty(name="Random Colors", default=True)
    distinct_mode: EnumProperty(
        name="Color Mode",
        items=[
            ('GOLDEN', "Golden Ratio", "Use golden ratio for maximum distinction"),
            ('HSV', "HSV Distinct", "Generate distinct hues"),
            ('RGB', "RGB Random", "Traditional random RGB"),
        ],
        default='GOLDEN'
    )

    def execute(self, context):
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_objects:
            self.report({'WARNING'}, get_text('no_mesh'))
            return {'CANCELLED'}
        
        count = 0
        golden_ratio = 0.618033988749895
        hue = random.random()
        
        for idx, obj in enumerate(selected_objects):
            material_name = obj.name
            mat = None
            material_exists = material_name in bpy.data.materials
            
            if not self.force_new and material_exists:
                mat = bpy.data.materials[material_name]
                if not mat.use_nodes:
                    mat.use_nodes = True
            else:
                if material_exists and self.force_new:
                    material_name = f"{obj.name}_{random.randint(1000,9999)}"
                mat = bpy.data.materials.new(name=material_name)
                mat.use_nodes = True
            
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.location = (0, 0)
            output = nodes.new('ShaderNodeOutputMaterial')
            output.location = (400, 0)
            links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
            
            if self.random_colors:
                if self.distinct_mode == 'GOLDEN':
                    hue = (hue + golden_ratio) % 1.0
                    s = min(1.0, max(0.0, 0.5 + random.random()*0.5)) * self.saturation
                    v = min(1.0, max(0.0, 0.7 + random.random()*0.3)) * self.value
                    r, g, b = colorsys.hsv_to_rgb(hue, s, v)
                elif self.distinct_mode == 'HSV':
                    h = idx / len(selected_objects)
                    s = min(1.0, max(0.0, 0.7 + random.random()*0.3)) * self.saturation
                    v = min(1.0, max(0.0, 0.8 + random.random()*0.2)) * self.value
                    r, g, b = colorsys.hsv_to_rgb(h, s, v)
                else:
                    r = random.random() * self.saturation
                    g = random.random() * self.saturation
                    b = random.random() * self.saturation
                    max_val = max(r, g, b)
                    min_val = min(r, g, b)
                    if max_val - min_val < 0.5:
                        if max_val == r:
                            r = min(1.0, r*1.5); g = max(0.0, g*0.7); b = max(0.0, b*0.7)
                        elif max_val == g:
                            g = min(1.0, g*1.5); r = max(0.0, r*0.7); b = max(0.0, b*0.7)
                        else:
                            b = min(1.0, b*1.5); r = max(0.0, r*0.7); g = max(0.0, g*0.7)
                r = min(1.0, max(0.0, r))
                g = min(1.0, max(0.0, g))
                b = min(1.0, max(0.0, b))
                bsdf.inputs['Base Color'].default_value = (r, g, b, 1.0)
            else:
                bsdf.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)
            
            obj.data.materials.clear()
            obj.data.materials.append(mat)
            count += 1
        
        self.report({'INFO'}, get_text('assigned').format(count))
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "random_colors", text=get_text('random_colors'))
        if self.random_colors:
            layout.prop(self, "distinct_mode", text=get_text('color_mode'), expand=True)
            row = layout.row(align=True)
            row.prop(self, "saturation", text=get_text('saturation'))
            row.prop(self, "value", text=get_text('value'))
        layout.prop(self, "force_new", text=get_text('force_new'))

# ==================== 自定义列表UI ====================

class MYNAME_UL_history(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon='TIME')
        else:
            layout.label(text="", icon='TIME')

class MYNAME_UL_templates(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon='FILE_TICK')
        else:
            layout.label(text="", icon='FILE_TICK')

# ==================== 主面板 ====================

class MYNAME_PT_main_panel(Panel):
    bl_label = "Invisible"
    bl_idname = "MYNAME_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Invisible"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.myname_tools
        
        # 重命名核心区域
        box = layout.box()
        box.label(text=get_text('renamer_box'), icon='SORTALPHA')
        
        row = box.row()
        row.label(text=get_text('delimiter_label'))
        row.prop(props, "delimiter", text="")
        
        box.label(text=get_text('name_parts_label'))
        for i, part in enumerate(props.name_parts):
            row = box.row(align=True)
            # 移动按钮
            if i > 0:
                op = row.operator("myname.move_name_part", text="", icon='TRIA_UP')
                op.direction = 'UP'
                op.index = i
            else:
                row.label(text="", icon='BLANK1')
            if i < len(props.name_parts)-1:
                op = row.operator("myname.move_name_part", text="", icon='TRIA_DOWN')
                op.direction = 'DOWN'
                op.index = i
            else:
                row.label(text="", icon='BLANK1')
            row.prop(part, "name_part", text="")
            op = row.operator("myname.remove_name_part", text="", icon='REMOVE')
            op.index = i
            if i < len(props.name_parts)-1:
                row.prop(part, "ignore_delimiter_after", text="", icon='CHECKBOX_HLT' if part.ignore_delimiter_after else 'CHECKBOX_DEHLT')
            else:
                row.prop(part, "ignore_delimiter_after", text="", icon='CHECKBOX_HLT' if part.ignore_delimiter_after else 'CHECKBOX_DEHLT')
        
        row = box.row()
        row.operator("myname.add_name_part", text=get_text('add_part'), icon='ADD')
        
        row = box.row(align=True)
        row.label(text=get_text('suffix_label'))
        row.prop(props, "suffix", text="")
        row.prop(props, "ignore_delimiter_before_suffix", text="", icon='CHECKBOX_HLT' if props.ignore_delimiter_before_suffix else 'CHECKBOX_DEHLT')
        
        row = box.row()
        row.operator("myname.set_suffix_high", text=get_text('high_btn'))
        row.operator("myname.set_suffix_low", text=get_text('low_btn'))
        
        box.prop(props, "only_rename_special", text=get_text('only_rename_special'))
        box.prop(props, "sync_mesh_name", text=get_text('sync_mesh'))
        box.prop(props, "sync_material_name", text=get_text('sync_material'))
        
        row = box.row()
        row.prop(props, "auto_detect_number", text=get_text('auto_detect'))
        if not props.auto_detect_number:
            row = box.row()
            row.label(text=get_text('start_number'))
            row.prop(props, "start_number", text="")
        row = box.row()
        row.label(text=get_text('digits'))
        row.prop(props, "digits", text="")
        
        box.operator("object.myname_rename_objects", text=get_text('apply_rename'), icon='SORTALPHA')
        box.operator("myname.reset_defaults", text=get_text('reset_defaults'), icon='LOOP_BACK')

# ==================== 子面板：历史记录 ====================
class MYNAME_PT_history(Panel):
    bl_label = "History"
    bl_idname = "MYNAME_PT_history"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Invisible"
    bl_parent_id = "MYNAME_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.myname_tools

        layout.label(text=get_text('history_label'))
        row = layout.row()
        row.template_list("MYNAME_UL_history", "", props, "history", props, "active_history_index", rows=3)
        col = row.column(align=True)
        if props.history:
            idx = props.active_history_index
            if 0 <= idx < len(props.history):
                op = col.operator("myname.load_history", text="", icon='IMPORT')
                op.index = idx
                op = col.operator("myname.delete_history", text="", icon='REMOVE')
                op.index = idx
        
        layout.operator("myname.clear_history", text=get_text('clear_history'), icon='TRASH')

# ==================== 子面板：模板 ====================
class MYNAME_PT_templates(Panel):
    bl_label = "Templates"
    bl_idname = "MYNAME_PT_templates"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Invisible"
    bl_parent_id = "MYNAME_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.myname_tools

        layout.label(text=get_text('templates_label'))
        row = layout.row()
        row.template_list("MYNAME_UL_templates", "", props, "templates", props, "active_template_index", rows=3)
        col = row.column(align=True)
        col.operator("myname.save_template", text="", icon='ADD')
        if props.templates:
            idx = props.active_template_index
            if 0 <= idx < len(props.templates):
                op = col.operator("myname.load_template", text="", icon='IMPORT')
                op.index = idx
                op = col.operator("myname.delete_template", text="", icon='REMOVE')
                op.index = idx
        
        row = layout.row(align=True)
        row.operator("myname.clear_templates", text=get_text('clear_templates'), icon='TRASH')
        row.operator("myname.export_templates", text=get_text('export_templates'), icon='EXPORT')
        row.operator("myname.import_templates", text=get_text('import_templates'), icon='IMPORT')

# ==================== 子面板：材质分配器 ====================
class MYNAME_PT_material(Panel):
    bl_label = "Material Assigner"
    bl_idname = "MYNAME_PT_material"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Invisible"
    bl_parent_id = "MYNAME_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.label(text=get_text('material_label'))
        layout.operator("object.myname_assign_materials", text=get_text('assign_material'), icon='MATERIAL_DATA')

# ==================== 注册 ====================

classes = (
    NamePartProperty,
    HistoryItem,
    TemplateItem,
    MYNAME_Properties,
    MYNAME_OT_add_name_part,
    MYNAME_OT_remove_name_part,
    MYNAME_OT_move_name_part,
    MYNAME_OT_set_suffix_high,
    MYNAME_OT_set_suffix_low,
    MYNAME_OT_rename_objects,
    MYNAME_OT_load_history,
    MYNAME_OT_delete_history,
    MYNAME_OT_clear_history,
    MYNAME_OT_save_template,
    MYNAME_OT_load_template,
    MYNAME_OT_delete_template,
    MYNAME_OT_clear_templates,
    MYNAME_OT_export_templates,
    MYNAME_OT_import_templates,
    MYNAME_OT_reset_defaults,
    MYNAME_OT_assign_materials,
    MYNAME_UL_history,
    MYNAME_UL_templates,
    MYNAME_PT_main_panel,
    MYNAME_PT_history,
    MYNAME_PT_templates,
    MYNAME_PT_material,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.myname_tools = PointerProperty(type=MYNAME_Properties)

def unregister():
    del bpy.types.Scene.myname_tools
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()