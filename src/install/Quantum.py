from GenericInstaller import GenericInstaller

class Quantum(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self, params):
        self.comment("*** Quantum Install ***")

    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        self.comment("*** Quantum Uninstall ***")

