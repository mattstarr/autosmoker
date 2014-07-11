#!/usr/bin/python

###############################################################################
#autosmoker.py - drive smoker door with servo based on manual or temperature 
#				 input, log temps and position to file
#6/23/14 - MTS - initial script to handle manual button input and LED output
#6/25/14 - MTS - added MCP3008 / potentiometer functionality
#6/26/14 - MTS - added .xls file output
#6/27/14 - MTS - added .csv file output, autoincrementing filenames
#7/4/14  - MTS - added some web UI interoperability, start thread
#7/9/14  - MTS - heavy use of try/except to attempt to isolate several bugs that 
#				 did not present themselves until live test.
#7/10/14 - MTS - eliminated large bug(s) by isolated motor control in own script 
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
#from RPIO import PWM
#import RPi.GPIO as RPIO
import wiringpi

from datetime import datetime #for current time
import csv #for csv output
import threading
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText

def getDTS():
	return time.strftime("%d/%m/%y %H:%M:%S")
	
startdts = time.strftime("%d%m%y%H%M") #date/time string (minus second)
logfilename = "debuglog" + startdts + ".log"

servofilename = "servo.txt"

def writeToLog(outputLine): #and print for debug if running from command line!
	with open(logfilename, 'a') as logfile:
		logfile.write(getDTS() + ": " + outputLine + '\n')
		print outputLine

def writeToServo(position): 
	with open(servofilename, 'w') as servofile:
		servofile.write(str(position))

writeToServo(0)		
		
try:   
	#attach yocto device
	writeToLog("Connecting yocto...")
	errmsg = YRefParam()
	if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS: #from yocto sample code
		sys.exit("init error" + str(errmsg))
except:
	e = sys.exc_info()[0]
	writeToLog("Error attaching yocto: " + str(e))

RPIO.setmode(RPIO.BCM)

#input/output (for now)
M_LED_PIN = 17 # UNUSED (for now)
R_LED_PIN = 22 # recording
L_LED_PIN = 27 # manual mode
R_SW_PIN = 23  # start record
M_SW_PIN = 24  # toggle manual mode
L_SW_PIN = 25  # stop record

#Input channels for MCP3008
POT_CHANNEL 		 = 0 # potentiometer input
AMBIENT_TEMP_CHANNEL = 1 # for later use


try:
	writeToLog("Setting up pin I/O...")
	#setup I/O
	RPIO.setup(L_LED_PIN, RPIO.OUT)
	RPIO.setup(R_LED_PIN, RPIO.OUT)
	RPIO.setup(M_LED_PIN, RPIO.OUT)
	RPIO.output(L_LED_PIN, True)
	RPIO.output(R_LED_PIN, True)
	RPIO.output(M_LED_PIN, True)
	RPIO.setup(L_SW_PIN, RPIO.IN)
	RPIO.setup(M_SW_PIN, RPIO.IN)
	RPIO.setup(R_SW_PIN, RPIO.IN)
except:
	e = sys.exc_info()[0]
	writeToLog("Error during pin setup: " + str(e))

blinkDelaySec = .25
longBlink = blinkDelaySec
shortBlink = blinkDelaySec / 2.0

try:
	writeToLog("Performing start-up blink sequence...")
	#show user that bootup is complete, script has started:
	for i in xrange(1,10):
		RPIO.output(L_LED_PIN, False)
		time.sleep(longBlink)
		RPIO.output(L_LED_PIN, True)
		RPIO.output(M_LED_PIN, False)
		time.sleep(longBlink)
		RPIO.output(M_LED_PIN, True)
		RPIO.output(R_LED_PIN, False)
		time.sleep(longBlink)
		RPIO.output(R_LED_PIN, True)
	#leave right LED on:
	RPIO.output(R_LED_PIN, False)
except:
	e = sys.exc_info()[0]
	writeToLog("Error during start-up blink: " + str(e))

try: #this may have halted us ONCE-- try to catch it again...		
	writeToLog("Recording initial L_SW_PIN position as off. State: ")
	ManualOffSwState = RPIO.input(L_SW_PIN) #set "off" to whatever the toggle switch is at when we start the script
	writeToLog(str(ManualOffSwState))
except:
	e = sys.exc_info()[0]
	writeToLog("Error during manual switch state init: " + str(e))
	
#Use for alerts and/or error codes
def blinkRLED(IDStr, count, blinkDelay):
	for i in xrange(1,count):
		RPIO.output(R_LED_PIN, True)
		time.sleep(blinkDelay)
		RPIO.output(R_LED_PIN, False)
		time.sleep(blinkDelay)

###########################################################
#Borrowed from Matt Hawkins script at: http://www.raspberrypi-spy.co.uk/2013/10/analogue-sensors-on-the-raspberry-pi-using-an-mcp3008/
# (Creative Commons Attribution-NonCommercial 3.0 License)
# Open SPI bus

try:
	writeToLog("Connecting ADC to SPI bus...")
	spi = spidev.SpiDev()
	spi.open(0,0)
except:
	e = sys.exc_info()[0]
	writeToLog("Error during SPI connect: " + str(e))

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
	tempF = tempC * 9.0 / 5.0 + 32.0
	return tempF


def rpio_callback(GPIO_id, val):
	#checking state during run instead, currently not using callback for toggle switch
	#if (GPIO_id == L_SW_PIN): #toggle manual mode
	#	if (val == False): #switch was pulled low (SOMEONE HIT IT!)
	#		writeToLog("Manual mode toggled to: " + str(mySmoker.manualServoMode))
	if (GPIO_id == M_SW_PIN):	
		if (val == False): #switch was pulled low (SOMEONE HIT IT!)
			smokeinfo.setRecording(True)			
			writeToLog("Manual recording button hit.")
	elif (GPIO_id == R_SW_PIN):	
		if (val == False): #switch was pulled low (SOMEONE HIT IT!)
			#smokeinfo.setRecording(False) #turn this off for now.
			writeToLog("Right switch hit.")

			
#output csv: (http://java.dzone.com/articles/python-101-reading-and-writing)
def outputCSV(ofilename, outputLine, mode):
	with open(ofilename, mode) as csv_file:
		writer = csv.writer(csv_file, delimiter=',')
		writer.writerow(outputLine)
			
class autoSmoker:
	def __init__(self):
		#sensor data
		#reference our sensor objects
		self.meatSensor = YTemperature.FindTemperature("smokerModule.meatTemp")
		self.smokerSensor = YTemperature.FindTemperature("smokerModule.smokerTemp")
		#servo data
		self.servoAngle = 0 #initial position is closed. 
		self.manualServoMode = False
		self.led1on = False #manual mode
		
	#sensor functions
	##################################
	def sensorTempF(self, sensor):
		if (sensor.isOnline()):
			return tempCtoF(sensor.get_currentValue())
		else:
			writeToLog("Could not get temp from sensor!")
			return 0

	def meatTempF(self):
		return self.sensorTempF(self.meatSensor)
		
	def smokerTempF(self):
		return self.sensorTempF(self.smokerSensor)
						
	#servo functions
	def setServoAngle(self, deg):
		if (deg < 0):
			self.servoAngle = 0
			writeToServo(deg)
		elif (deg > 180):
			self.servoAngle = 180
			writeToServo(deg)
		else:
			self.servoAngle = deg
			writeToServo(deg)
					
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
			
#RPIO.add_interrupt_callback(L_SW_PIN, rpio_callback) #checking state during run instead
RPIO.add_interrupt_callback(M_SW_PIN, rpio_callback)
RPIO.add_interrupt_callback(R_SW_PIN, rpio_callback)			
			
#start interrupt thread			
RPIO.wait_for_interrupts(threaded=True)


"""##############################################
#Email settings (outgoing) - put your settings here
##############################################"""
email_smtp_address = 
email_smtp_port = 587
email_login_name = 
email_password = 
emailserver = smtplib.SMTP(email_smtp_address, email_smtp_port)

class SmokeData:
	
	mailserverquit = False
	recording = False
	filename = "smokelog" + startdts + ".csv"
	targetMeatTemp = 145
	targetSmokerTemp = 225
	alertThresholdMinutes = 2	
	email_list = []
	startCookTime = 0
	elapsedTime = 0
		
	def setTargets(self, newMeatTemp, newSmokerTemp, newThresh):
		self.targetMeatTemp = newMeatTemp
		self.targetSmokerTemp = newSmokerTemp
		self.alertThresholdMinutes = newThresh
		
	def setEmailList(self, newEmailList):
		self.email_list = newEmailList
	
	def setRecording(self, newState):
		self.recording = newState
	
	def setFilename(self, newName):
		self.filename = newName
	
	def setStartCookTimeNow(self):
		self.startCookTime = time.time()
		
	def refreshElapsedTime(self):
		self.elapsedTime = time.time() - self.startCookTime
			
	def sendEmail(self, msgSubject, msgBody):
		if len(self.email_list) > 0: 
			fromaddr = email_login_name
			msg = MIMEMultipart()
			msg['Subject'] = msgSubject
			msg['From'] = fromaddr
			COMMASPACE = ', '
			msg['To'] = COMMASPACE.join(self.email_list)
			msg.attach(MIMEText(msgBody, 'plain'))
			try:
				writeToLog("Attempting to send email...")
				if (self.mailserverquit): #reconnect if we are sending an email after the first
					emailserver.connect(email_smtp_address, email_smtp_port)
				#emailserver.starttls()
				emailserver.ehlo()
				emailserver.set_debuglevel(True)
				emailserver.login(email_login_name, email_password)
				emailserver.sendmail(fromaddr, self.email_list, msg.as_string())
				emailserver.quit()
				self.mailserverquit = True #need to reconnect later if we want to send more mail
			except:
				e = sys.exc_info()[0]
				writeToLog("Error sending email: " + str(e))
		else:
			writeToLog("Did not send email: empty email list") #TODO: make client-viewable later
	def sendTestEmail(self):
		subject = "Test Email"
		body = "If you can read this, that's pretty sweet."
		self.sendEmail(subject, body)
	def sendMeatAtTempEmail(self, cookTime):
		subject = "Meat is done!"
		#from http://stackoverflow.com/questions/775049/python-time-seconds-to-hms
		m, s = divmod(cookTime, 60)
		h, m = divmod(m, 60)
		timestr = "%d:%02d:%02d" % (h, m, s)
		str1 = "The meat is done!\nThe meat has reached %1.2f degrees (F) after smoking for " % (mySmoker.meatTempF()) 
		str2 = ". The smoker temperature is %1.2f degrees (F)." % (mySmoker.smokerTempF())
		str3 = "\nThe target meat temperature was %1.2f degrees (F), and the target smoker temperature was %1.2f degrees (F)." % (self.targetMeatTemp, self.targetSmokerTemp)
		str4 = "\n\tlogfile: " + self.filename
		body = str1 + timestr + str2 + str3 + str4
		self.sendEmail(subject, body)
		
smokeinfo = SmokeData()
			
#while (elapsedTime < desiredCookTime ): #use later for a cook? 
class startIO(threading.Thread):
	meatAtTempTime = time.time() #use over time to verify we haven't got a false positive (i.e. probe set on grill while turning meat)
	meatAtTemp = False
	meatTempEmailSent = False #set to True after sent so that we aren't bombarding recipient with emails
	DELAY = 0.1 #keep servo response quick by not waiting too long. This delay will also be important
			#for knowing when to record values (for later plotting)
	WRITE_INTERVAL = 5 #output to file approximately every 5 seconds
	timerStart = time.time()
	n = 0
	#desiredCookTime = 120  #TODO: get from user input 
	startNewCSV = True
		
	def __init__ (self):
		threading.Thread.__init__(self)	
	
	def run(self):
		while (True):
			#added for using toggle switch
			try:
				if (RPIO.input(L_SW_PIN) != ManualOffSwState):
					mySmoker.setManualMode(True)
				else:
					mySmoker.setManualMode(False)
			except:
				e = sys.exc_info()[0]
				writeToLog("Error during manual switch state retrieval: " + str(e))
			
			try:
				if (mySmoker.manualServoMode == True):
					potLevel = ReadChannel(POT_CHANNEL)
					potVolts = ConvertVolts(potLevel,2)
					mySmoker.setServoFromPot(potVolts)
			except:
				e = sys.exc_info()[0]
				writeToLog("Error during manual positioning of servo: " + str(e))
		
			try:
				if (smokeinfo.recording == True):
					RPIO.output(M_LED_PIN, False)	
					smokeinfo.refreshElapsedTime()
					if ((time.time() - self.timerStart) >= self.WRITE_INTERVAL): #start timer over, record to file 
						self.timerStart = time.time() 
						self.n += 1
						if (self.startNewCSV == True):
							mode = 'wb' 		# write new file (binary)
							self.startNewCSV = False # append for rest of run 
						else:
							mode = 'ab' # append (binary)
						currentLine = [self.n, str(datetime.now()), round(smokeinfo.elapsedTime, 2), mySmoker.smokerTempF(), mySmoker.meatTempF(), mySmoker.servoAngle]
						outputCSV(smokeinfo.filename, currentLine, mode)
				else:
					smokeinfo.setStartCookTimeNow()	#keep moving timer forward until we start
					RPIO.output(M_LED_PIN, True)
			except:
				e = sys.exc_info()
				writeToLog("Error during CSV recording/recording state check: " + str(e))
			
			try:
				if (self.meatTempEmailSent == False):
					if (mySmoker.meatTempF() >= smokeinfo.targetMeatTemp):
						if (self.meatAtTemp == False): #start timer if not started
							self.meatAtTemp = True
							self.meatAtTempTime = time.time()	
							writeToLog("Starting timer, meat at: " + str(mySmoker.meatTempF()) + "F. -- target is: " + str(smokeinfo.targetMeatTemp) + "F.") 
							#thread.start_new_thread(blinkRLED, ("Thread-2", 3, longBlink ))
						if self.meatAtTemp and ((time.time() - self.meatAtTempTime) >= (smokeinfo.alertThresholdMinutes * 60.0)): #meat has been at temp longer than threshhold time
							writeToLog("meat at temp for required time.")
							#thread.start_new_thread(blinkRLED, ("Thread-2", 30, longBlink ))
							smokeinfo.sendMeatAtTempEmail(smokeinfo.elapsedTime) 
							self.meatTempEmailSent = True	
					else: #likely false alarm (or something else happened)
						if self.meatAtTemp:
							writeToLog("Resetting timer (meat below required temp). Meat at: " + str(mySmoker.meatTempF()) + "F. -- target is: " + str(smokeinfo.targetMeatTemp) + "F.") 
							self.meatAtTemp = False
			except:
				e = sys.exc_info()
				writeToLog("Error during meat temp check: " + str(e))
			time.sleep(self.DELAY)

	
try:
	print "Starting main thread..."
	thread = startIO()
	#thread.daemon = True
	#thread.setDaemon(True)
	thread.start()
except:
	print "DANGER, WILL ROBINSON!!!"
	e = sys.exc_info()[0]
	writeToLog("Error running main thread: " + str(e))	
