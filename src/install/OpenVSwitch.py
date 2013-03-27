from GenericInstaller import GenericInstaller
from Configuration import Configuration

class OpenVSwitch(GenericInstaller):

    # Return a list of command strings for installing this component
    def installCommands(self, params):
        self.comment("*** OpenVSwitch Install ***")


        self.comment("Install OVS package")
        self.add("module-assistant auto-install openvswitch-datapath")
        self.aptGet("openvswitch-switch")
        self.add("/etc/init.d/openvswitch-switch start")

        self.comment("Configure virtual bridging")
        self.add("ovs-vsctl add-br br-int")
        self.add("ovs-vsctl add-br br-ex")
        self.add("ovs-vsctl br-set-external-id br-ex bridge-id br-ex")
        self.add("ovs-vsctl add-port br-ex eth2")
        self.add("ovs-vsctl add-br br-eth1")
        self.add("ovs-vsctl add-port br-eth1 eth1")


    # Return a list of command strings for uninstalling this component
    def uninstallCommands(self, params):
        self.comment("*** OpenVSwitch Uninstall ***")
        self.aptGet("openvswitch-switch openvswitch-datapath-source", True)
