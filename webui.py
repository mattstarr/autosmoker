#helpful info/example at: http://www.themagpi.com/issue/issue-9/article/the-python-pit-drive-your-raspberry-pi-with-a-mobile-phone/
#smtp code from: http://www.pythonforbeginners.com/code-snippets-source-code/using-python-to-send-email

#imports
from datetime import datetime #for current time
from datetime import timedelta
import sys, time
import web
from web import form
import threading
	
urls = ('/', 'index')
render = web.template.render('templates/')

app = web.application(urls, globals())

meat_prompt = 'Target Meat Temp (F):'
smoker_prompt = 'Target Smoker Temp (F):'
filename_prompt = 'Output Filename:' 

startdts = time.strftime("%d%m%y%H%M") #date/time string (minus second)

class infoHandler:
	#from autosmoker to webui (mostly)
	meat_temp = 0
	smoker_temp = 0
	servo = 0
	manual = False
	startCookTime = 0
	#from webui to smoker (mostly)
	target_meat = 160
	target_smoker = 225
	email_list = []
	smokefile = "smokelog" + startdts + ".csv"
	recording = False
	changeTargets = True
	changeEmails = False
	sprocket = "A"
	
	def setSprocket(self, newSprocket):
		self.sprocket = newSprocket
	
	def setCurrentTemps(self, newMeatT, newSmokerT):
		self.meat_temp = newMeatT
		self.smoker_temp = newSmokerT	
	def setCurrentTargets(self, newMeatT, newSmokerT):
		self.target_meat = newMeatT
		self.target_smoker = newSmokerT	
		self.changeTargets = True
	def updatedTargets(self): #run after getting target values
		self.changeTargets = False
	def setServo(self, newAngle):
		self.servo = newAngle	
	def setManual(self, newMan):
		self.manual = newMan	
	def setRecording(self, newRec):
		if newRec == True:
			if self.recording == False: #start timer
				self.startCookTime = time.time()
			self.recording = True
		else:
			self.recording = False	
	def setEmailList(self, newList):
		self.email_list = newList		
		self.changeEmails = True
	def updatedEmails(self): #run after getting email list
		self.changeEmails = False
	def setFilename(self, newName):
		self.smokefile = newName		
	def getElapsedTime(self):
		if self.startCookTime == 0:
			return 0
		else:
			return (time.time() - self.startCookTime)
	
currentsmoke = infoHandler()	


main_form = form.Form(
	form.Button('btn', id="btnRefresh", value="refresh", html="REFRESH"),
	form.Textbox('Send to:', #parse to accept addresses separated by commas!
		id="destEmail",
		#value=""),
		value=', '.join(currentsmoke.email_list)),
	#allow custom mx form items later - for now, use account at mattstarr.net!
	form.Button('btn', id="btnSetEmail", value="set", html="Set Email Info"),
	form.Button('btn', id="btnTestEmail", value="test", html="Send Test Email"),
	#previously in separate form
	form.Textbox(filename_prompt, 
		form.notnull, 
		id="txtFileOut", 
		value=currentsmoke.smokefile),
	form.Textbox(meat_prompt, 
		form.notnull, 
		form.regexp('\d+', 'Temperature must be a digit!'),
		form.Validator('Must be a number', lambda x: not x or int(x) > 0),
		id="txtTargetMeatTemp",
		value=str(currentsmoke.target_meat)),		
	form.Textbox(smoker_prompt, 
		form.notnull, 
		form.regexp('\d+', 'Temperature must be a digit!'),
		form.Validator('Must be a number', lambda x: not x or int(x) > 0),
		id="txtTargetSmokerTemp",
		value=str(currentsmoke.target_smoker)),	
	form.Button('btn', id="btnStart", value="start", html="Start + Record")
)


def getMainForm():
	mainform = form.Form(
		form.Button('btn', id="btnRefresh", value="refresh", html="REFRESH"),
		form.Textbox('Send to:', #parse to accept addresses separated by commas!
			id="destEmail",
			#value=""),
			value=', '.join(currentsmoke.email_list)),
		#allow custom mx form items later - for now, use account at mattstarr.net!
		form.Button('btn', id="btnSetEmail", value="set", html="Set Email Info"),
		form.Button('btn', id="btnTestEmail", value="test", html="Send Test Email"),
		#previously in separate form
		form.Textbox(filename_prompt, 
			form.notnull, 
			id="txtFileOut", 
			value=currentsmoke.smokefile),
		form.Textbox(meat_prompt, 
			form.notnull, 
			form.regexp('\d+', 'Temperature must be a digit!'),
			form.Validator('Must be a number', lambda x: not x or int(x) > 0),
			id="txtTargetMeatTemp",
			value=str(currentsmoke.target_meat)),		
		form.Textbox(smoker_prompt, 
			form.notnull, 
			form.regexp('\d+', 'Temperature must be a digit!'),
			form.Validator('Must be a number', lambda x: not x or int(x) > 0),
			id="txtTargetSmokerTemp",
			value=str(currentsmoke.target_smoker)),	
		form.Button('btn', id="btnStart", value="start", html="Start + Record")
	)
	return mainform()



class index:
	rendertime = str(datetime.now())
	smoketimestr = ""
	targetmeat = ""
	targetsmoker = ""	
	meattempstr = ""
	smokertempstr = "" 
	manmodestr = ""
	servoangle = 0 
	doorangle = 0
	targetmeat = ""
	targetsmoker = ""
	form = getMainForm()
	
	def GET(self):
		#try:
			self.form = getMainForm()
			self.rendertime = str(datetime.now())
			self.smoketimestr = ""
			self.targetmeat = ""
			self.targetsmoker = ""
			if (currentsmoke.getElapsedTime() == 0):
				self.smoketimestr = "Smoke has not been started."
				self.targetmeat = "Target meat temperature not yet set."
				self.targetsmoker = "Target smoker temperature not yet set."
			else:
				#from http://stackoverflow.com/questions/775049/python-time-seconds-to-hms
				m, s = divmod(currentsmoke.getElapsedTime(), 60)
				h, m = divmod(m, 60)
				timestr = "%d:%02d:%02d" % (h, m, s)
				self.smoketimestr = "Elapsed smoke time: " + timestr
				self.targetmeat = "Target meat temperature: %1.2f degrees (F)." % currentsmoke.target_meat
				self.targetsmoker = "Target smoker temperature: %1.2f degrees (F)." % currentsmoke.target_smoker
			self.meattempstr = "{:.2f}".format(currentsmoke.meat_temp)
			self.smokertempstr = "{:.2f}".format(currentsmoke.smoker_temp)
			if (currentsmoke.manual == True):
				self.manmodestr = "Manual mode engaged."
			else:
				self.manmodestr = "Automatic mode engaged."
			self.servoangle = currentsmoke.servo
			sprocketmult = 0;
			if (currentsmoke.sprocket == "A"):
				sprocketmult = 0.625 #.625 is ratio of sprockets (10:16)
			elif (currentsmoke.sprocket == "B"):
				sprocketmult = 0.4166666666666667 #.416666667 is ratio of sprockets (10:24)
			else:
				print "wrong sprocket size!"
			self.doorangle = "{:.2f}".format(float(self.servoangle) * sprocketmult) 
			#except:
			#	e = sys.exc_info()
			#	autosmoker.writeToLog("Error during index.GET(): " + str(e))
			#	raise	
			return render.index(self.form, "Autosmoker Web UI", self.rendertime, self.smoketimestr, self.meattempstr, self.smokertempstr, self.manmodestr, self.servoangle, self.doorangle, self.targetmeat, self.targetsmoker)
	
    # POST is called when a web form is submitted
	def POST(self):
		#try:
			#figure out form validation and put here later(?)
			form = main_form(web.input())
			if form.btn.value == 'refresh': #do before validate, since we dont care!
				raise web.seeother('/')
			if form.validates():
				if form.btn.value == 'set':
					#parse comma separated email/text addresses:
					emails = str(form['Send to:'].value).split(",")
					currentsmoke.setEmailList(emails)
				elif form.btn.value == 'test': #currently defunct
					pass
					#autosmoker.smokeinfo.sendTestEmail()
				elif form.btn.value == 'start':
					#get the smoker and file rolling!!!
					currentsmoke.setCurrentTargets(int(form[meat_prompt].value), int(form[smoker_prompt].value)) 
					currentsmoke.setFilename(str(form[filename_prompt].value))
					currentsmoke.setRecording(True)
					print "setting true"
				else:
					print "What button did you even push?!?!"
				raise web.seeother('/')
			else:
				raise web.seeother('/')
				#return render.index(form, "Autosmoker Web UI")
		#except:
		#	e = sys.exc_info()
		#	autosmoker.writeToLog("Exception during index.POST(): " + str(e))	
		#	pass
# run

#class display:
	



if __name__ == '__main__':
	app.run()
	
#Uncomment to turn off debug:	
#web.config.debug = False
	