# Class to generate command files to install OpenStack Folsom
# Per OpenStack Folsum Guide (revised for Ubuntu Precise)

import os, errno
import Glance, Keystone, Nova, OpenVSwitch, RabbitMQ, MySQL
import OperatingSystem, Quantum, Configuration, Hypervisor

class OpenStack:

    def __init__(self):
        self._config = None
        self._declarations = None
        self._dict = None

    _CONTROLLER_INSTALLERS = [
        {
            "name": "operating_system", 
            "installer" : OperatingSystem.OperatingSystem() 
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
            "name": "nova",
            "installer": Nova.Nova()
        }, 

        {
            "name": "openvswitch",
            "installer": OpenVSwitch.OpenVSwitch()
        }, 

        {
            "name": "quantum",
            "installer": Quantum.Quantum()
        }
        ]

    _COMPUTE_INSTALLERS = [
        {
            "name": "operating_system", 
            "installer" : OperatingSystem.OperatingSystem() 
        },

        {
            "name": "hypervisor", 
            "installer": Hypervisor.Hypervisor()
        }, 

        {
            "name": "nova", 
            "installer": Nova.Nova()
        },

        {
            "name": "openvswitch", 
            "installer": OpenVSwitch.OpenVSwitch()
        } 
        ]



    def createCommands(self, \
                           installers, 
                           directory, 
                           install_filename,
                           uninstall_filename,
                           config_filename = "openstack.conf"):
        
        self._config = Configuration.Configuration(config_filename)
        self._declarations = self._config.dump()
        self._dict = self._config.getParameters()


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
            module_installer.installCommands(self._dict)
        else:
            module_installer.uninstallCommands(self._dict)
        module_install_commands = module_installer.getCommands()
        module_install_file.write(self._declarations)
        for ic in module_install_commands:
            module_install_file.write(ic)
            module_install_file.write("\n")
        module_install_file.close()
                



if __name__ == "__main__":
    openstack = OpenStack()
    openstack.createCommands(OpenStack._CONTROLLER_INSTALLERS, \
                                 "/tmp/install",
                                 "install_controller.sh", \
                                 "uninstall_controller.sh")
    openstack.createCommands(OpenStack._COMPUTE_INSTALLERS, \
                                 "/tmp/install",
                                 "install_compute.sh", \
                                 "uninstall_compute.sh")

