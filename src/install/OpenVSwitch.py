from GenericInstaller import GenericInstaller

class OpenVSwitch(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self, params):
        self.comment("*** OpenVSwitch Install ***")

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        self.comment("*** OpenVSwitch Uninstall ***")
