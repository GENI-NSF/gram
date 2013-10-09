from GenericInstaller import GenericInstaller
from gram.am.gram import config

class RabbitMQ(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self):
        self.comment("*** RabbitMQ Install ***")
        #rabbit_pwd = config.rabbit_password
        #self.add("rabbitmqctl change_password guest " + rabbit_pwd)

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self):
        self.comment("*** RabbitMQ Uninstall ***")

