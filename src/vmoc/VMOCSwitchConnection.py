#!/usr/bin/python

#----------------------------------------------------------------------
# Copyright (c) 2013 Raytheon BBN Technologies
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and/or hardware specification (the "Work") to
# deal in the Work without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Work, and to permit persons to whom the Work
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Work.
#
# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
# IN THE WORK.
#----------------------------------------------------------------------

# A connection to a switch, paired with a set of connections to controllers

from pox.core import core
log  = core.getLogger() # Use central logging service

import time
import threading
import pdb
from pox.lib.packet.ethernet import ethernet
from pox.lib.addresses import EthAddr
from pox.lib.packet.vlan import vlan
from pox.openflow import libopenflow_01 as of
from gram.am.gram import config
import VMOCManagementInterface
import VMOCSwitchControllerMap as scmap

class VMOCSwitchConnection(object):
    def __init__(self, connection):
        log.debug("VMOCSwitchConnection.__init__ " + \
                      str(connection))

        self._connection = connection
        self._dpid = connection.dpid
        self._port = connection.sock.getsockname()[1]
        self._packet_cache = {} # Packets by buffer_id
        if connection is not None:
            connection.addListeners(self)

    # Accessor to connection
    def getConnection(self): 
        return self._connection

    def __str__(self):
        return "[VMOCSwitchConnection DPID %x]" % (self._dpid)


    # Handle OF event message received from switch
    def _handle_ConnectionUp(self, event):
        log.debug(str(event))
        # Save the features reply and DPID to identify
        # this connection and allow us to respond to sub-controllers
        # with appropriate features reply
        self._features_reply = event.ofp
        self._dpid = event.dpid
#        We don't pass this along directly, but cache it so we can reply from VMOC
#        when the client requests come in. It is part of the OF startup protocol
#        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_ConnectionDown(self, event):
        log.debug("ConnectionDown " + str(event))
        scmap.remove_switch_connection(self, close_controller_connections=True)

    # Handle OF event message received from switch
    def _handle_PortStatus(self, event):
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_FlowRemoved(self, event):
        self.proocessEvent(event)

    # Handle OF event message received from switch
    def _handle_PacketIn(self, event):
        # Save in packet cache by buffer ID for resolving 
        # packet out from controller
        buffer_id = event.ofp.buffer_id
        self._packet_cache[buffer_id] = {'data':event.data, 'timestamp':time.time()}
        self.processEvent(event, str(event.parsed))

    # Retrieve packet from cache by buffer_id
    # Remove any packets that have been there longer 
    # than BUFFER_CACHE_TIMEOUT
    BUFFER_CACHE_TIMEOUT = 300
    def lookup_packet_by_buffer_id(self, buffer_id):
        packet = None
        if self._packet_cache.has_key(buffer_id):
            packet = self._packet_cache[buffer_id]['data']
        now = time.time()
        for buffer_id in self._packet_cache.keys():
            buffer = self._packet_cache[buffer_id]
            if(now - buffer['timestamp'] > VMOCSwitchConnection.BUFFER_CACHE_TIMEOUT):
                log.debug("Remvoing stale buffer %d " % buffer_id)
                del self._packet_cache[buffer_id]
        return packet

    # Handle OF event message received from switch
    def _handle_ErrorIn(self, event):
        self.processEvent(event)

    # Handle OF event message received from switch
    def _handle_BarrierIn(self, event):
#        self.processEvent(event)
        # Don't pass the Barrier reply from the switch over to the controller
        # We are already handling the handshake between VMOC-as-switch and controller
        # directly.
        pass

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

#        print "forwarding to controller : " + str(event)
        

        # Get list of controllers from VMOC Switch Controller MAP
        controller_conns = scmap.lookup_controllers_for_switch_connection(self)
        if not controller_conns: 
            log.debug("No controller connection : dropping " + str(event))
            return

        if event.ofp.header_type == of.OFPT_PACKET_IN:
            # Send the event to the client controller associated with this slice
            # Based on VLAN
            ethernet_packet = ethernet(raw=event.ofp.data)
            dst=ethernet_packet.dst
            src=ethernet_packet.src
            vlan_id = None
            if ethernet_packet.type == ethernet.VLAN_TYPE:
#                print "EVENT: " + str(event)
                vlan_data = event.ofp.data[ethernet.MIN_LEN:]
                vlan_packet = vlan(vlan_data)
                log.debug("VLAN PACKET : " + str(vlan_packet))
                vlan_id = vlan_packet.id

            # If the switch is a 'VLAN HYBRID', 
            # we will not  get tagged packets but we can use the
            # VLAN asssociated with the port
            port_info = config.vlan_port_map[str(self._port)]
            if not vlan_id and port_info and \
                    bool(port_info['handle_untagged']):
                vlan_id = int(port_info['vlan'])

            matched_controller_conn = None
            for controller_conn in controller_conns:
                if controller_conn.belongsToSlice(vlan_id, src, dst):
                    matched_controller_conn = controller_conn
                    break
            if matched_controller_conn is not None:
                log.debug("Sending packet " + str(event) + " " + str(ethernet_packet) +  " " + str(matched_controller_conn) + " " + str(vlan_id))
                try:
                    matched_controller_conn.send(event.ofp)
                except Exception as e:
                    log.debug("Error writing to controller connection: resetting %s" % e)
                    matched_controller_conn.close()
            else:
                log.debug("Dropping packet : " + str(event) + " " + str(ethernet_packet) + " " + str(vlan_id))
        else:
            # Send every non-packet message directly to each controller
            # And the controller connection will send back every response
            for controller_conn in controller_conns:
#                log.debug("Sending to CC : " + str(event.ofp.header_type))
                controller_conn.send(event.ofp)

    def send(self, msg):
        self._connection.send(msg)
        log.debug("Sent " + " " + str(type(msg)))



