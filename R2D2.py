"""R2D2_2 controller."""

# You may need to import some classes of the controller module. Ex:
#  from controller import Robot, Motor, DistanceSensor
from controller import Robot

def main():
    # create the Robot instance.
    robot = Robot()
    
    # get the time step of the current world.
    # timestep = int(robot.getBasicTimeStep())
    timestep = 64
    max_speed = 6.28
    
    #Creacion de instancias de motores, asociadas a los objetos motor 1 y 2
    left_motor = robot.getDevice('motor1')
    left_motor.setPosition(float('inf'))
    left_motor.setVelocity(0.0)
    
    right_motor = robot.getDevice('motor2')
    right_motor.setPosition(float('inf'))
    right_motor.setVelocity(0.0)

    cambio = False
    # Main loop:
    # - perform simulation steps until Webots is stopping the controller
    while robot.step(timestep) != -1:
        if cambio:
            left_speed = 0.5*max_speed
            right_speed = max_speed
            cambio = False
        else:
            left_speed = max_speed
            right_speed = 0.5*max_speed
            cambio = True

        left_motor.setVelocity(left_speed)
        right_motor.setVelocity(right_speed)

# Enter here exit cleanup code.

if __name__ == "__main__":
    main()