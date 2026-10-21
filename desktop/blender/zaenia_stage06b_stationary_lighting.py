import bpy
import math
from mathutils import Vector

# ============================================================
# ZÆNIA Desktop UI
# Stage 6B — Stationary Warehouse Lighting Validation
#
# Builds the approved raw warehouse blockout, then adds:
# - fixed Home camera
# - dark graphite materials
# - Midnight Blue architectural practicals
# - Amber Orange architectural practicals
# - soft floor reflections
# - subtle real light spill
#
# This is STILL a validation scene.
# No ZÆNIA planet-atom, UI, wall recess detailing, floor seams,
# particles, camera movement, pulsing, or final bloom.
#
# Locked identity colors:
# Midnight Blue  = #191970
# Deep Midnight  = #080D24
# Amber Orange   = #FFB000
# Hot Amber      = #FF8A00
# ============================================================


# ------------------------------------------------------------
# LOCKED ROOM / CAMERA
# ------------------------------------------------------------

ROOM_WIDTH = 28.0
ROOM_DEPTH = 42.0
ROOM_HEIGHT = 12.0

ROOM_FRONT_Y = 6.0
ROOM_BACK_Y = ROOM_FRONT_Y - ROOM_DEPTH
ROOM_CENTER_Y = (ROOM_FRONT_Y + ROOM_BACK_Y) / 2.0

WALL_THICKNESS = 0.50
FLOOR_THICKNESS = 0.20
CEILING_THICKNESS = 0.50
BACK_WALL_THICKNESS = 0.50

RIB_SPACING = 3.50
RIB_WIDTH_X = 0.42
RIB_DEPTH_Y = 0.42
RIB_DEPTH_Z = 0.42

CAMERA_LOCATION = (0.0, 4.0, 1.70)
CAMERA_TARGET = (0.0, -28.0, 1.70)
CAMERA_FOV_DEG = 50.0

ROOT_COLLECTION = "ZAENIA_ENVIRONMENT"
GEO_COLLECTION = "GEO_BLOCKOUT"
LIGHT_COLLECTION = "LIGHTS"
CAMERA_COLLECTION = "CAMERAS"
HELPER_COLLECTION = "HELPERS"


# ------------------------------------------------------------
# COLOR DEFINITIONS
# ------------------------------------------------------------

# Visual anchors requested for ZÆNIA.
MIDNIGHT_BLUE_HEX = "#191970"
DEEP_MIDNIGHT_HEX = "#080D24"
AMBER_ORANGE_HEX = "#FFB000"
HOT_AMBER_HEX = "#FF8A00"

# Blender RGB values in 0-1 range.
MIDNIGHT_BLUE = (0.098, 0.098, 0.439, 1.0)
DEEP_MIDNIGHT = (0.031, 0.051, 0.141, 1.0)
AMBER_ORANGE = (1.000, 0.690, 0.000, 1.0)
HOT_AMBER = (1.000, 0.541, 0.000, 1.0)

STRUCTURE_DARK = (0.025, 0.032, 0.045, 1.0)
STRUCTURE_SECONDARY = (0.050, 0.062, 0.082, 1.0)
FLOOR_DARK = (0.015, 0.021, 0.030, 1.0)
BACK_WALL_DARK = (0.010, 0.016, 0.026, 1.0)


# ------------------------------------------------------------
# BASIC SCENE HELPERS
# ------------------------------------------------------------

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)

    for collection in list(bpy.data.collections):
        if collection.name != "Collection":
            bpy.data.collections.remove(collection)


def create_collection(name, parent=None):
    collection = bpy.data.collections.new(name)

    if parent is None:
        bpy.context.scene.collection.children.link(collection)
    else:
        parent.children.link(collection)

    return collection


def move_to_collection(obj, collection):
    for current_collection in list(obj.users_collection):
        current_collection.objects.unlink(obj)

    collection.objects.link(obj)


def add_box(name, location, dimensions, collection):
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=location,
    )

    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = dimensions

    bpy.ops.object.transform_apply(
        location=False,
        rotation=False,
        scale=True,
    )

    move_to_collection(obj, collection)
    return obj


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


# ------------------------------------------------------------
# MATERIALS
# ------------------------------------------------------------

def make_principled_material(
    name,
    base_color,
    metallic,
    roughness,
):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True

    nodes = material.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")

    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness

    return material


def make_emission_material(
    name,
    color,
    strength,
):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True

    nodes = material.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")

    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.28

    # Blender 4.x Principled BSDF emission inputs.
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = strength
    else:
        # Fallback for older Blender versions.
        bsdf.inputs["Emission"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = strength

    return material


def assign_material(obj, material):
    if not hasattr(obj.data, "materials"):
        return

    obj.data.materials.clear()
    obj.data.materials.append(material)


# ------------------------------------------------------------
# GEOMETRY
# ------------------------------------------------------------

def build_shell(
    geo_collection,
    mat_structure,
    mat_floor,
    mat_back,
):
    floor = add_box(
        "GEO_Floor",
        (
            0.0,
            ROOM_CENTER_Y,
            -FLOOR_THICKNESS / 2.0,
        ),
        (
            ROOM_WIDTH + WALL_THICKNESS * 2.0,
            ROOM_DEPTH,
            FLOOR_THICKNESS,
        ),
        geo_collection,
    )
    assign_material(floor, mat_floor)

    left_wall = add_box(
        "GEO_Wall_Left",
        (
            -(ROOM_WIDTH / 2.0) - WALL_THICKNESS / 2.0,
            ROOM_CENTER_Y,
            ROOM_HEIGHT / 2.0,
        ),
        (
            WALL_THICKNESS,
            ROOM_DEPTH,
            ROOM_HEIGHT,
        ),
        geo_collection,
    )
    assign_material(left_wall, mat_structure)

    right_wall = add_box(
        "GEO_Wall_Right",
        (
            (ROOM_WIDTH / 2.0) + WALL_THICKNESS / 2.0,
            ROOM_CENTER_Y,
            ROOM_HEIGHT / 2.0,
        ),
        (
            WALL_THICKNESS,
            ROOM_DEPTH,
            ROOM_HEIGHT,
        ),
        geo_collection,
    )
    assign_material(right_wall, mat_structure)

    ceiling = add_box(
        "GEO_Ceiling",
        (
            0.0,
            ROOM_CENTER_Y,
            ROOM_HEIGHT + CEILING_THICKNESS / 2.0,
        ),
        (
            ROOM_WIDTH + WALL_THICKNESS * 2.0,
            ROOM_DEPTH,
            CEILING_THICKNESS,
        ),
        geo_collection,
    )
    assign_material(ceiling, mat_structure)

    back_wall = add_box(
        "GEO_Back_Wall",
        (
            0.0,
            ROOM_BACK_Y - BACK_WALL_THICKNESS / 2.0,
            ROOM_HEIGHT / 2.0,
        ),
        (
            ROOM_WIDTH + WALL_THICKNESS * 2.0,
            BACK_WALL_THICKNESS,
            ROOM_HEIGHT,
        ),
        geo_collection,
    )
    assign_material(back_wall, mat_back)


def build_primary_ribs(
    geo_collection,
    mat_structure_secondary,
):
    rib_count = int(round(ROOM_DEPTH / RIB_SPACING)) + 1

    for index in range(rib_count):
        y = ROOM_FRONT_Y - index * RIB_SPACING

        if y < ROOM_BACK_Y - 0.001:
            break

        number = index + 1

        left_rib = add_box(
            f"GEO_Rib_{number:02d}_Left",
            (
                -(ROOM_WIDTH / 2.0) + RIB_WIDTH_X / 2.0,
                y,
                ROOM_HEIGHT / 2.0,
            ),
            (
                RIB_WIDTH_X,
                RIB_DEPTH_Y,
                ROOM_HEIGHT,
            ),
            geo_collection,
        )
        assign_material(
            left_rib,
            mat_structure_secondary,
        )

        right_rib = add_box(
            f"GEO_Rib_{number:02d}_Right",
            (
                (ROOM_WIDTH / 2.0) - RIB_WIDTH_X / 2.0,
                y,
                ROOM_HEIGHT / 2.0,
            ),
            (
                RIB_WIDTH_X,
                RIB_DEPTH_Y,
                ROOM_HEIGHT,
            ),
            geo_collection,
        )
        assign_material(
            right_rib,
            mat_structure_secondary,
        )

        ceiling_rib = add_box(
            f"GEO_Rib_{number:02d}_Ceiling",
            (
                0.0,
                y,
                ROOM_HEIGHT - RIB_DEPTH_Z / 2.0,
            ),
            (
                ROOM_WIDTH,
                RIB_DEPTH_Y,
                RIB_DEPTH_Z,
            ),
            geo_collection,
        )
        assign_material(
            ceiling_rib,
            mat_structure_secondary,
        )


# ------------------------------------------------------------
# ARCHITECTURAL PRACTICALS
# ------------------------------------------------------------

def add_area_light(
    name,
    location,
    color,
    energy,
    size,
    collection,
    target,
):
    data = bpy.data.lights.new(
        name=name,
        type="AREA",
    )

    data.color = color[:3]
    data.energy = energy
    data.shape = "RECTANGLE"
    data.size = size
    data.size_y = size * 2.4

    obj = bpy.data.objects.new(
        name,
        data,
    )

    obj.location = location
    collection.objects.link(obj)

    look_at(
        obj,
        target,
    )

    return obj


def build_practical_lights(
    geo_collection,
    light_collection,
    mat_blue_emission,
    mat_amber_emission,
):
    # Practical light positions are intentionally asymmetric.
    # The architecture stays stationary.

    y_positions = [
        1.0,
        -6.0,
        -13.0,
        -20.0,
        -27.0,
        -34.0,
    ]

    for index, y in enumerate(y_positions, start=1):
        # LEFT: Midnight Blue vertical practical.
        blue_strip = add_box(
            f"GEO_Practical_Blue_{index:02d}",
            (
                -(ROOM_WIDTH / 2.0) + 0.06,
                y,
                5.0,
            ),
            (
                0.08,
                1.80,
                3.40,
            ),
            geo_collection,
        )
        assign_material(
            blue_strip,
            mat_blue_emission,
        )

        add_area_light(
            f"LGT_Blue_{index:02d}",
            (
                -(ROOM_WIDTH / 2.0) + 0.70,
                y,
                5.0,
            ),
            MIDNIGHT_BLUE,
            energy=520.0,
            size=2.0,
            collection=light_collection,
            target=(
                -7.0,
                y - 2.0,
                3.8,
            ),
        )

        # RIGHT: Amber Orange lower architectural practical.
        amber_strip = add_box(
            f"GEO_Practical_Amber_{index:02d}",
            (
                (ROOM_WIDTH / 2.0) - 0.06,
                y - 1.4,
                2.1,
            ),
            (
                0.08,
                2.10,
                1.65,
            ),
            geo_collection,
        )
        assign_material(
            amber_strip,
            mat_amber_emission,
        )

        add_area_light(
            f"LGT_Amber_{index:02d}",
            (
                (ROOM_WIDTH / 2.0) - 0.70,
                y - 1.4,
                2.4,
            ),
            AMBER_ORANGE,
            energy=410.0,
            size=1.8,
            collection=light_collection,
            target=(
                7.0,
                y - 3.0,
                2.0,
            ),
        )

    # Very subtle central depth lights.
    add_area_light(
        "LGT_Depth_Blue",
        (
            -5.5,
            ROOM_BACK_Y + 1.2,
            6.5,
        ),
        DEEP_MIDNIGHT,
        energy=340.0,
        size=4.0,
        collection=light_collection,
        target=(
            0.0,
            ROOM_CENTER_Y,
            4.0,
        ),
    )

    add_area_light(
        "LGT_Depth_Amber",
        (
            5.5,
            ROOM_BACK_Y + 1.2,
            3.2,
        ),
        AMBER_ORANGE,
        energy=235.0,
        size=3.0,
        collection=light_collection,
        target=(
            0.0,
            ROOM_CENTER_Y,
            2.0,
        ),
    )


# ------------------------------------------------------------
# CAMERA
# ------------------------------------------------------------

def build_camera(camera_collection):
    camera_data = bpy.data.cameras.new(
        "CAM_Home"
    )

    camera = bpy.data.objects.new(
        "CAM_Home",
        camera_data,
    )

    camera_collection.objects.link(camera)

    camera.location = CAMERA_LOCATION

    camera_data.lens = 50.0

    # Exact 50-degree horizontal-style field of view approximation.
    camera_data.angle = math.radians(
        CAMERA_FOV_DEG
    )

    look_at(
        camera,
        CAMERA_TARGET,
    )

    bpy.context.scene.camera = camera

    return camera


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def build_helpers(helper_collection):
    centerline = add_box(
        "HLP_Room_Centerline",
        (
            0.0,
            ROOM_CENTER_Y,
            0.01,
        ),
        (
            0.03,
            ROOM_DEPTH,
            0.02,
        ),
        helper_collection,
    )
    centerline.display_type = "WIRE"
    centerline.hide_render = True

    bpy.ops.object.empty_add(
        type="PLAIN_AXES",
        location=(0.0, 0.0, 0.0),
    )

    origin = bpy.context.active_object
    origin.name = "HLP_ZAENIA_Environment_Origin"

    move_to_collection(
        origin,
        helper_collection,
    )

    origin.hide_render = True
    origin.empty_display_size = 1.5


# ------------------------------------------------------------
# RENDER / COLOR MANAGEMENT
# ------------------------------------------------------------

def configure_scene():
    scene = bpy.context.scene

    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"

    # Use Eevee for quick validation.
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"

    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 50

    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    # Dark navy world. Not pure black.
    scene.world.use_nodes = True
    world_nodes = scene.world.node_tree.nodes

    background = world_nodes.get("Background")

    background.inputs["Color"].default_value = (
        0.002,
        0.004,
        0.012,
        1.0,
    )
    background.inputs["Strength"].default_value = 0.045

    # Keep lighting cinematic without crushing all shadow detail.
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():
    clear_scene()
    configure_scene()

    root = create_collection(
        ROOT_COLLECTION
    )

    geo = create_collection(
        GEO_COLLECTION,
        parent=root,
    )

    lights = create_collection(
        LIGHT_COLLECTION,
        parent=root,
    )

    cameras = create_collection(
        CAMERA_COLLECTION,
        parent=root,
    )

    helpers = create_collection(
        HELPER_COLLECTION,
        parent=root,
    )

    # Materials.
    mat_structure = make_principled_material(
        "MAT_Structure_Dark",
        STRUCTURE_DARK,
        metallic=0.75,
        roughness=0.48,
    )

    mat_structure_secondary = make_principled_material(
        "MAT_Structure_Secondary",
        STRUCTURE_SECONDARY,
        metallic=0.68,
        roughness=0.52,
    )

    mat_floor = make_principled_material(
        "MAT_Floor_Graphite",
        FLOOR_DARK,
        metallic=0.65,
        roughness=0.19,
    )

    mat_back = make_principled_material(
        "MAT_Back_Wall",
        BACK_WALL_DARK,
        metallic=0.48,
        roughness=0.60,
    )

    mat_blue_emission = make_emission_material(
        "MAT_Light_Midnight_Blue",
        MIDNIGHT_BLUE,
        strength=8.0,
    )

    mat_amber_emission = make_emission_material(
        "MAT_Light_Amber_Orange",
        AMBER_ORANGE,
        strength=7.0,
    )

    build_shell(
        geo,
        mat_structure,
        mat_floor,
        mat_back,
    )

    build_primary_ribs(
        geo,
        mat_structure_secondary,
    )

    build_practical_lights(
        geo,
        lights,
        mat_blue_emission,
        mat_amber_emission,
    )

    build_camera(
        cameras
    )

    build_helpers(
        helpers
    )

    # Set viewport to camera for immediate inspection.
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_perspective = "CAMERA"
            break

    bpy.ops.wm.save_as_mainfile(
        filepath=bpy.path.abspath(
            "//ZAENIA_Warehouse_Stage06B.blend"
        )
    )

    print("")
    print("==================================================")
    print("ZÆNIA Stage 6B lighting validation scene created.")
    print("")
    print("Stationary environment: YES")
    print("Midnight Blue: #191970")
    print("Amber Orange:  #FFB000")
    print("Camera motion: NONE")
    print("Light pulsing: NONE")
    print("")
    print("Press F12 for the first lighting validation render.")
    print("==================================================")
    print("")


main()
