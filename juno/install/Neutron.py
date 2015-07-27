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
import pdb;

class Neutron(GenericInstaller):

    neutron_directory = "/etc/neutron"
    neutron_conf_filename = "neutron.conf"
    saved_neutron_control_conf_filename = "/home/gram/gram/juno/install/control_files/neutron.conf"
    saved_neutron_network_conf_filename = "/home/gram/gram/juno/install/network_files/neutron.conf"
    saved_neutron_compute_conf_filename = "/home/gram/gram/juno/install/compute_files/neutron.conf"
    neutron_plugin_directory = "/etc/neutron/plugins/ml2"
    neutron_plugin_conf_filename = "ml2_conf.ini"
    saved_neutron_control_plugin_conf_filename = "/home/gram/gram/juno/install/control_files/ml2_conf.ini"
    saved_neutron_network_plugin_conf_filename = "/home/gram/gram/juno/install/network_files/ml2_conf.ini"
    saved_neutron_compute_plugin_conf_filename = "/home/gram/gram/juno/install/compute_files/ml2_conf.ini"
    neutron_l3_agent_filename = "l3_agent.ini"
    saved_neutron_l3_agent_filename = "/home/gram/gram/juno/install/network_files/l3_agent.ini"
    neutron_dhcp_conf_filename = "dhcp_agent.ini"
    saved_neutron_dhcp_conf_filename = "/home/gram/gram/juno/install/network_files/dhcp_agent.ini"
    neutron_dnsmasq_conf_filename = "dnsmasq-neutron.conf"
    saved_neutron_dnsmasq_conf_filename = "/home/gram/gram/juno/install/network_files/dnsmasq-neutron.conf"
    neutron_api_conf_filename = "api-paste.ini"
    service_tenant_name = "service"
    neutron_metadata_file = "metadata_agent.ini"
    saved_neutron_metadata_file = "/home/gram/gram/juno/install/network_files/metadata_agent.ini"
    neutron_ext_router_file = "/home/gram/neutron_ext_router"
    neutron_public_net_file = "/home/gram/neutron_public_net"
    neutron_post_install_file = "/home/gram/synch_control_network.sh"

    def __init__(self, control_node, node_type):
        self._control_node = control_node
        self._node_type = node_type

    # Return a list of command strings for installing this component
    def installCommands(self):
        control_address = config.control_address
        control_host = config.control_host
        metadata_port = config.metadata_port
        neutron_user = config.network_user
        neutron_password = config.network_password
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

        #pdb.set_trace()
        if self._node_type == 'control':
            connection = "connection = mysql:\/\/"+ neutron_user + ":" +  neutron_password + "@" + control_host + "\/neutron"  

            self.comment("*** Neutron Install ***")
            self.comment("Configure neutron services")


            self.backup(self.neutron_directory, backup_directory, self.neutron_conf_filename) 
            
            self.add("cp " + self.saved_neutron_control_conf_filename + " " + \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)
            
            self.sed("s/^connection = .*/" + connection + "/",
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)
            
            self.sed("s/^rabbit_host =.*/rabbit_host = " + control_host + "/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)
            
            self.sed("s/^rabbit_password =.*/rabbit_password = " + rabbit_password + "/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)


            self.sed("s/^nova_url =.*/nova_url = http:\/\/" + control_host + ":8774\/v2/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.sed("s/^nova_admin_auth_url =.*/nova_admin_auth_url = http:\/\/" + control_host + ":35357\/v2/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.add("source /etc/novarc")

            self.add("TENANTID=`keystone tenant-list | awk '/ service / { print $2 }'`")
            
            self.sed("s/^nova_admin_tenant_id =.*/nova_admin_tenant_id = ${TENANTID}/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)
            
            self.sed("s/^nova_admin_password =.*/nova_admin_password = " + config.service_password + "/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.sed("s/^auth_uri =.*/auth_uri = http:\/\/" + control_host +":5000\/v2.0/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.sed("s/^identity_uri =.*/identity_uri = http:\/\/" + control_host + ":35357/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.sed("s/^admin_password =.*/admin_password = " + config.service_password + "/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)
            
            self.backup(self.neutron_plugin_directory, backup_directory, self.neutron_plugin_conf_filename) 
            
            self.add("cp " + self.saved_neutron_control_plugin_conf_filename + " " + \
                     self.neutron_plugin_directory + "/" + \
                     self.neutron_plugin_conf_filename)
            
            self.add("su -s /bin/sh -c \"neutron-db-manage --config-file /etc/neutron/neutron.conf " + \
                     "--config-file /etc/neutron/plugins/ml2/ml2_conf.ini upgrade juno\" neutron")

            self.add("service nova-api restart")
            self.add("service nova-scheduler restart")
            self.add("service nova-conductor restart")
            self.add("service neutron-server restart")
            self.add("sleep 5")

            self.add("echo 'Post Creation of Gram Networks - need to sync up control and network'")
            self.add("echo 'Creating management network'")
            self.add("neutron net-create " + mgmt_net_name + " --provider:network_type vlan --provider:physical_network physnet2 --provider:segmentation_id " + mgmt_net_vlan + " --shared")
            self.add("echo 'Creating management subnet'")
            self.add("neutron subnet-create " + mgmt_net_name + " " + mgmt_net_cidr + " --dns-nameservers " + config.public_dns_nameservers)
            self.add('export MGMT_SUBNET_ID=`neutron net-list | grep ' + mgmt_net_name + ' | cut -d "|" -f 4`')
            self.add("echo 'Creating external network'")
            self.add("neutron net-create public --router:external=True")
            self.add('export PUBLIC_NET_ID=`neutron net-list | grep public | cut -d " " -f 2`')
            self.add("echo 'Creating external subnet'")
            self.add("neutron subnet-create --allocation_pool" + 
                     " start=" + public_subnet_start_ip + 
                     ",end=" + public_subnet_end_ip + 
                     " --gateway=" + public_gateway_ip + 
                     " $PUBLIC_NET_ID " + public_subnet_cidr + 
                     " -- --enable_dhcp=False")
            self.add("echo 'Creating router'")
            self.add("neutron router-create externalRouter")
            self.add("neutron router-gateway-set externalRouter $PUBLIC_NET_ID")
            self.add("neutron router-interface-add externalRouter $MGMT_SUBNET_ID")
            self.add('export EXTERNAL_ROUTER_ID=`neutron router-list | grep externalRouter | cut -d " " -f 2`')

            #need to add the next 2 fields into the l3_agent file config file -RRH
            self.add('ssh gram@' + config.network_host_addr + ' "echo $EXTERNAL_ROUTER_ID >' + self.neutron_ext_router_file + '"')
            self.add('ssh gram@' + config.network_host_addr + ' "echo $PUBLIC_NET_ID > ' + self.neutron_public_net_file + '"')
            #want to sed this value into the config.json file

            #this value needs to be put into the config.json for mgmt_ns - RRH
            #self.appendToFile('ssh gram@' + config.network_host_addr + '" ip netns | grep qrouter "', self.neutron_post_install_file)

            ## We need now to configure again the L3 agent in editing 
            ## /etc/neutron/l3_agent.ini file and modify the values for
            ## router (id from 'neutron router list')
            ## and
            ## external network (id from 'neutron net list')

            #RRH - need to fill this in with the externalRouter id
            #ssh gram@network_host_addr "echo ` neutron router-list |  awk '/ externalRouter / { print $2 }'` > ~/netlist"
            #self.sed("s/^router_id =.*/router_id = " + config.data_address + "/", \
            #         self.neutron_directory + "/" + \
            #         self.neutron_l3_agent_filename)


            #RRH - need to fill this in with the public network id
            #ssh gram@network_host_addr "echo ` neutron net-list |  awk '/ public / { print $2 }'` > ~/rtrlist"
            #self.sed("s/^gateway_external_network_id =.*/gateway_external_network_id = " + config.data_address + "/", \
            #         self.neutron_directory + "/" + \
            #         self.neutron_l3_agent_filename)

            #ssh gram@network_host_addr ip netns | grep qrouter


        elif self._node_type == 'compute':
            self.comment("*** Neutron Compute ***")
            self.backup(self.neutron_directory, backup_directory, self.neutron_conf_filename) 
            self.add("cp " + self.saved_neutron_compute_conf_filename + " " + \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.sed("s/^rabbit_host =.*/rabbit_host = " + control_host + "/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)
            
            self.sed("s/^rabbit_password =.*/rabbit_password = " + rabbit_password + "/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.sed("s/^auth_uri =.*/auth_uri = http:\/\/" + control_host +":5000\/v2.0/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.sed("s/^identity_uri =.*/identity_uri = http:\/\/" + control_host + ":35357/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.sed("s/^admin_password =.*/admin_password = " + config.service_password + "/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.comment("*** Plugin ML2 Conf ***")

            self.backup(self.neutron_plugin_directory, backup_directory, self.neutron_plugin_conf_filename) 
            
            self.add("cp " + self.saved_neutron_compute_plugin_conf_filename + " " + \
                     self.neutron_plugin_directory + "/" + \
                     self.neutron_plugin_conf_filename)

            self.sed("s/^local_ip =.*/local_ip = " + config.data_address + "/", \
                     self.neutron_plugin_directory + "/" + \
                     self.neutron_plugin_conf_filename)

            self.sed("s/^network_vlan_ranges.*/network_vlan_ranges=physnet1:1000:2100,physnet2:2101:3000/",
                     self.neutron_plugin_directory + "/" + \
                     self.neutron_plugin_conf_filename)

            self.sed("s/^bridge_mappings.*/bridge_mappings=external:br-ex,physnet1:br-" + config.data_interface + ",physnet2:br-" + config.management_interface + "/",
                     self.neutron_plugin_directory + "/" + \
                     self.neutron_plugin_conf_filename)


            self.add("service openvswitch-switch restart")
            self.add("service nova-compute restart")
            self.add("service neutron-plugin-openvswitch-agent restart")

        else:
            self.comment("*** Neutron Network Node Install ***")
            self.comment("*** Neutron Conf ***")
            self.backup(self.neutron_directory, backup_directory, self.neutron_conf_filename) 
            self.add("cp " + self.saved_neutron_network_conf_filename + " " + \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.sed("s/^rabbit_host =.*/rabbit_host = " + control_host + "/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)
            
            self.sed("s/^rabbit_password =.*/rabbit_password = " + rabbit_password + "/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.sed("s/^auth_uri =.*/auth_uri = http:\/\/" + control_host +":5000\/v2.0/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.sed("s/^identity_uri =.*/identity_uri = http:\/\/" + control_host + ":35357/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.sed("s/^admin_password =.*/admin_password = " + config.service_password + "/", \
                     self.neutron_directory + "/" + \
                     self.neutron_conf_filename)

            self.comment("*** Plugin ML2 Conf ***")

            self.backup(self.neutron_plugin_directory, backup_directory, self.neutron_plugin_conf_filename) 
            
            self.add("cp " + self.saved_neutron_network_plugin_conf_filename + " " + \
                     self.neutron_plugin_directory + "/" + \
                     self.neutron_plugin_conf_filename)

            self.sed("s/^local_ip =.*/local_ip = " + config.data_address + "/", \
                     self.neutron_plugin_directory + "/" + \
                     self.neutron_plugin_conf_filename)

            self.sed("s/^network_vlan_ranges.*/network_vlan_ranges=physnet1:1000:2100,physnet2:2101:3000/",
                     self.neutron_plugin_directory + "/" + \
                     self.neutron_plugin_conf_filename)

            self.sed("s/^bridge_mappings.*/bridge_mappings=external:br-ex,physnet1:br-" + config.data_interface + ",physnet2:br-" + config.management_interface + "/",
                     self.neutron_plugin_directory + "/" + \
                     self.neutron_plugin_conf_filename)

            self.backup(self.neutron_directory, backup_directory, self.neutron_l3_agent_filename) 
            
            self.add("cp " + self.saved_neutron_l3_agent_filename + " " + \
                     self.neutron_directory + "/" + \
                     self.neutron_l3_agent_filename)

            ## We need now to configure again the L3 agent in editing 
            ## /etc/neutron/l3_agent.ini file and modify the values for
            ## router (id from 'neutron router list')
            ## and
            ## external network (id from 'neutron net list')

            #RRH - need to fill this in with the externalRouter id
            #ssh gram@network_host_addr "echo ` neutron router-list |  awk '/ externalRouter / { print $2 }'` > ~/netlist"
            #self.sed("s/^router_id =.*/router_id = " + ~/neutron_rtr+ "/", \
            #         self.neutron_directory + "/" + \
            #         self.neutron_l3_agent_filename)


            #RRH - need to fill this in with the public network id
            #ssh gram@network_host_addr "echo ` neutron net-list |  awk '/ public / { print $2 }'` > ~/rtrlist"
            #self.sed("s/^gateway_external_network_id =.*/gateway_external_network_id = " + config.data_address + "/", \
            #         self.neutron_directory + "/" + \
            #         self.neutron_l3_agent_filename)

            #ssh gram@network_host_addr ip netns | grep qrouter

            self.backup(self.neutron_directory, backup_directory, self.neutron_dhcp_conf_filename) 
            
            self.add("cp " + self.saved_neutron_dhcp_conf_filename + " " + \
                     self.neutron_directory + "/" + \
                     self.neutron_dhcp_conf_filename)

            self.backup(self.neutron_directory, backup_directory, self.neutron_dnsmasq_conf_filename) 
            
            self.add("cp " + self.saved_neutron_dnsmasq_conf_filename + " " + \
                     self.neutron_directory + "/" + \
                     self.neutron_dnsmasq_conf_filename)

            self.add("pkill dnsmasq")

            self.backup(self.neutron_directory, backup_directory, self.neutron_metadata_file) 
            
            self.add("cp " + self.saved_neutron_metadata_file + " " + \
                     self.neutron_directory + "/" + \
                     self.neutron_metadata_file)

            self.sed("s/^auth_url =.*/auth_url = http:\/\/" + control_host +":5000\/v2.0/", \
                     self.neutron_directory + "/" + \
                     self.neutron_metadata_file)

            self.sed("s/^admin_password =.*/admin_password = " + config.service_password + "/", \
                     self.neutron_directory + "/" + \
                     self.neutron_metadata_file)

            self.sed("s/^nova_metadata_ip =.*/nova_metadata_ip = " + control_host +"/", \
                     self.neutron_directory + "/" + \
                     self.neutron_metadata_file)

            self.add("service openvswitch-switch restart")
            self.add("service neutron-plugin-openvswitch-agent restart")
            self.add("service neutron-l3-agent restart")
            self.add("service neutron-dhcp-agent restart")
            self.add("service neutron-metadata-agent restart")

            self.writeToFile("Post Creation of Gram Networks - need to sync up control and network", self.neutron_post_install_file)
            self.sed("s/^router_id =.*/router_id = `cat " + self.neutron_ext_router_file + "`/", \
                     self.neutron_directory + "/" + \
                     self.neutron_l3_agent_filename)

            self.sed("s/^gateway_external_network_id =.*/gateway_external_network_id = `cat " + self.neutron_public_net_file + "`/", \
                     self.neutron_directory + "/" + \
                     self.neutron_l3_agent_filename)



        #self.add("for i in `seq 1 30`; do")
        #self.add("  echo 'checking neutron status'")
        #self.add("  neutron net-list > /dev/null")
        #self.add("  if [ $? -eq 0 ]; then")
        #self.add("    break")
        #self.add("  fi") 
        #self.add("  sleep .5")
        #self.add("done")


    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        backup_directory = config.backup_directory

        self.comment("*** Neutron Uninstall ***")

        self.restore(self.neutron_directory, backup_directory, self.neutron_conf_filename)

        self.restore(self.neutron_plugin_directory, backup_directory, \
                        self.neutron_plugin_conf_filename)

        self.restore(self.neutron_directory, backup_directory, \
                        self.neutron_l3_agent_filename)

        self.restore(self.neutron_directory, backup_directory, \
                        self.neutron_dhcp_conf_filename)
