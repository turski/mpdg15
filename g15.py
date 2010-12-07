#coding=utf-8
import time, re, socket
from mpd import *
from bitarray import *
import smallfont

class G15(object):
	def __init__(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.keys = bitarray('0000000000')
		self.cmdbuf = bitarray(1504 *[False])

	def get_keys(self):
		try:
			buf = self.sock.recv(1024)
			a = bitarray(endian='little')
			a.fromstring(buf)
			self.keys = a[18:28]
		except socket.timeout:
			return None
		return self.keys

	def send(self, strbuf):
		strbuf += self.cmdbuf.tostring()
		self.sock.send(strbuf)

	def set_timeout(self, timeout):
		self.sock.settimeout(float(timeout))

	def connect(self, host, port):
		self.sock.connect((host, port))
		if self.sock.recv(16) != 'G15 daemon HELLO':
			exit()
		self.sock.send('RBUF')

	def disconnect(self):
		self.sock.close()


class G15Canvas(object):
	def __init__(self, daemon):
		self.daemon = daemon
		self.buf = None
		self.height = 43
		self.width = 160
		self.buf = [ bitarray(self.width * [False]) for x in range(self.height) ]
		self.clear()

	def blit(self, buf, mask):
		if mask != None:
			for i in xrange(43):
				self.buf[i] &= ~mask[i]
		if buf != None:
			for i in xrange(43):
				self.buf[i] |= buf[i]

	def clear(self):
		for row in self.buf:
			row.setall(False)

	def draw(self, *args):
		buf = ""
		for row in self.buf:
			buf += row.tostring()
		self.daemon.send(buf)


class G15Font(object):
	def __init__(self, font):
		self.font = font.font
		self.height = font.height
		self.width = font.width

	def draw_text(self, text):
		buf = [ bitarray() for x in range(self.height) ]
		for char in text:
			for i, row in enumerate(self.font.get(char, self.font[' '])):
				buf[i].extend(row)
		return buf


class G15Object(object):
	def __init__(self, canvas=None, draw_area=None, mask=None, img=None, align='l'):
		self.redraw = False
		self.canvas = canvas
		if draw_area != None:
			self.set_draw_area(draw_area)
			if mask != None:
				self.mask = mask
		else:
			self.mask = mask
		if isinstance(img, list):
			self.img = img
		elif isinstance(img, str):
			self.pbm2img(img)
		else:
			self.img = None
		self.set_align(align)
		self.buf = empty_img()
		self.old_offs = None

	def pbm2img(self, path):
		self.img = self._conv_pbm(path)
		self.redraw = True

	def pbm2mask(self, path):
		self.mask = self._conv_pbm(path)
		self.redraw = True

	def buf2img(self, buf):
		self.img = buf
		self.redraw = True

	def _conv_pbm(self, path):
		pbm = open(path, 'rb').read()
		pat = re.compile("^(?P<format>\w+)\n(?P<comment>#.*)\n(?P<width>\d+) (?P<height>\d+)\n(?P<data>.*)")
		result = pat.match(pbm)
		format = result.group('format')
		if format != 'P4':
			print('FormatError')
			exit(1)
		width = int(result.group('width'))
		height = int(result.group('height'))
		rowlen = width/8
		if width%8 > 0:
			rowlen += 1
		data = result.group('data')
		buf = []
		for i in xrange(height):
			x0 = i*rowlen
			x1 = (i+1)*rowlen
			line = data[x0:x1]
			row = bitarray()
			row.fromstring(line)
			buf.append(row[:width])
		return buf

	def set_align(self, align):
		draw_funcs = {'l': self._ldraw, 'r': self._rdraw, 'c': self._cdraw}
		self.align = align
		self._draw = draw_funcs[align]
		self.redraw = True

	def set_canvas(self, canvas):
		self.canvas = canvas
		self.redraw = True

	def set_draw_area(self, xy):
		self.draw_area = xy
		self.mask = self.create_mask(xy)
		self.redraw = True

	def create_mask(self, xy):
		x0, y0, x1, y1 = xy
		mask = empty_img()
		for y in range(y0, y1):
			mask[y][x0:x1] = True
		return mask

	def _ldraw(self, offs=(0,0)):
		ofs_x, ofs_y = offs
		x0 = self.draw_area[0]
		y0 = self.draw_area[1]
		ofs_x += x0
		ofs_y += y0
		buf = empty_img()
		for i, line in enumerate(self.img):
			linebuf = line.copy()
			if ofs_x == 0:
				pass
			elif ofs_x < 0:
				del linebuf[:abs(ofs_x)]
			else:
				linebuf[:0] = bitarray(ofs_x * [False])
			l = linebuf.length()
			if l == 160:
				pass
			elif l < 160:
				linebuf.extend((160-l)*[False])
			else:
				del(linebuf[160:])
			y = ofs_y + i
			linebuf &= self.mask[y]
			buf[y] = linebuf
		self.buf = buf
		self.redraw = False

	def _rdraw(self, offs=(0,0)):
		ofs_x, ofs_y = offs
		x0 = self.draw_area[2]
		y0 = self.draw_area[1]
		ofs_x += x0
		ofs_y += y0
		buf = empty_img()
		for i, line in enumerate(self.img):
			linebuf = line.copy()
			l = linebuf.length()
			if l == ofs_x:
				pass
			elif l < ofs_x:
				dl = ofs_x - l
				a = bitarray(dl)
				a.setall(False)
				linebuf = a + linebuf
			elif l > ofs_x:
				dl = l - ofs_x
				del linebuf[:dl]
			l = linebuf.length()
			if l == 160:
				pass
			elif l > 160:
				del linebuf[160:]
			elif l < 160:
				dl = 160 - l
				a = bitarray(dl)
				a.setall(False)
				linebuf += a
			y = ofs_y + i
			linebuf &= self.mask[y]
			buf[y] = linebuf
		self.buf = buf
		self.redraw = False

	def _cdraw(self, offs=(0,0)):
		ofs_x, ofs_y = offs
		x1 = (self.draw_area[0] + self.draw_area[2])/2
		y1 = self.draw_area[1]
		x1 += ofs_x
		y1 += ofs_y
		buf = empty_img()
		for i, line in enumerate(self.img):
			linebuf = line.copy()
			l = linebuf.length()
			x0 = x1 - (l/2)
			if x0 == 0:
				pass
			elif x0 < 0:
				del linebuf[:abs(x0)]
			elif x0 > 0:
				a = bitarray(x0)
				a.setall(False)
				linebuf = a + linebuf
			l = linebuf.length()
			if l == 160:
				pass
			elif l > 160:
				del linebuf[160:]
			elif l < 160:
				dl = 160 - l
				a = bitarray(dl)
				a.setall(False)
				linebuf += a
			y = y1 + i
			linebuf &= self.mask[y]
			buf[y] = linebuf
		self.buf = buf
		self.redraw = False

	def draw(self, offs=(0,0)):
		if offs != self.old_offs:
			self.redraw = True
			self.old_offs = offs
		if self.redraw == True:
			self._draw()
		self.canvas.blit(self.buf, self.mask)

	def wipe(self):
		self.canvas.blit(None, self.mask)

height = 43
width = 160
_empty_img = [ bitarray(width * [False]) for x in xrange(height) ]
empty_img = lambda: [ line.copy() for line in _empty_img ]