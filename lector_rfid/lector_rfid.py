from controller import Supervisor
import json
import math
import tkinter as tk
from tkinter import messagebox

# --- FUNCIONES AUXILIARES ---
def lanzar_ventana_alerta(distancia):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showwarning("⚠️ SEGURIDAD MUSEO", f"¡ALERTA! Cuadro 5 movido.\nDesplazamiento: {distancia:.4f} m")
    root.destroy()

def distance_2d(a, b):
    return math.dist(a, b)

# --- INICIALIZACIÓN ---
supervisor = Supervisor()
timestep = int(supervisor.getBasicTimeStep())

# 1. DEFINIR LA VARIABLE (Aquí evitamos el NameError)
# Buscamos el nodo del Supervisor por su nombre DEF en Webots
supervisor_robots = supervisor.getFromDef("Supervisor_Tiagos")

# 2. DEFINIR EL NODO DEL CUADRO
cuadro = supervisor.getFromDef("Cuadro_Con_RFID")
cuadro_pos_field = cuadro.getField("translation")

# --- CARGAR DATOS DEL JSON ---
try:
    with open("museo.json", "r") as f:
        db = json.load(f)
    cuadro_info = next(c for c in db["cuadros"] if c["id"] == 5)
    expected_pos = [cuadro_info["x"], cuadro_info["y"]]
except Exception as e:
    print(f"Error al cargar JSON: {e}")
    expected_pos = [0, 0]

alerta_activa = False

print("=== LECTOR RFID: VIGILANCIA ACTIVA ===")

# --- BUCLE PRINCIPAL ---
while supervisor.step(timestep) != -1:
    real_pos_3d = cuadro_pos_field.getSFVec3f()
    real_pos_2d = [real_pos_3d[0], real_pos_3d[1]]

    dist = distance_2d(real_pos_2d, expected_pos)

    # Si se mueve más de 5cm
    if dist > 0.05:
        if not alerta_activa:
            print(f"!!! MOVIMIENTO DETECTADO: {dist:.4f} m !!!")
            
            # AHORA SÍ: supervisor_robots ya está definido arriba
            if supervisor_robots is not None:
                datos_alerta = {
                    "alerta": "INTRUSION",
                    "cuadro_id": 5
                }
                # Enviamos la alerta al "buzón" del Supervisor Central
                supervisor_robots.getField("customData").setSFString(json.dumps(datos_alerta))
                print("[RFID] Alerta enviada al Supervisor Central.")
            else:
                print("[ERROR] No se pudo enviar la alerta: DEF 'Supervisor_Tiagos' no encontrado.")
            
            # Lanzamos la ventana de aviso
            lanzar_ventana_alerta(dist)
            alerta_activa = True 
    else:
        if alerta_activa:
            print("Cuadro devuelto a su sitio.")
            alerta_activa = False