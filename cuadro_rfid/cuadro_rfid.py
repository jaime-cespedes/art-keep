from controller import Robot
import math

robot = Robot()
timestep = int(robot.getBasicTimeStep())

emitter = robot.getDevice("rfid_cuadro_1")

# Información inicial
print("=== CUADRO RFID ===")
print("Emitter encontrado:", emitter is not None)
print("Canal del emitter:", emitter.getChannel())
print("Rango del emitter:", emitter.getRange())
print("====================")

contador = 0

while robot.step(timestep) != -1:
    mensaje = "CUADRO_5"
    emitter.send(mensaje.encode('utf-8'))
    contador += 1

    if contador % 20 == 0:
        print(f"[Cuadro] Enviando mensaje #{contador}: {mensaje}")
