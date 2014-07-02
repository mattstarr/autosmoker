#helpful info/example at: http://www.themagpi.com/issue/issue-9/article/the-python-pit-drive-your-raspberry-pi-with-a-mobile-phone/

#much from: http://webpy.org/docs/0.3/tutorial

#imports 
import web
from web import form

urls = ('/', 'index')
render = web.template.render('templates/')


class index:
	def GET(self):
		



























if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()