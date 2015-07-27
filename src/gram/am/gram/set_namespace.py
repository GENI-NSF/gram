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
import string
import fileinput
import sys
import config
import netaddr
import re
import json


def _execCommand(cmd_string) :
    """
       Execute the specified command.  Return the output of the command or
       raise and exception if the command execution fails.
    """
    if config.openstack_type == 'juno':
        netAddr = config.network_host_addr
        cmd_string = 'ssh gram@' + netAddr  + ' sudo ' +  cmd_string
    command = cmd_string.split()
    try :
        return subprocess.check_output(command)
    except :
        raise

def _getConfigParam(config_file,param):
    """
       Function to parse the gram config file and return the value of the specified parameter
    """

    data = None
    try:
        f = open(config_file, 'r')
        data = f.read()
        f.close()
    except Exception, e:
        print "Failed to read GRAM config file: " + config_file + str(e)
        return

    data_json = json.loads(data)

    return data_json[param]


def _getPublicIp(ns):
    """ Looks at the IP Tables in the management namespace and 
        figures out the SNAT IP address that is mapped to the
        management network
    """
    command = 'ip netns exec ' + ns + ' iptables -L -t nat --line-numbers'
    output = _execCommand(command)
    output_lines = output.split('\n')
    found = 0
    mgmt_cidr = _getConfigParam('/etc/gram/config.json','management_network_cidr')
    for line in output_lines:
        m = re.search(r'SNAT.*all.*' + mgmt_cidr + '.*to:(.*)',line)
        if m:
            return m.group(1)


def _getMgmtNamespace() :
    """
       Looks at the namespaces on the machine and finds one that has the management
       network and the external network:
    """
    # config.initialize('/etc/gram/config.json')
    mgmt_addr = (netaddr.IPNetwork(_getConfigParam('/etc/gram/config.json','management_network_cidr'))).broadcast  # first ip on the mgmt cidr
    public_addr = _getConfigParam('/etc/gram/config.json','public_subnet_start_ip')

    # get a list of the namespaces
    command = 'ip netns list'
    output = _execCommand(command)
    output_lines = output.split('\n')

    # check for both public and mgmt address in each namespace
    has_mgmt = 0
    has_public = 0
    for line in output_lines:
        try:
            command = 'ip netns exec ' + line + ' ifconfig'
            ifconfig = _execCommand(command)
        except subprocess.CalledProcessError as e:
            print e.returncode

        ifconfig_lines = ifconfig.split('\n')
        for ifconfig_line in ifconfig_lines:
            if str(mgmt_addr) in ifconfig_line:
                has_mgmt = 1
            if public_addr in ifconfig_line:
                has_public = 1
        if has_mgmt and has_public:
            return line
        else:
            has_mgmt = 0
            has_public = 0
    return None


def _setField(field,value,final=False):
    for line in fileinput.input('/etc/gram/config.json', inplace=1):
        if field in line:
            if not final:
                line = line.replace(line,'   "' + field + '": "' + value + '",\n' )
            else:
                line = line.replace(line,'   "' + field + '": "' + value + '"\n' )
        sys.stdout.write(line)

if __name__ == "__main__":

    
    # Get the namespace name
    config.initialize('/etc/gram/config.json')
    ns = _getMgmtNamespace()
    pub_ip = _getPublicIp(ns)
    
   # edit config.json to update the namespace
    if ns:
        _setField('mgmt_ns',ns,True)
    else:
        print 'Failed to set namespace'

   # set the public ip address
    if pub_ip:
        _setField('public_ip',pub_ip)
    else:
        print 'Failed to set public IP address'



