from GenericInstaller import GenericInstaller

# We assume at this point that these have been completed:
# steps #1 (install Ubuntu) and #2 (configure the network)
# and reboot
class OperatingSystem(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self, params):
        self.comment("*** OperatingSystem Install ***")
        self.comment("Step 2.1: Preparing Ubuntu 12.10")
        self.add("apt-get update")
        self.add("apt-get upgrade")

        self.comment("Step2.3 MySQL and RabbitMQ")
        self.add("apt-get install mysql-server python-mysqldb")
        self.sed('s/127.0.0.1/0.0.0.0/g', '/etc/mysql/my.cnf')
        self.aptGet("rabbitmq-server")
                        

        self.comment("Step 2.4: Configure NTP")
        self.aptGet("ntp")
        self.appendToFile('Use Ubuntu ntp server as fallback.',
                          '/etc/ntp.conf')
        self.appendToFile('server ntp.ubuntu.com iburst', 
                          '/etc/ntp.conf')
        self.appendToFile('server 127.127.1.0','/etc/ntp.conf')
        self.appendToFile('fudge 127.127.1.0 stratum 10', 
                          '/etc/ntp.conf')
        self.add('service ntp restart')

        self.comment("Step 2.5: Others")
        self.aptGet("vlan bridge-utils")
        self.sed('s/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/',
                 '/etc/sysctl.conf')
        self.add("sysctl net.ipv4.ip_forward=1")
        self.add('service networking restart')

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        self.comment("*** OperatingSystem Uninstall ***")
        self.aptGet("mysql-server python-mysqldb", True)
        self.aptGet("vlan bridge-utils ntp", True)

