#!/usr/bin/env python
import os, sys
import BaseHTTPServer
import traceback

next_step = None

class Give404:
	def __init__(self, path):
		self.path = path

	def __str__(self):
		return self.path

	def __repr__(self):
		return "404 on " + self.path

class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	def do_GET(self):
		leaf = os.path.basename(self.path)

		acceptable = dict([(str(x), x) for x in next_step])

		resp = acceptable.get(self.path, None) or \
		       acceptable.get(leaf, None) or \
		       acceptable.get('*', None)

		if not resp:
			self.send_error(404, "Expected %s; got %s" % (next_step, self.path))
			
		if os.path.exists(leaf) and not isinstance(resp, Give404):
			self.send_response(200)
			self.end_headers()
			self.wfile.write(file(leaf).read())
			self.wfile.close()
		else:
			self.send_error(404, "Missing: %s" % leaf)

def handle_requests(*script):
	server_address = ('localhost', 8000)
	httpd = BaseHTTPServer.HTTPServer(server_address, MyHandler)
	child = os.fork()
	if child:
		return child
	# We are the child
	try:
		sys.stderr = sys.stdout
		print "Waiting for request"
		global next_step
		for next_step in script:
			if type(next_step) != tuple: next_step = (next_step,)
			for x in next_step:
				httpd.handle_request()
		print "Done"
		os._exit(0)
	except:
		traceback.print_exc()
		os._exit(1)
