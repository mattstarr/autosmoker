#helpful info/example at: http://www.themagpi.com/issue/issue-9/article/the-python-pit-drive-your-raspberry-pi-with-a-mobile-phone/
#smtp code from: http://www.pythonforbeginners.com/code-snippets-source-code/using-python-to-send-email

#imports
from datetime import datetime #for current time
import time
import web
from web import form
print "importing autosmoker"
import autosmoker
print "import done"

urls = ('/', 'index')
render = web.template.render('templates/')

app = web.application(urls, globals())

meat_prompt = 'Target Meat Temp (F):'
smoker_prompt = 'Target Smoker Temp (F):'
filename_prompt = 'Output Filename:' 

main_form = form.Form(
	form.Button('btn', id="btnRefresh", value="refresh", html="REFRESH"),
	form.Textbox('Send to:', #parse to accept addresses separated by commas!
		id="destEmail",
		value=""),
	#allow custom mx form items later - for now, use account at mattstarr.net!
	form.Button('btn', id="btnSetEmail", value="set", html="Set Email Info"),
	form.Button('btn', id="btnTestEmail", value="test", html="Send Test Email"),
	#previously in separate form
	form.Textbox(filename_prompt, 
		form.notnull, 
		id="txtFileOut", 
		value="smokename.csv"),
	form.Textbox(meat_prompt, 
		form.notnull, 
		form.regexp('\d+', 'Temperature must be a digit!'),
		form.Validator('Must be a number', lambda x: not x or int(x) > 0),
		id="txtTargetMeatTemp",
		value="145"),		
	form.Textbox(smoker_prompt, 
		form.notnull, 
		form.regexp('\d+', 'Temperature must be a digit!'),
		form.Validator('Must be a number', lambda x: not x or int(x) > 0),
		id="txtTargetSmokerTemp",
		value="225"),	
	form.Button('btn', id="btnStart", value="start", html="Start + Record")
)

#set up some variables...
email_set = False

class index:
		
	def GET(self):
		rendertime = str(datetime.now())
		smoketimestr = ""
		if (autosmoker.smokeinfo.elapsedTime == 0):
			smoketimestr = "Smoke has not been started."
		else:
			smoketimestr = "Elapsed smoke time: %1.2f hours." % (float(autosmoker.smokeinfo.elapsedTime) / 3600.0) 
		meattemp = "{:.2f}".format(autosmoker.mySmoker.meatTempF())
		smokertemp = "{:.2f}".format(autosmoker.mySmoker.smokerTempF())
		manmode = ""
		if (autosmoker.mySmoker.manualServoMode == True):
			manmode = "Manual mode engaged."
		else:
			manmode = "Automatic mode engaged."
		servoangle = autosmoker.mySmoker.servoAngle
		doorangle = "{:.2f}".format(float(servoangle) * 0.625) #.625 is ratio of sprockets (10:16)
		
		form = main_form()
		return render.index(form, "Autosmoker Web UI", rendertime, smoketimestr, meattemp, smokertemp, manmode, servoangle, doorangle)
		
    # POST is called when a web form is submitted
	def POST(self):
		#figure out form validation and put here later(?)
		form = main_form(web.input())
		if form.btn.value == 'refresh': #do before validate, since we dont care!
			raise web.seeother('/')
		if form.validates():
			if form.btn.value == 'set':
				#parse comma separated email/text addresses:
				emails = str(form['Send to:'].value).split(",")
				autosmoker.smokeinfo.setEmailList(emails)
				#email_list = str(form['Send to:'].value)
				print autosmoker.smokeinfo.email_list
			elif form.btn.value == 'test':
				autosmoker.smokeinfo.sendTestEmail()
			elif form.btn.value == 'start':
				#get the smoker and file rolling!!!
				target_meat_temp = int(form[meat_prompt].value)
				target_smoker_temp = int(form[smoker_prompt].value)
				output_filename = str(form[filename_prompt].value)
				autosmoker.smokeinfo.setTargets(target_meat_temp, target_smoker_temp, 2) #add thresh input later
				
				run_smoker = True
				#start stuff!
				autosmoker.smokeinfo.setFilename(output_filename)
				autosmoker.smokeinfo.setRecording(True)
				print "setting true"
			else:
				print "What button did you even push?!?!"
			raise web.seeother('/')
		else:
			return render.index(form, "Autosmoker Web UI")
# run
if __name__ == '__main__':
    app.run()
	
#Uncomment to turn off debug:	
#web.config.debug = False
	