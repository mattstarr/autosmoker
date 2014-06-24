#imports
import os, sys
from yoctopuce.yocto_api import *
from yoctopuce.yocto_temperature import *
import RPIO
from RPIO import PWM

#90 deg L = 600 usec
#45 deg L = 1050 usec
#0 deg = 1500 usec
#45 deg R = 1950 usec
#90 deg R = 2400 usec 

#from 0 to 180
#usec = 600 + (10 * deg)

#RPIO.cleanup() # can be used after script to shut off GPIO 

#attach yocto device
errmsg = YRefParam()
YAPI.RegisterHub("usb",errmsg)

#attach servo
SERVO_PIN = 18
SERVO_MIN_USEC = 600
SERVO_MAX_USEC = 2400
servo = PWM.Servo()

#input/output (for now)
LED1_PIN = 17
LED2_PIN = 22
LED3_PIN = 27
SW1_PIN = 23
SW2_PIN = 24
SW3_PIN = 25

#setup I/O
RPIO.setup(LED1_PIN, RPIO.OUT)
RPIO.setup(LED2_PIN, RPIO.OUT)
RPIO.setup(LED3_PIN, RPIO.OUT)
RPIO.output(LED1_PIN, True)
RPIO.output(LED2_PIN, True)
RPIO.output(LED3_PIN, True)
RPIO.setup(SW1_PIN, RPIO.IN)
RPIO.setup(SW2_PIN, RPIO.IN)
RPIO.setup(SW3_PIN, RPIO.IN)

def tempCtoF(tempC):  #degrees Celsius to degrees Fahrenheit
	tempF = tempC * 9 / 5 + 32
	return tempF
	
class autoSmoker:
	def __init__(self):
		#sensor data
		##################################
		#reference our sensor objects
		self.meatSensor = YTemperature.FindTemperature("smokerModule.meatTemp")
		self.smokerSensor = YTemperature.FindTemperature("smokerModule.smokerTemp")
		#servo data
		##################################
		self.servoAngle = 90 #initial position is half open. 
		self.servoUsec =  SERVO_MIN_USEC + (self.servoAngle * 10)
		self.manualServoMode = False
		self.led1on = False #manual mode
		self.led2on = False #servo completely down
		self.led3on = False #servo completely up
		
	#sensor functions
	##################################
	def sensorTempF(sensor):
		if (sensor.isOnline()):
			return cToF(sensor.get_currentValue())
			
	def printTempF():
		if (self.meatSensor.isOnline()):
			print "Meat Temp   (F): ", sensorTempF(self.meatSensor)
		if (self.smokerSensor.isOnline()):
			print "Smoker Temp (F): ", sensorTempF(self.smokerSensor)
						
	#servo functions
	##################################
	def usecFromDeg(self, deg):
	   newUsec = SERVO_MIN_USEC + (10 * deg)
	   return newUsec;
	
	def setServoAngle(self, deg):
		if (deg < 0):
			self.servoAngle = 0
			self.servoUsec = self.usecFromDeg(0)
			servo.set_servo(SERVO_PIN, self.servoUsec)
		elif (deg > 180):
			self.servoAngle = 180
			self.servoUsec = self.usecFromDeg(180)
			servo.set_servo(SERVO_PIN, self.servoUsec)
		else:
			self.servoAngle = deg
			self.servoUsec = self.usecFromDeg(deg)
			servo.set_servo(SERVO_PIN, self.servoUsec)		
		#light appropriate LED if at limit
		if (self.servoAngle == 0):
			self.led2on = True
			RPIO.output(LED2_PIN, False)
		elif (self.servoAngle == 180):
			self.led3on = True
			RPIO.output(LED3_PIN, False)
		else:
			self.led2on = False
			RPIO.output(LED2_PIN, True)
			self.led3on = False
			RPIO.output(LED3_PIN, True)
			
	def incrementServoAngle(self, deg):
		self.setServoAngle(self.servoAngle + deg)
		
	def decrementServoAngle(self, deg):
		self.setServoAngle(self.servoAngle - deg)
		
	def setManualMode(self, newModeSetting):
		self.manualServoMode = newModeSetting
		if (self.manualServoMode == False):
			self.led1on = False
			RPIO.output(LED1_PIN, True)
		else:
			self.led1on = True
			RPIO.output(LED1_PIN, False)
		
	def toggleManualMode(self): #to be called by button callback function
		if (self.manualServoMode == False):
			self.setManualMode(True)
		else:
			self.setManualMode(False)
	
mySmoker = autoSmoker()
mySmoker.setServoAngle(90) #make sure it is set half open

def gpio_callback(gpio_id, val):
	if (gpio_id == SW2_PIN): #toggle manual mode
		if (val == False): #switch was pulled low (SOMEONE HIT IT!)
			mySmoker.toggleManualMode()
	elif (gpio_id == SW1_PIN):	#if manual mode, angle down
		if (mySmoker.manualServoMode == True):
			mySmoker.decrementServoAngle(10)
	elif (gpio_id == SW3_PIN):	#if manual mode, angle up
		if (mySmoker.manualServoMode == True):
			mySmoker.incrementServoAngle(10)
		
RPIO.add_interrupt_callback(SW1_PIN, gpio_callback)
RPIO.add_interrupt_callback(SW2_PIN, gpio_callback)
RPIO.add_interrupt_callback(SW3_PIN, gpio_callback)			
			
#start interrupt thread			
RPIO.wait_for_interrupts(threaded=True)
