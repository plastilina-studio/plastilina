# SPDX-FileCopyrightText: 2026 Plastilina Studio
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Plastilina -- Interactive tutorials inside Blender
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# See <https://www.gnu.org/licenses/>



"""
Each lesson builds its own scene, so your own work is never touched. A timer
watches what you do and moves to the next step when the current one is done.
"""
import json
import math
import os
import textwrap
import time

import bmesh
import bpy
from bpy.app.handlers import persistent
from bpy.props import IntProperty
from mathutils import Euler

from .lessons import LESSONS, RANKS

STEP_XP = 10
LESSON_XP = 30
TAB = "Tutor"

STATE = {"lesson": None, "step": 0, "base": {}, "cube": "Cube", "complete": False,
         "hint": False, "flash": None, "gained": 0}
RENDERS = [0]


# ----------------------------------------------------------------- progress
def progress_path():
    return os.path.join(bpy.utils.extension_path_user(__package__, create=True), "progress.json")


def load_progress():
    try:
        with open(progress_path()) as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data.setdefault("xp", 0)
    data.setdefault("steps", [])
    data.setdefault("lessons", [])
    data.setdefault("welcomed", False)
    return data


PROGRESS = {}


def save_progress():
    try:
        with open(progress_path(), "w") as f:
            json.dump(PROGRESS, f, indent=1)
    except OSError as e:
        print("Plastilina: could not save progress:", e)


def rank():
    xp = PROGRESS["xp"]
    idx = max(i for i, (need, _) in enumerate(RANKS) if xp >= need)
    if idx + 1 < len(RANKS):
        lo, hi = RANKS[idx][0], RANKS[idx + 1][0]
        return RANKS[idx][1], (xp - lo) / (hi - lo), f"{xp} XP · {hi - xp} to {RANKS[idx + 1][1]}"
    return RANKS[idx][1], 1.0, f"{xp} XP · Top rank"


# -------------------------------------------------------------------- probe
def find_view3d(wm):
    best = None
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D" and (best is None or area.width * area.height > best.width * best.height):
                best = area
    if not best:
        return None, None
    space = best.spaces.active
    return space, space.region_3d


class Probe:
    """Snapshot of what the learner is looking at, passed to lesson checks."""

    def __init__(self):
        self.wm = bpy.context.window_manager
        win = self.wm.windows[0] if self.wm.windows else None
        self.scene = win.scene if win else bpy.data.scenes.get(STATE.get("scene", ""), bpy.context.scene)
        self.view_layer = win.view_layer if win else self.scene.view_layers[0]
        self.obj = self.view_layer.objects.active
        self.space, self.rv3d = find_view3d(self.wm)
        self.cube_name = STATE["cube"]

    def op_key(self):
        ops = self.wm.operators
        return (len(ops), ops[-1].as_pointer()) if len(ops) else (0, 0)

    @staticmethod
    def render_count():
        return RENDERS[0]


# --------------------------------------------------------------- lesson flow
def current_step():
    return LESSONS[STATE["lesson"]]["steps"][STATE["step"]]


def start_step(p=None):
    p = p or Probe()
    base = {"_op": p.op_key()}
    st = current_step()
    if st["start"]:
        st["start"](p, base)
    STATE["base"] = base
    STATE["hint"] = False


def advance(award=True):
    lesson = LESSONS[STATE["lesson"]]
    st = current_step()
    key = f"{lesson['id']}:{STATE['step']}"
    if award:
        gained = 0
        if key not in PROGRESS["steps"]:
            PROGRESS["steps"].append(key)
            gained = STEP_XP
            PROGRESS["xp"] += gained
            STATE["gained"] += gained
        STATE["flash"] = (f"{st['title']}: done!" + (f"  +{gained} XP" if gained else ""), time.time())
    else:
        STATE["flash"] = (f"Skipped “{st['title']}”", time.time())
    STATE["step"] += 1
    if STATE["step"] >= len(lesson["steps"]):
        STATE["complete"] = True
        if lesson["id"] not in PROGRESS["lessons"]:
            PROGRESS["lessons"].append(lesson["id"])
            PROGRESS["xp"] += LESSON_XP
            STATE["gained"] += LESSON_XP
    else:
        start_step()
    save_progress()
    redraw()


def redraw():
    wm = bpy.context.window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def tick():
    try:
        if STATE["lesson"] is not None and not STATE["complete"]:
            st = current_step()
            if st["check"](Probe(), STATE["base"]):
                advance()
        flash = STATE["flash"]
        if flash and time.time() - flash[1] > 3:
            STATE["flash"] = None
            redraw()
    except ReferenceError:
        pass  # an object was deleted mid-check; try again next tick
    except Exception as e:  # never let a lesson bug kill the timer
        print("Plastilina:", repr(e))
    return 0.3


def show_tutor_sidebar():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != "VIEW_3D":
                continue
            area.spaces.active.show_region_ui = True
            for region in area.regions:
                if region.type == "UI":
                    try:
                        region.active_panel_category = TAB
                    except (TypeError, AttributeError):
                        pass
            area.tag_redraw()


# ------------------------------------------------------------- scene setup
def build_scene(lesson):
    """Create a fresh scene for `lesson` and return it."""
    setup = lesson.get("setup", {})
    name = f"Tutor · {lesson['title']}"
    old = bpy.data.scenes.get(name)
    if old:
        old.name = name + " (old)"
    scn = bpy.data.scenes.new(name)
    try:
        scn.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scn.render.engine = "BLENDER_EEVEE_NEXT"
    scn.render.resolution_percentage = 50
    if hasattr(scn, "eevee"):
        scn.eevee.taa_render_samples = 16

    world = bpy.data.worlds.new(name)
    world.color = (0.05, 0.05, 0.05)
    if world.node_tree is None and hasattr(world, "use_nodes"):
        world.use_nodes = True
    if world.node_tree:
        bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
        if bg:
            bg.inputs["Color"].default_value = (0.05, 0.05, 0.06, 1)
            bg.inputs["Strength"].default_value = 0.4 if setup.get("light", True) else 0.15
    scn.world = world

    me = bpy.data.meshes.new("Cube")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2)
    bm.to_mesh(me)
    bm.free()
    cube = bpy.data.objects.new("Cube", me)
    scn.collection.objects.link(cube)
    if setup.get("material"):
        mat = bpy.data.materials.new("Tutor Blue")
        if mat.node_tree is None and hasattr(mat, "use_nodes"):
            mat.use_nodes = True
        node = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if node:
            node.inputs["Base Color"].default_value = (0.21, 0.52, 0.89, 1)
            node.inputs["Roughness"].default_value = 0.35
        me.materials.append(mat)
        me.polygons.foreach_set("use_smooth", [False] * len(me.polygons))

    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.location = (7.36, -6.93, 4.96)
    cam.rotation_euler = (math.radians(63.6), 0, math.radians(46.7))
    scn.collection.objects.link(cam)
    scn.camera = cam

    if setup.get("light", True):
        data = bpy.data.lights.new("Light", "POINT")
        data.energy = 1000
        light = bpy.data.objects.new("Light", data)
        light.location = (4.08, 1.0, 5.9)
        scn.collection.objects.link(light)

    vl = scn.view_layers[0]
    for o in scn.objects:
        o.select_set(False, view_layer=vl)
    if setup.get("select_cube"):
        cube.select_set(True, view_layer=vl)
        vl.objects.active = cube
    STATE["cube"] = cube.name
    STATE["scene"] = scn.name
    return scn, old


def remove_scene(scn):
    for o in list(scn.objects):
        if o.users <= 1:
            bpy.data.objects.remove(o)
    bpy.data.scenes.remove(scn)


def reset_view(context):
    space, rv3d = find_view3d(context.window_manager)
    if not rv3d:
        return
    if rv3d.view_perspective == "CAMERA":
        rv3d.view_perspective = "PERSP"
    rv3d.view_perspective = "PERSP"
    rv3d.view_rotation = Euler((math.radians(62), 0, math.radians(40))).to_quaternion()
    rv3d.view_location = (0, 0, 0)
    rv3d.view_distance = 14
    space.shading.type = "SOLID"


# ---------------------------------------------------------------- operators
class TUTOR_OT_start_lesson(bpy.types.Operator):
    """Start this lesson in its own fresh scene"""
    bl_idname = "tutor.start_lesson"
    bl_label = "Start Lesson"
    bl_options = {"INTERNAL"}

    index: IntProperty()

    def execute(self, context):
        if context.object and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        lesson = LESSONS[self.index]
        scn, old = build_scene(lesson)
        if context.window:
            context.window.scene = scn
        if old:
            remove_scene(old)
        reset_view(context)
        STATE.update(lesson=self.index, step=0, complete=False, gained=0, flash=None)
        start_step()
        show_tutor_sidebar()
        redraw()
        return {"FINISHED"}


class TUTOR_OT_skip(bpy.types.Operator):
    """Skip this step (no XP)"""
    bl_idname = "tutor.skip"
    bl_label = "Skip Step"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        if STATE["lesson"] is not None and not STATE["complete"]:
            advance(award=False)
        return {"FINISHED"}


class TUTOR_OT_hint(bpy.types.Operator):
    """Show a hint for this step"""
    bl_idname = "tutor.hint"
    bl_label = "Hint"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        STATE["hint"] = not STATE["hint"]
        redraw()
        return {"FINISHED"}


class TUTOR_OT_exit(bpy.types.Operator):
    """Leave the lesson and return to the lesson list"""
    bl_idname = "tutor.exit"
    bl_label = "Back to Lessons"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        STATE.update(lesson=None, complete=False, flash=None)
        redraw()
        return {"FINISHED"}


class TUTOR_OT_open(bpy.types.Operator):
    """Open the interactive Blender tutorial in the 3D Viewport sidebar"""
    bl_idname = "tutor.open"
    bl_label = "Interactive Tutorial"

    def execute(self, context):
        show_tutor_sidebar()
        self.report({"INFO"}, "Plastilina is open in the sidebar (N ▸ Tutor)")
        return {"FINISHED"}


class TUTOR_OT_reset(bpy.types.Operator):
    """Erase all tutorial XP and completed lessons"""
    bl_idname = "tutor.reset"
    bl_label = "Reset Progress"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event, title="Reset Tutorial Progress?",
                                                     message="All XP and completed lessons will be erased.",
                                                     confirm_text="Reset", icon="WARNING")

    def execute(self, context):
        PROGRESS.update(xp=0, steps=[], lessons=[])
        save_progress()
        redraw()
        return {"FINISHED"}


# -------------------------------------------------------------------- panel
def wrapped(layout, context, text, icon="NONE"):
    width = context.region.width if context.region else 300
    chars = max(18, int((width - 40) / (6.3 * context.preferences.system.ui_scale)))
    col = layout.column(align=True)
    for i, line in enumerate(textwrap.wrap(text, chars)):
        col.label(text=line, icon=icon if i == 0 else "BLANK1" if icon != "NONE" else "NONE")
    return col


class TUTOR_PT_main(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = TAB
    bl_label = "Plastilina"

    def draw(self, context):
        if STATE["lesson"] is None:
            self.draw_menu(context)
        elif STATE["complete"]:
            self.draw_complete(context)
        else:
            self.draw_step(context)

    def draw_rank(self, layout):
        name, frac, text = rank()
        box = layout.box()
        box.label(text=name, icon="SOLO_ON")
        box.progress(factor=frac, text=text)

    def draw_menu(self, context):
        layout = self.layout
        self.draw_rank(layout)
        wrapped(layout, context, "Pick a lesson. Each one opens in its own scene, so your work is safe. "
                                 "Steps complete automatically when you do them.")
        for i, lesson in enumerate(LESSONS):
            done = lesson["id"] in PROGRESS["lessons"]
            box = layout.box()
            row = box.row()
            row.label(text=f"{i + 1}. {lesson['title']}", icon="CHECKMARK" if done else "RADIOBUT_OFF")
            row.operator("tutor.start_lesson", text="Replay" if done else "Start",
                         icon="LOOP_BACK" if done else "PLAY").index = i
            wrapped(box, context, lesson["summary"]).enabled = False
        layout.separator()
        layout.operator("tutor.reset", icon="TRASH", emboss=False)

    def draw_step(self, context):
        layout = self.layout
        lesson = LESSONS[STATE["lesson"]]
        steps = lesson["steps"]
        st = current_step()
        row = layout.row()
        row.label(text=lesson["title"], icon="HELP")
        row.operator("tutor.exit", text="", icon="X", emboss=False)
        layout.progress(factor=STATE["step"] / len(steps), text=f"Step {STATE['step'] + 1} of {len(steps)}")

        if STATE["flash"]:
            layout.box().label(text=STATE["flash"][0], icon="CHECKMARK")

        box = layout.box()
        title = box.row()
        title.scale_y = 1.4
        title.label(text=st["title"], icon="TRIA_RIGHT")
        wrapped(box, context, st["text"])
        if st["keys"]:
            box.label(text=st["keys"], icon="KEYINGSET")
        if st["hint"] and STATE["hint"]:
            wrapped(box.box(), context, st["hint"], icon="INFO")
        row = box.row(align=True)
        if st["hint"]:
            row.operator("tutor.hint", text="Hide Hint" if STATE["hint"] else "Hint", icon="QUESTION")
        row.operator("tutor.skip", icon="FORWARD")

        col = layout.column(align=True)
        for i, s in enumerate(steps):
            icon = "CHECKMARK" if i < STATE["step"] else "TRIA_RIGHT" if i == STATE["step"] else "RADIOBUT_OFF"
            r = col.row()
            r.enabled = i <= STATE["step"]
            r.label(text=s["title"], icon=icon)

    def draw_complete(self, context):
        layout = self.layout
        lesson = LESSONS[STATE["lesson"]]
        box = layout.box()
        r = box.row()
        r.scale_y = 1.5
        r.label(text="Lesson Complete!", icon="SOLO_ON")
        wrapped(box, context, f"You finished “{lesson['title']}”." +
                (f" +{STATE['gained']} XP" if STATE["gained"] else " (already completed before, no new XP)"))
        self.draw_rank(layout)
        nxt = STATE["lesson"] + 1
        if nxt < len(LESSONS):
            row = layout.row()
            row.scale_y = 1.4
            row.operator("tutor.start_lesson", text=f"Next: {LESSONS[nxt]['title']}", icon="PLAY").index = nxt
        else:
            wrapped(layout, context, "That's every lesson! Try modeling something of your own, like a mug, "
                                     "a table or a little house, using what you learned.", icon="INFO")
        layout.operator("tutor.exit", icon="TRIA_LEFT")


# ----------------------------------------------------------------- handlers
@persistent
def on_render_complete(*_):
    RENDERS[0] += 1


@persistent
def on_load_post(*_):
    STATE.update(lesson=None, complete=False, flash=None)


def welcome():
    if not PROGRESS.get("welcomed") and bpy.context.window_manager.windows:
        show_tutor_sidebar()
        PROGRESS["welcomed"] = True
        save_progress()
    return None


def help_menu(self, context):
    self.layout.separator()
    self.layout.operator("tutor.open", icon="HELP")


CLASSES = (TUTOR_OT_start_lesson, TUTOR_OT_skip, TUTOR_OT_hint, TUTOR_OT_exit, TUTOR_OT_open,
           TUTOR_OT_reset, TUTOR_PT_main)


def register():
    PROGRESS.clear()
    PROGRESS.update(load_progress())
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_help.append(help_menu)
    bpy.app.handlers.render_complete.append(on_render_complete)
    bpy.app.handlers.load_post.append(on_load_post)
    bpy.app.timers.register(tick, first_interval=1.0, persistent=True)
    bpy.app.timers.register(welcome, first_interval=1.5)


def unregister():
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
    if bpy.app.timers.is_registered(welcome):
        bpy.app.timers.unregister(welcome)
    for lst, fn in ((bpy.app.handlers.render_complete, on_render_complete),
                    (bpy.app.handlers.load_post, on_load_post)):
        if fn in lst:
            lst.remove(fn)
    bpy.types.TOPBAR_MT_help.remove(help_menu)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
