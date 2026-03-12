from controller import Robot

def main():
    robot = Robot()
    timestep = int(robot.getBasicTimeStep())
    max_speed = 6.28
    
    # Configuración de motores
    left_motor = robot.getDevice('motor1')
    right_motor = robot.getDevice('motor2')
    left_motor.setPosition(float('inf'))
    right_motor.setPosition(float('inf'))
    
    # --- BASE DE DATOS DEL MUSEO ---
    # Aquí definimos las obras en el orden de la exposición
    museo_db = [
        {"id": "001", "nombre": "La Gioconda", "info": "Esta obra de Da Vinci es famosa por su sonrisa enigmática."},
        {"id": "002", "nombre": "El Grito", "info": "Munch expresó la ansiedad humana en esta pintura expresionista."},
        {"id": "003", "nombre": "La Noche Estrellada", "info": "Van Gogh pintó esto desde su ventana en el asilo de Saint-Rémy."}
    ]
    
    # Variables de control
    indice_obra = 0
    estado = "NAVEGANDO"  # NAVEGANDO, EXPLICANDO, GIRANDO
    last_time = robot.getTime()
    mensaje_dado = False

    print("--- R2D2 Guía de Museo: Sistema Online ---")

    while robot.step(timestep) != -1:
        current_time = robot.getTime()
        dt = current_time - last_time

        # ESTADO 1: El robot se desplaza hacia la siguiente obra
        if estado == "NAVEGANDO":
            if not mensaje_dado:
                print(f"🤖 R2D2: Dirigiéndome a la Obra ID: {museo_db[indice_obra]['id']}...")
                mensaje_dado = True
            
            left_motor.setVelocity(0.6 * max_speed)
            right_motor.setVelocity(0.6 * max_speed)
            
            # Simulamos que llega a la obra tras 4 segundos de marcha
            if dt > 4.0:
                estado = "EXPLICANDO"
                last_time = current_time
                mensaje_dado = False

        # ESTADO 2: El robot se detiene y "lee" la base de datos
        elif estado == "EXPLICANDO":
            left_motor.setVelocity(0)
            right_motor.setVelocity(0)
            
            if not mensaje_dado:
                obra = museo_db[indice_obra]
                print(f"\n🔍 [IDENTIFICADOR LEÍDO: {obra['id']}]")
                print(f"🎨 Obra: {obra['nombre']}")
                print(f"🎙️ Explicación: {obra['info']}")
                mensaje_dado = True
            
            # Tiempo que tarda en "explicar" (ej. 5 segundos)
            if dt > 5.0:
                # Si hay más obras, giramos para buscar la siguiente
                if indice_obra < len(museo_db) - 1:
                    estado = "GIRANDO"
                    indice_obra += 1
                else:
                    print("\n🏁 R2D2: Exposición finalizada. Regresando a base.")
                    break # Fin del tour
                
                last_time = current_time
                mensaje_dado = False

        # ESTADO 3: Giro para encarar la siguiente pared/obra
        elif estado == "GIRANDO":
            left_motor.setVelocity(0.4 * max_speed)
            right_motor.setVelocity(-0.4 * max_speed)
            
            if dt > 1.2: # Ajusta para un giro de 90º o lo que necesite tu museo
                estado = "NAVEGANDO"
                last_time = current_time
                mensaje_dado = False

if __name__ == "__main__":
    main()