from GenericInstaller import GenericInstaller
from Configuration import Configuration

class RabbitMQ(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self, params):
        self.comment("*** RabbitMQ Install ***")
        self.aptGet("rabbitmq-server")
        rabbit_pwd_var = Configuration.ENV.RABBIT_PASSWORD
        self.add("rabbitmqctl change_password guest $" + rabbit_pwd_var)

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        self.comment("*** RabbitMQ Uninstall ***")
        self.aptGet("rabbitmq-server", True)
