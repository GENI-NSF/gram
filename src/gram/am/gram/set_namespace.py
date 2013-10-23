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
from open_stack_interface import _execCommand, _getConfigParam

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

if __name__ == "__main__":

   # Get the namespace name
   ns = _getMgmtNamespace()
   
   # edit config.json to update the namespace
   if ns:
     for line in fileinput.input('/etc/gram/config.json', inplace=1):
        if 'mgmt_ns' in line:
            line = line.replace(line,'   "mgmt_ns": "' + ns + '"\n' )
        sys.stdout.write(line) 




