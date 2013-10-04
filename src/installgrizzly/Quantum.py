from GenericInstaller import GenericInstaller
from gram.am.gram import config

class Quantum(GenericInstaller):

    quantum_directory = "/etc/quantum"
    quantum_conf_filename = "quantum.conf"
    quantum_l3_agent_filename = "l3_agent.ini"
    quantum_plugin_directory = "/etc/quantum/plugins/openvswitch"
    quantum_plugin_conf_filename = "ovs_quantum_plugin.ini"
    quantum_dhcp_conf_filename = "dhcp_agent.ini"
    quantum_api_conf_filename = "api-paste.ini"
    service_tenant_name = "service"
    quantum_metadata_file = "/etc/quantum/metadata_agent.ini"

    # Return a list of command strings for installing this component
    def installCommands(self):
        control_address = config.control_address
        metadata_port = config.metadata_port
        quantum_user = config.quantum_user
        quantum_password = config.quantum_password
        rabbit_password = config.rabbit_password
        os_password = config.os_password
        backup_directory = config.backup_directory
        public_gateway_ip = config.public_gateway_ip
        public_subnet_cidr = config.public_subnet_cidr
        public_subnet_start_ip = config.public_subnet_start_ip
        public_subnet_end_ip = config.public_subnet_end_ip
        mgmt_if = config.management_interface
        mgmt_net_name = config.management_network_name
        mgmt_net_cidr = config.management_network_cidr
        mgmt_net_vlan = config.management_network_vlan

        connection = "sql_connection = mysql:\/\/"+ quantum_user + ":" +  quantum_password + "@" + control_address + "\/quantum"  

        self.comment("*** Quantum Install ***")

        self.comment("Install packages")

        self.comment("Configure quantum services")
        #self.backup(self.quantum_directory, backup_directory, self.quantum_conf_filename)
        #self.backup(self.quantum_plugin_directory, backup_directory, self.quantum_plugin_conf_filename)
        self.backup(self.quantum_directory, backup_directory, self.quantum_api_conf_filename) 
 
        self.sed("s/sql_connection.*/" + connection + "/",
            self.quantum_plugin_directory + "/" + \
            self.quantum_plugin_conf_filename)

        self.sed("s/^.*Example: tenant_network_type.*/tenant_network_type=vlan/",
                     self.quantum_plugin_directory + "/" + \
                     self.quantum_plugin_conf_filename)
        #self.sed("s/^\# tenant_network_type.*/tenant_network_type=vlan/", \
        #             self.quantum_plugin_directory + "/" + \
        #             self.quantum_plugin_conf_filename)


        self.sed("s/^tunnel_id_ranges.*//",
                     self.quantum_plugin_directory + "/" + \
                     self.quantum_plugin_conf_filename)
        self.sed("s/^integration_bridge.*//",
                     self.quantum_plugin_directory + "/" + \
                     self.quantum_plugin_conf_filename)
        self.sed("s/^tunnel_bridge.*//", \
                     self.quantum_plugin_directory + "/" + \
                     self.quantum_plugin_conf_filename)
        self.sed("s/^local_ip.*//", \
                     self.quantum_plugin_directory + "/" + \
                     self.quantum_plugin_conf_filename)
        self.sed("s/^enable_tunneling.*//", \
                     self.quantum_plugin_directory + "/" + \
                     self.quantum_plugin_conf_filename)
        self.sed("s/^\# root_helper sudo \/usr.*/root_helper = sudo \/usr\/bin\/quantum-rootwrap \/etc\/quantum\/rootwrap.conf/",
                     self.quantum_plugin_directory + "/" + \
                     self.quantum_plugin_conf_filename)
        #self.sed("s/\# Default: tenant_network_type.*/tenant_network_type=vlan/",
        #             self.quantum_plugin_directory + "/" + \
        #             self.quantum_plugin_conf_filename)
        # TODO:  Figure out ranges
        self.sed("s/\# Default: network_vlan_ranges.*/network_vlan_ranges=physnet1:1000:2000,physnet2:2001:3000/",
                     self.quantum_plugin_directory + "/" + \
                     self.quantum_plugin_conf_filename)
        self.sed("s/\# Default: bridge_mappings.*/bridge_mappings=physnet1:br-" + config.data_interface + ",physnet2:br-" + config.management_interface + "/",
                     self.quantum_plugin_directory + "/" + \
                     self.quantum_plugin_conf_filename)
        

        self.sed("s/^# firewall_driver.*/firewall_driver = quantum.agent.linux.iptables_firewall.OVSHybridIptablesFirewallDriver/",self.quantum_plugin_directory + "/" + self.quantum_plugin_conf_filename)


        #self.sed("s/^\[filter:authtoken\].*/\[filter:authtoken\]\nauth_host = control_address\nauth_port = 35357\nauth_protocol = http\nadmin_tenant_name = service\nadmin_user = quantum\nadmin_password = service_pass\n" + "/", \
        #             self.quantum_plugin_directory + "/" + \
        #             self.quantum_api_conf_filename)

        self.sed("s/^\[filter:authtoken\].*//",self.quantum_directory + "/" + self.quantum_api_conf_filename)
        self.sed("s/^paste.filter_factory = keystonec.*//",self.quantum_directory + "/" + self.quantum_api_conf_filename)

        self.appendToFile("[filter:authtoken]",self.quantum_directory + "/" + self.quantum_api_conf_filename)
        self.appendToFile("paste.filter_factory = keystoneclient.middleware.auth_token:filter_factory",self.quantum_directory+ "/" + self.quantum_api_conf_filename)
        self.appendToFile("auth_host =" + control_address, self.quantum_directory + "/" + self.quantum_api_conf_filename )
        self.appendToFile("auth_port = 35357", self.quantum_directory + "/" + self.quantum_api_conf_filename)
        self.appendToFile("auth_protocol = http", self.quantum_directory + "/" + self.quantum_api_conf_filename)
        self.appendToFile("admin_tenant_name = service", self.quantum_directory + "/" + self.quantum_api_conf_filename)
        self.appendToFile("admin_user = " + quantum_user, self.quantum_directory + "/" + self.quantum_api_conf_filename)
        self.appendToFile("admin_password = service_pass", self.quantum_directory + "/" + self.quantum_api_conf_filename)
        
        self.appendToFile("rabbit_host = " + control_address,self.quantum_directory + "/" + self.quantum_conf_filename)


        self.sed("s/^auth_host.*/auth_host =" + control_address + "/", self.quantum_directory + "/" + self.quantum_conf_filename)
        self.sed("s/^auth_port.*/auth_port = 35357/", self.quantum_directory + "/" + self.quantum_conf_filename)
        self.sed("s/^auth_protocol.*/auth_protocol = http/", self.quantum_directory + "/" + self.quantum_conf_filename)
        self.sed("s/^signing_dir.*/signing_dir = \/var\/lib\/quantum\/keystone-signing/", self.quantum_directory + "/" + self.quantum_conf_filename)
        self.sed("s/^admin_tenant_name.*/admin_tenant_name = service/", self.quantum_directory + "/" + self.quantum_conf_filename)
        self.sed("s/^admin_user.*/admin_user = " + quantum_user + "/", self.quantum_directory + "/" + self.quantum_conf_filename)
        self.sed("s/^admin_password.*/admin_password = service_pass/", self.quantum_directory + "/" + self.quantum_conf_filename)
        self.sed("s/^\# allow_overlapping_ips .*/allow_overlapping_ips = True/",self.quantum_directory + "/" + self.quantum_conf_filename)

        self.writeToFile("[DEFAULT]",self.quantum_metadata_file)
        self.appendToFile("# The Quantum user information for accessing the Quantum API.",self.quantum_metadata_file)
        self.appendToFile("auth_url = http://" + control_address + ":35357/v2.0",self.quantum_metadata_file)
        self.appendToFile("auth_region = RegionOne",self.quantum_metadata_file)
        self.appendToFile("admin_tenant_name = service",self.quantum_metadata_file)
        self.appendToFile("admin_user = quantum",self.quantum_metadata_file)
        self.appendToFile("admin_password =service_pass",self.quantum_metadata_file)
        self.appendToFile("nova_metadata_ip =" + control_address,self.quantum_metadata_file)
        self.appendToFile("nova_metadata_port = 8775",self.quantum_metadata_file)
        self.appendToFile("metadata_proxy_shared_secret = helloOpenStack",self.quantum_metadata_file)
        # SD: Will need to double check that this works, not in the installation instructions

        self.add("source /etc/novarc")

        self.add("service quantum-server restart")
        self.add("service quantum-plugin-openvswitch-agent restart")
        self.add("service quantum-dhcp-agent restart")
        self.add("service quantum-l3-agent restart")
        self.add("for i in `seq 1 30`; do")
        self.add("  echo 'checking quantum status'")
        self.add("  quantum net-list > /dev/null")
        self.add("  if [ $? -eq 0 ]; then")
        self.add("    break")
        self.add("  fi") 
        self.add("  sleep .5")
        self.add("done")
        self.add("echo 'Creating management network'")
	self.add("quantum net-create " + mgmt_net_name + " --provider:network_type vlan --provider:physical_network physnet2 --provider:segmentation_id " + mgmt_net_vlan + " --shared")
        self.add("echo 'Creating management subnet'")
	self.add("quantum subnet-create " + mgmt_net_name + " " + mgmt_net_cidr)
	self.add('export MGMT_SUBNET_ID=`quantum net-list | grep ' + mgmt_net_name + ' | cut -d "|" -f 4`')
        self.add("echo 'Creating external network'")
        self.add("quantum net-create public --router:external=True")
        self.add('export PUBLIC_NET_ID=`quantum net-list | grep public | cut -d " " -f 2`')
        self.add("echo 'Creating external subnet'")
        self.add("quantum subnet-create --allocation_pool" + 
                 " start=" + public_subnet_start_ip + 
                 ",end=" + public_subnet_end_ip + 
                 " --gateway=" + public_gateway_ip + 
                 " $PUBLIC_NET_ID " + public_subnet_cidr + 
                 " -- --enable_dhcp=False")
        self.add("echo 'Creating router'")
        self.add("quantum router-create externalRouter")
        self.add("quantum router-gateway-set externalRouter $PUBLIC_NET_ID")
	self.add("quantum router-interface-add externalRouter $MGMT_SUBNET_ID")
        self.add('export EXTERNAL_ROUTER_ID=`quantum router-list | grep externalRouter | cut -d " " -f 2`')

        ## We need now to configure again the L3 agent in editing 
        ## /etc/quantum/l3_agent.ini file and modify the values for
        ## router (id from 'quantum router list')
        ## and
        ## external network (id from 'quantum net list')
        self.sed("/^gateway_external_network_id/ s/^/# /", 
                 self.quantum_directory + "/" + self.quantum_l3_agent_filename)
        self.sed("s/^\# gateway_external_network_id.*/gateway_external_network_id=$PUBLIC_NET_ID/",
                 self.quantum_directory + "/" + self.quantum_l3_agent_filename)
        self.sed("/^router_id/ s/^/# /", 
                 self.quantum_directory + "/" + self.quantum_l3_agent_filename)
        self.sed("s/\# router_id.*/router_id=$EXTERNAL_ROUTER_ID/",
                 self.quantum_directory + "/" + self.quantum_l3_agent_filename)
        self.sed("s/^\# use_namespaces.*/use_namespaces = True/", self.quantum_directory + "/" + self.quantum_l3_agent_filename)
        self.add("service quantum-l3-agent restart")
       

        
        self.sed("s/^\# use_namespaces.*/use_namespaces = True/", self.quantum_directory + "/" + self.quantum_dhcp_conf_filename)

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        backup_directory = config.backup_directory

        self.comment("*** Quantum Uninstall ***")

        self.restore(self.quantum_directory, backup_directory, self.quantum_conf_filename)

        self.restore(self.quantum_plugin_directory, backup_directory, \
                        self.quantum_plugin_conf_filename)

        self.restore(self.quantum_directory, backup_directory, \
                        self.quantum_l3_agent_filename)

        self.restore(self.quantum_directory, backup_directory, \
                        self.quantum_dhcp_conf_filename)
