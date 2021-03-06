#helpful info/example at: http://www.themagpi.com/issue/issue-9/article/the-python-pit-drive-your-raspberry-pi-with-a-mobile-phone/
#smtp code from: http://www.pythonforbeginners.com/code-snippets-source-code/using-python-to-send-email

#imports
from datetime import datetime #for current time
from datetime import timedelta
import sys, time
import web
from web import form
import threading
import smtpInfo
	
urls = ('/', 'index', 
		'/infopage.html', 'infopage',
		'/emailsettings.html', 'emailsettings')
render = web.template.render('templates/')

app = web.application(urls, globals())

#for index
meat_prompt = 'Target Meat Temp (F):'
smoker_prompt = 'Target Smoker Temp (F):'
filename_prompt = 'Output Filename:' 
webmanual_prompt = 'Manual Door Angle:'
radio_prompt='Mode:'
timer_prompt='5 min. Hold on:'
#for email_settings
server_prompt = 'Server IP/Hostname:'
port_prompt = 'Server Port #:'
username_prompt = 'Username:'
password_prompt = 'Password:'

startdts = time.strftime("%d%m%y%H%M") #date/time string (minus second)
		
emailInfo = smtpInfo.readSmtpInfo()	
		
class infoHandler:
	#from autosmoker to webui (mostly)
	meat_temp = 0
	smoker_temp = 0
	web_manual_angle = 0
	servo = 0
	manual = False
	radio = 'auto' #manual entry on webpage. cannot override manual switch
	startCookTime = 0
	#from webui to smoker (mostly)
	target_meat = 160
	target_smoker = 225
	email_list = []
	smokefile = "smokelog" + startdts + ".csv"
	recording = False
	changeTargets = True
	changeEmails = False
	startWithTimer=True #switch to checkbox later
	startWithTimerRadio='on'
	stopRecording = False
	
	def setStopRecording(self, newRec):
		self.stopRecording = newRec
	
	def setStartWithTimerRadio(self, newRadio): #cause checkboxes are not working for me
		self.startWithTimerRadio = newRadio
		if (self.startWithTimerRadio == 'on'):
			self.setStartWithTimer(True)
		else:
			self.setStartWithTimer(False)
	
	def setStartWithTimer(self, newChecked):
		self.startWithTimer = newChecked
	def getDoorAngle(self):
		sprmult = 0.625
		if (self.manual == False) and (self.radio == 'manual'):
			return int(self.web_manual_angle)
		else:
			return int(sprmult * self.servo)
	
	def setWebManual(self, newMan, newWebManualAngle):
		self.web_manual_angle = newWebManualAngle
		self.radio = newMan
		if (self.manual == False) and (self.radio == 'manual'):
			if (self.web_manual_angle <= 0):
				self.web_manual_angle = 0
				self.servo = 0
			else: 
				self.servo = round(1.6 * newWebManualAngle)
				if self.servo > 180:
					self.web_manual_angle = int(180.0 * 0.625)
					self.servo = 180		
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

def getMainForm():
	mainform = form.Form(
		form.Button('btn', id="btnRefresh", value="refresh", html="REFRESH"),
		form.Textbox('Send to:', #parse to accept addresses separated by commas!
			id="destEmail",
			#value=""),
			value=', '.join(currentsmoke.email_list)),
		#allow custom mx form items later - for now, use account at mattstarr.net!
		form.Button('btn', id="btnSetEmail", value="set", html="Set Email Info"),
		#form.Button('btn', id="btnTestEmail", value="test", html="Send Test Email"),
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
		form.Radio('startTimer',[('on','On'),('off','Off')],description=timer_prompt,value=currentsmoke.startWithTimerRadio),
		form.Button('btn', id="btnStart", value="start", html="Start + Record"),
		form.Button('btn', id="btnStop", value="stop", html="Stop"),
		form.Radio('radio',[('auto','Automatic'),('manual','Manual')],description=radio_prompt,value=currentsmoke.radio),
		form.Textbox(webmanual_prompt, 
			form.notnull, 
			form.regexp('\d+', 'Angle must be a digit!'),
			form.Validator('Must be a number', lambda x: not x or int(x) >= 0),
			id="txtWebManualAngle",
			value=str(currentsmoke.getDoorAngle())),	
		form.Button('btn', id="btnNewSettings", value="newsettings", html="Enter Settings")
	)
	return mainform()
	

def getEmailForm():
	emailform = form.Form(
		form.Textbox(server_prompt,
					id="txtServer",
					value=str(emailInfo.smtp_server)),
		form.Textbox(port_prompt,
					id="txtPort",
					value=str(emailInfo.smtp_port)),
		form.Textbox(username_prompt,
					id="txtUsername",
					value=emailInfo.smtp_username),
		form.Password(password_prompt,
					id="pwdPassword",
					value=emailInfo.smtp_password),
		form.Button('btn', id='btnEnter', value='enter', html="Save Settings")
	)
	return emailform()
					
main_form = getMainForm()
email_form = getEmailForm()

class index:
	form = getMainForm()
	
	def GET(self):
		#try:
			self.form = getMainForm()
			self.rendertime = str(datetime.now())
			return render.index(self.form, "Autosmoker Web UI")
	
    # POST is called when a web form is submitted
	def POST(self):
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
				currentsmoke.setStartWithTimerRadio(form['startTimer'].value)
				currentsmoke.setRecording(True)
				print "start"
			elif form.btn.value == 'stop':
				currentsmoke.setRecording(False)
				#currentsmoke.setStopRecording(True)
			elif form.btn.value == "newsettings":
				currentsmoke.setCurrentTargets(int(form[meat_prompt].value), int(form[smoker_prompt].value)) 
				currentsmoke.setWebManual(form['radio'].value, float(form[webmanual_prompt].value))
				currentsmoke.setStartWithTimerRadio(form['startTimer'].value)
			else:
				print "What button did you even push?!?!"
			raise web.seeother('/')
		else:
			raise web.seeother('/')
			
#class display:
class infopage:
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
	
	def GET(self):
		try:
			self.rendertime = str(datetime.now())
			self.smoketimestr = ""
			self.targetmeat = ""
			self.targetsmoker = ""
			if (currentsmoke.recording == False):
				self.smoketimestr = "Smoke is not recording."
				self.targetmeat = "Target meat temperature not yet set."
				self.targetsmoker = "Target smoker temperature not yet set."
			else:
				#from http://stackoverflow.com/questions/775049/python-time-seconds-to-hms
				m, s = divmod(currentsmoke.getElapsedTime(), 60)
				h, m = divmod(m, 60)
				timestr = "%d:%02d:%02d" % (h, m, s)
				self.smoketimestr = "Elapsed smoke time: " + timestr
				self.targetmeat = "Target meat temperature: %1.2f degrees (F)." % float(currentsmoke.target_meat)
				self.targetsmoker = "Target smoker temperature: %1.2f degrees (F)." % float(currentsmoke.target_smoker)
			self.meattempstr = "{:.2f}".format(float(currentsmoke.meat_temp))
			self.smokertempstr = "{:.2f}".format(float(currentsmoke.smoker_temp))
			if (currentsmoke.manual == True):
				self.manmodestr = "Manual mode engaged."
			else:
				if (currentsmoke.radio == 'manual'):
					self.manmodestr = "Web manual mode engaged."
				else:	
					self.manmodestr = "Automatic mode engaged."
			self.servoangle = currentsmoke.servo
			sprocketmult = 0.625 #.625 is ratio of sprockets (10:16)
			self.doorangle = "{:.2f}".format(float(self.servoangle) * sprocketmult) 
		except:
			e = sys.exc_info()
			print "Error during index.GET(): " + str(e)
			#autosmoker.writeToLog("Error during index.GET(): " + str(e))
			#	raise	
		return render.infopage(self.rendertime, self.smoketimestr, self.meattempstr, self.smokertempstr, self.manmodestr, self.servoangle, self.doorangle, self.targetmeat, self.targetsmoker)
	
    # POST is called when a web form is submitted
	def POST(self):
		raise web.seeother('/')
		#return render.index(form, "Autosmoker Web UI")	


class emailsettings:
	form = getEmailForm()
	
	def GET(self):
		self.form = getEmailForm()
		return render.emailsettings(self.form, "Email Settings")
	def POST(self):
		form = email_form(web.input())
		if form.validates():
			if form.btn.value == 'enter':
				newEmailSettings = smtpInfo.smtpInfo(form[server_prompt].value, int(form[port_prompt].value), form[username_prompt].value, form[password_prompt].value)
				smtpInfo.writeSmtpInfo(newEmailSettings)
			raise web.seeother('/')		

if __name__ == '__main__':
	app.run()
	
#Uncomment to turn off debug:	
#web.config.debug = False
	