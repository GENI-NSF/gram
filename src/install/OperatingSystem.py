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

