#helpful info/example at: http://www.themagpi.com/issue/issue-9/article/the-python-pit-drive-your-raspberry-pi-with-a-mobile-phone/
#smtp code from: http://www.pythonforbeginners.com/code-snippets-source-code/using-python-to-send-email

#imports
import web
from web import form
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
print "importing autosmoker"
import autosmoker
print "import done"
##############################################
#Email settings (outgoing)
email_smtp_address = 'smtp.ipage.com'
email_smtp_port = 587
email_login_name = 
email_password = 
emailserver = smtplib.SMTP(email_smtp_address, email_smtp_port)

urls = ('/', 'index')
render = web.template.render('templates/')

app = web.application(urls, globals())

meat_prompt = 'Target Meat Temp (F):'
smoker_prompt = 'Target Smoker Temp (F):'
filename_prompt = 'Output Filename:' 

main_form = form.Form(
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
#email_list = []
email_list = ""
mailserverquit = False #use to keep track if we have already logged in and out (if so, need to connect differently next time!)

class index:
		
	def GET(self):
		form = main_form()
		return render.index(form, "Autosmoker Web UI")
		
    # POST is called when a web form is submitted
	def POST(self):
		global email_list
		global mailserverquit
		#figure out form validation and put here later(?)
		form = main_form(web.input())
		if form.validates():
			if form.btn.value == 'set':
				#parse comma separated email/text addresses:
				email_list = str(form['Send to:'].value).split(",")
				#email_list = str(form['Send to:'].value)
				print email_list
			elif form.btn.value == 'test':
				if len(email_list) > 0: 
					fromaddr = email_login_name
					msg = MIMEMultipart()
					msg['Subject'] = 'test email'
					msg['From'] = fromaddr
					COMMASPACE = ', '
					msg['To'] = COMMASPACE.join(email_list)
					body = "If you can read this, that's pretty sweet."
					msg.attach(MIMEText(body, 'plain'))
					if (mailserverquit): #reconnect if we are sending an email after the first
						emailserver.connect(email_smtp_address, email_smtp_port)
					emailserver.ehlo()
					emailserver.starttls()
					emailserver.ehlo()
					emailserver.set_debuglevel(True)
					emailserver.login(email_login_name, email_password)
					emailserver.sendmail(fromaddr, email_list, msg.as_string())
					emailserver.quit()
					mailserverquit = True #need to reconnect later if we want to send more mail
				else:
					print "Error: empty email list" #TODO: make client-viewable later
				print len(email_list)
				print str(email_list)
			elif form.btn.value == 'start':
				#get the smoker and file rolling!!!
				target_meat_temp = int(form[meat_prompt].value)
				target_smoker_temp = int(form[smoker_prompt].value)
				output_filename = str(form[filename_prompt].value)
				run_smoker = True
				#start stuff!
				autosmoker.smokeData.setFilename(output_filename)
				autosmoker.smokeData.setRecording(True)
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
	