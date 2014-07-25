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
#import RPIO
#from RPIO import PWM
import RPi.GPIO as GPIO
import wiringpi

from datetime import datetime #for current time
import csv #for csv output
import threading
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
import random

"""##############################################
#Email settings (outgoing) - put your settings here
##############################################"""
email_smtp_address = 
email_smtp_port = 587
email_login_name = 
email_password = 
# emailserver = smtplib.SMTP(email_smtp_address, email_smtp_port)

def getDTS():
	return time.strftime("%d/%m/%y %H:%M:%S")
	
startdts = time.strftime("%d%m%y%H%M") #date/time string (minus second)
logfilename = "debuglog" + startdts + ".log"
#redirect sdout to file, since we are not running in a terminal -- fix?
#stdoutlog = "stdoutlog" + startdts + ".log"
#sys.stdout = open(stdoutlog, 'w')

servofilename = "servo.txt"

def writeToLog(outputLine): #and print for debug if running from command line!
	with open(logfilename, 'a') as logfile:
		logfile.write(getDTS() + ": " + outputLine + '\n')
		print outputLine

def writeToServo(position): 
	with open(servofilename, 'w') as servofile:
		servofile.write(str(position))

writeToServo(0)		
		
#try:   
#attach yocto device
writeToLog("Connecting yocto...")
errmsg = YRefParam()
if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS: #from yocto sample code
	sys.exit("init error" + str(errmsg))
#except:
#	e = sys.exc_info()[0]
#	writeToLog("Error attaching yocto: " + str(e))

GPIO.setmode(GPIO.BCM)

#input/output (for now)
M_LED_PIN = 17 
R_LED_PIN = 22 
L_LED_PIN = 27
R_SW_PIN = 23  
M_SW_PIN = 24  
L_SW_PIN = 25  

#Input channels for MCP3008
POT_CHANNEL 		 = 0 # potentiometer input
AMBIENT_TEMP_CHANNEL = 1 # for later use


try:
	writeToLog("Setting up pin I/O...")
	#setup I/O
	GPIO.setup(L_LED_PIN, GPIO.OUT)
	GPIO.setup(R_LED_PIN, GPIO.OUT)
	GPIO.setup(M_LED_PIN, GPIO.OUT)
	GPIO.output(L_LED_PIN, True)
	GPIO.output(R_LED_PIN, True)
	GPIO.output(M_LED_PIN, True)
	GPIO.setup(L_SW_PIN, GPIO.IN)
	GPIO.setup(M_SW_PIN, GPIO.IN)
	GPIO.setup(R_SW_PIN, GPIO.IN)
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
		GPIO.output(L_LED_PIN, False)
		time.sleep(longBlink)
		GPIO.output(L_LED_PIN, True)
		GPIO.output(M_LED_PIN, False)
		time.sleep(longBlink)
		GPIO.output(M_LED_PIN, True)
		GPIO.output(R_LED_PIN, False)
		time.sleep(longBlink)
		GPIO.output(R_LED_PIN, True)
	#leave right LED on:
	GPIO.output(R_LED_PIN, False)
except:
	e = sys.exc_info()[0]
	writeToLog("Error during start-up blink: " + str(e))

try: #this may have halted us ONCE-- try to catch it again...		
	writeToLog("Recording initial L_SW_PIN position as off. State: ")
	ManualOffSwState = GPIO.input(L_SW_PIN) #set "off" to whatever the toggle switch is at when we start the script
	writeToLog(str(ManualOffSwState))
except:
	e = sys.exc_info()[0]
	writeToLog("Error during manual switch state init: " + str(e))
	
#Use for alerts and/or error codes

class blinkRLED(threading.Thread):

	def __init__(self, count, blinkDelay):
		threading.Thread.__init__(self)	
		self.my_count = count
		self.my_blink_delay = blinkDelay
	def run(self):
		for i in xrange(1,self.my_count):
			GPIO.output(R_LED_PIN, True)
			time.sleep(self.my_blink_delay)
			GPIO.output(R_LED_PIN, False)
			time.sleep(self.my_blink_delay)

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


def GPIO_callback(GPIO_id, val):
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
		self.sprocket = "A" #A = 16t, B = 24t
		
	#sensor functions
	##################################
	def sensorTempF(self, sensor):
		try:
			if (sensor.isOnline()):
				return tempCtoF(sensor.get_currentValue())
			else:
				writeToLog("Could not get temp from sensor!")
				return 0
		except:
			e = sys.exc_info()
			writeToLog("Error: " + str(e))
			global errmsg
			errmsg = YRefParam()
			if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS: #from yocto sample code
				sys.exit("init error" + str(errmsg))
	
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
			GPIO.output(L_LED_PIN, True)
		else:
			self.led1on = True
			GPIO.output(L_LED_PIN, False)
		
	def toggleManualMode(self): #to be called by button callback function
		if (self.manualServoMode == False):
			self.setManualMode(True)
		else:
			self.setManualMode(False)
			
	def setServoFromAutomation(self, position):
		#use dictionary later...
		if (position == 1): #smother
			self.setServoAngle(0)
		elif (position == 2): #lower temp
			if (self.sprocket == "A"): #A = 16t, B = 24t
				self.setServoAngle(48)
			elif (self.sprocket == "B"): 
				self.setServoAngle(72)
		elif (position == 3): #hold temp 
			if (self.sprocket == "A"): #A = 16t, B = 24t
				self.setServoAngle(72)
			elif (self.sprocket == "B"): 
				self.setServoAngle(108)
		elif (position == 4): #increase temp
			if (self.sprocket == "A"): #A = 16t, B = 24t
				self.setServoAngle(96)
			elif (self.sprocket == "B"): 
				self.setServoAngle(144)
		elif (position == 5): #"revive" fire
			if (self.sprocket == "A"): #A = 16t, B = 24t
				self.setServoAngle(144)
			elif (self.sprocket == "B"): 
				self.setServoAngle(180)
		else:
			writeToLog("Incorrect position!")

mySmoker = autoSmoker()
mySmoker.setServoAngle(0) #make sure it is set closed
			
#RPIO.add_interrupt_callback(L_SW_PIN, rpio_callback) #checking state during run instead
#RPIO.add_interrupt_callback(M_SW_PIN, rpio_callback)
#RPIO.add_interrupt_callback(R_SW_PIN, rpio_callback)			
			
#start interrupt thread			
#RPIO.wait_for_interrupts(threaded=True)

class SmokeData:
	
	meatTemp = 0
	smokerTemp = 0
	mailserverquit = False
	recording = False
	filename = "smokelog" + startdts + ".csv"
	targetMeatTemp = 160
	targetSmokerTemp = 300
	alertThresholdMinutes = 2	
	email_list = []
	startCookTime = 0
	elapsedTime = 0
	tsThresh = 12.5 #target smoker temp threshold -- window for each position will be 2* this number
	webManual = False
	startWithTimer = True
	
	def setStartWithTimer(self, newValue):
		self.startWithTimer = newValue
	
	def setWebManual(self, newMan):
		self.webManual = newMan
		
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
			emailserver = smtplib.SMTP(email_smtp_address, email_smtp_port)
			fromaddr = email_login_name
			msg = MIMEMultipart()
			msg['Subject'] = msgSubject
			msg['From'] = fromaddr
			COMMASPACE = ', '
			msg['To'] = COMMASPACE.join(self.email_list)
			msg.attach(MIMEText(msgBody, 'plain'))
			try:
				emailserver.set_debuglevel(True)
				writeToLog("Attempting to send email...")
				if (self.mailserverquit): #reconnect if we are sending an email after the first
					emailserver.connect(email_smtp_address, email_smtp_port)
				emailserver.ehlo()
				emailserver.starttls()
				emailserver.ehlo()
				emailserver.login(email_login_name, email_password)
				emailserver.sendmail(fromaddr, self.email_list, msg.as_string())
				emailserver.quit()
				self.mailserverquit = True #need to reconnect later if we want to send more mail
				writeToLog("Email sent successfully (I think...)")
			except:
				e = sys.exc_info()
				writeToLog("Error sending email: " + str(e))
		else:
			writeToLog("Did not send email: empty email list") #TODO: make client-viewable later
	def sendTestEmail(self):
		subject = "Test Email"
		body = "If you can read this, that's pretty sweet."
		self.sendEmail(subject, body)
	def sendMeatAtTempEmail(self, cookTime):
		#from http://stackoverflow.com/questions/775049/python-time-seconds-to-hms
		m, s = divmod(cookTime, 60)
		h, m = divmod(m, 60)
		timestr = "%d:%02d:%02d" % (h, m, s)
		#randomly decide to add cook time to subject
		showtimechoice = random.randint(1,2)
		if showtimechoice == 1:
			subject = self.getRandSubjectStr() + " - cook time is " + timestr
		else:
			subject = self.getRandSubjectStr()
		str0 = self.getRandSubjectStr()
		str1 = "\nThe meat has reached %1.2f degrees (F) after smoking for " % (self.meatTemp) 
		str2 = ". The smoker temperature is %1.2f degrees (F)." % (self.smokerTemp)
		str3 = "\nThe target meat temperature was %1.2f degrees (F), and the target smoker temperature was %1.2f degrees (F)." % (self.targetMeatTemp, self.targetSmokerTemp)
		str4 = "\n\tlogfile: " + self.filename
		body = str0 + str1 + timestr + str2 + str3 + str4
		self.sendEmail(subject, body)
		
	def getRandSubjectStr(self): #keep it random-ish to avoid being marked as spam or UCE
		subj = ""
		choice = random.randint(1,12)
		if (choice == 1):
			subj = "Meat is done!"
		elif (choice == 2):
			subj = "Come grab your food!"
		elif (choice == 3):
			subj = "Time for eats!"
		elif (choice == 4):
			subj = "Rush to the smoker!"
		elif (choice == 5):
			subj = "Dude, food!"
		elif (choice == 6):
			subj = "It's just how you like it!"
		elif (choice == 7):
			subj = "Hurry, before it dries out!"
		elif (choice == 8):
			subj = "Time to rest your meat!"
		elif (choice == 9):
			subj = "nomnomnomnomnom alert!"
		elif (choice == 10):
			subj = "I hope you're hungry!"
		elif (choice == 11):
			subj = "Time to put something yummy in your tummy!"
		elif (choice == 12):
			subj = "RE: heads up on the chow."
		else:
			subj = "Here's a random subject title! Fix your code, jerk!"
		return subj
		
	def getNewTemps(self):
		curMeat = mySmoker.meatTempF()
		curSmoke = mySmoker.smokerTempF()
		#Yes - the following MAY rule out legitimate readings of 0 degrees F. However,
		#if read fails, we want to use old values until we can get our next reading, rather than 
		#placing an incorrect 0 in our dataset.
		if curMeat != 0:
			self.meatTemp = curMeat
		if curSmoke != 0:
			self.smokerTemp = curSmoke 
		
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
		position = 1
		newPosition = 3
		while (True):
			global errmsg
			errmsg = YRefParam()
			if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS: #from yocto sample code
				sys.exit("init error" + str(errmsg))
			#added for safety
			smokeinfo.getNewTemps()
			#added for using toggle switch
			try:
				if (GPIO.input(L_SW_PIN) != ManualOffSwState):
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
		
			#try:
			if (smokeinfo.recording == True):
				GPIO.output(M_LED_PIN, False)	
				smokeinfo.refreshElapsedTime()
				if ((time.time() - self.timerStart) >= self.WRITE_INTERVAL): #start timer over, record to file 
					self.timerStart = time.time() 
					self.n += 1
					if (self.startNewCSV == True):
						mode = 'wb' 		# write new file (binary)
						self.startNewCSV = False # append for rest of run 
					else:
						mode = 'ab' # append (binary)
					currentLine = [self.n, str(datetime.now()), round(smokeinfo.elapsedTime, 2), smokeinfo.smokerTemp, smokeinfo.meatTemp, mySmoker.servoAngle, mySmoker.manualServoMode, smokeinfo.targetSmokerTemp, smokeinfo.targetMeatTemp]
					outputCSV(smokeinfo.filename, currentLine, mode)
					
				#automation time!
				if (mySmoker.manualServoMode == False) and (smokeinfo.webManual == False):
					#hold at chosen position				
					if (smokeinfo.startWithTimer == True) and (smokeinfo.elapsedTime < 300):
						newPosition = 2
					else:
						#set position based on temp
						if (smokeinfo.smokerTemp > (smokeinfo.targetSmokerTemp + (3.0 * smokeinfo.tsThresh))):
							#quench
							newPosition = 1
						elif (smokeinfo.smokerTemp > (smokeinfo.targetSmokerTemp + smokeinfo.tsThresh)) and (smokeinfo.smokerTemp <= (smokeinfo.targetSmokerTemp + (3.0 * smokeinfo.tsThresh))):
							#lower temp
							newPosition = 2
						elif (smokeinfo.smokerTemp >= (smokeinfo.targetSmokerTemp - smokeinfo.tsThresh)) and (smokeinfo.smokerTemp <= (smokeinfo.targetSmokerTemp + smokeinfo.tsThresh)):
							#hold
							newPosition = 3
						elif (smokeinfo.smokerTemp >= (smokeinfo.targetSmokerTemp - (3.0 * smokeinfo.tsThresh))) and (smokeinfo.smokerTemp < (smokeinfo.targetSmokerTemp - smokeinfo.tsThresh)):
							#raise
							newPosition = 4
						elif (smokeinfo.smokerTemp < (smokeinfo.targetSmokerTemp - (3.0 * smokeinfo.tsThresh))):
							#"revive" fire
							newPosition = 5
						else:
							#???
							writeToLog("Logic error in automation...")
												
					if (newPosition != position):
						position = newPosition
						writeToLog("Target smoker temp: " + str(smokeinfo.targetSmokerTemp))
						writeToLog("Actual smoker temp: " + str(smokeinfo.smokerTemp))
						writeToLog("Setting position auto to: " + str(position))
						mySmoker.setServoFromAutomation(position)
				else:
					position = 0 #so that we can resume 5 min startup or other auto position
			else:
				smokeinfo.setStartCookTimeNow()	#keep moving timer forward until we start
				GPIO.output(M_LED_PIN, True)
			#except:
			#	e = sys.exc_info()
			#	writeToLog("Error during CSV recording/recording state check: " + str(e))
			
			#try:
			if (self.meatTempEmailSent == False):
				if (smokeinfo.meatTemp >= smokeinfo.targetMeatTemp):
					if (self.meatAtTemp == False): #start timer if not started
						self.meatAtTemp = True
						self.meatAtTempTime = time.time()	
						writeToLog("Starting timer, meat at: " + str(smokeinfo.meatTemp) + "F. -- target is: " + str(smokeinfo.targetMeatTemp) + "F.") 
						b10thread = blinkRLED(10, shortBlink)
						b10thread.start()
					if self.meatAtTemp and ((time.time() - self.meatAtTempTime) >= (smokeinfo.alertThresholdMinutes * 60.0)): #meat has been at temp longer than threshhold time
						writeToLog("meat at temp for required time.")
						b30thread = blinkRLED(30, longBlink)
						b30thread.start()
						smokeinfo.sendMeatAtTempEmail(smokeinfo.elapsedTime) 
						self.meatTempEmailSent = True	
				else: #likely false alarm (or something else happened)
					if (self.meatAtTemp and (smokeinfo.meatTemp < (smokeinfo.targetMeatTemp - 5.5))): #change 5.5 to thresh, later
						writeToLog("Resetting timer (meat below required temp). Meat at: " + str(smokeinfo.meatTemp) + "F. -- target is: " + str(smokeinfo.targetMeatTemp) + "F.") 
						self.meatAtTemp = False
			#except:
			##	writeToLog("Error during meat temp check: " + str(e))
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
