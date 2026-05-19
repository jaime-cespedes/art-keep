from controller import Supervisor
import math
import json

robot = Supervisor()
timestep = int(robot.getBasicTimeStep())

persona_node = robot.getFromDef("Persona2")
tiago_node = robot.getFromDef("Tiago_2")

if persona_node is None:
    raise RuntimeError("No se encontró DEF Persona2")

if tiago_node is None:
    raise RuntimeError("No se encontró DEF Tiago_2")

tiago_custom_data = tiago_node.getField("customData")

translation_field = persona_node.getField("translation")
rotation_field = persona_node.getField("rotation")

ALTURA_Z = 1.27
VEL_CAMINAR = 0.8
UMBRAL_PUNTO = 0.1
DISTANCIA_SEGUIR_TIAGO = 1.1


def get_pos():
    p = translation_field.getSFVec3f()
    return p[0], p[1]


def set_pos(x, y):
    translation_field.setSFVec3f([x, y, ALTURA_Z])


def set_yaw(yaw):
    rotation_field.setSFRotation([0, 0, 1, yaw])


def mover_hacia(destino_x, destino_y, dt):
    x, y = get_pos()

    dx = destino_x - x
    dy = destino_y - y
    distancia = math.sqrt(dx * dx + dy * dy)

    if distancia < UMBRAL_PUNTO:
        return True

    angulo = math.atan2(dy, dx)
    set_yaw(angulo)

    paso = min(VEL_CAMINAR * dt, distancia)

    nuevo_x = x + math.cos(angulo) * paso
    nuevo_y = y + math.sin(angulo) * paso

    set_pos(nuevo_x, nuevo_y)
    return False


def leer_estado_tiago():
    texto = tiago_custom_data.getSFString()

    try:
        return json.loads(texto)
    except Exception:
        return {}


def calcular_punto_seguimiento():
    pos_tiago = tiago_node.getPosition()
    estado_tiago = leer_estado_tiago()

    rx = pos_tiago[0]
    ry = pos_tiago[1]

    target = estado_tiago.get("target_point")

    if target is None:
        return rx - DISTANCIA_SEGUIR_TIAGO, ry

    tx = target[0]
    ty = target[1]

    dx = rx - tx
    dy = ry - ty

    norma = math.sqrt(dx * dx + dy * dy)

    if norma < 0.001:
        return rx - DISTANCIA_SEGUIR_TIAGO, ry

    px = rx + (dx / norma) * DISTANCIA_SEGUIR_TIAGO
    py = ry + (dy / norma) * DISTANCIA_SEGUIR_TIAGO

    return px, py


print("[PERSONA2] Controlador iniciado.")
print("[PERSONA2] Siguiendo a Tiago_2.")

while robot.step(timestep) != -1:
    dt = timestep / 1000.0

    px, py = calcular_punto_seguimiento()
    mover_hacia(px, py, dt)