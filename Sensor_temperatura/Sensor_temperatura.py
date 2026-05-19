from controller import Supervisor
import tkinter as tk
import threading
import random
import time

# =========================================================
# 0. Selección de modo
# =========================================================
# MODO 1 = ejecutar termostato ambiental completo
# MODO 2 = no hacer nada
MODO = 2

supervisor = Supervisor()
timestep = int(supervisor.getBasicTimeStep())

# =========================================================
# 1. Modo 2: no hacer nada
# =========================================================
if MODO == 2:
    print("Modo 2 activado: el sistema HVAC no hará nada.")

    while supervisor.step(timestep) != -1:
        pass

# =========================================================
# 2. Modo 1: ejecutar sistema completo
# =========================================================
else:
    # --- Crear ventana ANTES del bucle ---
    def crear_ventana():
        global etiqueta_temp, etiqueta_ac, ventana

        ventana = tk.Tk()
        ventana.title("Termostato Ambiental")
        ventana.geometry("260x170+50+50")
        ventana.configure(bg="#222222")

        titulo = tk.Label(
            ventana,
            text="Temperatura",
            font=("Arial", 14, "bold"),
            fg="white",
            bg="#222222"
        )
        titulo.pack(pady=5)

        etiqueta_temp = tk.Label(
            ventana,
            text="-- °C",
            font=("Arial", 28, "bold"),
            fg="#00ff00",
            bg="#222222"
        )
        etiqueta_temp.pack()

        etiqueta_ac = tk.Label(
            ventana,
            text="A/C: OFF",
            font=("Arial", 14, "bold"),
            fg="#00aaff",
            bg="#222222"
        )
        etiqueta_ac.pack(pady=10)

        ventana.mainloop()

    # Lanzar ventana en un hilo separado ANTES del step()
    ventana_thread = threading.Thread(target=crear_ventana)
    ventana_thread.daemon = True
    ventana_thread.start()

    # --- Variables del sistema ---
    tiempo = 0
    temperatura_base = 25
    variacion_ambiente = random.uniform(-1.5, 1.5)
    alerta_activada = False
    ac_encendido = False

    print("Modo 1 activado: Supervisor iniciado. Ventana del termostato creada.")

    # Esperar un poco para que Tkinter arranque
    time.sleep(0.5)

    while supervisor.step(timestep) != -1:
        tiempo += timestep / 1000.0

        # --- Simulación de temperatura ---
        if tiempo < 6:
            temperatura = temperatura_base + variacion_ambiente
        elif 6 <= tiempo < 10:
            temperatura = 35 + variacion_ambiente
        else:
            temperatura = temperatura_base + variacion_ambiente

        # --- Actualizar ventana ---
        try:
            etiqueta_temp.config(text=f"{temperatura:.1f} °C")
        except:
            pass

        # --- Activar alerta y aire acondicionado ---
        if temperatura >= 34 and not alerta_activada:
            alerta_activada = True
            ac_encendido = True

            etiqueta_temp.config(fg="red")
            etiqueta_ac.config(text="A/C: ON", fg="#00ff00")

            print("⚠️ ALERTA: Temperatura extrema detectada.")
            print("❄️ Aire acondicionado ACTIVADO.")

        # --- Desactivar alerta y aire acondicionado ---
        if temperatura < 30 and alerta_activada and tiempo > 10:
            alerta_activada = False
            ac_encendido = False

            etiqueta_temp.config(fg="#00ff00")
            etiqueta_ac.config(text="A/C: OFF", fg="#00aaff")

            print("Temperatura normalizada.")
            print("❄️ Aire acondicionado DESACTIVADO.")