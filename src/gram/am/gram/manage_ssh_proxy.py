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

import subprocess
import config
import string


portTableFile = '/tmp/gram-ssh-port-table.txt'
sshProxyExe = '/usr/bin/gram_ssh_proxy'

def _execCommand(cmd_string) :
    config.logger.info('Issuing command %s' % cmd_string)
    command = cmd_string.split()
    return subprocess.check_output(command) 


def _getPortFromTable(addr) :
	"""
	1) Open port file
	2) Iterate through entries
	3) Find matching address
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
	portNumber = 0
	for portLine in portLines :
		# Entries are of the format { address \t port }
		tokens = string.split(portLine)
		if len(tokens) > 1 :
			# Compare the port number to the current port counter
			# If the port is available then stop the search, otherwise go to the next port
			if addr == tokens[0] :
				return int(tokens[1])

	config.logger.error("Unable to find the address %s in port table file %s" % (addr % portTableFile))
	return 0


def _addNewProxy(addr) :
    """
    Access the GRAM SSH proxy daemon and create a new proxy with the given address
    """

    cmd_string = '%s ' % sshProxyExe
    cmd_string = cmd_string + '-m C -a %s ' % addr

    try :
        _execCommand(cmd_string)
    except :
        congig.logger.error("Unable to create SSH proxy for address  %s" % addr)
        return 0

    return _getPortFromTable(addr)


def _removeProxy(addr) :
    """
    Access the GRAM SSH proxy daemon and delete the with the given address
    """

    cmd_string = '%s ' % sshProxyExe
    cmd_string = cmd_string + '-m D -a %s ' % addr

    try:
        _execCommand(cmd_string)
    except :
        congig.logger.error("Address %s not present in SSH proxy" % addr)
