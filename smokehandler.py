import webui
import autosmoker
import sys
import threading
import time

class webserver(threading.Thread):
	def __init__ (self):
		threading.Thread.__init__(self)	
	
	def run(self):
		webui.app.run()
		
class datahandler(threading.Thread):
	DELAY = 0.1
			
	def __init__ (self):
		threading.Thread.__init__(self)	
	
	def run(self):
		while True:
			webui.currentsmoke.setCurrentTemps(autosmoker.smokeinfo.meatTemp, autosmoker.smokeinfo.smokerTemp)
			webui.currentsmoke.setServo(autosmoker.mySmoker.servoAngle)
			webui.currentsmoke.setManual(autosmoker.mySmoker.manualServoMode)
			if (autosmoker.smokeinfo.recording == False) and (webui.currentsmoke.recording == True):
				if (len(webui.currentsmoke.smokefile) > 0):
					autosmoker.smokeinfo.setFilename(webui.currentsmoke.smokefile)
				autosmoker.smokeinfo.setRecording(True)
			if (webui.currentsmoke.changeTargets == True):	
				autosmoker.smokeinfo.setTargets(webui.currentsmoke.target_meat, webui.currentsmoke.target_smoker,2)
				webui.currentsmoke.updatedTargets() #tell it that we dont need the new values, now
			if (webui.currentsmoke.changeEmails == True):
				autosmoker.smokeinfo.setEmailList(webui.currentsmoke.email_list)
				webui.currentsmoke.updatedTargets() #tell it that we dont need the new values, now
			time.sleep(self.DELAY)

threads = []
		
if __name__ == '__main__':
	try:
		print "starting data intermediary.."
		datathread = datahandler()
		datathread.start()
		threads.append(datathread)
		time.sleep(0.5) #make sure data has been pulled from autosmoker before starting webpage
		print "starting web page..."
		webthread = webserver()
		webthread.start()
		threads.append(webthread)
	except:
		print "DANGER, WILL ROBINSON!!!"
		e = sys.exc_info()[0]
		print ("Error: " + str(e))