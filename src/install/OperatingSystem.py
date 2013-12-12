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

from GenericInstaller import GenericInstaller
from gram.am.gram import config

# We assume at this point that these have been completed:
# steps #1 (install Ubuntu) and #3 (configure the network)
# and reboot
class OperatingSystem(GenericInstaller):

    def __init__(self, control_node):
        self._control_node = control_node

    # Return a list of command strings for installing this component
    def installCommands(self):
        self.comment("*** OperatingSystem Install ***")
        self.comment("Step 2. Add repository and upgrade Ubuntu")

        if self._control_node:
            self.comment("Set up ubuntu cloud keyring")
        

 
        self.comment("Enable IP forwarding")
        backup_directory = config.backup_directory
        self.backup("/etc", backup_directory, "sysctl.conf")
        self.sed('s/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/',
                 '/etc/sysctl.conf')
        self.add("sysctl net.ipv4.ip_forward=1")
        self.add('service networking restart')

        self.comment("Step 4: Configure NTP")
        self.backup("/etc", backup_directory, "ntp.conf")
        self.appendToFile('# Use Ubuntu ntp server as fallback.',
                          '/etc/ntp.conf')
        self.appendToFile('server ntp.ubuntu.com iburst', 
                          '/etc/ntp.conf')
        self.appendToFile('server 127.127.1.0','/etc/ntp.conf')
        self.appendToFile('fudge 127.127.1.0 stratum 10', 
                          '/etc/ntp.conf')
        self.add('service ntp restart')


    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        self.comment("*** OperatingSystem Uninstall ***")
        backup_directory = config.backup_directory
        self.restore("/etc", backup_directory, "sysctl.conf")
        self.restore("/etc", backup_directory, "ntp.conf")

