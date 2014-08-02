import json

filename = "smtpinfo.cfg"

class smtpInfo:
	#smtp_server = ""
	#smtp_port = 587
	#smtp_username = ""
	#smtp_password = ""
	
	def __init__(self, server, port, username, password):
	#def setInfo(self, server, port, username, password):
		self.smtp_server = server
		self.smtp_port = int(port)
		self.smtp_username = username
		self.smtp_password = password
		
def readSmtpInfo():
	injson = ""
	try:
		with open(filename, 'r') as infile:
			indata = infile.read()
		injson = json.loads(indata)
	except:
		print "noooooooooooooooope!"
	if ("server" in injson) and ("port" in injson) and ("username" in injson) and ("password" in injson):
		newSmtpInfo = smtpInfo(injson.get('server'), injson.get('port'), injson.get('username'), injson.get('password'))
		return newSmtpInfo
	else:
		print "No file or incorrect JSON information!"
		return smtpInfo("", 587, "", "")
		
def writeSmtpInfo(smtpInfoIn):
	data = {"server":smtpInfoIn.smtp_server,
		"port":str(smtpInfoIn.smtp_port),
		"username":smtpInfoIn.smtp_username,
		"password":smtpInfoIn.smtp_password}
	outdata = json.dumps(data)
	with open(filename, 'w') as outfile:
		outfile.write(outdata)