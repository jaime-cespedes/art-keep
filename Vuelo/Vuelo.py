from controller import Supervisor
import math
import json
import tkinter as tk
from tkinter import messagebox

# =========================================================
# 1. Inicialización
# =========================================================

robot = Supervisor()
timestep = int(robot.getBasicTimeStep())

robot_node = robot.getSelf()
custom_data_field = robot_node.getField("customData")

left_motor = robot.getDevice("wheel_left_joint")
right_motor = robot.getDevice("wheel_right_joint")

left_motor.setPosition(float("inf"))
right_motor.setPosition(float("inf"))
left_motor.setVelocity(0.0)
right_motor.setVelocity(0.0)

try:
    MI_NOMBRE = robot_node.getDef()
except Exception:
    MI_NOMBRE = ""

TIAGOS_DEF = ["Tiago_1", "Tiago_2"]
DISTANCIA_SEGURA_WP = 0.8
# =========================================================
# Sensores y avoidance
# =========================================================

DIST_THRESHOLD = 4
TURN_STEPS = 45
EVADE_STEPS = 30
MAX_VELOCITY = 10.15
K_HEADING = 2.0

ds_right = robot.getDevice("Sharp's IR sensor GP2Y0A710K0F")
ds_left  = robot.getDevice("Sharp's IR sensor GP2Y0A710K0F(1)")

for ds in [ds_right, ds_left]:
    if ds:
        ds.enable(timestep)

evasion_state = "NAVEGAR"
evasion_counter = 0
giro_lv = 0.0
giro_rv = 0.0

# =========================================================
# 2. Parámetros de movimiento
# =========================================================

VEL_AVANCE = 2.5
VEL_GIRO = 2.0
UMBRAL_PUNTO = 0.35
UMBRAL_ANGULO = 0.08

estado = "IDLE"
mission_id_actual = None
waypoints = []
indice_wp = 0
ultima_orden_procesada = None

aviso_alerta_mostrado = False

# =========================================================
# 3. Movimiento básico
# =========================================================

def detener():
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)


def avanzar(velocidad=None):
    if velocidad is None:
        velocidad = VEL_AVANCE

    left_motor.setVelocity(velocidad)
    right_motor.setVelocity(velocidad)


def girar_izquierda():
    left_motor.setVelocity(-VEL_GIRO)
    right_motor.setVelocity(VEL_GIRO)


def girar_derecha():
    left_motor.setVelocity(VEL_GIRO)
    right_motor.setVelocity(-VEL_GIRO)

def decidir_giro(val_left, val_right):

    obs_left = val_left > DIST_THRESHOLD
    obs_right = val_right > DIST_THRESHOLD

    turn_vel = 2.0

    if obs_left and not obs_right:
        return (turn_vel, -turn_vel)

    elif obs_right and not obs_left:
        return (-turn_vel, turn_vel)

    else:
        return (turn_vel, -turn_vel)


def normalizar_angulo(a):
    while a > math.pi:
        a -= 2 * math.pi

    while a < -math.pi:
        a += 2 * math.pi

    return a


def obtener_yaw():
    o = robot_node.getOrientation()
    return math.atan2(o[3], o[0])


def ir_a_punto(posicion, destino_x, destino_y, umbral=UMBRAL_PUNTO):
    global evasion_state, evasion_counter, giro_lv, giro_rv

    val_left  = ds_left.getValue() if ds_left else 0
    val_right = ds_right.getValue() if ds_right else 0
    obs_left  = val_left  > DIST_THRESHOLD
    obs_right = val_right > DIST_THRESHOLD

    dx = destino_x - posicion[0]
    dy = destino_y - posicion[1]
    distancia = math.sqrt(dx * dx + dy * dy)

    if distancia <= umbral:
        detener()
        evasion_state = "NAVEGAR"
        return True

    # ── MÁQUINA DE ESTADOS CON NAVEGACIÓN PROPORCIONAL ─────
    if evasion_state == "NAVEGAR":
        if obs_left or obs_right:
            giro_lv, giro_rv = decidir_giro(val_left, val_right)
            evasion_state   = "GIRAR"
            evasion_counter = TURN_STEPS
            print("🛑 Evasión: Girando...")
        else:
            # LÓGICA TIAGo LITE: Giro proporcional mientras avanza
            angulo_objetivo = math.atan2(dy, dx)
            yaw = obtener_yaw()
            error_angulo = normalizar_angulo(angulo_objetivo - yaw)
            
            # Ajuste de velocidad diferencial
            correccion = K_HEADING * error_angulo
            v_l = max(-MAX_VELOCITY, min(MAX_VELOCITY, VEL_AVANCE - correccion))
            v_r = max(-MAX_VELOCITY, min(MAX_VELOCITY, VEL_AVANCE + correccion))
            
            left_motor.setVelocity(v_l)
            right_motor.setVelocity(v_r)

    elif evasion_state == "GIRAR":
        left_motor.setVelocity(giro_lv)
        right_motor.setVelocity(giro_rv)
        evasion_counter -= 1
        if evasion_counter <= 0:
            evasion_state   = "EVADIR"
            evasion_counter = EVADE_STEPS

    elif evasion_state == "EVADIR":
        left_motor.setVelocity(VEL_AVANCE)
        right_motor.setVelocity(VEL_AVANCE)
        evasion_counter -= 1
        if obs_left or obs_right:
            giro_lv, giro_rv = decidir_giro(val_left, val_right)
            evasion_state   = "GIRAR"
            evasion_counter = TURN_STEPS
        elif evasion_counter <= 0:
            evasion_state = "NAVEGAR"

    return False

# =========================================================
# 4. Comunicación por customData
# =========================================================

def leer_custom_data():
    if custom_data_field is None:
        return {}

    texto = custom_data_field.getSFString()

    try:
        return json.loads(texto)
    except Exception:
        return {"status": texto}


def leer_custom_data_nodo(nodo):
    campo = nodo.getField("customData")

    if campo is None:
        return {}

    texto = campo.getSFString()

    try:
        return json.loads(texto)
    except Exception:
        return {"status": texto}


def extraer_destino_waypoint(wp):
    if isinstance(wp, dict):
        destino = wp.get("punto", None)
        nombre = wp.get("id", f"wp_{indice_wp}")
    else:
        destino = wp
        nombre = f"wp_{indice_wp}"

    if destino is None or len(destino) < 2:
        return None, None, nombre

    tx = destino[0]
    ty = destino[1]

    return tx, ty, nombre


def punto_actual_objetivo():
    if indice_wp < len(waypoints):
        wp = waypoints[indice_wp]
        tx, ty, nombre = extraer_destino_waypoint(wp)

        if tx is not None and ty is not None:
            return [tx, ty], nombre

    return None, None


def escribir_estado(status, extra=None):
    if custom_data_field is None:
        return

    target_point, target_id = punto_actual_objetivo()

    data = {
        "status": status,
        "mission_id": mission_id_actual,
        "current_waypoint": indice_wp,
        "waypoints": waypoints,
        "target_point": target_point,
        "target_id": target_id
    }

    if extra:
        data.update(extra)

    custom_data_field.setSFString(json.dumps(data))


def cargar_orden(orden):
    global estado
    global mission_id_actual
    global waypoints
    global indice_wp
    global ultima_orden_procesada
    global aviso_alerta_mostrado

    if not isinstance(orden, dict):
        return False

    if orden.get("cmd") != "GO_TO_WAYPOINTS":
        return False

    nueva_mision = orden.get("mission_id")

    if nueva_mision == ultima_orden_procesada:
        return False

    nuevos_waypoints = orden.get("waypoints", [])

    if not nuevos_waypoints:
        mission_id_actual = nueva_mision
        estado = "ERROR"
        escribir_estado("ERROR", {"reason": "empty_waypoints"})
        print("[TIAGo] ERROR: misión sin waypoints.")
        return True

    mission_id_actual = nueva_mision
    ultima_orden_procesada = nueva_mision
    waypoints = nuevos_waypoints
    indice_wp = 0
    estado = "MOVING"
    aviso_alerta_mostrado = False

    print(f"\n[TIAGo] Nueva misión recibida: {mission_id_actual}")
    print(f"[TIAGo] Waypoints recibidos: {len(waypoints)}")

    for i, wp in enumerate(waypoints):
        print(f"  wp {i}: {wp}")

    escribir_estado("MOVING")
    return True

# =========================================================
# 5. Evitar coincidir en el mismo waypoint
# =========================================================

def distancia_2d(p1, p2):
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return math.sqrt(dx * dx + dy * dy)


def nombre_tiago_actual():
    if MI_NOMBRE in TIAGOS_DEF:
        return MI_NOMBRE

    for nombre in TIAGOS_DEF:
        nodo = robot.getFromDef(nombre)

        if nodo is not None and nodo == robot_node:
            return nombre

    return MI_NOMBRE


def debo_esperar_por_waypoint(tx, ty, target_id):
    mi_nombre = nombre_tiago_actual()
    mi_pos = robot_node.getPosition()
    mi_dist = distancia_2d([mi_pos[0], mi_pos[1]], [tx, ty])

    for otro_nombre in TIAGOS_DEF:
        if otro_nombre == mi_nombre:
            continue

        otro_nodo = robot.getFromDef(otro_nombre)

        if otro_nodo is None:
            continue

        otro_estado = leer_custom_data_nodo(otro_nodo)
        otro_status = otro_estado.get("status")

        if otro_status not in ["MOVING", "WAITING"]:
            continue

        otro_target = otro_estado.get("target_point")
        otro_target_id = otro_estado.get("target_id")

        if otro_target is None:
            continue

        mismo_id = target_id is not None and otro_target_id == target_id
        mismo_punto = distancia_2d([tx, ty], otro_target) < DISTANCIA_SEGURA_WP

        if not mismo_id and not mismo_punto:
            continue

        otro_pos = otro_nodo.getPosition()
        otro_dist = distancia_2d([otro_pos[0], otro_pos[1]], [tx, ty])

        if otro_dist + 0.05 < mi_dist:
            return True

        if abs(otro_dist - mi_dist) <= 0.05 and otro_nombre < mi_nombre:
            return True

    return False

# =========================================================
# 6. Aviso a persona
# =========================================================

def avisar_persona_alerta():
    global aviso_alerta_mostrado

    if aviso_alerta_mostrado:
        return

    aviso_alerta_mostrado = True

    print("[TIAGo]: Please step away from the artwork.")
    print("[TIAGo]: You are too close to the painting.")

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    messagebox.showwarning(
        "TIAGo Warning",
        "Please step away from the artwork.\nYou are too close to the painting."
    )

    root.destroy()

# =========================================================
# 7. Bucle principal
# =========================================================

print("[TIAGo] Controlador Vuelo iniciado.")
escribir_estado("IDLE")

while robot.step(timestep) != -1:

    orden = leer_custom_data()

    if isinstance(orden, dict) and orden.get("cmd") == "GO_TO_WAYPOINTS":
        cargar_orden(orden)

    if estado == "IDLE":
        detener()
        escribir_estado("IDLE")

    elif estado in ["MOVING", "WAITING"]:

        if indice_wp >= len(waypoints):
            detener()
            
            # ════════════════════════════════════════════════════════════
            # SOLUCIÓN CLAVE: Primero se atiende la alerta (bloqueante)
            # ════════════════════════════════════════════════════════════
            extra = {}
            if "ALERTA" in str(mission_id_actual):
                avisar_persona_alerta()  # El código se detiene aquí hasta que pulsas OK
                extra["alerta_atendida"] = True

            # SÓLO cuando cierras el pop-up, el supervisor se entera de que terminaste
            estado = "ARRIVED"
            escribir_estado("ARRIVED", extra)

            print(f"[TIAGo] Misión completada de forma segura: {mission_id_actual}")
            continue

        wp = waypoints[indice_wp]
        tx, ty, nombre = extraer_destino_waypoint(wp)

        if tx is None or ty is None:
            print("[TIAGo] ERROR: waypoint inválido:", wp)
            estado = "ERROR"
            escribir_estado("ERROR", {"reason": "invalid_waypoint"})
            continue

        if debo_esperar_por_waypoint(tx, ty, nombre):
            detener()
            estado = "WAITING"
            escribir_estado("WAITING", {"reason": "waypoint_occupied"})
            continue

        estado = "MOVING"
        escribir_estado("MOVING")

        posicion = robot_node.getPosition()
        llego = ir_a_punto(posicion, tx, ty)

        if llego:
            print(f"[TIAGo] Waypoint alcanzado: {nombre}")
            indice_wp += 1
            escribir_estado("MOVING")

    elif estado == "ARRIVED":
        detener()

        extra = {}

        if "ALERTA" in str(mission_id_actual):
            extra["alerta_atendida"] = True

        escribir_estado("ARRIVED", extra)

    elif estado == "ERROR":
        detener()
        escribir_estado("ERROR")