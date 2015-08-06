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
import os
import socket

# We assume at this point that these have been completed:
# steps #1 (install Ubuntu) and #3 (configure the network)
# and reboot
class OperatingSystem(GenericInstaller):

    def __init__(self, control_node, node_type):
        self._control_node = control_node
        self._node_type = node_type
        self.omni_config = "/home/gram/.gcf/omni_config" 

    # Return a list of command strings for installing this component
    def installCommands(self):
        self.comment("*** OperatingSystem Install ***")
        self.comment("Step 2. Add repository and upgrade Ubuntu")
        self.backup("/etc", config.backup_directory, "ntp.conf")
        self.backup("/etc", config.backup_directory, "hosts")
        self.backup("/etc/network", config.backup_directory, "interfaces")
 
        #self.add("apt-get install -y ubuntu-cloud-keyring")
        #self.add("echo deb http://ubuntu-cloud.archive.canonical.com/ubuntu precise-updates/grizzly main >> grizzly.list")
        #self.add("mv grizzly.list /etc/apt/sources.list.d/")
        #self.add("sudo apt-get -y update && sudo apt-get -y dist-upgrade")
        #self.add("sudo apt-get install gdebi-core")
 

        if self._node_type == 'control':
            self.comment("Set up ntp")
            self.appendToFile('# Use Ubuntu ntp server as fallback.', '/etc/ntp.conf')
            self.appendToFile('server ntp.ubuntu.com iburst', '/etc/ntp.conf')
            self.appendToFile('server 127.127.1.0','/etc/ntp.conf')
            self.appendToFile('fudge 127.127.1.0 stratum 10', '/etc/ntp.conf')
            # write the interface file

            #deal with monitoring
            self.comment("Set up Monitoring")
            self.sed("s/\/usr\/local\/ops-monitoring/\/home\/gram\/ops-monitoring/",'/home/gram/ops-monitoring/local/wsgi/localstore.wsgi')
            self.sed("s/^dbtype:.*$/dbtype: mysql/",'/home/gram/ops-monitoring/config/local_datastore_operator.conf')
            self.sed("s/^database:.*$/database: monitoring/",'/home/gram/ops-monitoring/config/local_datastore_operator.conf')
            self.sed("s/^username:.*$/username: neutron/",'/home/gram/ops-monitoring/config/local_datastore_operator.conf')
            self.sed("s/^password:.*$/password: " + config.network_password + "/",'/home/gram/ops-monitoring/config/local_datastore_operator.conf')
            self.add('sudo a2enmod ssl')
            self.add('sudo a2ensite default-ssl');

            # configure ~/.gcf/gcf_config
            self.sed("s/base_name=geni.*/base_name=geni\/\/" + config.control_host + "\/\/gcf/","/home/gram/.gcf/gcf_config")
            self.sed("s/host=.*/host=" + config.external_address + "/","/home/gram/.gcf/gcf_config")

            # create an omni config file
            self.writeToFile("[omni]",self.omni_config)
            self.appendToFile("users = gramuser", self.omni_config)
            self.appendToFile("default_cf = my_gcf", self.omni_config)
            self.appendToFile("[my_gcf]",self.omni_config)
            self.appendToFile("type=gcf",self.omni_config)
            self.appendToFile("authority=geni:" + config.control_host + ":gcf",self.omni_config)
            self.appendToFile("cert=~/.gcf/gramuser-cert.pem", self.omni_config)
            self.appendToFile("key=~/.gcf/gramuser-key.pem", self.omni_config)
            self.appendToFile("ch = https://" + config.external_address + ":8000", self.omni_config)
            self.appendToFile("sa = https://" + config.external_address + ":8000", self.omni_config)
            self.appendToFile("[gramuser]", self.omni_config)
            self.appendToFile("urn=urn:publicid:IDN+geni:" + config.control_host + ":gcf+user+gramuser", self.omni_config)
            self.appendToFile("keys=~/.ssh/id_rsa.pub", self.omni_config)
            self.appendToFile("[aggregate_nicknames]", self.omni_config)
            self.appendToFile("gram=,https://" + config.external_address + ":5001", self.omni_config)
        
            # generate  credentials for this user
            #RRH - do we need this - we ask people to do it again later
            self.add("/opt/gcf/src/gen-certs.py --exp -u gramuser") 



        elif self._node_type == 'compute':
            self.comment("Set NTP to follow the control node")
            self.sed("s/server 0.ubuntu.pool.ntp.org/#server 0.ubuntu.pool.ntp.org/","/etc/ntp.conf")
            self.sed("s/server 1.ubuntu.pool.ntp.org/#server 1.ubuntu.pool.ntp.org/","/etc/ntp.conf")
            self.sed("s/server 2.ubuntu.pool.ntp.org/#server 2.ubuntu.pool.ntp.org/","/etc/ntp.conf")
            self.sed("s/server 3.ubuntu.pool.ntp.org/#server 3.ubuntu.pool.ntp.org/","/etc/ntp.conf")

            self.comment("Sysctl Conf")
            backup_directory = config.backup_directory
            self.backup("/etc", backup_directory, "sysctl.conf")
            self.sed("s/^#net.ipv4.conf.all.rp_filter.*/net.ipv4.conf.all.rp_filter=0/", "/etc/sysctl.conf")
            self.sed("s/^#net.ipv4.conf.default.rp_filter.*/net.ipv4.conf.default.rp_filter=0/", "/etc/sysctl.conf")
            self.add("sudo sysctl -p")


            self.comment("Getting Python pip to install psutil for monitoring")
        else: #node  type == 'network'
            self.comment("Set NTP to follow the control node")
            self.sed("s/server 0.ubuntu.pool.ntp.org/#server 0.ubuntu.pool.ntp.org/","/etc/ntp.conf")
            self.sed("s/server 1.ubuntu.pool.ntp.org/#server 1.ubuntu.pool.ntp.org/","/etc/ntp.conf")
            self.sed("s/server 2.ubuntu.pool.ntp.org/#server 2.ubuntu.pool.ntp.org/","/etc/ntp.conf")
            self.sed("s/server 3.ubuntu.pool.ntp.org/#server 3.ubuntu.pool.ntp.org/","/etc/ntp.conf")

            self.comment("Sysctl Conf")
            self.comment("Enable IP forwarding")
            backup_directory = config.backup_directory
            self.backup("/etc", backup_directory, "sysctl.conf")

            self.sed("s/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/", "/etc/sysctl.conf")
            self.sed("s/^#net.ipv4.conf.all.rp_filter.*/net.ipv4.conf.all.rp_filter=0/", "/etc/sysctl.conf")
            self.sed("s/^#net.ipv4.conf.default.rp_filter.*/net.ipv4.conf.default.rp_filter=0/", "/etc/sysctl.conf")
            self.add("sudo sysctl -p")

            self.comment("Getting Python pip to install psutil for monitoring")


        self.add("sudo apt-get install python-dev python-pip expect")
        self.add("sudo pip install psutil")
        self.add("sudo pip install flask")

 
        self.add('service ntp restart')


        # set up the /etc/hosts file
        self.appendToFile(config.external_address + " " + socket.getfqdn() + " " + socket.gethostname(), "~/hosts")
        #what is this for
        #self.appendToFile("", "\etc\hosts")
        self.appendToFile(" ", "~/hosts")
        self.appendToFile("::1     localhost ip6-localhost ip6-loopback", "~/hosts")
        self.appendToFile("fe00::0 ip6-localne", "~/hosts")
        self.appendToFile("ff00::0 ip6-mcastprefix", "~/hosts")
        self.appendToFile("ff02::1 ip6-allnodes", "~/hosts")
        self.appendToFile("ff02::2 ip6-allrouters", "~/hosts")
        #nodes = config.compute_hosts
        #for node in nodes:
        #    self.appendToFile(nodes[node] + " " + node,"~/hosts")



        # add these entries to satisfy omni/portal
        nodes = config.host_file_entries
        for node in nodes:
            self.appendToFile(nodes[node] + "\t" + node,"~/hosts")


        self.add("sudo cp ~/hosts /etc/hosts")

        #RRH - neutron installs something itself
        #self.writeToFile("Defaults:neutron !requiretty", "/etc/sudoers.d/neutron_sudoers")
        #self.appendToFile("neutron ALL=NOPASSWD: ALL","/etc/sudoers.d/neutron_sudoers")

        self.writeToFile('Defaults:gram !requiretty', "/etc/sudoers.d/gram_sudoers")
        self.appendToFile('gram ALL = (root) NOPASSWD: /usr/local/bin/gram_ssh_proxy, /*/ip, /usr/sbin/service, /home/gram/gram/src/install/network_files/synch_control_network.sh',"/etc/sudoers.d/gram_sudoers")


        # write the interface file
        self.writeToFile('auto lo','interfaces')
        self.appendToFile('iface lo inet loopback','interfaces')
        self.appendToFile('# Data network','interfaces')
        self.appendToFile('auto ' + config.data_interface,'interfaces')
        self.appendToFile('iface ' + config.data_interface + ' inet static','interfaces')
        self.appendToFile('address ' + config.data_address,'interfaces')
        self.appendToFile('netmask 255.255.255.0','interfaces')

        self.appendToFile('# control network','interfaces')
        self.appendToFile('auto ' + config.control_interface,'interfaces')
        self.appendToFile('iface ' + config.control_interface + ' inet static','interfaces')
        self.appendToFile('address ' + config.control_address,'interfaces')
        self.appendToFile('netmask 255.255.255.0','interfaces')

        self.appendToFile('# management network','interfaces')
        self.appendToFile('auto ' + config.management_interface,'interfaces')
        self.appendToFile('iface ' + config.management_interface + ' inet static','interfaces')
        self.appendToFile('address ' + config.management_address,'interfaces')
        self.appendToFile('netmask 255.255.255.0','interfaces')

        if self._node_type == 'control':
            self.appendToFile('# external network','interfaces')
            self.appendToFile('auto ' + config.external_interface,'interfaces')
            self.appendToFile('iface ' + config.external_interface + ' inet static','interfaces')
            self.appendToFile('address ' + config.external_address,'interfaces')
            self.appendToFile('netmask ' + config.external_netmask,'interfaces')
            self.appendToFile('gateway ' + config.public_gateway_ip, 'interfaces')
            self.appendToFile('dns-nameservers ' + config.public_dns_nameservers, 'interfaces')
            self.appendToFile(' ','interfaces')

            self.add('sudo mv interfaces /etc/network/interfaces')
            self.add('sudo ifdown ' + config.control_interface)
            self.add('sudo ifdown ' + config.data_interface)
            self.add('sudo ifdown ' + config.management_interface)
            self.add('sudo ifdown ' + config.external_interface)
            self.add('sudo service networking restart')
            self.add('sudo ifup ' + config.control_interface)
            self.add('sudo ifup ' + config.data_interface)
            self.add('sudo ifup ' + config.management_interface)
            self.add('sudo ifup ' + config.external_interface)


        else:

            self.appendToFile('#external network','interfaces')
            self.appendToFile('auto ' + config.external_interface,'interfaces')
            self.appendToFile('iface ' + config.external_interface + ' inet manual','interfaces')
            self.appendToFile('up ifconfig $IFACE 0.0.0.0 up','interfaces')
            self.appendToFile('up ip link set $IFACE promisc on','interfaces')
            self.appendToFile('down ip link set $IFACE promisc off','interfaces')
            self.appendToFile('down ifconfig $IFACE down','interfaces')


            self.appendToFile('# bridge to external network','interfaces')
            self.appendToFile('auto br-ex','interfaces')
            self.appendToFile('iface br-ex inet static','interfaces')
            self.appendToFile('address '  + config.external_address,'interfaces')
            self.appendToFile('netmask ' + config.external_netmask ,'interfaces')
            self.appendToFile('gateway ' + config.public_gateway_ip, 'interfaces')
            self.appendToFile('dns-nameservers ' + config.public_dns_nameservers, 'interfaces')
            self.appendToFile(' ','interfaces')

            #self.add("module-assistant auto-install openvswitch-datapath")
            #self.add("/etc/init.d/openvswitch-switch start")

            self.add('ovs-vsctl add-br br-int')
            self.add('ovs-vsctl add-br br-ex')
            self.add('ovs-vsctl add-port br-ex ' + config.external_interface)

            self.add('ovs-vsctl add-br br-' + config.management_interface)
            self.add('ovs-vsctl add-port br-' + config.management_interface + ' ' + config.management_interface) 

            self.add('ovs-vsctl add-br br-' + config.data_interface)
            self.add('ovs-vsctl add-port br-' + config.data_interface + ' ' + config.data_interface)

            self.add('mv interfaces /etc/network/interfaces')
            self.add('sudo ifdown ' + config.control_interface)
            self.add('sudo ifdown ' + config.data_interface)
            self.add('sudo ifdown ' + config.management_interface)
            self.add('sudo ifdown ' + config.external_interface)
            self.add('sudo service networking restart')
            self.add('sudo ifup ' + config.control_interface)
            self.add('sudo ifup ' + config.data_interface)
            self.add('sudo ifup ' + config.management_interface)
            self.add('sudo ifup ' + config.external_interface)
            self.add('sudo ifup br-ex')


        self.sed("s/managed=false/managed=true/",'/etc/NetworkManager/NetworkManager.conf')
        self.add("sudo apt-get remove --purge network-manager")



    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        self.comment("*** OperatingSystem Uninstall ***")
        backup_directory = config.backup_directory
        self.restore("/etc", backup_directory, "sysctl.conf")
        self.restore("/etc", backup_directory, "ntp.conf")

