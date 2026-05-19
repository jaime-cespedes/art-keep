from controller import Supervisor
import math
import json
import os
import tkinter as tk
from tkinter import messagebox

# =========================================================
# 1. Inicialización
# =========================================================

robot = Supervisor()
timestep = int(robot.getBasicTimeStep())

persona_node = robot.getFromDef("Persona1")
tiago_node = robot.getFromDef("Tiago_1")
supervisor_node = robot.getFromDef("Supervisor_Tiagos")

if persona_node is None:
    raise RuntimeError("No se encontró DEF Persona1")

if tiago_node is None:
    raise RuntimeError("No se encontró DEF Tiago_1")

if supervisor_node is None:
    raise RuntimeError("No se encontró DEF Supervisor_Tiagos")

tiago_custom_data = tiago_node.getField("customData")
supervisor_custom_data = supervisor_node.getField("customData")

translation_field = persona_node.getField("translation")
rotation_field = persona_node.getField("rotation")

# =========================================================
# 2. Configuración
# =========================================================

ALTURA_Z = 1.27

VEL_CAMINAR = 0.8
UMBRAL_PUNTO = 0.1

DISTANCIA_SEGUIR_TIAGO = 0.7
DISTANCIA_PELIGRO_CUADRO = 0.5
DISTANCIA_SEGURA_CUADRO = 1.4

CUADRO_ID_ALARMA = 6
TIEMPO_ESPERA_CERCA = 1.0

# =========================================================
# 3. Cargar museo.json
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "museo.json")

with open(JSON_PATH, "r", encoding="utf-8") as f:
    datos = json.load(f)

SALAS = {s["id"]: s for s in datos["salas"]}
CUADROS = datos["cuadros"]

cuadro_alarma = next(c for c in CUADROS if c["id"] == CUADRO_ID_ALARMA)

# =========================================================
# 4. Funciones de ventanas
# =========================================================

def mostrar_ventana_alarma():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    messagebox.showwarning(
        "PROXIMITY ALARM",
        "The visitor is too close to painting 6."
    )

    root.destroy()


def mostrar_ventana_segura():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    messagebox.showinfo(
        "SAFE DISTANCE RESTORED",
        "The visitor has moved back to a safe distance."
    )

    root.destroy()

# =========================================================
# 5. Movimiento persona
# =========================================================

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


def mirar_al_cuadro():
    x, y = get_pos()
    angulo = math.atan2(cuadro_alarma["y"] - y, cuadro_alarma["x"] - x)
    set_yaw(angulo)

# =========================================================
# 6. Funciones de TIAGo y cuadro
# =========================================================

def leer_estado_tiago():
    texto = tiago_custom_data.getSFString()

    try:
        return json.loads(texto)
    except Exception:
        return {}


def punto_delante_cuadro(cuadro, distancia_objetivo):
    sala = SALAS[cuadro["sala"]]

    cx = (sala["limites"]["x_min_pared"] + sala["limites"]["x_max_pared"]) / 2
    cy = (sala["limites"]["y_min_pared"] + sala["limites"]["y_max_pared"]) / 2

    dx = cx - cuadro["x"]
    dy = cy - cuadro["y"]

    norma = math.sqrt(dx * dx + dy * dy)

    if norma == 0:
        return cuadro["x"], cuadro["y"]

    return (
        cuadro["x"] + (dx / norma) * distancia_objetivo,
        cuadro["y"] + (dy / norma) * distancia_objetivo
    )


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


def tiago_ha_llegado_al_cuadro_6():
    estado_tiago = leer_estado_tiago()
    target_id = str(estado_tiago.get("target_id", ""))

    if target_id != "cuadro_6":
        return False

    pos_tiago = tiago_node.getPosition()

    punto_x, punto_y = punto_delante_cuadro(
        cuadro_alarma,
        0.9
    )

    distancia = math.sqrt(
        (pos_tiago[0] - punto_x) ** 2 +
        (pos_tiago[1] - punto_y) ** 2
    )

    return distancia < 0.45


def enviar_alarma():
    alarma = {
        "alerta": "INTRUSION",
        "cuadro_id": CUADRO_ID_ALARMA
    }

    supervisor_custom_data.setSFString(json.dumps(alarma))
    mostrar_ventana_alarma()

    print("[PERSONA] Alarma enviada al supervisor.")

# =========================================================
# 7. Puntos importantes
# =========================================================

OBJ_X_PELIGRO, OBJ_Y_PELIGRO = punto_delante_cuadro(
    cuadro_alarma,
    DISTANCIA_PELIGRO_CUADRO
)

OBJ_X_SEGURO, OBJ_Y_SEGURO = punto_delante_cuadro(
    cuadro_alarma,
    DISTANCIA_SEGURA_CUADRO
)

# =========================================================
# 8. Estados
# =========================================================

estado = "SIGUIENDO_TIAGO"

alarma_enviada = False
ventana_segura_mostrada = False
cuadro_6_procesado = False
tiempo_inicio_espera = 0.0

print("[PERSONA] Controlador iniciado.")
print("[PERSONA] Estado 1: seguir a Tiago_1 hasta cuadro 6.")
print("[PERSONA] Estado 2: acercarse demasiado al cuadro 6.")
print("[PERSONA] Estado 3: esperar 1 segundo y alejarse.")
print("[PERSONA] Estado 4: volver a seguir a Tiago_1.")

# =========================================================
# 9. Bucle principal
# =========================================================

while robot.step(timestep) != -1:
    dt = timestep / 1000.0

    # -----------------------------------------------------
    # 1. Seguir a TIAGo hasta cuadro 6
    # -----------------------------------------------------
    if estado == "SIGUIENDO_TIAGO":

        px, py = calcular_punto_seguimiento()
        mover_hacia(px, py, dt)

        if not cuadro_6_procesado and tiago_ha_llegado_al_cuadro_6():
            print("[PERSONA] Tiago_1 llegó al cuadro 6.")
            print("[PERSONA] Ahora se acerca demasiado al cuadro 6.")
            estado = "ACERCARSE_DEMASIADO"

    # -----------------------------------------------------
    # 2. Acercarse demasiado al cuadro 6
    # -----------------------------------------------------
    elif estado == "ACERCARSE_DEMASIADO":

        llego = mover_hacia(OBJ_X_PELIGRO, OBJ_Y_PELIGRO, dt)

        if llego:
            mirar_al_cuadro()

            if not alarma_enviada:
                alarma_enviada = True
                enviar_alarma()

            tiempo_inicio_espera = robot.getTime()
            estado = "ESPERAR_1_SEGUNDO"

    # -----------------------------------------------------
    # 3. Esperar 1 segundo y después alejarse
    # -----------------------------------------------------
    elif estado == "ESPERAR_1_SEGUNDO":

        mirar_al_cuadro()

        if robot.getTime() - tiempo_inicio_espera >= TIEMPO_ESPERA_CERCA:
            print("[PERSONA] Ha esperado 1 segundo. Ahora se aleja.")
            estado = "ALEJARSE_DEL_CUADRO"

    # -----------------------------------------------------
    # 4. Alejarse a distancia segura
    # -----------------------------------------------------
    elif estado == "ALEJARSE_DEL_CUADRO":

        llego = mover_hacia(OBJ_X_SEGURO, OBJ_Y_SEGURO, dt)

        if llego:
            mirar_al_cuadro()

            if not ventana_segura_mostrada:
                ventana_segura_mostrada = True
                mostrar_ventana_segura()

            print("[PERSONA] La persona ha vuelto a distancia segura.")

            cuadro_6_procesado = True
            estado = "SIGUIENDO_TIAGO"

    else:
        estado = "SIGUIENDO_TIAGO"