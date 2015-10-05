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

class OpenVSwitch(GenericInstaller):

    neutron_directory = "/etc/neutron"
    neutron_conf_filename = "neutron.conf"
    api_paste_filename = "api-paste.ini"
    api_paste = neutron_directory + "/" + api_paste_filename
    neutron_conf = neutron_directory + "/" + neutron_conf_filename
    neutron_plugin_directory = "/etc/neutron/plugins/openvswitch"
    neutron_plugin_filename = "ovs_neutron_plugin.ini"
    neutron_plugin_conf = neutron_plugin_directory + "/" + neutron_plugin_filename
    networking_directory = "/etc/network"
    interfaces_filename = "interfaces"

    def __init__(self, control_node, node_type):
        self._control_node = control_node
        self._node_type = node_type

    # Return a list of command strings for installing this component
    def installCommands(self):


        if self._node_type == 'control':
            self.installCommandsControl()
        elif self._node_type == 'compute':
            self.installCommandsCompute()
        else:
            self.installCommandsNetwork()

    def installCommandsControl(self):

        self.comment("*** OpenVSwitch Install (control) ***")

        backup_directory = config.backup_directory
        external_interface = config.external_interface
        mgmt_if = config.management_interface
        mgmt_net_name = config.management_network_name
        mgmt_net_vlan = config.management_network_vlan
        mgmt_net_cidr = config.management_network_cidr
        external_if = config.external_interface
        external_bridge = "br-ex"
        data_if = config.data_interface
        self.backup(self.neutron_directory, backup_directory, self.neutron_conf_filename)
        self.backup(self.neutron_plugin_directory, backup_directory, self.neutron_plugin_filename)
        self.comment("Install OVS package")

        self.comment("Modify /etc/network/interfaces to reflect the new configuration")
        # Replace references to management interface with references to br-ex
        #self.backup(self.networking_directory, backup_directory, self.interfaces_filename)
        interfaces = self.networking_directory + "/" + self.interfaces_filename

    def installCommandsCompute(self):

        self.comment("*** OpenVSwitch Install (compute) ***")
        #self.add("module-assistant auto-install openvswitch-datapath")

        control_address = config.control_address
        backup_directory = config.backup_directory
        external_interface = config.external_interface
        mgmt_if = config.management_interface
        mgmt_net_name = config.management_network_name
        mgmt_net_vlan = config.management_network_vlan
        mgmt_net_cidr = config.management_network_cidr
        external_if = config.external_interface
        external_bridge = "br-ex"
        data_if = config.data_interface


        #SD: compied this from folsom config
        # this happens in operating system now
        #self.comment("Configure virtual bridging")
        #self.add("ovs-vsctl add-br br-int")
        #self.add("ovs-vsctl add-br br-" + data_if)
        #self.add("ovs-vsctl add-port br-" + data_if + " " + data_if)
        #self.add("ovs-vsctl add-br br-" + mgmt_if)
        #self.add("ovs-vsctl add-port br-" + mgmt_if + " " + mgmt_if)

        backup_directory = config.backup_directory
        control_host = config.control_host
        rabbit_password = config.rabbit_password
        neutron_user = config.neutron_user
        neutron_password = config.neutron_password
        os_password = config.os_password
        mgmt_if = config.management_interface
        mgmt_net_name = config.management_network_name
        mgmt_net_vlan = config.management_network_vlan
        mgmt_net_cidr = config.management_network_cidr
        data_if = config.data_interface

        self.backup(self.neutron_directory, backup_directory, self.neutron_conf_filename)

        self.sed("s/^auth_host.*/auth_host =" + control_address + "/", self.neutron_conf)
        self.sed("s/^auth_port.*/auth_port = 35357/", self.neutron_conf)
        self.sed("s/^auth_protocol.*/auth_protocol = http/", self.neutron_conf)
        self.sed("s/^signing_dir.*/signing_dir = \/var\/lib\/neutron\/keystone-signing/",self.neutron_conf)
        self.sed("s/^admin_tenant_name.*/admin_tenant_name = service/", self.neutron_conf)
        self.sed("s/^admin_user.*/admin_user = " + neutron_user + "/", self.neutron_conf)
        self.sed("s/^admin_password.*/admin_pass = service_pass/", self.neutron_conf)
	self.sed("s/^# rabbit_host .*/rabbit_host = " + config.control_host_addr + "/" , self.neutron_conf)
        self.sed("s/^\# allow_overlapping_ips .*/allow_overlapping_ips = True/",self.neutron_conf)

        self.comment("edit ovs_neutron_plugin.ini")
        self.backup(self.neutron_plugin_directory, backup_directory, \
                        self.neutron_plugin_filename)
        connection = "sql_connection = mysql:\/\/" + neutron_user + ":" +\
            neutron_password + "@" + config.control_host_addr + ":3306\/neutron"
        self.sed("s/sql_connection.*/" + connection + "/", 
                 self.neutron_plugin_conf)
#        self.sed("s/reconnect_interval.*/reconnect_interval=2/", 
#                 self.neutron_plugin_conf)
        self.sed("/^tunnel_id_ranges.*/ s/^/#/",
                 self.neutron_plugin_conf)
        self.sed("/^integration_bridge.*/ s/^/#/",
                 self.neutron_plugin_conf)
        self.sed("/^tunnel_bridge.*/ s/^/\#/", \
                 self.neutron_plugin_conf)
        self.sed("/^local_ip.*/ s/^/\#/", \
                 self.neutron_plugin_conf)
        self.sed("/^enable_tunneling.*/ s/^/\#/", \
                 self.neutron_plugin_conf)
        self.sed("s/^tenant_network_type.*/tenant_network_type=vlan/", \
                 self.neutron_plugin_conf)
        self.sed("s/^\# root_helper sudo \/usr.*/root_helper = sudo \/usr\/bin\/neutron-rootwrap \/etc\/neutron\/rootwrap.conf/", 
                 self.neutron_plugin_conf)
        self.sed("s/\# Default: tenant_network_type.*/tenant_network_type=vlan/",
                 self.neutron_plugin_conf)
        # TODO:  How do we handle these ranges?
        self.sed("s/\# Default: network_vlan_ranges.*/network_vlan_ranges=physnet1:1000:2000,physnet2:2001:3000/", self.neutron_plugin_conf)
        self.sed("s/\# Default: bridge_mappings.*/bridge_mappings=physnet1:br-" + data_if + ",physnet2:br-" + mgmt_if + "/", self.neutron_plugin_conf)
        #self.sed("s/^# firewall_driver.*/firewall_driver = neutron.agent.linux.iptables_firewall.OVSHybridIptablesFirewallDriver/", self.neutron_plugin_conf)


        self.comment("Start the agent")
        self.add("service neutron-plugin-openvswitch-agent restart")

    def installCommandsNetwork(self):

        self.comment("*** OpenVSwitch Install (network) ***")

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        if self._node_type == 'control':
            self.uninstallCommandsControl()
        elif self._node_type == 'compute':
            self.uninstallCommandsCompute()
        else:
            self.uninstallCommandsNetwork()

    def uninstallCommandsControl(self):
        self.comment("*** OpenVSwitch Uninstall (control) ***")

    def uninstallCommandsCompute(self):
        self.comment("*** OpenVSwitch Uninstall (compute) ***")

        backup_directory = config.backup_directory
        self.restore(self.neutron_directory, backup_directory, self.neutron_conf_filename)

        self.restore(self.neutron_plugin_directory, backup_directory, \
                         self.neutron_plugin_filename)
        self.backup(self.neutron_directory, backup_directory, self.api_paste_filename)

    def uninstallCommandsNetwork(self):
        self.comment("*** OpenVSwitch Uninstall (network) ***")
