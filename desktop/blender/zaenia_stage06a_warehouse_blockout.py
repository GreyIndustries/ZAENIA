import bpy

ROOM_WIDTH = 28.0
ROOM_DEPTH = 42.0
ROOM_HEIGHT = 12.0

WALL_THICKNESS = 0.50
FLOOR_THICKNESS = 0.20
CEILING_THICKNESS = 0.50

RIB_SPACING = 3.50
RIB_WIDTH_X = 0.42
RIB_DEPTH_Y = 0.42
RIB_DEPTH_Z = 0.42

ROOM_FRONT_Y = 6.0
ROOM_BACK_Y = ROOM_FRONT_Y - ROOM_DEPTH
ROOM_CENTER_Y = (ROOM_FRONT_Y + ROOM_BACK_Y) / 2.0

COLLECTION_NAME = "ZAENIA_ENVIRONMENT"
BLOCKOUT_COLLECTION_NAME = "GEO_BLOCKOUT"


def remove_all_objects():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def remove_collection_if_exists(name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        return

    for obj in list(collection.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    bpy.data.collections.remove(collection)


def create_collection(name, parent=None):
    collection = bpy.data.collections.new(name)

    if parent is None:
        bpy.context.scene.collection.children.link(collection)
    else:
        parent.children.link(collection)

    return collection


def move_object_to_collection(obj, collection):
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

    move_object_to_collection(obj, collection)
    return obj


def set_blockout_material(obj):
    material_name = "MAT_Blockout_Neutral"

    material = bpy.data.materials.get(material_name)

    if material is None:
        material = bpy.data.materials.new(material_name)
        material.diffuse_color = (
            0.055,
            0.065,
            0.080,
            1.0,
        )
        material.roughness = 0.55
        material.metallic = 0.25

    if len(obj.data.materials) == 0:
        obj.data.materials.append(material)
    else:
        obj.data.materials[0] = material


def configure_scene():
    scene = bpy.context.scene

    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"

    scene.world.color = (
        0.005,
        0.007,
        0.012,
    )


def build_room_shell(collection):
    floor = add_box(
        name="GEO_Floor_Blockout",
        location=(
            0.0,
            ROOM_CENTER_Y,
            -FLOOR_THICKNESS / 2.0,
        ),
        dimensions=(
            ROOM_WIDTH + (WALL_THICKNESS * 2.0),
            ROOM_DEPTH,
            FLOOR_THICKNESS,
        ),
        collection=collection,
    )
    set_blockout_material(floor)

    left_wall = add_box(
        name="GEO_Wall_Left_Blockout",
        location=(
            -(ROOM_WIDTH / 2.0) - (WALL_THICKNESS / 2.0),
            ROOM_CENTER_Y,
            ROOM_HEIGHT / 2.0,
        ),
        dimensions=(
            WALL_THICKNESS,
            ROOM_DEPTH,
            ROOM_HEIGHT,
        ),
        collection=collection,
    )
    set_blockout_material(left_wall)

    right_wall = add_box(
        name="GEO_Wall_Right_Blockout",
        location=(
            (ROOM_WIDTH / 2.0) + (WALL_THICKNESS / 2.0),
            ROOM_CENTER_Y,
            ROOM_HEIGHT / 2.0,
        ),
        dimensions=(
            WALL_THICKNESS,
            ROOM_DEPTH,
            ROOM_HEIGHT,
        ),
        collection=collection,
    )
    set_blockout_material(right_wall)

    ceiling = add_box(
        name="GEO_Ceiling_Blockout",
        location=(
            0.0,
            ROOM_CENTER_Y,
            ROOM_HEIGHT + (CEILING_THICKNESS / 2.0),
        ),
        dimensions=(
            ROOM_WIDTH + (WALL_THICKNESS * 2.0),
            ROOM_DEPTH,
            CEILING_THICKNESS,
        ),
        collection=collection,
    )
    set_blockout_material(ceiling)


def build_primary_ribs(collection):
    rib_count = int(round(ROOM_DEPTH / RIB_SPACING)) + 1

    for index in range(rib_count):
        y = ROOM_FRONT_Y - (index * RIB_SPACING)

        if y < ROOM_BACK_Y - 0.001:
            break

        rib_number = index + 1

        left_rib = add_box(
            name=f"GEO_Rib_{rib_number:02d}_Left",
            location=(
                -(ROOM_WIDTH / 2.0) + (RIB_WIDTH_X / 2.0),
                y,
                ROOM_HEIGHT / 2.0,
            ),
            dimensions=(
                RIB_WIDTH_X,
                RIB_DEPTH_Y,
                ROOM_HEIGHT,
            ),
            collection=collection,
        )
        set_blockout_material(left_rib)

        right_rib = add_box(
            name=f"GEO_Rib_{rib_number:02d}_Right",
            location=(
                (ROOM_WIDTH / 2.0) - (RIB_WIDTH_X / 2.0),
                y,
                ROOM_HEIGHT / 2.0,
            ),
            dimensions=(
                RIB_WIDTH_X,
                RIB_DEPTH_Y,
                ROOM_HEIGHT,
            ),
            collection=collection,
        )
        set_blockout_material(right_rib)

        ceiling_rib = add_box(
            name=f"GEO_Rib_{rib_number:02d}_Ceiling",
            location=(
                0.0,
                y,
                ROOM_HEIGHT - (RIB_DEPTH_Z / 2.0),
            ),
            dimensions=(
                ROOM_WIDTH,
                RIB_DEPTH_Y,
                RIB_DEPTH_Z,
            ),
            collection=collection,
        )
        set_blockout_material(ceiling_rib)


def build_reference_markers(collection):
    center_marker = add_box(
        name="HLP_Room_Centerline",
        location=(
            0.0,
            ROOM_CENTER_Y,
            0.01,
        ),
        dimensions=(
            0.04,
            ROOM_DEPTH,
            0.02,
        ),
        collection=collection,
    )
    center_marker.display_type = "WIRE"
    center_marker.hide_render = True

    back_marker = add_box(
        name="HLP_Back_Plane",
        location=(
            0.0,
            ROOM_BACK_Y,
            ROOM_HEIGHT / 2.0,
        ),
        dimensions=(
            ROOM_WIDTH,
            0.04,
            ROOM_HEIGHT,
        ),
        collection=collection,
    )
    back_marker.display_type = "WIRE"
    back_marker.hide_render = True


def organize_outliner():
    bpy.ops.object.empty_add(
        type="PLAIN_AXES",
        location=(0.0, 0.0, 0.0),
    )

    root = bpy.context.active_object
    root.name = "HLP_ZAENIA_Environment_Origin"

    blockout_collection = bpy.data.collections.get(
        BLOCKOUT_COLLECTION_NAME
    )

    move_object_to_collection(
        root,
        blockout_collection,
    )

    root.hide_render = True
    root.empty_display_size = 1.5


def set_viewport():
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            space.overlay.show_floor = True
            space.overlay.show_axis_x = True
            space.overlay.show_axis_y = True
            space.shading.type = "MATERIAL"


def main():
    remove_all_objects()

    remove_collection_if_exists(
        BLOCKOUT_COLLECTION_NAME
    )

    remove_collection_if_exists(
        COLLECTION_NAME
    )

    configure_scene()

    environment_collection = create_collection(
        COLLECTION_NAME
    )

    blockout_collection = create_collection(
        BLOCKOUT_COLLECTION_NAME,
        parent=environment_collection,
    )

    build_room_shell(
        blockout_collection
    )

    build_primary_ribs(
        blockout_collection
    )

    build_reference_markers(
        blockout_collection
    )

    organize_outliner()
    set_viewport()

    bpy.ops.object.select_all(
        action="DESELECT"
    )

    for obj in blockout_collection.objects:
        if obj.name.startswith("GEO_"):
            obj.select_set(True)

    print("")
    print("==============================================")
    print("ZÆNIA Stage 6A blockout created successfully.")
    print("Room: 28 m wide x 42 m deep x 12 m high")
    print("Primary rib spacing: 3.5 m")
    print("No lights, neon, camera motion, or detail yet.")
    print("==============================================")
    print("")


main()
