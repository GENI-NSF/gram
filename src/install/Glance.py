from GenericInstaller import GenericInstaller

class Glance(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self, params):
        commands = []
        commands.append(self.comment("*** Glance Install ***"))
        return commands

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        commands = []
        commands.append(self.comment("*** Glance Uninstall ***"))
        return commands
