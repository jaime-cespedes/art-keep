from controller import Supervisor
import tkinter as tk
import threading
import time

# =========================================================
# 0. Selección de modo
# =========================================================
# MODO 1 = ejecutar simulación ambiental completa
# MODO 2 = no hacer nada
MODO = 2

supervisor = Supervisor()
timestep = int(supervisor.getBasicTimeStep())

# =========================================================
# 1. Modo 2: no hacer nada
# =========================================================
if MODO == 2:
    print("Modo 2 activado: sistema ambiental desactivado.")

    while supervisor.step(timestep) != -1:
        pass

# =========================================================
# 2. Modo 1: ejecutar sistema completo
# =========================================================
else:

    # --- Create window BEFORE the loop ---
    def crear_ventana():
        global etiqueta_temp, etiqueta_hum, etiqueta_ac, etiqueta_anti, ventana

        ventana = tk.Tk()
        ventana.title("Environmental Panel")
        ventana.geometry("300x260+50+50")
        ventana.configure(bg="#222222")

        titulo = tk.Label(
            ventana,
            text="Environmental Sensor",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#222222"
        )
        titulo.pack(pady=5)

        etiqueta_temp = tk.Label(
            ventana,
            text="Temp: -- °C",
            font=("Arial", 18, "bold"),
            fg="#00ff00",
            bg="#222222"
        )
        etiqueta_temp.pack(pady=5)

        etiqueta_hum = tk.Label(
            ventana,
            text="Humidity: -- %",
            font=("Arial", 18, "bold"),
            fg="#00aaff",
            bg="#222222"
        )
        etiqueta_hum.pack(pady=5)

        etiqueta_ac = tk.Label(
            ventana,
            text="A/C: OFF",
            font=("Arial", 16, "bold"),
            fg="#00aaff",
            bg="#222222"
        )
        etiqueta_ac.pack(pady=5)

        etiqueta_anti = tk.Label(
            ventana,
            text="Dehumidifier: OFF",
            font=("Arial", 16, "bold"),
            fg="#00aaff",
            bg="#222222"
        )
        etiqueta_anti.pack(pady=5)

        ventana.mainloop()

    # Launch window thread
    ventana_thread = threading.Thread(target=crear_ventana)
    ventana_thread.daemon = True
    ventana_thread.start()

    # --- Variables ---
    tiempo = 0

    temperatura = 25
    humedad = 45

    fase = 1  # 1=temp high, 2=wait, 3=humidity high, 4=normal

    ac_encendido = False
    anti_encendido = False

    time.sleep(0.5)

    print("Modo 1 activado: Environmental sequence active.")

    while supervisor.step(timestep) != -1:
        tiempo += timestep / 1000.0

        # --- PHASE 1: Temperature spike ---
        if fase == 1:
            if tiempo < 6:
                temperatura = 25
            elif 6 <= tiempo < 10:
                temperatura = 35
            else:
                temperatura = 25
                fase = 2
                fase2_inicio = tiempo

                print("Temperature normalized. A/C will turn OFF.")

                ac_encendido = False
                etiqueta_ac.config(
                    text="A/C: OFF",
                    fg="#00aaff"
                )

        # --- PHASE 2: Wait ---
        elif fase == 2:
            temperatura = 25

            if tiempo - fase2_inicio >= 3:
                fase = 3
                fase3_inicio = tiempo
                print("Starting humidity spike...")

        # --- PHASE 3: Humidity spike ---
        elif fase == 3:
            if tiempo - fase3_inicio < 4:
                humedad = 85
            else:
                humedad = 45
                fase = 4

                print("Humidity normalized. Dehumidifier will turn OFF.")

                anti_encendido = False
                etiqueta_anti.config(
                    text="Dehumidifier: OFF",
                    fg="#00aaff"
                )

        # --- PHASE 4: Everything normal ---
        elif fase == 4:
            temperatura = 25
            humedad = 45

        # --- Update window ---
        try:
            etiqueta_temp.config(
                text=f"Temp: {temperatura:.1f} °C"
            )

            etiqueta_hum.config(
                text=f"Humidity: {humedad:.1f} %"
            )
        except:
            pass

        # --- Activate A/C ---
        if temperatura >= 34 and not ac_encendido:
            ac_encendido = True

            etiqueta_ac.config(
                text="A/C: ON",
                fg="#00ff00"
            )

            etiqueta_temp.config(
                fg="red"
            )

            print("⚠️ A/C ACTIVATED due to high temperature.")

        # --- Activate Dehumidifier ---
        if humedad >= 80 and not anti_encendido:
            anti_encendido = True

            etiqueta_anti.config(
                text="Dehumidifier: ON",
                fg="#00ff00"
            )

            etiqueta_hum.config(
                fg="red"
            )

            print("⚠️ Dehumidifier ACTIVATED due to high humidity.")

        # --- Reset colors ---
        if temperatura < 30:
            etiqueta_temp.config(fg="#00ff00")

        if humedad < 70:
            etiqueta_hum.config(fg="#00aaff")