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
import os

def _acquireReadLock() :
        lockFile = None
	try:
            lockFile = open(config.port_table_lock_file, 'r')
	except IOError:
            config.logger.error("Unable to open file %s for reading" % config.port_table_lock_file)
            return None

        lockdata = struct.pack('hhllhh', fcntl.F_RDLCK, 0, 0, 0, 0, 0)
        try :
            fcntl.fcntl(lockFile.fileno(), fcntl.F_SETLKW, lockdata)
        except :
            lockFile.close()
            config.logger.error("Unable to lock file %s for reading" % config.port_table_lock_file)
            return None

        return lockFile


def _acquireWriteLock() :
        lockFile = None
	try:
            lockFile = open(config.port_table_lock_file, 'w')
	except IOError:
            config.logger.error("Unable to open file %s for writing" % config.port_table_lock_file)
            return None

        lockdata = struct.pack('hhllhh', fcntl.F_WRLCK, 0, 0, 0, 0, 0)
        try :
            fcntl.fcntl(lockFile.fileno(), fcntl.F_SETLKW, lockdata)
        except :
            lockFile.close()
            config.logger.error("Unable to lock file %s for writing" % config.port_table_lock_file)
            return None

        return lockFile


def _releaseLock(lockFile) :
        lockdata = struct.pack('hhllhh', fcntl.F_UNLCK, 0, 0, 0, 0, 0)
        try :
            fcntl.fcntl(lockFile.fileno(), fcntl.F_SETLK, lockdata)
        except :
            config.logger.error("Unable to release lock file %s" % config.port_table_lock_file)

        lockFile.close()
    

def _getPortFromTable(addr, delete) :
	"""
	1) Open port file
	2) Iterate through entries
	3) Find matching address
	"""
        # Acquire file lock on SSH port table
        lockfile = _acquireReadLock()
        if lockfile == None :
            return 0

        # Attempt to open the port table file for reading
        portLines = []
        try :
            scriptFile = open(config.port_table_file, 'r')
            portLines = scriptFile.readlines()
            scriptFile.close()
        except :
            _releaseLock(lockfile)
            config.logger.error("Unable to open file %s for reading" % config.port_table_file)
            return 0

        # Release the SSH port table file lock
        _releaseLock(lockfile)

        # If port table exists than iterate through sorted entries and find an available port
	portNumber = 0
        index = 0
        table_index = -1
	for portLine in portLines :
		# Entries are of the format { address \t port }
		tokens = string.split(portLine)
		if len(tokens) > 1 :
			# Compare the port number to the current port counter
			# If the port is available then stop the search, otherwise go to the next port
			if addr == tokens[0] :
				portNumber = int(tokens[1])
                                table_index = index
                index += 1

        # Now delete the line in the port file if necessary
        if delete and table_index >= 0 :
            lockfile = _acquireWriteLock()
	    if lockfile == None :
                return portNumber

            try :
                scriptFile = open(config.port_table_file, 'w')
            except :
                _releaseLock(lockfile)
                config.logger.error("Unable to open file %s for reading" % config.port_table_file)
                return portNumber

            # Write the contents of the port table
            index = 0
            for portLine in portLines :
                if index != table_index :
                    scriptFile.write(portLine)
                index += 1

            # Release the file lock and close the file
            scriptFile.close()
            _releaseLock(lockfile)

	return portNumber


def _updatePortTable(addr) :
    # Attempt to open the port table file for reading
    portLines = []
    scriptFile = None
    table_exists = False
    if os.path.isfile(config.port_table_file) :
        # Acquire file lock on SSH port table
        table_exists = True
        lockfile = _acquireReadLock()
        if lockfile == None :
            return 0

        # Attempt to open the port table file for reading
        try :
            scriptFile = open(config.port_table_file, 'r')
            portLines = scriptFile.readlines()
            scriptFile.close()
        except :
            _releaseLock(lockfile)
            config.logger.error("Unable to open file %s for reading" % config.port_table_file)
            return 0

        # Release the SSH port table file lock
        _releaseLock(lockfile)

    # Iterate through the port table
    duplicate = False
    index = 0
    portCounter = config.ssh_proxy_start_port
    portStr = '%d' % portCounter
    insert_index = -1
    for portLine in portLines :
	# Entries are of the format { address \t port }
	tokens = string.split(portLine)
	if len(tokens) > 1 :
            # Compare the port number to the current port counter
	    # If the port is available then stop the search, otherwise go to the next port
            portNumber = int(tokens[1])
	    if addr == tokens[0] :
                duplicate = True
            elif insert_index < 0 :
                if portCounter == portNumber :
                    portCounter += 1
		    portStr = '%d' % portCounter
		else :
                    insert_index = index

        # Increment the table entry index
        index += 1

    # Exit early if a duplicate entry is found
    if duplicate :
        config.logger.error("Duplicate address %s in port table file" % addr)
        return 0

    # Exit early if the port table has reached its maximum number of ports
    if config.ssh_proxy_end_port - config.ssh_proxy_start_port + 1 <= insert_index :
        config.logger.error("Maximum ports reached in SSH proxy port table")
        return 0

    # Insert a new line into the port table
    tab_char = '\t'
    newEntry = '%s%s%s%s' % (addr, '\t', portStr, '\n')
    if insert_index < 0 :
        portLines.append(newEntry)
    else :
        portLines.insert(insert_index, newEntry)

    # Ensure proper file permissions if this the port table is getting created
    if not table_exists :
        open(config.port_table_lock_file, 'w').close()
        os.chmod(config.port_table_lock_file, 0666)
        open(config.port_table_file, 'w').close()
        os.chmod(config.port_table_file, 0666)

    # Acquire a write lock on the port table file
    lockfile = _acquireWriteLock()
    if lockfile == None :
        return 0

    try :
        scriptFile = open(config.port_table_file, 'w')
    except :
        _releaseLock(lockfile)
        config.logger.error("Unable to open file %s for writing" % config.port_table_file)
        return 0

    # Write the contents of the port table
    for portLine in portLines :
        scriptFile.write(portLine)

    scriptFile.close()

    # Release the file lock and close the file
    _releaseLock(lockfile)

    # All good- return the assigned port number
    return portCounter


def _addNewProxy(addr) :
    """
    Access the GRAM SSH proxy daemon and create a new proxy with the given address
    """
    portNumber = _updatePortTable(addr)
    if portNumber == 0 :
        return 0

    cmd_string = '%s ' % config.ssh_proxy_exe
    cmd_string = cmd_string + '-m C -a %s ' % addr
    cmd_string = cmd_string + ' -p %d ' % portNumber
    cmd_string = cmd_string + ' -n %s ' % open_stack_interface._getConfigParam('/etc/gram/config.json','mgmt_ns')

    config.logger.info("Setting up ssh proxy: " + cmd_string)


    try :
        open_stack_interface._execCommand(cmd_string)
    except :
        config.logger.error("Unable to create SSH proxy for address  %s" % addr)
        return 0

    return portNumber


def _removeProxy(addr) :
    """
    Access the GRAM SSH proxy daemon and delete the with the given address
    """

    portNumber = _getPortFromTable(addr, True)
    if portNumber > 0 :
        cmd_string = '%s ' % config.ssh_proxy_exe
        cmd_string = cmd_string + '-m D -a %s ' % addr
        cmd_string = cmd_string + ' -p %d ' % portNumber
        cmd_string = cmd_string + ' -n %s ' % open_stack_interface._getConfigParam('/etc/gram/config.json','mgmt_ns')

        try:
            open_stack_interface._execCommand(cmd_string)
        except :
            config.logger.error("Address %s not present in SSH proxy" % addr)
