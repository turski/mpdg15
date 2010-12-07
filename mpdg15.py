#!/usr/bin/env python2
#coding=utf-8
import time, re, socket
from alsaaudio import Mixer
from mpd import *
from g15 import *
from bitarray import *
import smallfont
import os

workdir = '/home/tarmo/mpd-g15'
pidfile = '/tmp/mpdg15.pid'

class App(object):
	actions = {'main': (None, None, None, (exit, 0))}
	def __init__(self):
		pid = os.getpid()
		with open(pidfile, 'w') as _pidfile:
			_pidfile.write('%s\n'%pid)
		self.mode = 'main'
		self.font = G15Font(smallfont)
		self.init_g15()
		self.init_screen()
		self.init_mpd()

	def close(self):
		self.g15.disconnect()
		del self.g15
		self.mpd.disconnect()
		del self.mpd
		os.remove(pidfile)

	def check_keys(self):
		keys = self.g15.get_keys()
		if keys != None:
			for i in xrange(4):
				if (keys[i] == True) and (self.keys[i] == False):
					self.key_action(i)
			self.keys = keys

	def init_g15(self):
		host = 'localhost'
		port = 15550
		g15 = G15()
		g15.set_timeout(0.2)
		g15.connect(host, port)
		self.keys = bitarray('0000000000')
		self.g15 = g15

	def init_mpd(self):
		host = 'localhost'
		port = 6600
		mpd = MPDClient()
		mpd.connect(host, port)
		self.old_status = {}
		self.old_pos = 0
		self.lastsong = {}
		self.mpd = mpd

	def init_screen(self):
		self.screen = {  'main': G15Canvas(self.g15),
					   'volume': G15Canvas(self.g15) }
		self.old_time = ''
		self.old_vol = 0
		self.obj = {'artist': G15Object(canvas=self.screen['main'], draw_area=(0,0,125,7), align='l'),
					 'album': G15Object(canvas=self.screen['main'], draw_area=(0,7,125,14), align='l'),
					 'title': G15Object(canvas=self.screen['main'], draw_area=(0,14,125,21), align='l'),
				   'playbar': G15Object(canvas=self.screen['main'], draw_area=(0,23,160,31), img="%s/data/playbar.pbm"%workdir),
				  'playicon': G15Object(canvas=self.screen['main'], draw_area=(0,22,9,31)),
						't1': G15Object(canvas=self.screen['main'], draw_area=(0,35,20,43)),
						't2': G15Object(canvas=self.screen['main'], draw_area=(130,35,160,43), align='r'),
					  'time': G15Object(canvas=self.screen['main'], draw_area=(128,0,160,7), align='l'),
					'volume': G15Object(canvas=self.screen['main'], draw_area=(128,7,160,14), align='l') }
		self.screen[self.mode].draw()

	def key_action(self, n):
		act = self.actions[self.mode][n]
		if act != None:
			act[0](act[1])

	def run(self):
		while True:
			self.update_mpd()
			self.check_keys()
		self.close()

	def update_currentsong(self):
		currentsong = self.mpd.currentsong()
		for prop in ('artist', 'album', 'title'):
			string = currentsong.get(prop, ' ').decode('utf-8', 'replace')
			text = self.font.draw_text(string)
			self.obj[prop].buf2img(text)
			self.obj[prop].draw()
		return True

	def update_mpd(self):
		update = False
		try:
			status = self.mpd.status()
		except ConnectionError:
			status = {'state': 'nan'}
		state = status.get('state')
		if state != self.old_status.get('state'):
			update |= self.update_state(state)
		playtime = status.get('time')
		if playtime != self.old_status.get('time'):
			update |= self.update_playtime(playtime)
		if status.get('songid') != self.old_status.get('songid'):
			update |= self.update_currentsong()
		update |= self.update_time()
		update |= self.update_volume()
		if update == True:
			self.screen['main'].draw()
		self.old_status = status

	def update_playtime(self, playtime):
		ret = False
		if playtime:
			t1, t2 = playtime.split(':')
			old_t1, old_t2 = self.old_status.get('time', '0:0').split(':')
			if int(t2):
				pos = 2 + int(float(t1) / float(t2) * 146)
			else:
				pos = 75
			if pos != self.old_pos:
				ret = True
				bar = self.obj['playbar']
				icon = self.obj['playicon']
				icon.wipe()
				bar.draw()
				icon.set_draw_area((pos,22,pos+9,31))
				icon.draw()
			if t1 != old_t1:
				ret |= True
				m, s = divmod(int(t1), 60)
				string = "%s:%s"%(m,str(s).zfill(2))
				text = self.font.draw_text(string)
				self.obj['t1'].buf2img(text)
				self.obj['t1'].draw()
			if t2 != old_t2:
				ret |= True
				m, s = divmod(int(t2), 60)
				string = "%s:%s"%(m,str(s).zfill(2))
				text = self.font.draw_text(string)
				self.obj['t2'].buf2img(text)
				self.obj['t2'].draw()
		return ret

	def update_state(self, state):
		self.obj['playicon'].pbm2img('%s/data/%s.pbm'%(workdir,state))
		self.obj['playicon'].draw()
		return True

	def update_time(self):
		ret = False
		ctime = time.strftime("%H:%M:%S")
		if ctime != self.old_time:
			ret = True
			self.old_time = ctime
			textbuf = self.font.draw_text(ctime)
			self.obj['time'].buf2img(textbuf)
			self.obj['time'].draw()
		return ret

	def update_volume(self):
		ret = False
		vol = Mixer('Master').getvolume()[0]
		if vol != self.old_vol:
			ret = True
			self.old_vol = vol
			obj = self.obj['volume']
			vol_string = 'Vol: %s%%' % (vol)
			textbuf = self.font.draw_text(vol_string)
			obj.buf2img(textbuf)
			obj.draw()
		return ret

def run():
	app = App()
	app.run()

def daemonize():
	import daemon
	with daemon.DaemonContext():
		run()

if __name__ == '__main__':
	#daemonize()
	run()
