#----------------------------------------------------------------------
# Copyright (c) 2013 Raytheon BBN Technologies
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and/or hardware specification (the "Work") to
# deal in the Work without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Work, and to permit persons to whom the Work
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Work.
#
# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
# IN THE WORK.
#----------------------------------------------------------------------

import sys
import os
import time
import atexit
import stat
import string
import signal

"""
    NOTE: This module uses the nova rootwrap utility to execute the iptable commands
    with proper privelidges.
"""

class GramSSHProxyDaemon:
	"""
	The GramSSHProxyDaemon class creates and destroys SSH proxies within the GENI GRAM environment
	implemented via the iptables; The intent is that this daemon is executed with root priviledges
	otherwise the iptables requests will fail due to improper athentication
	"""
	portTableFile = "/tmp/gram-ssh-port-table.txt"
	rootwrapConfFile = "/etc/gram/rootwrap.conf"
	startPortNumber = 3000

	def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
		self.stdin = stdin
		self.stdout = stdout
		self.stderr = stderr
		self.pidfile = pidfile
		self.adding = False
		self.removing = False


	def delpid(self):
		os.remove(self.pidfile)


	def daemonize(self):
		"""
		do the UNIX double-fork magic, see Stevens' "Advanced 
		Programming in the UNIX Environment" for details
		http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
		"""
		try: 
			pid = os.fork() 
			if pid > 0:
				# exit first parent
				sys.exit(0) 
		except OSError, e: 
			sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
			sys.exit(1)
	
		# decouple from parent environment
		os.chdir("/") 
		os.setsid() 
		os.umask(0) 
	
		# do second fork
		try: 
			pid = os.fork() 
			if pid > 0:
				# exit from second parent
				sys.exit(0) 
		except OSError, e: 
			sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
			sys.exit(1) 
	
		# redirect standard file descriptors
		sys.stdout.flush()
		sys.stderr.flush()
		si = file(self.stdin, 'r')
		so = file(self.stdout, 'a+')
		se = file(self.stderr, 'a+', 0)
		os.dup2(si.fileno(), sys.stdin.fileno())
		os.dup2(so.fileno(), sys.stdout.fileno())
		os.dup2(se.fileno(), sys.stderr.fileno())
	
		# write pidfile
		atexit.register(self.delpid)
		pid = str(os.getpid())
		file(self.pidfile,'w+').write("%s\n" % pid)
	

	def start(self):
		"""
		Start the daemon
		"""
		# Check for a pidfile to see if the daemon already runs
		try:
			pf = file(self.pidfile,'r')
			pid = int(pf.read().strip())
			pf.close()
		except IOError:
			pid = None
	
		if pid:
			message = "pidfile %s already exist. Daemon already running?\n"
			sys.stderr.write(message % self.pidfile)
			sys.exit(1)
		
		# Start the daemon
		self.daemonize()
		
		#message = "Starting GRAM SSH daemon with pid %s\n"
		#print(message % self.pid)

		self.run()


	def stop(self):
		"""
		Stop the daemon
		"""
		# Get the pid from the pidfile
		try:
			pf = file(self.pidfile,'r')
			pid = int(pf.read().strip())
			pf.close()
		except IOError:
			pid = None
	
		if not pid:
			message = "pidfile %s does not exist. Daemon not running?\n"
			sys.stderr.write(message % self.pidfile)
			return # not an error in a restart

		# Try killing the daemon process	
		try:
			while 1:
				os.kill(pid, signal.SIGTERM)
				time.sleep(0.1)
		except OSError, err:
			err = str(err)
			if err.find("No such process") > 0:
				if os.path.exists(self.pidfile):
					os.remove(self.pidfile)
			else:
				print str(err)
				sys.exit(1)

		#message = "Stopping GRAM SSH daemon with pid %s\n"
		#sys.stout.write(message % self.pid)


	def restart(self):
		"""
		Restart the daemon
		"""
		self.stop()
		self.start()


	def is_running(self):
		# Get the pid from the pidfile
		try:
			pf = file(self.pidfile,'r')
			pid = int(pf.read().strip())
			pf.close()
		except IOError:
			return False
	
		return True


	def add_proxy_cmd(self, addr, portNumber) :
		"""
		Initiate iptables calls to set up SSH proxy
		"""

		# Translate the destination address of packets incoming on the designated port
		#cmd = 'nova-rootwrap %s ' % self.rootwrapConfFile
		cmd = '/sbin/iptables -t nat -I PREROUTING -p tcp --dport %d ' % portNumber
		cmd = cmd + '-j DNAT --to-destination %s:22 ' % addr
		os.system(cmd)

		# Set the host to forward packets from the given VM address
		#cmd = 'nova-rootwrap %s ' % self.rootwrapConfFile
		cmd = '/sbin/iptables -I FORWARD -p tcp -s %s -j ACCEPT ' % addr
		os.system(cmd)

		# Masquerade the source address of outgoing packets originally from the given VM address
		#cmd = 'nova-rootwrap %s ' % self.rootwrapConfFile
		cmd = '/sbin/iptables -t nat -I POSTROUTING -p tcp -s %s -j MASQUERADE ' % addr
		os.system(cmd)


	def delete_proxy_cmd(self, addr, portNumber) :
		"""
		Issue iptables commands to remove SSH proxy
		"""

		# Remove the PREROUTING entry
		#cmd = 'nova-rootwrap %s ' % self.rootwrapConfFile
		cmd = '/sbin/iptables -t nat -D PREROUTING -p tcp --dport %d ' % portNumber 
		cmd = cmd + '-j DNAT --to-destination %s:22 ' % addr
		os.system(cmd)

		# Remove the FORWARD entry
		#cmd = 'nova-rootwrap %s ' % self.rootwrapConfFile
		cmd = '/sbin/iptables -D FORWARD -p tcp -s %s -j ACCEPT ' % addr
		os.system(cmd)

		# Remove the POSTROUTING entry
		#cmd = 'nova-rootwrap %s ' % self.rootwrapConfFile
		cmd = '/sbin/iptables -t nat -D POSTROUTING -p tcp -s %s -j MASQUERADE ' % addr
		os.system(cmd)


	def add_proxy(self) :
		# First read port address table and find first disabled entry
		# Open the port table for reading
		portLines = []
		try:
			scriptFile = open(self.portTableFile, 'r')
			portLines = scriptFile.readlines()
			scriptFile.close()
		except IOError:
			return

		# Open the port table for writing
		try:
			writeFile = open(portTableFile, 'w')
		except IOError:
			#config.logger.error("Unable to open file %s for writing" % self.portTableFile)
			return

		# Iterate through the table entries and search for the given address
		portNumber = 0
		addr = ""
		for portLine in portLines :
			# Entries are of the format { address \t port \t enable-flag }
			# Find the enabled-flag field of the entries
			# If they are disabled (0), then rewrite the entry with the enable-flag on (1)
			# Otherwise re-write the entry to the port table as is
			tokens = string.split(portLine)
			if len(tokens) > 2 :
				if tokens[2] == "0" and portNumber == 0 :
					portNumber = int(tokens[1])
					addr = tokens[0]
					newLine = '%s\t' % addr
					newLine = newLine + '%d\t1\n' % portNumber
					writeFile.write(newLine)
				else :
					writeFile.write(portLine)

		# Close the writing file
		writeFile.close()
		
		# Return early if no newly enabled port address found
		if portNumber == 0 :
			return

		# Finally initiate the iptables commands
		self.add_proxy_cmd(addr, portNumber)


	def remove_proxy(self) :
		# First read port address table and find first disabled entry
		# Open the port table for reading
		portLines = []
		try:
			scriptFile = open(self.portTableFile, 'r')
			portLines = scriptFile.readlines()
			scriptFile.close()
		except IOError:
			return

		# Open the port table for writing
		try:
			writeFile = open(portTableFile, 'w')
		except IOError:
			#config.logger.error("Unable to open file %s for writing" % self.portTableFile)
			return

		# Iterate through the table entries and search for the given address
		portNumber = 0
		addr = ""
		for portLine in portLines :
			# Entries are of the format { address \t port \t enable-flag }
			# Find the enabled-flag field of the entries
			# If the flas is set to delete (2), then do not write the entry to the table file
			# Otherwise re-write the entry to the port table as is
			tokens = string.split(portLine)
			if len(tokens) > 2 :
				if tokens[2] == "2" and portNumber == 0 :
					portNumber = int(tokens[1])
					addr = tokens[0]
				else :
					writeFile.write(portLine)

		# Close the writing file
		writeFile.close()
		
		# Return early if no delete port address found
		if portNumber == 0 :
			return

		# Finally reissue the iptables commands
		self.delete_proxy_cmd(addr, portNumber)


	def receive_add_signal(self, signum, frame) :
		self.adding = True


	def receive_remove_signal(self, signum, frame) :
		self.removing = True


	def run(self):
		"""
		Busy wait loop
		"""
#		signal.signal(signal.SIGUSR1, self.receive_add_signal)
#		signal.signal(signal.SIGUSR2, self.receive_remove_signal)

		while True :
			if self.adding :
				self.adding = False
				self.add_proxy()

			if self.removing :
				self.removing = False
				self.remove_proxy()

			time.sleep(1)


