from GenericInstaller import GenericInstaller
from gram.am.gram import config

class OpenVSwitch(GenericInstaller):

    quantum_directory = "/etc/quantum"
    quantum_conf_filename = "quantum.conf"
    api_paste_filename = "api-paste.ini"
    api_paste = quantum_directory + "/" + api_paste_filename
    quantum_conf = quantum_directory + "/" + quantum_conf_filename
    quantum_plugin_directory = "/etc/quantum/plugins/openvswitch"
    quantum_plugin_filename = "ovs_quantum_plugin.ini"
    quantum_plugin_conf = quantum_plugin_directory + "/" + quantum_plugin_filename
    networking_directory = "/etc/network"
    interfaces_filename = "interfaces"

    def __init__(self, control_node):
        self._control_node = control_node

    # Return a list of command strings for installing this component
    def installCommands(self):


        if self._control_node:
            self.installCommandsControl()
        else:
            self.installCommandsCompute()

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

        self.comment("Install OVS package")
        #self.add("module-assistant auto-install openvswitch-datapath")
        #self.add("/etc/init.d/openvswitch-switch start")

        #self.comment("Configure virtual bridging")
        #self.add("ovs-vsctl add-br br-int")
        #self.add("ovs-vsctl add-br br-ex")

        #self.add("ovs-vsctl br-set-external-id br-ex bridge-id br-ex")
#        self.add("ovs-vsctl add-port br-ex " + external_if)

        # SD: needed for VLANs??
#        self.add("ovs-vsctl add-br br-" + data_if)
#        self.add("ovs-vsctl add-port br-" + data_if + " " + data_if)
#        self.add("ovs-vsctl add-br br-" + mgmt_if)
#        self.add("ovs-vsctl add-port br-" + mgmt_if + " " + mgmt_if)

        self.comment("Modify /etc/network/interfaces to reflect the new configuration")
        # Replace references to management interface with references to br-ex
        #self.backup(self.networking_directory, backup_directory, self.interfaces_filename)
        interfaces = self.networking_directory + "/" + self.interfaces_filename
        # Add new manual configuration for external interface
#        self.sed("s/" + external_interface + "/" + external_bridge + "/", interfaces)
#        self.appendToFile("", interfaces)
#        self.appendToFile("auto " + external_interface,  interfaces)
#        self.appendToFile("iface " + external_interface + " inet manual", interfaces)
#        self.appendToFile("up ifconfig $IFACE 0.0.0.0 up", interfaces)
#        self.appendToFile("up ip link set $IFACE promisc on", interfaces)
#        self.appendToFile("down ip link set $IFACE promisc off", interfaces)
#        self.appendToFile("down ifconfig $IFACE down",  interfaces)
#        self.add("service networking restart")
#        self.add("ifdown --force " + external_interface)
#        self.add("ifup --force " + external_interface)
#        self.add("ifdown --force br-ex")
#        self.add("ifup --force br-ex")

    def installCommandsCompute(self):

        self.comment("*** OpenVSwitch Install (compute) ***")
        self.add("module-assistant auto-install openvswitch-datapath")

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
        quantum_user = config.quantum_user
        quantum_password = config.quantum_password
        os_password = config.os_password
        mgmt_if = config.management_interface
        mgmt_net_name = config.management_network_name
        mgmt_net_vlan = config.management_network_vlan
        mgmt_net_cidr = config.management_network_cidr
        data_if = config.data_interface

        self.backup(self.quantum_directory, backup_directory, self.quantum_conf_filename)

        self.sed("s/^auth_host.*/auth_host =" + control_address + "/", self.quantum_conf)
        self.sed("s/^auth_port.*/auth_port = 35357/", self.quantum_conf)
        self.sed("s/^auth_protocol.*/auth_protocol = http/", self.quantum_conf)
        self.sed("s/^signing_dir.*/signing_dir = \/var\/lib\/quantum\/keystone-signing/",self.quantum_conf)
        self.sed("s/^admin_tenant_name.*/admin_tenant_name = service/", self.quantum_conf)
        self.sed("s/^admin_user.*/admin_user = " + quantum_user + "/", self.quantum_conf)
        self.sed("s/^admin_password.*/admin_pass = service_pass/", self.quantum_conf)
	self.sed("s/^# rabbit_host .*/rabbit_host = " + config.control_host_addr + "/" , self.quantum_conf)
        self.sed("s/^\# allow_overlapping_ips .*/allow_overlapping_ips = True/",self.quantum_conf)

        self.comment("edit ovs_quantum_plugin.ini")
        self.backup(self.quantum_plugin_directory, backup_directory, \
                        self.quantum_plugin_filename)
        connection = "sql_connection = mysql:\/\/" + quantum_user + ":" +\
            quantum_password + "@" + control_host + ":3306\/quantum"
        self.sed("s/sql_connection.*/" + connection + "/", 
                 self.quantum_plugin_conf)
#        self.sed("s/reconnect_interval.*/reconnect_interval=2/", 
#                 self.quantum_plugin_conf)
        self.sed("/^tunnel_id_ranges.*/ s/^/#/",
                 self.quantum_plugin_conf)
        self.sed("/^integration_bridge.*/ s/^/#/",
                 self.quantum_plugin_conf)
        self.sed("/^tunnel_bridge.*/ s/^/\#/", \
                 self.quantum_plugin_conf)
        self.sed("/^local_ip.*/ s/^/\#/", \
                 self.quantum_plugin_conf)
        self.sed("/^enable_tunneling.*/ s/^/\#/", \
                 self.quantum_plugin_conf)
        self.sed("s/^tenant_network_type.*/tenant_network_type=vlan/", \
                 self.quantum_plugin_conf)
        self.sed("s/^\# root_helper sudo \/usr.*/root_helper = sudo \/usr\/bin\/quantum-rootwrap \/etc\/quantum\/rootwrap.conf/", 
                 self.quantum_plugin_conf)
        self.sed("s/\# Default: tenant_network_type.*/tenant_network_type=vlan/",
                 self.quantum_plugin_conf)
        # TODO:  How do we handle these ranges?
        self.sed("s/\# Default: network_vlan_ranges.*/network_vlan_ranges=physnet1:1000:2000,physnet2:2001:3000/", self.quantum_plugin_conf)
        self.sed("s/\# Default: bridge_mappings.*/bridge_mappings=physnet1:br-" + data_if + ",physnet2:br-" + mgmt_if + "/", self.quantum_plugin_conf)
        #self.sed("s/^# firewall_driver.*/firewall_driver = quantum.agent.linux.iptables_firewall.OVSHybridIptablesFirewallDriver/", self.quantum_plugin_conf)


        self.comment("Start the agent")
        self.add("service quantum-plugin-openvswitch-agent restart")


    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        if self._control_node:
            self.uninstallCommandsControl()
        else:
            self.uninstallCommandsCompute()

    def uninstallCommandsControl(self):
        self.comment("*** OpenVSwitch Uninstall (control) ***")

    def uninstallCommandsCompute(self):
        self.comment("*** OpenVSwitch Uninstall (compute) ***")

        backup_directory = config.backup_directory
        self.restore(self.quantum_directory, backup_directory, self.quantum_conf_filename)

        self.restore(self.quantum_plugin_directory, backup_directory, \
                         self.quantum_plugin_filename)
        self.backup(self.quantum_directory, backup_directory, self.api_paste_filename)
