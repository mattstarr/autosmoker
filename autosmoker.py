#!/usr/bin/python

###############################################################################
#autosmoker.py - drive smoker door with servo based on manual or temperature 
#				 input, log temps and position to file
#6/23/14 - MTS - initial script to handle manual button input and LED output
#6/25/14 - MTS - added MCP3008 / potentiometer functionality
#6/26/14 - MTS - added .xls file output
#6/27/14 - MTS - added .csv file output, autoincrementing filenames
#7/4/14  - MTS - added some web UI interoperability, start thread
#
# TODO: Currently lots of extra functions. Trim fat when code completed.
# TODO: Consolidate/rearrange consts, vars, functions
###############################################################################

#imports
import spidev #for SPI
import os, sys, time
from yoctopuce.yocto_api import *
from yoctopuce.yocto_temperature import *
import RPIO
from RPIO import PWM
from datetime import datetime #for current time
import csv #for csv output
import thread

#attach yocto device
errmsg = YRefParam()
YAPI.RegisterHub("usb",errmsg)

#attach servo
SERVO_PIN = 18
SERVO_MIN_USEC = 600
SERVO_MAX_USEC = 2400
servo = PWM.Servo()

#input/output (for now)
M_LED_PIN = 17 # UNUSED (for now)
R_LED_PIN = 22 # recording
L_LED_PIN = 27 # manual mode
M_SW_PIN = 23  # start record
L_SW_PIN = 24  # toggle manual mode
R_SW_PIN = 25  # stop record

#Input channels for MCP3008
POT_CHANNEL 		 = 0 # potentiometer input
AMBIENT_TEMP_CHANNEL = 1 # for later use

#setup I/O
RPIO.setup(L_LED_PIN, RPIO.OUT)
RPIO.setup(R_LED_PIN, RPIO.OUT)
RPIO.setup(M_LED_PIN, RPIO.OUT)
RPIO.output(L_LED_PIN, True)
RPIO.output(R_LED_PIN, True)
RPIO.output(M_LED_PIN, True)
RPIO.setup(R_SW_PIN, RPIO.IN)
RPIO.setup(L_SW_PIN, RPIO.IN)
RPIO.setup(M_SW_PIN, RPIO.IN)

blinkDelay = .25
#show user that bootup is complete, script has started:
for i in xrange(1,10):
	RPIO.output(L_LED_PIN, False)
	time.sleep(blinkDelay)
	RPIO.output(L_LED_PIN, True)
	RPIO.output(M_LED_PIN, False)
	time.sleep(blinkDelay)
	RPIO.output(M_LED_PIN, True)
	RPIO.output(R_LED_PIN, False)
	time.sleep(blinkDelay)
	RPIO.output(R_LED_PIN, True)

#leave right LED on:
RPIO.output(R_LED_PIN, False)

ManualOffSwState = RPIO.input(R_SW_PIN) #set "off" to whatever the toggle switch is at when we start the script

recording = False #used by GPIO callback
#recording = True ##########auto start record for debug!!!!!!!!!!!!!!!
###########################################################
#Borrowed from Matt Hawkins script at: http://www.raspberrypi-spy.co.uk/2013/10/analogue-sensors-on-the-raspberry-pi-using-an-mcp3008/
# (Creative Commons Attribution-NonCommercial 3.0 License)
# Open SPI bus
spi = spidev.SpiDev()
spi.open(0,0)
 
# Function to read SPI data from MCP3008 chip
# Channel must be an integer 0-7
def ReadChannel(channel):
  adc = spi.xfer2([1,(8+channel)<<4,0])
  data = ((adc[1]&3) << 8) + adc[2]
  return data
 
# Function to convert data to voltage level,
# rounded to specified number of decimal places.
def ConvertVolts(data,places):
  volts = (data * 3.3) / float(1023)
  volts = round(volts,places)
  return volts
#End of borrowed code
###########################################################

def tempCtoF(tempC):  #degrees Celsius to degrees Fahrenheit
	tempF = tempC * 9 / 5 + 32
	return tempF


def gpio_callback(gpio_id, val):
	if (gpio_id == R_SW_PIN): #toggle manual mode
		if (val == False): #switch was pulled low (SOMEONE HIT IT!)
			mySmoker.toggleManualMode()
	elif (gpio_id == L_SW_PIN):	
		if (val == False): #switch was pulled low (SOMEONE HIT IT!)
			global recording
			smokeData.setRecording(True)
			
	elif (gpio_id == M_SW_PIN):	
		if (val == False): #switch was pulled low (SOMEONE HIT IT!)
			global recording
			smokeData.setRecording(False)
			

#output csv: (http://java.dzone.com/articles/python-101-reading-and-writing)
def outputCSV(ofilename, outputLine, mode):
	with open(ofilename, mode) as csv_file:
		writer = csv.writer(csv_file, delimiter=',')
		writer.writerow(outputLine)
	
class autoSmoker:
	def __init__(self):
		#sensor data
		##################################
		#reference our sensor objects
		self.meatSensor = YTemperature.FindTemperature("smokerModule.meatTemp")
		self.smokerSensor = YTemperature.FindTemperature("smokerModule.smokerTemp")
		#servo data
		##################################
		self.servoAngle = 0 #initial position is closed. 
		self.servoUsec =  SERVO_MIN_USEC + (self.servoAngle * 10)
		self.manualServoMode = False
		self.led1on = False #manual mode
		
	#sensor functions
	##################################
	def sensorTempF(self, sensor):
		if (sensor.isOnline()):
			return tempCtoF(sensor.get_currentValue())

	def meatTempF(self):
		return self.sensorTempF(self.meatSensor)
		
	def smokerTempF(self):
		return self.sensorTempF(self.smokerSensor)
						
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
					
	def setServoPercent(self, percent): #accepts percent (from 0 - 100)
			if (percent < 0 ):
				percent = 0
				print "input percent < 0. Setting to 0." 
			if (percent > 100):
				percent = 100
				print "input percent > 100. Setting to 100."
			newServoAngle = int((percent * 0.01) * 180)	
			self.setServoAngle(newServoAngle)	
	
	def setServoFromPot(self, potVoltage): #accepts voltage from potentiometer (0.0 - 3.3v)
		#0.0v = 0%
		#3.3v = 100%
		potPercent = potVoltage * (100/3.3) #invert if pot wanted in opposite orientation 
		self.setServoPercent(potPercent)
			
	def incrementServoAngle(self, deg):
		self.setServoAngle(self.servoAngle + deg)
		
	def decrementServoAngle(self, deg):
		self.setServoAngle(self.servoAngle - deg)

	def setManualMode(self, newModeSetting):
		self.manualServoMode = newModeSetting
		if (self.manualServoMode == False):
			self.led1on = False
			RPIO.output(L_LED_PIN, True)
		else:
			self.led1on = True
			RPIO.output(L_LED_PIN, False)
		
	def toggleManualMode(self): #to be called by button callback function
		if (self.manualServoMode == False):
			self.setManualMode(True)
		else:
			self.setManualMode(False)

mySmoker = autoSmoker()
mySmoker.setServoAngle(0) #make sure it is set closed
				
#RPIO.add_interrupt_callback(R_SW_PIN, gpio_callback)
RPIO.add_interrupt_callback(L_SW_PIN, gpio_callback)
RPIO.add_interrupt_callback(M_SW_PIN, gpio_callback)			
			
#start interrupt thread			
RPIO.wait_for_interrupts(threaded=True)

class SmokeData:
	recording = False
	filename = "default.csv"
	targetMeatTemp = 145
	targetSmokerTemp = 225
	
	
	def setRecording(self, newState):
		self.recording = newState
	
	def setFilename(self, newName):
		self.filename = newName

smokeData = SmokeData()
			
#while (elapsedTime < desiredCookTime ): #use later for a cook? 
def startIO(a, b):
	DELAY = 0.1 #keep servo response quick by not waiting too long. This delay will also be important
			#for knowing when to record values (for later plotting)

	WRITE_INTERVAL = 5 #output to file approximately every 5 seconds
	startCookTime = time.time()
	timerStart = time.time()
	n = 0
	elapsedTime = 0
	desiredCookTime = 120  #TODO: get from user input 
	startNewCSV = True
	while (True):
		#added for using toggle switch
		if (RPIO.input(R_SW_PIN) != ManualOffSwState):
			mySmoker.setManualMode(True)
		else:
			mySmoker.setManualMode(False)
		if (mySmoker.manualServoMode == True):
			potLevel = ReadChannel(POT_CHANNEL)
			potVolts = ConvertVolts(potLevel,2)
			mySmoker.setServoFromPot(potVolts)
		
		elapsedTime = time.time() - startCookTime # elapsed cook time
		if (smokeData.recording == True):
			RPIO.output(M_LED_PIN, False)
			if ((time.time() - timerStart) >= WRITE_INTERVAL): #start timer over, record to file 
				timerStart = time.time() 
				n += 1
				if (startNewCSV == True):
					mode = 'wb' 		# write new file (binary)
					startNewCSV = False # append for rest of run 
				else:
					mode = 'ab' # append (binary)
				currentLine = [n, str(datetime.now()), round(elapsedTime, 2), mySmoker.smokerTempF(), mySmoker.meatTempF(), mySmoker.servoAngle]
				outputCSV(smokeData.filename, currentLine, mode)
		else:
			startCookTime = time.time()	
			RPIO.output(M_LED_PIN, True)
		time.sleep(DELAY)
thread.start_new_thread(startIO, ("Thread-1", 0, ))