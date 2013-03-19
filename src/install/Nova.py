from GenericInstaller import GenericInstaller

class Nova(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self, params):
        self.comment("*** Nova Install ***")

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        self.comment("*** Nova Uninstall ***")
