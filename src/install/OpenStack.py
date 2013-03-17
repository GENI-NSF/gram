# Class to generate command files to install OpenStack Folsom
# Per OpenStack Folsum Guide (revised for Ubuntu Precise)

import Glance, Keystone, Nova, OpenVSwitch
import OperatingSystem, Quantum, Configuration

class OpenStack:

    def __init__(self):
        self._config = None


    def createCommands(self, \
                           install_filename="openstack_install.sh", \
                           uninstall_filename="openstack_uninstall.sh", \
                           config_filename = "openstack.conf"):
        
        self._config = Configuration.Configuration(config_filename)
        install_file = open(install_filename, 'w')
        uninstall_file = open(uninstall_filename, 'w')

        operating_system = OperatingSystem.OperatingSystem()
        keystone = Keystone.Keystone()
        glance = Glance.Glance()
        nova = Nova.Nova()
        open_vswitch = OpenVSwitch.OpenVSwitch()
        quantum = Quantum.Quantum()

        self.installerCommands(operating_system, install_file, uninstall_file)
        self.installerCommands(keystone, install_file, uninstall_file)
        self.installerCommands(glance, install_file, uninstall_file)
        self.installerCommands(nova, install_file, uninstall_file)
        self.installerCommands(open_vswitch, install_file, uninstall_file)
        self.installerCommands(quantum, install_file, uninstall_file)

        install_file.close()
        uninstall_file.close()

    def installerCommands(self, installer, install_file, uninstall_file):
        dict = self._config.getParameters()
        installer.installCommands(dict)
        install_commands = installer.getCommands()
        for ic in install_commands:
            install_file.write(ic)
            install_file.write("\n")

        installer.clear()
        installer.uninstallCommands(dict)
        uninstall_commands = installer.getCommands()
        for uc in uninstall_commands:
            uninstall_file.write(uc)
            uninstall_file.write("\n")
                          


if __name__ == "__main__":
    openstack = OpenStack()
    openstack.createCommands()

