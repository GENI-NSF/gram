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
    
             
            

        
