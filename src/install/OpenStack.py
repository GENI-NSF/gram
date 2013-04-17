# Class to generate command files to install OpenStack Folsom
# Per OpenStack Folsum Guide (revised for Ubuntu Precise)

import os, errno
from gram.am.gram import config
import Glance, Keystone, Nova, OpenVSwitch, RabbitMQ, MySQL
import OperatingSystem, Quantum,  Hypervisor

class OpenStack:

    def __init__(self):
        pass

    _CONTROL_INSTALLERS = [
        {
            "name": "operating_system_control", 
            "installer" : OperatingSystem.OperatingSystem(control_node=True) 
        },

        {
            "name": "mysql", 
            "installer": MySQL.MySQL()
        }, 

        {
            "name": "rabbitmq", 
            "installer": RabbitMQ.RabbitMQ()
        }, 

        {
            "name": "keystone", 
            "installer": Keystone.Keystone()
        }, 

        {
            "name": "glance", 
            "installer": Glance.Glance()
        }, 

        {
            "name": "nova_control",
            "installer": Nova.Nova(control_node=True)
        }, 

        {
            "name": "openvswitch_control",
            "installer": OpenVSwitch.OpenVSwitch(control_node=True)
        }, 

        {
            "name": "quantum",
            "installer": Quantum.Quantum()
        }
        ]

    _COMPUTE_INSTALLERS = [
        {
            "name": "operating_system_compute", 
            "installer" : OperatingSystem.OperatingSystem(control_node=False) 
        },

        {
            "name": "hypervisor", 
            "installer": Hypervisor.Hypervisor()
        }, 

        {
            "name": "nova_compute", 
            "installer": Nova.Nova(control_node=False)
        },

        {
            "name": "openvswitch_compute", 
            "installer": OpenVSwitch.OpenVSwitch(control_node=False)
        } 
        ]



    def createCommands(self, \
                           installers, 
                           directory, 
                           install_filename,
                           uninstall_filename):
        try:
            os.makedirs(directory)
        except OSError as exc: # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(directory):
                pass
            else: raise
            
        install_file = open(directory + "/" + install_filename, 'w')
        uninstall_file = open(directory + "/" + uninstall_filename, 'w')

        for module in installers:
            module_name = module["name"]
            module_installer = module["installer"]

            install_file.write("%s/install_%s.sh\n" % \
                                   (directory, module_name))
            uninstall_file.write("%s/uninstall_%s.sh\n" % \
                                     (directory, module_name))

            self.installerCommands(directory, module_name, \
                                       module_installer, True)
            self.installerCommands(directory, module_name, \
                                       module_installer, False)

        install_file.close()
        uninstall_file.close()

    def installerCommands(self, dir, module_name, module_installer, install):
        prefix = "install"
        if not install: 
            prefix = "uninstall"

        module_install_file = open("%s/%s_%s.sh" % (dir, prefix, module_name), "w")
        module_installer.clear()
        if install:
            module_installer.installCommands()
        else:
            module_installer.uninstallCommands()
        module_install_commands = module_installer.getCommands()
        for ic in module_install_commands:
            module_install_file.write(ic)
            module_install_file.write("\n")
        module_install_file.close()
                



if __name__ == "__main__":
    config.initialize("/etc/gram/config.json")
    openstack = OpenStack()
    openstack.createCommands(OpenStack._CONTROL_INSTALLERS, \
                                 "/tmp/install",
                                 "install_control.sh", \
                                 "uninstall_control.sh")
    openstack.createCommands(OpenStack._COMPUTE_INSTALLERS, \
                                 "/tmp/install",
                                 "install_compute.sh", \
                                 "uninstall_compute.sh")

