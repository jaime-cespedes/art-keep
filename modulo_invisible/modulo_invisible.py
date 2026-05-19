from controller import Supervisor
import math
import tkinter as tk
from tkinter import messagebox

# =========================================================
# 1. Inicialización
# =========================================================
robot = Supervisor()
timestep = int(robot.getBasicTimeStep())

persona = robot.getFromDef("Persona")
protector = robot.getFromDef("Protector_Obra")
tiago = robot.getFromDef("Tiago")

if persona is None:
    raise RuntimeError("No se encontró DEF Persona")

if protector is None:
    raise RuntimeError("No se encontró DEF Protector_Obra")

if tiago is None:
    print("AVISO: No se encontró DEF Tiago. La alarma solo se mostrará localmente.")
    tiago_custom_data = None
else:
    tiago_custom_data = tiago.getField("customData")

# =========================================================
# 2. Configuración
# =========================================================
UMBRAL_ALARMA = 0.5  # 50 cm
alarma_activada = False

print("=== PROXIMITY SENSOR ACTIVE ===")

# =========================================================
# 3. Ventana visual
# =========================================================
def mostrar_alerta_proximidad(distancia):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    messagebox.showwarning(
        "Proximity Sensor Alert",
        f"Proximity sensor activated!\n\n"
        f"A visitor is too close to the artwork.\n"
        f"Distance detected: {distancia:.2f} m"
    )

    root.destroy()

# =========================================================
# 4. Distancia 2D
# Tu mundo usa X-Y como plano del suelo y Z como altura
# =========================================================
def distancia_2d(p1, p2):
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return math.sqrt(dx * dx + dy * dy)

# =========================================================
# 5. Bucle principal
# =========================================================
while robot.step(timestep) != -1:
    pos_persona = persona.getPosition()
    pos_protector = protector.getPosition()

    distancia = distancia_2d(pos_persona, pos_protector)

    if distancia <= UMBRAL_ALARMA:
        if not alarma_activada:
            alarma_activada = True

            print("!!! PROXIMITY SENSOR ACTIVATED !!!")
            print(f"Detected distance: {distancia:.2f} m")

            # Avisar a TIAGo
            if tiago_custom_data is not None:
                tiago_custom_data.setSFString("ALARMA_PERSONA")
                print("Alert sent to TIAGo.")

            mostrar_alerta_proximidad(distancia)

    else:
        alarma_activada = False