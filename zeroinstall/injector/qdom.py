"""A quick DOM implementation.

Python's xml.dom is very slow. The xml.sax module is also slow (as it imports urllib2).
This is our light-weight version.
"""

# Copyright (C) 2006, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from xml.parsers import expat
import sys

class Element(object):
	__slots__ = ['uri', 'name', 'attrs', 'childNodes', 'content']
	def __init__(self, uri, name, attrs):
		self.uri = uri
		self.name = name
		self.attrs = attrs.copy()
		self.childNodes = []
	
	def __str__(self):
		attrs = [n + '=' + self.attrs[n] for n in self.attrs]
		start = '<{%s}%s %s' % (self.uri, self.name, ' '.join(attrs))
		if self.childNodes:
			return start + '>\n'.join(map(str, self.childNodes)) + ('</%s>' % (self.name))
		elif self.content:
			return start + '>' + self.content + ('</%s>' % (self.name))
		else:
			return start + '/>'
	
	def getAttribute(self, name):
		return self.attrs.get(name, None)

class QSAXhandler:
	def __init__(self):
		self.stack = []
	
	def startElementNS(self, fullname, attrs):
		split = fullname.split(' ', 1)
		if len(split) == 2:
			self.stack.append(Element(split[0], split[1], attrs))
		else:
			self.stack.append(Element(None, fullname, attrs))
		self.contents = ''
	
	def characters(self, data):
		self.contents += data
	
	def endElementNS(self, name):
		contents = self.contents.strip()
		self.stack[-1].content = contents
		self.contents = ''
		new = self.stack.pop()
		if self.stack:
			self.stack[-1].childNodes.append(new)
		else:
			self.doc = new

def parse(source):
	handler = QSAXhandler()
	parser = expat.ParserCreate(namespace_separator = ' ')

	parser.StartElementHandler = handler.startElementNS
	parser.EndElementHandler = handler.endElementNS
	parser.CharacterDataHandler = handler.characters

	parser.ParseFile(source)
	return handler.doc