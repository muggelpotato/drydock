# Blender scene for build.py: boat.glb turning in place
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

OUT, FPS, LIGHTING = sys.argv[-3], int(sys.argv[-2]), sys.argv[-1]
TURN = 2.5
TICKS = math.lcm(round(360 / TURN), 16)
FRAMES = TICKS * FPS // 20
WIDTH, HEIGHT = 1200, 400
FILL = 0.8
ELEVATION = math.radians(20)
YAW = math.radians(-135)
RENDERER = Matrix(((0, 0, -1), (0, -1, 0), (-1, 0, 0)))
OAR = Matrix(((-1, 0, 0), (0, -1, 0), (0, 0, 1)))
Z_UP = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
scene = bpy.context.scene
camera = scene.camera


def paddle(time, side):
    lerp = lambda a, b, t: a + (b - a) * t
    x = lerp(-math.pi / 3, -math.pi / 12, (math.sin(-time) + 1) / 2)
    y = lerp(-math.pi / 4, math.pi / 4, (math.sin(-time + 1) + 1) / 2)
    if side == 1:
        y = math.pi - y
    part = Matrix.Rotation(math.pi / 16, 3, "Z") @ Matrix.Rotation(y, 3, "Y") @ Matrix.Rotation(x, 3, "X")
    return (Z_UP @ RENDERER @ part @ OAR @ Z_UP.transposed()).to_quaternion()

def light(energy, position, size, color):
    data = bpy.data.lights.new("Light", "AREA")
    data.energy, data.color, data.shape, data.size = energy, color, "DISK", size
    obj = bpy.data.objects.new("Light", data)
    scene.collection.objects.link(obj)
    obj.location = target + Vector(position)
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()

def node(tree, kind, operation, *inputs):
    new = tree.nodes.new(kind)
    new.operation = operation
    for socket, value in zip(new.inputs, inputs):
        if isinstance(value, bpy.types.NodeSocket):
            tree.links.new(value, socket)
        else:
            socket.default_value = value
    return new.outputs["Value"]


bpy.data.batch_remove([bpy.data.objects["Cube"], bpy.data.objects["Light"]])
bpy.ops.import_scene.gltf(filepath=str(Path(__file__).with_name("boat.glb")))
empties = {obj.name.split(".")[0]: obj for obj in bpy.data.objects if obj.type == "EMPTY"}
root, left, right = empties["boat_root"], empties["paddle_left"], empties["paddle_right"]
meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
materials = {slot.material for obj in meshes for slot in obj.material_slots}

root.rotation_mode = "XYZ"
left.rotation_quaternion = paddle(0, 0)
for frame in range(1, FRAMES + 1):
    tick = (frame - 1) * 20 / FPS
    root.rotation_euler = (0, 0, YAW + math.radians(TURN * tick))
    right.rotation_quaternion = paddle(math.pi / 8 * tick, 1)
    root.keyframe_insert("rotation_euler", frame=frame)
    right.keyframe_insert("rotation_quaternion", frame=frame)

points = []
for frame in range(1, FRAMES + 1):
    scene.frame_set(frame)
    points += [obj.matrix_world @ vertex.co for obj in meshes for vertex in obj.data.vertices]
target = Vector((0, 0, (min(p.z for p in points) + max(p.z for p in points)) / 2))
camera.location = target + 9 * Vector((0, -math.cos(ELEVATION), math.sin(ELEVATION)))
camera.rotation_euler = (math.pi / 2 - ELEVATION, 0, 0)
scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
bpy.context.view_layer.update()
for _ in range(8):
    view = [world_to_camera_view(scene, camera, p) for p in points]
    x0, x1 = min(v.x for v in view), max(v.x for v in view)
    y0, y1 = min(v.y for v in view), max(v.y for v in view)
    camera.data.shift_x += (x0 + x1) / 2 - 0.5
    camera.data.shift_y += ((y0 + y1) / 2 - 0.5) * HEIGHT / WIDTH
    camera.data.lens *= FILL / (y1 - y0)

if LIGHTING == "studio":
    light(500, (-5, -5, 6), 3, (1, 0.96, 0.9))
    light(60, (6, -4, 1), 6, (0.9, 0.95, 1))
    light(500, (1, 7, 4), 2, (1, 1, 1))
    background = scene.world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (1, 1, 1, 1)
    background.inputs["Strength"].default_value = 0.1
    for material in materials:
        bsdf = material.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Roughness"].default_value = 0.8
        bsdf.inputs["Specular IOR Level"].default_value = 0.3
    scene.view_settings.view_transform = "Khronos PBR Neutral"
    scene.cycles.denoising_use_gpu = True
else:
    for material in materials:
        tree = material.node_tree
        bsdf = tree.nodes["Principled BSDF"]
        normal = tree.nodes.new("ShaderNodeNewGeometry").outputs["Normal"]
        diffuse = [node(tree, "ShaderNodeMath", "MAXIMUM", node(tree, "ShaderNodeVectorMath", "DOT_PRODUCT", normal, Vector(direction).normalized()), 0) for direction in ((0.2, 0.7, 1), (-0.2, -0.7, 1))]
        shade = node(tree, "ShaderNodeMath", "MINIMUM", node(tree, "ShaderNodeMath", "MULTIPLY_ADD", node(tree, "ShaderNodeMath", "ADD", *diffuse), 0.6, 0.4), 1)
        emission = tree.nodes.new("ShaderNodeEmission")
        tree.links.new(bsdf.inputs["Base Color"].links[0].from_socket, emission.inputs["Color"])
        tree.links.new(node(tree, "ShaderNodeMath", "POWER", shade, 2.2), emission.inputs["Strength"])
        mix = tree.nodes.new("ShaderNodeMixShader")
        tree.links.new(bsdf.inputs["Alpha"].links[0].from_socket, mix.inputs["Fac"])
        tree.links.new(tree.nodes.new("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
        tree.links.new(emission.outputs[0], mix.inputs[2])
        tree.links.new(mix.outputs[0], tree.nodes["Material Output"].inputs["Surface"])
    scene.view_settings.view_transform = "Standard"
    scene.cycles.use_denoising = False

cycles = bpy.context.preferences.addons["cycles"].preferences
cycles.compute_device_type = "OPTIX"
cycles.refresh_devices()
scene.render.engine = "CYCLES"
scene.cycles.device = "GPU"
scene.cycles.samples = 512
scene.render.use_persistent_data = True
scene.render.film_transparent = True
scene.render.dither_intensity = 0
scene.frame_end = FRAMES
scene.render.filepath = f"{OUT}/"
bpy.ops.render.render(animation=True)