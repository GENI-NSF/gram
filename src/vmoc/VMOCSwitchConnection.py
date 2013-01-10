# A connection to a switch, paired with a set of connections to controllers

from pox.core import core
log = core.getLogger() # Use central logging service

import threading
import pdb
import VMOCManagementInterface
import VMOCSwitchControllerMap as scmap

class VMOCSwitchConnection(object):
    def __init__(self, connection):
        log.debug("VMOCSwitchConnection.__init__ " + \
                      str(connection))

        self._connection = connection
        if connection is not None:
            connection.addListeners(self)

    # Accessor to connection
    def getConnection(self): 
        return self._connection

    # Handle OF event message received from switch
    def _handle_ConnectionUp(self, event):
        log.debug(str(event))
        # Save the features reply and DPID to identify
        # this connection and allow us to respond to sub-controllers
        # with appropriate features reply
        self._features_reply = event.ofp
        self._dpid = event.dpid
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_ConnectionDown(self, event):
        log.debug("ConnectionDown " + str(event))
        scmap.remove_switch_connection(self)

    # Handle OF event message received from switch
    def _handle_PortStatus(self, event):
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_FlowRemoved(self, event):
        self.proocessEvent(event)

    # Handle OF event message received from switch
    def _handle_PacketIn(self, event):
        self.processEvent(event, str(event.parsed))

    # Handle OF event message received from switch
    def _handle_ErrorIn(self, event):
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_BarrierIn(self, event):
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_RawStatsReply(self, event):
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_SwitchDescReceived(self, event):
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_FlowStatsReceived(self, event):
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_AggregateFlowStatsReceived(self, event):
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_TableStatsReceived(self, event):
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_PortStatsReceived(self, event):
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_QueueStatsReceived(self, event):
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_FlowRemoved(self, event):
        self.processEvent(event)

    def processEvent(self, event, details=""):
#        if hasattr(event, 'ofp'):
#            log.debug("Event " + str(event) + " " + details + " " + 
#                      str(type(event.ofp)))
#        else:
        log.debug("Event " + str(event) + " " + details)
        self.forwardToAppropriateController(event);

    def forwardToAppropriateController(self, event):

        # Get list of controllers from VMOC Switch Controller MAP
        controller_conns = scmap.lookup_controllers_for_switch_connection(self)

        # For now:
        # Send it directly to every registered controller
        # And the controller connection will send back every response
        for controller_conn in controller_conns:
             controller_conn.send(event.ofp)

    def send(self, msg):
        bytes_sent = self._connection.send(msg)
#        log.debug("Sent " + str(bytes_sent) + " bytes")



