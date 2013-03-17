from GenericInstaller import GenericInstaller

class Nova(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self, params):
        commands = []
        commands.append(self.comment("*** Nova Install ***"))
        return commands

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        commands = []
        commands.append(self.comment("*** Nova Uninstall ***"))
        return commands
