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
import stat
import os
import config
import signal
import string

sshProxyPIDFile = '/tmp/gram-ssh-proxy.pid'
portTableFile = '/tmp/gram-ssh-port-table.txt'
startPortNumber = 3000

def _addPortTable(addr) :
	"""
	1) Open port address file
	2) Iterate through entries
	3) Find avilable port
	4) Add new entry to file and close file
	5) Return new port number 
	"""
	# First attempt to open the port table file for reading
	fileExists = True
	portLines = []
	try:
		scriptFile = open(portTableFile, 'r')
		portLines = scriptFile.readlines()
		scriptFile.close()
	except IOError:
		fileExists = False

	portNumber = startPortNumber
	if fileExists :
		# If port table exists than iterate through sorted entries and find an available port
		index = 0
		for portLine in portLines :
			# Entries are of the format { address \t port }
			tokens = string.split(portLine)
			if len(tokens) > 2 :
				# Compare the port number to the current port counter
				# If the port is available then stop the search, otherwise go to the next port
				latestPort = int(tokens[1])
				if latestPort == portNumber :
					portNumber = portNumber + 1
					index = index + 1
				else :
					break

		# Create the new entry into the port table
		# Format: addr port enabled-flag
		newLine = '%s\t' % addr
		newLine = newLine + '%d\t0\n' % portNumber

		# The port table is sorted
		# If the port is in the middle or at the beginning of the list, then insert it into the correct position
		# Otherwise append the entry to the end
		if index < len(portLines) :
			portLines.insert(index, newLine)
		else :
			portLines.append(newLine)

		# Open the port table for writing
		try:
			writeFile = open(portTableFile, 'w')
		except IOError:
			config.logger.error("Unable to open file %s for writing" % portTableFile)
			return 0

		# Write all of the address/port entries to file and close the file
		for portLine in portLines :
			writeFile.write(portLine)

		writeFile.close()

	else :
		# Open the port table for writing
		try:
			writeFile = open(portTableFile, 'w')
		except IOError:
			config.logger.error("Unable to open file %s for writing" % portTableFile)
			return 0

		# Write the one and only entry to the file and close the file
		newLine = '%s\t' % addr
		newLine = newLine + '%d\t0\n' % portNumber
		writeFile.write(newLine)
		writeFile.close()

	# Return the selected port number
       	return portNumber


def _removePortTable(addr) :
	"""
	1) Open port file
	2) Iterate through entries
	3) Find matching address
	4) update entry for deleting to file
	5) Close the file and return new port number 
	"""
	# First attempt to open the port table file for reading
	portLines = []
	try:
		scriptFile = open(portTableFile, 'r')
		portLines = scriptFile.readlines()
		scriptFile.close()
	except IOError:
		config.logger.error("Unable to open file %s for reading" % portTableFile)
		return 0

	# If port table exists than iterate through sorted entries and find an available port
	index = 0
	portNumber = 0
	portIndex = 0
	for portLine in portLines :
		# Entries are of the format { address \t port }
		tokens = string.split(portLine)
		if len(tokens) > 2 :
			# Compare the port number to the current port counter
			# If the port is available then stop the search, otherwise go to the next port
			if addr == tokens[0] and tokens[2] != "2" :
				portNumber =int(tokens[1])
				portIndex = index

		index = index + 1

	# Return early if no entry found
	if portNumber == 0 :
		config.logger.error("Unable to find the address %s in port table file %s" % (addr % portTableFile))
		return 0

	# Open the port table for writing
	try:
		writeFile = open(portTableFile, 'w')
	except IOError:
		config.logger.error("Unable to open file %s for writing" % portTableFile)
		return 0

       	# Create the new entry into the port table
	# Format: addr port enabled-flag
	newLine = '%s\t' % addr
	newLine = newLine + '%d\t2\n' % portNumber

	# Write all of the address/port entries to file and close the file
	index = 0
	for portLine in portLines :
		if index == portIndex :
			writeFile.write(newLine)
		else :
			writeFile.write(portLine)

		index = index + 1

	writeFile.close()

	# Return the selected port number
       	return portNumber


def _addNewProxy(addr) :
    """
    Access the GRAM SSH proxy daemon and create a new proxy with the given address
    """
    # Get the pid from the pidfile
    pid = 0
    try:
        pf = file(sshProxyPIDFile, 'r')
        pid = int(pf.read().strip())
        pf.close()
    except IOError:
        config.logger.error("Unable to access SSH Proxy PID file-- is the proxy running?")
        return 0

    # Update the port address table file
    portNumber = _addPortTable(addr)

    if portNumber > 0 :
        message = 'Creating SSH proxy for %s ' % addr
        message = message + 'at port %d... ' % portNumber
        config.logger.info(message)

	# Signal GRAM SSH proxy daemon to create proxy
	os.kill(pid, signal.SIGUSR1)
    else :
        message = 'Error creating SSH proxy for %s ' % addr
        config.logger.info(message)

    return portNumber


def _removeProxy(addr) :
    """
    Access the GRAM SSH proxy daemon and delete the with the given address
    """
    # Get the pid from the pidfile
    pid = 0
    try:
        pf = file(sshProxyPIDFile, 'r')
        pid = int(pf.read().strip())
        pf.close()
    except IOError:
        config.logger.error("Unable to access SSH Proxy PID file-- is the proxy running?")
        return 0

    # Update the port address table file
    portNumber = _removePortTable(addr)

    if portNumber > 0 :
        message = 'Deleting SSH proxy for %s ' % addr
        message = message + 'at port %d... ' % portNumber
        config.logger.info(message)

	# Signal GRAM SSH proxy daemon to delete proxy
	os.kill(pid, signal.SIGUSR2)
    else :
        message = 'Error deleting SSH proxy for %s ' % addr
        config.logger.info(message)

    return portNumber
