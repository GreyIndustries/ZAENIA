import bpy
import math
from mathutils import Vector

# ============================================================
# ZÆNIA Desktop UI
# Stage 6D — Cinematic Stationary Hangar Background
#
# Builds the approved stationary warehouse foundation and adds:
# - shallow wall recesses
# - clean structural trim
# - recessed Midnight Blue / Amber Orange light channels
# - floor panel seams
# - wall-mounted and ceiling practical lighting only; floor reflects the light
# - ceiling ribs + recessed ceiling channels
# - open-ended warehouse depth, with no far wall
# - upper catwalks, central bridge, diagonal trusses, wall towers, atmospheric depth
# - beveled architectural edges
#
# Still intentionally excluded:
# - ZÆNIA planet-atom core
# - UI panels
# - particles
# - camera movement
# - pulsing
# - clutter / pipes / exposed cables
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
ROOM_DEPTH = 72.0
ROOM_HEIGHT = 14.0

ROOM_FRONT_Y = 6.0
ROOM_BACK_Y = ROOM_FRONT_Y - ROOM_DEPTH
ROOM_CENTER_Y = (ROOM_FRONT_Y + ROOM_BACK_Y) / 2.0

WALL_THICKNESS = 0.50
FLOOR_THICKNESS = 0.20
CEILING_THICKNESS = 0.50
BACK_WALL_THICKNESS = 0.50

RIB_SPACING = 4.00
RIB_WIDTH_X = 0.42
RIB_DEPTH_Y = 0.42
RIB_DEPTH_Z = 0.42

CAMERA_LOCATION = (0.0, 4.5, 1.55)
CAMERA_TARGET = (0.0, -38.0, 3.60)
CAMERA_FOV_DEG = 52.0

ROOT_COLLECTION = "ZAENIA_ENVIRONMENT"
GEO_COLLECTION = "GEO_ARCHITECTURE"
LIGHT_COLLECTION = "LIGHTS"
CAMERA_COLLECTION = "CAMERAS"
HELPER_COLLECTION = "HELPERS"


# ------------------------------------------------------------
# COLOR DEFINITIONS
# ------------------------------------------------------------

# Visual anchors remain Midnight Blue and Amber Orange.
# These lighting tuples are tuned for Blender/AgX so they READ correctly
# in the final render instead of clipping toward white/yellow.
MIDNIGHT_BLUE = (0.024, 0.030, 0.260, 1.0)      # visual anchor: #191970
MIDNIGHT_SPILL = (0.045, 0.065, 0.320, 1.0)
DEEP_MIDNIGHT = (0.014, 0.026, 0.095, 1.0)         # visual anchor: #080D24

AMBER_ORANGE = (1.000, 0.240, 0.010, 1.0)          # visual anchor: amber-orange
AMBER_SPILL = (1.000, 0.320, 0.022, 1.0)
HOT_AMBER = (1.000, 0.180, 0.000, 1.0)

STRUCTURE_DARK = (0.024, 0.030, 0.042, 1.0)
STRUCTURE_SECONDARY = (0.046, 0.056, 0.074, 1.0)
RECESS_DARK = (0.012, 0.020, 0.036, 1.0)
FLOOR_DARK = (0.014, 0.020, 0.030, 1.0)
FLOOR_SEAM = (0.006, 0.010, 0.016, 1.0)
BACK_WALL_DARK = (0.008, 0.014, 0.024, 1.0)


# ------------------------------------------------------------
# BASIC HELPERS
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


def add_box(
    name,
    location,
    dimensions,
    collection,
    bevel=0.0,
):
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

    if bevel > 0.0:
        modifier = obj.modifiers.new(
            name="Bevel",
            type="BEVEL",
        )
        modifier.width = bevel
        modifier.segments = 2
        modifier.limit_method = "ANGLE"

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

    bsdf = material.node_tree.nodes.get("Principled BSDF")

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

    bsdf = material.node_tree.nodes.get("Principled BSDF")

    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.26

    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = strength
    else:
        bsdf.inputs["Emission"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = strength

    return material


def assign_material(obj, material):
    if not hasattr(obj.data, "materials"):
        return

    obj.data.materials.clear()
    obj.data.materials.append(material)


# ------------------------------------------------------------
# ROOM SHELL
# ------------------------------------------------------------

def build_shell(
    geo,
    mat_structure,
    mat_floor,
    mat_back,
):
    floor = add_box(
        "GEO_Floor",
        (0.0, ROOM_CENTER_Y, -FLOOR_THICKNESS / 2.0),
        (
            ROOM_WIDTH + WALL_THICKNESS * 2.0,
            ROOM_DEPTH,
            FLOOR_THICKNESS,
        ),
        geo,
        bevel=0.02,
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
        geo,
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
        geo,
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
        geo,
    )
    assign_material(ceiling, mat_structure)



# ------------------------------------------------------------
# PRIMARY STRUCTURE
# ------------------------------------------------------------

def build_primary_ribs(
    geo,
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
            geo,
            bevel=0.05,
        )
        assign_material(left_rib, mat_structure_secondary)

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
            geo,
            bevel=0.05,
        )
        assign_material(right_rib, mat_structure_secondary)

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
            geo,
            bevel=0.05,
        )
        assign_material(ceiling_rib, mat_structure_secondary)


# ------------------------------------------------------------
# WALL RECESSES
# ------------------------------------------------------------

def build_wall_recesses(
    geo,
    mat_recess,
    mat_structure_secondary,
):
    bay_centers = []
    y = 0.0
    while y > ROOM_BACK_Y + 6.0:
        bay_centers.append(y)
        y -= 8.0

    for index, y in enumerate(bay_centers, start=1):
        # Left dark recess panel.
        recess_left = add_box(
            f"GEO_Recess_Left_{index:02d}",
            (
                -(ROOM_WIDTH / 2.0) + 0.10,
                y,
                5.2,
            ),
            (
                0.10,
                4.5,
                5.2,
            ),
            geo,
            bevel=0.08,
        )
        assign_material(recess_left, mat_recess)

        # Right dark recess panel.
        recess_right = add_box(
            f"GEO_Recess_Right_{index:02d}",
            (
                (ROOM_WIDTH / 2.0) - 0.10,
                y,
                4.2,
            ),
            (
                0.10,
                4.5,
                4.6,
            ),
            geo,
            bevel=0.08,
        )
        assign_material(recess_right, mat_recess)

        # Thin structural trim around recess zones.
        left_trim = add_box(
            f"GEO_Trim_Left_{index:02d}",
            (
                -(ROOM_WIDTH / 2.0) + 0.16,
                y,
                8.45,
            ),
            (
                0.14,
                4.8,
                0.22,
            ),
            geo,
            bevel=0.04,
        )
        assign_material(left_trim, mat_structure_secondary)

        right_trim = add_box(
            f"GEO_Trim_Right_{index:02d}",
            (
                (ROOM_WIDTH / 2.0) - 0.16,
                y,
                7.25,
            ),
            (
                0.14,
                4.8,
                0.22,
            ),
            geo,
            bevel=0.04,
        )
        assign_material(right_trim, mat_structure_secondary)


# ------------------------------------------------------------
# FLOOR DETAIL
# ------------------------------------------------------------

def build_floor_seams(
    geo,
    mat_floor_seam,
):
    # Long center seams.
    for x in (-7.0, 0.0, 7.0):
        seam = add_box(
            f"GEO_Floor_Seam_Long_{int(x + 20):02d}",
            (
                x,
                ROOM_CENTER_Y,
                0.004,
            ),
            (
                0.035,
                ROOM_DEPTH - 0.5,
                0.008,
            ),
            geo,
        )
        assign_material(seam, mat_floor_seam)

    # Cross seams every 3.5 m, aligned with the structural rhythm.
    seam_count = int(round(ROOM_DEPTH / RIB_SPACING))

    for index in range(seam_count):
        y = ROOM_FRONT_Y - 1.75 - index * RIB_SPACING

        cross_seam = add_box(
            f"GEO_Floor_Seam_Cross_{index + 1:02d}",
            (
                0.0,
                y,
                0.004,
            ),
            (
                ROOM_WIDTH - 1.0,
                0.035,
                0.008,
            ),
            geo,
        )
        assign_material(cross_seam, mat_floor_seam)


# ------------------------------------------------------------
# CEILING DETAIL
# ------------------------------------------------------------

def build_ceiling_detail(
    geo,
    mat_recess,
    mat_structure_secondary,
):
    # Two long recessed ceiling troughs.
    for index, x in enumerate((-6.0, 6.0), start=1):
        trough = add_box(
            f"GEO_Ceiling_Trough_{index:02d}",
            (
                x,
                ROOM_CENTER_Y,
                ROOM_HEIGHT - 0.18,
            ),
            (
                3.4,
                ROOM_DEPTH - 1.0,
                0.22,
            ),
            geo,
            bevel=0.05,
        )
        assign_material(trough, mat_recess)

    # Narrow center spine.
    center_spine = add_box(
        "GEO_Ceiling_Center_Spine",
        (
            0.0,
            ROOM_CENTER_Y,
            ROOM_HEIGHT - 0.32,
        ),
        (
            1.0,
            ROOM_DEPTH - 1.0,
            0.30,
        ),
        geo,
        bevel=0.06,
    )
    assign_material(center_spine, mat_structure_secondary)


# ------------------------------------------------------------
# BACK WALL DEPTH FRAME
# ------------------------------------------------------------


def add_beam_between(
    name,
    start,
    end,
    thickness,
    collection,
    material,
):
    """Create a rectangular structural beam between two 3D points."""
    start_v = Vector(start)
    end_v = Vector(end)
    direction = end_v - start_v
    length = direction.length
    midpoint = (start_v + end_v) * 0.5

    beam = add_box(
        name,
        midpoint,
        (thickness, thickness, length),
        collection,
        bevel=min(0.06, thickness * 0.15),
    )

    beam.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    assign_material(beam, material)
    return beam


def build_side_catwalks(
    geo,
    mat_structure_secondary,
    mat_recess,
):
    """
    Upper side catwalks and railings create the layered industrial depth
    visible in the approved cinematic reference.
    """
    deck_z = 5.55
    deck_width = 3.0
    deck_depth = 46.0
    deck_center_y = -29.0

    for side_name, x in (
        ("Left", -(ROOM_WIDTH / 2.0) + 2.8),
        ("Right", (ROOM_WIDTH / 2.0) - 2.8),
    ):
        deck = add_box(
            f"GEO_Catwalk_{side_name}",
            (x, deck_center_y, deck_z),
            (deck_width, deck_depth, 0.26),
            geo,
            bevel=0.05,
        )
        assign_material(deck, mat_structure_secondary)

        # Dark underside gives depth.
        underside = add_box(
            f"GEO_Catwalk_{side_name}_Under",
            (x, deck_center_y, deck_z - 0.24),
            (deck_width - 0.25, deck_depth, 0.18),
            geo,
            bevel=0.03,
        )
        assign_material(underside, mat_recess)

        inner_x = x + (1.30 if side_name == "Left" else -1.30)

        # Continuous rails.
        for z_off in (0.85, 1.30):
            rail = add_box(
                f"GEO_Catwalk_{side_name}_Rail_{int(z_off*100)}",
                (inner_x, deck_center_y, deck_z + z_off),
                (0.10, deck_depth, 0.10),
                geo,
                bevel=0.02,
            )
            assign_material(rail, mat_structure_secondary)

        # Repeating vertical rail posts.
        y = -7.0
        post_index = 1
        while y > -51.0:
            post = add_box(
                f"GEO_Catwalk_{side_name}_Post_{post_index:02d}",
                (inner_x, y, deck_z + 0.68),
                (0.10, 0.10, 1.55),
                geo,
                bevel=0.02,
            )
            assign_material(post, mat_structure_secondary)
            y -= 4.0
            post_index += 1


def build_cross_bridge(
    geo,
    mat_structure_secondary,
    mat_recess,
    mat_blue,
    mat_amber,
):
    """
    One elevated bridge across the hangar creates a strong middle-depth anchor
    like the cinematic target image.
    """
    bridge_y = -27.5
    bridge_z = 5.55

    deck = add_box(
        "GEO_Bridge_Deck",
        (0.0, bridge_y, bridge_z),
        (23.6, 2.2, 0.32),
        geo,
        bevel=0.06,
    )
    assign_material(deck, mat_structure_secondary)

    under = add_box(
        "GEO_Bridge_Under",
        (0.0, bridge_y, bridge_z - 0.28),
        (22.8, 1.75, 0.22),
        geo,
        bevel=0.04,
    )
    assign_material(under, mat_recess)

    # Guard rails on both long sides.
    for y_off in (-0.88, 0.88):
        for z_off in (0.88, 1.34):
            rail = add_box(
                f"GEO_Bridge_Rail_{str(y_off).replace('.','_')}_{int(z_off*100)}",
                (0.0, bridge_y + y_off, bridge_z + z_off),
                (23.0, 0.10, 0.10),
                geo,
                bevel=0.02,
            )
            assign_material(rail, mat_structure_secondary)

    # Under-bridge architectural lights, not floor lights.
    amber_strip = add_box(
        "GEO_Bridge_Light_Amber",
        (-6.2, bridge_y + 0.96, bridge_z - 0.42),
        (5.4, 0.08, 0.06),
        geo,
        bevel=0.02,
    )
    assign_material(amber_strip, mat_amber)

    blue_strip = add_box(
        "GEO_Bridge_Light_Blue",
        (6.2, bridge_y - 0.96, bridge_z - 0.42),
        (5.4, 0.08, 0.06),
        geo,
        bevel=0.02,
    )
    assign_material(blue_strip, mat_blue)


def build_diagonal_trusses(
    geo,
    mat_structure_secondary,
):
    """Large diagonal supports add the distant cinematic hangar silhouette."""
    add_beam_between(
        "GEO_Truss_Left_01",
        (-11.5, -41.0, 0.5),
        (-4.0, -29.0, 10.5),
        0.42,
        geo,
        mat_structure_secondary,
    )

    add_beam_between(
        "GEO_Truss_Right_01",
        (11.5, -46.0, 0.5),
        (4.5, -31.0, 10.8),
        0.42,
        geo,
        mat_structure_secondary,
    )

    add_beam_between(
        "GEO_Truss_Left_02",
        (-10.5, -56.0, 0.8),
        (-2.5, -42.0, 9.5),
        0.34,
        geo,
        mat_structure_secondary,
    )


def build_wall_towers(
    geo,
    mat_structure_secondary,
    mat_recess,
):
    """Tall layered wall masses create more depth than the earlier flat walls."""
    y = -8.0
    index = 1

    while y > ROOM_BACK_Y + 7.0:
        for side_name, x in (
            ("Left", -(ROOM_WIDTH / 2.0) + 0.65),
            ("Right", (ROOM_WIDTH / 2.0) - 0.65),
        ):
            tower = add_box(
                f"GEO_Tower_{side_name}_{index:02d}",
                (x, y, 6.5),
                (1.25, 1.60, 11.5),
                geo,
                bevel=0.08,
            )
            assign_material(tower, mat_structure_secondary)

            inset = add_box(
                f"GEO_TowerInset_{side_name}_{index:02d}",
                (
                    x + (0.61 if side_name == "Left" else -0.61),
                    y,
                    6.0,
                ),
                (0.08, 0.92, 7.4),
                geo,
                bevel=0.03,
            )
            assign_material(inset, mat_recess)

        y -= 8.0
        index += 1


def build_ceiling_panels(
    geo,
    mat_structure_secondary,
    mat_recess,
):
    """Layered overhead panels mimic the heavy ceiling structure in the target."""
    y = 0.0
    index = 1

    while y > ROOM_BACK_Y + 5.0:
        left_panel = add_box(
            f"GEO_CeilingPanel_Left_{index:02d}",
            (-6.3, y, ROOM_HEIGHT - 0.55),
            (10.8, 2.2, 0.24),
            geo,
            bevel=0.04,
        )
        assign_material(left_panel, mat_structure_secondary)

        right_panel = add_box(
            f"GEO_CeilingPanel_Right_{index:02d}",
            (6.3, y - 1.4, ROOM_HEIGHT - 0.55),
            (10.8, 2.2, 0.24),
            geo,
            bevel=0.04,
        )
        assign_material(right_panel, mat_recess)

        y -= 6.5
        index += 1


def make_volume_material():
    """Create very subtle atmospheric haze for depth."""
    material = bpy.data.materials.new(name="MAT_Atmosphere_Haze")
    material.use_nodes = True

    nodes = material.node_tree.nodes
    links = material.node_tree.links

    for node in list(nodes):
        nodes.remove(node)

    output = nodes.new(type="ShaderNodeOutputMaterial")
    volume = nodes.new(type="ShaderNodeVolumePrincipled")

    volume.inputs["Density"].default_value = 0.006
    volume.inputs["Color"].default_value = (0.018, 0.028, 0.060, 1.0)
    volume.inputs["Anisotropy"].default_value = 0.18

    links.new(
        volume.outputs["Volume"],
        output.inputs["Volume"],
    )

    return material


def build_atmosphere(
    geo,
    volume_material,
):
    haze = add_box(
        "GEO_Atmosphere_Haze",
        (0.0, -30.0, 6.0),
        (26.0, 60.0, 11.0),
        geo,
    )
    assign_material(haze, volume_material)

# ------------------------------------------------------------
# LIGHTING
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

    obj = bpy.data.objects.new(name, data)
    obj.location = location
    collection.objects.link(obj)

    look_at(obj, target)
    return obj


def build_practicals(
    geo,
    lights,
    mat_blue,
    mat_amber,
):
    y_positions = []
    y = 1.0
    while y > ROOM_BACK_Y + 5.0:
        y_positions.append(y)
        y -= 8.0

    for index, y in enumerate(y_positions, start=1):
        # Midnight Blue left architectural channel.
        blue_vertical = add_box(
            f"GEO_LightChannel_Blue_V_{index:02d}",
            (
                -(ROOM_WIDTH / 2.0) + 0.055,
                y,
                5.0,
            ),
            (
                0.06,
                0.14,
                2.85,
            ),
            geo,
            bevel=0.03,
        )
        assign_material(blue_vertical, mat_blue)

        # Midnight Blue upper horizontal channel.
        blue_upper = add_box(
            f"GEO_LightChannel_Blue_H_{index:02d}",
            (
                -9.5,
                y,
                9.15,
            ),
            (
                2.80,
                0.12,
                0.06,
            ),
            geo,
            bevel=0.03,
        )
        assign_material(blue_upper, mat_blue)

        add_area_light(
            f"LGT_Blue_{index:02d}",
            (
                -(ROOM_WIDTH / 2.0) + 0.75,
                y,
                5.2,
            ),
            MIDNIGHT_SPILL,
            energy=560.0,
            size=3.2,
            collection=lights,
            target=(-7.0, y - 1.5, 4.0),
        )

        # Amber Orange right lower channel.
        amber_vertical = add_box(
            f"GEO_LightChannel_Amber_V_{index:02d}",
            (
                (ROOM_WIDTH / 2.0) - 0.055,
                y - 1.2,
                2.35,
            ),
            (
                0.06,
                0.14,
                1.70,
            ),
            geo,
            bevel=0.03,
        )
        assign_material(amber_vertical, mat_amber)

        # Amber lower wall segment.
        amber_lower_wall = add_box(
            f"GEO_LightChannel_Amber_Wall_Low_{index:02d}",
            (
                (ROOM_WIDTH / 2.0) - 0.08,
                y - 0.4,
                1.15,
            ),
            (
                0.08,
                2.40,
                0.06,
            ),
            geo,
            bevel=0.025,
        )
        assign_material(amber_lower_wall, mat_amber)

        add_area_light(
            f"LGT_Amber_{index:02d}",
            (
                (ROOM_WIDTH / 2.0) - 0.80,
                y - 1.2,
                2.6,
            ),
            AMBER_SPILL,
            energy=410.0,
            size=2.8,
            collection=lights,
            target=(7.0, y - 2.0, 2.0),
        )

    # Cross-color architectural accents travel deeper through the hangar.
    cross_y_positions = []
    y = -3.0
    while y > ROOM_BACK_Y + 6.0:
        cross_y_positions.append(y)
        y -= 12.0

    for index, y in enumerate(cross_y_positions, start=1):
        amber_ceiling_left = add_box(
            f"GEO_LightChannel_Amber_Ceiling_Left_{index:02d}",
            (-5.0, y, ROOM_HEIGHT - 0.22),
            (2.25, 0.10, 0.05),
            geo,
            bevel=0.02,
        )
        assign_material(amber_ceiling_left, mat_amber)

        blue_ceiling_right = add_box(
            f"GEO_LightChannel_Blue_Ceiling_Right_{index:02d}",
            (5.0, y - 1.0, ROOM_HEIGHT - 0.22),
            (2.25, 0.10, 0.05),
            geo,
            bevel=0.02,
        )
        assign_material(blue_ceiling_right, mat_blue)

        blue_wall_low_left = add_box(
            f"GEO_LightChannel_Blue_Wall_Low_Left_{index:02d}",
            (-(ROOM_WIDTH / 2.0) + 0.08, y - 2.0, 1.10),
            (0.08, 2.10, 0.06),
            geo,
            bevel=0.02,
        )
        assign_material(blue_wall_low_left, mat_blue)

        amber_wall_low_right = add_box(
            f"GEO_LightChannel_Amber_Wall_Low_Right_{index:02d}",
            ((ROOM_WIDTH / 2.0) - 0.08, y - 3.0, 1.10),
            (0.08, 2.10, 0.06),
            geo,
            bevel=0.02,
        )
        assign_material(amber_wall_low_right, mat_amber)

    # Additional tall wall bars create the layered neon rhythm from the target.
    extra_y = -4.0
    extra_index = 1

    while extra_y > ROOM_BACK_Y + 6.0:
        left_amber_bar = add_box(
            f"GEO_WallBar_Amber_Left_{extra_index:02d}",
            (-(ROOM_WIDTH / 2.0) + 0.09, extra_y, 7.7),
            (0.08, 0.16, 2.25),
            geo,
            bevel=0.025,
        )
        assign_material(left_amber_bar, mat_amber)

        right_blue_bar = add_box(
            f"GEO_WallBar_Blue_Right_{extra_index:02d}",
            ((ROOM_WIDTH / 2.0) - 0.09, extra_y - 2.2, 6.8),
            (0.08, 0.16, 2.55),
            geo,
            bevel=0.025,
        )
        assign_material(right_blue_bar, mat_blue)

        extra_y -= 10.0
        extra_index += 1

    # Subtle depth blend.
    add_area_light(
        "LGT_Depth_Midnight",
        (-5.8, ROOM_BACK_Y + 1.0, 7.1),
        MIDNIGHT_SPILL,
        energy=460.0,
        size=6.5,
        collection=lights,
        target=(0.0, -20.0, 4.5),
    )

    add_area_light(
        "LGT_Depth_Amber",
        (5.8, ROOM_BACK_Y + 1.0, 3.0),
        AMBER_SPILL,
        energy=300.0,
        size=5.5,
        collection=lights,
        target=(0.0, -20.0, 2.5),
    )



def build_environment_fill_lights(lights):
    """
    Stationary cinematic fill system.

    Goal:
    - Midnight Blue and Amber Orange both exist across the room.
    - The center reads as a blended transition zone.
    - The back wall remains visible enough to frame the future ZÆNIA core.
    - No whole-room pulse, motion, or white clipping.
    """

    # Broad Midnight Blue source from upper-left.
    add_area_light(
        "LGT_Fill_Midnight_Left",
        (-8.0, -8.0, 8.8),
        MIDNIGHT_SPILL,
        energy=720.0,
        size=11.5,
        collection=lights,
        target=(1.5, -22.0, 4.2),
    )

    # Broad Amber Orange source from upper-right.
    add_area_light(
        "LGT_Fill_Amber_Right",
        (8.0, -10.0, 7.0),
        AMBER_SPILL,
        energy=610.0,
        size=11.0,
        collection=lights,
        target=(-1.5, -22.0, 3.6),
    )

    # Cross-spill: blue reaches the right half.
    add_area_light(
        "LGT_Cross_Midnight_Right",
        (9.0, -24.0, 8.8),
        DEEP_MIDNIGHT,
        energy=300.0,
        size=8.5,
        collection=lights,
        target=(-1.0, -20.0, 4.0),
    )

    # Cross-spill: amber reaches the left half.
    add_area_light(
        "LGT_Cross_Amber_Left",
        (-9.0, -27.0, 6.0),
        AMBER_ORANGE,
        energy=190.0,
        size=8.0,
        collection=lights,
        target=(1.0, -21.0, 3.0),
    )

    # Blended center bridge, deliberately low intensity.
    add_area_light(
        "LGT_Center_Bridge_Midnight",
        (-2.8, -18.0, 7.4),
        MIDNIGHT_SPILL,
        energy=250.0,
        size=7.0,
        collection=lights,
        target=(0.0, -29.0, 4.6),
    )

    add_area_light(
        "LGT_Center_Bridge_Amber",
        (2.8, -19.0, 5.2),
        AMBER_SPILL,
        energy=170.0,
        size=7.0,
        collection=lights,
        target=(0.0, -29.0, 3.2),
    )

    # Gentle cool front fill keeps structural ribs visible.
    add_area_light(
        "LGT_Fill_Front_Midnight",
        (0.0, 3.0, 10.0),
        DEEP_MIDNIGHT,
        energy=430.0,
        size=11.0,
        collection=lights,
        target=(0.0, -16.0, 4.0),
    )


def build_open_end_depth_fade(lights):
    """
    The warehouse has NO wall at the far end.

    Instead, a very weak deep-midnight light keeps the architecture readable
    while the open end naturally disappears into darkness.
    """
    add_area_light(
        "LGT_Open_End_Depth_Fill",
        (0.0, ROOM_BACK_Y + 7.0, 8.0),
        DEEP_MIDNIGHT,
        energy=180.0,
        size=9.0,
        collection=lights,
        target=(0.0, ROOM_BACK_Y - 10.0, 4.0),
    )


# ------------------------------------------------------------
# CAMERA / HELPERS
# ------------------------------------------------------------

def build_camera(cameras):
    camera_data = bpy.data.cameras.new("CAM_Home")
    camera = bpy.data.objects.new("CAM_Home", camera_data)
    cameras.objects.link(camera)

    camera.location = CAMERA_LOCATION
    camera_data.angle = math.radians(CAMERA_FOV_DEG)

    look_at(camera, CAMERA_TARGET)

    bpy.context.scene.camera = camera
    return camera


def build_helpers(helpers):
    centerline = add_box(
        "HLP_Room_Centerline",
        (0.0, ROOM_CENTER_Y, 0.01),
        (0.03, ROOM_DEPTH, 0.02),
        helpers,
    )
    centerline.display_type = "WIRE"
    centerline.hide_render = True

    bpy.ops.object.empty_add(
        type="PLAIN_AXES",
        location=(0.0, 0.0, 0.0),
    )
    origin = bpy.context.active_object
    origin.name = "HLP_ZAENIA_Environment_Origin"
    move_to_collection(origin, helpers)
    origin.hide_render = True
    origin.empty_display_size = 1.5


# ------------------------------------------------------------
# SCENE / RENDER
# ------------------------------------------------------------

def configure_scene():
    scene = bpy.context.scene

    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"

    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"

    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 50
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (
        0.002,
        0.004,
        0.012,
        1.0,
    )
    background.inputs["Strength"].default_value = 0.080

    scene.view_settings.exposure = 0.58

    try:
        scene.view_settings.look = "AgX - Medium Low Contrast"
    except Exception:
        pass


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():
    clear_scene()
    configure_scene()

    root = create_collection(ROOT_COLLECTION)
    geo = create_collection(GEO_COLLECTION, root)
    lights = create_collection(LIGHT_COLLECTION, root)
    cameras = create_collection(CAMERA_COLLECTION, root)
    helpers = create_collection(HELPER_COLLECTION, root)

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

    mat_recess = make_principled_material(
        "MAT_Recess_Dark",
        RECESS_DARK,
        metallic=0.50,
        roughness=0.62,
    )

    mat_floor = make_principled_material(
        "MAT_Floor_Graphite",
        FLOOR_DARK,
        metallic=0.65,
        roughness=0.22,
    )

    mat_floor_seam = make_principled_material(
        "MAT_Floor_Seam",
        FLOOR_SEAM,
        metallic=0.25,
        roughness=0.62,
    )

    mat_back = make_principled_material(
        "MAT_Back_Wall",
        BACK_WALL_DARK,
        metallic=0.48,
        roughness=0.60,
    )

    mat_blue = make_emission_material(
        "MAT_Light_Midnight_Blue",
        MIDNIGHT_BLUE,
        strength=1.35,
    )

    mat_amber = make_emission_material(
        "MAT_Light_Amber_Orange",
        AMBER_ORANGE,
        strength=1.20,
    )

    mat_atmosphere = make_volume_material()

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

    build_wall_recesses(
        geo,
        mat_recess,
        mat_structure_secondary,
    )

    build_floor_seams(
        geo,
        mat_floor_seam,
    )

    build_ceiling_detail(
        geo,
        mat_recess,
        mat_structure_secondary,
    )

    build_side_catwalks(
        geo,
        mat_structure_secondary,
        mat_recess,
    )

    build_cross_bridge(
        geo,
        mat_structure_secondary,
        mat_recess,
        mat_blue,
        mat_amber,
    )

    build_diagonal_trusses(
        geo,
        mat_structure_secondary,
    )

    build_wall_towers(
        geo,
        mat_structure_secondary,
        mat_recess,
    )

    build_ceiling_panels(
        geo,
        mat_structure_secondary,
        mat_recess,
    )

    build_atmosphere(
        geo,
        mat_atmosphere,
    )

    build_practicals(
        geo,
        lights,
        mat_blue,
        mat_amber,
    )

    build_environment_fill_lights(
        lights
    )

    build_open_end_depth_fade(
        lights
    )

    build_camera(cameras)
    build_helpers(helpers)

    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_perspective = "CAMERA"
            break

    output_dir = r"C:\\Projects\\ZAENIA\\desktop\\blender"
    output_path = output_dir + r"\\ZAENIA_Warehouse_Stage06D_CinematicHangar.blend"

    bpy.ops.wm.save_as_mainfile(
        filepath=output_path
    )

    print("")
    print("======================================================")
    print("ZÆNIA Stage 6D cinematic hangar scene created.")
    print("")
    print("Stationary environment: YES")
    print("Midnight Blue: #191970")
    print("Amber Orange:  #FFB000")
    print("Camera motion: NONE")
    print("Light pulsing: NONE")
    print("Lighting balance: cinematic Midnight Blue + Amber Orange with wall/ceiling practicals")
    print("Core / UI: NOT ADDED")
    print("")
    print("Press F12 for the architectural validation render.")
    print("======================================================")
    print("")


main()
