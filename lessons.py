# SPDX-FIleCopyrightText: 2026 Plastilina Studio
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Plastilina -- Interactive tutorials inside Blender
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# See <https://www.gnu.org/licenses/>


"""Lesson content for Blender Tutor.

Each step has a title, instructions, optional keys and hint, and two callables:
  start(p, base) -> record a baseline when the step begins (optional)
  check(p, base) -> True once the learner has done the thing
`p` is a Probe (see __init__.py) giving the scene, active object, 3D view, etc.
"""
import bmesh


# ------------------------------------------------------------------ helpers
def norm_op(name):
    """'MESH_OT_inset' -> 'mesh.inset'."""
    if "_OT_" in name:
        a, b = name.split("_OT_", 1)
        return f"{a.lower()}.{b}"
    return name


def new_op(p, base, *names):
    """True if an operator named in `names` ran since the step started."""
    ops = p.wm.operators
    if not len(ops) or p.op_key() == base.get("_op"):
        return False
    return norm_op(ops[-1].bl_idname) in names


def edit_counts(p):
    obj = p.obj
    if not obj or obj.type != "MESH" or obj.mode != "EDIT":
        return None
    bm = bmesh.from_edit_mesh(obj.data)
    return len(bm.verts), len(bm.edges), len(bm.faces)


def cube(p):
    return p.scene.objects.get(p.cube_name)


def meshes_named(p, prefix):
    return [o for o in p.scene.objects if o.type == "MESH" and o.name.startswith(prefix)]


def principled(obj):
    mat = obj.active_material if obj else None
    if not mat or not mat.node_tree:
        return None
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def subsurf(obj):
    return next((m for m in obj.modifiers if m.type == "SUBSURF"), None) if obj else None


def lights(p):
    return [o for o in p.scene.objects if o.type == "LIGHT"]


def step(title, text, check, start=None, keys="", hint=""):
    return {"title": title, "text": text, "check": check, "start": start, "keys": keys, "hint": hint}


# ----------------------------------------------------------- start helpers
def remember_view(p, base):
    if p.rv3d:
        base["rot"] = p.rv3d.view_rotation.copy()
        base["dist"] = p.rv3d.view_distance
        base["loc"] = p.rv3d.view_location.copy()
        base["side"] = p.rv3d.is_orthographic_side_view


def remember_cube(p, base):
    c = cube(p)
    if c:
        base["loc"] = c.location.copy()
        base["rot"] = c.rotation_euler.copy()
        base["scale"] = c.scale.copy()


def remember_objects(p, base):
    base["names"] = {o.name for o in p.scene.objects}
    base["count"] = len(p.scene.objects)
    base["spheres"] = len(meshes_named(p, "Sphere"))


def remember_edit(p, base):
    base["counts"] = edit_counts(p)


def remember_lights(p, base):
    base["lights"] = {o.name: o.location.copy() for o in lights(p)}


def remember_camera(p, base):
    cam = p.scene.camera
    base["cam"] = (cam.location.copy(), cam.rotation_euler.copy()) if cam else None


def remember_renders(p, base):
    base["renders"] = p.render_count()


def remember_materials(p, base):
    base["mat"] = p.obj.active_material.name if p.obj and p.obj.active_material else None


# ------------------------------------------------------------ check helpers
def view_rotated(p, base):
    return p.rv3d and "rot" in base and p.rv3d.view_rotation.rotation_difference(base["rot"]).angle > 0.35


def view_zoomed(p, base):
    return p.rv3d and "dist" in base and abs(p.rv3d.view_distance / max(base["dist"], 1e-6) - 1) > 0.25


def view_panned(p, base):
    return p.rv3d and "loc" in base and (p.rv3d.view_location - base["loc"]).length > 0.1 * max(base["dist"], 1)


def side_view(p, base):
    if not p.rv3d or not p.rv3d.is_orthographic_side_view:
        return False
    return not base.get("side") or p.rv3d.view_rotation.rotation_difference(base["rot"]).angle > 0.01


def back_to_persp(p, base):
    return p.rv3d and not p.rv3d.is_orthographic_side_view


def cube_selected(p, base):
    c = cube(p)
    return c is not None and p.obj == c and c.select_get(view_layer=p.view_layer)


def cube_moved(p, base):
    c = cube(p)
    return c and "loc" in base and (c.location - base["loc"]).length > 0.5


def cube_moved_x(p, base):
    c = cube(p)
    if not c or "loc" not in base:
        return False
    d = c.location - base["loc"]
    return abs(d.x) > 0.5 and abs(d.y) < 1e-4 and abs(d.z) < 1e-4


def cube_rotated(p, base):
    c = cube(p)
    return c and "rot" in base and sum(abs(a - b) for a, b in zip(c.rotation_euler, base["rot"])) > 0.1


def cube_scaled(p, base):
    c = cube(p)
    return c and "scale" in base and any(abs(a - b) > 0.1 for a, b in zip(c.scale, base["scale"]))


def sphere_added(p, base):
    return any(o.name not in base["names"] for o in meshes_named(p, "Sphere"))


def sphere_duplicated(p, base):
    return len(meshes_named(p, "Sphere")) > base["spheres"]


def object_deleted(p, base):
    return len(p.scene.objects) < base["count"]


def undo_done(p, base):
    return len(p.scene.objects) > base["count"]


def in_edit_mode(p, base):
    return p.obj is not None and p.obj.type == "MESH" and p.obj.mode == "EDIT"


def face_mode(p, base):
    return tuple(p.scene.tool_settings.mesh_select_mode) == (False, False, True)


def one_face_selected(p, base):
    return in_edit_mode(p, base) and p.obj.data.total_face_sel == 1


def faces_grew(p, base, by=1):
    now, then = edit_counts(p), base.get("counts")
    return bool(now and then and now[2] >= then[2] + by)


def extruded(p, base):
    return new_op(p, base, "view3d.edit_mesh_extrude_move_normal", "mesh.extrude_region_move",
                  "mesh.extrude_context_move", "view3d.edit_mesh_extrude_move_shrink_fatten",
                  "mesh.extrude_region_shrink_fatten") or faces_grew(p, base, 4)


def inset(p, base):
    return new_op(p, base, "mesh.inset") or faces_grew(p, base, 4)


def loopcut(p, base):
    return new_op(p, base, "mesh.loopcut_slide") or faces_grew(p, base, 4)


def beveled(p, base):
    return new_op(p, base, "mesh.bevel") or faces_grew(p, base, 1)


def object_mode(p, base):
    return p.obj is not None and p.obj.mode == "OBJECT"


def smooth_shaded(p, base):
    obj = p.obj
    return (obj and obj.type == "MESH" and obj.mode == "OBJECT" and len(obj.data.polygons)
            and all(poly.use_smooth for poly in obj.data.polygons))


def has_subsurf(p, base):
    return subsurf(p.obj) is not None


def subsurf_level3(p, base):
    m = subsurf(p.obj)
    return m is not None and m.levels >= 3


def new_material(p, base):
    mat = p.obj.active_material if p.obj else None
    return mat is not None and mat.name != base.get("mat")


def color_changed(p, base):
    node = principled(p.obj)
    if not node:
        return False
    col = node.inputs["Base Color"].default_value
    return any(abs(c - 0.8) > 0.05 for c in col[:3])


def glossy(p, base):
    node = principled(p.obj)
    return node is not None and node.inputs["Roughness"].default_value < 0.3


def material_preview(p, base):
    return p.space is not None and p.space.shading.type in ("MATERIAL", "RENDERED")


def rendered_preview(p, base):
    return p.space is not None and p.space.shading.type == "RENDERED"


def camera_view(p, base):
    return p.rv3d is not None and p.rv3d.view_perspective == "CAMERA"


def light_added(p, base):
    return any(o.name not in base["lights"] for o in lights(p))


def light_moved(p, base):
    return any(o.name in base["lights"] and (o.location - base["lights"][o.name]).length > 0.5
               for o in lights(p))


def light_colored(p, base):
    return any(any(abs(c - 1) > 0.05 for c in o.data.color) for o in lights(p))


def camera_moved(p, base):
    cam = p.scene.camera
    if not cam or base.get("cam") is None:
        return False
    loc, rot = base["cam"]
    return (cam.location - loc).length > 1e-3 or any(abs(x - y) > 1e-3 for x, y in zip(cam.rotation_euler, rot))


def rendered(p, base):
    return p.render_count() > base["renders"]


# ------------------------------------------------------------------ lessons
# setup: what the lesson scene starts with (see build_scene in __init__.py).
LESSONS = [
    {
        "id": "navigate",
        "title": "Getting Around",
        "summary": "Orbit, zoom and pan the 3D viewport",
        "setup": {"select_cube": False},
        "steps": [
            step("Orbit", "Hold the middle mouse button and drag in the viewport to orbit around the scene.",
                 view_rotated, remember_view, keys="Middle mouse drag",
                 hint="No middle button? Click and drag the colored axis gizmo at the top right of the viewport."),
            step("Zoom", "Scroll the mouse wheel to zoom in and out.",
                 view_zoomed, remember_view, keys="Mouse wheel",
                 hint="On a trackpad, drag the magnifying-glass icon at the top right of the viewport, or press Ctrl + middle mouse drag."),
            step("Pan", "Hold Shift and drag with the middle mouse button to slide the view sideways.",
                 view_panned, remember_view, keys="Shift + Middle mouse drag",
                 hint="Or drag the hand icon at the top right of the viewport."),
            step("Front View", "Press 1 on the numpad for a straight-on front view. 3 is the side view and 7 is the top view.",
                 side_view, remember_view, keys="Numpad 1 / 3 / 7",
                 hint="No numpad? Click one of the colored circles (X, Y or Z) on the axis gizmo at the top right."),
            step("Back to 3D", "Orbit again to leave the flat side view and look around in 3D.",
                 back_to_persp, remember_view, keys="Middle mouse drag",
                 hint="If it stays flat, press Numpad 5 to toggle between perspective and orthographic."),
        ],
    },
    {
        "id": "transform",
        "title": "Select & Transform",
        "summary": "Select, move, rotate, scale, add and delete objects",
        "setup": {"select_cube": False},
        "steps": [
            step("Select the Cube", "Left-click the cube to select it. Selected objects get an orange outline.",
                 cube_selected, keys="Left click",
                 hint="Can't see the cube? Press Home with the mouse over the viewport to show everything."),
            step("Move It", "Move the mouse over the viewport, press G (grab) and move the mouse. Left-click to confirm, or right-click to cancel.",
                 cube_moved, remember_cube, keys="G",
                 hint="Shortcuts act on whatever is under the mouse, so keep the pointer over the 3D viewport."),
            step("Move Along an Axis", "Press G, then X to lock movement to the red X axis. Type 2 and press Enter to move it exactly 2 units.",
                 cube_moved_x, remember_cube, keys="G  X  2  Enter",
                 hint="Y and Z lock to the green and blue axes. Pressing the axis key twice switches to the object's own axes."),
            step("Rotate", "Press R to rotate. For a precise turn try R, Z, 45, Enter.",
                 cube_rotated, remember_cube, keys="R",
                 hint="Hold Ctrl while moving the mouse to snap in 5° steps."),
            step("Scale", "Press S to scale. Move the mouse toward the cube to shrink it, away to grow it, then click.",
                 cube_scaled, remember_cube, keys="S",
                 hint="S, Z scales only along Z: great for turning a cube into a slab."),
            step("Add a Sphere", "Press Shift+A ▸ Mesh ▸ UV Sphere. New objects appear at the 3D cursor (the red and white circle).",
                 sphere_added, remember_objects, keys="Shift + A",
                 hint="You can also use the Add menu in the viewport header."),
            step("Duplicate", "With the sphere selected, press Shift+D, move the mouse and click to place the copy.",
                 sphere_duplicated, remember_objects, keys="Shift + D",
                 hint="Right-click while moving places the copy right on top of the original."),
            step("Delete", "Select one of the objects and press X ▸ Delete (or just the Delete key).",
                 object_deleted, remember_objects, keys="X  or  Delete"),
            step("Undo", "Changed your mind? Press Ctrl+Z to undo the delete.",
                 undo_done, remember_objects, keys="Ctrl + Z",
                 hint="Ctrl+Shift+Z redoes. Edit ▸ Undo History shows every step."),
        ],
    },
    {
        "id": "edit",
        "title": "Edit Mode Modeling",
        "summary": "Edit vertices, edges and faces: extrude, inset, loop cut, bevel",
        "setup": {"select_cube": True},
        "steps": [
            step("Enter Edit Mode", "With the cube selected and the mouse over the viewport, press Tab. Edit Mode lets you change the shape itself.",
                 in_edit_mode, keys="Tab",
                 hint="You can also use the mode dropdown at the top left of the viewport."),
            step("Face Select", "Press 3 (on the top row, not the numpad) to switch to Face select mode. 1 selects vertices, 2 selects edges.",
                 face_mode, keys="3",
                 hint="The three small icons next to the mode dropdown do the same thing."),
            step("Pick One Face", "Click the top face of the cube so only that face is selected.",
                 one_face_selected, keys="Left click",
                 hint="If several faces are selected, click once on empty space, then click the top face."),
            step("Extrude", "Press E to extrude the face, move the mouse up and click. Extruding is how you grow new geometry.",
                 extruded, remember_edit, keys="E"),
            step("Inset", "Press I and move the mouse to inset the selected face, then click.",
                 inset, remember_edit, keys="I",
                 hint="Now try E again to push the inset face in or out: that's how you make panels and buttons."),
            step("Loop Cut", "Press Ctrl+R and hover over a side edge. A yellow line previews the cut. Click, then right-click to keep it centered.",
                 loopcut, remember_edit, keys="Ctrl + R",
                 hint="Scroll the mouse wheel before clicking to add several cuts at once."),
            step("Bevel", "Press 2 for edge select, click an edge, then press Ctrl+B and move the mouse to round it off.",
                 beveled, remember_edit, keys="2  Ctrl + B",
                 hint="Scroll while beveling to add segments for a smoother curve."),
            step("Back to Object Mode", "Press Tab again to return to Object Mode.",
                 object_mode, keys="Tab"),
        ],
    },
    {
        "id": "shade",
        "title": "Make It Pretty",
        "summary": "Smooth shading, modifiers and materials",
        "setup": {"select_cube": True},
        "steps": [
            step("Shade Smooth", "Right-click the cube in the viewport and choose Shade Smooth.",
                 smooth_shaded, keys="Right click",
                 hint="Make sure you're in Object Mode (press Tab if you're in Edit Mode)."),
            step("Subdivision Surface", "Press Ctrl+2 to add a Subdivision Surface modifier. It smooths the shape without editing it.",
                 has_subsurf, keys="Ctrl + 2",
                 hint="Or open Properties ▸ the blue wrench tab ▸ Add Modifier ▸ Generate ▸ Subdivision Surface."),
            step("More Levels", "In Properties, open the blue wrench tab (Modifiers) and set Levels Viewport to 3.",
                 subsurf_level3, keys="Properties ▸ Modifiers",
                 hint="The Properties editor is usually on the right side, below the Outliner."),
            step("New Material", "Open the Material tab (red sphere icon in Properties) and click New.",
                 new_material, remember_materials, keys="Properties ▸ Material"),
            step("Pick a Color", "Click the Base Color swatch and choose any color you like.",
                 color_changed, keys="Properties ▸ Material"),
            step("Material Preview", "Press Z ▸ Material Preview, or click the third sphere icon at the top right of the viewport, to see your color.",
                 material_preview, keys="Z"),
            step("Make It Glossy", "Lower Roughness below 0.3 for a shiny finish.",
                 glossy, keys="Properties ▸ Material",
                 hint="Double-click a slider to type an exact value, or drag it."),
        ],
    },
    {
        "id": "render",
        "title": "Lights, Camera, Render",
        "summary": "Look through the camera, light the scene and render an image",
        "setup": {"select_cube": False, "material": True, "light": False},
        "steps": [
            step("Camera View", "Press Numpad 0 to look through the scene camera. The framed area is what will be rendered.",
                 camera_view, keys="Numpad 0",
                 hint="No numpad? Use View ▸ Cameras ▸ Active Camera, or click the camera icon at the top right of the viewport."),
            step("Add a Light", "This scene is dark. Press Shift+A ▸ Light ▸ Area to add a light.",
                 light_added, remember_lights, keys="Shift + A"),
            step("Place the Light", "Move the light above the cube: press G, then Z, and move the mouse up.",
                 light_moved, remember_lights, keys="G  Z",
                 hint="Make sure the light (not the cube) is selected. Click it in the Outliner at the top right."),
            step("Light Color", "In Properties, open the green light-bulb tab and change the light's Color.",
                 light_colored, keys="Properties ▸ Light",
                 hint="Warm colors like orange feel like sunset; blue feels cold."),
            step("Rendered Preview", "Press Z ▸ Rendered to preview the final lighting live in the viewport.",
                 rendered_preview, keys="Z"),
            step("Frame Your Shot", "Orbit to a view you like, then press Ctrl+Alt+Numpad 0 to move the camera to your view.",
                 camera_moved, remember_camera, keys="Ctrl + Alt + Numpad 0",
                 hint="No numpad? View ▸ Align View ▸ Align Active Camera to View. Or select the camera and move it with G."),
            step("Render!", "Press F12 to render the final image. It opens in a new window.",
                 rendered, remember_renders, keys="F12",
                 hint="Save it from the render window with Image ▸ Save As."),
        ],
    },
]

RANKS = [(0, "Default Cube"), (60, "Vertex Wrangler"), (160, "Mesh Maker"),
         (280, "Modifier Mage"), (420, "Render Wizard")]
