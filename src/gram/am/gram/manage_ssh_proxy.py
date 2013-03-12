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

import open_stack_interface
import config
import string
import struct
import fcntl


def _acquireReadLock() :
        lockFile = None
	try:
            lockFile = open(config.port_table_lock_file, 'r')
	except IOError:
            config.logger.error("Unable to open file %s" % config.port_table_lock_file)
            return None

        lockdata = struct.pack('hhllhh', fcntl.F_RDLCK, 0, 0, 0, 0, 0)
        try :
            fcntl.fcntl(lockFile.fileno(), fcntl.F_SETLKW, lockdata)
        except :
            config.logger.error("Unable to lock file %s" % config.port_table_lock_file)
            return None

        return lockFile


def _releaseLock(lockFile) :
        lockdata = struct.pack('hhllhh', fcntl.F_UNLCK, 0, 0, 0, 0, 0)
        try :
            fcntl.fcntl(lockFile.fileno(), fcntl.F_SETLK, lockdata)
        except :
            config.logger.error("Unable to release lock file %s" % config.port_table_lock_file)
            return None

        lockFile.close()
    

def _getPortFromTable(addr) :
	"""
	1) Open port file
	2) Iterate through entries
	3) Find matching address
	"""
        # Acquire file lock on SSH port table
        filelock = _acquireReadLock()
        if filelock == None :
            return 0

        # Attempt to open the port table file for reading
        portLines = []
        try:
            scriptFile = open(config.port_table_file, 'r')
            portLines = scriptFile.readlines()
            scriptFile.close()
	except IOError:
            config.logger.error("Unable to open file %s for reading" % config.port_table_file)
            return 0

        # Release the SSH port table file lock
        _releaseLock(filelock)

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

	config.logger.error("Unable to find the address %s in port table file %s" % (addr % config.port_table_file))
	return 0


def _addNewProxy(addr) :
    """
    Access the GRAM SSH proxy daemon and create a new proxy with the given address
    """

    cmd_string = '%s ' % config.ssh_proxy_exe
    cmd_string = cmd_string + '-m C -a %s ' % addr

    try :
        open_stack_interface._execCommand(cmd_string)
    except :
        config.logger.error("Unable to create SSH proxy for address  %s" % addr)
        return 0

    return _getPortFromTable(addr)


def _removeProxy(addr) :
    """
    Access the GRAM SSH proxy daemon and delete the with the given address
    """

    cmd_string = '%s ' % config.ssh_proxy_exe
    cmd_string = cmd_string + '-m D -a %s ' % addr

    try:
        open_stack_interface._execCommand(cmd_string)
    except :
        config.logger.error("Address %s not present in SSH proxy" % addr)
