# Top level module for VMOC (VLAN-based Multiplexed Openflow Controller)

# VMOC is three things
#   It is a POX controller to an OF switch
#   It is a server for a command interface to add/delete sub-controllers
#   It is a client to sub-controllers (acting as a switch)

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from  VMOCManagementInterface import VMOCManagementInterface 
from VMOCSwitchConnection import VMOCSwitchConnection
import VMOCSwitchControllerMap as scmap
import time
import threading
import pdb

log = core.getLogger() # Use central logging service


class VMOCController(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        log.debug("Connection %s" % (event.connection))
        switch = VMOCSwitchConnection(event.connection)
        scmap.add_switch_connection(switch)


def launch(management_port = 7001, default_controller_url = "https://localhost:9000"):
    log.debug("VMOC.launch");
    core.registerNew(VMOCController)
    # In case we get a string from command line
    management_port = int(management_port) 
    management_interface = VMOCManagementInterface(management_port, default_controller_url)
    management_interface.start()

