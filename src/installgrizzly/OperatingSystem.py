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
        self.backup("/etc", config.backup_directory, "ntp.conf")

        # write the interface file
        self.writeToFile('auto lo','interfaces')
        self.appendToFile('iface lo inet loopback\n','interfaces')
        self.appendToFile('# Data network','interfaces')
        self.appendToFile('auto ' + config.data_interface,'interfaces')
        self.appendToFile('iface ' + config.data_interface + ' inet static','interfaces')
        self.appendToFile('address ' + config.data_address,'interfaces')
        self.appendToFile('netmask 255.255.255.0\n','interfaces')

        self.appendToFile('# control network','interfaces')
        self.appendToFile('auto ' + config.control_interface,'interfaces')
        self.appendToFile('iface ' + config.control_interface + ' inet static','interfaces')
        self.appendToFile('address ' + config.control_address,'interfaces')
        self.appendToFile('netmask 255.255.255.0\n','interfaces')

        self.appendToFile('# management network','interfaces')
        self.appendToFile('auto ' + config.management_interface,'interfaces')
        self.appendToFile('iface ' + config.management_interface + ' inet static','interfaces')
        self.appendToFile('address ' + config.management_address,'interfaces')
        self.appendToFile('netmask 255.255.255.0\n','interfaces')

        self.appendToFile('# bridge to external network','interfaces')
        self.appendToFile('auto br-ex','interfaces')
        self.appendToFile('iface br-ex inet static','interfaces')
        self.appendToFile('address '  + config.external_address,'interfaces')
        self.appendToFile('netmask ' + config.external_netmask ,'interfaces')
        self.appendToFile('gateway ' + config.public_gateway_ip, 'interfaces')
        self.appendToFile('dns-nameservers ' + config.public_dns_nameservers, 'interfaces')
        self.appendToFile(' ','interfaces')


        self.appendToFile('#external network','interfaces')
        self.appendToFile('auto ' + config.external_interface,'interfaces')
        self.appendToFile('iface ' + config.external_interface + ' inet manual','interfaces')
        self.appendToFile('up ifconfig $IFACE 0.0.0.0 up','interfaces')
        self.appendToFile('up ip link set $IFACE promisc on','interfaces')
        self.appendToFile('down ip link set $IFACE promisc off','interfaces')
        self.appendToFile('down ifconfig $IFACE down','interfaces')

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

        #self.add("apt-get install -y ubuntu-cloud-keyring")
        #self.add("echo deb http://ubuntu-cloud.archive.canonical.com/ubuntu precise-updates/grizzly main >> grizzly.list")
        #self.add("mv grizzly.list /etc/apt/sources.list.d/")
        #self.add("sudo apt-get -y update && sudo apt-get -y dist-upgrade")
        #self.add("sudo apt-get install gdebi-core")
 
        if self._control_node:
            self.comment("Set up ubuntu cloud keyring")
            self.appendToFile('# Use Ubuntu ntp server as fallback.', '/etc/ntp.conf')
            self.appendToFile('server ntp.ubuntu.com iburst', '/etc/ntp.conf')
            self.appendToFile('server 127.127.1.0','/etc/ntp.conf')
            self.appendToFile('fudge 127.127.1.0 stratum 10', '/etc/ntp.conf')
            # write the interface file

        else:
            self.comment("Set NTP to follow the control node")
            self.sed("s/server 0.ubuntu.pool.ntp.org/#server 0.ubuntu.pool.ntp.org/","/etc/ntp.conf")
            self.sed("s/server 1.ubuntu.pool.ntp.org/#server 1.ubuntu.pool.ntp.org/","/etc/ntp.conf")
            self.sed("s/server 2.ubuntu.pool.ntp.org/#server 2.ubuntu.pool.ntp.org/","/etc/ntp.conf")
            self.sed("s/server 3.ubuntu.pool.ntp.org/#server 3.ubuntu.pool.ntp.org/","/etc/ntp.conf")

 
        self.add('service ntp restart')
        self.comment("Enable IP forwarding")
        backup_directory = config.backup_directory
        self.backup("/etc", backup_directory, "sysctl.conf")
        self.sed('s/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/',
                 '/etc/sysctl.conf')
        self.add("sysctl net.ipv4.ip_forward=1")
        self.add('service networking restart')

        # configure ~/.gcf/gcf_config
        self.sed("s/base_name=geni.*/base_name=geni\/\/" + config.service_token + "\/\/gcf/","/home/gram/.gcf/gcf_config")
        self.sed("s/host=.*/host=" + config.control_host + "/","/home/gram/.gcf/gcf_config")
        self.appendToFile(config.control_host + " " + config.control_host_addr, "/etc/hosts")
        nodes = config.compute_hosts
        for node in nodes:
            self.appendToFile(node + " " + nodes[node],"/etc/hosts")

        self.writeToFile("Defaults:quantum !requiretty", "/etc/sudoers.d/quantum_sudoers")
        self.appendToFile("quantum ALL=NOPASSWD: ALL","/etc/sudoers.d/quantum_sudoers")

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        self.comment("*** OperatingSystem Uninstall ***")
        backup_directory = config.backup_directory
        self.restore("/etc", backup_directory, "sysctl.conf")
        self.restore("/etc", backup_directory, "ntp.conf")

