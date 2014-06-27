#!/usr/bin/python

###############################################################################
#autosmoker.py - drive smoker door with servo based on manual or temperature 
#				 input, log temps and position to file
#6/23/14 - MTS - initial script to handle manual button input and LED output
#6/25/14 - MTS - added MCP3008 / potentiometer functionality
#6/26/14 - MTS - added .xls file output
#6/27/14 - MTS - added .csv file output, autoincrementing filenames
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
import xlwt #for excel output
from datetime import datetime #for current time

##### Servo position / pulse width
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

#Input channels for MCP3008
POT_CHANNEL = 0

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
	if (gpio_id == SW2_PIN): #toggle manual mode
		if (val == False): #switch was pulled low (SOMEONE HIT IT!)
			mySmoker.toggleManualMode()
	elif (gpio_id == SW1_PIN):	#if manual mode, angle down
		if (val == False): #switch was pulled low (SOMEONE HIT IT!)
			global recording
			recording = True
			RPIO.output(LED2_PIN, False)
			
	elif (gpio_id == SW3_PIN):	#if manual mode, angle up
		if (val == False): #switch was pulled low (SOMEONE HIT IT!)
			global recording
			recording = False
			RPIO.output(LED2_PIN, True)

def outputXLS(book, sheet, n, dateTime, elapsedTime, smokerTemp, meatTemp, servoAngle):
	sheet.write(n,DATE_TIME_COLUMN, dateTime)
	sheet.write(n,ELAPSED_TIME_COLUMN, elapsedTime)
	sheet.write(n,SMOKER_TEMP_COLUMN, smokerTemp)
	sheet.write(n,MEAT_TEMP_COLUMN, meatTemp)
	sheet.write(n,SERVO_ANGLE_COLUMN, servoAngle)
	book.save('test.xls')
			
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
				
RPIO.add_interrupt_callback(SW1_PIN, gpio_callback)
RPIO.add_interrupt_callback(SW2_PIN, gpio_callback)
RPIO.add_interrupt_callback(SW3_PIN, gpio_callback)			
			
#start interrupt thread			
RPIO.wait_for_interrupts(threaded=True)

recording = False #used by GPIO callback

###########################################################
# excel output code learned from:
# http://stackoverflow.com/questions/13437727/python-write-to-excel-spreadsheet
###########################################################
DATE_TIME_COLUMN    = 0
ELAPSED_TIME_COLUMN = 1
SMOKER_TEMP_COLUMN  = 2
MEAT_TEMP_COLUMN    = 3
SERVO_ANGLE_COLUMN  = 4

xls_book = xlwt.Workbook(encoding="utf-8")
xls_sheet = xls_book.add_sheet("Sheet 1")
xls_sheet.write(0,DATE_TIME_COLUMN, "Date/Time")
xls_sheet.write(0,ELAPSED_TIME_COLUMN, "Elapsed Time")
xls_sheet.write(0,SMOKER_TEMP_COLUMN, "Smoker Temperature")
xls_sheet.write(0,MEAT_TEMP_COLUMN, "Meat Temperature")
xls_sheet.write(0,SERVO_ANGLE_COLUMN, "Servo Angle")

DELAY = 0.1 #keep servo response quick by not waiting too long. This delay will also be important
			#for knowing when to record values (for later plotting)

WRITE_INTERVAL = 5 #output to file approximately every 5 seconds
startCookTime = time.time()
timerStart = time.time()
n = 0
			
while (True):
	if (mySmoker.manualServoMode == True):
		potLevel = ReadChannel(POT_CHANNEL)
		potVolts = ConvertVolts(potLevel,2)
		mySmoker.setServoFromPot(potVolts)
	
	if (recording == True):
		if ((time.time() - timerStart) >= WRITE_INTERVAL): #start timer over, record to file 
			timerStart = time.time() 
			n += 1
			elapsedTime = time.time() - startCookTime # elapsed cook time
			outputXLS(xls_book, xls_sheet, n, str(datetime.now()), round(elapsedTime, 2), mySmoker.smokerTempF(), mySmoker.meatTempF(), mySmoker.servoAngle)
	time.sleep(DELAY)
