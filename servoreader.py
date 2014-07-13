import RPIO
from RPIO import PWM
import time

SERVO_PIN = 18
SERVO_MIN_USEC = 600
SERVO_MAX_USEC = 2400
servo = PWM.Servo()

servofilename = "servo.txt"

def usecFromDeg(deg):
	   newUsec = SERVO_MIN_USEC + (10 * deg)
	   return newUsec;
	   
def readToServo(): 
	with open(servofilename, 'r') as servofile:
		linein = servofile.read()
		if len(linein) > 0:
			newPosition = int(linein)
			return newPosition
		else:
			print "error, using old value!"
			return degree
DELAY = 0.3
degree = 0	   
olddegree = 0
	   
while True:
	degree = readToServo()
	if (abs(degree - olddegree) > 4) or ((abs(degree - olddegree) > 1) and ((degree == 0) or (degree == 180))):
		olddegree = degree
		servoUsec = usecFromDeg(degree)
		servo.set_servo(SERVO_PIN, servoUsec)
		time.sleep(DELAY)
		servo.stop_servo(SERVO_PIN)
	time.sleep(DELAY)