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

class Nova(GenericInstaller):

    nova_directory = "/etc/nova"
    api_paste_filename = "api-paste.ini"
    service_tenant_name = "service"
    config_filename = "nova.conf"
    saved_control_config_filename = "/home/gram/gram/juno/install/control_files/nova.conf"
    saved_compute_config_filename = "/home/gram/gram/juno/install/compute_files/nova.conf"
    nova_compute_filename = "nova-compute.conf"
    saved_nova_compute_filename = "/home/gram/gram/juno/install/compute_files/nova-compute.conf"

    def __init__(self, control_node, node_type):
        self._control_node = control_node
        self._node_type = node_type
        self.nova_user = None
        self.nova_password = None
        self.neutron_user = None
        self.neutron_password = None
        self.rabbit_password = None
        self.os_password = None
        self.backup_directory = None
        self.connection = None
        self.control_host = None

    # Return a list of command strings for installing this component
    def installCommands(self):
        self.nova_user = config.nova_user
        self.nova_password = config.nova_password
        self.neutron_user = config.network_user
        self.neutron_password = config.network_password
        self.rabbit_password = config.rabbit_password
        self.os_password = config.os_password
        self.backup_directory = config.backup_directory
        self.control_host = config.control_host
        self.control_host_addr = config.control_host_addr

        self.connection = "connection = mysql:\/\/" + \
            self.nova_user + ":" + \
            self.nova_password + "@" + self.control_host + "\/nova"

        #if self._control_node:
        if self._node_type == 'control':
            self.connection = "connection = mysql:\/\/" + \
                self.nova_user + ":" + \
                self.nova_password + "@" + self.control_host + "\/nova"
            self.installCommandsControl()
        elif self._node_type == 'compute':
            self.installCommandsCompute()
        else:
            self.installCommandsNetwork()

    def installCommandsControl(self):
        self.comment("*** Nova Install (control) ***")

        self.backup(self.nova_directory, self.backup_directory, \
                        self.config_filename)

        nova_conf = self.nova_directory + "/" + self.config_filename

        self.add("cp " + self.saved_control_config_filename + " " + \
                 nova_conf)

        self.sed("s/^connection =.*/" + self.connection + "/", \
                     nova_conf)

        self.sed("s/^rabbit_host =.*/rabbit_host = " + self.control_host + "/", \
                    nova_conf)

        self.sed("s/^rabbit_password =.*/rabbit_password = " + config.rabbit_password + "/", \
                    nova_conf)

        self.sed("s/^my_ip =.*/my_ip = " + self.control_host_addr + "/", \
                    nova_conf)

        self.sed("s/^vncserver_listen =.*/vncserver_listen = " + self.control_host_addr + "/", \
                    nova_conf)

        self.sed("s/^vncserver_proxyclient_address =.*/vncserver_proxyclient_address = " + self.control_host_addr + "/", \
                    nova_conf)

        self.sed("s/^auth_uri =.*/auth_uri = http:\/\/" + config.control_host +":5000\/v2.0/", \
                    nova_conf)

        self.sed("s/^identity_uri =.*/identity_uri = http:\/\/" + config.control_host + ":35357/", \
                    nova_conf)

        self.sed("s/^admin_password =.*/admin_password = " + config.service_password + "/", \
                    nova_conf)

        self.sed("s/^host =.*/host = " + config.control_host + "/", nova_conf)

        self.sed("s/^url =.*/url = http:\/\/" + config.control_host +":9696/", \
                    nova_conf)

        self.sed("s/^admin_auth_url =.*/admin_auth_url = http:\/\/" + config.control_host + ":35357\/v2.0/", \
                    nova_conf)

        self.add("su -s /bin/sh -c \"nova-manage db sync\" nova")
        self.add('service nova-api restart')
        self.add('service nova-cert restart')
        self.add('service nova-consoleauth restart')
        self.add('service nova-scheduler restart')
        self.add('service nova-conductor restart')
        self.add('service nova-novncproxy restart')
        self.add('rm -f /var/lib/nova/nova.sqlite')

    def installCommandsCompute(self):
        self.comment("*** Nova Install (compute) ***")


        self.comment("Configure NOVA")
        self.backup(self.nova_directory, self.backup_directory, self.config_filename)
        nova_conf = self.nova_directory + "/" + self.config_filename

        self.add("cp " + self.saved_compute_config_filename + " " + \
                 nova_conf)

        self.sed("s/^rabbit_host =.*/rabbit_host = " + self.control_host + "/", \
                    nova_conf)

        self.sed("s/^rabbit_password =.*/rabbit_password = " + config.rabbit_password + "/", \
                    nova_conf)

        self.sed("s/^my_ip =.*/my_ip = " + config.control_address + "/", \
                    nova_conf)

        self.sed("s/^vncserver_proxyclient_address =.*/vncserver_proxyclient_address = " + config.control_address + "/", \
                    nova_conf)

        #RRH this actually needs to be the control host external IP address - not the external of the compute
        self.sed("s/^novncproxy_base_url =.*/novncproxy_base_url = http:\/\/" + config.control_host_external_addr + ":6080\/vnc_auto.html/", \
                    nova_conf)

        self.sed("s/^auth_uri =.*/auth_uri = http:\/\/" + config.control_host +":5000\/v2.0/", \
                    nova_conf)

        self.sed("s/^identity_uri =.*/identity_uri = http:\/\/" + config.control_host + ":35357/", \
                    nova_conf)

        #should take care of the keystone_authtoken section and the neutron section passwords
        self.sed("s/^admin_password =.*/admin_password = " + config.service_password + "/", \
                    nova_conf)

        self.sed("s/^host =.*/host = " + config.control_host + "/", nova_conf)

        self.sed("s/^url =.*/url = http:\/\/" + config.control_host +":9696/", \
                    nova_conf)

        self.sed("s/^admin_auth_url =.*/admin_auth_url = http:\/\/" + config.control_host + ":35357\/v2.0/", \
                    nova_conf)

        nova_compute_file = self.nova_directory + "/" + self.nova_compute_filename


        self.backup(self.nova_directory, self.backup_directory, \
                        self.nova_compute_filename)

        self.add("cp " + self.saved_nova_compute_filename + " " + \
                        nova_compute_file)

        self.add("rm -f /var/lib/nova/nova.sqlite")


        self.comment("Restart Nova Services")
        self.add("service openvswitch-switch restart")
        self.add("service nova-compute restart")
        self.add("service neutron-plugin-openvswitch-agent restart")

    def installCommandsNetwork(self):
        self.comment("Restart Nova Services")

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        self.nova_user = config.nova_user
        self.nova_password = config.nova_password
        self.rabbit_password = config.rabbit_password
        self.os_password = config.os_password
        self.backup_directory = config.backup_directory
        #if self._control_node:
        if self._node_type == 'control':
            self.uninstallCommandsControl()
        elif self._node_type == 'compute':
            self.uninstallCommandsCompute()
        else:
            self.uninstallCommandsNetwork()

    def uninstallCommandsControl(self):
        self.comment("*** Nova Uninstall (control) ***")

        self.restore(self.nova_directory, self.backup_directory, \
                         self.api_paste_filename)
        self.restore(self.nova_directory, self.backup_directory, self.config_filename)

    def uninstallCommandsCompute(self):
        self.comment("*** Nova Uninstall (compute) ***")

        self.restore(self.nova_directory, self.backup_directory, \
                         self.api_paste_filename)
        self.restore(self.nova_directory, self.backup_directory, \
                         self.nova_compute_filename)
        self.restore(self.nova_directory, self.backup_directory, self.config_filename)

    def uninstallCommandsNetwork(self):
        self.comment("*** Nova Uninstall (network) ***")

        self.restore(self.nova_directory, self.backup_directory, \
                         self.api_paste_filename)
        self.restore(self.nova_directory, self.backup_directory, \
                         self.nova_compute_filename)
        self.restore(self.nova_directory, self.backup_directory, self.config_filename)

    def modify_api_paste_file(self):
        self.backup(self.nova_directory, self.backup_directory, \
                        self.api_paste_filename)

        #self.sed("s/^\[filter:authtoken\].*/\[filter:authtoken\]\nauth_host =" control_host + "\nauth_port = 35357\nauth_protocol = http\nadmin_tenant_name = service\nadmin_user = neutron\nadmin_password = service_pass\n" + "/", \
         #            self.nova_directory + "/" + \
         #            self.api_paste_filename)


        self.sed("s/^auth_host.*/auth_host = " + self.control_host_addr + "/",self.nova_directory + "/" +self.api_paste_filename)
        self.sed("s/^auth_port.*/auth_port = 35357/",self.nova_directory + "/" +self.api_paste_filename)
        self.sed("s/^admin_tenant_name.*/admin_tenant_name = service/",self.nova_directory + "/" +self.api_paste_filename)
        self.sed("s/^admin_user.*/admin_user = nova/",self.nova_directory + "/" +self.api_paste_filename)
        self.sed("s/^admin_password.*/admin_password = service_pass/",self.nova_directory + "/" +self.api_paste_filename)
        self.sed("s/^#signing_dir.*/signing_dirname = \/tmp\/keystone-signing-nova/",self.nova_directory + "/" +self.api_paste_filename)
#        self.sed("s/admin_tenant_name.*/admin_tenant_name = " + \
#                     self.service_tenant_name + "/", 
#                 self.nova_directory + "/" + self.api_paste_filename)
#        self.sed("s/admin_user.*/admin_user = " + self.nova_user + "/", 
#                 self.nova_directory + "/" + self.api_paste_filename)
#        self.sed("s/admin_password.*/admin_password = " + self.os_password + "/", 
#                 self.nova_directory + "/" + self.api_paste_filename)
#        if self._control_node:
#            self.sed("/volume/d", 
#                     self.nova_directory + "/" + self.api_paste_filename)



