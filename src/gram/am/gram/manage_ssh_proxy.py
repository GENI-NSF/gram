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

#import open_stack_interface
#import config
import os

# Table to map current IP addresses to ports
class SSHProxyTable:
	_address_to_port = {}

	@classmethod
	def _get(cls):
		return SSHProxyTable._address_to_port

	@classmethod
	def _restore(cls, address_to_port):
		SSHProxyTable._address_to_port = address_to_port

	@classmethod
	def _lookup(cls, addr):
		if address in SSHProxyTable._address_to_port:
			return SSHProxyTable._address_to_port[addr]
		else:
			config.logger.error("IP Address not found for SSH Proxy: %s" % \
						    addr)
		return None

	@classmethod
	# Add proxy port for given IP address
	# If port provided, check if already taken. If so, error, if not grab it
	# Otherwise take the next available one
	def _add(cls, addr, port=None):
		port_number = 0
		# If port is supplied, must be free or already match one assigned to addr
		if port is not None:
			# IP Address already assigned to a different port?
			if addr in SSHProxyTable._address_to_port:
				assigned_port = SSHProxyTable._address_to_port[addr]
				if port <> assigned_port:
					config.logger.error("SSH Proxy for addr %s already assigned to port %s" % (addr, assigned_port))
					return port_number
				elif port in SSHProxyTable._address_to_port.values():
					config.logger.error("Port already assigned to another IP %s" % port)
				else:
					# Already assigned : No op
					port_number = assigned_port
			else:
				# Port is specified but not taken so grab it
				SSHProxyTable._address_to_port[addr] = port
				port_number = port
		else:
			# Find next free port
			next_free_port = -1
			for i in range(config.ssh_proxy_start_port, 
				       config.ssh_proxy_end_port+1):
				if i not in SSHProxyTable._address_to_port.values():
					next_free_port = i
					break
			if next_free_port == -1:
				config.logger.error("No free ports available for SSH proxy")
			elif addr in SSHProxyTable._address_to_port:
				current_port = SSHProxyTable._address_to_port[addr]
				config.logger.error("SSH proxy for addr %s already set to %s" % (addr, current_port))
			else:
				SSHProxyTable._address_to_port[addr] = next_free_port
				port_number = next_free_port

		return  port_number

	@classmethod
	# Remove proxy for a given IP address
	# Remove address => port mapping
	# Return port to list of free ports
	def _remove(cls, addr):
		port_number = 0
		if addr in SSHProxyTable._address_to_port:
			port_number = SSHProxyTable._address_to_port[addr]
			del SSHProxyTable._address_to_port[addr]
		else:
			config.logger.error("IP Address not found for SSH Proxy: %s" % \
						    addr)
		return  port_number
		

def _addNewProxy(addr,port=None) :
    """
    Access the GRAM SSH proxy daemon and create a new proxy with the given address
    """
    portNumber = SSHProxyTable._add(addr, port)
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

    portNumber = SSHProxyTable._remove(addr)
    if portNumber > 0 :
	    cmd_string = '%s ' % config.ssh_proxy_exe
	    cmd_string = cmd_string + '-m D -a %s ' % addr
	    cmd_string = cmd_string + ' -p %d ' % portNumber
	    cmd_string = cmd_string + ' -n %s ' % open_stack_interface._getConfigParam('/etc/gram/config.json','mgmt_ns')

	    try:
		    open_stack_interface._execCommand(cmd_string)
	    except :
		    config.logger.error("Address %s not present in SSH proxy" % addr)

def _getIpTable():
    """ 
    Print out the IP tables
    """

    cmd_string = '%s ' % config.ssh_proxy_exe
    cmd_string = cmd_string + ' -m L -n %s' % open_stack_interface._getConfigParam('/etc/gram/config.json','mgmt_ns')
   
    output = ""
    try:
        output = open_stack_interface._execCommand(cmd_string)
    except :
        config.logger.error("Address %s not present in SSH proxy" % addr)

    return output

if __name__ == "__main__":
	print "TABLE = %s" % SSHProxyTable._get()
	SSHProxyTable._restore({"10.10.10.8": 105, "10.10.10.9" : 106})
	print "TABLE = %s" % SSHProxyTable._get()
	print "LOOKUP = %s" % SSHProxyTable._lookup('10.10.10.8')
	print "LOOKUP = %s" % SSHProxyTable._lookup('10.10.10.7')
	SSHProxyTable._add("128.89.0.1", 107)
	print "TABLE = %s" % SSHProxyTable._get()
	print "LOOKUP = %s" % SSHProxyTable._lookup('128.89.0.1')
	SSHProxyTable._remove("128.89.0.1")
	print "TABLE = %s" % SSHProxyTable._get()
	print "LOOKUP = %s" % SSHProxyTable._lookup('128.89.0.1')

