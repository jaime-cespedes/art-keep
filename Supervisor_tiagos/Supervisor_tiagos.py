from controller import Supervisor
import json
import os
import math

import time

# =========================================================
# 1. CONFIGURACIÓN DEL SUPERVISOR
# =========================================================

TIAGOS_DEF = ["Tiago_1", "Tiago_2"]

ORDEN_MANUAL_SALAS = {
    1: [3, 1, 2, 4, 5, 6]
}

DISTANCIA_SEGURA_WP = 0.8

PARKING_HUB = {
    "Tiago_1": [-2.10, -13.00],
    "Tiago_2": [1.60, -13.00]
}

MISIONES_TIAGOS = {
    "Tiago_1": {
        "tipo": "sala",
        "sala_id": 1
    },
    "Tiago_2": {
        "tipo": "todo"
    }
}

# =========================================================
# 2. INICIALIZACIÓN
# =========================================================

robot = Supervisor()
timestep = int(robot.getBasicTimeStep())

self_node = robot.getSelf()
self_custom = self_node.getField("customData")

tiagos = {}

for nombre in TIAGOS_DEF:
    nodo = robot.getFromDef(nombre)

    if nodo is not None:
        tiagos[nombre] = nodo
        print(f"[SUPERVISOR_TIAGOS] Encontrado {nombre}")
    else:
        print(f"[SUPERVISOR_TIAGOS] No encontrado {nombre}")

if not tiagos:
    raise RuntimeError("No se encontró ningún TIAGo.")

# =========================================================
# 3. CARGAR museo.json
# =========================================================

try:
    with open("museo.json", "r", encoding="utf-8") as f:
        datos = json.load(f)
except Exception as e:
    raise RuntimeError(f"No se pudo cargar museo.json: {e}")

SALAS = {sala["id"]: sala for sala in datos["salas"]}
CUADROS = datos["cuadros"]
HUB_EXTERIOR = datos["parametros"]["hub_exterior"]
MARGEN_PAREDES = datos["parametros"].get("margen_paredes", 0.65)

ROBOTS_FIN_NOTIFICADO = set()
MEMORIA_MISIONES = {nombre: None for nombre in TIAGOS_DEF}

# Flag que bloquea la reanudación automática mientras el robot
# aún no ha aceptado la misión LLM recién enviada.
MISION_LLM_PENDIENTE = {nombre: False for nombre in TIAGOS_DEF}
MISSION_FILES = {
    "Tiago_1": "C:/Users/domit/Desktop/UPM/8vo semestre/ATA/proyecto/ArtKeep/ATA_MUSEO_TIAGO_DDS_FINAL/ATA_MUSEO_TIAGO_DDS_FINAL/controllers/artkeep_shared/mission_command_1.json",
    "Tiago_2": "C:/Users/domit/Desktop/UPM/8vo semestre/ATA/proyecto/ArtKeep/ATA_MUSEO_TIAGO_DDS_FINAL/ATA_MUSEO_TIAGO_DDS_FINAL/controllers/artkeep_shared/mission_command_2.json"
}

# =========================================================
# 4. FUNCIONES AUXILIARES
# =========================================================

def distancia_2d(p1, p2):
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return math.sqrt(dx * dx + dy * dy)


def get_custom_data(nodo):
    campo = nodo.getField("customData")

    if campo is None:
        return {}

    texto = campo.getSFString()

    try:
        return json.loads(texto)
    except Exception:
        return {"status": texto}


def set_custom_data(nodo, data):
    campo = nodo.getField("customData")

    if campo is not None:
        campo.setSFString(json.dumps(data))


def estado_tiago(nombre):
    return get_custom_data(tiagos[nombre])


def tiago_libre(nombre):
    estado = estado_tiago(nombre)
    status = estado.get("status", "IDLE")

    return status in [
        "IDLE",
        "ERROR",
        "",
        None
    ]


def limpiar_custom_supervisor():
    if self_custom is not None:
        self_custom.setSFString("IDLE")


def obtener_punto_wp(wp):
    if isinstance(wp, dict):
        return wp.get("punto")
    return wp


def waypoint_ocupado_por_otro(nombre_tiago, punto):
    if punto is None:
        return False

    for otro_nombre in TIAGOS_DEF:
        if otro_nombre == nombre_tiago:
            continue

        estado = estado_tiago(otro_nombre)
        status = estado.get("status")

        if status not in ["MOVING", "WAITING"]:
            continue

        otro_punto = estado.get("target_point")

        if otro_punto is None:
            continue

        if distancia_2d(punto, otro_punto) < DISTANCIA_SEGURA_WP:
            return True

    return False

# =========================================================
# 5. RUTAS DESDE museo.json
# =========================================================

def obtener_lane_sala(sala_id, sentido):
    rutas = datos.get("rutas_desde_hub", {})
    bloque = rutas.get(str(sala_id), {})

    if isinstance(bloque, dict):
        return bloque.get(sentido, [])

    if isinstance(bloque, list):
        return bloque

    return []


def punto_parada_cuadro(cuadro):
    sala = SALAS[cuadro["sala"]]
    limites = sala["limites"]

    cx = (limites["x_min_pared"] + limites["x_max_pared"]) / 2.0
    cy = (limites["y_min_pared"] + limites["y_max_pared"]) / 2.0

    dx = cx - cuadro["x"]
    dy = cy - cuadro["y"]

    norma = math.sqrt(dx * dx + dy * dy)

    if norma == 0:
        px = cuadro["x"]
        py = cuadro["y"]
    else:
        offset = 0.9
        px = cuadro["x"] + (dx / norma) * offset
        py = cuadro["y"] + (dy / norma) * offset

    px = max(
        limites["x_min_pared"] + MARGEN_PAREDES,
        min(limites["x_max_pared"] - MARGEN_PAREDES, px)
    )

    py = max(
        limites["y_min_pared"] + MARGEN_PAREDES,
        min(limites["y_max_pared"] - MARGEN_PAREDES, py)
    )

    return [px, py]


def ordenar_cuadros_sala(sala_id):
    cuadros = [c for c in CUADROS if c["sala"] == sala_id]

    if sala_id in ORDEN_MANUAL_SALAS:
        orden = []

        for cuadro_id in ORDEN_MANUAL_SALAS[sala_id]:
            cuadro = next((c for c in cuadros if c["id"] == cuadro_id), None)

            if cuadro is not None:
                orden.append(cuadro)

        return orden

    sala = SALAS[sala_id]
    start = sala["puerta"]["dentro"]

    pendientes = cuadros[:]
    orden = []

    cx = start[0]
    cy = start[1]

    while pendientes:
        mejor = min(
            pendientes,
            key=lambda c: distancia_2d([cx, cy], punto_parada_cuadro(c))
        )

        orden.append(mejor)

        p = punto_parada_cuadro(mejor)
        cx = p[0]
        cy = p[1]

        pendientes.remove(mejor)

    return orden


def sala_desde_posicion(pos_x, pos_y):
    """Devuelve el id de sala en la que está la posición dada, o None si está fuera."""
    for sala_id, sala in SALAS.items():
        lim = sala["limites"]
        if (lim["x_min_pared"] <= pos_x <= lim["x_max_pared"] and
                lim["y_min_pared"] <= pos_y <= lim["y_max_pared"]):
            return sala_id
    return None

# =========================================================
# 6. CONSTRUCCIÓN DE MISIONES
# =========================================================

def waypoints_para_ir_a_sala(sala_id):
    waypoints = []

    waypoints.append({
        "id": "hub_exterior",
        "punto": HUB_EXTERIOR,
        "tipo": "hub"
    })

    lane_ida = obtener_lane_sala(sala_id, "ida")

    for wp in lane_ida:
        waypoints.append(wp)

    return waypoints


def waypoints_para_salir_de_sala(sala_id, nombre_tiago=None):
    waypoints = []

    lane_vuelta = obtener_lane_sala(sala_id, "vuelta")

    for wp in lane_vuelta:
        waypoints.append(wp)

    waypoints.append({
        "id": "hub_exterior",
        "punto": HUB_EXTERIOR,
        "tipo": "hub"
    })

    if nombre_tiago in PARKING_HUB:
        waypoints.append({
            "id": f"parking_hub_{nombre_tiago}",
            "punto": PARKING_HUB[nombre_tiago],
            "tipo": "parking"
        })

    return waypoints


def waypoints_para_recorrer_sala(sala_id, nombre_tiago=None):
    waypoints = waypoints_para_ir_a_sala(sala_id)

    cuadros = ordenar_cuadros_sala(sala_id)

    for cuadro in cuadros:
        waypoints.append({
            "id": f"cuadro_{cuadro['id']}",
            "punto": punto_parada_cuadro(cuadro),
            "tipo": "obra",
            "nombre": cuadro["nombre"]
        })

    waypoints.extend(waypoints_para_salir_de_sala(sala_id, nombre_tiago))

    return waypoints


def waypoints_para_ir_a_cuadro(cuadro_id, nombre_tiago=None, desde_sala_id=None):
    """
    Genera waypoints completos para navegar hasta un cuadro concreto.

    Si el robot ya está dentro de una sala (desde_sala_id no es None), primero
    genera los waypoints de salida de esa sala antes de los de entrada a la sala
    del cuadro destino. Esto evita la navegación en línea recta atravesando paredes.

    Args:
        cuadro_id: ID del cuadro destino.
        nombre_tiago: Nombre del robot (para el parking).
        desde_sala_id: ID de la sala donde está actualmente el robot, o None.
    """
    cuadro = next((c for c in CUADROS if c["id"] == cuadro_id), None)

    if cuadro is None:
        return []

    sala_destino_id = cuadro["sala"]
    waypoints = []

    # ---------------------------------------------------------
    # Si el robot está dentro de una sala, primero hay que salir
    # ---------------------------------------------------------
    if desde_sala_id is not None and desde_sala_id != sala_destino_id:
        salida = obtener_lane_sala(desde_sala_id, "vuelta")
        waypoints.extend(salida)
        waypoints.append({
            "id": "hub_exterior",
            "punto": HUB_EXTERIOR,
            "tipo": "hub"
        })

    elif desde_sala_id is not None and desde_sala_id == sala_destino_id:
        # Mismo sala: no hace falta salir ni entrar, ir directo al cuadro
        waypoints.append({
            "id": f"cuadro_{cuadro['id']}",
            "punto": punto_parada_cuadro(cuadro),
            "tipo": "obra",
            "nombre": cuadro["nombre"]
        })
        return waypoints

    else:
        # Robot en el hub o pasillo: añadir hub como punto de partida
        waypoints.append({
            "id": "hub_exterior",
            "punto": HUB_EXTERIOR,
            "tipo": "hub"
        })

    # ---------------------------------------------------------
    # Entrar a la sala destino
    # ---------------------------------------------------------
    entrada = obtener_lane_sala(sala_destino_id, "ida")
    waypoints.extend(entrada)

    # ---------------------------------------------------------
    # Waypoint final: el cuadro
    # ---------------------------------------------------------
    waypoints.append({
        "id": f"cuadro_{cuadro['id']}",
        "punto": punto_parada_cuadro(cuadro),
        "tipo": "obra",
        "nombre": cuadro["nombre"]
    })

    return waypoints


def waypoints_para_recorrer_todo(nombre_tiago=None):
    waypoints = []
    salas_a_recorrer = [2, 1, 3]

    for sala_id in salas_a_recorrer:
        waypoints.extend(waypoints_para_recorrer_sala(sala_id, nombre_tiago))

    return waypoints


def crear_mision_para_tiago(nombre_tiago):
    config = MISIONES_TIAGOS.get(nombre_tiago, {"tipo": "ninguna"})
    tipo = config.get("tipo", "ninguna")

    if tipo == "sala":
        sala_id = config.get("sala_id")
        waypoints = waypoints_para_recorrer_sala(sala_id, nombre_tiago)
        mission_id = f"SALA_{sala_id}"

    elif tipo == "cuadro":
        cuadro_id = config.get("cuadro_id")
        waypoints = waypoints_para_ir_a_cuadro(cuadro_id, nombre_tiago)
        mission_id = f"CUADRO_{cuadro_id}"

    elif tipo == "todo":
        waypoints = waypoints_para_recorrer_todo(nombre_tiago)
        mission_id = "TODO_MUSEO"

    else:
        waypoints = []
        mission_id = "SIN_MISION"

    return mission_id, waypoints

# =========================================================
# 7. ENVIAR MISIÓN A TIAGO
# =========================================================

def enviar_mision(nombre_tiago, mission_id, waypoints):
    if not waypoints:
        print("[SUPERVISOR_TIAGOS] No se puede enviar misión vacía.")
        return False

    primer_punto = obtener_punto_wp(waypoints[0])

    if waypoint_ocupado_por_otro(nombre_tiago, primer_punto):
        print(f"[SUPERVISOR_TIAGOS] {nombre_tiago} espera: primer waypoint ocupado.")
        return False

    orden = {
        "cmd": "GO_TO_WAYPOINTS",
        "mission_id": mission_id,
        "waypoints": waypoints
    }

    ROBOTS_FIN_NOTIFICADO.discard(nombre_tiago)

    set_custom_data(tiagos[nombre_tiago], orden)

    print("\n===================================")
    print(f"ROBOT: {nombre_tiago}")
    print(f"MISIÓN: {mission_id}")
    print(f"WAYPOINTS: {len(waypoints)}")
    print("===================================")

    for i, wp in enumerate(waypoints):
        print(f"  {i}: {wp}")

    return True


def guardar_mision_actual(nombre):
    """
    Guarda los waypoints PENDIENTES de la misión actual para reanudarla después.
    Solo guarda misiones de tour (SALA / TODO_MUSEO), no misiones LLM puntuales.
    """
    estado = estado_tiago(nombre)
    m_id = str(estado.get("mission_id", ""))

    # No guardar misiones LLM puntuales (ir a cuadro concreto)
    # Solo tiene sentido reanudar tours de sala o museo completo
    if not any(k in m_id for k in ["SALA_", "TODO_MUSEO", "GUIA", "PATRULLA"]):
        return False

    wps = estado.get("waypoints", [])
    idx = estado.get("current_waypoint", 0)

    # Guardamos desde idx (waypoint actual, no el siguiente) para no
    # saltarnos el punto al que el robot estaba yendo
    wps_restantes = wps[idx:] if len(wps) > idx else wps

    # Filtrar: quedarnos solo con los waypoints que siguen siendo
    # relevantes (obras y salida), no los de entrada que ya recorrió
    MEMORIA_MISIONES[nombre] = {
        "mission_id": m_id + f"_R{int(time.time())}",
        "waypoints": wps_restantes
    }

    print(f"💾 [MEMORIA] {nombre}: misión '{m_id}' guardada desde wp {idx} "
          f"({len(wps_restantes)} waypoints restantes).")

    return True


def obtener_sala_actual_tiago(nombre):
    """Devuelve el id de sala donde está el robot ahora mismo, o None."""
    pos = tiagos[nombre].getPosition()
    return sala_desde_posicion(pos[0], pos[1])


def procesar_mision_llm():

    for robot_objetivo, mission_file in MISSION_FILES.items():

        if not os.path.exists(mission_file):
            continue

        try:

            with open(mission_file, "r", encoding="utf-8") as f:
                mission_data = json.load(f)

            print("\n🤖 MISIÓN RECIBIDA DESDE LLM")
            print(mission_data)

            print("===================================")
            print("✅ DEBUG LLM → SUPERVISOR OK")
            print(f"Robot destino: {robot_objetivo}")

            modo = mission_data.get("modo")

            print(f"Modo recibido: {modo}")

            if modo == 1:
                print(f"🎯 Cuadro objetivo: {mission_data.get('cuadro_id')}")

            elif modo == 2:
                print(f"🏛️ Sala objetivo: {mission_data.get('sala_id')}")

            print("===================================")

            # =====================================================
            # MODO 1 -> IR A CUADRO
            # Antes de interrumpir, guardar misión actual y
            # calcular la ruta correcta desde donde esté el robot.
            # =====================================================

            if modo == 1:
                cuadro_id = mission_data.get("cuadro_id")
                # Guardar la misión actual para reanudarla después
                guardar_mision_actual(robot_objetivo)
                # Detectar en qué sala está el robot ahora mismo
                sala_actual = obtener_sala_actual_tiago(robot_objetivo)

                print(f"📍 {robot_objetivo} está en sala: {sala_actual}")

                waypoints = waypoints_para_ir_a_cuadro(
                    cuadro_id,
                    nombre_tiago=robot_objetivo,
                    desde_sala_id=sala_actual
                )
                mission_id = f"LLM_CUADRO_{cuadro_id}"
                ok = enviar_mision(
                    robot_objetivo,
                    mission_id,
                    waypoints
                )
                if ok:
                    # Bloquear reanudación hasta que el robot acepte esta misión
                    MISION_LLM_PENDIENTE[robot_objetivo] = True
                    
                    # ════════════════════════════════════════════════════════════
                    # SOLUCIÓN CLAVE: Forzamos al supervisor a olvidar el tour viejo
                    # ════════════════════════════════════════════════════════════
                    # if robot_objetivo in misiones_asignadas:
                    #     del misiones_asignadas[robot_objetivo]

            # =====================================================
            # MODO 2 -> TOUR SALA
            # =====================================================

            elif modo == 2:
                sala_id = mission_data.get("sala_id")

                # ════════════════════════════════════════════════════════════
                # MEJORA: Guardamos el estado previo por si estaba en "TODO_MUSEO"
                # ════════════════════════════════════════════════════════════
                guardar_mision_actual(robot_objetivo)

                waypoints = waypoints_para_recorrer_sala(
                    sala_id,
                    robot_objetivo
                )

                mission_id = f"LLM_SALA_{sala_id}"

                ok = enviar_mision(
                    robot_objetivo,
                    mission_id,
                    waypoints
                )
                
                if ok:
                    # Bloquear reanudación hasta que el robot asimile el movimiento
                    MISION_LLM_PENDIENTE[robot_objetivo] = True
                    
                    # ════════════════════════════════════════════════════════════
                    # SOLUCIÓN CLAVE: Forzamos al supervisor a olvidar el tour viejo
                    # ════════════════════════════════════════════════════════════
                    # if robot_objetivo in misiones_asignadas:
                    #     del misiones_asignadas[robot_objetivo]

            # =====================================================
            # BORRAR JSON
            # =====================================================
            os.remove(mission_file)
            print("✅ Misión LLM procesada correctamente.")

        except Exception as e:

            print("❌ ERROR procesando misión LLM")
            print(e)

# =========================================================
# 8. BUCLE PRINCIPAL
# =========================================================

print("[SUPERVISOR_TIAGOS] Supervisor iniciado con misiones manuales.")
limpiar_custom_supervisor()

misiones_asignadas = {}

while robot.step(timestep) != -1:
    procesar_mision_llm()

    # -----------------------------------------------------
    # 8.1 GESTIÓN DE EMERGENCIAS
    # -----------------------------------------------------

    mi_data = get_custom_data(self_node)

    if isinstance(mi_data, dict) and mi_data.get("alerta") == "INTRUSION":
        id_cuadro_alarma = mi_data.get("cuadro_id")

        # Para emergencias también necesitamos waypoints completos con ruta
        # Buscamos la sala del cuadro de alarma para calcular la ruta correcta
        cuadro_alarma = next((c for c in CUADROS if c["id"] == id_cuadro_alarma), None)
        sala_alarma = cuadro_alarma["sala"] if cuadro_alarma else None

        mejor_robot = None
        dist_min = float("inf")
        punto_destino = None

        if cuadro_alarma:
            punto_destino = punto_parada_cuadro(cuadro_alarma)

            for nombre in TIAGOS_DEF:
                pos = tiagos[nombre].getPosition()
                d = distancia_2d([pos[0], pos[1]], punto_destino)

                if d < dist_min:
                    dist_min = d
                    mejor_robot = nombre

        if mejor_robot and sala_alarma:
            m_id_alerta = f"ALERTA_ACTIVA_{id_cuadro_alarma}"

            if "ALERTA" not in str(estado_tiago(mejor_robot).get("mission_id", "")):
                print(f"🚨 [SISTEMA] {mejor_robot} acude al cuadro {id_cuadro_alarma}")

                guardar_mision_actual(mejor_robot)

                sala_actual = obtener_sala_actual_tiago(mejor_robot)

                wps_emergencia = waypoints_para_ir_a_cuadro(
                    id_cuadro_alarma,
                    nombre_tiago=mejor_robot,
                    desde_sala_id=sala_actual
                )

                enviar_mision(mejor_robot, m_id_alerta, wps_emergencia)

        limpiar_custom_supervisor()

# -----------------------------------------------------
# 8.2 ASIGNACIÓN Y REANUDACIÓN
# -----------------------------------------------------

    for nombre in TIAGOS_DEF:
        estado = estado_tiago(nombre)
        status = estado.get("status", "IDLE")
        mission_id_robot = str(estado.get("mission_id", ""))

        # =====================================================
        # MISIÓN LLM EN TRANSICIÓN
        # =====================================================

        if MISION_LLM_PENDIENTE[nombre]:
            robot_en_llm = (
                "LLM_" in mission_id_robot and
                status in ("MOVING", "WAITING", "ARRIVED")
            )

            if robot_en_llm:
                MISION_LLM_PENDIENTE[nombre] = False
                print(f"✅ [LLM] {nombre} ejecutando misión LLM.")

            else:
                continue

        # =====================================================
        # ROBOT TERMINÓ SU MISIÓN
        # =====================================================

        if status == "ARRIVED":

            if nombre not in ROBOTS_FIN_NOTIFICADO:

                print(
                    f"🏁 [FIN] {nombre} terminó su misión "
                    f"y está aparcado en el hub."
                )

                ROBOTS_FIN_NOTIFICADO.add(nombre)

            # NO hacer nada más
            # Evita reasignar automáticamente la misión inicial
            continue

        # =====================================================
        # ROBOT LIBRE
        # =====================================================

        if tiago_libre(nombre):

            # -------------------------------------------------
            # REANUDAR MISIÓN GUARDADA
            # -------------------------------------------------

            if MEMORIA_MISIONES[nombre] is not None:

                recuerdo = MEMORIA_MISIONES[nombre]
                wps_reanudar = recuerdo["waypoints"]

                # =================================================
                # Si el robot está dentro de una sala,
                # prefijar salida correcta
                # =================================================

                sala_actual = obtener_sala_actual_tiago(nombre)

                if sala_actual is not None:

                    salida = obtener_lane_sala(
                        sala_actual,
                        "vuelta"
                    )

                    salida_con_hub = salida + [{
                        "id": "hub_exterior",
                        "punto": HUB_EXTERIOR,
                        "tipo": "hub"
                    }]

                    primer_wp_id = (
                        wps_reanudar[0].get("id", "")
                        if wps_reanudar else ""
                    )

                    ya_tiene_salida = any(
                        s.get("id") == primer_wp_id
                        for s in salida
                    )

                    if not ya_tiene_salida:

                        wps_reanudar = (
                            salida_con_hub +
                            wps_reanudar
                        )

                        print(
                            f"🚪 [REANUDAR] {nombre} "
                            f"prefijando salida de sala "
                            f"{sala_actual}."
                        )

                print(
                    f"✅ [REANUDAR] {nombre} vuelve "
                    f"a su misión anterior: "
                    f"'{recuerdo['mission_id']}' "
                    f"({len(wps_reanudar)} wps)."
                )

                ok = enviar_mision(
                    nombre,
                    recuerdo["mission_id"],
                    wps_reanudar
                )

                if ok:
                    MEMORIA_MISIONES[nombre] = None

            # -------------------------------------------------
            # ASIGNAR MISIÓN INICIAL SOLO UNA VEZ
            # -------------------------------------------------

            elif nombre not in misiones_asignadas:

                mission_id, waypoints = crear_mision_para_tiago(nombre)

                if waypoints:

                    ok = enviar_mision(
                        nombre,
                        mission_id,
                        waypoints
                    )

                    if ok:
                        misiones_asignadas[nombre] = mission_id

                else:

                    misiones_asignadas[nombre] = "SIN_MISION"

                    print(
                        f"⏸️ {nombre} no tiene misión asignada."
                    )