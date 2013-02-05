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

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.openflow import *
from VMOCUtils import *

log = core.getLogger()

class SimpleLearningSwitch(object):

    def __init__(self, connection, write_flowmods):
        self._write_flowmods = write_flowmods
        self._connection = connection

        self._mac_to_port = {}

        connection.addListeners(self)

    # Simple learning switch logic
    # Remember where a given packet came from (src, port)
    # If a packet comes in with an unknwon dest, flood the packet
    def _handle_PacketIn(self, event):

        packet = event.parsed # Ethernet packet

        # Learn that this MAC comes from this port
        src_port = event.port
        src = packet.src
        dst = packet.dst

        if not self._mac_to_port.has_key(src) or self._mac_to_port[src] != src_port:
            log.debug("Learned that " + str(src) + " => " + str(src_port))
            self._mac_to_port[src] = src_port
            log.debug("Map = " + str(self._mac_to_port))

        if not self._mac_to_port.has_key(dst):
            flood_packet(event, self._connection)
        else:
            out_port = self._mac_to_port[dst]
            if self._write_flowmods:
                send_flowmod_for_packet(event, self._connection, packet, out_port)

            send_packet_out(self._connection, event.ofp.buffer_id, \
                                event.ofp.data, src_port, out_port)

    def lookup_port_for_mac(self, mac):
        if self._mac_to_port.has_key(mac):
            return self._mac_to_port[mac]
        else:
            return None
    
             
            

        
