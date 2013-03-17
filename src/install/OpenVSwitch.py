from GenericInstaller import GenericInstaller

class OpenVSwitch(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self, params):
        commands = []
        commands.append(self.comment("*** OpenVSwitch Install ***"))
        return commands

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        commands = []
        commands.append(self.comment("*** OpenVSwitch Uninstall ***"))
        return commands
