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

class Horizon(GenericInstaller):

    horizon_directory = "/etc/openstack-dashboard"
    horizon_conf_filename = "local_settings.py"
    saved_horizon_conf_filename = "/home/gram/gram/juno/install/control_files/local_settings.py"
    backup_directory = config.backup_directory

    # Return a list of command strings for installing this component
    def installCommands(self):
        self.comment("*** Horizon Install ***")

        self.comment("Step 1. Configure Horizon")

        self.backup(self.horizon_directory, self.backup_directory, \
                        self.horizon_conf_filename)

        self.comment("Step 2. Configure conf file")
        self.add("cp " + self.saved_horizon_conf_filename + " " + \
                 self.horizon_directory + "/" + \
                     self.horizon_conf_filename)

        self.sed('s/^OPENSTACK_HOST =.*/OPENSTACK_HOST = \\\"' + config.control_host + '\\\"/', \
                     self.horizon_directory + "/" + \
                     self.horizon_conf_filename)

        self.add("apt-get remove -y --purge openstack-dashboard-ubuntu-theme")
        self.add("service apache2 restart")
        self.add("service memcached restart")


    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        self.comment("*** Horizon Uninstall ***")
        backup_directory = config.backup_directory
        self.restore(self.horizon_directory, backup_directory, \
                         self.horizon_conf_filename)
